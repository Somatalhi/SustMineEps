"""Write jobs.yaml: one Kubernetes Job per (design, lever, eps) for the Aim 3 pilot.
Usage:  python make_jobs_eps.py            (uses the PLAN below)
Then:   kubectl apply -f jobs.yaml
Each job copies /data/sustmine-eps (refreshed by update-job.yaml) to /work, links results/
to the volume, and runs one eps_sweep.py call with a single eps value (or 'inf' for the
unconstrained baseline). 2 CPUs per job; HiGHS runs single-threaded, the second core is slack.
"""
PLAN = [
    # tag, design (capex rate thr pb), lever, eps values
    ("A", "1180 28 15 9",  "waste",   ["inf", 44, 40, 36, 32, 28, 24, 20]),
    ("A", "1180 28 15 9",  "life",    [14, 12, 10]),
    ("A", "1180 28 15 9",  "lifemin", [20, 24, 28, 32, 36, 40]),
    ("B", "1300 28 15 13", "waste",   ["inf", 80, 70, 60, 50, 40]),
    ("B", "1300 28 15 13", "life",    [20, 18, 16, 14, 12, 10]),
    ("B", "1300 28 15 13", "lifemin", [26, 30, 34, 38, 42, 46, 50]),
]
TIME_LIMIT, GAP = 600, 0.01

TEMPLATE = """---
apiVersion: batch/v1
kind: Job
metadata:
  name: eps-{tag}-{lever}-{eps}
spec:
  backoffLimit: 1
  ttlSecondsAfterFinished: 172800
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: run
        image: python:3.12-slim
        command: ["/bin/bash", "-c"]
        args:
          - |
            set -e
            mkdir -p /work && cp -r /data/sustmine-eps/. /work/ && rm -rf /work/results
            mkdir -p /data/sustmine-eps/results && ln -s /data/sustmine-eps/results /work/results
            cd /work
            pip install -q -r requirements.txt
            python -u eps_sweep.py --design {design} --lever {lever} --eps {epsval} --no_base \\
                   --tag {tag} --time_limit {tl} --gap {gap}
        resources:
          requests: {{cpu: "2", memory: "4Gi"}}
          limits:   {{cpu: "2", memory: "4Gi"}}
        volumeMounts:
        - {{name: data, mountPath: /data}}
      volumes:
      - name: data
        persistentVolumeClaim: {{claimName: sustmine-data}}
"""
docs = []
for tag, design, lever, eps_list in PLAN:
    for e in eps_list:
        name_e = str(e).replace(".", "p").lower()
        docs.append(TEMPLATE.format(tag=tag.lower(), lever=lever, eps=name_e, design=design,
                                    epsval=e, tl=TIME_LIMIT, gap=GAP))
open("jobs.yaml", "w").write("".join(docs))
print(f"jobs.yaml: {len(docs)} jobs")
