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
    # the published numbers from before the measuring stick was fixed (AUD-46, Oct 27, 2026: total-return markets,
    # bad price files gated, split-adjusted SEC numbers), kept so the article can show what moved
    old = modelcompare.load()
    if old.get("before_aud46"):
        out["before_aud46"] = old["before_aud46"]
    elif old.get("models") and not old.get("bench"):
        keep = {}
        for k, m in old["models"].items():
            a = m.get("all") or {}
            if a:
                keep[k] = {"edge12": a.get("edge12"), "flips": m.get("flips"), "buy_fell30": (a.get("buy") or {}).get("fell30"),
                           "sell_fell30": (a.get("sell") or {}).get("fell30"), "buy_beat12": (a.get("buy") or {}).get("beat12"),
                           "sell_beat12": (a.get("sell") or {}).get("beat12"), "e1": (m.get("e1") or {}).get("edge12"),
                           "e2": (m.get("e2") or {}).get("edge12"), "e3": (m.get("e3") or {}).get("edge12")}
        out["before_aud46"] = {"built": old.get("built"), "models": keep}
    with open(modelcompare.OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {modelcompare.OUT} in {time.time() - t0:.0f}s")
    for k, m in out["models"].items():
        a, an = m.get("all") or {}, m.get("an") or {}
        print(f"{k:9s} edge12 {a.get('edge12')}  e1 {(m.get('e1') or {}).get('edge12')}  e2 {(m.get('e2') or {}).get('edge12')}  e3 {(m.get('e3') or {}).get('edge12')}  "
              f"flips {m.get('flips')}  | an edge3 {an.get('edge3')} edge12 {an.get('edge12')}  buy {an.get('buy', {}).get('n')}")
        if m.get("us"):
            yr = lambda r: f"{r['mean']:+.3f} ±{r['pm']:.3f} ({r['pos']}/{r['n']} yrs up)" if r else "-"
            print(f"{'':9s} US {m['us'].get('edge12')} yearly {yr(m.get('us_yr'))}  TSX {m['tsx'].get('edge12')} yearly {yr(m.get('tsx_yr'))}  all yearly {yr(m.get('yr'))}")


if __name__ == "__main__":
    main()
