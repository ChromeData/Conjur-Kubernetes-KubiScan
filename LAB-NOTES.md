# Lab Notes, 08 Conjur on Kubernetes + KubiScan

Running log. Errors, dead ends, fixes, surprises. Dated, newest at the bottom.

---

## Format

```
### YYYY-MM-DD, what I was trying to do

**Expected:**
**Got:**
**Cause:**
**Fix:**
```

---

## Design decisions

### An offline linter next to the live scanner

KubiScan needs a running cluster. That makes it the authoritative check but a
slow one, and useless at PR time. `rbac_lint.py` parses the YAML and flags the
same escalation verbs offline, so a risky role is caught before it's applied.
The two should agree. Where they disagree is interesting: the linter sees the
declared rule, KubiScan sees the effective permission after aggregation and
bindings.

### Wildcard verbs must satisfy specific checks

A rule with `verbs: ["*"]` on secrets has to trip the `secrets-read` check, not
slip through because it doesn't literally list `get`. The `_has` helper treats
`*` as matching anything. Pinned by a test.

### The clean workload must stay clean

`demo-workload.yaml` defines only a ServiceAccount and Deployment, no Roles. A
test asserts the linter finds zero risks in it, so if someone later adds a
convenience RoleBinding there, CI catches it.

---

## Known traps (confirm on the cluster)

- **KubiScan flags the Conjur install itself.** The Helm chart creates roles
  that KubiScan may (correctly) call risky. Triage those separately from the
  planted fixture. Don't count them as false positives without checking.
- **authn-k8s wiring is the hard part.** The demo workload's secret injection
  needs the cyberark secrets-provider init container configured against the
  cluster's authn-k8s service ID. The manifest has a placeholder; wire it per
  the Conjur docs and record what broke.
- **kubecontext guard.** `run-kubiscan.sh` refuses any context without
  `pam-lab08` in the name. Confirm your kind context matches or it aborts.

---

## Open questions

- [ ] Do KubiScan and rbac_lint.py agree on the six planted risks?
- [ ] Which risky roles come from the Conjur Helm chart vs. the fixture?
- [ ] Does the secret actually land in /conjur/secrets with no static token?
- [ ] Capture KubiScan's risky-subjects output for findings/.

---

## Log

### 2026-08-12, linter run against the planted fixture

Ran the offline linter against `k8s/risky-rbac.yaml` before touching a cluster:

```
  [escalate      ] ClusterRole/lab-escalate: can grant itself arbitrary permissions
  [bind          ] ClusterRole/lab-bind: can bind any role to itself, including cluster-admin
  [secrets-read  ] ClusterRole/lab-secret-reader: can read secrets cluster-wide
  [pods-create   ] Role/lab-pod-creator: can create pods
  [wildcard-all  ] ClusterRole/lab-wildcard: wildcard verb on wildcard resource
  ...
11 risky RBAC rule(s) found.
```

All six planted primitives caught, and the clean workload trips none. Full output in
`findings/rbac-lint-run.txt`.

11 rules from 6 objects because several trip more than one check: the wildcard role
matches `secrets-read`, `pods-create`, and `wildcard-all` at once. That's correct
behaviour (a `*` grant genuinely is all of those) but it means the count is rules
matched, not objects at risk. Worth remembering before quoting the number.

---

### 2026-08-12, kubeconform failed CI on the kind config

**Expected:** manifests validate.

**Got:**

```
k8s/kind-config.yaml - failed validation: could not find schema for Cluster
Summary: 9 resources found in 3 files - Valid: 8, Invalid: 0, Errors: 1
```

**Cause:** `kind-config.yaml` is a kind CLI config (`kind.x-k8s.io`), not a Kubernetes
API object, so there is no upstream schema for it. Note `Invalid: 0`, nothing was
actually wrong with any real manifest.

**Fix:** `-skip Cluster`. Chose that over dropping `-strict`, which would have stopped
catching unknown fields in the manifests that *do* matter.
