# Guía: Actualización de Código para Migración

## 🎯 Objetivo

Proporcionar una guía detallada para actualizar todo el código fuente de TinkuBot y soportar la migración de las tablas en inglés a español, manteniendo la compatibilidad durante el proceso.

## 📋 Servicios Afectados

### Python Services
1. **ai-service-clientes** (puerto 5001)
2. **ai-service-proveedores** (puerto 5002)

### Node.js Services
1. **whatsapp-service-clientes** (puerto 7001)
2. **whatsapp-service-proveedores** (puerto 7002)

### Configuración
1. Variables de entorno
2. Docker Compose
3. Scripts de despliegue

---

## 🐍 Cambios en Python Services

### 1. AI Service Clientes

#### Archivo: `python-services/ai-service-clientes/main.py`

**Cambios principales en funciones de clientes:**

```python
# ANTES (Línea ~552)
def get_or_create_customer(
    phone: str,
    *,
    full_name: Optional[str] = None,
    city: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Obtiene o crea un registro en `customers` asociado al teléfono."""

    if not supabase or not phone:
        return None

    try:
        existing = (
            supabase.table("customers")  # ← TABLA ANTIGUA
            .select(
                "id, phone_number, full_name, city, city_confirmed_at, notes, created_at, updated_at"
            )
            .eq("phone_number", phone)  # ← CAMPO ANTIGUO
            .limit(1)
            .execute()
        )
        if existing.data:
            return existing.data[0]

        payload: Dict[str, Any] = {
            "phone_number": phone,  # ← CAMPO ANTIGUO
            "full_name": full_name or "Cliente TinkuBot",
        }

        if city:
            payload["city"] = city
            payload["city_confirmed_at"] = datetime.utcnow().isoformat()

        created = supabase.table("customers").insert(payload).execute()  # ← TABLA ANTIGUA
        if created.data:
            return created.data[0]
    except Exception as exc:
        logger.warning(f"No se pudo crear/buscar customer {phone}: {exc}")
    return None

# DESPUÉS (Nueva implementación)
def get_or_create_cliente(
    telefono: str,
    *,
    nombre_completo: Optional[str] = None,
    ciudad: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Obtiene o crea un registro en `clientes` asociado al teléfono."""

    if not supabase or not telefono:
        return None

    # Determinar qué tabla usar según modo de migración
    table_name = "clientes" if not settings.migration_mode else "customers"
    phone_field = "telefono" if not settings.migration_mode else "phone_number"
    name_field = "nombre_completo" if not settings.migration_mode else "full_name"

    try:
        existing = (
            supabase.table(table_name)
            .select(
                f"id, {phone_field}, {name_field}, city, city_confirmed_at, notes, created_at, updated_at"
            )
            .eq(phone_field, telefono)
            .limit(1)
            .execute()
        )
        if existing.data:
            return existing.data[0]

        payload: Dict[str, Any] = {
            phone_field: telefono,
            name_field: nombre_completo or "Cliente TinkuBot",
        }

        if ciudad:
            payload["city"] = ciudad
            payload["city_confirmed_at"] = datetime.utcnow().isoformat()

        created = supabase.table(table_name).insert(payload).execute()
        if created.data:
            return created.data[0]
    except Exception as exc:
        logger.warning(f"No se pudo crear/buscar cliente {telefono}: {exc}")
    return None
```

**Cambio en función de actualización de ciudad:**

```python
# ANTES (Línea ~593)
def update_customer_city(customer_id: Optional[str], city: str) -> Optional[Dict[str, Any]]:
    if not supabase or not customer_id or not city:
        return None
    try:
        update_resp = (
            supabase.table("customers")  # ← TABLA ANTIGUA
            .update(
                {
                    "city": city,
                    "city_confirmed_at": datetime.utcnow().isoformat(),
                }
            )
            .eq("id", customer_id)
            .execute()
        )
        if update_resp.data:
            return update_resp.data[0]

# DESPUÉS (Nueva implementación)
def update_cliente_ciudad(cliente_id: Optional[str], ciudad: str) -> Optional[Dict[str, Any]]:
    if not supabase or not cliente_id or not ciudad:
        return None

    table_name = settings.get_table_name("clientes")

    try:
        update_resp = (
            supabase.table(table_name)
            .update(
                {
                    "city": ciudad,
                    "city_confirmed_at": datetime.utcnow().isoformat(),
                }
            )
            .eq("id", cliente_id)
            .execute()
        )
        if update_resp.data:
            return update_resp.data[0]

        select_resp = (
            supabase.table(table_name)
            .select(
                f"id, phone_number, full_name, city, city_confirmed_at, updated_at"
            )
            .eq("id", cliente_id)
            .limit(1)
            .execute()
        )
        if select_resp.data:
            return select_resp.data[0]
    except Exception as exc:
        logger.warning(f"No se pudo actualizar city para customer {cliente_id}: {exc}")
    return None
```

**Cambio en inserción de service_requests:**

