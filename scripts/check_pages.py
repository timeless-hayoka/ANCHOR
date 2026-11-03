"""Check the actual Pages artifact for script failures and broken project paths."""
import json
import re
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'dist-pages'
BASE = 'https://timeless-hayoka.github.io/ANCHOR/'


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        for key in ('href', 'src'):
            if attrs.get(key):
                self.links.append(attrs[key])


def check():
    count = 0
    pages = {}
    for path in SITE.glob('*.html'):
        text = path.read_text(encoding='utf-8')
        parsed = Page()
        parsed.feed(text)
        pages[path.name] = parsed
        assert '{{ANCHOR_RELEASE}}' not in text, path
        assert 'name="viewport"' in text, path
        assert 'name="description"' in text, path
        for script in re.findall(r'<script[^>]*>(.*?)</script>', text, re.S):
            with tempfile.NamedTemporaryFile(suffix='.js', mode='w') as output:
                output.write(script)
                output.flush()
                subprocess.run(['node', '--check', output.name], check=True, capture_output=True)
            # Static demos must never call a backend, even from dormant controls.
            assert not re.search(r'fetchJSON\s*\(|["\'`]/api/|EventSource\s*\(', script), path
            count += 1
    for name, page in pages.items():
        for link in page.links:
            resolved = urlparse(urljoin(BASE + name, link))
            if resolved.netloc == 'timeless-hayoka.github.io':
                assert resolved.path.startswith('/ANCHOR/'), (name, link)
                target = unquote(resolved.path.removeprefix('/ANCHOR/')) or 'index.html'
                assert (SITE / target).is_file(), (name, link)
                if resolved.fragment and target in pages:
                    assert resolved.fragment in pages[target].ids, (name, link)
            elif resolved.netloc == 'github.com' and '/blob/main/' in resolved.path:
                target = resolved.path.split('/blob/main/', 1)[1]
                assert (ROOT / target).is_file(), (name, link)
    source_rows = json.loads((ROOT / 'benchmarks/index.json').read_text())['benchmarks']
    for row in source_rows:
        if row.get('publication_tier') == 'published':
            assert row.get('record'), (row['id'], 'missing record reference')
            for field in ('record', 'published_record', 'artifact_json', 'metrics_json', 'regression_report'):
                if row.get(field):
                    artifact = (ROOT / row[field]).resolve()
                    assert artifact.is_relative_to(ROOT / 'benchmarks') and artifact.is_file(), (row['id'], field, 'published evidence missing')
    benchmarks = json.loads((SITE / 'benchmarks/index.json').read_text())['benchmarks']
    for row in benchmarks:
        for field in ('record', 'published_record', 'artifact_json'):
            if row.get(field):
                assert (ROOT / row[field]).is_file(), (row['id'], field)
    assert benchmarks and all(row['publication_tier'] == 'published' for row in benchmarks)
    assert "fetch('./benchmarks/index.json')" in (SITE / 'index.html').read_text()
    subprocess.run(['node', str(ROOT / 'scripts/check_pages_runtime.cjs')], check=True)
    print(f'PASS: {len(pages)} pages, {count} scripts, all static links, published benchmark packaging, no backend routes')


if __name__ == '__main__':
    check()
