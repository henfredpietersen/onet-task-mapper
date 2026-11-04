"""How TITLE_WEIGHT in mapper/model.py was picked, on the tuning half of the reported titles only.

    python scripts/tune.py

Picked 0.7: the best top-three rate on the tuning half (0.3 -> 59.1%, 0.5 -> 62.4%, 0.7 -> 62.7%,
0.85 -> 62.0%, 1.0 -> 61.5%). The held-out half is not read here.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mapper import model as m  # noqa: E402


def main() -> int:
    snap = json.loads((ROOT / "data" / "onet.json").read_text(encoding="utf-8"))
    mapper = m.Mapper(snap)
    for w in (0.3, 0.5, 0.7, 0.85, 1.0):
        m.TITLE_WEIGHT = w
        r = m.evaluate(mapper, snap["test_titles"], "dev")
        print(f"TITLE_WEIGHT {w}: top-1 {r['top1']:.1%}, top-3 {r['top3']:.1%} on {r['n']} tuning titles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
