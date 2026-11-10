"""Verify historical quotes without modifying the pre-implementation consequences."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'consequences/journal_consequences.py').is_file())
OUT = Path(__file__).resolve().parent
CHANGE = OUT.parent
BASE = 'c6651d852fb84fc2c90a794f2419a21dbf6103ce'
sys.path[:0] = [str(ROOT / p) for p in ('consequences', 'roots')]
from journal_consequences import _citations


def baseline(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', BASE + ':' + path]).decode('utf-8')


def main():
    consequences = (CHANGE / 'consequences.md').read_text(encoding='utf-8')
    assert consequences == baseline('openspec/changes/trace-modules/consequences.md')
    snapshot = (OUT / 'baseline-sources.md').read_text(encoding='utf-8')
    relocations = json.loads((OUT / 'evidence-relocations.json').read_text(encoding='utf-8'))
    assert len(relocations) == 8
    for item in relocations:
        assert item['quote'] in baseline(item['original_path']) and item['quote'] in snapshot
    historical = []
    for path, quote in _citations(consequences):
        if quote not in (ROOT / path).read_text(encoding='utf-8'):
            assert quote in baseline(path) and quote in snapshot
            historical.append({'path': path, 'quote': quote, 'baseline': BASE})
    assert len(historical) == 6
    result = {'baseline': BASE, 'journal_relocations': len(relocations),
              'consequences_unchanged': True,
              'consequences_sha256': hashlib.sha256(consequences.encode()).hexdigest(),
              'historical_consequence_signals': historical}
    (OUT / 'historical-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('History verified: 8 journal quotes, 6 historical consequence signals; original consequences unchanged.')


if __name__ == '__main__':
    main()
