"""Offline reproduction of quarantined source inventories, never trading outcomes.

Inputs are retained GitHub API metadata. Git tree hashes check internal object
identity; they do not authenticate public availability at historical cutoffs.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
START = datetime(2021, 1, 4, tzinfo=timezone.utc)
CUTOFFS = [(START + timedelta(weeks=i)).strftime('%Y-%m-%dT%H:%M:%SZ') for i in range(52)]
API = 'https://api.github.com/repos/coinmetrics/data/git/'
INDEX = 'https://api.github.com/repos/croque-m/coinmetrics-data/commits?until='


def timestamp(value):
    result = datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    return result


def git_sha(value):
    if not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{40}', value) is None:
        raise ValueError('Invalid Git object ID')
    return value


def verify_tree(tree):
    if tree.get('truncated') is not False or not isinstance(tree.get('tree'), list):
        raise ValueError('Missing or truncated Git tree')
    names = set()
    entries = []
    allowed = {'tree': {'040000'}, 'blob': {'100644', '100755', '120000'}, 'commit': {'160000'}}
    for item in tree['tree']:
        name = item.get('path')
        if not isinstance(name, str) or not name or name in {'.', '..'} or '/' in name or '\x00' in name or name in names:
            raise ValueError('Ambiguous Git tree path')
        if item.get('mode') not in allowed.get(item.get('type'), set()):
            raise ValueError('Invalid Git tree mode/type')
        names.add(name)
        git_sha(item.get('sha'))
        entries.append(item)
    payload = b''
    for item in sorted(entries, key=lambda e: (e['path'] + ('/' if e['type'] == 'tree' else '')).encode()):
        payload += (item['mode'].lstrip('0').encode() + b' ' + item['path'].encode()
                    + b'\x00' + bytes.fromhex(item['sha']))
    digest = hashlib.sha1(b'tree ' + str(len(payload)).encode() + b'\x00' + payload,
                          usedforsecurity=False).hexdigest()
    if digest != git_sha(tree.get('sha')):
        raise ValueError('Git tree content hash mismatch')
    return entries


def validate_snapshot(record):
    cutoff = timestamp(record['cutoff'])
    before = (cutoff - timedelta(seconds=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    if record['index']['url'] != INDEX + quote(before, safe='') + '&per_page=1':
        raise ValueError('Index request differs from frozen cutoff')
    hint = record['index']['response']
    if not isinstance(hint, list) or len(hint) != 1:
        raise ValueError('Not a single index hint')
    sha = git_sha(hint[0]['sha'])
    commit = record['commit']['response']
    if record['commit']['url'] != API + 'commits/' + sha or commit['sha'] != sha:
        raise ValueError('Commit did not resolve at exact upstream URL')
    committed = timestamp(commit['committer']['date'])
    if committed >= cutoff:
        raise ValueError('Commit is not strictly before cutoff')
    root = record['root_tree']['response']
    if record['root_tree']['url'] != API + 'trees/' + commit['tree']['sha'] or root['sha'] != commit['tree']['sha']:
        raise ValueError('Root tree binding mismatch')
    root_entries = verify_tree(root)
    csv_nodes = [e for e in root_entries if e['path'] == 'csv' and e['type'] == 'tree']
    if len(csv_nodes) != 1:
        raise ValueError('Missing unique csv subtree')
    csv = record['csv_tree']['response']
    if record['csv_tree']['url'] != API + 'trees/' + csv_nodes[0]['sha'] or csv['sha'] != csv_nodes[0]['sha']:
        raise ValueError('CSV subtree binding mismatch')
    entries = verify_tree(csv)
    if any(e['type'] == 'tree' for e in entries):
        raise ValueError('Nested csv directory outside frozen direct-file contract')
    files = []
    for item in entries:
        if not item['path'].endswith('.csv') or item['path'] == 'metrics.csv':
            continue
        if (item['type'] != 'blob' or item['mode'] != '100644'
                or re.fullmatch(r'[a-z0-9_]+\.csv', item['path']) is None
                or type(item.get('size')) is not int or item['size'] <= 0):
            raise ValueError('Invalid source CSV metadata')
        files.append({'source_symbol': item['path'][:-4], 'path': 'csv/' + item['path'],
                      'blob_sha': item['sha'], 'raw_bytes_declared': item['size']})
    if not files:
        raise ValueError('Empty source inventory')
    return {'cutoff': record['cutoff'], 'status': 'VERIFIED_TREE_INVENTORY_ONLY',
            'commit': sha, 'committer_at': commit['committer']['date'],
            'commit_age_hours': (cutoff - committed).total_seconds() / 3600,
            'root_tree_sha': root['sha'], 'csv_tree_sha': csv['sha'],
            'public_availability_authenticated': False,
            'source_file_count': len(files), 'files': sorted(files, key=lambda f: f['source_symbol'])}


def evaluate(records):
    if len(records) != 52 or [r.get('cutoff') for r in records] != CUTOFFS:
        raise ValueError('Frozen complete ordered 52-cutoff denominator mismatch')
    weeks = []
    previous = None
    sets = []
    symbols = Counter()
    distinct_blobs = set()
    for record in records:
        try:
            if record.get('status') != 'ACQUIRED_UNVALIDATED_METADATA':
                raise ValueError(record.get('error', 'Acquisition unavailable'))
            result = validate_snapshot(record)
            current = {r['source_symbol']: r['blob_sha'] for r in result['files']}
            result['appeared_since_previous_week'] = sorted(current.keys() - previous.keys()) if previous is not None else None
            result['disappeared_since_previous_week'] = sorted(previous.keys() - current.keys()) if previous is not None else None
            result['changed_blobs_since_previous_week'] = sum(current[s] != previous[s] for s in current.keys() & previous.keys()) if previous is not None else None
            sets.append(set(current))
            symbols.update(current.keys())
            distinct_blobs.update(current.values())
            previous = current
        except (KeyError, TypeError, ValueError) as exc:
            result = {'cutoff': record['cutoff'], 'status': 'UNVERIFIED_RETAINED_FAILURE', 'error': str(exc)}
            previous = None
        weeks.append(result)
    success = [w for w in weeks if w['status'] == 'VERIFIED_TREE_INVENTORY_ONLY']
    return {
        'task': 'COINMETRICS-2021-WEEKLY-INVENTORY-v1',
        'classification': 'QUARANTINED_LONGITUDINAL_SOURCE_INVENTORY_ONLY',
        'summary': {
            'cutoffs_frozen': 52, 'verified_tree_weeks': len(success), 'failed_weeks': 52-len(success),
            'source_symbol_week_rows': sum(w['source_file_count'] for w in success),
            'observed_unique_source_symbols': len(symbols),
            'common_source_symbols_all_52': len(set.intersection(*sets)) if len(success) == 52 else None,
            'distinct_source_blobs_declared': len(distinct_blobs),
            'minimum_weekly_source_files': min((w['source_file_count'] for w in success), default=None),
            'maximum_weekly_source_files': max((w['source_file_count'] for w in success), default=None),
            'maximum_commit_age_hours': max((w['commit_age_hours'] for w in success), default=None),
            'adjacent_week_appearance_occurrences': sum(len(w.get('appeared_since_previous_week') or []) for w in success),
            'adjacent_week_disappearance_occurrences': sum(len(w.get('disappeared_since_previous_week') or []) for w in success),
            'canonical_cohort_snapshots': 0, 'historical_2x_events': 0, 'matched_controls': 0,
            'precursor_tests': 0, 'qualified_current_candidates': 0,
        },
        'source_symbol_week_counts': dict(sorted(symbols.items())), 'weeks': weeks,
        'outcomes_opened': False, 'cohort_admission': False, 'protected_oos_opened': False,
        'broker_connected': False, 'trade_authority': False,
        'limitations': [
            'Unsigned upstream Git committer dates are not authenticated historical public availability.',
            'Historical index fork is an index hint only; original upstream must resolve each exact object.',
            'Tree verification proves internal identity of retained metadata, not independent acquisition attestation.',
            'No source CSV values were read; declared blob sizes are metadata, not verified acquired byte counts.',
            'Source symbols are not canonical assets or historically tradable venue members.',
            'Retained source files may be stale, revised, wrappers, stablecoins or obsolete series.',
            'Appearance/disappearance denotes source-file presence only, never listing/delisting or outcome.',
            'Changes of blob identity are revisions of files, not necessarily revisions of existing observations.',
            'A gap prevents adjacent-week comparison; failures never become absent assets or negative outcomes.',
        ],
    }


def main():
    freeze_bytes = (ROOT / 'freeze.json').read_bytes()
    freeze = json.loads(freeze_bytes)
    if freeze['cutoffs'] != CUTOFFS or freeze['source_repository'] != 'coinmetrics/data' or freeze['freeze_comment'] != 5825179094:
        raise ValueError('Frozen source contract mismatch')
    acquisition = gzip.decompress((ROOT / 'acquisition.json.gz').read_bytes())
    result = evaluate(json.loads(acquisition))
    result.update({'freeze_sha256': hashlib.sha256(freeze_bytes).hexdigest(),
                   'acquisition_sha256': hashlib.sha256(acquisition).hexdigest(),
                   'reproducer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    output = (json.dumps(result, indent=2, sort_keys=True) + '\n').encode()
    (ROOT / 'results.json.gz').write_bytes(gzip.compress(output, mtime=0))
    (ROOT / 'summary.json').write_text(json.dumps(result['summary'], indent=2, sort_keys=True) + '\n')
    print(json.dumps(result['summary'], indent=2, sort_keys=True))
    if result['summary']['failed_weeks']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
