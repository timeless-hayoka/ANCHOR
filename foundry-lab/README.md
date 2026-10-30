# ANCHOR Foundry proof smoke lab

Self-contained **local-only** Solidity fixture. This is not evidence of a live vulnerability or a bug-bounty finding.

Run from the repository root:

```bash
cd foundry-lab
forge --version
forge test -vvv
```

The positive control demonstrates a nested callback against a deliberately vulnerable withdrawal contract. The negative control demonstrates that the effects-before-interactions implementation prevents the nested withdrawal. Neither test accesses external contracts, RPC endpoints, or real funds.

Proof criteria: both tests must pass, the positive control must observe two callbacks, and the negative control must observe one callback. Record the commit, Forge version, and full output. A passing smoke lab establishes only that the isolated harness works; real target verification requires confirmed authorization, a clean reproduction, independent review, and impact evidence.

The workflow `ANCHOR Foundry lab proof` can be launched manually from the feature branch and uploads its logs even when tests fail.
