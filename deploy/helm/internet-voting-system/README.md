# internet-voting-system Helm chart

Renders the prototype API + static web client on Kubernetes.

```bash
# Demo (memory-only, no persistence)
helm install ivs deploy/helm/internet-voting-system \
  --set storage.backend=memory

# Single-replica SQLite with a 5Gi PVC
helm install ivs deploy/helm/internet-voting-system \
  --set storage.backend=sqlite \
  --set storage.sqlite.pvcSize=5Gi

# Multi-replica with a pre-existing Postgres
helm install ivs deploy/helm/internet-voting-system \
  --set storage.backend=postgres \
  --set storage.postgres.dsn="postgresql://voting:secret@pg.svc:5432/voting"
```

## What's in the chart

| Object | Purpose |
|---|---|
| `Deployment ivs-api` | API pods. ``replicaCount`` is forced to 1 when storage=sqlite to avoid PVC contention. |
| `Service ivs-api` | ClusterIP for `:8787` |
| `Deployment ivs-web` | nginx serving the static client |
| `Service ivs-web` | ClusterIP for `:80` |
| `PersistentVolumeClaim ivs-data` | Only rendered when storage=sqlite |
| `Secret ivs-pg` | Holds the DSN; only rendered when storage=postgres and no existingSecret is provided |
| `PodDisruptionBudget ivs-api` | Default minAvailable=1 |

## Production caveats

This chart is intentionally minimal so it can be audited at a glance. Before
running it in production add the following yourself:

1. **NetworkPolicy** restricting API egress to the Postgres service only.
2. **PodSecurityAdmission** label on the namespace (`restricted` profile).
3. **HorizontalPodAutoscaler** if you keep storage=postgres.
4. **External secrets** (External Secrets Operator / Vault) for the DSN.
5. **Service mesh / sidecar** mTLS between API and Postgres.
6. **CDN/WAF** in front of the Service — see `docs/operations.md`.
