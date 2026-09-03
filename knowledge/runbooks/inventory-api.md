# inventory-api Runbook

## Empty search results

An empty inventory-api log result is not proof that the service is healthy. Check whether the
requested time window is correct and compare request volume with the normal baseline.

## Safe response

Prefer read-only metrics and deployment checks before any action. If evidence is incomplete,
report what is unknown instead of inventing a root cause.

## Escalation

Escalate when inventory updates are missing for more than fifteen minutes or when deployment
state cannot be confirmed from the operations source.
