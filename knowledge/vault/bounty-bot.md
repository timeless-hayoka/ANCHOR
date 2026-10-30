# bounty-bot — Vault Note

## ANCHOR Subsystem Informed
`bounty_crawler.py` · `bounty_scout.py` · `bounty_sentinel.py`

## Source
https://github.com/timeless-hayoka/bounty-bot

## Key Lesson
Platform crawlers must treat scope declarations as first-class objects
parsed once, cached with TTL, and re-validated before every submission.
bounty-bot's strict scope-confirmation gate eliminated an entire class of
out-of-scope false submissions; ANCHOR's sentinel should replicate that
gate at crawl time, not just at emit time.

## Applicability
- Scope parse → cache → re-check loop belongs in `bounty_crawler.py`.
- Sentinel validation (`bounty_sentinel.py`) should reference the same
  scope object the crawler produced, not re-fetch independently.
