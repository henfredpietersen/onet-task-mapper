"""The real snapshot, the numbers the README quotes, and the published page."""

import importlib.util
import json
import sys
from pathlib import Path

from mapper import model as m

ROOT = Path(__file__).resolve().parents[1]
SNAP = json.loads((ROOT / "data" / "onet.json").read_text(encoding="utf-8"))


def test_snapshot_is_consistent():
    task_ids = {str(t[0]) for o in SNAP["occupations"] for t in o["tasks"]}
    assert set(SNAP["aei"]) <= task_ids
    meta = SNAP["aei_meta"]
    assert (len(SNAP["occupations"]), meta["onet_tasks"], meta["onet_tasks_with_data"]) == (923, 18797, 2715)
    assert meta["month_start"] == "2026-05-01" and meta["aei_tasks_not_in_onet_30"] == 0
    shares = [v["global_pct"] for v in SNAP["aei"].values() if "global_pct" in v]
    assert 0 < sum(shares) <= 100 and max(shares) < 10
    # reported titles used for testing were removed from the matcher's alternate titles
    alts = {(o["code"], a.lower()) for o in SNAP["occupations"] for a in o["alt"]}
    assert not alts & {(c, t.lower()) for t, c in SNAP["test_titles"]}


def test_readme_numbers_match_a_fresh_run():
    mp = m.Mapper(SNAP)
    test, dev = m.evaluate(mp, SNAP["test_titles"], "test"), m.evaluate(mp, SNAP["test_titles"], "dev")
    assert (test["n"], test["top1"], test["top3"], test["same_soc"]) == (3874, 0.4639, 0.6515, 0.4775)
    assert (dev["n"], dev["top1"], dev["top3"]) == (4081, 0.4499, 0.6268)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for s in ("46.4%", "65.2%", "47.8%", "3,874", "4,081", "2,715", "18,797", "923", "May 2026", "197"):
        assert s in readme, s


def test_published_page_embeds_current_code():
    spec = importlib.util.spec_from_file_location("build", ROOT / "web" / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert (ROOT / "docs" / "demo.js").read_text(encoding="utf-8") == mod.build(), "docs/demo.js is stale: run python web/build.py"


def test_driver_runs_like_the_page():
    sys.path.insert(0, str(ROOT / "web"))
    import driver

    info = json.loads(driver.setup(json.dumps(SNAP)))
    assert info["test"]["top1"] == 0.4639 and info["titles_total"] == 7955
    r = json.loads(driver.lookup("Bookkeeper"))
    assert r["occupation"]["title"] == "Bookkeeping, Accounting, and Auditing Clerks" and len(r["candidates"]) >= 2
    other = json.loads(driver.lookup("Bookkeeper", r["candidates"][1]["index"]))
    assert other["occupation"]["code"] == r["candidates"][1]["code"]
