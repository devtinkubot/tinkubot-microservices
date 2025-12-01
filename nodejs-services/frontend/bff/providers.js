const axios = require('axios');
const mqtt = require('mqtt');

const toPositiveInt = value => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
};

const requestTimeoutMs =
  toPositiveInt(process.env.PROVIDERS_SERVICE_TIMEOUT_MS) ?? 5000;
const pendingLimit = toPositiveInt(process.env.PROVIDERS_PENDING_LIMIT) ?? 100;

const providerHost =
  process.env.PROVIDERS_SERVICE_HOST ||
  'ai-proveedores' || // fallback a servicio python
  'providers-service';
const providerPort =
  toPositiveInt(process.env.PROVIDERS_SERVICE_PORT) ||
  toPositiveInt(process.env.PROVEEDORES_SERVER_PORT) ||
  8002;
const providerBaseUrl =
  process.env.PROVIDERS_SERVICE_URL ||
  `http://${providerHost}:${providerPort}`;

const supabaseUrl = (process.env.SUPABASE_URL || '').trim();
const supabaseServiceKey = (
  process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_BACKEND_API_KEY || ''
).trim();
const supabaseProvidersTable =
  (process.env.SUPABASE_PROVIDERS_TABLE || 'providers').trim();
const supabaseProvidersBucket = (
  process.env.SUPABASE_PROVIDERS_BUCKET || 'tinkubot-providers'
).trim();

const supabaseRestBaseUrl = supabaseUrl
  ? `${supabaseUrl.replace(/\/$/, '')}/rest/v1`
  : null;

const bucketPattern = supabaseProvidersBucket.replace(
  /[.*+?^${}()|[\]\\]/g,
  '\\$&'
);

const generarUrlFirmadaSupabase = filePath => {
  if (!filePath) return null;
  const trimmed = filePath.trim();
  if (!trimmed) return null;

  if (
    trimmed.startsWith('/admin/providers/image/') ||
    trimmed.includes('apikey=')
  ) {
    return trimmed;
  }

  const [pathWithoutQuery] = trimmed.split('?');
  let storagePath = null;

  if (
    bucketPattern &&
    pathWithoutQuery.includes(`/storage/v1/object/${supabaseProvidersBucket}/`)
  ) {
    const match = pathWithoutQuery.match(
      new RegExp(`/storage/v1/object/${bucketPattern}/(.+)`)
    );
    if (match && match[1]) {
      storagePath = match[1];
    }
  } else if (bucketPattern && pathWithoutQuery.includes('/object/')) {
    const match = pathWithoutQuery.match(
      new RegExp(`/object/(?:public/)?${bucketPattern}/(.+)`)
    );
    if (match && match[1]) {
      storagePath = match[1];
    }
  }

  if (!storagePath && !pathWithoutQuery.includes('://')) {
    storagePath = pathWithoutQuery.replace(/^\/+/, '');
  }

  if (storagePath) {
    const sanitizedSegments = storagePath
      .split('/')
      .filter(segment => segment && segment !== '.' && segment !== '..');
    const sanitizedPath = sanitizedSegments.join('/');
    if (sanitizedPath) {
      return `/admin/providers/image/${sanitizedPath}`;
    }
  }

  return trimmed;
};

const supabaseClient =
  supabaseRestBaseUrl && supabaseServiceKey
    ? axios.create({
        baseURL: supabaseRestBaseUrl,
        timeout: requestTimeoutMs,
        headers: {
          apikey: supabaseServiceKey,
          Authorization: `Bearer ${supabaseServiceKey}`
        }
      })
    : null;

const providerServiceClient =
  supabaseClient === null
    ? axios.create({
        baseURL: providerBaseUrl,
        timeout: requestTimeoutMs
      })
    : null;

if (supabaseClient) {
  console.warn(
    `📦 Provider data source: Supabase REST (${supabaseProvidersTable})`
  );
} else {
  console.warn(`📦 Provider service base URL: ${providerBaseUrl}`);
}

const limpiarTexto = valor => {
  if (typeof valor === 'string') {
    const trimmed = valor.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  }
  return undefined;
};

