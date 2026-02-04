const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

const toPositiveInt = value => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
};

const requestTimeoutMs =
  toPositiveInt(process.env.PROVIDERS_SERVICE_TIMEOUT_MS) ?? 5000;
const pendingLimit = toPositiveInt(process.env.PROVIDERS_PENDING_LIMIT) ?? 100;

const supabaseUrl = (process.env.SUPABASE_URL || '').trim();
const supabaseServiceKey = (process.env.SUPABASE_SERVICE_KEY || '').trim();
const supabaseProvidersTable =
  (process.env.SUPABASE_PROVIDERS_TABLE || 'providers').trim();
const supabaseProvidersBucket = (
  process.env.SUPABASE_PROVIDERS_BUCKET || 'tinkubot-providers'
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
    return `✅ Hola ${safeName}, tu perfil en TinkuBot fue aprobado. Ya puedes responder solicitudes cuando te escribamos.`;
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
    'select=*,provider_services(service_name,service_name_normalized,display_order)'
  ];

  if (incluirEstado) {
    // Tabla sin verification_status: usar verified=false como condición
    parametrosBase.push('verified=eq.false');
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
    const lista = Array.isArray(response.data)
      ? response.data.map(normalizarProveedorSupabase)
      : normalizarListaProveedores(response.data).map(normalizarProveedorSupabase);
    // Asegurar que rechazados no aparezcan aunque el filtro falle
    return lista.filter(item => item?.status !== 'rejected');
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
      return lista.filter(item => item?.status !== 'rejected');
    }
    throw error;
  }
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

async function aprobarProveedor(providerId, payload = {}, requestId = null) {
  try {
    const timestamp = new Date().toISOString();
    const payloadPrincipal = {
      verified: true,
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

    const approvalMessage = construirMensajeAprobacion(registro?.full_name);
    await enviarNotificacionWhatsapp({
      to: registro?.phone,
      message: approvalMessage,
      requestId
    });

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

module.exports = {
  obtenerProveedoresPendientes,
  aprobarProveedor,
  rechazarProveedor
};
