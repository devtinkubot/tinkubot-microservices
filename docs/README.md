# 📚 Documentación TinkuBot

Bienvenido a la documentación oficial de TinkuBot. Aquí encontrarás toda la información necesaria para entender, operar y mantener el sistema.

## 🚀 Estado Actual del Sistema

**✅ Sistema Operativo**: TinkuBot está funcionando con la arquitectura actual implementada.
- **Tabla principal**: `customers` (no `clientes` - la migración a español no se realizó)
- **Consentimiento**: Completamente implementado y funcional
- **Flujo de clientes**: Activo en producción
- **Servicios**: Todos los microservicios operativos

## 📋 Documentación Disponible

### 📖 **Documentación Principal (Actualizada)**

#### [📄 Arquitectura de Base de Datos](./database-architecture.md)
- Estructura real de tablas implementadas
- Campos y relaciones de `customers`, `consents`, `service_requests`
- Flujo de datos real del sistema
- **Estado**: ✅ Actualizado con código en producción

#### [📄 Flujo de Consentimiento](./consent-flow.md)
- Implementación completa del sistema de consentimiento
- Flujo paso a paso con capturas de pantalla
- Estructura de datos y metadata legal
- **Estado**: ✅ Funcionando en producción

#### [📄 Operaciones y Mantenimiento](./OPERATIONS.md)
- Guía de despliegue y configuración
- Comandos útiles diarios
- Variables de entorno
- Flujo completo incluyendo consentimiento
- **Estado**: ✅ Actualizado con puertos correctos

#### [📄 Guía Principal del Proyecto](../CLAUDE.md)
- Arquitectura general de microservicios
- Comandos de desarrollo
- Estructura de datos y flujos
- **Estado**: ✅ Actualizado con tablas reales

### 🧪 **Testing y Validación**

#### [📄 Checklist de QA](./qa-checklist.md)
- Casos de prueba completos para validar el sistema
- Escenarios de consentimiento, búsqueda, y feedback
- Queries de validación de base de datos
- **Estado**: ✅ Listo para ejecución en QA

### 🏗️ **Arquitectura**

#### [📄 Flujo de Interés de Proveedores](./architecture/provider-interest-flow.md)
- Documentación del flujo de proveedores
- **Estado**: Requiere validación

### 📦 **Documentación Histórica (Archivada)**

La siguiente documentación ha sido movida a `archive/` porque está obsoleta:

- [📁 Migración a Español](./archive/migracion-architectura-espanol.md) - *No implementado*
- [📁 Guías de Migración](./archive/) - *Planes no ejecutados*
- [📁 Plan de Consentimiento](./archive/consent-onboarding-plan.md) - *Reemplazado por implementación real*

> **Nota**: La documentación en `archive/` se conserva para referencia histórica pero no refleja el estado actual del sistema.

## 🎯 Resumen Ejecutivo del Estado Actual

### ✅ **Implementado y Funcionando**

1. **Sistema de Consentimiento**
   - Tabla `customers` con campo `has_consent`
   - Tabla `consents` para registro legal completo
   - Flujo automatizado de solicitud y registro

2. **Gestión de Clientes**
   - Registro automático en `customers`
   - Detección y actualización de ciudades
   - Historial de solicitudes en `service_requests`

3. **Búsqueda de Proveedores**
   - Integración con `ai-service-proveedores`
   - Respuestas estructuradas con opciones
   - Sistema de feedback programado

4. **Infraestructura**
   - WhatsApp Web.js para automatización
   - OpenAI para procesamiento de lenguaje
   - Supabase para persistencia de datos
   - Redis para caché y sesiones

### ⚠️ **Consideraciones Importantes**

- **No se migró a nombres en español**: Las tablas mantienen nombres en inglés (`customers`, no `clientes`)
- **El sistema funciona correctamente**: La arquitectura actual es estable y operativa
- **El consentimiento es obligatorio**: Ningún cliente puede usar el servicio sin aceptar términos

## 🚀 Para Empezar

### Para Desarrolladores
1. Lee [`../CLAUDE.md`](../CLAUDE.md) para entender la arquitectura
2. Revisa [`database-architecture.md`](./database-architecture.md) para las tablas
3. Consulta [`OPERATIONS.md`](./OPERATIONS.md) para comandos útiles

### Para QA
1. Ejecuta el [`qa-checklist.md`](./qa-checklist.md) completo
2. Valida todos los escenarios de consentimiento
3. Verifica la persistencia de datos en Supabase

### Para Operaciones
1. Usa [`OPERATIONS.md`](./OPERATIONS.md) como guía diaria
2. Monitorea los health checks de los servicios
3. Revisa los logs de consentimientos regularmente

## 📞 Soporte

Si encuentras alguna discrepancia entre la documentación y el código real:

1. **Verifica el código fuente**: La verdad está en el código implementado
2. **Revisa la fecha de actualización**: Prioriza documentos más recientes
3. **Reporta la incidencia**: Crea un ticket para actualizar la documentación

---

**Última actualización**: Enero 2025
**Estado**: Documentación sincronizada con producción
**Mantenimiento**: Revisar trimestralmente o después de cambios mayores