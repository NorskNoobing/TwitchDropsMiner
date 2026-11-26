"""Stop automatic upstream sync when workflow changes need maintainer review."""

import json
import subprocess
import sys


def check(target: str) -> int:
    base = subprocess.check_output(
        ['git', 'merge-base', 'HEAD', target], text=True,
    ).strip()
    # Compare upstream changes, not the fork's intentional workflow removals.
    changed = subprocess.check_output([
        'git', 'diff', '--name-only', '--no-renames', '-z', base, target, '--',
        '.github/workflows', '.github/scripts/check_upstream_workflows.py',
    ])
    paths = [path for path in changed.decode('utf-8', errors='replace').split('\0') if path]
    if paths:
        print('::error::Upstream workflow changes require manual review; sync stopped before merge.')
        for path in paths:
            print(json.dumps(path))
        return 1
    print('No upstream workflow changes; automatic sync may continue.')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: check_upstream_workflows.py UPSTREAM_COMMIT')
    raise SystemExit(check(sys.argv[1]))
