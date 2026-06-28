# ANCHOR Work Queue

This queue keeps the current implementation work visible and easy to track.

## In progress now

- [x] Wire dashboard fields into the live ANCHOR UI
- [x] Scaffold the script registry JSON and loader
- [x] Add the evidence-storage interface to the benchmark runner
- [x] Record the work in the repo as durable docs

## Follow-up tasks

- [ ] Add a live script-registry endpoint to the dashboard sidebar
- [ ] Promote benchmark storage metadata into the published manifest
- [ ] Add a small report view for latest evidence bundles
- [ ] Convert the highest-value backlog items into GitHub issues
- [ ] Ingest the top 3 repo notes into the ANCHOR vault

## Suggested issue titles

- `ANCHOR: wire benchmark overview into dashboard`
- `ANCHOR: add shared evidence storage manifest`
- `ANCHOR: expose guarded script registry`
- `ANCHOR: import AI-Forge-Protocol proof-gate lessons`
- `ANCHOR: import bounty-bot outcome workflow lessons`
- `ANCHOR: import apex-mothership dashboard lessons`

## Definition of done

- benchmark runs show the latest storage and evidence paths
- the dashboard can explain what is running without opening the terminal
- the script registry is loaded from a JSON source, not hardcoded
- the vault has short notes from the top 3 source repos
- future benchmark work can be added without changing the core wiring again

## GitHub issues

- #1 - ANCHOR: add ScaBench scored report to benchmark overview
- #2 - ANCHOR: expose guarded script registry from the dashboard sidebar
- #3 - ANCHOR: promote benchmark storage metadata into the published manifest
- #4 - ANCHOR: add a latest evidence bundle report view
- #5 - ANCHOR: ingest source repo notes into the vault
