# BUG HUNTING MAP

ANCHOR uses this map to move from vague suspicion to a reproducible, in-scope proof.

## Language Bug Shapes

### Python

- Indentation mistakes
- Type confusion
- Slow loops
- Bad imports
- Memory-heavy data use

### JavaScript

- Async timing bugs
- `undefined` or `null` errors
- Bad DOM handling
- Weak input validation

### C / C++

- Buffer overflows
- Memory leaks
- Use-after-free
- Pointer mistakes
- Unsafe string handling

### Java / C#

- Null pointer errors
- Thread bugs
- Bad exception handling
- Dependency issues

### SQL

- Injection risk
- Bad queries
- Missing indexes
- Weak permissions

### Bash / PowerShell

- Unsafe command input
- Bad file paths
- Permission mistakes
- Environment variable issues

### Rust

- Logic bugs
- Lifetime confusion
- Unsafe blocks

### Go

- Goroutine leaks
- Race conditions
- Ignored error handling

### Solidity / EVM

- Access-control mistakes
- Accounting drift
- Rounding residue
- State-machine errors
- Unsafe external call ordering
- Upgrade or initialization mistakes
- Share or asset mispricing

## What Makes Systems Stutter

### CPU

- Too many processes
- Infinite loops
- Heavy background tasks

### RAM

- Memory leaks
- Too many apps open
- Swapping to disk

### Storage

- Slow disk reads
- Full drive
- Fragmented or failing storage

### GPU

- Driver issues
- Overheating
- Heavy rendering load

### Network

- Packet loss
- DNS delay
- Bad routing
- Weak Wi-Fi

### OS

- Bad drivers
- Corrupted files
- Permission conflicts
- Update problems

## Bug Hunting Checklist

### Inputs

- What data enters the system?
- Can bad input break it?
- Are types and bounds checked?

### Memory

- Is RAM usage growing forever?
- Are there leaks?
- Do crashes appear only under load?

### Timing

- Does the bug happen only sometimes?
- Could two tasks touch the same data?
- Does order of operations change the outcome?

### Files

- Are paths safe?
- Are permissions correct?
- Are files locked, stale, or missing?

### Network

- Are requests failing?
- Are timeouts handled?
- Is returned data validated?

### Logs

- What error appears first?
- What changed before the bug?
- Can the bug be repeated?

## ANCHOR Translation

For ANCHOR, convert each suspicion into:

`language -> bug type -> symptom -> hypothesis -> repro path -> impact -> fix pattern`

For smart contracts, bias toward:

- Authorization boundaries
- Asset accounting
- Queue and state transitions
- Rounding and residual balances
- Partial execution and retry paths
- Shutdown, pause, or recovery behavior

Do not promote a claim just because it is plausible. Promote it only when the repro survives the proof gate.