```python
# ANTES (Línea ~735)
supabase.table("service_requests").insert({
    "phone": phone,
    "intent": "service_request",
    "profession": profession,
    "location_city": location,
    "requested_at": datetime.utcnow().isoformat(),
    "resolved_at": datetime.utcnow().isoformat(),
    "suggested_providers": providers,
}).execute()

# DESPUÉS (Nueva implementación)
table_name = settings.get_table_name("solicitudes_servicio")
supabase.table(table_name).insert({
    "telefono": phone,
    "tipo_solicitud": "servicio",
    "profesion_solicitada": profession,
    "ciudad": location,
    "solicitado_at": datetime.utcnow().isoformat(),
    "resuelto_at": datetime.utcnow().isoformat(),
    "proveedores_sugeridos": providers,
}).execute()
```

**Cambio en función principal de manejo de WhatsApp:**

```python
# ANTES (Línea ~877)
customer_profile = get_or_create_customer(phone=phone)

# DESPUÉS (Nueva implementación)
customer_profile = get_or_create_cliente(telefono=phone)
```

#### Archivo: `python-services/ai-service-clientes/config.py`

```python
# Añadir soporte para migración
class Settings:
    # ... configuración existente ...

    # Configuración de migración
    migration_mode: bool = os.getenv("MIGRATION_MODE", "false").lower() == "true"

    # Nombres de tablas
    table_clientes: str = os.getenv("TABLE_CLIENTES", "clientes")
    table_profesiones: str = os.getenv("TABLE_PROFESIONES", "profesiones")
    table_solicitudes_servicio: str = os.getenv("TABLE_SOLICITUDES_SERVICIO", "solicitudes_servicio")
    table_mensajes: str = os.getenv("TABLE_MENSAJES", "mensajes")
    table_sesiones: str = os.getenv("TABLE_SESIONES", "sesiones")
    table_tareas_programadas: str = os.getenv("TABLE_TAREAS_PROGRAMADAS", "tareas_programadas")

    # Tablas legacy (para fallback)
    table_customers_legacy: str = "customers"
    table_service_requests_legacy: str = "service_requests"
    table_messages_legacy: str = "messages"
    table_sessions_legacy: str = "sessions"
    table_task_queue_legacy: str = "task_queue"

    def get_table_name(self, table_type: str) -> str:
        """Obtener nombre de tabla según modo de migración"""
        if self.migration_mode:
            legacy_mapping = {
                "clientes": self.table_customers_legacy,
                "solicitudes_servicio": self.table_service_requests_legacy,
                "mensajes": self.table_messages_legacy,
                "sesiones": self.table_sessions_legacy,
                "tareas_programadas": self.table_task_queue_legacy
            }
            return legacy_mapping.get(table_type, table_type)

        new_mapping = {
            "clientes": self.table_clientes,
            "profesiones": self.table_profesiones,
            "solicitudes_servicio": self.table_solicitudes_servicio,
            "mensajes": self.table_mensajes,
            "sesiones": self.table_sesiones,
            "tareas_programadas": self.table_tareas_programadas
        }
        return new_mapping.get(table_type, table_type)

settings = Settings()
```

### 2. AI Service Proveedores

#### Archivo: `python-services/ai-service-proveedores/main_proveedores.py`

**Cambio en función de búsqueda de proveedores:**

```python
# ANTES (Línea ~223)
async def supabase_find_or_create_user_provider(
    phone: str, name: Optional[str], city: Optional[str]
) -> Optional[str]:
    if not supabase:
        return None
    try:
        res = (
            supabase.table("users")  # ← TABLA ANTIGUA
            .select("id")
            .eq("phone_number", phone)  # ← CAMPO ANTIGUO
            .limit(1)
            .execute()
        )
        if res.data:
            user_id = res.data[0]["id"]
            # asegurar tipo y datos básicos
            try:
                supabase.table("users").update({  # ← TABLA ANTIGUA
                    "user_type": "provider",
                    "name": name or "Proveedor TinkuBot",
                    "city": city,
                    "status": "active",
                }).eq("id", user_id).execute()
            except Exception as e:
                logger.warning(f"Error updating user status: {e}")
            return user_id
        ins = (
            supabase.table("users")  # ← TABLA ANTIGUA
            .insert({
                "phone_number": phone,  # ← CAMPO ANTIGUO
                "name": name or "Proveedor TinkuBot",
                "user_type": "provider",
                "city": city,
                "status": "active",
            })
            .execute()
        )
        if ins.data:
            return ins.data[0]["id"]
    except Exception as e:
        logger.warning(f"No se pudo crear/buscar provider user {phone}: {e}")
    return None

# DESPUÉS (Nueva implementación)
async def get_or_create_proveedor(
    telefono: str, nombre: Optional[str], ciudad: Optional[str]
) -> Optional[str]:
    if not supabase:
        return None

    table_name = provider_settings.get_table_name("proveedores")
    phone_field = "telefono" if not provider_settings.migration_mode else "phone_number"

    try:
        res = (
            supabase.table(table_name)
            .select("id")
            .eq(phone_field, telefono)
            .limit(1)
            .execute()
        )
        if res.data:
            proveedor_id = res.data[0]["id"]
            # asegurar datos básicos
            try:
                update_data = {
                    "nombre": nombre or "Proveedor TinkuBot",
                    "ciudad": ciudad,
                    "estado": "activo",
                }
                if provider_settings.migration_mode:
                    update_data.update({
                        "user_type": "provider",
                        "name": nombre or "Proveedor TinkuBot",
                        "status": "active"
                    })

                supabase.table(table_name).update(update_data).eq("id", proveedor_id).execute()
            except Exception as e:
                logger.warning(f"Error updating provider status: {e}")
            return proveedor_id

        # Crear nuevo proveedor
        insert_data = {
            phone_field: telefono,
            "nombre": nombre or "Proveedor TinkuBot",
            "ciudad": ciudad,
            "estado": "activo",
        }

        if provider_settings.migration_mode:
            insert_data.update({
                "user_type": "provider",
                "status": "active"
            })

        ins = supabase.table(table_name).insert(insert_data).execute()
        if ins.data:
            return ins.data[0]["id"]
    except Exception as e:
        logger.warning(f"No se pudo crear/buscar proveedor {telefono}: {e}")
    return None
```