const extraerUrlDocumento = valor => {
  if (!valor) return undefined;
  if (typeof valor === 'string') {
    return limpiarTexto(valor);
  }
  if (typeof valor !== 'object') {
    return undefined;
  }

  const recopilar = origen => {
    if (!origen || typeof origen !== 'object') return undefined;
    const claves = [
      'publicUrl',
      'public_url',
      'signedUrl',
      'signed_url',
      'url',
      'href'
    ];
    for (const clave of claves) {
      const candidato = origen[clave];
      if (typeof candidato === 'string') {
        const limpio = candidato.trim();
        if (limpio.length > 0) {
          return limpio;
        }
      }
    }
    const path = origen.path || origen.filePath;
    if (typeof path === 'string' && path.trim().length > 0) {
      return path.trim();
    }
    return undefined;
  };

  return recopilar(valor) || recopilar(valor.data);
};

// --- MQTT para eventos de aprobación ---
const mqttHost = process.env.MQTT_HOST || 'mosquitto';
const mqttPort = toPositiveInt(process.env.MQTT_PORT) || 1883;
const mqttUser = process.env.MQTT_USUARIO || process.env.MQTT_USER;
const mqttPassword = process.env.MQTT_PASSWORD || process.env.MQTT_PASS;
const mqttTopicProviderApproved =
  process.env.MQTT_TEMA_PROVEEDOR_APROBADO || 'providers/approved';

const mqttOptions = {};
if (mqttUser && mqttPassword) {
  mqttOptions.username = mqttUser;
  mqttOptions.password = mqttPassword;
}

let mqttClient = null;
const initMqttClient = () => {
  try {
    const url = `mqtt://${mqttHost}:${mqttPort}`;
    mqttClient = mqtt.connect(url, mqttOptions);
    mqttClient.on('connect', () => {
      console.warn(
        `📡 MQTT conectado (${url}) tópico aprobación=${mqttTopicProviderApproved}`
      );
    });
    mqttClient.on('error', err => {
      console.error('❌ Error MQTT (bff):', err?.message || err);
    });
  } catch (err) {
    console.error('❌ No se pudo inicializar MQTT en BFF:', err?.message || err);
  }
};

const publishProviderApproved = payload => {
  if (!mqttClient || !mqttClient.connected) return false;
  try {
    const body = JSON.stringify({
      approved_at: new Date().toISOString(),
      ...payload
    });
    mqttClient.publish(mqttTopicProviderApproved, body);
    return true;
  } catch (err) {
    console.error(
      '❌ No se pudo publicar provider approved via MQTT:',
      err?.message || err
    );
    return false;
  }
};

initMqttClient();

const prepararUrlDocumento = (...valores) => {
  for (const valor of valores) {
    const candidato = extraerUrlDocumento(valor);
    if (candidato) {
      return generarUrlFirmadaSupabase(candidato);
    }
  }
  return null;
};

const normalizarEstadoProveedor = registro => {
  const estado = limpiarTexto(
    registro?.verification_status || registro?.status
  );
  if (estado === 'approved' || estado === 'rejected' || estado === 'pending') {
    return estado;
  }
  return registro?.verified ? 'approved' : 'pending';
};

