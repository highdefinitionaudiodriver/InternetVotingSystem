# Grafana dashboards

`internet-voting-system.json` is a starter dashboard for the prototype API.

## Import

1. In Grafana, open **Dashboards → New → Import**.
2. Paste the contents of `internet-voting-system.json`, or upload it via
   "Upload JSON file".
3. When prompted for the Prometheus datasource, pick the one that scrapes
   `internet_voting_*` metrics. The dashboard template variable
   `DS_PROMETHEUS` will be wired up automatically.

## Panels

| Panel | PromQL | Purpose |
|---|---|---|
| Active elections | `internet_voting_total_elections` | Sanity gauge during launch |
| Total ballots recorded | `internet_voting_total_ballots_recorded` | Headline counter |
| Audit log entries | `internet_voting_audit_log_entries` | Operational growth indicator |
| Ballot intake rate (per minute) | `rate(internet_voting_total_ballots_recorded[5m]) * 60` | Spot bursts / DDoS / dead-air |
| Ballots per election | `internet_voting_election_ballots` | Per-election timeline split by `status` |

## Privacy guarantees

The dashboard only consumes the safe-to-expose aggregates published by
`/metrics`. It never displays:

- `voter_hash`
- `ballot_id`, `receipt_hash`
- candidate-level vote counts (those live behind `/elections/{id}/tally`,
  which is reserved for the post-election publication step)
- contents of the audit log

If you fork this dashboard, do not add panels that scrape `/elections/.../tally`
or `/audit-log` directly — those routes return PII-adjacent or candidate-
level data that must not flow into a monitoring stack.
