# ANCHOR Vault

This file stores the durable brief for ANCHOR's benchmark roadmap and corpus direction.

## Current Direction

ANCHOR should treat benchmark growth as a roadmap, not as a loose list of practice sites.
The priority is measurable progress: reproducible runs, clear evidence, and benchmark families
that can be compared over time.
## Sibling Project: Apex Mothership

`apex-mothership` is a private supporting project in the same ecosystem. It is a Python-based
security command center with a FastAPI backend and a React dashboard.

Captured brief from the repo:

- unified security command center for network auditing, OSINT, and AI-assisted research
- live telemetry for CPU, RAM, disk, and network state
- AI bridge for security insights and strategy
- SSD-backed mission/report vaulting
- script discovery for custom `.py`, `.sh`, and `.js` tools

How it relates to ANCHOR:

- ANCHOR remains the flagship evidence gate and benchmark system
- Apex Mothership is a supporting operations surface and dashboard layer
- ANCHOR should stay evidence-first while Apex Mothership handles operator-facing command-and-control style views

Integration detail is captured in [docs/APEX_MOTHERSHIP_INTEGRATION.md](APEX_MOTHERSHIP_INTEGRATION.md).


## Tier 1: Core Benchmark Corpus

These are the official benchmark family targets.

| Platform | Purpose | Status |
| --- | --- | --- |
| Damn Vulnerable DeFi | Primary Foundry benchmark corpus | In progress |
| Ethernaut | EVM fundamentals and exploit patterns | Next |
| Capture The Ether | Core EVM exploit techniques | Planned |

Why these come first:

- They are repeatable.
- They are well understood.
- They can become regression tests.
- They build a stable evaluation baseline for ANCHOR.

## Tier 2: Advanced Smart Contract Research

These expand ANCHOR beyond basic exploit reproduction.

| Platform | Focus |
| --- | --- |
| Paradigm CTF | Advanced EVM, bytecode, cross-chain |
| Solodit | Historical audit findings and defensive learning |

Use these after the Damn Vulnerable DeFi harness is stable.

## Tier 3: Web Security Benchmark Pack

These are best treated as a future ANCHOR Web family, separate from the smart-contract suite.

- PortSwigger Web Security Academy
- VulnForge Academy
- Vulnshop
- web-vuln-by-example
- HackLab

Suggested family split:

- `benchmarks/web3/`
- `benchmarks/web/`
- `benchmarks/audits/`

## Tier 4: Real Bug Bounty Programs

These are not benchmarks. They are authorized targets where the method gets exercised.

- Immunefi
- HackerOne
- Bugcrowd
- Code4rena
- Sherlock

These should feed the outcome ledger once evidence is reproducible and the target stays in scope.

## Suggested Benchmark Layout

```text
benchmarks/
├── web3/
│   ├── damn-vulnerable-defi/
│   ├── ethernaut/
│   ├── capture-the-ether/
│   └── paradigm/
├── web/
│   ├── portswigger/
│   ├── vulnforge/
│   ├── vulnshop/
│   └── hacklab/
├── audits/
│   └── solodit/
└── index.json
```

## Success Metrics

Use the same metrics across every benchmark family:

- Detection rate
- Reproduction rate
- False positives
- False negatives
- Time to reproduce
- Evidence completeness
- Outcome status
- Lessons learned

Keeping these stable makes cross-family comparison possible without changing the evaluation philosophy.

## Roadmap Rule

Finish the Damn Vulnerable DeFi family first.

Once DVD is consistently reproducible and well-instrumented, Ethernaut and the other benchmark families can plug into a mature harness instead of forcing another redesign.


## Knowledge intake

- [docs/ANCHOR_KNOWLEDGE_INGESTION.md](ANCHOR_KNOWLEDGE_INGESTION.md) - top repos to mine first and how to extract reusable notes
- [docs/ANCHOR_WORK_QUEUE.md](ANCHOR_WORK_QUEUE.md) - current tracked work items and follow-up backlog

## Source Repo Notes

### AI-Forge-Protocol

- Source: https://github.com/timeless-hayoka/AI-Forge-Protocol
- What it is: a validation and patch-gating workflow for AI-assisted code changes.
- Core lesson: generated code should survive a reproducible harness and a real check stage before it is treated as safe to ship.
- Reusable pattern for ANCHOR: use a measurable gate that separates plausible output from shippable output, and store investigation output so it can be reviewed later.
- Best ANCHOR fit: proof gate, benchmark validation, and patch admission control.
- Supporting scripts in source repo: `scripts/run.sh`, `scripts/verification_check.sh`
- Related docs in source repo: `docs/ENGINEERING_AUDIT.md`, `docs/INTEGRATION_TARGETS.md`, `docs/LEADERBOARD.md`

