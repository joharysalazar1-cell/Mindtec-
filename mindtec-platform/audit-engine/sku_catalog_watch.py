"""Observe two explicitly selected local SKU inputs; never download or publish."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import time

import sku_catalog_run as runner
import supervisor
import windows_job

LOADED = {**runner.LOADED, 'sku_catalog_watch.py': Path(__file__).read_bytes(),
          'supervisor.py': supervisor.IMPLEMENTATION_BYTES,
          'windows_job.py': Path(windows_job.__file__).read_bytes()}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


class Observer:
    def __init__(self, workbook, catalog, runtime):
        self.workbook = Path(workbook).resolve()
        self.catalog = Path(catalog).resolve()
        self.runtime = Path(runtime).resolve()
        if self.workbook == self.catalog or any(p.is_relative_to(self.runtime) for p in (self.workbook, self.catalog)):
            raise ValueError('Distinct inputs outside observer custody required')
        self.binding = {'schema': 'mindtec-sku-observer-binding/1',
                        'workbook': str(self.workbook), 'catalog': str(self.catalog)}
        self.accepted = None

    def bind(self):
        self.runtime.mkdir(parents=True, exist_ok=True)
        path = self.runtime / 'binding.json'
        if path.exists():
            if path.read_bytes() != runner.encode(self.binding):
                raise ValueError('Runtime belongs to different source paths')
        else:
            with path.open('xb') as handle:
                handle.write(runner.encode(self.binding))

    def poll(self):
        health = {'schema': 'mindtec-sku-observer-health/1', 'pid': os.getpid(),
                  'checked_at': now(), 'network_delivery': False, 'custody_verified': False,
                  'last_accepted': self.accepted}
        try:
            self.bind()
            if any(Path(__file__).with_name(name).read_bytes() != raw for name, raw in LOADED.items()):
                raise ValueError('Loaded implementation changed; restart required')
            pointer = self.runtime / 'accepted.json'
            if pointer.exists():
                prior = json.loads(pointer.read_text(encoding='utf-8'))
                key = prior.get('context_sha256', '')
                if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
                    raise ValueError('Invalid accepted context')
                prior_value = runner.verify(self.runtime / 'runs' / key)
                prior_inputs = {n: runner.digest((self.runtime / 'runs' / key / n).read_bytes())
                                for n in ('source.xlsx', 'catalog.csv')}
                expected_key = runner.digest(runner.encode({'binding': self.binding,
                    'inputs': prior_inputs,
                    'implementation': {n: runner.digest(v) for n, v in LOADED.items()}}))
                if key != expected_key or prior.get('summary') != prior_value['summary']:
                    raise ValueError('Accepted pointer differs from retained context or summary')
                self.accepted = prior
            original = {'source.xlsx': runner.digest(self.workbook.read_bytes()),
                        'catalog.csv': runner.digest(self.catalog.read_bytes())}
            context = runner.digest(runner.encode({'binding': self.binding, 'inputs': original,
                         'implementation': {n: runner.digest(v) for n, v in LOADED.items()}}))
            target = self.runtime / 'runs' / context
            reused = target.exists()
            value = runner.verify(target) if reused else runner.run(self.workbook, self.catalog, target)
            if any(runner.digest((target / n).read_bytes()) != sha for n, sha in original.items()):
                raise ValueError('Source changed during acquisition; no promotion')
            if any(Path(__file__).with_name(name).read_bytes() != raw for name, raw in LOADED.items()):
                raise ValueError('Implementation changed during calculation; no promotion')
            self.accepted = {'context_sha256': context, 'summary': value['summary']}
            supervisor.atomic(pointer, self.accepted)
            health.update(status='healthy', state='verified_unchanged' if reused else 'new_cut_accepted',
                          custody_verified=True, last_accepted=self.accepted)
        except Exception as error:
            health.update(status='degraded', state='no_new_cut_accepted',
                          error_type=type(error).__name__, reason=str(error)[:1000],
                          last_accepted=self.accepted)
        health['checked_at'] = now()
        supervisor.atomic(self.runtime / 'health.json', health)
        return health


def watch(observer, interval=60, iterations=None):
    if isinstance(interval, bool) or not isinstance(interval, (int, float)) or not 60 <= interval <= 3600:
        raise ValueError('Polling interval must be 60 to 3600 seconds')
    if iterations is not None and (type(iterations) is not int or iterations < 1):
        raise ValueError('Positive iteration count required')
    with supervisor.exclusive(observer.runtime / 'sku-catalog-observer.lock'):
        health = None
        try:
            count = 0
            while True:
                health = observer.poll()
                count += 1
                if iterations is not None and count >= iterations:
                    return health
                time.sleep(interval)
        finally:
            if health is not None:
                health.update(last_poll_status=health['status'], status='stopped',
                              observer_running=False, checked_at=now())
                supervisor.atomic(observer.runtime / 'health.json', health)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', required=True)
    parser.add_argument('--catalog', required=True)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--interval', type=float, default=60)
    parser.add_argument('--iterations', type=int)
    args = parser.parse_args()
    print(json.dumps(watch(Observer(args.workbook, args.catalog, args.runtime),
                           args.interval, args.iterations)))
