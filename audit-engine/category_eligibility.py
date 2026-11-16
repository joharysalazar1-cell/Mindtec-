"""Resolve subcategory eligibility only from explicit answers or agreed parent gates."""
from pathlib import Path

VERSION='category-eligibility/1.0.0'
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()

def observed(a):return a.get('state')=='observed'
def words(a):return a['value'].split() if observed(a) and isinstance(a.get('value'),str) else []

def decide(child,choice,*,parent_code=None,broad=None,registry=None,allowed_registry_codes=(),positive_repeat=False,positive_sibling=False):
 sources=[child,choice];signals=[];yesno=child.get('value') if observed(child) and child.get('value') in ('si','no') else None
 positive=bool(words(choice)) or positive_repeat
 broad=broad or {};registry=registry or {};bt=words(broad);rt=words(registry)
 broad_resolved=bool(parent_code and bt);registry_resolved=bool(parent_code and rt and set(rt)<=set(allowed_registry_codes))
 parents_agree_negative=broad_resolved and registry_resolved and parent_code not in bt and parent_code not in rt
 parents_disagree=broad_resolved and registry_resolved and ((parent_code in bt)!=(parent_code in rt))
 if parent_code:sources += [a for a in [broad,registry] if a]
 if parents_disagree:signals.append('parent_category_lists_disagree')
 if yesno=='no' and positive:
  value=None;method='conflicting_child_answers';reason='La subcategoría se niega pero hay marcas declaradas; requiere revisión.';signals.append('subcategory_denied_with_brand_evidence')
 elif yesno=='si' and parents_agree_negative:
  value=None;method='conflicting_child_and_parents';reason='La subcategoría se afirma pero ambas listas excluyen su familia.';signals.append('subcategory_positive_outside_parent_family')
 elif yesno is not None:
  value=yesno=='si';method='explicit_subcategory_answer';reason='Respuesta explícita de venta de la subcategoría.'
 elif parents_agree_negative and not positive and not positive_sibling:
  value=False;method='agreed_explicit_parent_exclusion';reason='Ambas listas explícitas excluyen la familia y no hay evidencia positiva de sus subcategorías; la pregunta hija quedó sin responder.'
 else:
  value=None;method='eligibility_unresolved';reason='Faltan respuestas inequívocas o existen contradicciones; no se imputa ausencia.'
  if parents_agree_negative and (positive or positive_sibling):signals.append('brand_evidence_outside_parent_family')
 return {'eligible':value,'method':method,'reason':reason,'signals':signals,'sources':sources,'parent_code':parent_code}
