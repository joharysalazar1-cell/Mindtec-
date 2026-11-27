"""Cold faces by explicit category; never partition legacy global faces by guess."""
import collections, math, re
from pathlib import Path
import engine

VERSION = 'declared-cold-share/1.1.0'
IMPLEMENTATION_BYTES = Path(__file__).read_bytes()
OTHER = {'otro', 'otras', 'otras_marcas', 'other'}

def integer(answer):
 value = answer.get('value')
 return int(value) if answer.get('state') == 'observed' and type(value) in (int, float) and math.isfinite(value) and value >= 0 and float(value).is_integer() else None

def inventory(flat, record, category, decision, cooler_rules=None):
 answers = []; signals = []; rows = []; faces = {}
 def keep(a): answers.append(a); return a
 def missing(route): return {'route': route, 'state': 'route_not_mapped', 'value': None, 'cells': []}
 gate = keep(flat.suffix(record, 'hay_enfriadores'))
 n = keep(flat.suffix(record, 'n_frio_' + category)); expected = integer(n)
 groups = flat.groups(record, 'rep_frio_' + category)
 legacy = flat.groups(record, 'rep_caras_frias')
 # Category absence does not authorize discarding contradictory category rows.
 eligible = decision['eligible']
 if eligible is False and not groups and not (expected is not None and expected > 0):
  return {'eligible': False, 'source_eligible': False, 'state': 'not_applicable', 'faces': None, 'known_faces': 0, 'faces_by_code': {}, 'rows': [], 'signals': [], 'layout': 'not_applicable', 'answers': answers}
 if eligible is False:
  eligible = None; signals.append('cold_category_scope_conflict')
 if eligible is None: signals.append('category_eligibility_pending')
 # A global list cannot be copied into every category. Preserve its cells.
 legacy_layout = n['state'] == 'route_not_mapped'
 if legacy_layout:
  keep(flat.suffix(record, 'n_marcas_frias')); keep(flat.suffix(record, 'marcas_frias_seleccionadas'))
  for fields in legacy.values(): answers.extend(fields.values())
 # A negative cooler gate proves zero only with no contradictory cold row in
 # any category, no positive count, and no unmapped filled cold-route cell.
 all_routes = set(flat.bindings[record['form']]) | {r for rs in flat.ambiguous[record['form']].values() for r in rs}
 rule = (cooler_rules or {}).get('forms', {}).get(record['form'])
 if rule and category.startswith('bsa_') and gate['state'] == 'observed' and gate['value'] == 'si' and eligible is True:
  bsa_count = keep(flat.suffix(record, 'cuantos_enfriadores_bsa'))
  if integer(bsa_count) == 0:
   scoped_routes = sorted(r for r in all_routes if r.startswith(('rep_frio_bsa_', 'rep_caras_frias[')) or r.split('/')[-1].startswith(('n_frio_bsa_', 'n_marcas_frias', 'marcas_frias_seleccionadas')))
   observations = [keep(flat.query(record, route)) for route in scoped_routes]
   for fields in flat.groups(record, 'rep_enfriador').values(): observations.extend(keep(a) for a in fields.values())
   for header in flat.unmapped[record['form']]:
    if re.search(r'(?:rep_frio_bsa_|caras_frio_bsa_|n_frio_bsa_|caras_frias|rep_caras_frias)', header) and record['row']['cells'][flat.columns[header]] not in (None, ''):
     observations.append(keep({'route': None, 'state': 'unmapped_cold_observation', 'value': None, 'cells': [flat.cell(record, flat.columns[header])]}))
   contradiction = any(any(c['value'] not in (None, '') for c in a['cells']) and not ((a.get('route') or '').split('/')[-1].startswith(('n_frio_bsa_', 'n_marcas_frias')) and integer(a) == 0) for a in observations)
   if not contradiction:
    return {'eligible': True, 'source_eligible': decision['eligible'], 'state': 'complete', 'faces': 0, 'known_faces': 0, 'faces_by_code': {}, 'rows': [], 'signals': [], 'layout': 'admitted_zero_bsa_coolers', 'answers': answers}
   signals.append('zero_bsa_coolers_with_cold_observations')
 if gate['state'] == 'observed' and gate['value'] == 'no':
  cold_routes = sorted(r for r in all_routes if r.startswith(('rep_frio_', 'rep_caras_frias[')) or r.split('/')[-1].startswith(('n_frio_', 'n_marcas_frias')))
  observed = [keep(flat.query(record, route)) for route in cold_routes]
  observed += [keep(flat.suffix(record, key)) for key in ['cuantos_enfriadores', 'cuantos_enfriadores_bsa']]
  for fields in flat.groups(record, 'rep_enfriador').values(): observed.extend(keep(a) for a in fields.values())
  for header in flat.unmapped[record['form']]:
   if re.search(r'(?:rep_frio_|caras_frio_|n_frio_|caras_frias|rep_caras_frias)', header) and record['row']['cells'][flat.columns[header]] not in (None, ''):
    observed.append(keep({'route': None, 'state': 'unmapped_cold_observation', 'value': None, 'cells': [flat.cell(record, flat.columns[header])]}))
  contradiction = any(any(c['value'] not in (None, '') for c in a['cells']) and not ((a.get('route') or '').split('/')[-1].startswith(('n_frio_', 'n_marcas_frias', 'cuantos_enfriadores')) and integer(a) == 0) for a in observed)
  if not contradiction and eligible is True:
   return {'eligible': True, 'source_eligible': decision['eligible'], 'state': 'complete', 'faces': 0, 'known_faces': 0, 'faces_by_code': {}, 'rows': [], 'signals': [], 'layout': 'explicit_no_coolers', 'answers': answers}
  if contradiction: signals.append('negative_cooler_gate_with_cold_observations')
 elif gate['state'] != 'observed' or gate['value'] != 'si': signals.append('cooler_gate_unresolved')
 if legacy_layout:
  signals.append('legacy_global_cold_faces_not_category_attributed')
 else:
  if expected is None: signals.append('cold_brand_count_unresolved')
  indices = []
  for name, fields in sorted(groups.items()):
   match = re.fullmatch('rep_frio_' + re.escape(category) + r'\[([1-9]\d*)\]', name)
   indices.append(int(match[1]) if match else None)
   def field(key): return keep(fields.get(key, missing(name + '/' + key)))
   code = field('marca_frio_act_' + category); label = field('marca_frio_lbl_' + category); count = field('caras_frio_' + category)
   value = integer(count); c = code['value'] if code['state'] == 'observed' and isinstance(code['value'], str) and code['value'].strip() else None
   if c is None: signals.append('cold_brand_identity_unresolved')
   elif c in faces: signals.append('duplicate_cold_brand_row')
   if value is None: signals.append('cold_face_count_unresolved')
   # Free-text other branches need a separately admitted structure.
   if c in OTHER: signals.append('cold_other_brand_layout_unresolved')
   if c is not None: faces[c] = None if c in faces else value
   rows.append({'group': name, 'code': c, 'label': label.get('value'), 'faces': value})
  if expected is not None and (expected != len(groups) or set(indices) != set(range(1, expected + 1))): signals.append('cold_enumeration_incomplete')
 # Unmapped explicit cold counts cannot silently disappear from a denominator.
 token = re.compile(r'(?:caras_frio_|marca_frio_act_|rep_frio_)' + re.escape(category) + r'(?![A-Za-z0-9_])')
 for header in flat.unmapped[record['form']]:
  if token.search(header) and record['row']['cells'][flat.columns[header]] not in (None, ''):
   keep({'route': None, 'state': 'unmapped_cold_observation', 'value': None, 'cells': [flat.cell(record, flat.columns[header])]}); signals.append('unmapped_cold_observation')
 signals = sorted(set(signals))
 return {'eligible': eligible, 'source_eligible': decision['eligible'], 'state': 'pending' if signals else 'complete', 'faces': None if signals else sum(faces.values()), 'known_faces': sum(v for v in faces.values() if v is not None), 'faces_by_code': faces, 'rows': rows, 'signals': signals, 'layout': 'legacy_global_unattributed' if legacy_layout else 'explicit_category_repetitions', 'answers': answers}

