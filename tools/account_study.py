"""Rerun the account-planning study (tools/qstrat/accountplan.py) from the dev engine cache and
write data/accountplan.json, which /guides/plan-an-account/ reads.

    python tools/account_study.py
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
from qstrat import accountplan  # noqa: E402

CACHE_DIR = os.environ.get("BTP_CACHE") or os.path.join(os.path.dirname(HERE), ".cache")


def main():
    t0 = time.time()
    prices, irx, now = engine.load_all()
    with open(os.path.join(CACHE_DIR, "results.pkl"), "rb") as f:
        results = pickle.load(f)
    meta = {k[0]: results.pop(k) for k in [k for k in results if k[1] == "__meta"]}
    site = Site(results, preview=True, prices=prices, irx=irx, meta=meta)
    out = accountplan.study(site)
    with open(accountplan.OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {accountplan.OUT} in {time.time() - t0:.0f}s: {out['stocks']} stocks, {out['years']} years")
    print("SPY", out["spy"]); print("ALL", out["all"])
    for k, v in out["n"].items():
        print(f"n={k:>2}  cagr {v['cagr_med']:+.3f} ({v['cagr_p10']:+.3f}..{v['cagr_p90']:+.3f})  dd {v['dd_med']:+.3f}  dd50 {v['dd50']:.2f}  lost {v['lost']:.2f}  beat all {v['beat_all']:.2f}")
    for k, v in out["core"].items():
        print(f"core {k:>8}  cagr {v['cagr_med']:+.3f} p10 {v['cagr_p10']:+.3f}  dd {v['dd_med']:+.3f}  falls {v.get('falls')}")
    for k, v in out["caps"].items():
        print(f"caps {k:>6}  cagr {v['cagr_med']:+.3f} p10 {v['cagr_p10']:+.3f}  dd {v['dd_med']:+.3f} dd p10 {v['dd_p10']:+.3f} dd50 {v['dd50']:.2f}")


if __name__ == "__main__":
    main()
