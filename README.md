# onet-task-mapper

Type a job title or paste a job ad. This finds the closest occupations in O*NET (the US Department of Labor's database of what jobs involve) and lists that occupation's tasks. Next to each task is how often Claude.ai conversations in May 2026 were about it, worldwide and in South Africa, and whether those conversations had Claude doing the task or working alongside the person. That data comes from the Anthropic Economic Index. Paste an ad, and it also marks which of the occupation's tasks the ad actually asks for.

**Try it live:** https://outview.co.za/case-study-onet-tasks/ (runs in your browser)

Built AI-assisted under my direction. I chose the data, how the matching is tested and how the usage numbers are explained. Claude generated the code, and I reviewed it, ran it and checked the tests. I didn't hand-write it.

## Why

It's the question every AI enablement conversation starts with: which parts of this job are people already handing to AI, and which aren't? O*NET breaks 923 occupations into 18,797 tasks. The Economic Index says which of those tasks show up in real Claude conversations. Joining them shows, task by task, where AI use is already happening, from real usage rather than guesses.

## How good is the matching?

O*NET publishes 7,955 job titles that real workers reported for their occupation ("Sample of Reported Titles"). I split them by a hash of the title: 4,081 to tune on and 3,874 held out. Held-out titles are also removed from the matcher's own title list, so it can't just look them up.

| On the 3,874 held-out titles | |
|---|---|
| Exact occupation first, out of 923 | **46.4%** |
| Exact occupation in the top three | **65.2%** |
| Same 6-digit SOC occupation first | 47.8% |
| Picking at random | 0.1% |

Most misses land on a neighbouring occupation ("Advanced Practice Nurse" → Nurse Practitioners instead of Clinical Nurse Specialists), which is why the demo shows the top five and lets you switch.

## How it works

- **Matching.** TF-IDF word matching on two fields: the title (official title plus alternate titles) and the content (description plus every task statement). Score = 0.7 × title + 0.3 × content. The 0.7 was picked on the tuning half (`scripts/tune.py`): it gave the best top-three rate there.
- **Tasks.** The chosen occupation's tasks are listed with the Index's figures for May 2026, highest share first.
- **Job ads.** A pasted ad is split into clauses (on full stops, commas, semicolons and "and"), and each task is compared with each clause. A task counts as "in your ad" if a clause shares at least two words with it and matches it closely enough; the page shows that clause. One shared word ("billing", "writer") isn't enough, so it errs towards missing a task rather than claiming one.

## The usage numbers

From the [Anthropic Economic Index](https://www.anthropic.com/economic-index) release of 26 June 2026 (CC-BY), Claude.ai conversations, May 2026:

- **Share of conversations:** of all conversations the Index matched to an O*NET task, the share matched to this one. Worldwide, and among conversations from South Africa.
- **Automation vs augmentation:** of those conversations worldwide, the split between Claude doing the task and Claude working alongside the person.
- **Not published:** the Index publishes a figure only above its aggregation thresholds. 2,715 of the 18,797 tasks have a worldwide figure for May 2026, and 197 have a South Africa figure. A missing figure is not a zero, and the demo shows the two differently ("not published" vs "under 0.005%").

**This is usage, not job risk.** It counts what people asked Claude about. It doesn't say any job will change, shrink or disappear.

## The data

`scripts/make_snapshot.py` joins O*NET 30.0 (CC BY 4.0, U.S. Department of Labor, Employment and Training Administration) with the Index on O*NET Task ID. Every task in the Index's data maps to an O*NET 30.0 task. The workflow `.github/workflows/snapshot.yml` downloads both on GitHub's servers and rebuilds `data/onet.json`, recording each file's SHA-256.

## What this isn't

- Word matching, not understanding. A title O*NET doesn't know (most "AI" job titles) lands on the closest older occupation.
- "In your ad" will miss tasks described in different words.
- One month of Claude.ai conversations. Other AI tools, and other months, could look different.

## Run it

```bash
python -m pytest -q                     # 11 tests, standard library + pytest
python scripts/tune.py                  # how the title weight was picked (tuning half only)
python web/build.py                     # rebuild docs/demo.js after changing mapper/ or web/
python -m http.server -d . 8000         # then open http://localhost:8000/docs/demo.html
```

## What was tested

- `tests/test_model.py`: plurals fold and job-ad filler words are dropped; search finds occupations by title and alternate title; published-zero and not-published stay different and sort correctly; ad clauses mark the right tasks and one shared word isn't enough; the split is stable.
- `tests/test_snapshot_and_page.py`: every Index task exists in O*NET 30.0, shares add up sensibly, held-out titles really are kept out of the title list, a fresh run reproduces every number in this README, the published page embeds the current code, and the page's calls work.
- I also ran the page's code under Pyodide 0.26.4 (the version the page loads) and got the same scores.

CI runs lint, the tests and the page drift check on every push.

MIT licence. Data: O*NET 30.0 (CC BY 4.0); Anthropic Economic Index (CC-BY).
