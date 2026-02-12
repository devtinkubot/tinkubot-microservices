const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

const toPositiveInt = value => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
};

const requestTimeoutMs =
  toPositiveInt(process.env.PROVIDERS_SERVICE_TIMEOUT_MS) ?? 5000;
const pendingLimit = toPositiveInt(process.env.PROVIDERS_PENDING_LIMIT) ?? 100;
const monetizationLimit =
  toPositiveInt(process.env.MONETIZATION_PROVIDER_LIMIT) ?? 100;

const supabaseUrl = (process.env.SUPABASE_URL || '').trim();
const supabaseServiceKey = (process.env.SUPABASE_SERVICE_KEY || '').trim();
const supabaseProvidersTable =
  (process.env.SUPABASE_PROVIDERS_TABLE || 'providers').trim();
const supabaseProvidersBucket = (
  process.env.SUPABASE_PROVIDERS_BUCKET || 'tinkubot-providers'
).trim();
const aiProveedoresUrl = (process.env.AI_PROVEEDORES_URL || '').trim();
const aiProveedoresInternalToken = (
  process.env.AI_PROVEEDORES_INTERNAL_TOKEN || ''
).trim();

const supabaseRestBaseUrl = supabaseUrl
  ? `${supabaseUrl.replace(/\/$/, '')}/rest/v1`
  : null;

const WA_GATEWAY_URL = process.env.WA_GATEWAY_URL || 'http://wa-gateway:7000';
const WA_GATEWAY_SEND_PATH = process.env.WA_GATEWAY_SEND_PATH || '/send';
const PROVEEDORES_ACCOUNT_ID =
  process.env.PROVEEDORES_INSTANCE_ID || 'bot-proveedores';

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

const withRequestId = (config, requestId) => {
  if (!config.headers) config.headers = {};
  config.headers['x-request-id'] = requestId;
  return config;
};

const invalidarCacheProveedor = async (phone, requestId = null) => {
  if (!aiProveedoresUrl || !phone) return;

  const baseUrl = aiProveedoresUrl.replace(/\/$/, '');
  const headers = {};
  if (requestId) headers['x-request-id'] = requestId;
  if (aiProveedoresInternalToken) {
    headers['x-internal-token'] = aiProveedoresInternalToken;
  }

  try {
    await axiosClient.post(
      `${baseUrl}/admin/invalidate-provider-cache`,
      { phone },
      { headers }
    );
  } catch (error) {
    console.warn('⚠️ No se pudo invalidar cache de proveedor:', error?.message || error);
  }
};

console.warn(
  `📦 Provider data source: Supabase REST (${supabaseProvidersTable})`
);
console.warn(`📡 WA-Gateway URL: ${WA_GATEWAY_URL}`);

const limpiarTexto = valor => {
  if (typeof valor === 'string') {
    const trimmed = valor.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  }
  return undefined;
};

const timestampIncluyeZona = valor =>
  /(?:[zZ]|[+-]\d{2}(?::?\d{2})?)$/.test(valor);

