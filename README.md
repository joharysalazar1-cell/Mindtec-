# MindTEC

Código y documentación del sistema de inteligencia y auditoría de datos.

## Bibliotecas y repositorios de datos

El [toolkit de datos](data-toolkit/README.md) reúne 51 bibliotecas en 10 perfiles, un catálogo de repositorios oficiales y un lock con hashes para Windows x64 / Python 3.14. Consulta la [biblioteca de referencias](data-toolkit/BIBLIOTECAS.md) para elegir herramientas según la tarea.

## Sistema de auditoría v0.1

Consulta la instalación y el uso en [el README del sistema](MindTEC_Audit_Engine/MindTEC_Intelligence_Audit_System_v0.1/README.md).

## Acceder desde otra PC

Descarga este repositorio desde GitHub con **Code > Download ZIP**, o clónalo con Git:

```powershell
git clone https://github.com/joharysalazar1-cell/Mindtec-.git
cd "Mindtec-/MindTEC_Audit_Engine/MindTEC_Intelligence_Audit_System_v0.1 copy"
```

Para ejecutar el sistema, sigue las instrucciones de instalación del README del sistema. Los datos de entrada y los resultados de auditoría se mantienen fuera del repositorio.

## Motor de auditoría actualizado

La carpeta [MindTEC_Audit_Engine](MindTEC_Audit_Engine/) contiene el proyecto copiado desde esta PC. La interfaz Streamlit está en la subcarpeta **MindTEC_Intelligence_Audit_System_v0.1 copy**.

Los datos y resultados se conservan en la copia local; se excluyen de GitHub junto con el entorno virtual y los archivos de respaldo.

## Auditor interactivo y conexión API

Ejecuta la aplicación de la carpeta **MindTEC_Intelligence_Audit_System_v0.1 copy**. Incluye una demo sintética, contraste entre fuentes, indicadores con denominador explícito y hallazgos exportables. Consulta [la guía de ejecución y API](MindTEC_Audit_Engine/MindTEC_Intelligence_Audit_System_v0.1%20copy/docs/auditor_motor.md).

GitHub distribuye el código; una URL de aplicación compartida requiere desplegar Streamlit. La API se conecta al configurar el endpoint, la autenticación y el esquema de respuesta; las credenciales y los datos reales quedan fuera del repositorio.
