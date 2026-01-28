"""Offline tests for the RBAC linter, plus a check that the risky fixture trips
every planted risk and the clean workload trips none.

No cluster, no KubiScan. The point of the linter is to catch escalation in the
YAML before anything is applied, so the tests run on YAML alone.

Run:  python -m pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import rbac_lint  # noqa: E402

K8S = Path(__file__).resolve().parent.parent / "k8s"


def role(*rules, kind="ClusterRole", name="r"):
    return {"kind": kind, "metadata": {"name": name}, "rules": list(rules)}


class TestSingleRule:
    def test_escalate_flagged(self):
        r = {"apiGroups": ["rbac.authorization.k8s.io"],
             "resources": ["clusterroles"], "verbs": ["escalate"]}
        assert "escalate" in rbac_lint.analyze_rule(r)

    def test_bind_flagged(self):
        r = {"resources": ["clusterrolebindings"], "verbs": ["bind"]}
        assert "bind" in rbac_lint.analyze_rule(r)

    def test_secret_read_flagged(self):
        r = {"apiGroups": [""], "resources": ["secrets"], "verbs": ["get", "list"]}
        assert "secrets-read" in rbac_lint.analyze_rule(r)

    def test_pod_create_flagged(self):
        r = {"resources": ["pods"], "verbs": ["create"]}
        assert "pods-create" in rbac_lint.analyze_rule(r)

    def test_wildcard_flagged(self):
        r = {"apiGroups": ["*"], "resources": ["*"], "verbs": ["*"]}
        assert "wildcard-all" in rbac_lint.analyze_rule(r)

    def test_benign_rule_is_clean(self):
        # Reading configmaps is not an escalation.
        r = {"apiGroups": [""], "resources": ["configmaps"], "verbs": ["get"]}
        assert rbac_lint.analyze_rule(r) == []

    def test_listing_pods_is_not_creating_them(self):
        # get/list on pods is fine; only create is the escalation.
        r = {"resources": ["pods"], "verbs": ["get", "list"]}
        assert "pods-create" not in rbac_lint.analyze_rule(r)


class TestDoc:
    def test_non_rbac_doc_ignored(self):
        assert rbac_lint.analyze_doc({"kind": "ConfigMap"}) == []

    def test_wildcard_verb_covers_specific_checks(self):
        # A rule with verbs:["*"] on secrets should still flag secrets-read,
        # because "*" includes get/list/watch.
        r = {"resources": ["secrets"], "verbs": ["*"]}
        assert "secrets-read" in rbac_lint.analyze_rule(r)


class TestFixtures:
    def test_risky_fixture_trips_all_planted_risks(self):
        findings = rbac_lint.analyze_text((K8S / "risky-rbac.yaml").read_text())
        risks = {f["risk"] for f in findings}
        # Every escalation planted in the fixture must be caught.
        for expected in ("escalate", "bind", "secrets-read", "pods-create", "wildcard-all"):
            assert expected in risks, f"{expected} not caught in fixture"

    def test_clean_workload_has_no_risky_rbac(self):
        # demo-workload.yaml defines a ServiceAccount + Deployment, no Roles.
        findings = rbac_lint.analyze_text((K8S / "demo-workload.yaml").read_text())
        assert findings == []


# --- regressions from the first real cluster run, 2026-08-12 -----------------
#
# Both of these shipped green. The unit tests all passed because every one of
# them fed analyze_text a hand-written manifest, which is not the shape the
# tool actually meets in use.


def test_kubectl_list_wrapper_is_traversed():
    """kubectl -o json wraps everything in kind: List.

    The original analyze_doc checked the top-level kind, saw "List", and
    returned []. Run against a live cluster holding four cluster-admin
    equivalent roles it printed "No risky RBAC found" and exited 0.
    """
    doc = """
    kind: List
    apiVersion: v1
    items:
      - kind: ClusterRole
        metadata: {name: sneaky}
        rules:
          - apiGroups: ["*"]
            resources: ["*"]
            verbs: ["*"]
    """
    findings = rbac_lint.analyze_text(doc)
    assert findings, "List wrapper must be traversed, not skipped"
    assert any(f["risk"] == "wildcard-all" for f in findings)


def test_typed_list_kinds_are_traversed():
    """kubectl also emits ClusterRoleList / RoleList depending on invocation."""
    doc = """
    kind: ClusterRoleList
    items:
      - kind: ClusterRole
        metadata: {name: sneaky}
        rules:
          - apiGroups: [""]
            resources: ["secrets"]
            verbs: ["get"]
    """
    assert any(f["risk"] == "secrets-read" for f in rbac_lint.analyze_text(doc))


def test_builtin_roles_are_classified_not_counted():
    """Kubernetes' own roles carry kubernetes.io/bootstrapping: rbac-defaults.

    cluster-admin really can escalate. Reporting it is true and useless: the
    live run produced 62 findings, 47 of them on roles Kubernetes installed
    itself. Flagged, still printed, but not what the exit code is about.
    """
    doc = """
    kind: ClusterRole
    metadata:
      name: cluster-admin
      labels:
        kubernetes.io/bootstrapping: rbac-defaults
    rules:
      - apiGroups: ["*"]
        resources: ["*"]
        verbs: ["*"]
    """
    findings = rbac_lint.analyze_text(doc)
    assert findings, "built-ins are still analyzed"
    assert all(f["builtin"] for f in findings), "and marked as built-in"


def test_custom_role_is_not_marked_builtin():
    doc = """
    kind: ClusterRole
    metadata: {name: lab-wildcard}
    rules:
      - apiGroups: ["*"]
        resources: ["*"]
        verbs: ["*"]
    """
    assert all(not f["builtin"] for f in rbac_lint.analyze_text(doc))