const normalizarTimestampComoUtc = valor => {
  const texto = limpiarTexto(valor);
  if (!texto) return undefined;
  return timestampIncluyeZona(texto) ? texto : `${texto}Z`;
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

const construirMensajeAprobacion = nombre => {
  const safeName = limpiarTexto(nombre);
  if (safeName) {
    return `✅ Hola *${safeName}*, tu perfil en TinkuBot fue aprobado. Ya puedes responder solicitudes cuando te escribamos.`;
  }
  return '✅ Tu perfil en TinkuBot fue aprobado. Ya puedes responder solicitudes cuando te escribamos.';
};

const construirMensajeRechazo = (nombre, motivo) => {
  const safeName = limpiarTexto(nombre);
  const safeReason = limpiarTexto(motivo);
  if (safeName && safeReason) {
    return `❌ Hola ${safeName}, tu perfil en TinkuBot fue rechazado. Motivo: ${safeReason}. Puedes corregir tus datos y volver a postular.`;
  }
  if (safeName) {
    return `❌ Hola ${safeName}, tu perfil en TinkuBot fue rechazado. Puedes corregir tus datos y volver a postular.`;
  }
  if (safeReason) {
    return `❌ Tu perfil en TinkuBot fue rechazado. Motivo: ${safeReason}. Puedes corregir tus datos y volver a postular.`;
  }
  return '❌ Tu perfil en TinkuBot fue rechazado. Puedes corregir tus datos y volver a postular.';
};

const construirMensajeEntrevista = nombre => {
  const safeName = limpiarTexto(nombre);
  if (safeName) {
    return `Hola ${safeName}, para continuar con tu registro necesitamos una breve entrevista de validación. Responde a este mensaje para coordinar.`;
  }
  return 'Para continuar con tu registro necesitamos una breve entrevista de validación. Responde a este mensaje para coordinar.';
};

const enviarNotificacionWhatsapp = async ({ to, message, requestId }) => {
  if (!limpiarTexto(to)) {
    console.warn('⚠️ Notificación WhatsApp omitida: teléfono vacío');
    return false;
  }
  if (!limpiarTexto(message)) {
    console.warn('⚠️ Notificación WhatsApp omitida: mensaje vacío');
    return false;
  }

  try {
    const payload = {
      account_id: PROVEEDORES_ACCOUNT_ID,
      to,
      message
    };
    const headers = {};
    if (requestId) headers['x-request-id'] = requestId;
    await axios.post(`${WA_GATEWAY_URL}${WA_GATEWAY_SEND_PATH}`, payload, {
      timeout: requestTimeoutMs,
      headers
    });
    return true;
  } catch (err) {
    console.error(
      '❌ Error enviando notificación WhatsApp via wa-gateway:',
      err?.response?.data || err?.message || err
    );
    return false;
  }
};


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
  // Si la tabla ya no tiene verification_status, derivar desde verified/status
  const estadoCrudo = limpiarTexto(registro?.status);
  const estado = estadoCrudo ? estadoCrudo.toLowerCase() : '';

  if (['approved', 'aprobado', 'ok'].includes(estado)) {
    return 'approved';
  }
  if (['rejected', 'rechazado', 'denied'].includes(estado)) {
    return 'rejected';
  }
  if (['needs_info', 'falta_info', 'faltainfo'].includes(estado)) {
    return 'interview_required';
  }
  if (['interview_required', 'entrevista', 'auditoria'].includes(estado)) {
    return 'interview_required';
  }
  if (['pending', 'pendiente'].includes(estado)) {
    return 'pending';
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
  const servicesFromRelation = Array.isArray(registro?.provider_services)
    ? registro.provider_services
        .filter(item => item && typeof item.service_name === 'string')
        .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0))
        .map(item => item.service_name.trim())
        .filter(item => item.length > 0)
    : [];
  const servicesRaw =
    limpiarTexto(registro?.services) ||
    (servicesFromRelation.length > 0 ? servicesFromRelation.join(' | ') : null);
  const servicesList =
    servicesFromRelation.length > 0
      ? servicesFromRelation
      : Array.isArray(registro?.services_list)
        ? registro.services_list.filter(
            item => typeof item === 'string' && item.trim().length > 0
          )
        : servicesRaw
          ? servicesRaw
              .split('|')
              .map(item => item.trim())
              .filter(item => item.length > 0)
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
    normalizarTimestampComoUtc(registro?.created_at) ||
    normalizarTimestampComoUtc(registro?.registered_at) ||
    normalizarTimestampComoUtc(registro?.inserted_at) ||
    new Date().toISOString();
  const notes = limpiarTexto(registro?.notes) || null;
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
    limpiarTexto(registro?.verification_reviewer) ||
    limpiarTexto(registro?.reviewer_name) ||
    null;
  const verificationReviewedAt =
    normalizarTimestampComoUtc(registro?.verification_reviewed_at) ||
    normalizarTimestampComoUtc(registro?.reviewed_at) ||
    null;

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

const normalizarEstadoMonetizacion = value => {
  const estado = limpiarTexto(value)?.toLowerCase();
  if (estado === 'paused_paywall' || estado === 'suspended') {
    return estado;
  }
  return 'active';
};

const toIsoUtc = value => {
  const text = limpiarTexto(value);
  if (!text) return null;
  return timestampIncluyeZona(text) ? text : `${text}Z`;
};

