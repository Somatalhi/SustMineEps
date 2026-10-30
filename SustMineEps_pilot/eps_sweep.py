"""eps_sweep.py -- epsilon-constraint sweep on the exact scheduler for a fixed design.

For a design x = (capex, rate, throughput, pushback) held fixed, re-solve the NPV-maximal
schedule under a tightening limit on one sustainability indicator and record the NPV given up.

Levers (what the limit is and how it enters the CPIT model):
    waste   total waste mined <= eps (Mt)          one whole-horizon constraint on y_{b,T}
    life    mine life <= eps (years)               horizon T = eps / tau  (land = footprint x life,
                                                   so this is also the land lever)
    lifemin mine life >= eps (years)               ore processed >= floor x plant capacity in every
                                                   period up to eps (resource lower bounds)

Usage (from the aim3 folder, with sustmine_search/ beside it):
    python eps_sweep.py --design 1180 28 15 9  --lever waste --eps 46 40 35 30 25 20 15
    python eps_sweep.py --design 1180 28 15 9  --lever life  --eps 16 14 12 10
    python eps_sweep.py --design 1180 28 15 9  --lever lifemin --eps 16 20 24 28 32 36 40 --floor 0.6
    python eps_sweep.py --design 1300 28 15 13 --lever waste ...

Writes results/sweep_<tag>_<lever>.csv with one row per eps: eps, feasible, npv, waste, land,
life, employees, gap, seconds, plus the unconstrained row (eps = inf) first. Plain
epsilon-constraint (no augmentation term); dominated points are flagged, not removed.
"""
import argparse, os, sys, time
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from params import P
from sustmine_search.precedence import pushback_precedence
from sustmine_search.cpit_adapter import value_table, build_cpit, schedule_aggregates
from sustmine_search.cpit import solve_cpit
from sustmine_search.evaluate_mip import project, employees, PERIOD_YEARS

ap = argparse.ArgumentParser()
ap.add_argument("--design", type=float, nargs=4, required=True, metavar=("CAPEX", "RATE", "THR", "PB"))
ap.add_argument("--lever", choices=["waste", "life", "lifemin"], required=True)
ap.add_argument("--eps", type=float, nargs="+", required=True)
ap.add_argument("--floor", type=float, default=0.6, help="lifemin: minimum ore per period as a fraction of plant capacity")
ap.add_argument("--bp", default="bench_phases.pkl")
ap.add_argument("--time_limit", type=int, default=300)
ap.add_argument("--gap", type=float, default=0.01)
ap.add_argument("--tag", default=None)
ap.add_argument("--out", default="results")
a = ap.parse_args()

bp = pd.read_pickle(a.bp)
x = project(a.design, bp, P)
cx, rate, thr, k = float(x[0]), float(x[1]), float(x[2]), int(x[3])
tag = a.tag or f"pb{k}_thr{thr:.0f}"
tau = PERIOD_YEARS
if np.any(np.abs(x - np.array(a.design, float)) > 1e-9):
    print("design mapped onto Omega ->", np.round(x, 2).tolist())

sub = bp[bp.pb <= k].reset_index(drop=True)
preds = pushback_precedence(sub)
d = value_table(sub, P)
d["metal_g"] = sub.metal_g.values * 1e6
waste_b = (sub.waste_t.values * 1.0)                      # Mt per unit
area = float(sub.drop_duplicates("pb").area_ha.sum())
mcap, pcap = rate * 1e6 * tau, thr * 1e6 * tau
disc = (1.0 + P["discount"]) ** tau - 1.0
t_need = max(d.tonnes.sum() / mcap, d.processing_tonnes.sum() / pcap)
T_free = int(min(int(np.ceil(P["life_max"] / tau)), max(2, np.ceil(1.5 * t_need))))


def solve(T, totals=None, lb_ore=None):
    I, pred_idx, ids = build_cpit(d, preds, mcap, pcap, T, disc)
    if lb_ore is not None:                                 # production floor: periods 0..len-1
        I["lb"][1, :len(lb_ore)] = lb_ore
    t0 = time.time()
    res = solve_cpit(I, pred_idx, time_limit=a.time_limit, gap=a.gap, msg=False, threads=1, totals=totals)
    sec = time.time() - t0
    if not res["incumbent"]:
        return dict(feasible=False, npv=np.nan, waste=np.nan, land=np.nan, life=np.nan, gap=np.nan, seconds=sec)
    mined_at = {t: [] for t in range(1, T + 1)}
    for i, per in enumerate(res["period"]):
        if per >= 0:
            mined_at[int(per) + 1].append(ids[i])
    agg = schedule_aggregates(d, dict(mined_at=mined_at))
    L = agg["life"] * tau
    npv = res["objective"] / 1e6 - cx - P["reclam"] / (1.0 + P["discount"]) ** max(L, 1)
    return dict(feasible=True, npv=npv, waste=float(agg["waste"].sum()), land=area * L, life=L,
                gap=res["mip_gap"], seconds=sec, highs=res["highs_status"])


rows = []
print(f"design {tag}: capex {cx:.0f} rate {rate:.1f} thr {thr:.1f} pit {k}; T_free = {T_free} periods")
base = solve(T_free)
base.update(eps=np.inf, lever=a.lever); rows.append(base)
print(f"  unconstrained: NPV {base['npv']:.0f}  waste {base['waste']:.1f}  life {base['life']:.0f}  ({base['seconds']:.0f}s, gap {base['gap']:.3f})")

for eps in a.eps:
    if a.lever == "waste":
        r = solve(T_free, totals=[(waste_b, "<=", eps)])
    elif a.lever == "life":
        T = max(1, int(round(eps / tau)))
        r = solve(T)
    else:  # lifemin
        T = max(T_free, int(np.ceil(eps / tau)))
        n_floor = int(np.ceil(eps / tau))
        r = solve(T, lb_ore=np.full(n_floor, a.floor * pcap))
    r.update(eps=eps, lever=a.lever); rows.append(r)
    print(f"  eps {eps:>6g}: " + ("infeasible" if not r["feasible"] else
          f"NPV {r['npv']:.0f}  waste {r['waste']:.1f}  life {r['life']:.0f}  land {r['land']:.0f}  ({r['seconds']:.0f}s, gap {r['gap']:.3f})"))

df = pd.DataFrame(rows)
df.insert(0, "design", tag)
for c, v in zip(["capex", "rate", "thr", "pb"], [cx, rate, thr, k]):
    df[c] = v
df["employees"] = employees(rate, thr, P)
# flag points dominated on (npv, indicator) within the sweep
ind = {"waste": "waste", "life": "land", "lifemin": "life"}[a.lever]
better_ind = (lambda u, v: u <= v) if a.lever != "lifemin" else (lambda u, v: u >= v)
dom = []
for i, r in df.iterrows():
    dom.append(any(j != i and q.feasible and r.feasible and q.npv >= r.npv and better_ind(q[ind], r[ind])
                   and (q.npv > r.npv or q[ind] != r[ind]) for j, q in df.iterrows()))
df["dominated"] = dom
os.makedirs(a.out, exist_ok=True)
path = f"{a.out}/sweep_{tag}_{a.lever}.csv"
df.to_csv(path, index=False)
print("wrote", path)
