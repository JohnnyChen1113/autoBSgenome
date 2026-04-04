#!/usr/bin/env python3
"""One-time script to sync build-queue.json with packages.json on gh-pages.
Marks all published packages as 'done' in the queue."""

import json
import subprocess
import sys

def get_gh_pages_file(filename):
    result = subprocess.run(['git', 'show', f'gh-pages:{filename}'], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error reading {filename}: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)

def main():
    packages = get_gh_pages_file('packages.json')
    queue = get_gh_pages_file('build-queue.json')

    # Get all published organism names
    flat = packages.get('flat', [])
    published_organisms = set(p.get('organism', '') for p in flat)
    print(f"Published organisms: {len(published_organisms)}")

    # Update queue entries
    updated = 0
    for item in queue:
        if item.get('organism') in published_organisms and item.get('status') != 'done':
            old_status = item['status']
            item['status'] = 'done'
            print(f"  {old_status} -> done: {item.get('organism')}")
            updated += 1

    print(f"\nUpdated {updated} entries")

    # Write to temp file for checkout+commit
    with open('/tmp/build-queue-fixed.json', 'w') as f:
        json.dump(queue, f)

    # Stats after fix
    from collections import Counter
    counts = Counter(i.get('status') for i in queue)
    print(f"\nNew counts:")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

if __name__ == '__main__':
    main()
