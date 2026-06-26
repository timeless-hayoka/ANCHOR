# Proof Gate

The proof gate is the core ANCHOR rule:

A plausible claim is not a finding.

## Why the gate exists

Security tools can produce:

- false positives
- incomplete exploit stories
- benchmark-only wins that do not survive real execution
- impressive narratives with no reproducible impact

The proof gate exists to stop those from being promoted.

## What passes the gate

A claim passes only when:

- the target is in scope
- the mechanism is stated clearly
- the proof of concept is complete
- the behavior executes on real code in an authorized environment
- the impact is measurable and not just speculative

## What fails the gate

A claim fails when it depends on:

- mocked-only environments
- fabricated function paths
- missing steps or hidden assumptions
- impossible state setup
- out-of-scope attack preconditions
- ambiguous impact that cannot be demonstrated

## Gate outcomes

### Rejected

The claim does not survive testing or is not validly framed.

### Contained

The mechanism exists in some form, but the claimed impact is overstated or blocked.

### Proven

The claim reproduces with a complete path and measurable impact.

## Public language rules

Do not say:

- zero-day
- critical
- exploitable
- confirmed finding

unless the gate has already passed that level of confidence.

Prefer:

- signal
- hypothesis
- pending reproduction
- reproduced on authorized fork
- council accepted

## Relationship to tools

Static analyzers, fuzzers, symbolic execution, and LLM reasoning all feed the gate.

None of them are the gate.

Forge-style reproduction is the hard boundary between suggestion and finding.
