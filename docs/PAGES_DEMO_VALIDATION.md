# Public Pages demo validation — 2026-11-03

The public site is a static preview. It must not depend on ANCHOR's local operator backend or present illustrative fixtures as current research results.

## Changes

- Repair console JavaScript quoting and multiline report strings, missing SWC metadata, report field hydration/clearing, and zero-impact CVSS scoring.
- Replace the backend-dependent published dashboard with an explicitly labeled, browser-only demo. Canned replies are rendered as text, capped, and never sent or stored.
- Correct research links to repository documents. Load benchmark metadata relative to the Pages project path, show metadata failures visibly, and remove duplicate confidence indicators.
- Stage only demo HTML and evidence-backed published index entries. No target working directories, private history, backend configuration, or credentials are packaged.
- Remove release template placeholders; provide page descriptions, a canonical landing URL, a main landmark, focus outlines, keyboard-operable case cards, preview selection state, and phone-width layouts.
- Add artifact and runtime checks to both pull-request CI and Pages deployment.

## Reproduction

From the repository root, with Python 3.11+ and Node 22+:

```sh
python3 scripts/build_pages.py
python3 scripts/check_pages.py
```

The checks parse all inline JavaScript, validate local links and source document paths, reject backend route references, execute console startup and all ten view renderers, and check known/zero-impact CVSS vectors, case report generation, untested-state accounting, and local chat.

A planted missing `SWC` lookup was rejected specifically with `SWC is not defined` by the runtime test, then restored and rechecked successfully.

## Browser observations

Tested the staged artifact in Chrome: all ten console navigation sections; case-to-report loading; Clear; CVSS with all impacts set to None (0.0); dashboard topic buttons, text submission, reset, and literal rendering of HTML-like input. Inspected all three pages in 390px-wide frames. This is responsive-layout QA, not a physical-device or full accessibility certification.

The browser extension emits its own metadata errors; those are separate from page-script failures.

## Missing historical benchmark evidence

The source index marks these entries published, but their referenced records and JSON artifacts are missing from this checkout:

- `dvd-phase1-local-2026-06-27T08-55-16Z`
- `dvd-phase1-local-2026-06-27T16-06-54Z`
- `sarif-known-findings-2026-06-30T23-48-08Z`

The site build logs and excludes these entries. It retains the Phase 0 baseline and `dvd-phase1-local-2026-06-27T00-23-21Z`, whose referenced evidence files exist. This check establishes file availability, not independent revalidation of their research conclusions. Do not recreate missing evidence from index summary numbers. Restore original artifacts and review them separately before displaying these entries.

## Deployment

This feature branch does not alter the public deployment until merged. The Pages workflow builds and validates `dist-pages/`, then deploys that directory. Recheck the public URL and the resulting Actions run after merge.

## Test result

`python -m pytest tests/ -q`: **284 passed, 1 skipped, 18 subtests passed** in this environment. Required dependencies were installed from the repository's requirements before rerunning. The site-specific artifact/runtime checks and `git diff --check` also passed. Hosted CI and post-merge deployment are separate checks and must be reviewed on GitHub.
