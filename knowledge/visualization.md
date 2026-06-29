# Visualization

## Surfaces

1. **CLI tables** — benchmark history, outcome summary, work queue (`anchor work queue`).
2. **SARIF cluster HTML** — UMAP export via `./anchor sarif visualize`.
3. **Dashboard** — `interfaces/static/anchor_dashboard.html` + `anchor_server` API.

## Dashboard data feeds

| API / file | Widget use |
| --- | --- |
| `/benchmarks/index.json` | Run history, publication tier |
| `/api/outcomes/summary` | Acceptance/rejection rates |
| `/api/work-queue/summary` | Operator next actions |
| SSE `/runs/{id}/events` | Live hunt / benchmark stream |

## Cluster visualization

- Input: embedded findings from SQLite after `sarif process`.
- Output: interactive HTML (UMAP 2D); color by cluster_id.
- Use for triage meetings—not as proof of exploitability.

## Design guidelines

- Show **validation state** badges (DETECTED / CORRELATED / REPRODUCED_REAL) on every finding card.
- Separate **tool severity** from **promotion status** visually.
- Link every dashboard row to artifact path on disk (reproducibility).
- Default history view: **published tier only**; development runs behind a toggle.

## Telemetry without noise

- Aggregate benchmark metrics in `benchmark.json` — do not stream full SARIF to the browser.
- Trend lines from `anchor_trends.py` — compare published runs only unless `--include-development`.
