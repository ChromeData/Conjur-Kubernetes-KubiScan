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

### 2026-08-12, first real cluster, and the linter was lying

Built a kind cluster, applied the risky RBAC, exported the live state with
`kubectl get clusterroles,roles -A -o json` (84 objects) and ran the linter
against it.

```
No risky RBAC found.        exit 0
```

Four deliberately cluster-admin-equivalent ClusterRoles sitting in the cluster,
created by this repo on purpose, and the tool reported clean.

`kubectl -o json` returns **one** document of kind `List` with everything under
`items[]`. `analyze_doc` checked the top-level kind, saw `List`, and returned
`[]`. Every unit test passed the whole time, because all of them fed
`analyze_text` a hand-written single-document manifest. The linter was only ever
tested in the shape it does not meet in practice.

**Third time this session.** gitleaks silently detecting nothing after a version
change in lab 07. checkov silently evaluating nothing on nested ARM in lab 10.
Now this. Same failure every time: a security tool reporting clean because it
read nothing, with no signal that anything was wrong. Worth treating as the
default suspicion rather than a curiosity, and it is why "0 findings" should
never be accepted without a positive control.

Fixed the traversal, reran, got **62 findings, of which only 11 were the planted
roles**. The other 47 were roles Kubernetes installs itself. `cluster-admin`
really can escalate, bind and impersonate; saying so is true and useless, and it
buries the ones that matter.

Fixed by classifying, not suppressing. Kubernetes stamps its own roles with
`kubernetes.io/bootstrapping: rbac-defaults`, which beats matching on names.
Built-ins are still analysed and counted, just not what the exit code turns on.

Final: **15 findings on non-built-in roles**, every planted risk caught.

Four of the fifteen were not planted by this lab at all:
`local-path-provisioner-role`, which is kind's default storage provisioner,
ships with escalate, bind and impersonate. A development cluster arrives with
privileged infrastructure already inside it before anyone writes a Role.

Also made a missing input file an error instead of a clean pass. Four regression
tests added, 15 pass.

**Not done:** KubiScan itself never ran, so the cross-check between the static
linter and KubiScan's effective-permission view is still unverified. Conjur was
not installed, so secret delivery is untested. Full output in
`findings/live-cluster-run.txt`.

---
