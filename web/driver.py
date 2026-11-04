"""Glue between the demo page and mapper/. The page runs this and mapper/ unchanged in the browser
(Pyodide). tests/test_snapshot_and_page.py makes the same calls under CPython."""

from __future__ import annotations

import json

from mapper import model as m

_state: dict = {}


def setup(snapshot_json: str) -> str:
    snap = json.loads(snapshot_json)
    mapper = m.Mapper(snap)
    _state["m"] = mapper
    test = m.evaluate(mapper, snap["test_titles"], "test")
    titles = {o["code"]: o["title"] for o in snap["occupations"]}
    sample = [{"title": t, "right": titles[c], "got": titles[g]} for t, c, g in test["misses"][::40][:8]]
    return json.dumps({
        "source": snap["source"], "aei_meta": snap["aei_meta"], "occupations": len(snap["occupations"]),
        "titles_total": len(snap["test_titles"]),
        "test": {k: v for k, v in test.items() if k != "misses"}, "miss_sample": sample,
        "title_weight": m.TITLE_WEIGHT, "ad_match": m.AD_MATCH,
    })


def lookup(text: str, pick: int = -1) -> str:
    mapper = _state["m"]
    hits = mapper.search(text, k=5)
    if not hits:
        return json.dumps({"candidates": [], "occupation": None})
    chosen = pick if pick >= 0 else hits[0][0]
    return json.dumps({
        "candidates": [{"index": i, "code": mapper.occ[i]["code"], "title": mapper.occ[i]["title"], "score": s} for i, s in hits],
        "occupation": mapper.tasks(chosen, text),
    })
