#!/usr/bin/env python3
"""One-shot: rewrite build-queue.json on gh-pages to use normalized names.

- Replaces each item's `package_name` with the normalized form
- Marks items that can't be normalized as status=skip_malformed + skip_reason
- Resets items stuck in `building` whose normalized name doesn't appear in
  packages.json back to `pending` (so they'll be re-dispatched)
- Prints a summary of changes but does not push — run `git push` manually

Usage:
    python3 scripts/sweep_queue_normalize.py

Assumes you've already run: git fetch origin gh-pages && git checkout gh-pages
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from normalize_package_name import build_package_name


def gh_pages_json(filename):
    r = subprocess.run(
        ['git', 'show', f'origin/gh-pages:{filename}'],
        capture_output=True, text=True, check=True
    )
    return json.loads(r.stdout)


def main():
    queue = gh_pages_json('build-queue.json')
    packages = gh_pages_json('packages.json')
    published_names = {p.get('package') for p in packages.get('flat', [])}
    print(f'Queue size: {len(queue)}, published packages: {len(published_names)}')

    changes = Counter()
    for item in queue:
        provider = 'Ensembl' if item.get('data_source') == 'ensembl' else 'NCBI'
        name, reason = build_package_name(
            item.get('organism', ''), provider, item.get('assembly', '')
        )
        old_name = item.get('package_name', '')

        if not name:
            if item['status'] not in ('done', 'skip_prokaryote'):
                item['status'] = 'skip_malformed'
                item['skip_reason'] = reason
                changes['marked_malformed'] += 1
            continue

        if old_name != name:
            item['package_name'] = name
            changes['renamed'] += 1

        if item['status'] == 'building' and name not in published_names:
            item['status'] = 'pending'
            changes['reset_building_to_pending'] += 1
        elif item['status'] == 'building' and name in published_names:
            item['status'] = 'done'
            changes['confirmed_done'] += 1

    print('\n=== Change summary ===')
    for k, v in changes.most_common():
        print(f'  {k}: {v}')

    status_counts = Counter(item['status'] for item in queue)
    print('\n=== Final status distribution ===')
    for s, c in status_counts.most_common():
        print(f'  {s}: {c}')

    out = 'build-queue.normalized.json'
    with open(out, 'w') as f:
        json.dump(queue, f, indent=2)
    print(f'\nWrote {out}')


if __name__ == '__main__':
    main()
