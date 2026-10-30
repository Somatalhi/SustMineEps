"""design_front.py -- the design-side trade-off from the Aim 2 search results.

Pools the final NSGA-III populations at one budget, keeps feasible designs, and for each
indicator extracts the two-dimensional nondominated front of (NPV, indicator): the NPV
available at each indicator level when the DESIGN changes. Its local slope is the design rate,
to be compared with the schedule rate from eps_sweep.py.

Usage:  python design_front.py --in ../py/results/exp1_cpit_5000 --algo nsga3
Writes  results/design_front_<indicator>.csv  (npv, indicator, capex, rate, thr, pb) sorted by
        indicator, and prints the piecewise slopes.
"""
import argparse, glob, os, re
import numpy as np, pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--in", dest="IN", required=True)
ap.add_argument("--algo", default="nsga3")
ap.add_argument("--out", default="results")
a = ap.parse_args()

X, F = [], []
for f in sorted(glob.glob(f"{a.IN}/{a.algo}_seed*.npz")):
    d = np.load(f)
    feas = (d["G"] <= 0).all(1)
    X.append(d["X"][feas]); F.append(d["F"][feas])
X, F = np.vstack(X), np.vstack(F)
npv, waste, land, emp, life = -F[:, 0], F[:, 1], F[:, 2], -F[:, 3], -F[:, 4]
print(f"{len(F)} feasible designs pooled from {a.algo} at {a.IN}")

# indicator value and the direction that is "better"
IND = {"waste": (waste, "min"), "land": (land, "min"), "life": (life, "max")}
os.makedirs(a.out, exist_ok=True)
for name, (v, sense) in IND.items():
    s = v if sense == "min" else -v                       # minimise s, maximise npv
    order = np.lexsort((-npv, s))                           # by s asc, then npv desc
    front, best = [], -np.inf
    for i in order:
        if npv[i] > best + 1e-9:
            front.append(i); best = npv[i]
    fr = pd.DataFrame(dict(npv=npv[front], indicator=v[front], capex=X[front, 0], rate=X[front, 1],
                           thr=X[front, 2], pb=np.round(X[front, 3]).astype(int), life=life[front], waste=waste[front]))
    fr = fr.sort_values("indicator").reset_index(drop=True)
    # piecewise slope: NPV given up per unit of indicator improvement, between adjacent front points
    dn = fr.npv.diff(); di = fr.indicator.diff()
    fr["design_rate"] = (dn / di).abs() if sense == "min" else (dn / di).abs()
    fr.to_csv(f"{a.out}/design_front_{name}.csv", index=False)
    unit = {"waste": "$M per Mt", "land": "$M per ha.yr", "life": "$M per year"}[name]
    print(f"\n{name}: {len(fr)} front points; design rate ({unit}) median {fr.design_rate.median():.1f}, "
          f"IQR [{fr.design_rate.quantile(.25):.1f}, {fr.design_rate.quantile(.75):.1f}]")
    print(fr[["pb", "thr", "rate", "indicator", "npv", "life", "waste", "design_rate"]].round(1).to_string(index=False))