def aggregate(rows, period, kind):
 applicable = [r for r in rows if r['eligible'] is not False]; pending = [r for r in applicable if r['state'] != 'complete']
 complete = bool(applicable) and not pending
 numerator = sum(r['brand_faces'] for r in applicable) if complete else None
 denominator = sum(r['category_faces'] for r in applicable) if complete else None
 return {'period': period, 'period_kind': kind, 'brand': rows[0]['brand'], 'brand_code': rows[0]['brand_code'], 'category': rows[0]['category'], 'cohort_store_months': len(rows), 'applicable_store_months': len(applicable), 'pending_store_months': len(pending), 'store_months_with_category_signals': sum(bool(r['category_signals']) for r in rows), 'numerator': numerator, 'denominator': denominator, 'value': 100 * numerator / denominator if denominator else None, 'state': 'pending_observations' if pending else 'no_eligible_base' if not applicable else 'zero_observed_faces' if not denominator else 'complete', 'months_observed': sorted({r['month'] for r in rows}), 'store_rows': [r['id'] for r in rows]}

def evaluate(flat, catalog, cohort, eligibility_checks, source_answers, source_cells, cooler_rules=None):
 if cooler_rules is not None:
  if cooler_rules.get('schema') != 'mindtec-cold-layout/1' or cooler_rules.get('detailed_workbook_sha256') != flat.source_sha256 or not isinstance(cooler_rules.get('version'), str) or not cooler_rules['version'].strip() or not isinstance(cooler_rules.get('forms'), dict) or not cooler_rules['forms'] or any(value != 'explicit_zero_bsa_count_means_no_bsa_cold_faces' for value in cooler_rules['forms'].values()): raise ValueError('Source-bound supported cooler-scope rules required')
 cohort = list(cohort); identities = [(c['category'], c['brand_code'], c['brand']) for c in catalog]
 if not cohort or len(set(cohort)) != len(cohort) or not identities or len(set(identities)) != len(identities): raise ValueError('Unique admitted cohort and full catalogue required')
 labels = collections.defaultdict(set)
 for cat, code, brand in identities: labels[(cat, code)].add(brand)
 if any(code not in OTHER and len(v) > 1 for (_, code), v in labels.items()): raise ValueError('Ambiguous catalogue brand code')
 decisions = {}
 for item in eligibility_checks:
  key = (item['kobo_id'], item['month'], item['category'])
  if key in decisions: raise ValueError('Duplicate category decision')
  decisions[key] = item
 expected = {(visit, month, cat) for visit, month in cohort for cat, _, _ in identities}
 if set(decisions) != expected: raise ValueError('Eligibility scope differs')
 records = {(r['id'], r['month']): r for r in flat.records}; answers = {}; cells = {}; prepared = {}; rows = []; monthly = collections.defaultdict(list); annual = collections.defaultdict(list)
 def retain(a):
  ids = []
  for cell in a.get('cells', []):
   cid = engine.sha(engine.canonical(cell)); cells[cid] = cell; ids.append(cid)
  binding = {'route': a.get('route'), 'state': a['state'], 'value': a.get('value'), 'cell_ids': ids}
  aid = engine.sha(engine.canonical(binding)); answers[aid] = binding; return aid
 for key in sorted(expected):
  if key[:2] not in records: raise ValueError('Admitted detailed visit missing')
  decision = decisions[key]; inv = inventory(flat, records[key[:2]], key[2], decision, cooler_rules); support = []
  for aid in decision['support']:
   a = source_answers[aid]
   if engine.sha(engine.canonical(a)) != aid: raise ValueError('Eligibility answer fingerprint differs')
   for cid in a['cell_ids']:
    if engine.sha(engine.canonical(source_cells[cid])) != cid: raise ValueError('Eligibility cell fingerprint differs')
    cells[cid] = source_cells[cid]
   answers[aid] = a; support.append(aid)
  inv['answer_ids'] = sorted(set(support + [retain(a) for a in inv.pop('answers')]))
  prepared[key] = inv
 for cat, code, brand in sorted(identities):
  for visit, month in sorted(cohort):
   inv = prepared[(visit, month, cat)]; decision = decisions[(visit, month, cat)]; known = inv['faces_by_code'].get(code)
   if inv['state'] == 'complete' and code not in inv['faces_by_code']: known = 0
   row = {'id': engine.sha(engine.canonical([visit, month, cat, code, brand])), 'kobo_id': visit, 'month': month, 'category': cat, 'brand_code': code, 'brand': brand, 'eligible': inv['eligible'], 'source_eligible': inv['source_eligible'], 'state': inv['state'], 'brand_faces': inv['faces_by_code'].get(code, 0) if inv['state'] == 'complete' else None, 'known_brand_faces_not_full_share': known, 'category_faces': inv['faces'], 'known_category_faces_subtotal_not_total': inv['known_faces'], 'signals': inv['signals'], 'category_signals': decision['signals'], 'answer_ids': inv['answer_ids']}
   rows.append(row); monthly[(month, cat, code, brand)].append(row); annual[(month[:4], cat, code, brand)].append(row)
 return {'schema': 'mindtec-declared-cold-share/1', 'version': VERSION, 'source_sha256': flat.source_sha256, 'unit': '%', 'formula': '100 * sum of brand cold faces / sum of category cold faces; complete applicable store-months only.', 'monthly': [aggregate(rs, k[0], 'month') for k, rs in sorted(monthly.items())], 'annual_observed_months': [aggregate(rs, k[0], 'year_observed_months_pooled_cold_faces') for k, rs in sorted(annual.items())], 'stores': rows, 'category_inventories': [dict(kobo_id=k[0], month=k[1], category=k[2], **inv) for k, inv in sorted(prepared.items())], 'cells': cells, 'answer_evidence': answers, 'limits': ['Global legacy cold lists are not partitioned by category or copied into several denominators.', 'Cold faces are declared counts, not measured temperature, equipment availability or accessible operating capacity.', 'No cooler is zero only with an explicit negative gate and no conflicting cold observations.', 'Year views pool faces from observed months; no annualization or averaging of shares.', 'Known subtotals never replace an incomplete category total.', 'Operational reconstruction, not official-panel reconciliation, human validation or fraud determination.']}
