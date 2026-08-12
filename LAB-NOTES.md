# Lab Notes — Conjur on Kubernetes + KubiScan

> Running log, newest first.

## Known traps (pre-seeded)

### authn-k8s certificate wiring is the hard part

The Kubernetes authenticator needs the cluster CA and a correctly annotated
service account. Most first-run failures are a cert or namespace mismatch, and the
error surfaces as an opaque 401 from Conjur, not "your cert is wrong." Budget time
here and log the exact fix.

### KubiScan will flag Conjur's own service accounts

Conjur's installer creates service accounts with real permissions. KubiScan
correctly flags some of them. The lab is not "make KubiScan return nothing" — it's
"explain each finding." A privileged SA that Conjur legitimately needs is a
different thing from a cluster-default risk, and telling them apart is the skill.

### kind vs minikube secret behaviour

If you swap kind for minikube, the authn-k8s host config differs. Pin one and note
which — the manifests here assume kind.

## YYYY-MM-DD — <first real entry>

**Goal:** · **What happened:** · **Why:** · **Fix:** · **Time lost:**

## Open questions
- [ ] Which KubiScan findings are Conjur-install artifacts vs. real risks?
- [ ] Does the demo pod ever hold the secret on disk, or only in memory?
