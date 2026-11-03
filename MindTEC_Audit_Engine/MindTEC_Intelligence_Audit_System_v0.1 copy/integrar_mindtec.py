"""Integra cuatro CSV exportados del sistema de normalización sin alterar sus datos originales.
Uso: python integrar_mindtec.py --carpeta "RUTA_CON_CSV" --salida "RUTA_SALIDA"
"""
from pathlib import Path
import argparse, json
import pandas as pd

ARCHIVOS = {
 'lineas':'entrega_normalizada_2026-11-03.csv',
 'facturas':'facturas_normalizadas_2026-11-03.csv',
 'productos':'catalogo_producto_2026-11-03.csv',
 'distribuidores':'catalogo_distribuidor_2026-11-03.csv',
}

def cargar(ruta):
    return pd.read_csv(ruta, sep=None, engine='python', encoding='utf-8-sig', low_memory=False) if False else pd.read_csv(ruta, sep=None, engine='python', encoding='utf-8-sig')

def integrar(carpeta, salida):
    carpeta, salida = Path(carpeta), Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    datos = {nombre:cargar(carpeta/archivo) for nombre,archivo in ARCHIVOS.items()}
    l,f,p,d = (datos[x] for x in ('lineas','facturas','productos','distribuidores'))
    for tabla,clave in ((f,'ID factura'),(p,'Producto (SKU)'),(d,'Valor')):
        if tabla[clave].isna().any() or tabla[clave].duplicated().any():
            raise ValueError(f'Clave no única o nula en {clave}; se detiene la integración para evitar duplicación.')
    # Prefijar columnas auxiliares para que la procedencia sea explícita.
    p2=p.rename(columns={'Producto (SKU)':'Producto',**{c:'catalogo_producto__'+c for c in p.columns if c!='Producto (SKU)'}})
    d2=d.rename(columns={'Valor':'Distribuidor',**{c:'catalogo_distribuidor__'+c for c in d.columns if c!='Valor'}})
    f2=f.rename(columns={c:'factura__'+c for c in f.columns if c!='ID factura'})
    base=l.merge(f2,on='ID factura',how='left',validate='many_to_one',indicator='_union_factura')
    base=base.merge(p2,on='Producto',how='left',validate='many_to_one',indicator='_union_producto')
    base=base.merge(d2,on='Distribuidor',how='left',validate='many_to_one',indicator='_union_distribuidor')
    if len(base)!=len(l):raise AssertionError('La unión alteró el número de líneas.')
    base.to_csv(salida/'lineas_enriquecidas.csv',index=False,encoding='utf-8-sig')
    f.to_csv(salida/'facturas_sin_duplicar.csv',index=False,encoding='utf-8-sig')
    resumen={
     'registros_lineas_originales':len(l),'registros_lineas_integradas':len(base),
     'facturas':len(f),'facturas_con_lineas':int(f['ID factura'].isin(l['ID factura']).sum()),
     'facturas_sin_lineas':f.loc[~f['ID factura'].isin(l['ID factura']),'ID factura'].astype(str).tolist(),
     'lineas_sin_factura':int((base['_union_factura']!='both').sum()),
     'lineas_sin_producto_catalogado':int((base['_union_producto']!='both').sum()),
     'lineas_sin_distribuidor_catalogado':int((base['_union_distribuidor']!='both').sum()),
     'lineas_sin_producto_informado':int(l['Producto'].isna().sum()),
     'lineas_sin_distribuidor_informado':int(l['Distribuidor'].isna().sum()),
     'filas_exactamente_duplicadas_en_origen':int(l.duplicated().sum()),
     'total_facturas_sin_duplicar':float(pd.to_numeric(f['Total factura'],errors='coerce').sum()),
     'total_neto_lineas':float(pd.to_numeric(l['Total neto'],errors='coerce').sum()),
    }
    resumen['diferencia_total_neto_menos_facturas']=round(resumen['total_neto_lineas']-resumen['total_facturas_sin_duplicar'],2)
    (salida/'control_integracion.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(resumen,ensure_ascii=False,indent=2))
    print('Archivos generados en:',salida.resolve())
    return resumen

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--carpeta',default='.',help='Carpeta que contiene los cuatro CSV')
    ap.add_argument('--salida',default='data/processed/integracion_2026-11-03')
    args=ap.parse_args()
    integrar(args.carpeta,args.salida)
