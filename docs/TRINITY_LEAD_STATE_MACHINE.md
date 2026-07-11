# Trinity Lead State Machine

Trinity leads move through a strict, evidence-gated lifecycle. A plausible
claim is not a finding (see `TRINITY_RUBRIC.md`) — a lead only advances when
the evidence required for its next state is present, reviewable, and tied to
an authorized target.

The machine-readable contract lives in `trinity_lead_state_machine.py`
(states, transitions, validation) with a JSON Schema mirror in
`schemas/trinity_schemas/trinity_lead_state_machine.schema.json` and a worked
example in `examples/trinity_lead_state_machine.example.json`.

## States

```text
signal
  -> hypothesis
  -> repro_attempted
  -> reproduced_real
  -> council_accepted
  -> report_ready
```

Any active state (`signal`, `hypothesis`, `repro_attempted`) can also route to
a terminal kill state: `rejected`, `out_of_scope`, or `duplicate`. Two extra
states handle stalls without losing history:

- `needs_environment` — reproduction could not run (missing fork/tooling);
  returns to `repro_attempted` once resolved.
- `needs_manual_review` — a human needs to look before the lead can advance;
  can fall back to `hypothesis` or advance to `council_accepted`.

`report_ready`, `rejected`, `out_of_scope`, and `duplicate` are terminal —
there is no transition out of them.

## Allowed transitions

| From | To |
| --- | --- |
| `signal` | `hypothesis`, `rejected`, `out_of_scope`, `duplicate` |
| `hypothesis` | `repro_attempted`, `rejected`, `out_of_scope`, `duplicate`, `needs_manual_review` |
| `repro_attempted` | `reproduced_real`, `needs_environment`, `rejected`, `out_of_scope` |
| `needs_environment` | `repro_attempted`, `rejected` |
| `reproduced_real` | `council_accepted`, `needs_manual_review`, `rejected` |
| `needs_manual_review` | `council_accepted`, `hypothesis`, `rejected` |
| `council_accepted` | `report_ready`, `rejected` |
| `report_ready` / `rejected` / `out_of_scope` / `duplicate` | *(terminal)* |

Any transition not listed above is rejected by `can_transition` /
`apply_transition` in `trinity_lead_state_machine.py`.

## Required fields by state

Each lead record carries the fields the Trinity rubric asks for: `claim`,
`scope`, `mechanism`, `falsifier`, `repro_plan`, and `impact_boundary`. A
state cannot be reached until its cumulative field set is non-empty:

| State | Required fields |
| --- | --- |
| `signal` | *(none — a raw signal)* |
| `hypothesis` | `claim`, `scope`, `mechanism`, `falsifier` |
| `repro_attempted` / `needs_environment` | + `repro_plan` |
| `reproduced_real` / `needs_manual_review` | + `repro_plan`, and at least one `evidence_refs` entry |
| `council_accepted` | + `impact_boundary`, and at least one `review_refs` entry |
| `report_ready` | all of the above |

This is the enforcement mechanism for the acceptance criterion "prevent
direct promotion to report-ready without reproduction and impact evidence":
the transition graph only allows `report_ready` via `council_accepted`, and
`council_accepted` cannot be reached without reproduction evidence
(`evidence_refs`) and an `impact_boundary` already recorded.

## Serialized lead record

```json
{
  "schema_version": "1.0",
  "lead_id": "lead_001",
  "target": "authorized-demo-target",
  "scope_status": "authorized",
  "state": "report_ready",
  "title": "Unchecked external call may break accounting invariant",
  "claim": "...",
  "scope": "...",
  "mechanism": "...",
  "falsifier": "...",
  "repro_plan": "...",
  "impact_boundary": "...",
  "evidence_refs": ["evidence/lead_001/forge_output.txt"],
  "review_refs": ["reviews/lead_001/council_review.md"],
  "created_at": "2026-07-03T00:00:00Z",
  "updated_at": "2026-07-03T00:30:00Z",
  "events": [
    {
      "event_id": "evt_001",
      "lead_id": "lead_001",
      "from_state": null,
      "to_state": "signal",
      "actor": "trinity",
      "reason": "Initial signal created from authorized analysis.",
      "evidence_refs": [],
      "created_at": "2026-07-03T00:00:00Z"
    }
  ]
}
```

See `examples/trinity_lead_state_machine.example.json` for a full lead that
walks from `signal` to `report_ready`.

## Validation errors

`validate_lead()` returns a list of plain-English error strings (empty list
means the record is internally consistent for its current state):

- unknown `state` or `scope_status`
- missing `lead_id`, `target`, or `title`
- a required field for the current state is empty
- the current state requires `evidence_refs` or `review_refs` and none are
  present

`apply_transition()` raises `LeadTransitionError` (message is the joined
validation errors) if the target state is illegal for the current state, or
if the resulting record fails `validate_lead()`.

## Surfacing state

`render_lead_state()` produces a one-line console/run-log summary, e.g.:

```
[lead_001] report_ready — Unchecked external call may break accounting invariant (OK)
```

The CLI exposes this over a lead record file:

```
anchor lead show path/to/lead.json
anchor lead show path/to/lead.json --json
```

`show --json` also runs `validate_lead()` and includes any errors, so a lead
can be checked in CI or before it's promoted without hand-reading the JSON.
