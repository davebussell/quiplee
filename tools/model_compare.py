"""Rerun the old-vs-new model study (tools/qstrat/modelcompare.py) from the dev engine cache and
write data/modelcompare.json, which articles/old-vs-new-signal/ reads.

    python tools/dev_render.py engine      # once, if there's no cache yet
    python tools/model_compare.py
"""
import json
import os
import pickle
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from qstrat import engine  # noqa: E402
from qstrat.render import Site  # noqa: E402
from qstrat import modelcompare  # noqa: E402

CACHE_DIR = os.environ.get("BTP_CACHE") or os.path.join(os.path.dirname(HERE), ".cache")


def main():
    t0 = time.time()
    prices, irx, now = engine.load_all()
    with open(os.path.join(CACHE_DIR, "results.pkl"), "rb") as f:
        results = pickle.load(f)
    meta = {k[0]: results.pop(k) for k in [k for k in results if k[1] == "__meta"]}
    site = Site(results, preview=True, prices=prices, irx=irx, meta=meta)
    out = modelcompare.study(site)
    with open(modelcompare.OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {modelcompare.OUT} in {time.time() - t0:.0f}s")
    for k, m in out["models"].items():
        a, an = m.get("all") or {}, m.get("an") or {}
        print(f"{k:9s} edge12 {a.get('edge12')}  e1 {(m.get('e1') or {}).get('edge12')}  e2 {(m.get('e2') or {}).get('edge12')}  e3 {(m.get('e3') or {}).get('edge12')}  "
              f"flips {m.get('flips')}  | an edge3 {an.get('edge3')} edge12 {an.get('edge12')}  buy {an.get('buy', {}).get('n')}")


if __name__ == "__main__":
    main()
