"""Map a job title or job ad to O*NET occupations and tasks, with observed AI usage per task.

Standard library only, so the same file runs in the browser (Pyodide) and in CI.

- Occupations are searched two ways: by title (official title + alternate titles) and by
  content (description + task statements), with TF-IDF word matching. The final score is
  TITLE_WEIGHT x title match + (1 - TITLE_WEIGHT) x content match. TITLE_WEIGHT was picked on
  the development half of O*NET's reported job titles (scripts/tune.py), never the test half.
- For the chosen occupation, every task is listed with the Anthropic Economic Index figures
  for May 2026: the share of Claude.ai conversations matched to that task, worldwide and in
  South Africa, and how those conversations split between automation and augmentation.
  A task with no figure wasn't published (too few conversations), which is not the same as zero.
- If you paste a job ad, each task is also checked against the ad's clauses (split on full stops,
  commas, semicolons and "and"). A task counts as in the ad if a clause shares at least two words
  with it and matches it at least AD_MATCH well, so you can see which tasks the ad asks for.

Usage shares describe how people use Claude. They say nothing about job risk.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict

TITLE_WEIGHT = 0.7
TEST_SHARE = 50  # percent of reported titles held out for the test half
AD_MATCH = 0.30  # a task counts as "in the ad" if a sentence of the ad matches it at least this well
STOP = set("""a an and or of the for with without to in on at by from as is are be this that these those other
    such including include may also using use used etc all any each who which their your our you we they it its
    job role position work working team company candidate candidates experience years year looking seeking
    ability able strong excellent good great responsible responsibilities requirement requirements""".split())
WORD = re.compile(r"[a-z0-9]+")


def stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("es") and w[:-2].endswith(("s", "x", "ch", "sh")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def words(text: str) -> list[str]:
    return [stem(w) for w in WORD.findall((text or "").lower()) if len(w) > 1 and w not in STOP]


def _idf(docs: list[list[str]]) -> dict[str, float]:
    df = Counter()
    for d in docs:
        df.update(set(d))
    n = len(docs)
    return {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}


def _vec(toks: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = Counter(t for t in toks if t in idf)
    v = {t: (1 + math.log(c)) * idf[t] for t, c in tf.items()}
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: x / norm for t, x in v.items()}


class _Field:
    def __init__(self, docs: list[list[str]]):
        self.idf = _idf(docs)
        self.post: dict[str, list[tuple[int, float]]] = defaultdict(list)
        for i, d in enumerate(docs):
            for t, w in _vec(d, self.idf).items():
                self.post[t].append((i, w))

    def scores(self, toks: list[str]) -> dict[int, float]:
        out: dict[int, float] = defaultdict(float)
        for t, w in _vec(toks, self.idf).items():
            for i, x in self.post.get(t, ()):
                out[i] += w * x
        return out


def is_test(title: str) -> bool:
    return int(hashlib.sha1(title.lower().encode()).hexdigest(), 16) % 100 < TEST_SHARE


class Mapper:
    def __init__(self, snap: dict):
        self.occ = snap["occupations"]
        self.aei = snap["aei"]
        self.titles = _Field([words(" ".join([o["title"]] * 2 + o["alt"])) for o in self.occ])
        self.content = _Field([words(o["desc"] + " " + " ".join(t[1] for t in o["tasks"])) for o in self.occ])

    def search(self, text: str, k: int = 5) -> list[tuple[int, float]]:
        toks = words(text)
        ts, cs = self.titles.scores(toks), self.content.scores(toks)
        scores = {i: TITLE_WEIGHT * ts.get(i, 0.0) + (1 - TITLE_WEIGHT) * cs.get(i, 0.0) for i in set(ts) | set(cs)}
        ranked = sorted(scores, key=lambda i: (-scores[i], self.occ[i]["code"]))[:k]
        return [(i, round(scores[i], 4)) for i in ranked]

    def tasks(self, i: int, ad_text: str = "") -> dict:
        o = self.occ[i]
        # compare tasks with clauses, not whole sentences: ads pack several duties into one sentence
        sentences = [s for s in re.split(r"(?<=[.!?;:,])\s+|\n+|•|\s+and\s+", ad_text or "") if len(words(s)) >= 2]
        idf = self.content.idf
        sent_vecs = [(s.strip(), _vec(words(s), idf)) for s in sentences]
        rows = []
        for task_id, text, core in o["tasks"]:
            a = self.aei.get(str(task_id), {})
            best, best_s = 0.0, None
            if sent_vecs:
                tv = _vec(words(text), idf)
                for s, sv in sent_vecs:
                    if len(set(tv) & set(sv)) < 2:  # one shared word ("writer", "billing") isn't enough
                        continue
                    sim = sum(w * sv.get(t, 0.0) for t, w in tv.items())
                    if sim > best:
                        best, best_s = sim, s
            rows.append({"id": task_id, "task": text, "core": core,
                         "global_pct": a.get("global_pct"), "za_pct": a.get("za_pct"),
                         "automation": a.get("global_auto"), "augmentation": a.get("global_aug"),
                         "in_ad": best >= AD_MATCH, "ad_sentence": best_s if best >= AD_MATCH else None,
                         "ad_match": round(best, 3)})
        rows.sort(key=lambda r: (-(r["global_pct"] if r["global_pct"] is not None else -1), not r["core"], r["id"]))
        published = [r for r in rows if r["global_pct"] is not None]
        return {
            "code": o["code"], "title": o["title"], "desc": o["desc"], "tasks": rows,
            "n_tasks": len(rows), "n_published": len(published),
            "n_with_share": sum(1 for r in published if r["global_pct"] > 0),
            "share_sum": round(sum(r["global_pct"] for r in published), 2),
            "n_in_ad": sum(r["in_ad"] for r in rows),
        }


def evaluate(mapper: Mapper, titles: list[list[str]], half: str = "test") -> dict:
    """Reported job title -> does the right occupation come back first / in the top 3?"""
    chosen = [(t, c) for t, c in titles if is_test(t) == (half == "test")]
    top1 = top3 = soc1 = 0
    misses = []
    for title, code in chosen:
        hits = [mapper.occ[i]["code"] for i, _ in mapper.search(title, k=3)]
        top1 += bool(hits) and hits[0] == code
        top3 += code in hits
        soc1 += bool(hits) and hits[0][:7] == code[:7]
        if hits and hits[0] != code and len(misses) < 400:
            misses.append([title, code, hits[0]])
    n = len(chosen)
    return {"half": half, "n": n, "top1": round(top1 / n, 4), "top3": round(top3 / n, 4),
            "same_soc": round(soc1 / n, 4), "chance": round(1 / len(mapper.occ), 4), "misses": misses}