**Cambio en función de registro de proveedores:**

```python
# ANTES (Línea ~499)
async def register_provider_in_supabase(
    provider_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    # 1) User provider upsert
    provider_user_id = await supabase_find_or_create_user_provider(
        phone, name, city
    )

    # DESPUÉS (Nueva implementación)
async def register_proveedor_in_supabase(
    proveedor_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    # 1) Proveedor upsert
    proveedor_id = await get_or_create_proveedor(
        telefono, nombre, ciudad
    )
```

**Cambio en búsqueda de proveedores:**

```python
# ANTES (Línea ~361)
async def search_providers_in_supabase(
    profession: str, location: str, radius: float = 10.0
) -> List[Dict[str, Any]]:
    """Buscar proveedores usando las tablas actuales (users, professions, provider_professions, provider_services)."""

    # ... lógica con tablas antiguas ...
    pp = (
        supabase.table("provider_professions")  # ← TABLA ANTIGUA
        .select("provider_id,experience_years")
        .eq("profession_id", prof_id)
        .execute()
    )

# DESPUÉS (Nueva implementación)
async def search_proveedores_in_supabase(
    profesion: str, ubicacion: str, radio: float = 10.0
) -> List[Dict[str, Any]]:
    """Buscar proveedores usando las tablas nuevas (proveedores, profesiones, proveedor_profesiones, servicios_proveedor)."""

    # ... lógica con tablas nuevas ...
    pp = (
        supabase.table("proveedor_profesiones")  # ← TABLA NUEVA
        .select("proveedor_id,anos_experiencia")
        .eq("profesion_id", prof_id)
        .execute()
    )
```

#### Archivo: `python-services/ai-service-proveedores/config_proveedores.py`

```python
# Configuración similar a la de ai-service-clientes
class ProviderSettings:
    # ... configuración existente ...

    migration_mode: bool = os.getenv("MIGRATION_MODE", "false").lower() == "true"

    # Nombres de tablas
    table_proveedores: str = os.getenv("TABLE_PROVEEDORES", "proveedores")
    table_profesiones: str = os.getenv("TABLE_PROFESIONES", "profesiones")
    table_proveedor_profesiones: str = os.getenv("TABLE_PROVEEDOR_PROFESIONES", "proveedor_profesiones")
    table_servicios_proveedor: str = os.getenv("TABLE_SERVICIOS_PROVEEDOR", "servicios_proveedor")

    def get_table_name(self, table_type: str) -> str:
        """Obtener nombre de tabla según modo de migración"""
        if self.migration_mode:
            legacy_mapping = {
                "proveedores": "users",
                "profesiones": "professions",
                "proveedor_profesiones": "provider_professions",
                "servicios_proveedor": "provider_services"
            }
            return legacy_mapping.get(table_type, table_type)

        new_mapping = {
            "proveedores": self.table_proveedores,
            "profesiones": self.table_profesiones,
            "proveedor_profesiones": self.table_proveedor_profesiones,
            "servicios_proveedor": self.table_servicios_proveedor
        }
        return new_mapping.get(table_type, table_type)

provider_settings = ProviderSettings()
```

---

## 🟢 Cambios en Node.js Services

### 1. WhatsApp Service Clientes

#### Archivo: `nodejs-services/whatsapp-service-clientes/SupabaseStore.js`

