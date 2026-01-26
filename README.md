# Lab 08 — Conjur Secrets on Kubernetes + KubiScan RBAC Audit

[![tests](https://github.com/ChromeData/Conjur-Kubernetes-KubiScan/actions/workflows/tests.yml/badge.svg)](https://github.com/ChromeData/Conjur-Kubernetes-KubiScan/actions/workflows/tests.yml)

**Pods get their secrets from Conjur so none holds a static credential — then a
second check hunts the RBAC permissions that make perfect secrets management
pointless. Both halves of the same problem, because doing one without the other
is theatre.**

| | |
|---|---|
| **Domains** | CyberArk/Idira · Linux · Kubernetes |
| **Built on** | [cyberark/conjur](https://github.com/cyberark/conjur) + [conjur-oss-helm-chart](https://github.com/cyberark/conjur-oss-helm-chart) · [cyberark/KubiScan](https://github.com/cyberark/KubiScan) (GPL-3.0) |
| **Cost** | $0 (local kind/minikube) · **Runtime** ~4 hours |
| **Status** | 🟡 Built, tests pass, not yet run on a cluster |

---

## The point

You can do secrets *perfectly* — Conjur brokers every credential, nothing static
in a pod — and still be wide open, because a service account with `escalate`,
`bind`, or `create pods` can mint itself a token that reads everything. Secrets
injection and RBAC are two halves of one problem. This lab does both.

## The two checks

**KubiScan** (CyberArk's tool) runs against the live cluster and finds risky
subjects, roles, and pods from the *effective* permissions.

**[`scripts/rbac_lint.py`](./scripts/rbac_lint.py)** is my offline pre-check — it
parses the RBAC YAML and flags the same escalation primitives *before* anything
is applied, so they're caught at PR time instead of after `kubectl apply`. The
two are complementary: static analysis on the YAML in CI, plus the authoritative
live scan. **Agreement between them is the lab's cross-check.**

## The planted risks

[`k8s/risky-rbac.yaml`](./k8s/risky-rbac.yaml) embeds six escalation primitives,
each of which defeats good secrets hygiene:

| Risk | Why it beats secrets injection |
|---|---|
| `escalate` | grant yourself any permission |
| `bind` | bind cluster-admin to yourself |
| secrets `get/list` | just read all the secrets directly |
| pods `create` | schedule a pod wearing a privileged token |
| `*/*/*` wildcard | cluster-admin by another name |
| SA → wildcard binding | makes the wildcard live |

The linter catches all of them — **11 offline tests** prove it, including that the
clean workload trips *none* and that benign rules (list configmaps, get pods)
aren't false-flagged. CI also schema-validates every manifest with kubeconform.

```bash
python -m pytest tests/ -v
python scripts/rbac_lint.py k8s/risky-rbac.yaml
```

## What I didn't build

Conjur and KubiScan are CyberArk's. The secrets-injection workload, the planted
risky-RBAC fixture, the offline RBAC linter, and the tests are mine.

---

## Running it

```bash
make cluster        # kind cluster
make conjur         # Conjur via Helm + authn-k8s
make deploy         # secret-consumer workload (no static credential)
make apply-rbac     # plant the risky RBAC
make kubiscan       # live-cluster audit
python scripts/rbac_lint.py k8s/*.yaml   # offline cross-check
make destroy
```

Needs kind or minikube, kubectl, Helm, Python 3.

## Findings

`findings/` fills in from the KubiScan run. [LAB-NOTES.md](./LAB-NOTES.md) is the
log — the interesting question is which risky findings come from the Conjur
install itself.

## License

Lab code: MIT ([LICENSE](./LICENSE)). Conjur (LGPL) and KubiScan (GPL-3.0) keep
their licenses, credited above and not vendored.
