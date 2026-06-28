# ANCHOR Script Registry Design

This document defines a guardrailed script registry for ANCHOR.
The registry is meant to support benchmark helpers and authorized local tooling without becoming an open-ended execution surface.

## Goals

- make approved scripts discoverable
- keep execution auditable
- distinguish benchmark helpers from risky utilities
- prevent hidden command execution paths

## Registry Scope

The registry may include:

- benchmark helper scripts
- evidence formatting scripts
- local report transforms
- safe analysis utilities
- repo-specific wrappers

The registry should not include unrestricted offensive tooling.

## Registry Record Shape

Each script entry should include:

- `id`
- `name`
- `description`
- `path`
- `language`
- `owner`
- `scope`
- `allowed_inputs`
- `requires_authorization`
- `output_types`
- `audit_tag`

Example:

```json
{
  "id": "dvd-nonce-search",
  "name": "Wallet Mining Nonce Search",
  "description": "Finds a Safe CREATE2 nonce for the wallet-mining benchmark.",
  "path": "test/wallet-mining/find_nonce.py",
  "language": "python",
  "owner": "ANCHOR",
  "scope": "benchmark",
  "allowed_inputs": ["factory", "initCodeHash", "initializerHash", "target"],
  "requires_authorization": true,
  "output_types": ["text/nonce"],
  "audit_tag": "benchmark-helper"
}
```

## Execution Rules

- Scripts are read from an allowlisted registry only.
- Every execution is logged.
- Benchmarks can call helpers automatically when the helper is in scope.
- External or live-target actions require explicit authorization markers.

## Storage Rules

Each execution should write an audit entry containing:

- script id
- timestamp
- caller
- input summary
- output summary
- success or failure
- linked benchmark or outcome id

## Interface Shape

The registry can be exposed as:

- a JSON manifest
- a CLI listing command
- a dashboard panel
- an API endpoint for approved consumers

## Safety Boundaries

Do not allow the registry to become:

- a generic shell launcher
- an unreviewed arbitrary-code runner
- a silent persistence mechanism
- a replacement for proof-gated workflow

## Implementation Priority

Start with benchmark helpers that are already part of the repo and then grow the registry as the benchmark corpus stabilizes.