```javascript
// ANTES (implementación actual)
class SupabaseStore {
    constructor(supabaseUrl, supabaseKey, bucketName = 'wa_sessions') {
        this.supabase = createClient(supabaseUrl, supabaseKey);
        this.bucketName = bucketName;
    }

    async saveSession(sessionId, sessionData) {
        // Guardar sesión con formato antiguo
        const { data, error } = await this.supabase.storage
            .from(this.bucketName)
            .upload(`sessions/${sessionId}.json`, JSON.stringify(sessionData), {
                upsert: true
            });

        if (error) throw error;
        return data;
    }
}

// DESPUÉS (Nueva implementación con soporte de migración)
class SupabaseStore {
    constructor(supabaseUrl, supabaseKey, bucketName = 'wa_sessions') {
        this.supabase = createClient(supabaseUrl, supabaseKey);
        this.bucketName = bucketName;
        this.migrationMode = process.env.MIGRATION_MODE === 'true';
        this.tableMapping = {
            sesiones: this.migrationMode ? 'sessions' : 'sesiones',
            mensajes: this.migrationMode ? 'messages' : 'mensajes',
            clientes: this.migrationMode ? 'customers' : 'clientes'
        };
    }

    async saveSession(sessionId, sessionData) {
        try {
            // Guardar en base de datos además de storage
            const sessionTable = this.tableMapping.sesiones;
            const phoneField = this.migrationMode ? 'phone_number' : 'telefono';

            const sessionPayload = {
                id_sesion: sessionId,
                estado: 'activa',
                datos_sesion: sessionData,
                ultima_actividad: new Date().toISOString(),
                ...(sessionData.phoneNumber && { [phoneField]: sessionData.phoneNumber })
            };

            const { data, error } = await this.supabase
                .from(sessionTable)
                .upsert(sessionPayload)
                .select()
                .single();

            if (error) {
                console.warn('Error guardando en base de datos, usando storage fallback:', error);
                // Fallback a storage original
                return this.saveSessionToStorage(sessionId, sessionData);
            }

            // También guardar en storage para backup
            await this.saveSessionToStorage(sessionId, sessionData);

            return data;
        } catch (error) {
            console.error('Error en saveSession:', error);
            throw error;
        }
    }

    async saveSessionToStorage(sessionId, sessionData) {
        const { data, error } = await this.supabase.storage
            .from(this.bucketName)
            .upload(`sessions/${sessionId}.json`, JSON.stringify(sessionData), {
                upsert: true
            });

        if (error) throw error;
        return data;
    }

    async getSession(sessionId) {
        try {
            const sessionTable = this.tableMapping.sesiones;

            // Intentar obtener de base de datos primero
            const { data, error } = await this.supabase
                .from(sessionTable)
                .select('*')
                .eq('id_sesion', sessionId)
                .single();

            if (data && !error) {
                return data.datos_sesion;
            }

            // Fallback a storage
            return this.getSessionFromStorage(sessionId);
        } catch (error) {
            console.warn('Error obteniendo de base de datos, usando storage fallback:', error);
            return this.getSessionFromStorage(sessionId);
        }
    }

    async getSessionFromStorage(sessionId) {
        const { data, error } = await this.supabase.storage
            .from(this.bucketName)
            .download(`sessions/${sessionId}.json`);

        if (error) throw error;

        const sessionData = await data.text();
        return JSON.parse(sessionData);
    }

    async saveMessage(phoneNumber, message, isBot = false) {
        try {
            const messageTable = this.tableMapping.mensajes;
            const phoneField = this.migrationMode ? 'phone_number' : 'telefono';

            const messagePayload = {
                [phoneField]: phoneNumber,
                tipo_mensaje: 'texto',
                contenido: message,
                estado_procesamiento: 'completado',
                metadata: { is_bot: isBot },
                creado_at: new Date().toISOString()
            };

            const { data, error } = await this.supabase
                .from(messageTable)
                .insert(messagePayload)
                .select()
                .single();

            if (error) {
                console.error('Error guardando mensaje:', error);
                return null;
            }

            return data;
        } catch (error) {
            console.error('Error en saveMessage:', error);
            return null;
        }
    }
}

module.exports = SupabaseStore;
```

#### Archivo: `nodejs-services/whatsapp-service-clientes/index.js`

```javascript
// Actualizar configuración y uso de SupabaseStore
const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_BACKEND_API_KEY;
const supabaseBucket = process.env.SUPABASE_BUCKET_NAME;

// Determinar tabla de clientes según modo de migración
const clientTable = process.env.MIGRATION_MODE === 'true' ? 'customers' : 'clientes';
const phoneField = process.env.MIGRATION_MODE === 'true' ? 'phone_number' : 'telefono';

if (!supabaseUrl || !supabaseKey || !supabaseBucket) {
    console.error('❌ Faltan variables de entorno de Supabase');
    process.exit(1);
}

const supabaseStore = new SupabaseStore(supabaseUrl, supabaseKey, supabaseBucket);

// Actualizar función de guardar cliente si existe
async function saveCustomer(phoneNumber, customerData) {
    try {
        const payload = {
            [phoneField]: phoneNumber,
            nombre_completo: customerData.fullName || customerData.name,
            ciudad: customerData.city,
            estado: 'activo',
            actualizado_at: new Date().toISOString()
        };

        const { data, error } = await supabaseClient
            .from(clientTable)
            .upsert(payload)
            .select()
            .single();

        if (error) {
            console.error('Error guardando cliente:', error);
            return null;
        }

        return data;
    } catch (error) {
        console.error('Error en saveCustomer:', error);
        return null;
    }
}
```

### 2. WhatsApp Service Proveedores

#### Archivo: `nodejs-services/whatsapp-service-proveedores/SupabaseStore.js`