const agruparEventosPorProveedor = eventos => {
  const grouped = new Map();
  for (const item of eventos || []) {
    const providerId = limpiarTexto(item?.provider_id);
    if (!providerId) continue;
    if (!grouped.has(providerId)) {
      grouped.set(providerId, []);
    }
    grouped.get(providerId).push(item);
  }
  return grouped;
};

const agruparFeedbackPorLeadId = feedbackRows => {
  const grouped = new Map();
  for (const item of feedbackRows || []) {
    const leadEventId = limpiarTexto(item?.lead_event_id);
    if (!leadEventId) continue;
    grouped.set(leadEventId, item);
  }
  return grouped;
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
    'select=*,provider_services(service_name,service_name_normalized,display_order)'
  ];

  if (incluirEstado) {
    parametrosBase.push('or=(status.is.null,status.in.(new,pending))');
  }

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
    const lista = Array.isArray(response.data)
      ? response.data.map(normalizarProveedorSupabase)
      : normalizarListaProveedores(response.data).map(normalizarProveedorSupabase);
    return lista;
  } catch (error) {
    if (error.response?.status === 400) {
      // Columna verification_status podría no existir; reintentar sin filtro.
      const rutaFallback = construirRutaSupabasePendientes(false);
      const response = await supabaseClient.get(rutaFallback, {
        headers: {
          Accept: 'application/json'
        }
      });
      const lista = Array.isArray(response.data)
        ? response.data.map(normalizarProveedorSupabase)
        : normalizarListaProveedores(response.data).map(
            normalizarProveedorSupabase
          );
      return lista;
    }
    throw error;
  }
};

const construirRutaSupabasePostRevision = () => {
  const parametrosBase = [
    `limit=${pendingLimit}`,
    `order=created_at.desc`,
    'select=*,provider_services(service_name,service_name_normalized,display_order)',
    'status=in.(interview_required,rejected)'
  ];

  return `${supabaseProvidersTable}?${parametrosBase.join('&')}`;
};

const obtenerProveedoresPostRevisionSupabase = async () => {
  if (!supabaseClient) {
    return [];
  }

  const ruta = construirRutaSupabasePostRevision();
  const response = await supabaseClient.get(ruta, {
    headers: {
      Accept: 'application/json'
    }
  });
  const lista = Array.isArray(response.data)
    ? response.data.map(normalizarProveedorSupabase)
    : normalizarListaProveedores(response.data).map(normalizarProveedorSupabase);
  return lista;
};

