# Threat Model

ANCHOR is built for authorized smart-contract security research on the operator's own machine.

## In-scope threats for ANCHOR itself

### 1. Overclaiming risk

The biggest product risk is not code execution. It is false confidence.

Examples:

- a tool hit gets spoken about as a finding
- a partial PoC gets presented as complete
- a benchmark quirk gets described as production impact

Mitigation:

- explicit proof gate
- council review
- evidence lifecycle states
- benchmark records with false-positive accounting

### 2. Local evidence tampering

A user or process could alter output after a run.

Mitigation:

- signed evidence bundles
- run provenance
- integrity digests
- archived artifacts

### 3. Scope drift

A hunt can slide from authorized review into prohibited testing or invalid framing.

Mitigation:

- scope confirmation step
- target notes
- explicit prohibited-actions awareness
- report gate before publication

### 4. Unsafe hunt orchestration

A local run server that launches arbitrary scripts can create unnecessary risk.

Mitigation:

- fixed project roots
- allowlisted scripts
- path validation
- least-privilege local usage

### 5. Event-stream reliability failure

If the live stream drops events, the operator can misunderstand the case state.

Mitigation:

- replayable event history
- client reconnect behavior
- final registry verification

## Non-goals

ANCHOR is not trying to:

- replace human judgment
- provide legal admissibility guarantees
- authorize targets on the operator's behalf
- turn weak signals into marketable findings

## Security posture

ANCHOR should be evaluated as:

- a local research workflow
- an evidence-preserving run service
- a disciplined proof gate

not as a hype-driven autonomous attacker.
