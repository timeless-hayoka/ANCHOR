# Enzyme Blue Hunt Plan

Scope verified from Immunefi:
https://immunefi.com/bug-bounty/enzymefinance/scope/#impacts

## Chosen target

`UnpermissionedActionsWrapper`

## Why this is the solid win

- The name points at the likely bug class directly: permissioning / authorization.
- Authorization flaws tend to have a clean reproduction path and a reviewer-friendly PoC.
- A valid report can often show a concrete impact in the program's scope language: theft, freezing, or griefing through an unauthorized action path.

## Authorized boundary

- Local fork or production-code mirror only.
- No live mainnet probing.
- No out-of-scope components.
- No social engineering.
- No partial or mocked PoC.


## Current status

- Preliminary review says the wrapper is probably a convenience layer, not the authorization boundary itself.
- The real gate is the Comptroller `callOnExtension` + `permissionedVaultActionAllowed` path.
- `FeeManager.receiveCallFromComptroller` and `ComptrollerLib.__assertPermissionedVaultAction` both read as intentional and gated, so this lead is not a confirmed vuln yet.
- Keep the target ledger honest: do not promote this to a finding without a forked reproduction.

## If this lead stays clean

- Next pass: `FeeManager` and adjacent permissioned action flows.
- Fallback: choose a different in-scope contract with a stronger externalized state change and a cleaner local fork repro.

## Evidence gate

1. Confirm the exact contract address and deployed code from the program scope.
2. Reproduce on a local fork of the deployed code.
3. Show the unauthorized action path with a self-contained Foundry test.
4. Capture a signed evidence bundle from the ANCHOR server.
5. Preserve the failed attempts that ruled out false positives.

## What the final artifact must prove

- The action can be triggered without the required authority, or
- The missing permission check causes a program-scope impact, and
- The reproduction is deterministic on a fork with a complete test.

## Next output

- A runnable Foundry test or harness.
- A bundle that signs the repro and the provenance.
- A short writeup that maps the impact to Immunefi scope.
