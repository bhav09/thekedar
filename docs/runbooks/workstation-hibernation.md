# On-call runbook — workstation hibernation / wake failures

## Symptoms
- @Coder tasks fail at boot/sync step
- Dashboard workstation-health stuck in `booting`

## Immediate actions
1. Run hibernate monitor manually: `thekedar-orchestrator hibernate`
2. Verify `GCP_PROJECT_ID` and workstation config ID on workspace row
3. For local dev, expect simulated boot — check Postgres `workstation_health` table

## Cost control
- Idle workstations should transition to `sleeping` after 30 minutes without activity
