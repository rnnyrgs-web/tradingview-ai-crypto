import copy
import hashlib
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / 'research_data/coinmetrics_2021_census/weekly/reproduce.py'
spec = importlib.util.spec_from_file_location('weekly_inventory', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def tree(entries):
    payload = b''
    for e in sorted(entries, key=lambda e: (e['path'] + ('/' if e['type'] == 'tree' else '')).encode()):
        payload += e['mode'].lstrip('0').encode() + b' ' + e['path'].encode() + b'\0' + bytes.fromhex(e['sha'])
    digest = hashlib.sha1(b'tree ' + str(len(payload)).encode() + b'\0' + payload, usedforsecurity=False).hexdigest()
    return {'sha': digest, 'truncated': False, 'tree': entries}


def record():
    csv = tree([{'mode': '100644', 'path': 'obsolete.csv', 'type': 'blob', 'sha': 'a'*40, 'size': 123},
                {'mode': '100644', 'path': 'metrics.csv', 'type': 'blob', 'sha': 'b'*40, 'size': 10}])
    root = tree([{'mode': '040000', 'path': 'csv', 'type': 'tree', 'sha': csv['sha']}])
    sha = 'c'*40
    base = 'https://api.github.com/repos/coinmetrics/data/git/'
    return {
        'cutoff': '2021-01-04T00:00:00Z', 'status': 'ACQUIRED_UNVALIDATED_METADATA',
        'index': {'url': 'https://api.github.com/repos/croque-m/coinmetrics-data/commits?until=2021-01-03T23%3A59%3A59Z&per_page=1',
                  'response': [{'sha': sha}]},
        'commit': {'url': base+'commits/'+sha, 'response': {'sha': sha, 'committer': {'date': '2021-01-03T13:00:00Z'}, 'tree': {'sha': root['sha']}}},
        'root_tree': {'url': base+'trees/'+root['sha'], 'response': root},
        'csv_tree': {'url': base+'trees/'+csv['sha'], 'response': csv},
    }


def test_retains_obsolete_source_and_excludes_only_dictionary():
    result = module.validate_snapshot(record())
    assert [r['source_symbol'] for r in result['files']] == ['obsolete']
    assert result['status'] == 'VERIFIED_TREE_INVENTORY_ONLY'
    assert result['public_availability_authenticated'] is False


@pytest.mark.parametrize('attack', ['truncated', 'blob_substitution', 'fork_source', 'future_commit', 'csv_link', 'index_sha'])
def test_provenance_attacks_fail(attack):
    r = copy.deepcopy(record())
    if attack == 'truncated':
        r['csv_tree']['response']['truncated'] = True
    elif attack == 'blob_substitution':
        r['csv_tree']['response']['tree'][0]['sha'] = 'd'*40
    elif attack == 'fork_source':
        r['commit']['url'] = r['commit']['url'].replace('coinmetrics/data', 'croque-m/coinmetrics-data')
    elif attack == 'future_commit':
        r['commit']['response']['committer']['date'] = r['cutoff']
    elif attack == 'csv_link':
        r['root_tree']['response']['tree'][0]['sha'] = 'e'*40
    elif attack == 'index_sha':
        r['index']['response'][0]['sha'] = 'f'*40
    with pytest.raises(ValueError):
        module.validate_snapshot(r)


def test_missing_or_duplicate_cutoff_cannot_shrink_denominator():
    with pytest.raises(ValueError):
        module.evaluate([record()])
    with pytest.raises(ValueError):
        module.evaluate([record()] * 52)


def test_all_failed_cutoffs_retained_without_intersection_claim():
    rows = [{'cutoff': d, 'status': 'ACQUISITION_FAILED', 'error': 'unavailable'} for d in module.CUTOFFS]
    result = module.evaluate(rows)
    assert len(result['weeks']) == 52
    assert result['summary']['failed_weeks'] == 52
    assert result['summary']['common_source_symbols_all_52'] is None
    assert result['summary']['canonical_cohort_snapshots'] == 0


def test_missing_week_does_not_create_appearance_or_disappearance():
    rows = [{'cutoff': d, 'status': 'ACQUISITION_FAILED', 'error': 'unavailable'} for d in module.CUTOFFS]
    rows[0] = record()
    third = record()
    third['cutoff'] = module.CUTOFFS[2]
    third['index']['url'] = third['index']['url'].replace('2021-01-03', '2021-01-17')
    rows[2] = third
    result = module.evaluate(rows)
    assert result['weeks'][2]['appeared_since_previous_week'] is None
    assert result['weeks'][2]['disappeared_since_previous_week'] is None
