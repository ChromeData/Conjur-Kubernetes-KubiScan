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
