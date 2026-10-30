"""plot_rates.py -- schedule rate versus design rate, one panel per indicator.

Reads results/sweep_<design>_<lever>.csv (eps_sweep.py) and results/design_front_<ind>.csv
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
for f in sorted(glob.glob("results/sweep_*_*.csv")):
    m = re.match(r".*sweep_(.+)_(waste|life|lifemin)\.csv", f.replace("\\", "/"))
    sweeps.setdefault(m.group(2), {})[m.group(1)] = pd.read_csv(f)
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
