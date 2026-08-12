#!/usr/bin/env bash
# Proves the RBAC linter can still detect, in both shapes it meets in the wild.
#
# WHY THIS EXISTS
#
# Every unit test feeds analyze_text a hand-written single-document manifest.
# That is not the shape the linter meets in use. Against a live cluster holding
# four cluster-admin-equivalent roles it printed:
#
#     No risky RBAC found.        exit 0
#
# because `kubectl get -o json` wraps everything in one `kind: List` document
# and the top-level kind check returned []. Every test passed the whole time.
#
# So this runs the linter against the repo's OWN deliberately-dangerous
# manifest, in both shapes, and fails if either comes back clean. A linter that
# finds nothing here is broken, not reassuring.
#
# Run locally:  bash scripts/canary.sh

set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
listfile="$(mktemp -t rbac-list-XXXXXX.json)"
trap 'rm -f "${listfile}"' EXIT

expect_findings() {
  local label="$1" target="$2"
  local out rc
  out="$(python3 scripts/rbac_lint.py "${target}" 2>&1)"
  rc=$?

  # rc 1 means findings. rc 0 means it read the file and found nothing, which
  # is the bug. Anything else means it could not run at all, and that must not
  # be mistaken for a detection: an earlier version of this canary "passed"
  # because the linter exited non-zero on a file that did not exist.
  if [[ ${rc} -eq 1 ]]; then
    echo "  ${label}: $(echo "${out}" | grep -oE '^[0-9]+ risky' || echo 'findings') — OK"
  elif [[ ${rc} -eq 0 ]]; then
    echo "  ${label}: FOUND NOTHING in a file full of planted escalation"
    fail=1
  else
    echo "  ${label}: linter could not run (exit ${rc}). Not a detection."
    echo "${out}" | sed 's/^/      /'
    fail=1
  fi
}

echo "==> shape 1: the manifest as written"
expect_findings "risky-rbac.yaml" "k8s/risky-rbac.yaml"

echo "==> shape 2: wrapped the way kubectl -o json returns it"
python3 - "${listfile}" <<'PY'
import json
import sys

import yaml

docs = [d for d in yaml.safe_load_all(open("k8s/risky-rbac.yaml")) if d]
json.dump({"kind": "List", "apiVersion": "v1", "items": docs}, open(sys.argv[1], "w"))
print(f"  wrapped {len(docs)} objects in a List")
PY
expect_findings "List-wrapped" "${listfile}"

echo
if [[ ${fail} -eq 0 ]]; then
  echo "CANARY PASSED: the linter rejects the planted roles in both shapes."
else
  echo "CANARY FAILED: the linter is not detecting what this repo plants on purpose."
  exit 1
fi
