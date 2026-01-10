# Guía de Migración: Eliminar ai-search

## Estado Actual

**Fase Completada: Extract + Update (sin breaking changes)**

- ✅ QueryInterpreterService creado (IA que interpreta queries)
- ✅ ProviderRepository creado (acceso directo a Supabase)
- ✅ search_service.py actualizado con funciones *_new y *_legacy
- ✅ main.py actualizado con inicializaciones
- ✅ Funciones legacy mantenidas como fallback
- ✅ NO breaking changes en imports

## Estrategia de Migración

### Fase 1: Validación (ANTES de eliminar ai-search)

```bash
# 1. Levantar servicios con ai-search aún activo
docker-compose up -d ai-search ai-clientes

# 2. Verificar logs que muestran "[NUEVO]" o "[LEGACY]"
docker-compose logs -f ai-clientes | grep -E "\[NUEVO\]|\[LEGACY\]"

# 3. Probar búsqueda con IA
# POST /process-message con {"message": "tengo goteras"}
# Debería ver logs:
# 🔍 [NUEVO] Buscando con IA + DB: query='plomero en Quito'
# 🧠 IA interpretó: 'tengo goteras' → 'plomero'
# ✅ [NUEVO] Búsqueda DB directo: 10 proveedores

# 4. Verificar que nueva lógica funciona
# Si ves "[NUEVO]" y resultados correctos → EXITO
# Si ves "[LEGACY]" → fallback funcionando (ai-search aún se usa)
```

### Fase 2: Eliminación (DESPUÉS de validar)

**Opción A: Eliminación completa (sin rollback fácil)**

```bash
# 1. Eliminar servicio ai-search del proyecto
rm -rf python-services/ai-search/

# 2. Eliminar search_client.py (ya no se necesita)
rm python-services/ai-clientes/search_client.py

# 3. Actualizar docker-compose.yml
# Eliminar toda la sección "ai-search:"

# 4. Actualizar search_service.py
# - Eliminar import: from search_client import search_client
# - Eliminar funciones: *_legacy, _fallback_*
# - Renombrar *_new → nombres definitivos
# - Eliminar instancia global search_client

# 5. Reiniciar servicios
docker-compose down
docker-compose up -d ai-clientes
```

**Opción B: Eliminación gradual (CON rollback fácil)**

```bash
# Paso 1: Desactivar ai-search en docker-compose.yml
# Commentar toda la sección "ai-search:"

# Paso 2: Verificar que funciona sin ai-search
docker-compose up -d ai-clientes
# Probar búsqueda - debería usar *_new

# Paso 3: Si todo funciona, eliminar archivos
rm -rf python-services/ai-search/
rm python-services/ai-clientes/search_client.py

# Paso 4: Limpiar código legacy
# Editar search_service.py:
# - Eliminar imports de search_client
# - Eliminar funciones *_legacy
# - Renombrar funciones *_new → sin sufijo

# Paso 5: Commit cambios
git add .
git commit -m "feat(sprint-2.4): remove ai-search SPOF"
```

### Fase 3: Limpieza de Código (OPCIONAL)

Después de validar que todo funciona sin ai-search, puedes limpiar:

```python
# search_service.py - ANTES (actual)
async def intelligent_search_providers_new(payload): ...
async def intelligent_search_providers_legacy(payload): ...
async def intelligent_search_providers_remote(payload):  # Enruta

# search_service.py - DESPUÉS (limpio)
async def intelligent_search_providers(payload):  # Solo implementa lógica nueva
    # IA interpreta + DB directo
    ...
```

## Rollback

Si algo sale mal:

```bash
# Opción 1: Git revert (MÁS SEGURO)
git revert <commit-hash>
git push

# Opción 2: Git reset (MÁS RÁPIDO pero destructivo)
git reset --hard HEAD~1  # Volver al commit anterior
git push --force

# Opción 3: Reactivar ai-search
# Descomentar sección en docker-compose.yml
docker-compose up -d ai-search
```

## Checklist de Validación

Antes de eliminar ai-search, verificar:

- [ ] Nuevos servicios se inicializan correctamente
  ```bash
  docker-compose logs ai-clientes | grep "QueryInterpreterService inicializado"
  docker-compose logs ai-clientes | grep "ProviderRepository inicializado"
  ```

- [ ] Búsquedas usan "[NUEVO]" en logs
  ```bash
  docker-compose logs ai-clientes | grep "\[NUEVO\]"
  ```

- [ ] IA interpreta queries correctamente
  ```bash
  # Probar "tengo goteras" → debe interpretar como "plomero"
  # Probar "limpieza facial" → debe interpretar como "estética"
  ```

- [ ] Búsqueda DB directo retorna proveedores
  ```bash
  # POST /process-message debe retornar providers
  # Verificar que providers.data no esté vacío
  ```

- [ ] Disponibilidad MQTT aún funciona
  ```bash
  # Los 10 proveedores aún se contactan por WhatsApp
  # MQTT Broker aún publica respuestas
  ```

## Archivos Modificados

```
python-services/ai-clientes/
├── services/
│   ├── query_interpreter_service.py  # NUEVO - IA interpreta queries
│   ├── providers/
│   │   ├── __init__.py               # NUEVO
│   │   └── provider_repository.py    # NUEVO - Acceso directo Supabase
│   └── search_service.py             # MODIFICADO - Funciones *_new y *_legacy
├── main.py                            # MODIFICADO - Inicializa nuevos servicios
└── search_client.py                   # A ELIMINAR después de validar
```

## Comandos Útiles

```bash
# Verificar que nuevos servicios compilan
python3 -m py_compile services/query_interpreter_service.py
python3 -m py_compile services/providers/provider_repository.py

# Verificar imports
grep -r "from.*search_service import" services/

# Verificar referencias a search_client
grep -r "search_client" --include="*.py" .

# Ver logs de AI interpretando queries
docker-compose logs ai-clientes | grep "IA interpretó"

# Ver logs de búsqueda DB directo
docker-compose logs ai-clientes | grep "DB directo"
```

## Soporte

Si encuentras problemas:

1. **Verificar logs**: `docker-compose logs ai-clientes | tail -100`
2. **Verificar imports**: `python3 -c "from services.search_service import ..."`
3. **Rollback a commit anterior**: `git revert <hash>`
4. **Reactivar ai-search**: Descomentar en docker-compose.yml

## Resumen

**Estado Actual**: Funcionalidad implementada CON fallback a ai-search

**Próximo Paso**: Validar que nueva lógica funciona sin ai-search

**Beneficios Esperados**:
- ✅ Eliminar SPOF (ai-clientes deja de depender de ai-search)
- ✅ Menor latencia (150ms vs 100-300ms actual)
- ✅ IA de interpretación mantenida (DIFERENCIADOR)
- ✅ Disponibilidad real vía MQTT (DIFERENCIADOR PRINCIPAL)
