# Evidence Lifecycle

ANCHOR treats evidence as an object that matures over time.

## Lifecycle stages

### 1. Signal captured

A tool, trace, benchmark, or reviewer notices a possible issue.

Artifacts may include:

- detector hit
- trace snippet
- source location
- state delta note

### 2. Hypothesis recorded

The suspected issue is written in falsifiable form.

Artifacts may include:

- target contract
- mechanism summary
- expected impact
- falsifier conditions

### 3. Reproduction attempted

The team creates a real test path.

Artifacts may include:

- Foundry test
- fork configuration
- calldata sequence
- preconditions
- observed revert or success state

### 4. Reproduced real

The issue executes end to end.

Artifacts may include:

- passing PoC
- logs
- balances before and after
- assertion count
- final impact measurement

### 5. Council accepted

The evidence is reviewed and the framing is approved.

Artifacts may include:

- severity rationale
- scope decision
- known-issue check
- alternative explanation check

### 6. Report ready

The issue is ready for external communication.

Artifacts may include:

- Markdown report
- remediation note
- benchmark annotation
- disclosure packaging

### 7. Archived

The case is preserved for future verification.

Artifacts may include:

- signed evidence bundle
- benchmark record
- reproduction command
- lessons learned

## Integrity goals

Evidence should be:

- reproducible
- attributable to a specific run
- linked to the exact hypothesis
- exportable
- tamper-evident

## Bundle philosophy

A signed evidence bundle is not legal chain of custody by itself.

It is a tamper-evident local artifact that helps reviewers verify:

- what was claimed
- what was tested
- what reproduced
- which run produced the result
