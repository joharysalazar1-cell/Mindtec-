"""Retain the separately scoped global cold reference in a coherent local cycle."""
import argparse
from pathlib import Path
import engine
import collection_watch
import cold_legacy_run
import integrated_reconstruction as projection

ROOT = Path(__file__).resolve().parent
FILES = ('cold_legacy_stage.py', 'cold_legacy_run.py', 'cold_legacy_reference.py', 'collection_adapter.py', 'invoice_adapter.py')
LOADED = {name: (ROOT/name).read_bytes() for name in FILES}
KIND = 'legacy_global_cold_reference'


def verify(runtime, run_id=None):
    root = Path(runtime).resolve()
    if not (root/'audit.sqlite').is_file():
        raise ValueError('Existing legacy cold custody required')
    with engine.Engine(root) as e:
        e.db.execute('BEGIN')
        try:
            e.verify()
            row = e.db.execute("SELECT * FROM runs WHERE json_extract(rules_json,'$.kind')=? AND (? IS NULL OR id=?) ORDER BY at DESC,id DESC LIMIT 1", (KIND, run_id, run_id)).fetchone()
            if row is None:
                raise ValueError('Accepted legacy reference required')
            rules = engine.load_json_bytes(row['rules_json'].encode()); refs = rules['reference_sources']
            if collection_watch.object_bytes(e, refs['implementation']) != engine.code_bundle(LOADED):
                raise ValueError('Retained legacy reference implementation differs')
            source_raw = collection_watch.object_bytes(e, refs['source_cold_result']); source = engine.load_json_bytes(source_raw)
            workbook = collection_watch.object_bytes(e, refs['detailed_workbook'])
            expected = cold_legacy_run.calculate(source_raw, workbook)
            expected.update(source_ps_run_id=source['source_ps_run_id'], source_ps_snapshot_sha256=source['source_ps_snapshot_sha256'], source_cold_snapshot_sha256=engine.sha(source_raw))
            result = collection_watch.object_bytes(e, row['snapshot_hash'])
            if result != engine.canonical(expected).encode():
                raise ValueError('Legacy reference differs from replay')
            return {'run_id': row['id'], 'snapshot_sha256': row['snapshot_hash'], 'custody_verified': True}
        finally:
            e.db.execute('ROLLBACK')


def execute(cold_runtime, runtime):
    source = Path(cold_runtime).resolve(); output = Path(runtime).resolve()
    if source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError('Separate cold source and legacy reference custody required')
    cold = projection.captured(source, 'declared_cold_share')
    with engine.Engine(source) as e:
        e.db.execute('BEGIN')
        try:
            e.verify(); row = e.db.execute('SELECT rules_json FROM runs WHERE id=?', (cold['meta']['run_id'],)).fetchone()
            if row is None:
                raise ValueError('Retained cold execution required')
            rules = engine.load_json_bytes(row['rules_json'].encode()); workbook = collection_watch.object_bytes(e, rules['reference_sources']['detailed_workbook'])
        finally:
            e.db.execute('ROLLBACK')
    result = cold_legacy_run.calculate(cold['raw'], workbook)
    result.update(source_ps_run_id=cold['result']['source_ps_run_id'], source_ps_snapshot_sha256=cold['result']['source_ps_snapshot_sha256'], source_cold_snapshot_sha256=engine.sha(cold['raw']))
    for name, raw in LOADED.items():
        if (ROOT/name).read_bytes() != raw:
            raise ValueError('Loaded legacy reference implementation changed')
    refs = {'source_cold_result': (cold['raw'], '.json'), 'source_cold_execution': (cold['execution'], '.json'), 'detailed_workbook': (workbook, '.xlsx'), 'implementation': (engine.code_bundle(LOADED), '.json')}
    rule = {'kind': KIND, 'version': result['version'], 'reference_sources': {name: engine.sha(value[0]) for name, value in refs.items()}}
    summary = {'visits': len(result['stores']), 'original_cells_verified': len(result['cells']), 'monthly_reference_rows': len(result['monthly']), 'scope_separate_from_category_kpi': True, 'network_delivery': False}
    with engine.Engine(output) as e:
        accepted = e.record_result(engine.canonical(result).encode(), cold['policy'], rule, [], summary, refs)
    return verify(output, accepted['run_id'])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--cold-runtime', required=True, type=Path); p.add_argument('--runtime', required=True, type=Path); a = p.parse_args()
    print(engine.canonical(execute(a.cold_runtime, a.runtime)))