const normalizarProveedorSupabase = registro => {
  const nombre =
    limpiarTexto(registro?.full_name) ||
    limpiarTexto(registro?.name) ||
    'Proveedor sin nombre';
  const businessName =
    limpiarTexto(registro?.business_name) ||
    limpiarTexto(registro?.profession) ||
    null;
  const contact =
    limpiarTexto(registro?.contact_name) || nombre || 'Contacto no definido';
  const contactEmail =
    limpiarTexto(registro?.contact_email) || limpiarTexto(registro?.email) || null;
  const contactPhone =
    limpiarTexto(registro?.contact_phone) || limpiarTexto(registro?.phone) || null;
  const phone = limpiarTexto(registro?.phone) || null;
  const email = limpiarTexto(registro?.email) || null;
  const ciudad = limpiarTexto(registro?.city) || null;
  const provincia = limpiarTexto(registro?.province) || null;
  const profession = limpiarTexto(registro?.profession) || null;
  const servicesRaw = limpiarTexto(registro?.services) || null;
  const servicesList = Array.isArray(registro?.services_list)
    ? registro.services_list.filter(item => typeof item === 'string' && item.trim().length > 0)
    : servicesRaw
        ? servicesRaw.split('|').map(item => item.trim()).filter(item => item.length > 0)
        : [];
  const experienceYears =
    typeof registro?.experience_years === 'number'
      ? registro.experience_years
      : Number.isFinite(Number(registro?.experience_years))
        ? Number(registro?.experience_years)
        : null;
  const socialMediaUrl =
    limpiarTexto(registro?.social_media_url) ||
    limpiarTexto(registro?.social_media_link) ||
    null;
  const socialMediaType =
    limpiarTexto(registro?.social_media_type) ||
    limpiarTexto(registro?.social_media_platform) ||
    null;
  const hasConsent =
    typeof registro?.has_consent === 'boolean' ? registro.has_consent : null;
  const rating =
    typeof registro?.rating === 'number'
      ? registro.rating
      : Number.isFinite(Number(registro?.rating))
        ? Number(registro?.rating)
        : null;
  const registeredAt =
    registro?.created_at ||
    registro?.registered_at ||
    registro?.inserted_at ||
    new Date().toISOString();
  const notes =
    limpiarTexto(registro?.verification_notes) ||
    limpiarTexto(registro?.notes) ||
    null;
  const dniFrontPhotoUrl = prepararUrlDocumento(
    registro?.dni_front_photo_url,
    registro?.dni_front_url,
    registro?.documents?.dni_front
  );
  const dniBackPhotoUrl = prepararUrlDocumento(
    registro?.dni_back_photo_url,
    registro?.dni_back_url,
    registro?.documents?.dni_back
  );
  const facePhotoUrl = prepararUrlDocumento(
    registro?.face_photo_url,
    registro?.selfie_url,
    registro?.documents?.face
  );
  const verificationReviewer =
    limpiarTexto(registro?.verification_reviewer) || null;
  const verificationReviewedAt = registro?.verification_reviewed_at || null;

  return {
    id: registro?.id,
    name: nombre,
    businessName,
    contact,
    contactEmail,
    contactPhone,
    registeredAt,
    status: normalizarEstadoProveedor(registro),
    notes,
    phone,
    email,
    city: ciudad,
    province: provincia,
    profession,
    servicesRaw,
    servicesList,
    experienceYears,
    socialMediaUrl,
    socialMediaType,
    hasConsent,
    rating,
    documents: {
      dniFront: dniFrontPhotoUrl,
      dniBack: dniBackPhotoUrl,
      face: facePhotoUrl
    },
    verificationReviewer,
    verificationReviewedAt
  };
};

const normalizarListaProveedores = payload => {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && Array.isArray(payload.providers)) {
    return payload.providers;
  }
  return [];
};

const gestionarErrorAxios = error => {
  const status = error.response?.status ?? 500;
  const data =
    error.response?.data ??
    (error.message ? { error: error.message } : { error: 'Error desconocido' });

  return {
    status,
    data
  };
};

const construirRutaSupabasePendientes = (incluirEstado = true) => {
  const parametrosBase = [
    `limit=${pendingLimit}`,
    `order=created_at.desc`,
    'select=*'
  ];

  if (incluirEstado) {
    const condicion = encodeURIComponent(
      '(verification_status.is.null,verification_status.eq.pending)'
    );
    parametrosBase.push(`or=${condicion}`);
  }

  parametrosBase.push('verified=eq.false');

  return `${supabaseProvidersTable}?${parametrosBase.join('&')}`;
};

const obtenerProveedoresPendientesSupabase = async () => {
  if (!supabaseClient) {
    return [];
  }

  try {
    const ruta = construirRutaSupabasePendientes(true);
    const response = await supabaseClient.get(ruta, {
      headers: {
        Accept: 'application/json'
      }
    });
    return Array.isArray(response.data)
      ? response.data.map(normalizarProveedorSupabase)
      : normalizarListaProveedores(response.data).map(normalizarProveedorSupabase);
  } catch (error) {
    if (error.response?.status === 400) {
      // Columna verification_status podría no existir; reintentar sin filtro.
      const rutaFallback = construirRutaSupabasePendientes(false);
      const response = await supabaseClient.get(rutaFallback, {
        headers: {
          Accept: 'application/json'
        }
      });
      return Array.isArray(response.data)
        ? response.data.map(normalizarProveedorSupabase)
        : normalizarListaProveedores(response.data).map(
            normalizarProveedorSupabase
          );
    }
    throw error;
  }
};

const construirRutaSupabasePorId = providerId => {
  const encodedId = encodeURIComponent(providerId);
  return `${supabaseProvidersTable}?id=eq.${encodedId}`;
};