const construirRutaSupabasePorId = providerId => {
  const encodedId = encodeURIComponent(providerId);
  return `${supabaseProvidersTable}?id=eq.${encodedId}&select=*,provider_services(service_name,service_name_normalized,display_order)`;
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

async function obtenerProveedoresPendientes(requestId = null) {
  try {
    return await obtenerProveedoresPendientesSupabase();
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerProveedoresNuevos(requestId = null) {
  try {
    return await obtenerProveedoresPendientesSupabase();
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerProveedoresPostRevision(requestId = null) {
  try {
    return await obtenerProveedoresPostRevisionSupabase();
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

const construirRespuestaAccion = (providerId, estadoFinal, mensaje, registro) => {
  const updatedAt = registro?.updated_at || new Date().toISOString();

  return {
    providerId,
    status: estadoFinal,
    updatedAt,
    message: mensaje
  };
};

async function aprobarProveedor(providerId, payload = {}, requestId = null) {
  try {
    const timestamp = new Date().toISOString();
    const payloadPrincipal = {
      verified: true,
      status: 'approved',
      updated_at: timestamp,
      approved_notified_at: timestamp
    };

    const datosActualizados = await intentarActualizacionSupabase(
      providerId,
      payloadPrincipal,
      { verified: true, updated_at: timestamp, approved_notified_at: timestamp }
    );

    const registro =
      Array.isArray(datosActualizados) && datosActualizados.length > 0
        ? datosActualizados[0]
        : null;

    const mensaje = 'Proveedor aprobado correctamente.';

    const approvalMessage = construirMensajeAprobacion(registro?.full_name);
    await enviarNotificacionWhatsapp({
      to: registro?.phone,
      message: approvalMessage,
      requestId
    });

    await invalidarCacheProveedor(registro?.phone, requestId);

    return construirRespuestaAccion(providerId, 'approved', mensaje, registro);
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function rechazarProveedor(providerId, payload = {}, requestId = null) {
  try {
    const timestamp = new Date().toISOString();
    const payloadPrincipal = {
      verified: false,
      status: 'rejected',
      updated_at: timestamp,
      rejected_notified_at: timestamp
    };

    if (limpiarTexto(payload.notes)) {
      payloadPrincipal.notes = payload.notes.trim();
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

    const mensaje = 'Proveedor rechazado correctamente.';

    const rejectionMessage = construirMensajeRechazo(
      registro?.full_name,
      payload.notes
    );
    await enviarNotificacionWhatsapp({
      to: registro?.phone,
      message: rejectionMessage,
      requestId
    });

    return construirRespuestaAccion(providerId, 'rejected', mensaje, registro);
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function revisarProveedor(providerId, payload = {}, requestId = null) {
  try {
    const estadoSolicitado = limpiarTexto(payload.status);
    const estadoFinal =
      estadoSolicitado && ['approved', 'rejected', 'interview_required'].includes(estadoSolicitado)
        ? estadoSolicitado
        : null;

    if (!estadoFinal) {
      return {
        providerId,
        status: 'pending',
        updatedAt: new Date().toISOString(),
        message: 'Selecciona un resultado válido para continuar.'
      };
    }

    const timestamp = new Date().toISOString();
    const payloadBase = {
      updated_at: timestamp,
      status: estadoFinal,
      verified: estadoFinal === 'approved'
    };

    if (estadoFinal === 'approved') {
      payloadBase.approved_notified_at = timestamp;
    } else if (estadoFinal === 'rejected') {
      payloadBase.rejected_notified_at = timestamp;
    }

    if (limpiarTexto(payload.notes)) {
      payloadBase.notes = payload.notes.trim();
    }

    const payloadConRevisor = {
      ...payloadBase,
      verification_reviewer: limpiarTexto(payload.reviewer),
      verification_reviewed_at: timestamp
    };

    const payloadFallback = {
      updated_at: timestamp,
      verified: estadoFinal === 'approved'
    };

    const datosActualizados = await intentarActualizacionSupabase(
      providerId,
      payloadConRevisor,
      payloadFallback
    );

    const registro =
      Array.isArray(datosActualizados) && datosActualizados.length > 0
        ? datosActualizados[0]
        : null;

    let mensajeProveedor = limpiarTexto(payload.message);
    if (!mensajeProveedor) {
      if (estadoFinal === 'approved') {
        mensajeProveedor = construirMensajeAprobacion(registro?.full_name);
      } else if (estadoFinal === 'interview_required') {
        mensajeProveedor = construirMensajeEntrevista(registro?.full_name);
      } else {
        mensajeProveedor = construirMensajeRechazo(registro?.full_name, payload.notes);
      }
    }

    await enviarNotificacionWhatsapp({
      to: registro?.phone || payload.phone,
      message: mensajeProveedor,
      requestId
    });

    if (estadoFinal === 'approved') {
      await invalidarCacheProveedor(registro?.phone || payload.phone, requestId);
    }

    return construirRespuestaAccion(providerId, estadoFinal, 'Revisión guardada correctamente.', registro);
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

const obtenerWalletsMonetizacion = async ({
  status = 'all',
  limit = monetizationLimit,
  offset = 0
} = {}) => {
  if (!supabaseClient) return [];

  const query = [
    'select=provider_id,free_leads_remaining,paid_leads_remaining,billing_status,updated_at',
    `order=updated_at.desc`,
    `limit=${limit}`,
    `offset=${offset}`
  ];
  const estado = normalizarEstadoMonetizacion(status);
  if (status !== 'all') {
    query.push(`billing_status=eq.${estado}`);
  }

  const response = await supabaseClient.get(`provider_lead_wallet?${query.join('&')}`, {
    headers: { Accept: 'application/json' }
  });
  return Array.isArray(response.data) ? response.data : [];
};

const obtenerWalletsResumen = async () => {
  if (!supabaseClient) return [];
  const response = await supabaseClient.get(
    'provider_lead_wallet?select=provider_id,free_leads_remaining,paid_leads_remaining,billing_status',
    {
      headers: { Accept: 'application/json' }
    }
  );
  return Array.isArray(response.data) ? response.data : [];
};

const obtenerWalletPorProviderId = async providerId => {
  if (!supabaseClient || !providerId) return null;
  const encodedId = encodeURIComponent(providerId);
  const response = await supabaseClient.get(
    `provider_lead_wallet?select=provider_id,free_leads_remaining,paid_leads_remaining,billing_status,updated_at&provider_id=eq.${encodedId}&limit=1`,
    {
      headers: { Accept: 'application/json' }
    }
  );
  if (Array.isArray(response.data) && response.data.length > 0) {
    return response.data[0];
  }
  return null;
};

const obtenerEventosLeadDesde = async ({ sinceIso, providerIds = null }) => {
  if (!supabaseClient) return [];

  const params = [
    'select=id,provider_id,created_at',
    `created_at=gte.${encodeURIComponent(sinceIso)}`,
    'order=created_at.desc',
    'limit=5000'
  ];
  if (Array.isArray(providerIds) && providerIds.length > 0) {
    const encodedIds = providerIds.map(id => `"${id}"`).join(',');
    params.push(`provider_id=in.(${encodedIds})`);
  }

  const response = await supabaseClient.get(`lead_events?${params.join('&')}`, {
    headers: { Accept: 'application/json' }
  });
  return Array.isArray(response.data) ? response.data : [];
};

const obtenerFeedbackPorLeadIds = async leadIds => {
  if (!supabaseClient || !Array.isArray(leadIds) || leadIds.length === 0) return [];
  const encodedIds = leadIds.map(id => `"${id}"`).join(',');
  const response = await supabaseClient.get(
    `lead_feedback?select=lead_event_id,hired&lead_event_id=in.(${encodedIds})`,
    {
      headers: { Accept: 'application/json' }
    }
  );
  return Array.isArray(response.data) ? response.data : [];
};

const obtenerProveedoresPorIds = async providerIds => {
  if (!supabaseClient || !Array.isArray(providerIds) || providerIds.length === 0) return [];
  const encodedIds = providerIds.map(id => `"${id}"`).join(',');
  const response = await supabaseClient.get(
    `${supabaseProvidersTable}?select=id,full_name,phone,city&limit=500&id=in.(${encodedIds})`,
    {
      headers: { Accept: 'application/json' }
    }
  );
  return Array.isArray(response.data) ? response.data : [];
};

const normalizarProveedorMonetizacion = ({
  wallet,
  provider,
  eventos = [],
  feedbackByLeadId = new Map()
}) => {
  let hiredYes30d = 0;
  let hiredNo30d = 0;
  let lastLeadAt = null;

  for (const evento of eventos) {
    const leadId = limpiarTexto(evento?.id);
    if (!lastLeadAt) {
      lastLeadAt = toIsoUtc(evento?.created_at);
    }
    if (!leadId) continue;
    const feedback = feedbackByLeadId.get(leadId);
    if (!feedback || typeof feedback.hired !== 'boolean') continue;
    if (feedback.hired) {
      hiredYes30d += 1;
    } else {
      hiredNo30d += 1;
    }
  }

  return {
    providerId: String(wallet?.provider_id || provider?.id || ''),
    name:
      limpiarTexto(provider?.full_name) ||
      limpiarTexto(provider?.name) ||
      'Proveedor sin nombre',
    phone: limpiarTexto(provider?.phone) || null,
    city: limpiarTexto(provider?.city) || null,
    billingStatus: normalizarEstadoMonetizacion(wallet?.billing_status),
    freeLeadsRemaining: Number(wallet?.free_leads_remaining || 0),
    paidLeadsRemaining: Number(wallet?.paid_leads_remaining || 0),
    leadsShared30d: eventos.length,
    hiredYes30d,
    hiredNo30d,
    lastLeadAt
  };
};

async function obtenerMonetizacionResumen() {
  try {
    const wallets = await obtenerWalletsResumen();
    const now = Date.now();
    const since7d = new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString();
    const since30d = new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString();

    const [eventos7d, eventos30d] = await Promise.all([
      obtenerEventosLeadDesde({ sinceIso: since7d }),
      obtenerEventosLeadDesde({ sinceIso: since30d })
    ]);

    const feedback30d = await obtenerFeedbackPorLeadIds(
      eventos30d.map(item => item.id).filter(Boolean)
    );

    const hiredYes30d = feedback30d.filter(item => item.hired === true).length;
    const hiredNo30d = feedback30d.filter(item => item.hired === false).length;
    const totalFeedback30d = hiredYes30d + hiredNo30d;
    const hiredRate30d =
      totalFeedback30d > 0 ? Number((hiredYes30d / totalFeedback30d).toFixed(4)) : null;

    const activeProviders = wallets.filter(
      w => normalizarEstadoMonetizacion(w.billing_status) === 'active'
    ).length;
    const pausedProviders = wallets.filter(
      w => normalizarEstadoMonetizacion(w.billing_status) === 'paused_paywall'
    ).length;

    return {
      activeProviders,
      pausedProviders,
      leadsShared7d: eventos7d.length,
      leadsShared30d: eventos30d.length,
      hiredYes30d,
      hiredNo30d,
      hiredRate30d
    };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerMonetizacionProveedores({
  status = 'all',
  limit = monetizationLimit,
  offset = 0
} = {}) {
  try {
    const wallets = await obtenerWalletsMonetizacion({ status, limit, offset });
    const providerIds = wallets.map(item => String(item.provider_id)).filter(Boolean);
    const [providers, eventos30d] = await Promise.all([
      obtenerProveedoresPorIds(providerIds),
      obtenerEventosLeadDesde({
        sinceIso: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
        providerIds
      })
    ]);

    const eventosByProvider = agruparEventosPorProveedor(eventos30d);
    const feedback30d = await obtenerFeedbackPorLeadIds(
      eventos30d.map(item => item.id).filter(Boolean)
    );
    const feedbackByLeadId = agruparFeedbackPorLeadId(feedback30d);
    const providerById = new Map(
      providers.map(item => [String(item.id), item])
    );

    const items = wallets.map(wallet =>
      normalizarProveedorMonetizacion({
        wallet,
        provider: providerById.get(String(wallet.provider_id)),
        eventos: eventosByProvider.get(String(wallet.provider_id)) || [],
        feedbackByLeadId
      })
    );

    return {
      items,
      pagination: {
        limit,
        offset,
        count: items.length
      }
    };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerMonetizacionProveedor(providerId) {
  try {
    const id = limpiarTexto(providerId);
    if (!id) {
      return {
        providerId: '',
        name: 'Proveedor no encontrado',
        phone: null,
        city: null,
        billingStatus: 'active',
        freeLeadsRemaining: 0,
        paidLeadsRemaining: 0,
        leadsShared30d: 0,
        hiredYes30d: 0,
        hiredNo30d: 0,
        lastLeadAt: null
      };
    }

    const wallet = (await obtenerWalletPorProviderId(id)) || {
      provider_id: id,
      free_leads_remaining: 0,
      paid_leads_remaining: 0,
      billing_status: 'active'
    };
    const [providers, eventos30d] = await Promise.all([
      obtenerProveedoresPorIds([id]),
      obtenerEventosLeadDesde({
        sinceIso: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
        providerIds: [id]
      })
    ]);
    const feedback30d = await obtenerFeedbackPorLeadIds(
      eventos30d.map(item => item.id).filter(Boolean)
    );
    const feedbackByLeadId = agruparFeedbackPorLeadId(feedback30d);

    return normalizarProveedorMonetizacion({
      wallet,
      provider: providers[0],
      eventos: eventos30d,
      feedbackByLeadId
    });
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

module.exports = {
  obtenerProveedoresPendientes,
  obtenerProveedoresNuevos,
  obtenerProveedoresPostRevision,
  aprobarProveedor,
  rechazarProveedor,
  revisarProveedor,
  obtenerMonetizacionResumen,
  obtenerMonetizacionProveedores,
  obtenerMonetizacionProveedor
};
