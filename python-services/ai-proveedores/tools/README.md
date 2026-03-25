# Tools

Herramientas operativas y scripts de mantenimiento para `ai-proveedores`.

## Qué va aquí

- Backfills de datos históricos.
- Reportes manuales de revisión.
- Sincronizaciones puntuales.
- Utilidades de depuración y limpieza.
- Verificaciones post-migración.

## Subcarpetas

- `backfill/`: procesos y verificaciones de backfill.
- `maintenance/`: utilidades operativas, depuración y sincronización.
- `reports/`: generación de reportes de revisión.

## Uso

Ejecuta cada herramienta desde esta carpeta o siguiendo las instrucciones internas de cada script.

Ejemplos:

```bash
cd python-services/ai-proveedores/tools/backfill
./run_backfill.sh --help
./verify_backfill.sh
```
