"""One-time representation normalization; does not change selected versions."""
import json,pathlib
root=pathlib.Path(__file__).resolve().parent
data=json.loads((root/'catalog.json').read_text(encoding='utf-8'))
for p in data['packages']:
    if len(p['license'])>300:p['license']=p['license'][:300]+'… (texto completo en metadata_api)'
(root/'catalog.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
md=(root/'BIBLIOTECAS.md').read_text(encoding='utf-8').replace('Cada enlace procede de la ficha oficial de la distribución en PyPI.','Enlaces obtenidos de PyPI y documentación oficial; catalog.json registra la procedencia de cada repositorio.')
(root/'BIBLIOTECAS.md').write_text(md,encoding='utf-8')
