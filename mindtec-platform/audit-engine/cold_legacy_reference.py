"""Recover recorded global cold-face shares without inventing category attribution.

This is a separate September reference, never the category cold-share KPI.
Input: a retained cold_share result with source-bound answer and cell hashes.
"""
import collections
import hashlib
import json
import math
import re

VERSION = 'legacy-global-recorded-cold-share/1.0.0'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def count(answer):
    value = answer.get('value')
    return int(value) if answer.get('state') == 'observed' and type(value) in (int, float) and math.isfinite(value) and value >= 0 and float(value).is_integer() else None


def reconstruct(source, catalogue):
    answers = source['answer_evidence']; cells = source['cells']
    visits = collections.defaultdict(list)
    for inv in source['category_inventories']:
        visits[(inv['month'], inv['kobo_id'])].append(inv)
    stores = []
    for (month, visit), inventories in sorted(visits.items()):
        if not any(i['layout'] == 'legacy_global_unattributed' for i in inventories):
            # Explicit no-cooler visits of the legacy month still belong to its cohort.
            legacy_month = any(i['month'] == month and i['layout'] == 'legacy_global_unattributed' for i in source['category_inventories'])
            if not legacy_month:
                continue
        retained = {}
        aid_set = sorted({a for inv in inventories for a in inv['answer_ids']})
        for aid in aid_set:
            a = answers[aid]
            if digest(a) != aid:
                raise ValueError('Answer hash differs')
            for cid in a['cell_ids']:
                if digest(cells[cid]) != cid or cells[cid]['kobo_id'] != visit or cells[cid]['source_sha256'] != source['source_sha256']:
                    raise ValueError('Cell identity or hash differs')
            route = a.get('route') or ''
            if route and (route.startswith('rep_caras_frias[') or route.split('/')[-1] in {'n_marcas_frias', 'marcas_frias_seleccionadas', 'hay_enfriadores'}):
                if route in retained and retained[route] != a:
                    raise ValueError('Conflicting retained route')
                retained[route] = a
        def suffix(name):
            matches = [a for route, a in retained.items() if route.split('/')[-1] == name]
            return matches[0] if len(matches) == 1 else {'state': 'unresolved', 'value': None}
        groups = collections.defaultdict(dict)
        for route, a in retained.items():
            m = re.fullmatch(r'rep_caras_frias\[([1-9]\d*)\]/([^/]+)', route)
            if m:
                groups[int(m[1])][m[2]] = a
        groups = {index: fields for index, fields in groups.items() if any(a.get('state') == 'observed' or any(cells[cid]['value'] not in (None, '') for cid in a.get('cell_ids', [])) for a in fields.values())}
        issues = []; rows = []; totals = {}
        gate = suffix('hay_enfriadores')
        proven_zero = any(i['layout'] == 'explicit_no_coolers' and i['state'] == 'complete' for i in inventories)
        if proven_zero and gate.get('state') == 'observed' and gate.get('value') == 'no' and not groups:
            expected = 0
        else:
            expected = count(suffix('n_marcas_frias'))
            if expected is None or set(groups) != set(range(1, expected + 1)):
                issues.append('enumeration_unresolved')
            selection = suffix('marcas_frias_seleccionadas')
            selected = selection['value'].split() if selection['state'] == 'observed' and isinstance(selection['value'], str) else None
            for index, fields in sorted(groups.items()):
                identity = fields.get('marca_fria_actual', {})
                code = identity.get('value') if identity.get('state') == 'observed' else None
                faces = count(fields.get('caras_frias', {}))
                label = fields.get('marca_fria_label', {}).get('value')
                if not isinstance(code, str) or not code.strip():
                    issues.append('brand_identity_unresolved')
                elif code in totals:
                    issues.append('duplicate_brand')
                else:
                    totals[code] = faces
                if faces is None:
                    issues.append('face_count_unresolved')
                rows.append({'index': index, 'code': code, 'label': label, 'faces': faces})
            if selected is None or len(selected) != len(set(selected)) or set(selected) != set(totals) or len(selected) != expected:
                issues.append('selection_does_not_match_rows')
            if gate.get('state') != 'observed' or gate.get('value') != 'si':
                issues.append('cooler_gate_not_confirmed')
        stores.append({'kobo_id': visit, 'month': month, 'state': 'complete' if not issues else 'pending', 'issues': sorted(set(issues)), 'expected_rows': expected, 'recorded_faces': sum(totals.values()) if not issues else None, 'known_faces_subtotal': sum(v for v in totals.values() if v is not None), 'faces_by_code': totals, 'rows': rows, 'answer_ids': [aid for aid in aid_set if answers[aid] in retained.values()]})
    identities = sorted({(c['brand_code'], c['brand']) for c in catalogue})
    monthly = []
    for month in sorted({s['month'] for s in stores}):
        cohort = [s for s in stores if s['month'] == month]; complete = [s for s in cohort if s['state'] == 'complete']; pending = [s for s in cohort if s['state'] != 'complete']
        denominator = sum(s['recorded_faces'] for s in complete)
        observed_codes = {code for s in complete for code in s['faces_by_code']}
        all_identities = identities + [(code, code) for code in sorted(observed_codes - {c for c, _ in identities})]
        for code, brand in all_identities:
            numerator = sum(s['faces_by_code'].get(code, 0) for s in complete)
            monthly.append({'month': month, 'brand_code': code, 'brand': brand, 'cohort_visits': len(cohort), 'complete_visits': len(complete), 'pending_visits': len(pending), 'numerator_in_complete_visits': numerator, 'denominator_in_complete_visits': denominator, 'share_in_complete_visits': 100 * numerator / denominator if denominator else None, 'whole_cohort_share': 100 * numerator / denominator if denominator and not pending else None, 'state': 'pending_visits' if pending else 'zero_recorded_faces' if not denominator else 'complete', 'category_attribution': 'unavailable', 'zero_means': 'zero faces in the enumerated recorded list, not certified physical absence'})
    used = {aid for s in stores for aid in s['answer_ids']}
    return {'schema': 'mindtec-legacy-global-cold-reference/1', 'version': VERSION, 'source_sha256': source['source_sha256'], 'scope': 'all brands enumerated in legacy global cold list; no category filter', 'formula': '100 * recorded brand faces / recorded global faces, pooled across visits; complete-visit subset shown separately if any visit is unresolved', 'monthly': monthly, 'stores': stores, 'answer_evidence': {aid: answers[aid] for aid in sorted(used)}, 'cells': {cid: cells[cid] for cid in sorted({cid for aid in used for cid in answers[aid]['cell_ids']})}, 'limits': ['This reference does not replace category cold share.', 'The global list does not identify how brand faces divide among categories.', 'No extrapolation to October or annual comparison.', 'A recorded zero is not independent proof of physical brand absence.', 'Pending visits are disclosed; subset results are not the full cohort.']}