```javascript
// Implementación similar a la de clientes pero para proveedores
class SupabaseStore {
    constructor(supabaseUrl, supabaseKey, bucketName = 'wa_sessions') {
        this.supabase = createClient(supabaseUrl, supabaseKey);
        this.bucketName = bucketName;
        this.migrationMode = process.env.MIGRATION_MODE === 'true';
        this.tableMapping = {
            proveedores: this.migrationMode ? 'users' : 'proveedores',
            sesiones: this.migrationMode ? 'sessions' : 'sesiones',
            mensajes: this.migrationMode ? 'messages' : 'mensajes'
        };
    }

    async saveProvider(providerData) {
        try {
            const providerTable = this.tableMapping.proveedores;
            const phoneField = this.migrationMode ? 'phone_number' : 'telefono';
            const nameField = this.migrationMode ? 'name' : 'nombre';

            const payload = {
                [phoneField]: providerData.phoneNumber,
                [nameField]: providerData.name,
                email: providerData.email,
                ciudad: providerData.city,
                estado: 'activo',
                ...(this.migrationMode && { user_type: 'provider' }),
                actualizado_at: new Date().toISOString()
            };

            const { data, error } = await this.supabase
                .from(providerTable)
                .upsert(payload)
                .select()
                .single();

            if (error) {
                console.error('Error guardando proveedor:', error);
                return null;
            }

            return data;
        } catch (error) {
            console.error('Error en saveProvider:', error);
            return null;
        }
    }

    async getProvider(phoneNumber) {
        try {
            const providerTable = this.tableMapping.proveedores;
            const phoneField = this.migrationMode ? 'phone_number' : 'telefono';

            const { data, error } = await this.supabase
                .from(providerTable)
                .select('*')
                .eq(phoneField, phoneNumber)
                .single();

            if (error) {
                console.error('Error obteniendo proveedor:', error);
                return null;
            }

            return data;
        } catch (error) {
            console.error('Error en getProvider:', error);
            return null;
        }
    }
}

module.exports = SupabaseStore;
```

---

## 🔧 Scripts de Actualización Automatizada

### Script: `scripts/update-code-migration.py`

```python
#!/usr/bin/env python3

# update-code-migration.py - Script para actualizar código automáticamente

import os
import re
import sys
from pathlib import Path

class CodeUpdater:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / "backup_pre_migration"

    def create_backup(self):
        """Crear backup de archivos que serán modificados"""
        print("🔄 Creando backup de archivos...")

        files_to_backup = [
            "python-services/ai-service-clientes/main.py",
            "python-services/ai-service-clientes/config.py",
            "python-services/ai-service-proveedores/main_proveedores.py",
            "python-services/ai-service-proveedores/config_proveedores.py",
            "nodejs-services/whatsapp-service-clientes/SupabaseStore.js",
            "nodejs-services/whatsapp-service-clientes/index.js",
            "nodejs-services/whatsapp-service-proveedores/SupabaseStore.js",
            "nodejs-services/whatsapp-service-proveedores/index.js"
        ]

        self.backup_dir.mkdir(exist_ok=True)

        for file_path in files_to_backup:
            source = self.project_root / file_path
            if source.exists():
                dest = self.backup_dir / file_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
                print(f"✅ Backup creado: {file_path}")
            else:
                print(f"⚠️ Archivo no encontrado: {file_path}")

    def update_python_file(self, file_path, replacements):
        """Actualizar archivo Python con reemplazos específicos"""
        file_path = self.project_root / file_path

        if not file_path.exists():
            print(f"❌ Archivo no encontrado: {file_path}")
            return False

        content = file_path.read_text(encoding='utf-8')
        original_content = content

        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            print(f"✅ Actualizado: {file_path}")
            return True
        else:
            print(f"📝 Sin cambios necesarios: {file_path}")
            return False

    def update_ai_service_clientes(self):
        """Actualizar AI Service Clientes"""
        print("\n🐍 Actualizando AI Service Clientes...")

        replacements = [
            # Reemplazar función get_or_create_customer
            (r'def get_or_create_customer\(', 'def get_or_create_cliente('),
            (r'phone: str,', 'telefono: str,'),
            (r'full_name: Optional\[str\] = None,', 'nombre_completo: Optional[str] = None,'),
            (r'city: Optional\[str\] = None,', 'ciudad: Optional[str] = None,'),

            # Reemplazar referencias a tabla customers
            (r'supabase\.table\("customers"\)', 'supabase.table(settings.get_table_name("clientes"))'),
            (r'\.eq\("phone_number",', '.eq("telefono",'),
            (r'"phone_number": phone,', '"telefono": telefono,'),
            (r'"full_name": full_name', '"nombre_completo": nombre_completo'),

            # Actualizar funciones relacionadas
            (r'def update_customer_city\(', 'def update_cliente_ciudad('),
            (r'customer_id: Optional\[str\]', 'cliente_id: Optional[str]'),

            # Actualizar service_requests
            (r'supabase\.table\("service_requests"\)', 'supabase.table(settings.get_table_name("solicitudes_servicio"))'),
            (r'"phone": phone,', '"telefono": telefono,'),
            (r'"profession": profession,', '"profesion_solicitada": profession,'),
            (r'"location_city": location,', '"ciudad": location,'),
            (r'"suggested_providers": providers,', '"proveedores_sugeridos": providers,'),

            # Actualizar llamadas a funciones
            (r'get_or_create_customer\(phone=', 'get_or_create_cliente(telefono=')
        ]

        self.update_python_file("python-services/ai-service-clientes/main.py", replacements)

    def update_ai_service_proveedores(self):
        """Actualizar AI Service Proveedores"""
        print("\n🐍 Actualizando AI Service Proveedores...")

        replacements = [
            # Reemplazar función principal
            (r'async def supabase_find_or_create_user_provider\(', 'async def get_or_create_proveedor('),
            (r'phone: str,', 'telefono: str,'),
            (r'name: Optional\[str\]', 'nombre: Optional[str]'),
            (r'city: Optional\[str\]', 'ciudad: Optional[str]'),

            # Reemplazar referencias a tabla users
            (r'supabase\.table\("users"\)', 'supabase.table(provider_settings.get_table_name("proveedores"))'),
            (r'\.eq\("phone_number",', '.eq("telefono",'),
            (r'"phone_number": phone,', '"telefono": telefono,'),
            (r'"name": name', '"nombre": nombre'),
            (r'"user_type": "provider"', ''),
            (r'"status": "active"', '"estado": "activo"'),

            # Actualizar tablas relacionadas
            (r'supabase\.table\("provider_professions"\)', 'supabase.table(provider_settings.get_table_name("proveedor_profesiones"))'),
            (r'supabase\.table\("provider_services"\)', 'supabase.table(provider_settings.get_table_name("servicios_proveedor"))'),
            (r'supabase\.table\("professions"\)', 'supabase.table(provider_settings.get_table_name("profesiones"))'),

            # Actualizar funciones de búsqueda
            (r'async def search_providers_in_supabase\(', 'async def search_proveedores_in_supabase('),
            (r'profession: str,', 'profesion: str,'),
            (r'location: str,', 'ubicacion: str,'),
            (r'radius: float = 10.0', 'radio: float = 10.0')
        ]

        self.update_python_file("python-services/ai-service-proveedores/main_proveedores.py", replacements)

    def update_nodejs_services(self):
        """Actualizar servicios Node.js"""
        print("\n🟢 Actualizando servicios Node.js...")

        # Actualizar SupabaseStore de clientes
        self.update_javascript_file(
            "nodejs-services/whatsapp-service-clientes/SupabaseStore.js",
            [
                # Añadir soporte de migración
                (r'constructor\(supabaseUrl, supabaseKey, bucketName = \'wa_sessions\'\) {',
                 'constructor(supabaseUrl, supabaseKey, bucketName = \'wa_sessions\') {\n        this.migrationMode = process.env.MIGRATION_MODE === \'true\';\n        this.tableMapping = {'),
            ]
        )

        # Actualizar índice de clientes
        self.update_javascript_file(
            "nodejs-services/whatsapp-service-clientes/index.js",
            [
                (r'const clientTable = \'customers\';',
                 'const clientTable = process.env.MIGRATION_MODE === \'true\' ? \'customers\' : \'clientes\';'),
            ]
        )

    def update_javascript_file(self, file_path, replacements):
        """Actualizar archivo JavaScript"""
        file_path = self.project_root / file_path

        if not file_path.exists():
            print(f"❌ Archivo no encontrado: {file_path}")
            return False

        content = file_path.read_text(encoding='utf-8')
        original_content = content

        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            print(f"✅ Actualizado: {file_path}")
            return True
        else:
            print(f"📝 Sin cambios necesarios: {file_path}")
            return False

    def run_update(self):
        """Ejecutar actualización completa"""
        print("🚀 Iniciando actualización de código para migración...")

        # Crear backup
        self.create_backup()

        # Actualizar servicios Python
        self.update_ai_service_clientes()
        self.update_ai_service_proveedores()

        # Actualizar servicios Node.js
        self.update_nodejs_services()

        print("\n🎉 Actualización de código completada!")
        print(f"📁 Backup guardado en: {self.backup_dir}")

def main():
    if len(sys.argv) < 2:
        print("Uso: python update-code-migration.py <project_root>")
        sys.exit(1)

    project_root = sys.argv[1]
    updater = CodeUpdater(project_root)
    updater.run_update()

if __name__ == "__main__":
    main()
```

