# Security

## No-Egress Proof

DomeKit includes a verification script that proves zero network egress:

```bash
./scripts/no-egress-proof.sh apps/health-poc/domekit.yaml
```

This script:
1. Validates manifest blocks network (`outbound: deny`)
2. Tests tool calling loop with mocked model (no real network)
3. Verifies policy engine denies all outbound hosts
4. Confirms zero socket connections during request processing

## Best Practices

**DO:**
- Start with `policy_mode: local_only`
- Use exact paths for SQLite databases (no globs)
- Keep `network.outbound: deny` in production
- Review audit logs regularly
- Use `max_rows` and `max_bytes` limits
- Run with least privilege (non-root user)

**DON'T:**
- Use `policy_mode: developer` in production
- Allow `/` or `*` in filesystem paths
- Disable audit logging
- Run as root
- Expose the runtime to public networks

## Threat Model

| Threat | Mitigation |
|--------|------------|
| **Data exfiltration via network** | `network.outbound: deny` blocks all egress |
| **Unauthorized database access** | Manifest whitelist + path validation |
| **Path traversal attacks** | Path resolution + prefix validation |
| **SQL injection** | Read-only mode + parameterized queries |
| **Privilege escalation** | No shell execution, sandboxed tools |
| **Audit log tampering** | Append-only JSONL, file permissions |

## Compliance

DomeKit's audit trails and policy enforcement can support compliance with:
- **HIPAA** — local processing, audit trails, access controls
- **GDPR** — data minimization, right to audit, local storage
- **SOC 2** — audit logging, access controls, policy enforcement
- **PCI DSS** — data isolation, audit trails, least privilege

DomeKit provides tools for compliance but doesn't guarantee it. Consult your compliance team.
