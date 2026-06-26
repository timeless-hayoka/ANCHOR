# Benchmarks

Benchmarks let other researchers evaluate ANCHOR by outcome and method.

## Purpose

Each benchmark answers:

- what was tested
- how it was tested
- what was detected
- what reproduced
- what failed to reproduce
- what the system learned

## Required sections

Every benchmark record should include:

- Target
- Scope
- Methodology
- Tooling
- Detection results
- Reproduction results
- False positives
- False negatives
- Lessons learned
- Evidence artifacts

## Current benchmark families

- [damn-vulnerable-defi](damn-vulnerable-defi/README.md)
- [ethernaut](ethernaut/README.md)
- [openzeppelin](openzeppelin/README.md)
- [custom](custom/README.md)

## Interpretation rule

A benchmark win is not a meaningful signal unless the reproduction result is clear.

Detection-only numbers are useful, but reproduction is what makes the benchmark persuasive.
