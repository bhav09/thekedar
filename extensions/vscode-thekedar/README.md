# Thekedar VS Code Extension (stub — M6 D3)

Minimal extension scaffold for surfacing dashboard widgets inside the IDE.

## Planned commands
- `thekedar.showActiveRuns` — fetch `/api/v1/widgets/active-runs`
- `thekedar.approvePending` — open dashboard approval deep link

## Local dev
Point `THEKEDAR_DASHBOARD_URL` at your dashboard-hub instance and implement
`fetch` calls from a VS Code webview panel.

This directory is a placeholder; full extension packaging is post-GA.