### Script: `scripts/validate-code-changes.py`

```python
#!/usr/bin/env python3

# validate-code-changes.py - Validar cambios en código post-migración

import os
import sys
import ast
from pathlib import Path

class CodeValidator:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.errors = []
        self.warnings = []

    def validate_python_syntax(self, file_path):
        """Validar sintaxis de archivo Python"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            ast.parse(content)
            return True
        except SyntaxError as e:
            self.errors.append(f"Error de sintaxis en {file_path}: {e}")
            return False

    def validate_imports(self, file_path):
        """Validar que los imports sean correctos"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and 'settings' in node.module:
                        # Verificar que settings esté importado correctamente
                        for alias in node.names:
                            if alias.name == 'settings':
                                return True

            self.warnings.append(f"Posible import faltante de settings en {file_path}")
            return False
        except Exception as e:
            self.errors.append(f"Error validando imports en {file_path}: {e}")
            return False

    def validate_table_references(self, file_path):
        """Validar referencias a tablas"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Buscar referencias directas a tablas antiguas
            old_tables = ['customers', 'users', 'service_requests', 'provider_professions']
            issues_found = []

            for table in old_tables:
                pattern = f'supabase.table\("{table}"\)'
                if pattern in content:
                    issues_found.append(table)

            if issues_found:
                self.warnings.append(f"Referencias a tablas antiguas en {file_path}: {', '.join(issues_found)}")
                return False

            return True
        except Exception as e:
            self.errors.append(f"Error validando referencias a tablas en {file_path}: {e}")
            return False

    def validate_python_files(self):
        """Validar todos los archivos Python"""
        print("🔍 Validando archivos Python...")

        python_files = [
            "python-services/ai-service-clientes/main.py",
            "python-services/ai-service-clientes/config.py",
            "python-services/ai-service-proveedores/main_proveedores.py",
            "python-services/ai-service-proveedores/config_proveedores.py"
        ]

        for file_path in python_files:
            full_path = self.project_root / file_path

            if not full_path.exists():
                self.warnings.append(f"Archivo no encontrado: {file_path}")
                continue

            print(f"  📝 Validando {file_path}")

            # Validar sintaxis
            if not self.validate_python_syntax(full_path):
                continue

            # Validar imports
            self.validate_imports(full_path)

            # Validar referencias a tablas
            self.validate_table_references(full_path)

    def validate_javascript_files(self):
        """Validar archivos JavaScript"""
        print("\n🔍 Validando archivos JavaScript...")

        js_files = [
            "nodejs-services/whatsapp-service-clientes/SupabaseStore.js",
            "nodejs-services/whatsapp-service-clientes/index.js",
            "nodejs-services/whatsapp-service-proveedores/SupabaseStore.js"
        ]

        for file_path in js_files:
            full_path = self.project_root / file_path

            if not full_path.exists():
                self.warnings.append(f"Archivo no encontrado: {file_path}")
                continue

            print(f"  📝 Validando {file_path}")

            # Validar sintaxis básica de JavaScript
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Verificar sintaxis básica
                if content.count('{') != content.count('}'):
                    self.errors.append(f"Error de llaves desbalanceadas en {file_path}")

                if content.count('(') != content.count(')'):
                    self.errors.append(f"Error de paréntesis desbalanceados en {file_path}")

            except Exception as e:
                self.errors.append(f"Error validando {file_path}: {e}")

    def validate_configuration(self):
        """Validar archivos de configuración"""
        print("\n🔍 Validando configuración...")

        env_files = ['.env', '.env.example', 'docker-compose.yml']

        for env_file in env_files:
            full_path = self.project_root / env_file

            if full_path.exists():
                print(f"  📝 Validando {env_file}")

                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Verificar variables de migración
                if 'MIGRATION_MODE' not in content and env_file == '.env.example':
                    self.warnings.append(f"Variable MIGRATION_MODE no encontrada en {env_file}")

    def run_validation(self):
        """Ejecutar validación completa"""
        print("🔍 Iniciando validación de cambios post-migración...")

        self.validate_python_files()
        self.validate_javascript_files()
        self.validate_configuration()

        # Reporte de resultados
        print("\n📊 Resultados de validación:")

        if self.errors:
            print(f"\n❌ Errores encontrados ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings:
            print(f"\n⚠️ Advertencias ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ No se encontraron problemas. ¡Validación exitosa!")
        elif not self.errors:
            print("\n⚠️ Se encontraron advertencias pero no errores críticos.")
        else:
            print("\n❌ Se encontraron errores críticos que deben ser corregidos.")
            return False

        return True

def main():
    if len(sys.argv) < 2:
        print("Uso: python validate-code-changes.py <project_root>")
        sys.exit(1)

    project_root = sys.argv[1]
    validator = CodeValidator(project_root)
    success = validator.run_validation()

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
```

