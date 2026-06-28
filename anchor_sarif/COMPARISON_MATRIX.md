# Static Analysis Tool Comparison for DeFi / Smart Contract Targets

Focus: False Positive Rate + SWC Coverage (based on typical DeFi benchmarks like Damn Vulnerable DeFi, real bounties, and internal testing as of 2026).

| Tool          | False Positive Rate (DeFi) | SWC Coverage | Speed     | SARIF/Structured Output | Best For                          | Ensemble Value with ANCHOR | Notes |
|---------------|----------------------------|--------------|-----------|--------------------------|-----------------------------------|----------------------------|-------|
| **Slither**   | Medium                     | Excellent (90%+) | Very Fast | JSON + SARIF            | Broad detection, CI             | High (baseline)           | Already core to ANCHOR |
| **Aderyn**    | Low-Medium                 | Very Good    | Extremely Fast | JSON                    | Fast CI, high-severity focus    | Very High                 | Excellent modern complement |
| **Mythril**   | Medium-High                | Good         | Slow      | JSON                    | Deep symbolic paths             | High                      | Great for complex reentrancy |
| **Halmos**    | Low                        | Good (invariants) | Medium    | JSON                    | Invariant & property testing    | Very High                 | Strong for proof gate |
| **CodeQL**    | Low                        | Excellent    | Medium    | Native SARIF            | Deep taint + dataflow           | High                      | Already integrated |
| **Semgrep**   | Medium                     | Good         | Very Fast | Native SARIF            | Custom rules, speed             | High                      | Already integrated |
| **Wake**      | Low-Medium                 | Good         | Fast      | JSON                    | Modern Foundry workflow         | High                      | Good developer experience |
| **SonarQube** | Low                        | Good         | Medium    | Native SARIF            | Quality + security              | Medium                    | Broader than pure security |

**Key Insights for ANCHOR**:
- **Best ensemble right now**: Slither + Aderyn + Halmos (fast + deep + invariant)
- **Lowest FP + high SWC**: Aderyn + Halmos combination
- **Deepest analysis**: Mythril + CodeQL
- The `anchor_sarif` pipeline + adapters makes it trivial to run any combination and get normalized, clustered, LLM-summarized results.

This matrix is based on real usage patterns in DeFi bug bounties and ANCHOR benchmark data.
