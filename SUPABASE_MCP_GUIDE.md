# Supabase MCP - Guía de Uso Automático

## Configuración Actual

✅ **Supabase MCP está habilitado** en `~/.claude/settings.json`
- Plugin: `supabase@claude-plugins-official: true`
- Access Token: Configurado
- Project: euescxureboitxqjduym

## Comportamiento Automático Configurado

A partir de ahora, Claude Code **automáticamente** usará Supabase MCP cuando:

### 1. Antes de Implementar Código
- Inspectar estructura de tablas
- Validar queries con datos reales
- Verificar que los datos existen

### 2. Durante Debugging
- Consultar estado actual de datos
- Verificar integridad referencial
- Inspeccionar registros relacionados

### 3. Al Modificar Database
- Validar estado antes de migraciones
- Verificar éxito después de cambios
- Revisar esquemas y relaciones

### 4. Para Testing
- Probar queries SQL directamente
- Validar lógica de búsqueda
- Verificar resultados esperados

## Ejemplos de Uso Automático

### Escenario 1: "Arregla la búsqueda de proveedores por ciudad"
```
1. [AUTOMÁTICO] Usar Supabase MCP para ver estructura tabla providers
2. [AUTOMÁTICO] Query de prueba: SELECT * FROM providers WHERE city='Quito'
3. [AUTOMÁTICO] Verificar resultados y columnas disponibles
4. Luego: Implementar el fix en el código Python
```

### Escenario 2: "Debug por qué no se guarda el proveedor"
```
1. [AUTOMÁTICO] Query: SELECT * FROM providers WHERE phone='...'
2. [AUTOMÁTICO] Verificar si existe el registro
3. [AUTOMÁTICO] Inspeccionar columnas y valores
4. Luego: Identificar el bug en el código
```

### Escenario 3: "Agregar filtro por profesión"
```
1. [AUTOMÁTICO] Ver esquema: columnas disponibles en providers
2. [AUTOMÁTICO] Test query: SELECT * FROM providers WHERE profession='...'
3. [AUTOMÁTICO] Validar resultados con datos reales
4. Luego: Implementar el filtro en el servicio
```

## Ventajas

✅ **Más rápido**: No escribir scripts Python solo para ver datos
✅ **Más seguro**: Validar con datos reales antes de deploy
✅ **Más preciso**: Ver estructura actual vs asumir
✅ **Más eficiente**: Debugging en segundos vs minutos

## Recordatorios

❌ **NO** crear scripts de test para queries (usa MCP)
❌ **NO** ejecutar código solo para inspeccionar datos (usa MCP)
❌ **NO** asumir estructura de tabla (verifica con MCP)

✅ **SÍ** usar MCP para inspección rápida
✅ **SÍ** validar queries con MCP antes de implementar
✅ **SÍ** verificar datos con MCP durante debugging
