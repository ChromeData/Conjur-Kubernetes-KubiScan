# Lab 08 — Conjur Secrets on Kubernetes + KubiScan RBAC Audit

**Inject secrets into Kubernetes workloads via Conjur so no pod holds a static
credential, then audit the cluster's RBAC with CyberArk's KubiScan to find the
risky permissions that undo all of it.**

| | |
|---|---|
| **Domains** | CyberArk/Idira · Linux · Kubernetes |
| **Built on** | [cyberark/conjur](https://github.com/cyberark/conjur) + [conjur-oss-helm-chart](https://github.com/cyberark/conjur-oss-helm-chart) (LGPL/Apache) · [cyberark/KubiScan](https://github.com/cyberark/KubiScan) (GPL-3.0) |
| **Runtime** | ~4 hours · $0 (local kind/minikube cluster) |
| **Status** | 🟡 In progress |

---

## Why this lab exists

Secrets injection and RBAC are two halves of the same problem. You can do secrets
perfectly — Conjur brokers every credential, nothing static in a pod — and still be
wide open because a service account has `escalate`, `bind`, or `create pods` and can
mint itself a token that reads everything. This lab does both halves: the clean
secrets path, then the audit that proves whether the cluster's RBAC actually holds.

It also adds the Kubernetes dimension your other labs don't cover, which matters
because that's where cloud PAM is heading.

## What I built

- A local **kind** cluster with **Conjur OSS deployed via its Helm chart**.
- A **Conjur authn-k8s** setup so pods authenticate by their service-account
  identity and pull secrets at runtime — no secrets in manifests, no static tokens.
- A demo workload that consumes a brokered secret to prove the path end-to-end.
- A **KubiScan audit** stage that enumerates risky RBAC (privileged service
  accounts, dangerous verbs, tokens that can escalate), with the findings triaged
  against what I actually deployed.

## What I did not build

Conjur, its Helm chart, and KubiScan are all CyberArk's. My work is the cluster, the
authn-k8s wiring, the demo workload, and the RBAC-audit analysis.

---

## Running it

```bash
make cluster        # kind create + namespaces
make conjur         # helm install conjur-oss, initialise account
make authn-k8s      # configure the k8s authenticator + host identities
make demo           # deploy a pod that pulls a secret at runtime
make audit          # clone + run KubiScan, output to findings/
make destroy        # kind delete cluster
```

## The two findings sets

**Secrets path:** confirm the demo pod got its secret and that
`kubectl get secret` / the manifest contain nothing sensitive.

**RBAC audit:** KubiScan output, triaged —

| KubiScan finding | Real risk? | Introduced by | Action |
|------------------|-----------|---------------|--------|
| Privileged service accounts | | | |
| Risky roles (escalate/bind/impersonate) | | | |
| Pods with risky SA tokens | | | |

The analysis worth writing: which risky permissions came from Conjur's own install
(and are they justified?), and which are cluster defaults most people never audit?

## What broke

See [LAB-NOTES.md](./LAB-NOTES.md).
