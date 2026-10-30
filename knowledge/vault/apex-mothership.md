# apex-mothership — Vault Note

## ANCHOR Subsystem Informed
`trinity_lead_state_machine.py` · `anchor_work_queue.py`

## Source
https://github.com/timeless-hayoka/apex-mothership

## Key Lesson
A single lead state machine that owns task dispatch, heartbeat collection,
and failure escalation keeps multi-agent coordination deterministic.
apex-mothership showed that letting workers self-escalate causes retry
storms; routing all escalation through the lead eliminates that.
ANCHOR's trinity lead should be the sole authority for retry decisions.

## Applicability
- Workers report status; they never re-enqueue their own tasks.
- Work queue (`anchor_work_queue.py`) accepts pushes only from the lead.