---

## 📋 Testing de Cambios

### Script: `scripts/test-migration-changes.py`

```python
#!/usr/bin/env python3

# test-migration-changes.py - Testing completo de cambios de migración

import os
import sys
import asyncio
import httpx
from pathlib import Path

class MigrationTester:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.test_results = []

    async def test_ai_service_clientes(self):
        """Testing AI Service Clientes"""
        print("🧪 Testing AI Service Clientes...")

        try:
            async with httpx.AsyncClient() as client:
                # Test health check
                response = await client.get("http://localhost:5001/health", timeout=10)
                if response.status_code == 200:
                    self.test_results.append("✅ AI Service Clientes: Health check OK")
                else:
                    self.test_results.append(f"❌ AI Service Clientes: Health check failed ({response.status_code})")

                # Test procesamiento de mensaje
                test_payload = {
                    "message": "Hola, necesito un plomero en Quito",
                    "context": {"phone": "+593999999999"}
                }

                response = await client.post("http://localhost:5001/process-message", json=test_payload, timeout=30)
                if response.status_code == 200:
                    self.test_results.append("✅ AI Service Clientes: Procesamiento de mensaje OK")
                else:
                    self.test_results.append(f"❌ AI Service Clientes: Procesamiento fallido ({response.status_code})")

        except Exception as e:
            self.test_results.append(f"❌ AI Service Clientes: Error de conexión - {e}")

    async def test_ai_service_proveedores(self):
        """Testing AI Service Proveedores"""
        print("🧪 Testing AI Service Proveedores...")

        try:
            async with httpx.AsyncClient() as client:
                # Test health check
                response = await client.get("http://localhost:5002/health", timeout=10)
                if response.status_code == 200:
                    self.test_results.append("✅ AI Service Proveedores: Health check OK")
                else:
                    self.test_results.append(f"❌ AI Service Proveedores: Health check failed ({response.status_code})")

                # Test búsqueda de proveedores
                search_payload = {
                    "profession": "plomero",
                    "location": "Quito",
                    "radius": 10.0
                }

                response = await client.post("http://localhost:5002/search-providers", json=search_payload, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if "providers" in data:
                        self.test_results.append("✅ AI Service Proveedores: Búsqueda de proveedores OK")
                    else:
                        self.test_results.append("❌ AI Service Proveedores: Respuesta de búsqueda inválida")
                else:
                    self.test_results.append(f"❌ AI Service Proveedores: Búsqueda fallida ({response.status_code})")

        except Exception as e:
            self.test_results.append(f"❌ AI Service Proveedores: Error de conexión - {e}")

    async def test_whatsapp_services(self):
        """Testing WhatsApp Services"""
        print("🧪 Testing WhatsApp Services...")

        try:
            async with httpx.AsyncClient() as client:
                # Test WhatsApp Clientes
                response = await client.get("http://localhost:7001/health", timeout=10)
                if response.status_code == 200:
                    self.test_results.append("✅ WhatsApp Clientes: Health check OK")
                else:
                    self.test_results.append(f"❌ WhatsApp Clientes: Health check failed ({response.status_code})")

                # Test WhatsApp Proveedores
                response = await client.get("http://localhost:7002/health", timeout=10)
                if response.status_code == 200:
                    self.test_results.append("✅ WhatsApp Proveedores: Health check OK")
                else:
                    self.test_results.append(f"❌ WhatsApp Proveedores: Health check failed ({response.status_code})")

        except Exception as e:
            self.test_results.append(f"❌ WhatsApp Services: Error de conexión - {e}")

    def test_database_connectivity(self):
        """Testing conectividad a base de datos"""
        print("🧪 Testing conectividad a base de datos...")

        try:
            # Importar y probar configuración
            sys.path.append(str(self.project_root / "python-services" / "ai-service-clientes"))
            from config import settings

            # Verificar variables de entorno
            if settings.migration_mode is not None:
                self.test_results.append("✅ Configuración: MIGRATION_MODE configurada")
            else:
                self.test_results.append("❌ Configuración: MIGRATION_MODE no configurada")

            # Verificar nombres de tablas
            expected_tables = ["clientes", "proveedores", "profesiones", "solicitudes_servicio"]
            for table in expected_tables:
                table_name = settings.get_table_name(table)
                if table_name:
                    self.test_results.append(f"✅ Configuración: Tabla {table} -> {table_name}")
                else:
                    self.test_results.append(f"❌ Configuración: Tabla {table} no configurada")

        except Exception as e:
            self.test_results.append(f"❌ Configuración: Error - {e}")

    async def run_tests(self):
        """Ejecutar todos los tests"""
        print("🚀 Iniciando testing de cambios de migración...")

        # Test de configuración
        self.test_database_connectivity()

        # Tests de servicios
        await self.test_ai_service_clientes()
        await self.test_ai_service_proveedores()
        await self.test_whatsapp_services()

        # Reporte de resultados
        print("\n📊 Resultados de testing:")

        passed = 0
        failed = 0

        for result in self.test_results:
            print(f"  {result}")
            if result.startswith("✅"):
                passed += 1
            else:
                failed += 1

        print(f"\n📈 Resumen: {passed} pasaron, {failed} fallaron")

        if failed == 0:
            print("🎉 Todos los tests pasaron exitosamente!")
            return True
        else:
            print("⚠️ Algunos tests fallaron. Revisar los errores.")
            return False

def main():
    if len(sys.argv) < 2:
        print("Uso: python test-migration-changes.py <project_root>")
        sys.exit(1)

    project_root = sys.argv[1]
    tester = MigrationTester(project_root)

    # Ejecutar tests asíncronos
    success = asyncio.run(tester.run_tests())

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
```

