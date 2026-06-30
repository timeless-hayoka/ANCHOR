# Contributing to ANCHOR

Thank you for contributing to ANCHOR. This project is built around **evidence-gated research**, a structured knowledge corpus, and a clean sibling-repository model.

Read [docs/PHILOSOPHY.md](docs/PHILOSOPHY.md) for why ANCHOR exists before diving into implementation details.

## Engineering principles

- Evidence over intuition.
- One source of truth (trends in `anchor_trends.py`; strategy consumes; UI renders).
- Benchmarks before public claims.
- Tests before integration.
- Preserve reproducibility—failed attempts are data.

## Repository structure

| Repo | Role |
| ---- | ---- |
| [ANCHOR](https://github.com/timeless-hayoka/ANCHOR) | Proof gate, benchmarks, knowledge corpus, CLI, HTTP API |
| [infj-bot](https://github.com/timeless-hayoka/infj-bot) (`anchor` branch) | Companion runtime, dashboard, MCP tools |
| [timeless-hayoka](https://github.com/timeless-hayoka/timeless-hayoka) | Portfolio architecture and roadmap |

Do not treat a personal home-directory git snapshot as the canonical remote for ANCHOR or infj-bot. Push from each project’s own clone.

## Development setup

### 1. Clone repositories

```bash
git clone https://github.com/timeless-hayoka/ANCHOR.git
git clone -b anchor https://github.com/timeless-hayoka/infj-bot.git infj_bot
```

Place them as siblings when possible:

```text
~/projects/
  ANCHOR/
  infj_bot/
```

### 2. Set `ANCHOR_ROOT`

```bash
export ANCHOR_ROOT="$(cd ANCHOR && pwd)"
```

Add that line to your shell profile if you want it persistent. ANCHOR, infj-bot, and MCP tools use `ANCHOR_ROOT` to locate the knowledge corpus and benchmark tree.

### 3. Python environment

```bash
cd "$ANCHOR_ROOT"
./anchor env init
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/ -q
```

## Contribution workflow

### 1. Branch

```bash
git checkout -b feature/my-contribution
```

### 2. Run tests

```bash
# Full suite
.venv/bin/python -m pytest tests/ -q

# Focused benchmark test
.venv/bin/python -m pytest tests/test_defihacklabs_source_comparison_benchmark.py -q
```

### 3. Add a benchmark

Create a folder under `benchmarks/` with:

- `inputs/corpus.json`
- `expected/expectations.json`
- `run_*.py` runner script
- `README.md`

Wire the runner into `anchor_cli.py` if it needs a first-class command. Add tests under `tests/`.

### 4. Update the knowledge corpus

**Reference topics** (markdown, versioned):

1. Add or edit a `.md` file under `knowledge/`.
2. Register it in `knowledge/manifest.json` (`slug`, `title`, `subsystems`, `tags`).
3. Run `pytest tests/test_knowledge_provider.py`.

```bash
./anchor knowledge list
./anchor knowledge show sarif
./anchor knowledge search "promotion gate"
```

**Archival JSON** (training runs, detector output, scenarios) uses `knowledge/pipeline.py`—do not hand-edit generated files under `knowledge/training/`, `knowledge/detectors/`, or `knowledge/scenarios/` unless you are fixing a specific artifact.

Reference material must be evidence-backed. Do not promote scanner noise as findings without reproduction steps.

### 5. Commit and push

```bash
git add .
git commit -m "feat: descriptive title"
git push origin feature/my-contribution
```

Open a pull request with what changed, how you tested it, and whether benchmark artifacts were updated.

## Pull request checklist

- [ ] Tests pass (`pytest tests/ -q`)
- [ ] Documentation updated (README, docs/, or benchmark README as applicable)
- [ ] Benchmark artifacts included or manifest updated (if applicable)
- [ ] No generated logs, Chroma data, or `.env` files committed
- [ ] No duplicated trend/strategy math (consumers only)
- [ ] `ANCHOR_ROOT` / path assumptions documented if behavior is environment-sensitive

## Code style

- Python: follow existing module patterns; keep functions small and testable
- Solidity / Foundry: `forge fmt` where applicable
- Documentation: clear, concise, evidence-focused
- Tests: new behavior should have tests

## Reproduction gate

Before claiming Phase C credibility, follow [docs/REPRODUCTION.md](docs/REPRODUCTION.md) on a clean machine and compare your manifest output to published entries in `benchmarks/index.json`.

## Questions

Open a GitHub issue on [timeless-hayoka/ANCHOR](https://github.com/timeless-hayoka/ANCHOR/issues) with your environment, commit hash, and reproduction steps.

Thank you for helping build a reproducible, evidence-gated security research platform.
