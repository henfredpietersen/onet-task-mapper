"""Build data/onet.json from O*NET 30.0 and the Anthropic Economic Index (June 2026 release).

    python scripts/make_snapshot.py --onet db_30_0_text.zip --aei aei_claude_ai_2026-06-26.csv

Run by .github/workflows/snapshot.yml, which downloads both files on GitHub's servers.

O*NET (CC BY 4.0, U.S. Department of Labor/Employment and Training Administration):
occupations, task statements, alternate titles, and the job titles incumbents reported
("Sample of Reported Titles", used only to test the occupation matcher).

Anthropic Economic Index (CC-BY): for each O*NET task, the share of Claude.ai conversations
in the month that were matched to it ("pct"), worldwide and for South Africa, plus the share of
those conversations classed as automation or augmentation (worldwide). The Index only publishes
a cell above its aggregation thresholds, so a missing task means "not published", not zero.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ONET_URL = "https://www.onetcenter.org/dl_files/database/db_30_0_text.zip"
AEI_URL = ("https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/"
           "release_2026_06_26/data/aei_claude_ai_2026-06-26.csv")
MAX_ALT_TITLES = 25
GEOS = {"GLOBAL": "global", "ZAF": "za"}
METRICS = {"pct", "collaboration_bucket_automation_pct", "collaboration_bucket_augmentation_pct"}

csv.field_size_limit(sys.maxsize)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_tsv(z: zipfile.ZipFile, suffix: str) -> list[dict]:
    name = next(n for n in z.namelist() if n.endswith("/" + suffix))
    text = z.read(name).decode("utf-8", "replace")
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


def load_onet(path: Path) -> tuple[list[dict], list[list[str]]]:
    with zipfile.ZipFile(path) as z:
        occ = read_tsv(z, "Occupation Data.txt")
        tasks = read_tsv(z, "Task Statements.txt")
        alts = read_tsv(z, "Alternate Titles.txt")
        reported = read_tsv(z, "Sample of Reported Titles.txt")
    by_code_tasks = defaultdict(list)
    for t in tasks:
        by_code_tasks[t["O*NET-SOC Code"]].append([int(t["Task ID"]), t["Task"].strip(), t["Task Type"] == "Core"])
    reported_set = {(r["O*NET-SOC Code"], r["Reported Job Title"].strip().lower()) for r in reported}
    by_code_alt = defaultdict(list)
    for a in alts:
        code, title = a["O*NET-SOC Code"], a["Alternate Title"].strip()
        # Titles that are also in the reported-titles test set are left out, so the test is fair.
        if (code, title.lower()) in reported_set:
            continue
        if len(by_code_alt[code]) < MAX_ALT_TITLES:
            by_code_alt[code].append(title)
    occupations = []
    for o in occ:
        code = o["O*NET-SOC Code"]
        if not by_code_tasks.get(code):
            continue  # some codes have no task statements (e.g. "All Other" groups)
        occupations.append({"code": code, "title": o["Title"].strip(), "desc": o["Description"].strip(),
                            "alt": by_code_alt.get(code, []), "tasks": by_code_tasks[code]})
    known = {o["code"] for o in occupations}
    test_titles = sorted({(r["Reported Job Title"].strip(), r["O*NET-SOC Code"]) for r in reported
                          if r["O*NET-SOC Code"] in known})
    return occupations, [list(t) for t in test_titles]


def load_aei(path: Path) -> tuple[dict, dict]:
    """task_id -> {global_pct, global_auto, global_aug, za_pct} for the latest month in the file."""
    rows = []
    months = set()
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r["category_name"] == "onet" and r["hierarchy_level"] == "0" and r["geo_id"] in GEOS
                    and r["metric_id"] in METRICS):
                rows.append(r)
                months.add((r["date_start"], r["date_end"]))
    latest = max(months)
    out: dict[str, dict] = defaultdict(dict)
    for r in rows:
        if (r["date_start"], r["date_end"]) != latest:
            continue
        key = {"pct": "pct", "collaboration_bucket_automation_pct": "auto",
               "collaboration_bucket_augmentation_pct": "aug"}[r["metric_id"]]
        geo = GEOS[r["geo_id"]]
        if geo == "za" and key != "pct":
            continue
        try:
            out[r["node_external_id"]][f"{geo}_{key}"] = float(r["value"])
        except ValueError:
            continue
    meta = {"month_start": latest[0], "month_end_exclusive": latest[1], "tasks_with_data": len(out),
            "months_in_file": sorted(m[0] for m in months)}
    return dict(out), meta


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--onet", required=True, type=Path)
    p.add_argument("--aei", required=True, type=Path)
    p.add_argument("--out", default="data/onet.json", type=Path)
    a = p.parse_args(argv)
    occupations, test_titles = load_onet(a.onet)
    aei, meta = load_aei(a.aei)
    task_ids = {str(t[0]) for o in occupations for t in o["tasks"]}
    matched = task_ids & set(aei)
    snap = {
        "source": {
            "onet": {"url": ONET_URL, "sha256": sha256(a.onet), "version": "O*NET 30.0",
                     "licence": "CC BY 4.0, U.S. Department of Labor, Employment and Training Administration"},
            "aei": {"url": AEI_URL, "sha256": sha256(a.aei), "release": "Anthropic Economic Index, 26 June 2026",
                    "licence": "CC-BY", "page": "https://www.anthropic.com/economic-index"},
        },
        "aei_meta": {**meta, "onet_tasks": len(task_ids), "onet_tasks_with_data": len(matched),
                     "aei_tasks_not_in_onet_30": len(set(aei) - task_ids)},
        "occupations": occupations,
        "aei": {k: v for k, v in sorted(aei.items(), key=lambda kv: int(kv[0])) if k in task_ids},
        "test_titles": test_titles,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(occupations)} occupations, {len(task_ids)} tasks, {len(matched)} with AEI data "
          f"({meta['month_start']}), {len(test_titles)} reported titles -> {a.out} "
          f"({a.out.stat().st_size:,} bytes)")
    print(json.dumps(snap["aei_meta"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
