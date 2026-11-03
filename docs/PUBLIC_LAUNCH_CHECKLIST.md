# Public onboarding follow-through — 2026-11-03

| Requested task | Result |
| --- | --- |
| Confirm post-merge checks | PR #30 merge commit `62aa7294235d6b824c7c008e02d553011b6953e4`: Python baseline (including Foundry job) succeeded; Pages deployment succeeded |
| Improve homepage pitch | Clear researcher audience, evidence workflow, static-demo boundary, and first-local-run action |
| Add getting-started guide | Website page plus `GETTING_STARTED.md`; fresh environment install and four-case local corpus execution verified |
| Resolve missing benchmark records | Three unsubstantiated historical publications withdrawn to development/evidence_missing, with previous states and missing paths preserved |
| Connect GitHub profile | Profile repository README updated to link the live website in commit `750482ae9b7c81b24bedc09ceaf7ee41e6f574c5` |

## Validation

- Fresh detached checkout and virtual environment: requirements installed; corpus run `sarif-known-findings-2026-11-03T10-43-45Z` passed all four labeled cases (3 TP, 1 TN, 0 FP/FN).
- Repository tests: 284 passed, 1 skipped, 18 subtests passed.
- Four-page artifact/link/script checks and console runtime smoke tests passed.
- A deliberately re-published missing-evidence record was rejected specifically by the new source-manifest validation; the source was restored afterward.
- Browser: homepage-to-guide navigation and guide content verified; inspected homepage and guide in 390px frames. Guide document width equaled its content width (375px excluding the scrollbar), with no horizontal overflow.

The new corpus run is a signal-processing regression check, not an exploit finding and not a reconstruction of historical results. No historical evidence was fabricated. See [publication review](BENCHMARK_PUBLICATION_REVIEW.md) for recovery requirements.

Repository and website changes in this feature branch need review and merge before they appear on the public site. The profile link is already committed. Hosting settings, paid domains, and account credentials were not changed.
