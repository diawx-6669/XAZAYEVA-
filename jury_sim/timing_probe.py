"""Item 5c: timing side channel. Latency of get_record/get_document for IDs that are evidence of a
truth issue vs. other IDs of the same table (serve, 30 rounds). Jury-side only: it uses truth to label."""
import json
import random
import statistics
import time

from common import WORK
from contract_check import Serve


def main():
    out = {}
    for n in (5, 12, 17):
        d = WORK / "closed" / f"{n:02d}"
        t = json.loads((d / "grader" / "truth.json").read_text())
        ev = {e for i in t["issues"] for s in i["evidence_sets"] for e in s}
        led = [l.split(",")[0] for l in (d / "public" / "ledger.csv").read_text().splitlines()[1:]]
        hot = [x for x in led if x in ev]
        cold = random.Random(n).sample([x for x in led if x not in ev], len(hot))
        s = Serve()
        lat = {"evidence": [], "other": []}
        try:
            for rnd in range(4):
                s.reset(n=n)
                order = [(x, "evidence") for x in hot] + [(x, "other") for x in cold]
                random.Random(rnd).shuffle(order)
                for x, lab in order[:98]:
                    t0 = time.perf_counter()
                    s.step("get_record", table="ledger", id=x)
                    lat[lab].append((time.perf_counter() - t0) * 1e6)
        finally:
            s.close()
        out[n] = {k: {"n": len(v), "median_us": round(statistics.median(v), 1), "mean_us": round(statistics.mean(v), 1)}
                  for k, v in lat.items()}
    (WORK / "timing_probe.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
