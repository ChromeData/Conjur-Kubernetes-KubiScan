#!/usr/bin/env bash
# Configure Conjur's Kubernetes authenticator and load the host identity for the
# demo workload. This is the fiddly part of the lab — see LAB-NOTES for the cert
# gotchas. Conjur + the authenticator are upstream CyberArk; this wires them up.

set -euo pipefail

NS_CONJUR="conjur"
NS_APP="app"
ACCOUNT="lab"

echo "==> Locating the Conjur pod"
POD="$(kubectl get pods -n "${NS_CONJUR}" -l app=conjur-oss -o jsonpath='{.items[0].metadata.name}')"
echo "    ${POD}"

echo "==> Enabling the authn-k8s authenticator (service id: lab-cluster)"
# In Conjur this is enabled via CONJUR_AUTHENTICATORS + policy. Policy load below
# defines the authenticator webservice and the app host.
kubectl exec -n "${NS_CONJUR}" "${POD}" -- bash -c "cat > /tmp/authn.yml" <<'POLICY'
- !policy
  id: conjur/authn-k8s/lab-cluster
  body:
    - !webservice
    - !variable kubernetes/service-account-token
    - !variable kubernetes/ca-cert
    - !variable kubernetes/api-url
    - !group apps

- !policy
  id: app-identities
  body:
    - !host
      id: app/secret-consumer
      annotations:
        authn-k8s/namespace: app
        authn-k8s/service-account: secret-consumer

- !grant
  role: !group conjur/authn-k8s/lab-cluster/apps
  member: !host app-identities/app/secret-consumer
POLICY

echo "==> Loading authenticator + identity policy"
kubectl exec -n "${NS_CONJUR}" "${POD}" -- conjurctl policy load "${ACCOUNT}" /tmp/authn.yml || {
  echo "Policy load failed — most often a leftover host from a prior run. See LAB-NOTES."
  exit 1
}

cat <<EOF

  authn-k8s configured for service id 'lab-cluster'.
  Next: 'make demo' to deploy the workload, then check it authenticates.

  If the pod gets a 401 from Conjur, it is almost always the CA cert or the
  namespace/service-account annotations not matching. That debugging IS the lab —
  write down the exact mismatch and fix in LAB-NOTES.
EOF
