# Plan de Onboarding Seguro para Proveedores

## Objetivo

Implementar un proceso de registro que priorice la seguridad y verificación de identidad, usando evidencia fotográfica y redes sociales, con revisión manual en la primera fase.

## Resumen del Flujo

1. **Bot (WhatsApp)**
   - Detecta proveedor nuevo.
   - Informa sobre el proceso de verificación y envía enlace único a webapp.

2. **Webapp de Onboarding**
   - Solicita anverso/reverso de DNI o pasaporte.
   - Solicita selfie tomada en ese momento (captura de cámara).
   - Pide enlaces a redes sociales (Facebook, Instagram).
   - Confirma aceptación de términos biométricos y envía los archivos.

3. **Storage en Supabase**
   - Bucket dedicado `verifications` con políticas RLS estrictas.
   - Archivos subidos mediante URL firmada (caducidad corta).
   - Metadatos: `provider_id`, `timestamp`, `terms_version`.

4. **Backend/DB**
   - Registra en `provider_verifications` (o tabla existente) estado `pending`, rutas de archivos y enlaces sociales.
   - Guarda bandera `accepted_terms_biometric = true` con timestamp.
   - Al aprobar, replica los enlaces sociales verificados al perfil público para que el cliente pueda consultarlos.

5. **Revisión Manual (Fase 1)**
   - Equipo de verificación accede a consola interna (puede ser Supabase UI o panel propio).
   - Compara foto de documento, selfie y redes sociales.
   - Asigna resultado: `approved`, `rejected`, `needs_more_info` y un `verification_score`.
   - En caso de rechazo, el bot/notificación informa al proveedor para reintento.

6. **Automatización (Fase 2, opcional)**
   - Integrar servicio biométrico para comparar selfie vs. documento.
   - Automatizar verificación de redes (APIs oficiales o scraping controlado).
   - Mantener revisión manual como fallback.

## Fases y Prioridad

### Fase 1 (Critica / MVP)
- Webapp simple para subir fotos (documento + selfie).
- Almacenamiento seguro en Supabase Storage.
- Registro en base de datos de estado `pending` y enlaces sociales.
- Consola/manual review para validar identidad y redes.
- Bot informa resultado (aprobado / rechazo con reintento).

### Fase 2 (Mejoras)
- Integrar APIs de reconocimiento facial para scoring automático.
- Automatizar verificación de redes sociales (cuando sea viable).
- Dashboard con métricas de conversión, tiempos de revisión, distribuciones de score.
- Retención y eliminación automática (según política) con notificaciones.

### Fase 3 (Escalamiento)
- Revisiones distribuidas (equipos o BPO).
- Alertas automáticas cuando detecte inconsistencias.
- Auditoría detallada (log de accesos e informes para Legal).

## Consideraciones Técnicas

- **Seguridad:** cifrar en tránsito y en reposo, restringir lectura a servicios autorizados.
- **Consentimiento:** guardar versión y timestamp aceptados (ya disponible, sumar cláusula biométrica).
- **Tokens de subida:** generarlos desde el backend con expiración (ej. 15 min) y un solo uso.
- **Validación de archivos:** limitar a JPG/PNG, tamaño máx. (10 MB) y validar doble subida (frente/reverso).
- **Trazabilidad:** consolidar `verification_score` para exponerlo a otras áreas (Ops, CX).

## Próximos Pasos

1. Ajustar texto de consentimiento para incluir tratamiento biométrico (Legal).
2. Diseñar y maquetar la webapp (UX/Front).
3. Configurar bucket `verifications` y políticas RLS en Supabase (DevOps/Persistencia).
4. Definir tabla `provider_verifications` y metadatos necesarios.
5. Construir panel interno de revisión (puede iniciar en Supabase UI).
6. Integrar flujo en el bot para enviar enlace + trackear estados (`pending`, `approved`, `rejected`).
