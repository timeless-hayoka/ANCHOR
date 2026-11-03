"""Stage only public demo assets and published benchmark metadata for Pages."""
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'dist-pages'


def build():
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()
    revision = subprocess.check_output(['git', 'rev-parse', '--short=12', 'HEAD'], cwd=ROOT, text=True).strip()
    for source in (ROOT / 'demo').glob('*.html'):
        text = source.read_text(encoding='utf-8')
        text = text.replace('Static demo · smart-contract vulnerability pipeline', f'Static demo · build {revision}')
        (OUTPUT / source.name).write_text(text, encoding='utf-8')
    index = json.loads((ROOT / 'benchmarks/index.json').read_text(encoding='utf-8'))
    published = []
    for row in index.get('benchmarks', []):
        if row.get('publication_tier') != 'published':
            continue
        paths = [row.get(field) for field in ('record', 'published_record', 'artifact_json') if row.get(field)]
        if not row.get('record') or not all(
            (ROOT / value).resolve().is_relative_to(ROOT / 'benchmarks') and (ROOT / value).is_file()
            for value in paths
        ):
            print(f"Excluded published index entry with missing evidence: {row.get('id')}")
            continue
        published.append(row)
    if not published:
        raise ValueError('No published benchmark records; refusing to publish misleading fallback metadata')
    (OUTPUT / 'benchmarks').mkdir()
    (OUTPUT / 'benchmarks/index.json').write_text(json.dumps({'benchmarks': published}, indent=2) + '\n', encoding='utf-8')
    (OUTPUT / '.nojekyll').touch()
    print(f'Staged public Pages demo at {OUTPUT} ({len(published)} published benchmarks)')


if __name__ == '__main__':
    build()
