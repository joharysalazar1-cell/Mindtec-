"""Structural suitability checks, not a certification of source truth."""
import unicodedata
import pandas as pd


def label(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(value).lower()) if not unicodedata.combining(c)).strip()


PROFILES={
    'Facturas': {'ID de factura': ['id factura','invoice_id'], 'Tienda': ['codigo sticker','codigo tienda','id_tienda','tienda_id'], 'Monto de factura': ['total factura','total_factura'], 'Fecha': ['fecha de emision','fecha']},
    'Líneas de factura': {'ID de factura':['id factura','invoice_id'], 'Producto':['producto','sku','producto_id'], 'Cantidad':['cantidad','quantity'], 'Importe de línea':['total neto','importe','total_linea']},
    'Catálogo de productos': {'Identificador':['id','sku','producto_id'], 'Producto':['producto','producto (sku)'], 'Marca':['marca'], 'Presentación':['contenido','presentacion']},
    'Catálogo de distribuidores': {'Identificador':['id','distribuidor_id'], 'Nombre':['valor','distribuidor','razon social']},
    'Control de envíos': {'Envío':['envio kobo','envio_id'], 'Tienda':['codigo tienda','codigo sticker','id_tienda'], 'Formulario':['formulario'], 'Fecha':['fecha visita','fecha de visita']},
    'Censo / observaciones de campo': {'Tienda':['codigo sticker','codigo tienda','id_tienda','tienda_id'], 'Periodo / visita':['fecha visita','fecha de visita','fecha','periodo','ola'], 'Producto / marca':['producto','marca','sku'], 'Exhibición o disponibilidad':['caras','caras_marca','share_of_shelf','presencia','d_quiebre_stock','quiebre']},
    'Export de indicadores del dashboard': {'Indicador':['indicador','metric'], 'Valor':['valor','valor_pct','value'], 'Periodo':['periodo','ola','fecha']},
    'Referencia externa': {},
}


def check_source(df,role):
    columns={label(c):str(c) for c in df.columns}
    checks=[]
    for concept,aliases in PROFILES[role].items():
        matched=[columns[a] for a in aliases if a in columns]
        checks.append(dict(requisito=concept,columna_detectada=' / '.join(matched),estado='Detectado' if matched else 'Requiere mapeo o fuente adicional'))
    table=pd.DataFrame(checks,columns=['requisito','columna_detectada','estado'])
    return table


def register_upload(state,name,content,sheets=None):
    import hashlib
    digest=hashlib.sha256(content).hexdigest()
    extension=name.rsplit('.',1)[-1].lower()
    if extension not in ('csv','xlsx','xls'):raise ValueError('Formato no admitido.')
    records=state.setdefault('archivos_cargados',{})
    if digest not in records:
        records[digest]=dict(nombre=name,extension=extension,tamano=len(content),contenido=content,hojas=sheets,origen='carga manual')
    return digest
