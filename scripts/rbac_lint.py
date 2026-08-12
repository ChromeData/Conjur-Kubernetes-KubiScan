#!/usr/bin/env python3
"""Flag dangerous Kubernetes RBAC from manifests, before the cluster exists.

KubiScan is the authoritative check — it runs against a live cluster and sees
the effective permissions. This is the fast pre-check: parse Role / ClusterRole
YAML and flag the verb+resource combinations that grant escalation, so you catch
them at PR time instead of after `kubectl apply`.

The two are complementary, not redundant: this runs offline in CI on the YAML;
KubiScan runs on the cluster and catches things static analysis can't (effective
bindings, aggregated roles). Agreement between them is the lab's cross-check.

Run:  python scripts/rbac_lint.py k8s/risky-rbac.yaml
"""

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")


# Each rule: (id, human reason, predicate over a policy rule dict).
def _has(rule, key, *values):
    got = rule.get(key, []) or []
    return any(v in got for v in values) or "*" in got


DANGEROUS = [
    ("escalate", "can grant itself arbitrary permissions (escalate)",
     lambda r: _has(r, "verbs", "escalate")),
    ("bind", "can bind any role to itself, including cluster-admin (bind)",
     lambda r: _has(r, "verbs", "bind")),
    ("impersonate", "can act as any user/group/SA (impersonate)",
     lambda r: _has(r, "verbs", "impersonate")),
    ("secrets-read", "can read secrets cluster-wide",
     lambda r: _has(r, "resources", "secrets")
     and _has(r, "verbs", "get", "list", "watch")),
    ("pods-create", "can create pods (schedule a pod with a privileged token)",
     lambda r: _has(r, "resources", "pods")
     and _has(r, "verbs", "create")),
    ("wildcard-all", "wildcard verb on wildcard resource (cluster-admin-equivalent)",
     lambda r: _has(r, "verbs", "*") and _has(r, "resources", "*")),
    ("token-create", "can mint service-account tokens",
     lambda r: _has(r, "resources", "serviceaccounts/token")
     and _has(r, "verbs", "create")),
]


def analyze_rule(rule):
    """Return the ids of every danger a single policy rule triggers."""
    return [rid for rid, _reason, pred in DANGEROUS if pred(rule)]


def analyze_doc(doc):
    """Return findings for one RBAC object. Empty for non-RBAC docs."""
    if not doc or doc.get("kind") not in ("Role", "ClusterRole"):
        return []
    name = doc.get("metadata", {}).get("name", "?")
    kind = doc["kind"]
    findings = []
    for rule in doc.get("rules", []) or []:
        for rid in analyze_rule(rule):
            reason = next(r for i, r, _ in DANGEROUS if i == rid)
            findings.append({"kind": kind, "name": name, "risk": rid, "reason": reason})
    return findings


def analyze_text(text):
    """Findings across a multi-doc YAML string."""
    findings = []
    for doc in yaml.safe_load_all(text):
        findings.extend(analyze_doc(doc))
    return findings


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: rbac_lint.py <manifest.yaml> [more.yaml ...]")

    total = []
    for path in sys.argv[1:]:
        findings = analyze_text(Path(path).read_text())
        for f in findings:
            print(f"  [{f['risk']:14}] {f['kind']}/{f['name']}: {f['reason']}")
        total.extend(findings)

    print()
    if total:
        print(f"{len(total)} risky RBAC rule(s) found.")
        print("Confirm each against KubiScan's live-cluster output — they should agree.")
        sys.exit(1)
    print("No risky RBAC found.")


if __name__ == "__main__":
    main()
