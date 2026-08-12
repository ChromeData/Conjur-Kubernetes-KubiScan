#!/usr/bin/env bash
# Run cyberark/KubiScan against the lab cluster and capture the RBAC risk report.
# KubiScan is upstream CyberArk work (GPL-3.0); this only invokes it.

set -euo pipefail
LAB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${LAB_ROOT}/findings"
mkdir -p "$OUT"

if [[ ! -d "${LAB_ROOT}/vendor/KubiScan" ]]; then
  git clone --depth 1 https://github.com/cyberark/KubiScan "${LAB_ROOT}/vendor/KubiScan"
fi

# KubiScan reads the current kubecontext. Confirm it's the lab cluster first — you
# do NOT want to point this at a real cluster by accident (read-only, but still).
CTX="$(kubectl config current-context)"
echo "==> kubecontext: ${CTX}"
[[ "${CTX}" == *"pam-lab08"* ]] || { echo "Not the lab cluster. Aborting."; exit 1; }

cd "${LAB_ROOT}/vendor/KubiScan"
python3 -m pip install -r requirements.txt --quiet

echo "==> Risky roles"
python3 KubiScan.py -rr        | tee "${OUT}/risky-roles.txt"
echo "==> Risky subjects (service accounts / users)"
python3 KubiScan.py -rs        | tee "${OUT}/risky-subjects.txt"
echo "==> Pods using risky service-account tokens"
python3 KubiScan.py -rp        | tee "${OUT}/risky-pods.txt"

echo
echo "==> Triage each finding in findings/ against what you deployed."
echo "    The interesting question: which came from the Conjur install itself?"
