# Dashboard integrado: código de la entrega revisada

Esta carpeta conserva el código fuente de la integración del 24/11/2026. Se añade junto al dashboard anterior: no lo reemplaza ni cambia las aplicaciones existentes del repositorio.

## Cambios incluidos

- Vista ejecutiva, los 12 KPI y comparación entre plataforma y reconstrucción, con periodos mensuales y año observado.
- Diferencia directa, sesgo, MAE, RMSE, varianzas muestrales, covarianza, Pearson, r² y concordancia de Lin; se mantienen separados los indicadores y sus unidades.
- Referencias canónicas de producto de Scan separadas de la marca originalmente declarada.
- Revisión documental por caso, conservación de originales, versiones y huellas de evidencia.
- Confirmación humana de atribución de caras de Soy: conserva la etiqueta original y recalcula estante, agregados y métricas derivadas aplicables. La confirmación de caras no certifica códigos SKU ni completa otros componentes por inferencia.
- HTML integrado con carga local comprimida y cinco vistas anteriores completas; el historial permanece separado por fecha.

## Código y datos separados

`source/`, hojas de cálculo, bases SQLite, objetos de custodia, resultados, HTML con datos y credenciales quedan fuera de Git. Las fechas de las carpetas describen cortes privados; GitHub no contiene esos insumos ni es la versión navegable del dashboard.

Este es un paquete de código del entorno de trabajo, no una aplicación autónoma lista para ejecutar con datos reales después de clonar. Las copias en `engine/` se ejecutan desde el directorio original de `audit-engine`, junto con sus módulos de custodia y los insumos privados exigidos. No ejecute los scripts de revisión sobre otra colecta sin adaptar y verificar su alcance.

Los constructores web se ejecutan desde el checkout privado que contiene los informes de entrada. Con las fuentes privadas preparadas y sus ejecuciones verificadas, el orden es:

```powershell
node build-kpi-comparison.cjs
node build-executive.cjs
node build-integrated-local.cjs
```

Las rutas de salida del último constructor corresponden al espacio de trabajo original. Ajuste la ubicación de entrega antes de usarlo en otra estructura. Este commit no publica un sitio, no sincroniza Scan y no instala procesos automáticos.

## Verificaciones sin datos privados

Requiere Node 24 o posterior y Python 3 para validar sintaxis del backend:

```powershell
node dashboard-html/integrated/test-public.cjs
```

La prueba usa únicamente pares sintéticos para comprobar sesgo, errores, varianzas, covarianza y concordancia. También comprueba la sintaxis de los módulos y los controles de conservación de vistas.

La entrega local se verificó además con los insumos privados: atribución confirmada, preservación de celdas, comparación recalculada, reconstrucciones vigentes y conservación de las cinco vistas anteriores. Esas comprobaciones requieren los archivos de origen y no se presentan como reproducibles públicamente sin ellos.

## Interpretación

Una correlación alta no es un porcentaje de confianza. La varianza entre marcas describe heterogeneidad; la varianza de diferencias describe desacuerdo. El contraste con el panel es descriptivo mientras no se acredite la misma fórmula, universo, aplicabilidad y versión. No se inventan p-valores ni se convierten faltantes en ceros para aumentar cobertura.
