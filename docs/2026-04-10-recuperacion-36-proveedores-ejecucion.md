# Ejecucion piloto y recuperacion operativa de proveedores perdidos

Fecha: 2026-04-10
Autor: Codex
Contexto base: `docs/2026-04-10-recuperacion-36-proveedores-bug-verified.md`

## Resumen

Se ejecuto una recuperacion operativa re-publicando eventos historicos de `provider_onboarding_events`
para proveedores ausentes en Supabase, usando el worker ya corregido tras el bug de la columna
`verified`.

La estrategia aplicada fue:

1. Validar ausencia previa en Supabase.
2. Detectar en Redis el intento mas reciente y coherente por telefono.
3. Re-publicar los eventos al mismo stream con `idempotency_key` nuevos.
4. Verificar procesamiento en logs del worker.
5. Confirmar presencia final en Supabase y estado `pending_verification`.

## Casos recuperados en esta ejecucion

### Piloto inicial

- `3aac2498-2991-48d4-9a99-8235af167389` -> `593995971988@s.whatsapp.net`
- `0d769fd5-7eca-4955-b718-7a1f74091ca3` -> `593959091325@s.whatsapp.net`

### Lote adicional recuperado

- `f46a6470-10b1-4ca3-9b40-d729ced26653` -> `593959950572@s.whatsapp.net`
- `937d29e2-4f20-47de-a408-4bd768d06311` -> `593999701420@s.whatsapp.net`
- `6f3b9de0-fa1d-4c95-b7e7-40e45c6659f6` -> `593986914965@s.whatsapp.net`
- `a2afd6ae-bd4b-4208-bd13-ae85734ce0f1` -> `593998905993@s.whatsapp.net`
- `031d9076-85d4-4dd8-9a91-33950c3aafeb` -> `593994685769@s.whatsapp.net`
- `60f9f106-0b67-4823-bdc0-cfccc7e39bd3` -> `593987450112@s.whatsapp.net`
- `393f138f-acfe-4f10-8936-9b607e4de684` -> `593980569520@s.whatsapp.net`
- `53d0914e-d536-41f4-a142-ad5908a2ea45` -> `593986310580@s.whatsapp.net`
- `fda8a782-6cd6-42be-88fc-6a607d7ca0ec` -> `593995376732@s.whatsapp.net`
- `6293d068-663a-4e5b-b322-9121c7d72a15` -> `593990549380@s.whatsapp.net`

## Validaciones realizadas

- Antes de cada replay se verifico que los `provider_id` objetivo no existieran en `providers`.
- Se confirmo presencia de eventos en Redis para cada telefono.
- Se verifico en logs de `tinkubot-provider-onboarding-worker` el procesamiento de:
  - `consent`
  - `city`
  - `dni_front`
  - `face`
  - `experience`
  - `services`
  - `social`
- Se confirmo en Supabase que los 12 `provider_id` anteriores existen.
- Se verifico estado final consolidado:
  - `expected: 12`
  - `found: 12`
  - `missing: []`
  - `statuses: { pending_verification: 12 }`
- Se realizo una pasada final para detectar remanentes:
  - `remaining_count: 0`

## Incidencias durante la ejecucion

- Los payloads de imagen hicieron fallar un primer intento de `XADD` por tamano de argumentos del
  proceso.
- Se resolvio operativamente usando envio por `stdin` hacia `redis-cli --pipe`.
- Para evitar re-publicar eventos del propio piloto, se excluyeron `idempotency_key` con prefijo
  `pilot-replay-`.
- En algunos casos fue necesario re-publicar solo eventos finales (`services` y/o `social`) para
  corregir el `onboarding_step` sin reabrir checkpoints previos.
- Se observo un `409` puntual por duplicado en `provider_services`, pero el flujo termino con el
  proveedor en `pending_verification`.

## Conclusion

La recuperacion operativa ejecutada en esta sesion quedo cerrada satisfactoriamente.

- Los casos intervenidos fueron recuperados.
- Todos quedaron visibles en dashboard como `Nuevos`.
- No se detectaron grupos coherentes adicionales cuyo intento mas reciente por telefono siga ausente
  en Supabase.
