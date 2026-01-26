# Ejemplo de Uso de Repositorios

Este documento muestra cómo migrar el código de main.py para usar los nuevos repositorios.

## 1. Inicializar Repositorios (en main.py)

```python
from infrastructure.persistencia import (
    RepositorioClientesSupabase,
    RepositorioFlujoRedis,
)

# Inicializar repositorios
repositorio_clientes = RepositorioClientesSupabase(supabase)
repositorio_flujo = RepositorioFlujoRedis(redis_client)
```

## 2. Reemplazar funciones de main.py

### Antes (código original en main.py):

```python
async def get_or_create_customer(phone, full_name=None, city=None):
    if not supabase or not phone:
        return None
    try:
        existing = await run_supabase(
            lambda: supabase.table("customers")
            .select("id, phone_number, full_name, city, city_confirmed_at, has_consent, notes, created_at, updated_at")
            .eq("phone_number", phone)
            .limit(1)
            .execute(),
            label="customers.by_phone",
        )
        if existing.data:
            return existing.data[0]

        payload = {
            "phone_number": phone,
            "full_name": full_name or "Cliente TinkuBot",
        }
        if city:
            payload["city"] = city
            payload["city_confirmed_at"] = datetime.utcnow().isoformat()

        created = await run_supabase(
            lambda: supabase.table("customers").insert(payload).execute(),
            label="customers.insert",
        )
        if created.data:
            return created.data[0]
    except Exception as exc:
        logger.warning(f"No se pudo crear/buscar customer {phone}: {exc}")
    return None
```

### Después (usando el repositorio):

```python
# Usar el repositorio
customer = await repositorio_clientes.obtener_o_crear(
    phone=phone,
    full_name=full_name,
    city=city,
)
```

## 3. Mapeo de Funciones

### RepositorioClientesSupabase

| Función original (main.py) | Método del repositorio |
|----------------------------|------------------------|
| `get_or_create_customer(phone, full_name, city)` | `repositorio_clientes.obtener_o_crear(phone, full_name=..., city=...)` |
| `update_customer_city(customer_id, city)` | `repositorio_clientes.actualizar_ciudad(customer_id, city)` |
| `clear_customer_city(customer_id)` | `repositorio_clientes.limpiar_ciudad(customer_id)` |
| `clear_customer_consent(customer_id)` | `repositorio_clientes.limpiar_consentimiento(customer_id)` |

### RepositorioFlujoRedis

| Función original (main.py) | Método del repositorio |
|----------------------------|------------------------|
| `get_flow(phone)` | `repositorio_flujo.obtener(phone)` |
| `set_flow(phone, data)` | `repositorio_flujo.guardar(phone, data)` |
| `reset_flow(phone)` | `repositorio_flujo.resetear(phone)` |

## 4. Inyectar dependencias en el orquestador

```python
# En startup_event()
orquestador.inyectar_callbacks(
    # Reemplazar funciones originales con métodos de repositorios
    get_or_create_customer=repositorio_clientes.obtener_o_crear,
    update_customer_city=repositorio_clientes.actualizar_ciudad,
    clear_customer_city=repositorio_clientes.limpiar_ciudad,
    clear_customer_consent=repositorio_clientes.limpiar_consentimiento,

    get_flow=repositorio_flujo.obtener,
    set_flow=repositorio_flujo.guardar,
    reset_flow=repositorio_flujo.resetear,

    # ... otros callbacks existentes
)
```

## 5. Beneficios de la Refactorización

1. **Separación de responsabilidades**: main.py ahora solo contiene la capa HTTP
2. **Testabilidad**: Los repositorios se pueden testear independientemente
3. **Reutilización**: Los repositorios se pueden usar en otros módulos
4. **Mantenibilidad**: La lógica de acceso a datos está centralizada
5. **Consistencia**: Todas las operaciones usan los mismos métodos con la misma lógica

## 6. Próximos Pasos

1. Reemplazar todas las llamadas a funciones originales en main.py
2. Actualizar el orquestador para usar los repositorios
3. Eliminar las funciones originales de main.py
4. Verificar que todos los tests pasan
