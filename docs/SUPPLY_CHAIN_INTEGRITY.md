# Supply Chain Integrity Gate (initial offline scanner)

This experimental feature checks **local npm package metadata** for install hooks,
install-time network activity, execution indicators, and source-commit mismatch
against a separately supplied reviewed commit.

Run from repository root:

```bash
python -m unittest tests.test_supply_chain_integrity -v
python supply_chain_integrity.py path/to/package-metadata.json --approved-commit <reviewed-sha>
```

Exit 1 means at least one high-severity heuristic. The tool **does not execute**
packages, fetch URLs, verify signatures, prove maliciousness, or establish that a
provenance attestation is authentic. Supply the approved commit from an independent
review process; do not trust a commit identifier supplied by the package itself.

Future gates: inspect actual npm tarball bytes; validate SLSA provenance and signer;
compare release commits against reviewed PRs; inspect GitHub workflow permissions;
scan unpacked artifacts safely; emit SARIF; add inert positive/negative fixtures
and CI integration. Never run known malicious historical artifacts.
