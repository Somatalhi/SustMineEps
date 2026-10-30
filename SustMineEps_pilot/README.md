# SustMineEps: pricing sustainability improvements on the exact scheduler (Aim 3 pilot)

Question. For a mine design that Aim 2 shortlisted, how much NPV does each unit of
sustainability improvement cost when the design is held fixed and only the schedule
changes (the schedule rate), how far can the schedule move the indicator at all (the
reach), and how does that compare with the cost of the same improvement obtained by
changing the design (the design rate, read off the Aim 2 front)?

Method. Epsilon-constraint sweeps on the MineLib CPIT model solved exactly (HiGHS), one
indicator at a time, for the archetype designs of Aim 2:

| lever   | limit                      | how it enters the model                              |
|---------|----------------------------|------------------------------------------------------|
| waste   | total waste <= eps (Mt)    | one whole-horizon constraint on the units mined      |
| life    | mine life <= eps (yr)      | horizon T = eps / tau (land = footprint x life)      |
| lifemin | mine life >= eps (yr)      | ore floor per period (fraction of plant capacity)    |

Pilot is plain epsilon-constraint; the AUGMECON2 augmentation comes after the pilot.

Files
* `sustmine_search/` copied from SustMinePlus (cpit.py has the `totals` side constraints).
* `params.py`, `bench_phases.pkl` copied from SustMinePlus.
* `eps_sweep.py`  one design, one lever, a list of eps values -> results/sweep_<design>_<lever>.csv
* `design_front.py`  design-side (NPV, indicator) fronts from the Aim 2 results
* `plot_rates.py`  schedule rate vs design rate per indicator -> results/fig_rates.pdf, rates.csv

Pilot runs (archetype A: pushback 9 through a 15 Mt/y plant; B: pushback 13, 15 Mt/y):
```
python eps_sweep.py --design 1180 28 15 9  --lever waste   --eps 44 40 36 32 28 24 20
python eps_sweep.py --design 1180 28 15 9  --lever life    --eps 14 12 10
python eps_sweep.py --design 1180 28 15 9  --lever lifemin --eps 20 24 28 32 36 40
python eps_sweep.py --design 1300 28 15 13 --lever waste   --eps 80 70 60 50 40
python eps_sweep.py --design 1300 28 15 13 --lever life    --eps 20 18 16 14 12 10
python eps_sweep.py --design 1300 28 15 13 --lever lifemin --eps 26 30 34 38 42 46 50
python design_front.py --in ../py/results/exp1_cpit_5000
python plot_rates.py
```

On the NRP cluster (one job per eps value, all in parallel; results land on the shared
volume under /data/sustmine-eps/results):
```
cd nrp
kubectl apply -f update-job.yaml ; kubectl logs job/sustmine-eps-update -f      (wait for UPDATE DONE)
python make_jobs_eps.py ; kubectl apply -f jobs.yaml                          (36 jobs)
kubectl get jobs | find /c "1/1"                                               (until 36)
kubectl apply -f shell-pod.yaml ; kubectl wait --for=condition=Ready pod/sustmine-shell --timeout=300s
kubectl cp sustmine-shell:/data/sustmine-eps/results ..\results
cd .. ; python design_front.py --in <path to Aim 2 results>\exp1_cpit_5000 ; python plot_rates.py
```
