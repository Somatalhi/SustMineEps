"""plot_rates.py -- schedule rate versus design rate, one panel per indicator.

Reads results/sweep_<design>_<lever>_eps*.csv (eps_sweep.py, one file per eps) and results/design_front_<ind>.csv
(design_front.py). Draws, per indicator, the design-side front (grey) and each design's
schedule-side sweep (coloured, starting at its unconstrained point), and prints a table of
rates: NPV given up per unit of indicator improvement by rescheduling (schedule rate) and by
redesigning (design rate near the same indicator value), plus the reach of each lever.

Usage:  python plot_rates.py
Writes  results/fig_rates.pdf/.png and results/rates.csv
"""
import glob, os, re
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LEVER_IND = {"waste": ("waste", "waste, Mt", "min"), "life": ("land", "land, ha.yr", "min"),
             "lifemin": ("life", "mine life, yr", "max")}
sweeps = {}
parts = {}
for f in sorted(glob.glob("results/sweep_*_*_eps*.csv")):
    m = re.match(r".*sweep_(.+)_(waste|life|lifemin)_eps(.+)\.csv", f.replace("\\", "/"))
    parts.setdefault((m.group(2), m.group(1)), []).append(pd.read_csv(f))
for (lever, tag), lst in parts.items():
    df = pd.concat(lst, ignore_index=True)
    df["eps"] = df["eps"].astype(float)                      # 'inf' parses to inf
    sweeps.setdefault(lever, {})[tag] = df
if not sweeps:
    raise SystemExit("no results/sweep_*_eps*.csv found")
# the unconstrained baseline of a design is the same whatever the lever: share it across levers
bases = {}
for lever, d in sweeps.items():
    for tag, df in d.items():
        b = df[np.isinf(df.eps) & df.feasible]
        if len(b): bases[tag] = b.iloc[0]
for lever, d in sweeps.items():
    for tag, df in d.items():
        if not np.isinf(df.eps).any():
            if tag not in bases:
                raise SystemExit(f"no unconstrained baseline (eps=inf) found for design {tag}")
            d[tag] = pd.concat([bases[tag].to_frame().T.assign(lever=lever), df], ignore_index=True)
            d[tag]["eps"] = d[tag]["eps"].astype(float)
            for c in ["npv", "waste", "land", "life", "feasible"]:
                d[tag][c] = d[tag][c].astype(float if c != "feasible" else bool)
fronts = {k: pd.read_csv(f"results/design_front_{k}.csv") for k in ["waste", "land", "life"]
          if os.path.exists(f"results/design_front_{k}.csv")}

fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
rows = []
for ax, (lever, (ind, label, sense)) in zip(axes, LEVER_IND.items()):
    if ind in fronts:
        fr = fronts[ind]
        ax.plot(fr.indicator, fr.npv, "-", color="0.6", lw=1, label="design front (Aim 2)")
        ax.plot(fr.indicator, fr.npv, ".", color="0.5", ms=4)
    for tag, df in sweeps.get(lever, {}).items():
        df = df[df.feasible].sort_values(ind)
        base = df[np.isinf(df.eps)].iloc[0]
        ax.plot(df[ind], df.npv, "o-", ms=4, label=f"schedule sweep, {tag}")
        ax.plot([base[ind]], [base.npv], "k*", ms=9)
        # schedule rate: NPV given up per unit of improvement from the unconstrained point
        d = df[~np.isinf(df.eps) & (df[ind] != base[ind])]
        if len(d):
            imp = (base[ind] - d[ind]) if sense == "min" else (d[ind] - base[ind])
            rate = (base.npv - d.npv) / imp
            ok = imp > 0
            reach = float(imp[ok].max()) if ok.any() else 0.0
            # design rate near the same indicator value, from the front's piecewise slopes
            drate = np.nan
            if ind in fronts and len(fr) > 1:
                j = int(np.argmin(np.abs(fr.indicator.values - base[ind])))
                drate = float(np.nanmedian(fr.design_rate.values[max(1, j - 1):j + 2]))
            rows.append(dict(indicator=ind, design=tag, base_npv=round(base.npv, 1), base_ind=round(base[ind], 1),
                             schedule_rate_median=round(float(np.nanmedian(rate[ok])), 1),
                             schedule_rate_first=round(float(rate[ok].iloc[0]), 1),
                             reach=round(reach, 1), reach_pct=round(100 * reach / abs(base[ind]), 1),
                             design_rate_local=round(drate, 1)))
    ax.set_xlabel(label); ax.set_ylabel("NPV, $M"); ax.grid(alpha=0.3)
axes[0].legend(frameon=False, fontsize=7)
fig.tight_layout()
for ext in ("pdf", "png"): fig.savefig(f"results/fig_rates.{ext}", dpi=200)
R = pd.DataFrame(rows); R.to_csv("results/rates.csv", index=False)
print(R.to_string(index=False))
print("\nrates are $M of NPV per unit of indicator improvement (Mt, ha.yr, year); reach is how far the "
      "schedule lever can move the indicator at fixed design, in units and as % of the unconstrained value.")
