# MDRRMO Naic UAT Sign-off

**Status: COMPLETE**

**Completed:** 2026-08-10

This sign-off records functional user-acceptance testing of the deployment
candidate. It does not by itself authorize production deployment.

## Passed UAT areas

- Authentication and session behavior
- Role and permission boundaries
- Disaster-event lifecycle
- Barangay report data integrity
- Evacuation-center report data integrity
- Validation and correction/resubmission workflow
- SitRep reporting and current Excel/PDF exports
- Audit trail behavior
- Backup creation and archive verification
- Database outage handling, application logging, reconnection, and
  failed-write rollback behavior

## Items intentionally outside this UAT sign-off

- Authoritative barangay/PSGC master-data approval by MDRRMO/LGU
- Authoritative alert-level terminology and operational meaning
- Official MDRRMO Excel/PDF layout templates
- Production hostname, HTTPS/TLS, firewall/network placement
- Production Google OIDC redirect registration
- Off-machine/off-site backup storage policy

The official report layouts remain provisional until the office provides
the authoritative formats.