---

## 📋 Checklist de Actualización de Código

### Pre-Actualización
- [ ] Backup completo del código fuente
- [ ] Scripts de actualización desarrollados
- [ ] Tests de validación creados
- [ ] Equipo notificado de cambios

### Durante Actualización
- [ ] AI Service Clientes actualizado
- [ ] AI Service Proveedores actualizado
- [ ] WhatsApp Services actualizados
- [ ] Configuración modificada
- [ ] Validación de sintaxis completada

### Post-Actualización
- [ ] Todos los servicios funcionando
- [ ] Tests de integración pasando
- [ ] Logs sin errores críticos
- [ ] Documentación actualizada
- [ ] Equipo capacitado

---

## 🚨 Troubleshooting

### Problemas Comunes en Python

1. **Error de importación de settings**
   ```python
   # Solución: Asegurarse que el import esté al principio del archivo
   from config import settings
   ```

2. **Error de sintaxis post-migración**
   ```bash
   # Validar sintaxis
   python -m py_compile main.py
   ```

3. **Error en nombres de tabla**
   ```python
   # Depurar nombres de tabla
   print(f"Tabla actual: {settings.get_table_name('clientes')}")
   ```

### Problemas Comunes en Node.js

1. **Error de sintaxis JavaScript**
   ```bash
   # Validar con Node.js
   node -c SupabaseStore.js
   ```

2. **Error en variables de entorno**
   ```bash
   # Verificar variables cargadas
   echo $MIGRATION_MODE
   ```

3. **Error de conexión a Supabase**
   ```javascript
   // Depurar conexión
   console.log('Supabase URL:', process.env.SUPABASE_URL);
   ```

---

## 📞 Soporte

Para problemas durante la actualización de código:

- **Documentación técnica**: `docs/guias/migracion-datos.md`
- **Scripts de actualización**: `scripts/update-code-migration.py`
- **Scripts de validación**: `scripts/validate-code-changes.py`
- **Testing**: `scripts/test-migration-changes.py`

**Importante**: Realizar siempre pruebas en ambiente de staging antes de aplicar cambios en producción.