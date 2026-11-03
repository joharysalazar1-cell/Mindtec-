"""Independent, non-mutating audit operations."""
import numpy as np
import pandas as pd


def quality_report(df, keys=()):
    rows = []
    def add(rule, count, detail):
        rows.append(dict(control=rule, casos=int(count), detalle=detail))
    add('Duplicados exactos', df.duplicated().sum(), 'Alertas; no se eliminan registros.')
    for col in df:
        add(f'Faltantes: {col}', df[col].isna().sum(), 'Confirmar obligatoriedad o no aplicabilidad.')
    if keys:
        add('Clave incompleta', df[list(keys)].isna().any(axis=1).sum(), ', '.join(keys))
        add('Clave repetida', df.duplicated(list(keys), keep=False).sum(), 'Filas implicadas; comprobar unidad de observación.')
    return pd.DataFrame(rows)


def reconcile(left, right, left_keys, right_keys, left_value, right_value, atol=0.0, rtol=0.0):
    """Full outer comparison. Reject ambiguous keys instead of multiplying rows."""
    if not left_keys or len(left_keys) != len(right_keys):
        raise ValueError('Selecciona el mismo número de claves en ambas fuentes.')
    frames = []
    for df, keys, value, label in ((left,left_keys,left_value,'base'), (right,right_keys,right_value,'referencia')):
        if value in keys:
            raise ValueError('La medida no puede formar parte de la clave.')
        if df[keys].isna().any(axis=None):
            raise ValueError(f'Hay claves incompletas en {label}; revísalas en Auditoría de la base.')
        if df.duplicated(keys).any():
            raise ValueError(f'La clave de {label} se repite. Agrega claves o prepara una agregación explícita en otra fuente.')
        out = df[keys + [value]].copy()
        out.columns = [f'clave_{i+1}' for i in range(len(keys))] + [label]
        for col in out.columns[:-1]:
            out[col] = out[col].astype('string')
        # Text comparison is exact; no stripping, case-folding or alias replacement.
        converted = pd.to_numeric(out[label], errors='coerce')
        invalid = out[label].notna() & (converted.isna() | ~np.isfinite(converted))
        if invalid.any():
            raise ValueError(f'Medidas no numéricas o infinitas en {label}: {int(invalid.sum())}. No se convierten silenciosamente.')
        out[label] = converted
        # Type conversion itself must not collapse different source keys.
        if out.duplicated(list(out.columns[:-1])).any():
            raise ValueError(f'Claves ambiguas al comparar como texto en {label}.')
        frames.append(out)
    keys = [f'clave_{i+1}' for i in range(len(left_keys))]
    result = frames[0].merge(frames[1], on=keys, how='outer', validate='one_to_one', indicator=True)
    result['diferencia'] = result['base'] - result['referencia']
    result['diferencia_pct'] = result['diferencia'].div(result['referencia'].replace(0,np.nan))*100
    result['estado'] = 'Diferencia no explicada'
    both = result['_merge'].eq('both')
    missing = result[['base','referencia']].isna().any(axis=1)
    close = np.isclose(result['base'],result['referencia'],atol=atol,rtol=rtol,equal_nan=False)
    result.loc[both & close,'estado'] = 'Dentro de tolerancia'
    result.loc[both & result['base'].eq(result['referencia']),'estado'] = 'Coincidencia exacta'
    result.loc[both & missing,'estado'] = 'Medida faltante'
    result.loc[result['_merge'].eq('left_only'),'estado'] = 'Solo en base'
    result.loc[result['_merge'].eq('right_only'),'estado'] = 'Solo en referencia'
    return result.drop(columns='_merge')


def ratio_metric(df, mode, numerator, denominator, entity=None, eligible=None, eligible_value=None):
    """Explicit ratio of sums or distinct eligible entities; never guess business semantics."""
    data = df.copy()
    if mode == 'Tiendas':
        if not entity or not eligible:
            raise ValueError('Define identificador y criterio de elegibilidad.')
        data = data[data[eligible].astype('string').eq(str(eligible_value)).fillna(False)]
        if data[entity].isna().any():
            raise ValueError('Hay identificadores faltantes en las filas elegibles.')
        den = data[entity].nunique()
        num = data.loc[data[numerator].astype('string').eq(str(denominator)).fillna(False),entity].nunique()
    else:
        numbers = data[[numerator,denominator]].apply(pd.to_numeric,errors='coerce')
        if numbers.isna().any(axis=None) or not np.isfinite(numbers.to_numpy()).all():
            raise ValueError('Hay medidas faltantes o no numéricas. Define primero su tratamiento.')
        if (numbers < 0).any(axis=None) or (numbers[numerator] > numbers[denominator]).any():
            raise ValueError('Se requieren valores no negativos y numerador ≤ denominador en cada fila.')
        num,den = numbers[numerator].sum(),numbers[denominator].sum()
    if den <= 0:
        raise ValueError('El denominador es cero: indicador no verificable.')
    return float(num),float(den),float(100*num/den)
