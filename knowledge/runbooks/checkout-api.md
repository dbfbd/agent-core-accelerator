# checkout-api Runbook

## Payment upstream timeout

When checkout-api error rate rises together with messages containing "payment upstream timeout",
first compare the latest deployment with the last known healthy version. Confirm that payment
latency is elevated before changing checkout-api itself.

## Safe response

Collect metrics, logs, and deployment evidence before proposing a restart. A restart is a
high-risk action and requires explicit operator approval. If the payment dependency remains
unhealthy, restarting checkout-api may only hide the symptom briefly.

## Recovery confirmation

After an approved action, verify that error rate and p95 latency return toward baseline. Record
the evidence IDs used for the decision and state any remaining uncertainty.
