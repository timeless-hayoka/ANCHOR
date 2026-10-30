# AI-Forge-Protocol — Vault Note

## ANCHOR Subsystem Informed
`knowledge/pipeline.py` · `target_forge.py`

## Source
https://github.com/timeless-hayoka/AI-Forge-Protocol

## Key Lesson
Structured protocol envelopes (phase gates, explicit hand-off schemas) let
autonomous agents hand work between stages without context loss. ANCHOR's
target-forge and knowledge pipeline should adopt the same pattern: every
stage emits a typed artifact the next stage can validate before consuming.

## Applicability
- Phase-gate validation prevents silent drift between discovery → analysis.
- Envelope schema doubles as an audit trail.