const intentarActualizacionSupabase = async (
  providerId,
  payloadPrincipal,
  payloadFallback
) => {
  if (!supabaseClient) {
    return null;
  }
  const ruta = construirRutaSupabasePorId(providerId);
  try {
    const response = await supabaseClient.patch(ruta, payloadPrincipal, {
      headers: {
        Prefer: 'return=representation',
        'Content-Type': 'application/json',
        Accept: 'application/json'
      }
    });
    return response.data;
  } catch (error) {
    if (
      error.response?.status === 400 &&
      payloadFallback &&
      Object.keys(payloadFallback).length > 0
    ) {
      const response = await supabaseClient.patch(ruta, payloadFallback, {
        headers: {
          Prefer: 'return=representation',
          'Content-Type': 'application/json',
          Accept: 'application/json'
        }
      });
      return response.data;
    }
    throw error;
  }
};

async function obtenerProveedoresPendientes() {
  try {
    if (supabaseClient) {
      return await obtenerProveedoresPendientesSupabase();
    }

    const response = await providerServiceClient.get('/providers', {
      params: {
        status: 'pending'
      }
    });

    return normalizarListaProveedores(response.data);
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

const construirRespuestaAccion = (providerId, estadoFinal, mensaje, registro) => {
  const updatedAt =
    registro?.updated_at ||
    registro?.verification_reviewed_at ||
    new Date().toISOString();

  return {
    providerId,
    status: estadoFinal,
    updatedAt,
    message: mensaje
  };
};

async function aprobarProveedor(providerId, payload = {}) {
  try {
    if (supabaseClient) {
      const timestamp = new Date().toISOString();
      const payloadPrincipal = {
        verified: true,
        verification_status: 'approved',
        verification_reviewed_at: timestamp,
        updated_at: timestamp
      };
      if (payload.reviewer) {
        payloadPrincipal.verification_reviewer = payload.reviewer;
      }
      if (payload.notes) {
        payloadPrincipal.verification_notes = payload.notes;
      }

      const datosActualizados = await intentarActualizacionSupabase(
        providerId,
        payloadPrincipal,
        { verified: true, updated_at: timestamp }
      );

      const registro =
        Array.isArray(datosActualizados) && datosActualizados.length > 0
          ? datosActualizados[0]
          : null;

      const mensaje =
        payload.notes && payload.notes.length > 0
          ? 'Proveedor aprobado con observaciones.'
          : 'Proveedor aprobado correctamente.';

      // Publicar evento de aprobación por MQTT para que wa-proveedores envíe el WhatsApp
      publishProviderApproved({
        provider_id: providerId,
        phone: registro?.phone,
        full_name: registro?.full_name,
      });

      return construirRespuestaAccion(providerId, 'approved', mensaje, registro);
    }

    const response = await providerServiceClient.post(
      `/providers/${providerId}/approve`,
      payload
    );
    const respData =
      response.data ?? {
        providerId,
        status: 'approved',
        message: 'Proveedor aprobado correctamente.'
      };

    publishProviderApproved({
      provider_id: providerId,
      phone: respData.phone,
      full_name: respData.full_name,
    });

    return respData;
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function rechazarProveedor(providerId, payload = {}) {
  try {
    if (supabaseClient) {
      const timestamp = new Date().toISOString();
      const payloadPrincipal = {
        verified: false,
        verification_status: 'rejected',
        verification_reviewed_at: timestamp,
        updated_at: timestamp
      };
      if (payload.reviewer) {
        payloadPrincipal.verification_reviewer = payload.reviewer;
      }
      if (payload.notes) {
        payloadPrincipal.verification_notes = payload.notes;
      }

      const datosActualizados = await intentarActualizacionSupabase(
        providerId,
        payloadPrincipal,
        { verified: false, updated_at: timestamp }
      );

      const registro =
        Array.isArray(datosActualizados) && datosActualizados.length > 0
          ? datosActualizados[0]
          : null;

      const mensaje =
        payload.notes && payload.notes.length > 0
          ? 'Proveedor rechazado con observaciones.'
          : 'Proveedor rechazado correctamente.';

      return construirRespuestaAccion(providerId, 'rejected', mensaje, registro);
    }

    const response = await providerServiceClient.post(
      `/providers/${providerId}/reject`,
      payload
    );
    return (
      response.data ?? {
        providerId,
        status: 'rejected',
        message: 'Proveedor rechazado correctamente.'
      }
    );
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

module.exports = {
  obtenerProveedoresPendientes,
  aprobarProveedor,
  rechazarProveedor
};
