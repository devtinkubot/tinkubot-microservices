const axios = require("axios");

const toPositiveInt = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
};

const requestTimeoutMs =
  toPositiveInt(process.env.PROVIDERS_SERVICE_TIMEOUT_MS) ?? 5000;
const pendingLimit = toPositiveInt(process.env.PROVIDERS_PENDING_LIMIT) ?? 100;
const monetizationLimit =
  toPositiveInt(process.env.MONETIZATION_PROVIDER_LIMIT) ?? 100;

const supabaseUrl = (process.env.SUPABASE_URL || "").trim();
const supabaseServiceKey = (process.env.SUPABASE_SERVICE_KEY || "").trim();
const supabaseProvidersTable = (
  process.env.SUPABASE_PROVIDERS_TABLE || "providers"
).trim();
const supabaseProvidersBucket = (
  process.env.SUPABASE_PROVIDERS_BUCKET || "tinkubot-providers"
).trim();
const aiProveedoresUrl = (process.env.AI_PROVEEDORES_URL || "").trim();
const aiProveedoresInternalToken = (
  process.env.AI_PROVEEDORES_INTERNAL_TOKEN || ""
).trim();

const supabaseRestBaseUrl = supabaseUrl
  ? `${supabaseUrl.replace(/\/$/, "")}/rest/v1`
  : null;

const WA_GATEWAY_URL = process.env.WA_GATEWAY_URL || "http://wa-gateway:7000";
const WA_GATEWAY_SEND_PATH = process.env.WA_GATEWAY_SEND_PATH || "/send";
const PROVEEDORES_ACCOUNT_ID =
  process.env.PROVEEDORES_INSTANCE_ID || "bot-proveedores";

const bucketPattern = supabaseProvidersBucket.replace(
  /[.*+?^${}()|[\]\\]/g,
  "\\$&",
);

const generarUrlFirmadaSupabase = (filePath) => {
  if (!filePath) return null;
  const trimmed = filePath.trim();
  if (!trimmed) return null;

  if (
    trimmed.startsWith("/admin/providers/image/") ||
    trimmed.includes("apikey=")
  ) {
    return trimmed;
  }

  const [pathWithoutQuery] = trimmed.split("?");
  let storagePath = null;

  if (
    bucketPattern &&
    pathWithoutQuery.includes(`/storage/v1/object/${supabaseProvidersBucket}/`)
  ) {
    const match = pathWithoutQuery.match(
      new RegExp(`/storage/v1/object/${bucketPattern}/(.+)`),
    );
    if (match && match[1]) {
      storagePath = match[1];
    }
  } else if (bucketPattern && pathWithoutQuery.includes("/object/")) {
    const match = pathWithoutQuery.match(
      new RegExp(`/object/(?:public/)?${bucketPattern}/(.+)`),
    );
    if (match && match[1]) {
      storagePath = match[1];
    }
  }

  if (!storagePath && !pathWithoutQuery.includes("://")) {
    storagePath = pathWithoutQuery.replace(/^\/+/, "");
  }

  if (storagePath) {
    const sanitizedSegments = storagePath
      .split("/")
      .filter((segment) => segment && segment !== "." && segment !== "..");
    const sanitizedPath = sanitizedSegments.join("/");
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
          Authorization: `Bearer ${supabaseServiceKey}`,
        },
      })
    : null;

const invalidarCacheProveedor = async (phone, requestId = null) => {
  if (!aiProveedoresUrl || !phone) return;

  const baseUrl = aiProveedoresUrl.replace(/\/$/, "");
  const headers = {};
  if (requestId) headers["x-request-id"] = requestId;
  if (aiProveedoresInternalToken) {
    headers["x-internal-token"] = aiProveedoresInternalToken;
  }

  try {
    await axios.post(
      `${baseUrl}/admin/invalidate-provider-cache`,
      { phone },
      { headers },
    );
  } catch (error) {
    console.warn(
      "⚠️ No se pudo invalidar cache de proveedor:",
      error?.message || error,
    );
  }
};

const crearClienteAiProveedores = (requestId = null) => {
  if (!aiProveedoresUrl) {
    const error = new Error("AI Proveedores no configurado.");
    error.status = 500;
    throw error;
  }

  const headers = {};
  if (requestId) headers["x-request-id"] = requestId;
  if (aiProveedoresInternalToken) {
    headers["x-internal-token"] = aiProveedoresInternalToken;
  }

  return axios.create({
    baseURL: aiProveedoresUrl.replace(/\/$/, ""),
    timeout: requestTimeoutMs,
    headers,
  });
};

console.warn(
  `📦 Provider data source: Supabase REST (${supabaseProvidersTable})`,
);
console.warn(`📡 WA-Gateway URL: ${WA_GATEWAY_URL}`);

const limpiarTexto = (valor) => {
  if (typeof valor === "string") {
    const trimmed = valor.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  }
  return undefined;
};

const timestampIncluyeZona = (valor) =>
  /(?:[zZ]|[+-]\d{2}(?::?\d{2})?)$/.test(valor);

const normalizarTimestampComoUtc = (valor) => {
  const texto = limpiarTexto(valor);
  if (!texto) return undefined;
  return timestampIncluyeZona(texto) ? texto : `${texto}Z`;
};

const extraerUrlDocumento = (valor) => {
  if (!valor) return undefined;
  if (typeof valor === "string") {
    return limpiarTexto(valor);
  }
  if (typeof valor !== "object") {
    return undefined;
  }

  const recopilar = (origen) => {
    if (!origen || typeof origen !== "object") return undefined;
    const claves = [
      "publicUrl",
      "public_url",
      "signedUrl",
      "signed_url",
      "url",
      "href",
    ];
    for (const clave of claves) {
      const candidato = origen[clave];
      if (typeof candidato === "string") {
        const limpio = candidato.trim();
        if (limpio.length > 0) {
          return limpio;
        }
      }
    }
    const path = origen.path || origen.filePath;
    if (typeof path === "string" && path.trim().length > 0) {
      return path.trim();
    }
    return undefined;
  };

  return recopilar(valor) || recopilar(valor.data);
};

const construirMensajeAprobacion = (nombre) => {
  const safeName = limpiarTexto(nombre);
  const saludo = safeName
    ? `✅ Hola *_${safeName}_*. Ya formas parte de TinkuBot. El siguiente paso es completar tu perfil profesional.`
    : "✅ Ya formas parte de TinkuBot. El siguiente paso es completar tu perfil profesional.";

  return {
    message: saludo,
    ui: {
      type: "buttons",
      id: "provider_basic_approval_v1",
      options: [{ id: "continue_profile_completion", title: "Continuar" }],
    },
  };
};

const construirMensajeAprobacionPerfil = (nombre) => {
  const safeName = limpiarTexto(nombre);
  if (safeName) {
    return `✅ Hola *${safeName}*, tu perfil profesional fue aprobado. Ya puedes operar como proveedor en TinkuBot.`;
  }
  return "✅ Tu perfil profesional fue aprobado. Ya puedes operar como proveedor en TinkuBot.";
};

const construirMenuProveedorAprobado = () => ({
  message: "*TinkuBot Proveedores*\n\nElige la opción de interés.",
  ui: {
    type: "list",
    id: "provider_main_menu_v1",
    list_button_text: "Ver menú",
    list_section_title: "Menú del Proveedor",
    options: [
      {
        id: "provider_menu_info_personal",
        title: "Información personal",
        description: "Nombre, ubicación, documentos y foto de perfil",
      },
      {
        id: "provider_menu_info_profesional",
        title: "Información profesional",
        description: "Servicios, certificados y redes sociales",
      },
      {
        id: "provider_menu_eliminar_registro",
        title: "Eliminar mi registro",
        description: "Eliminar permanentemente tu perfil",
      },
      {
        id: "provider_menu_salir",
        title: "Salir",
        description: "Cerrar el menú actual",
      },
    ],
  },
});

const construirMensajeRevisionPerfilProfesional = (nombre) => {
  const safeName = limpiarTexto(nombre);
  if (safeName) {
    return `✅ Hola *${safeName}*, tu perfil profesional fue enviado a revisión. Te notificaremos cuando quede aprobado.`;
  }
  return "✅ Tu perfil profesional fue enviado a revisión. Te notificaremos cuando quede aprobado.";
};

const construirMensajeRechazo = (nombre, motivo) => {
  const safeName = limpiarTexto(nombre);
  const safeReason = limpiarTexto(motivo);
  if (safeName && safeReason) {
    return `❌ Hola ${safeName}, no pudimos aprobar tu registro básico. Motivo: ${safeReason}. Revisa tus datos y documentos y vuelve a intentarlo.`;
  }
  if (safeName) {
    return `❌ Hola ${safeName}, no pudimos aprobar tu registro básico con la información enviada. Revisa tus datos y documentos y vuelve a intentarlo.`;
  }
  if (safeReason) {
    return `❌ No pudimos aprobar tu registro básico. Motivo: ${safeReason}. Revisa tus datos y documentos y vuelve a intentarlo.`;
  }
  return "❌ No pudimos aprobar tu registro básico con la información enviada. Revisa tus datos y documentos y vuelve a intentarlo.";
};

const construirMensajeEntrevista = (nombre) => {
  const safeName = limpiarTexto(nombre);
  if (safeName) {
    return `Hola ${safeName}, necesitamos una validación adicional para continuar con tu registro básico. Responde a este mensaje para coordinar el siguiente paso.`;
  }
  return "Necesitamos una validación adicional para continuar con tu registro básico. Responde a este mensaje para coordinar el siguiente paso.";
};

/**
 * Formatea teléfono para WhatsApp basándose en el patrón:
 * - Teléfonos normales (ej: 5939xxx) → @s.whatsapp.net
 * - LIDs largos (ej: 254429618032748) → @lid
 * - Ya tiene @ → se usa tal cual
 */
const formatearTelefonoWhatsApp = (phone) => {
  if (!phone) return null;

  const phoneStr = String(phone).trim();
  if (!phoneStr) return null;

  // Ya tiene formato JID - usar tal cual
  if (phoneStr.includes("@")) return phoneStr;

  // Extraer solo dígitos
  const digitos = phoneStr.replace(/\D/g, "");
  if (!digitos) return null;

  // LID: >= 15 dígitos y no empieza con código de país conocido
  // (códigos de país típicos: 593 Ecuador, 54 Argentina, 52 México, etc.)
  const codigosPais = [
    "593",
    "54",
    "52",
    "57",
    "56",
    "51",
    "507",
    "502",
    "503",
    "505",
  ];
  const esTelefonoNormal =
    codigosPais.some((c) => digitos.startsWith(c)) && digitos.length <= 13;

  if (digitos.length >= 15 && !esTelefonoNormal) {
    return `${digitos}@lid`;
  }

  return `${digitos}@s.whatsapp.net`;
};

const enviarNotificacionWhatsapp = async ({ to, message, ui, requestId }) => {
  if (!limpiarTexto(to)) {
    console.warn("⚠️ Notificación WhatsApp omitida: teléfono vacío");
    return false;
  }
  if (!limpiarTexto(message)) {
    console.warn("⚠️ Notificación WhatsApp omitida: mensaje vacío");
    return false;
  }

  try {
    const payload = {
      account_id: PROVEEDORES_ACCOUNT_ID,
      to,
      message,
      ...(ui && { ui }),
    };
    const headers = {};
    if (requestId) headers["x-request-id"] = requestId;
    await axios.post(`${WA_GATEWAY_URL}${WA_GATEWAY_SEND_PATH}`, payload, {
      timeout: requestTimeoutMs,
      headers,
    });
    return true;
  } catch (err) {
    console.error(
      "❌ Error enviando notificación WhatsApp via wa-gateway:",
      err?.response?.data || err?.message || err,
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

const normalizarEstadoProveedor = (registro) => {
  // Si la tabla ya no tiene verification_status, derivar desde verified/status
  const estadoCrudo = limpiarTexto(registro?.status);
  const estado = estadoCrudo ? estadoCrudo.toLowerCase() : "";

  if (["approved_basic", "aprobado_basico", "basic_approved"].includes(estado)) {
    return "approved_basic";
  }
  if (
    ["profile_pending_review", "perfil_pendiente_revision", "professional_review_pending"].includes(
      estado,
    )
  ) {
    return "profile_pending_review";
  }
  if (["approved", "aprobado", "ok"].includes(estado)) {
    return "approved";
  }
  if (["rejected", "rechazado", "denied"].includes(estado)) {
    return "rejected";
  }
  if (["needs_info", "falta_info", "faltainfo"].includes(estado)) {
    return "interview_required";
  }
  if (["interview_required", "entrevista", "auditoria"].includes(estado)) {
    return "interview_required";
  }
  if (["pending", "pendiente"].includes(estado)) {
    return "pending";
  }
  return registro?.verified ? "approved" : "pending";
};

const construirCatalogoTaxonomiaPublicado = (
  domains = [],
  rules = [],
  aliases = [],
  canonicalServices = [],
  publication = null,
) => {
  const domainsById = new Map();
  const rulesByDomainId = new Map();
  const canonicalsByDomainId = new Map();
  const canonicalsById = new Map();
  const aliasesByDomainId = new Map();

  for (const domain of domains) {
    const id = limpiarTexto(domain?.id);
    const code = limpiarTexto(domain?.code);
    if (!id || !code) continue;
    domainsById.set(id, {
      id,
      code,
      displayName: limpiarTexto(domain?.display_name) || code,
      status: limpiarTexto(domain?.status) || null,
      aliases: [],
      canonicalServices: [],
      rules: [],
    });
  }

  for (const rule of rules) {
    const domainId = limpiarTexto(rule?.domain_id);
    if (!domainId || !domainsById.has(domainId)) continue;
    if (!rulesByDomainId.has(domainId)) {
      rulesByDomainId.set(domainId, []);
    }
    rulesByDomainId.get(domainId).push({
      id: limpiarTexto(rule?.id) || null,
      required_dimensions: Array.isArray(rule?.required_dimensions)
        ? rule.required_dimensions.filter(item => typeof item === "string" && item.trim())
        : [],
      generic_examples: Array.isArray(rule?.generic_examples)
        ? rule.generic_examples.filter(item => typeof item === "string" && item.trim())
        : [],
      sufficient_examples: Array.isArray(rule?.sufficient_examples)
        ? rule.sufficient_examples.filter(item => typeof item === "string" && item.trim())
        : [],
      client_prompt_template: limpiarTexto(rule?.client_prompt_template) || null,
      provider_prompt_template: limpiarTexto(rule?.provider_prompt_template) || null,
    });
  }

  for (const canonical of canonicalServices) {
    const domainId = limpiarTexto(canonical?.domain_id);
    if (!domainId || !domainsById.has(domainId)) continue;
    const status = limpiarTexto(canonical?.status)?.toLowerCase() || "";
    if (status && !["active", "published"].includes(status)) continue;
    const record = {
      id: limpiarTexto(canonical?.id) || null,
      canonical_name: limpiarTexto(canonical?.canonical_name) || null,
      canonical_normalized:
        limpiarTexto(canonical?.canonical_normalized) ||
        normalizarAliasTaxonomia(canonical?.canonical_name || ""),
      status: limpiarTexto(canonical?.status) || null,
      description: limpiarTexto(canonical?.description) || null,
    };
    if (!canonicalsByDomainId.has(domainId)) {
      canonicalsByDomainId.set(domainId, []);
    }
    canonicalsByDomainId.get(domainId).push(record);
    if (record.id) {
      canonicalsById.set(record.id, record);
    }
  }

  for (const alias of aliases) {
    const domainId = limpiarTexto(alias?.domain_id);
    if (!domainId || !domainsById.has(domainId)) continue;
    const status = limpiarTexto(alias?.status)?.toLowerCase() || "";
    if (status && !["active", "published"].includes(status)) continue;
    const record = {
      id: limpiarTexto(alias?.id) || null,
      alias_text: limpiarTexto(alias?.alias_text) || null,
      alias_normalized:
        limpiarTexto(alias?.alias_normalized) ||
        normalizarAliasTaxonomia(alias?.alias_text || ""),
      canonical_service_id: limpiarTexto(alias?.canonical_service_id) || null,
      canonical_name: null,
      status: limpiarTexto(alias?.status) || null,
    };
    if (record.canonical_service_id && canonicalsById.has(record.canonical_service_id)) {
      record.canonical_name =
        canonicalsById.get(record.canonical_service_id)?.canonical_name || null;
    }
    if (!aliasesByDomainId.has(domainId)) {
      aliasesByDomainId.set(domainId, []);
    }
    aliasesByDomainId.get(domainId).push(record);
  }

  const catalogDomains = Array.from(domainsById.values())
    .map(domain => ({
      ...domain,
      aliases: (aliasesByDomainId.get(domain.id) || []).sort((a, b) =>
        (a.alias_text || "").localeCompare(b.alias_text || "", "es", { sensitivity: "base" }),
      ),
      canonicalServices: (canonicalsByDomainId.get(domain.id) || []).sort((a, b) =>
        (a.canonical_name || "").localeCompare(b.canonical_name || "", "es", {
          sensitivity: "base",
        }),
      ),
      rules: rulesByDomainId.get(domain.id) || [],
    }))
    .sort((a, b) =>
      (a.displayName || a.code).localeCompare(b.displayName || b.code, "es", {
        sensitivity: "base",
      }),
    );

  return {
    version: publication?.version ?? null,
    publishedAt: publication?.published_at ?? null,
    domains: catalogDomains,
  };
};

const derivarTaxonomiaServiciosProveedor = (providerServices, taxonomyCatalog) => {
  if (!Array.isArray(providerServices) || providerServices.length === 0) {
    return [];
  }

  const domains = Array.isArray(taxonomyCatalog?.domains) ? taxonomyCatalog.domains : [];
  if (domains.length === 0) {
    return providerServices.map(item => ({
      serviceName: item.serviceName,
      normalizedName: item.normalizedName,
      domainCode: null,
      domainDisplayName: null,
      canonicalName: null,
      matchType: "unresolved",
    }));
  }

  return providerServices.map(item => {
    const normalizedName =
      limpiarTexto(item.normalizedName) || normalizarAliasTaxonomia(item.serviceName || "");
    for (const domain of domains) {
      const canonical = (domain.canonicalServices || []).find(
        entry => limpiarTexto(entry.canonical_normalized) === normalizedName,
      );
      if (canonical) {
        return {
          serviceName: item.serviceName,
          normalizedName,
          domainCode: domain.code,
          domainDisplayName: domain.displayName || domain.code,
          canonicalName: canonical.canonical_name || item.serviceName,
          matchType: "canonical",
        };
      }

      const alias = (domain.aliases || []).find(
        entry => limpiarTexto(entry.alias_normalized) === normalizedName,
      );
      if (alias) {
        return {
          serviceName: item.serviceName,
          normalizedName,
          domainCode: domain.code,
          domainDisplayName: domain.displayName || domain.code,
          canonicalName: alias.canonical_name || null,
          matchType: "alias",
        };
      }
    }

    return {
      serviceName: item.serviceName,
      normalizedName,
      domainCode: null,
      domainDisplayName: null,
      canonicalName: null,
      matchType: "unresolved",
    };
  });
};

const normalizarProveedorSupabase = (registro) => {
  const nombre =
    limpiarTexto(registro?.full_name) ||
    limpiarTexto(registro?.name) ||
    "Proveedor sin nombre";
  const businessName = limpiarTexto(registro?.business_name) || null;
  const contact =
    limpiarTexto(registro?.contact_name) || nombre || "Contacto no definido";
  const contactPhone =
    limpiarTexto(registro?.contact_phone) ||
    limpiarTexto(registro?.phone) ||
    null;
  const realPhone = limpiarTexto(registro?.real_phone) || null;
  const phone = limpiarTexto(registro?.phone) || null;
  const ciudad = limpiarTexto(registro?.city) || null;
  const provincia = limpiarTexto(registro?.province) || null;
  const providerServicesDetailed = Array.isArray(registro?.provider_services)
    ? registro.provider_services
        .filter((item) => item && typeof item.service_name === "string")
        .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0))
        .map(item => ({
          serviceName: item.service_name.trim(),
          normalizedName:
            limpiarTexto(item.service_name_normalized) ||
            normalizarAliasTaxonomia(item.service_name),
        }))
        .filter(item => item.serviceName.length > 0)
    : [];
  const servicesFromRelation = providerServicesDetailed.map(item => item.serviceName);
  const servicesRaw =
    limpiarTexto(registro?.services) ||
    (servicesFromRelation.length > 0 ? servicesFromRelation.join(" | ") : null);
  const servicesList =
    servicesFromRelation.length > 0
      ? servicesFromRelation
      : Array.isArray(registro?.services_list)
        ? registro.services_list.filter(
            (item) => typeof item === "string" && item.trim().length > 0,
          )
        : servicesRaw
          ? servicesRaw
              .split("|")
              .map((item) => item.trim())
              .filter((item) => item.length > 0)
          : [];
  const experienceYears =
    typeof registro?.experience_years === "number"
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
    typeof registro?.has_consent === "boolean" ? registro.has_consent : null;
  const rating =
    typeof registro?.rating === "number"
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
    registro?.documents?.dni_front,
  );
  const dniBackPhotoUrl = prepararUrlDocumento(
    registro?.dni_back_photo_url,
    registro?.dni_back_url,
    registro?.documents?.dni_back,
  );
  const facePhotoUrl = prepararUrlDocumento(
    registro?.face_photo_url,
    registro?.selfie_url,
    registro?.documents?.face,
  );
  const verificationReviewer =
    limpiarTexto(registro?.verification_reviewer) ||
    limpiarTexto(registro?.reviewer_name) ||
    null;
  const verificationReviewedAt =
    normalizarTimestampComoUtc(registro?.verification_reviewed_at) ||
    normalizarTimestampComoUtc(registro?.reviewed_at) ||
    null;
  const certificates = Array.isArray(registro?.provider_certificates)
    ? registro.provider_certificates
        .filter(item => item && typeof item.file_url === "string")
        .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0))
        .map(item => ({
          id: item.id,
          fileUrl: prepararUrlDocumento(item.file_url),
          displayOrder:
            typeof item.display_order === "number"
              ? item.display_order
              : Number.isFinite(Number(item.display_order))
                ? Number(item.display_order)
                : null,
          status: limpiarTexto(item.status) || null,
          createdAt: normalizarTimestampComoUtc(item.created_at) || null,
          updatedAt: normalizarTimestampComoUtc(item.updated_at) || null,
        }))
        .filter(item => typeof item.fileUrl === "string" && item.fileUrl.length > 0)
    : [];
  const contactStatus = phone?.endsWith("@lid")
    ? realPhone
      ? "lid_with_real_phone"
      : "lid_missing_real_phone"
    : realPhone
      ? "real_phone_available"
      : "basic_phone_only";
  return {
    id: registro?.id,
    name: nombre,
    businessName,
    contact,
    contactPhone,
    registeredAt,
    status: normalizarEstadoProveedor(registro),
    notes,
    phone,
    realPhone,
    contactStatus,
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
      face: facePhotoUrl,
    },
    certificates,
    verificationReviewer,
    verificationReviewedAt,
  };
};

const normalizarListaProveedores = (payload) => {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && Array.isArray(payload.providers)) {
    return payload.providers;
  }
  return [];
};

const normalizarEstadoMonetizacion = (value) => {
  const estado = limpiarTexto(value)?.toLowerCase();
  if (estado === "paused_paywall" || estado === "suspended") {
    return estado;
  }
  return "active";
};

const toIsoUtc = (value) => {
  const text = limpiarTexto(value);
  if (!text) return null;
  return timestampIncluyeZona(text) ? text : `${text}Z`;
};

const agruparEventosPorProveedor = (eventos) => {
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

const agruparFeedbackPorLeadId = (feedbackRows) => {
  const grouped = new Map();
  for (const item of feedbackRows || []) {
    const leadEventId = limpiarTexto(item?.lead_event_id);
    if (!leadEventId) continue;
    grouped.set(leadEventId, item);
  }
  return grouped;
};

const gestionarErrorAxios = (error) => {
  const status = error.response?.status ?? 500;
  const data =
    error.response?.data ??
    (error.message ? { error: error.message } : { error: "Error desconocido" });

  return {
    status,
    data,
  };
};

const construirRutaSupabasePendientes = (incluirEstado = true) => {
  const parametrosBase = [
    `limit=${pendingLimit}`,
    `order=created_at.desc`,
    "select=*,provider_services(service_name,service_name_normalized,display_order),provider_certificates(id,file_url,display_order,status,created_at,updated_at)",
  ];

  if (incluirEstado) {
    parametrosBase.push("or=(status.is.null,status.in.(new,pending))");
  }

  return `${supabaseProvidersTable}?${parametrosBase.join("&")}`;
};

const obtenerProveedoresPendientesSupabase = async () => {
  if (!supabaseClient) {
    return [];
  }

  try {
    const ruta = construirRutaSupabasePendientes(true);
    const response = await supabaseClient.get(ruta, {
      headers: {
        Accept: "application/json",
      },
    });
    const lista = Array.isArray(response.data)
      ? response.data.map(item => normalizarProveedorSupabase(item))
      : normalizarListaProveedores(response.data).map(
          item => normalizarProveedorSupabase(item),
        );
    return lista;
  } catch (error) {
    if (error.response?.status === 400) {
      // Columna verification_status podría no existir; reintentar sin filtro.
      const rutaFallback = construirRutaSupabasePendientes(false);
      const response = await supabaseClient.get(rutaFallback, {
        headers: {
          Accept: "application/json",
        },
      });
      const lista = Array.isArray(response.data)
        ? response.data.map(item => normalizarProveedorSupabase(item))
        : normalizarListaProveedores(response.data).map(
            item => normalizarProveedorSupabase(item),
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
    "select=*,provider_services(service_name,service_name_normalized,display_order),provider_certificates(id,file_url,display_order,status,created_at,updated_at)",
    "status=in.(profile_pending_review,interview_required,rejected)",
  ];

  return `${supabaseProvidersTable}?${parametrosBase.join("&")}`;
};

const obtenerProveedoresPostRevisionSupabase = async () => {
  if (!supabaseClient) {
    return [];
  }

  const ruta = construirRutaSupabasePostRevision();
  const response = await supabaseClient.get(ruta, {
    headers: {
      Accept: "application/json",
    },
  });
  const lista = Array.isArray(response.data)
    ? response.data.map(item => normalizarProveedorSupabase(item))
    : normalizarListaProveedores(response.data).map(
        item => normalizarProveedorSupabase(item),
      );
  return lista;
};

const construirRutaSupabasePorId = (providerId) => {
  const encodedId = encodeURIComponent(providerId);
  return `${supabaseProvidersTable}?id=eq.${encodedId}&select=*,provider_services(service_name,service_name_normalized,display_order),provider_certificates(id,file_url,display_order,status,created_at,updated_at)`;
};

const intentarActualizacionSupabase = async (
  providerId,
  payloadPrincipal,
  payloadFallback,
) => {
  if (!supabaseClient) {
    return null;
  }
  const ruta = construirRutaSupabasePorId(providerId);
  try {
    const response = await supabaseClient.patch(ruta, payloadPrincipal, {
      headers: {
        Prefer: "return=representation",
        "Content-Type": "application/json",
        Accept: "application/json",
      },
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
          Prefer: "return=representation",
          "Content-Type": "application/json",
          Accept: "application/json",
        },
      });
      return response.data;
    }
    throw error;
  }
};

async function obtenerProveedoresPendientes(_requestId = null) {
  try {
    return await obtenerProveedoresPendientesSupabase();
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerProveedoresNuevos(_requestId = null) {
  try {
    return await obtenerProveedoresPendientesSupabase();
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerProveedoresPostRevision(_requestId = null) {
  try {
    return await obtenerProveedoresPostRevisionSupabase();
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

const construirRespuestaAccion = (
  providerId,
  estadoFinal,
  mensaje,
  registro,
) => {
  const updatedAt = registro?.updated_at || new Date().toISOString();

  return {
    providerId,
    status: estadoFinal,
    updatedAt,
    message: mensaje,
  };
};

async function aprobarProveedor(providerId, _payload = {}, requestId = null) {
  try {
    const timestamp = new Date().toISOString();
    const payloadPrincipal = {
      verified: false,
      status: "approved_basic",
      updated_at: timestamp,
      approved_notified_at: timestamp,
    };

    const datosActualizados = await intentarActualizacionSupabase(
      providerId,
      payloadPrincipal,
      {
        verified: false,
        updated_at: timestamp,
        approved_notified_at: timestamp,
      },
    );

    const registro =
      Array.isArray(datosActualizados) && datosActualizados.length > 0
        ? datosActualizados[0]
        : null;

    const mensaje = "Onboarding básico aprobado correctamente.";

    const approvalResult = construirMensajeAprobacion(registro?.full_name);
    const telefonoBruto = registro?.real_phone || registro?.phone;
    const telefonoNotificacion = formatearTelefonoWhatsApp(telefonoBruto);
    await enviarNotificacionWhatsapp({
      to: telefonoNotificacion,
      message: approvalResult.message,
      ui: approvalResult.ui,
      requestId,
    });

    await invalidarCacheProveedor(registro?.phone, requestId);

    return construirRespuestaAccion(providerId, "approved_basic", mensaje, registro);
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function rechazarProveedor(providerId, payload = {}, requestId = null) {
  try {
    const timestamp = new Date().toISOString();
    const payloadPrincipal = {
      verified: false,
      status: "rejected",
      updated_at: timestamp,
      rejected_notified_at: timestamp,
    };

    if (limpiarTexto(payload.notes)) {
      payloadPrincipal.notes = payload.notes.trim();
    }

    const datosActualizados = await intentarActualizacionSupabase(
      providerId,
      payloadPrincipal,
      { verified: false, updated_at: timestamp },
    );

    const registro =
      Array.isArray(datosActualizados) && datosActualizados.length > 0
        ? datosActualizados[0]
        : null;

    const mensaje = "Onboarding básico rechazado correctamente.";

    const rejectionMessage = construirMensajeRechazo(
      registro?.full_name,
      payload.notes,
    );
    const telefonoRechazoBruto = registro?.real_phone || registro?.phone;
    const telefonoRechazo = formatearTelefonoWhatsApp(telefonoRechazoBruto);
    await enviarNotificacionWhatsapp({
      to: telefonoRechazo,
      message: rejectionMessage,
      requestId,
    });

    return construirRespuestaAccion(providerId, "rejected", mensaje, registro);
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function revisarProveedor(providerId, payload = {}, requestId = null) {
  try {
    const estadoSolicitado = limpiarTexto(payload.status);
    const estadoFinal =
      estadoSolicitado &&
      [
        "approved_basic",
        "profile_pending_review",
        "approved",
        "rejected",
        "interview_required",
      ].includes(estadoSolicitado)
        ? estadoSolicitado
        : null;

    if (!estadoFinal) {
      return {
        providerId,
        status: "pending",
        updatedAt: new Date().toISOString(),
        message: "Selecciona un resultado válido para continuar.",
      };
    }

    const timestamp = new Date().toISOString();
    const payloadBase = {
      updated_at: timestamp,
      status: estadoFinal,
      verified: estadoFinal === "approved",
    };

    if (estadoFinal === "approved" || estadoFinal === "approved_basic") {
      payloadBase.approved_notified_at = timestamp;
    } else if (estadoFinal === "rejected") {
      payloadBase.rejected_notified_at = timestamp;
    }

    if (limpiarTexto(payload.notes)) {
      payloadBase.notes = payload.notes.trim();
    }

    const payloadConRevisor = {
      ...payloadBase,
      verification_reviewer: limpiarTexto(payload.reviewer),
      verification_reviewed_at: timestamp,
    };

    const payloadFallback = {
      updated_at: timestamp,
      verified: estadoFinal === "approved",
    };

    const datosActualizados = await intentarActualizacionSupabase(
      providerId,
      payloadConRevisor,
      payloadFallback,
    );

    const registro =
      Array.isArray(datosActualizados) && datosActualizados.length > 0
        ? datosActualizados[0]
        : null;

    let mensajeProveedor = limpiarTexto(payload.message);
    let uiProveedor = null;
    if (estadoFinal === "approved_basic") {
      const resultado = construirMensajeAprobacion(registro?.full_name);
      mensajeProveedor = resultado.message;
      uiProveedor = resultado.ui;
    } else if (!mensajeProveedor) {
      if (estadoFinal === "approved") {
        mensajeProveedor = construirMensajeAprobacionPerfil(registro?.full_name);
      } else if (estadoFinal === "profile_pending_review") {
        mensajeProveedor = construirMensajeRevisionPerfilProfesional(
          registro?.full_name,
        );
      } else if (estadoFinal === "interview_required") {
        mensajeProveedor = construirMensajeEntrevista(registro?.full_name);
      } else {
        mensajeProveedor = construirMensajeRechazo(
          registro?.full_name,
          payload.notes,
        );
      }
    }

    const telefonoRevisarBruto =
      registro?.real_phone || registro?.phone || payload.phone;
    const telefonoRevisar = formatearTelefonoWhatsApp(telefonoRevisarBruto);
    await enviarNotificacionWhatsapp({
      to: telefonoRevisar,
      message: mensajeProveedor,
      ui: uiProveedor,
      requestId,
    });

    if (estadoFinal === "approved") {
      const menuProveedor = construirMenuProveedorAprobado();
      await enviarNotificacionWhatsapp({
        to: telefonoRevisar,
        message: menuProveedor.message,
        ui: menuProveedor.ui,
        requestId,
      });
    }

    if (estadoFinal === "approved") {
      await invalidarCacheProveedor(
        registro?.phone || payload.phone,
        requestId,
      );
    }

    return construirRespuestaAccion(
      providerId,
      estadoFinal,
      "Resultado del onboarding guardado correctamente.",
      registro,
    );
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

const obtenerWalletsMonetizacion = async ({
  status = "all",
  limit = monetizationLimit,
  offset = 0,
} = {}) => {
  if (!supabaseClient) return [];

  const query = [
    "select=provider_id,free_leads_remaining,paid_leads_remaining,billing_status,updated_at",
    `order=updated_at.desc`,
    `limit=${limit}`,
    `offset=${offset}`,
  ];
  const estado = normalizarEstadoMonetizacion(status);
  if (status !== "all") {
    query.push(`billing_status=eq.${estado}`);
  }

  const response = await supabaseClient.get(
    `provider_lead_wallet?${query.join("&")}`,
    {
      headers: { Accept: "application/json" },
    },
  );
  return Array.isArray(response.data) ? response.data : [];
};

const obtenerWalletsResumen = async () => {
  if (!supabaseClient) return [];
  const response = await supabaseClient.get(
    "provider_lead_wallet?select=provider_id,free_leads_remaining,paid_leads_remaining,billing_status",
    {
      headers: { Accept: "application/json" },
    },
  );
  return Array.isArray(response.data) ? response.data : [];
};

const obtenerWalletPorProviderId = async (providerId) => {
  if (!supabaseClient || !providerId) return null;
  const encodedId = encodeURIComponent(providerId);
  const response = await supabaseClient.get(
    `provider_lead_wallet?select=provider_id,free_leads_remaining,paid_leads_remaining,billing_status,updated_at&provider_id=eq.${encodedId}&limit=1`,
    {
      headers: { Accept: "application/json" },
    },
  );
  if (Array.isArray(response.data) && response.data.length > 0) {
    return response.data[0];
  }
  return null;
};

const obtenerEventosLeadDesde = async ({ sinceIso, providerIds = null }) => {
  if (!supabaseClient) return [];

  const params = [
    "select=id,provider_id,created_at",
    `created_at=gte.${encodeURIComponent(sinceIso)}`,
    "order=created_at.desc",
    "limit=5000",
  ];
  if (Array.isArray(providerIds) && providerIds.length > 0) {
    const encodedIds = providerIds.map((id) => `"${id}"`).join(",");
    params.push(`provider_id=in.(${encodedIds})`);
  }

  const response = await supabaseClient.get(`lead_events?${params.join("&")}`, {
    headers: { Accept: "application/json" },
  });
  return Array.isArray(response.data) ? response.data : [];
};

const obtenerFeedbackPorLeadIds = async (leadIds) => {
  if (!supabaseClient || !Array.isArray(leadIds) || leadIds.length === 0)
    return [];
  const encodedIds = leadIds.map((id) => `"${id}"`).join(",");
  const response = await supabaseClient.get(
    `lead_feedback?select=lead_event_id,hired&lead_event_id=in.(${encodedIds})`,
    {
      headers: { Accept: "application/json" },
    },
  );
  return Array.isArray(response.data) ? response.data : [];
};

const obtenerProveedoresPorIds = async (providerIds) => {
  if (
    !supabaseClient ||
    !Array.isArray(providerIds) ||
    providerIds.length === 0
  )
    return [];
  const encodedIds = providerIds.map((id) => `"${id}"`).join(",");
  const response = await supabaseClient.get(
    `${supabaseProvidersTable}?select=id,full_name,phone,city&limit=500&id=in.(${encodedIds})`,
    {
      headers: { Accept: "application/json" },
    },
  );
  return Array.isArray(response.data) ? response.data : [];
};

const normalizarProveedorMonetizacion = ({
  wallet,
  provider,
  eventos = [],
  feedbackByLeadId = new Map(),
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
    if (!feedback || typeof feedback.hired !== "boolean") continue;
    if (feedback.hired) {
      hiredYes30d += 1;
    } else {
      hiredNo30d += 1;
    }
  }

  return {
    providerId: String(wallet?.provider_id || provider?.id || ""),
    name:
      limpiarTexto(provider?.full_name) ||
      limpiarTexto(provider?.name) ||
      "Proveedor sin nombre",
    phone: limpiarTexto(provider?.phone) || null,
    city: limpiarTexto(provider?.city) || null,
    billingStatus: normalizarEstadoMonetizacion(wallet?.billing_status),
    freeLeadsRemaining: Number(wallet?.free_leads_remaining || 0),
    paidLeadsRemaining: Number(wallet?.paid_leads_remaining || 0),
    leadsShared30d: eventos.length,
    hiredYes30d,
    hiredNo30d,
    lastLeadAt,
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
      obtenerEventosLeadDesde({ sinceIso: since30d }),
    ]);

    const feedback30d = await obtenerFeedbackPorLeadIds(
      eventos30d.map((item) => item.id).filter(Boolean),
    );

    const hiredYes30d = feedback30d.filter(
      (item) => item.hired === true,
    ).length;
    const hiredNo30d = feedback30d.filter(
      (item) => item.hired === false,
    ).length;
    const totalFeedback30d = hiredYes30d + hiredNo30d;
    const hiredRate30d =
      totalFeedback30d > 0
        ? Number((hiredYes30d / totalFeedback30d).toFixed(4))
        : null;

    const activeProviders = wallets.filter(
      (w) => normalizarEstadoMonetizacion(w.billing_status) === "active",
    ).length;
    const pausedProviders = wallets.filter(
      (w) =>
        normalizarEstadoMonetizacion(w.billing_status) === "paused_paywall",
    ).length;

    return {
      activeProviders,
      pausedProviders,
      leadsShared7d: eventos7d.length,
      leadsShared30d: eventos30d.length,
      hiredYes30d,
      hiredNo30d,
      hiredRate30d,
    };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerMonetizacionProveedores({
  status = "all",
  limit = monetizationLimit,
  offset = 0,
} = {}) {
  try {
    const wallets = await obtenerWalletsMonetizacion({ status, limit, offset });
    const providerIds = wallets
      .map((item) => String(item.provider_id))
      .filter(Boolean);
    const [providers, eventos30d] = await Promise.all([
      obtenerProveedoresPorIds(providerIds),
      obtenerEventosLeadDesde({
        sinceIso: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
        providerIds,
      }),
    ]);

    const eventosByProvider = agruparEventosPorProveedor(eventos30d);
    const feedback30d = await obtenerFeedbackPorLeadIds(
      eventos30d.map((item) => item.id).filter(Boolean),
    );
    const feedbackByLeadId = agruparFeedbackPorLeadId(feedback30d);
    const providerById = new Map(
      providers.map((item) => [String(item.id), item]),
    );

    const items = wallets.map((wallet) =>
      normalizarProveedorMonetizacion({
        wallet,
        provider: providerById.get(String(wallet.provider_id)),
        eventos: eventosByProvider.get(String(wallet.provider_id)) || [],
        feedbackByLeadId,
      }),
    );

    return {
      items,
      pagination: {
        limit,
        offset,
        count: items.length,
      },
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
        providerId: "",
        name: "Proveedor no encontrado",
        phone: null,
        city: null,
        billingStatus: "active",
        freeLeadsRemaining: 0,
        paidLeadsRemaining: 0,
        leadsShared30d: 0,
        hiredYes30d: 0,
        hiredNo30d: 0,
        lastLeadAt: null,
      };
    }

    const wallet = (await obtenerWalletPorProviderId(id)) || {
      provider_id: id,
      free_leads_remaining: 0,
      paid_leads_remaining: 0,
      billing_status: "active",
    };
    const [providers, eventos30d] = await Promise.all([
      obtenerProveedoresPorIds([id]),
      obtenerEventosLeadDesde({
        sinceIso: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
        providerIds: [id],
      }),
    ]);
    const feedback30d = await obtenerFeedbackPorLeadIds(
      eventos30d.map((item) => item.id).filter(Boolean),
    );
    const feedbackByLeadId = agruparFeedbackPorLeadId(feedback30d);

    return normalizarProveedorMonetizacion({
      wallet,
      provider: providers[0],
      eventos: eventos30d,
      feedbackByLeadId,
    });
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerTaxonomiaSugerencias({
  status = "pending",
  limit = 50,
} = {}) {
  if (!supabaseClient) {
    const error = new Error(
      "Supabase REST no configurado para consultar sugerencias de taxonomía.",
    );
    error.status = 500;
    throw error;
  }

  try {
    const params = {
      select: [
        "id",
        "source_channel",
        "source_text",
        "normalized_text",
        "context_excerpt",
        "proposed_domain_code",
        "proposed_service_candidate",
        "proposed_canonical_name",
        "missing_dimensions",
        "proposal_type",
        "confidence_score",
        "evidence_json",
        "review_status",
        "cluster_key",
        "occurrence_count",
        "first_seen_at",
        "last_seen_at",
        "created_at",
        "updated_at",
      ].join(","),
      order: "last_seen_at.desc",
      limit,
    };

    if (status && status !== "all") {
      params.review_status = `eq.${status}`;
    }

    const response = await supabaseClient.get(
      "/service_taxonomy_suggestions",
      {
        params,
      },
    );

    return {
      suggestions: Array.isArray(response.data) ? response.data : [],
    };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerGovernanceReviews({
  status = "pending",
  limit = 100,
} = {}) {
  if (!supabaseClient) {
    const error = new Error(
      "Supabase REST no configurado para consultar reviews de gobernanza.",
    );
    error.status = 500;
    throw error;
  }

  try {
    const params = {
      select: [
        "id",
        "provider_id",
        "raw_service_text",
        "service_name",
        "service_name_normalized",
        "suggested_domain_code",
        "proposed_category_name",
        "proposed_service_summary",
        "assigned_domain_code",
        "assigned_category_name",
        "assigned_service_name",
        "assigned_service_summary",
        "review_reason",
        "review_status",
        "source",
        "reviewed_by",
        "reviewed_at",
        "review_notes",
        "created_at",
        "updated_at",
        "published_provider_service_id",
      ].join(","),
      order: "created_at.desc",
      limit,
    };

    if (status && status !== "all") {
      params.review_status = `eq.${status}`;
    }

    const response = await supabaseClient.get(
      "/provider_service_catalog_reviews",
      { params },
    );
    const rows = Array.isArray(response.data) ? response.data : [];
    const providerIds = [...new Set(rows.map(item => limpiarTexto(item.provider_id)).filter(Boolean))];

    let providersById = new Map();
    let servicesByProviderId = new Map();

    if (providerIds.length > 0) {
      const [providersResponse, providerServicesResponse] = await Promise.all([
        supabaseClient.get("/providers", {
          params: {
            select: "id,full_name,phone,city,status",
            id: `in.(${providerIds.map(id => `"${id}"`).join(",")})`,
            limit: providerIds.length,
          },
        }),
        supabaseClient.get("/provider_services", {
          params: {
            select: "provider_id,service_name,display_order",
            provider_id: `in.(${providerIds.map(id => `"${id}"`).join(",")})`,
            order: "display_order.asc",
            limit: providerIds.length * 10,
          },
        }),
      ]);

      const providers = Array.isArray(providersResponse.data) ? providersResponse.data : [];
      const providerServices = Array.isArray(providerServicesResponse.data)
        ? providerServicesResponse.data
        : [];

      providersById = new Map(
        providers.map(item => [item.id, item]),
      );
      servicesByProviderId = providerServices.reduce((acc, item) => {
        const key = limpiarTexto(item.provider_id);
        const serviceName = limpiarTexto(item.service_name);
        if (!key || !serviceName) return acc;
        const current = acc.get(key) || [];
        current.push(serviceName);
        acc.set(key, current);
        return acc;
      }, new Map());
    }

    return {
      reviews: rows.map(item => {
        const providerId = limpiarTexto(item.provider_id) || null;
        const provider = providerId ? providersById.get(providerId) : null;
        return {
          id: item.id,
          providerId,
          providerName: limpiarTexto(provider?.full_name) || null,
          providerPhone: limpiarTexto(provider?.phone) || null,
          providerCity: limpiarTexto(provider?.city) || null,
          rawServiceText: limpiarTexto(item.raw_service_text) || "",
          serviceName: limpiarTexto(item.service_name) || "",
          serviceNameNormalized: limpiarTexto(item.service_name_normalized) || "",
          suggestedDomainCode: limpiarTexto(item.suggested_domain_code) || null,
          proposedCategoryName: limpiarTexto(item.proposed_category_name) || null,
          proposedServiceSummary: limpiarTexto(item.proposed_service_summary) || null,
          assignedDomainCode: limpiarTexto(item.assigned_domain_code) || null,
          assignedCategoryName: limpiarTexto(item.assigned_category_name) || null,
          assignedServiceName: limpiarTexto(item.assigned_service_name) || null,
          assignedServiceSummary: limpiarTexto(item.assigned_service_summary) || null,
          reviewReason: limpiarTexto(item.review_reason) || null,
          reviewStatus: limpiarTexto(item.review_status) || "pending",
          source: limpiarTexto(item.source) || null,
          reviewedBy: limpiarTexto(item.reviewed_by) || null,
          reviewedAt: limpiarTexto(item.reviewed_at) || null,
          reviewNotes: limpiarTexto(item.review_notes) || null,
          createdAt: limpiarTexto(item.created_at) || null,
          updatedAt: limpiarTexto(item.updated_at) || null,
          publishedProviderServiceId: limpiarTexto(item.published_provider_service_id) || null,
          currentProviderServices: providerId
            ? servicesByProviderId.get(providerId) || []
            : [],
        };
      }),
    };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerGovernanceDomains() {
  if (!supabaseClient) {
    const error = new Error(
      "Supabase REST no configurado para consultar dominios de gobernanza.",
    );
    error.status = 500;
    throw error;
  }

  try {
    const response = await supabaseClient.get("/service_domains", {
      params: {
        select: "code,display_name,description,status",
        order: "code.asc",
        limit: 500,
      },
    });
    const domains = Array.isArray(response.data) ? response.data : [];
    return {
      domains: domains.map(item => ({
        code: limpiarTexto(item.code) || "",
        displayName: limpiarTexto(item.display_name) || limpiarTexto(item.code) || "",
        description: limpiarTexto(item.description) || null,
        status: limpiarTexto(item.status) || null,
      })),
    };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerGovernanceMetrics() {
  if (!supabaseClient) {
    const error = new Error(
      "Supabase REST no configurado para consultar métricas de gobernanza.",
    );
    error.status = 500;
    throw error;
  }

  try {
    const [reviewsResponse, domainsResponse, providerServicesResponse] = await Promise.all([
      supabaseClient.get("/provider_service_catalog_reviews", {
        params: {
          select: "review_status,suggested_domain_code",
          limit: 5000,
        },
      }),
      supabaseClient.get("/service_domains", {
        params: {
          select: "id,status",
          limit: 500,
        },
      }),
      supabaseClient.get("/provider_services", {
        params: {
          select: "id",
          limit: 5000,
        },
      }),
    ]);

    const reviews = Array.isArray(reviewsResponse.data) ? reviewsResponse.data : [];
    const domains = Array.isArray(domainsResponse.data) ? domainsResponse.data : [];
    const providerServices = Array.isArray(providerServicesResponse.data)
      ? providerServicesResponse.data
      : [];

    const summary = {
      pending: 0,
      approvedExistingDomain: 0,
      approvedNewDomain: 0,
      rejected: 0,
      activeDomains: domains.filter(item => ["active", "published"].includes(limpiarTexto(item.status) || "")).length,
      operationalServices: providerServices.length,
    };
    const suggestedDomainCounts = new Map();

    for (const item of reviews) {
      const status = limpiarTexto(item.review_status) || "pending";
      if (status === "pending") summary.pending += 1;
      else if (status === "approved_existing_domain") summary.approvedExistingDomain += 1;
      else if (status === "approved_new_domain") summary.approvedNewDomain += 1;
      else if (status === "rejected") summary.rejected += 1;

      const domainCode = limpiarTexto(item.suggested_domain_code);
      if (domainCode) {
        suggestedDomainCounts.set(domainCode, (suggestedDomainCounts.get(domainCode) || 0) + 1);
      }
    }

    const topSuggestedDomains = [...suggestedDomainCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([domainCode, count]) => ({ domainCode, count }));

    return { summary, topSuggestedDomains };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function aprobarGovernanceReview(reviewId, payload = {}, requestId = null) {
  try {
    const client = crearClienteAiProveedores(requestId);
    const response = await client.post(
      `/admin/service-governance/reviews/${encodeURIComponent(reviewId)}/approve`,
      {
        domain_code: payload.domainCode,
        category_name: payload.categoryName,
        service_name: payload.serviceName,
        service_summary: payload.serviceSummary,
        reviewer: payload.reviewer,
        notes: payload.notes,
        create_domain_if_missing: Boolean(payload.createDomainIfMissing),
      },
    );
    return {
      success: Boolean(response.data?.success),
      reviewId: limpiarTexto(response.data?.reviewId) || reviewId,
      providerId: limpiarTexto(response.data?.providerId) || null,
      reviewStatus: limpiarTexto(response.data?.reviewStatus) || "approved_existing_domain",
      domainCode: limpiarTexto(response.data?.domainCode) || null,
      createdDomain: Boolean(response.data?.createdDomain),
      publishedProviderServiceId: limpiarTexto(response.data?.publishedProviderServiceId) || null,
      message: limpiarTexto(response.data?.message) || null,
    };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function rechazarGovernanceReview(reviewId, payload = {}, requestId = null) {
  try {
    const client = crearClienteAiProveedores(requestId);
    const response = await client.post(
      `/admin/service-governance/reviews/${encodeURIComponent(reviewId)}/reject`,
      {
        reviewer: payload.reviewer,
        notes: payload.notes,
      },
    );
    return {
      success: Boolean(response.data?.success),
      reviewId: limpiarTexto(response.data?.reviewId) || reviewId,
      providerId: limpiarTexto(response.data?.providerId) || null,
      reviewStatus: limpiarTexto(response.data?.reviewStatus) || "rejected",
      message: limpiarTexto(response.data?.message) || null,
    };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerTaxonomiaClusters({
  status = "pending",
  limit = 50,
} = {}) {
  const result = await obtenerTaxonomiaSugerencias({
    status,
    limit: Math.max(limit * 5, 200),
  });
  const clusters = construirClustersTaxonomia(result.suggestions || []).slice(0, limit);
  return { clusters };
}

async function obtenerTaxonomiaCatalogo() {
  if (!supabaseClient) {
    const error = new Error(
      "Supabase REST no configurado para consultar catálogo de taxonomía.",
    );
    error.status = 500;
    throw error;
  }

  try {
    const [
      publicationsResponse,
      domainsResponse,
      rulesResponse,
      aliasesResponse,
      canonicalServicesResponse,
    ] = await Promise.all([
      supabaseClient.get("/service_taxonomy_publications", {
        params: {
          select: "version,status,published_at",
          status: "eq.published",
          order: "version.desc",
          limit: 1,
        },
      }),
      supabaseClient.get("/service_domains", {
        params: {
          select: "id,code,display_name,status",
          limit: 500,
        },
      }),
      supabaseClient.get("/service_precision_rules", {
        params: {
          select: [
            "id",
            "domain_id",
            "required_dimensions",
            "generic_examples",
            "sufficient_examples",
            "client_prompt_template",
            "provider_prompt_template",
          ].join(","),
          limit: 500,
        },
      }),
      supabaseClient.get("/service_domain_aliases", {
        params: {
          select: "id,domain_id,alias_text,alias_normalized,canonical_service_id,status",
          limit: 5000,
        },
      }),
      supabaseClient.get("/service_canonical_services", {
        params: {
          select: "id,domain_id,canonical_name,canonical_normalized,status,description",
          limit: 5000,
        },
      }),
    ]);

    const publications = Array.isArray(publicationsResponse.data)
      ? publicationsResponse.data
      : [];
    const domains = Array.isArray(domainsResponse.data) ? domainsResponse.data : [];
    const rules = Array.isArray(rulesResponse.data) ? rulesResponse.data : [];
    const aliases = Array.isArray(aliasesResponse.data) ? aliasesResponse.data : [];
    const canonicalServices = Array.isArray(canonicalServicesResponse.data)
      ? canonicalServicesResponse.data
      : [];

    return construirCatalogoTaxonomiaPublicado(
      domains,
      rules,
      aliases,
      canonicalServices,
      publications[0] || null,
    );
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerTaxonomiaOverview() {
  if (!supabaseClient) {
    const error = new Error(
      "Supabase REST no configurado para consultar overview de taxonomía.",
    );
    error.status = 500;
    throw error;
  }

  try {
    const [
      suggestionsResponse,
      draftsResponse,
      publicationsResponse,
      domainsResponse,
      rulesResponse,
      aliasesResponse,
      canonicalServicesResponse,
      runtimeEventsResponse,
    ] = await Promise.all([
      supabaseClient.get("/service_taxonomy_suggestions", {
        params: {
          select: "review_status,source_channel",
          limit: 1000,
        },
      }),
      supabaseClient.get("/service_taxonomy_change_queue", {
        params: {
          select: "status",
          limit: 1000,
        },
      }),
      supabaseClient.get("/service_taxonomy_publications", {
        params: {
          select: "version,status,published_at",
          order: "version.desc",
          limit: 5,
        },
      }),
      supabaseClient.get("/service_domains", {
        params: {
          select: "id,code,status",
          limit: 500,
        },
      }),
      supabaseClient.get("/service_precision_rules", {
        params: {
          select: "id,domain_id,status",
          limit: 500,
        },
      }),
      supabaseClient.get("/service_domain_aliases", {
        params: {
          select: "id,domain_id,status",
          limit: 2000,
        },
      }),
      supabaseClient.get("/service_canonical_services", {
        params: {
          select: "id,domain_id,status",
          limit: 2000,
        },
      }),
      supabaseClient.get("/service_taxonomy_runtime_events", {
        params: {
          select: "event_name,source_channel,domain_code,fallback_source,created_at",
          created_at: `gte.${new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()}`,
          order: "created_at.desc",
          limit: 5000,
        },
      }),
    ]);

    const suggestions = Array.isArray(suggestionsResponse.data)
      ? suggestionsResponse.data
      : [];
    const drafts = Array.isArray(draftsResponse.data) ? draftsResponse.data : [];
    const publications = Array.isArray(publicationsResponse.data)
      ? publicationsResponse.data
      : [];
    const domains = Array.isArray(domainsResponse.data) ? domainsResponse.data : [];
    const rules = Array.isArray(rulesResponse.data) ? rulesResponse.data : [];
    const aliases = Array.isArray(aliasesResponse.data) ? aliasesResponse.data : [];
    const canonicalServices = Array.isArray(canonicalServicesResponse.data)
      ? canonicalServicesResponse.data
      : [];
    const runtimeEvents = Array.isArray(runtimeEventsResponse.data)
      ? runtimeEventsResponse.data
      : [];

    const suggestionStatusCounts = {
      pending: 0,
      enriched: 0,
      approved: 0,
      rejected: 0,
      superseded: 0,
    };
    const suggestionSourceCounts = {
      client: 0,
      provider: 0,
      admin: 0,
      system: 0,
    };
    for (const item of suggestions) {
      const status = limpiarTexto(item.review_status);
      const source = limpiarTexto(item.source_channel);
      if (status && status in suggestionStatusCounts) {
        suggestionStatusCounts[status] += 1;
      }
      if (source && source in suggestionSourceCounts) {
        suggestionSourceCounts[source] += 1;
      }
    }

    const draftStatusCounts = {
      draft: 0,
      applied: 0,
      published: 0,
      rejected: 0,
    };
    for (const item of drafts) {
      const status = limpiarTexto(item.status);
      if (status && status in draftStatusCounts) {
        draftStatusCounts[status] += 1;
      }
    }

    const activePublication = publications.find(item => item?.status === "published") || null;
    const publishedDomains = domains.filter(
      item => item?.status === "published" || item?.status === "active",
    );
    const publishedDomainIds = new Set(
      publishedDomains.map(item => item?.id).filter(Boolean),
    );
    const domainsWithRules = new Set(
      rules
        .filter(item => publishedDomainIds.has(item?.domain_id))
        .map(item => item?.domain_id)
        .filter(Boolean),
    );
    const domainsWithAliases = new Set(
      aliases
        .filter(item => publishedDomainIds.has(item?.domain_id))
        .map(item => item?.domain_id)
        .filter(Boolean),
    );
    const domainsWithCanonicals = new Set(
      canonicalServices
        .filter(item => publishedDomainIds.has(item?.domain_id))
        .map(item => item?.domain_id)
        .filter(Boolean),
    );
    const runtimeEventCounts = {
      clarificationRequested: 0,
      genericServiceBlocked: 0,
      genericFallbackUsed: 0,
      precisionPromptFallbackUsed: 0,
    };
    const runtimeSourceCounts = {
      client: 0,
      provider: 0,
      admin: 0,
      system: 0,
    };
    const domainRuntimeMap = new Map();

    for (const item of runtimeEvents) {
      const eventName = limpiarTexto(item.event_name);
      const source = limpiarTexto(item.source_channel);
      const domainCode = limpiarTexto(item.domain_code) || "sin-dominio";

      if (source && source in runtimeSourceCounts) {
        runtimeSourceCounts[source] += 1;
      }

      if (eventName === "clarification_requested") {
        runtimeEventCounts.clarificationRequested += 1;
      } else if (eventName === "generic_service_blocked") {
        runtimeEventCounts.genericServiceBlocked += 1;
      } else if (eventName === "generic_fallback_used") {
        runtimeEventCounts.genericFallbackUsed += 1;
      } else if (eventName === "precision_prompt_fallback_used") {
        runtimeEventCounts.precisionPromptFallbackUsed += 1;
      }

      if (!domainRuntimeMap.has(domainCode)) {
        domainRuntimeMap.set(domainCode, {
          domainCode,
          clarificationRequested: 0,
          genericServiceBlocked: 0,
          fallbackUsed: 0,
        });
      }

      const bucket = domainRuntimeMap.get(domainCode);
      if (eventName === "clarification_requested") {
        bucket.clarificationRequested += 1;
      } else if (eventName === "generic_service_blocked") {
        bucket.genericServiceBlocked += 1;
      } else if (eventName === "generic_fallback_used") {
        bucket.fallbackUsed += 1;
      }
    }

    const topAmbiguousDomains = Array.from(domainRuntimeMap.values())
      .filter(
        item =>
          item.domainCode !== "sin-dominio" &&
          (item.clarificationRequested > 0 || item.genericServiceBlocked > 0),
      )
      .sort((a, b) => {
        const aScore =
          a.clarificationRequested * 2 + a.genericServiceBlocked + a.fallbackUsed;
        const bScore =
          b.clarificationRequested * 2 + b.genericServiceBlocked + b.fallbackUsed;
        return bScore - aScore || a.domainCode.localeCompare(b.domainCode);
      })
      .slice(0, 5);

    return {
      summary: {
        activeVersion: activePublication?.version ?? null,
        publishedAt: activePublication?.published_at ?? null,
        domainsPublished: publishedDomains.length,
        domainsWithRules: domainsWithRules.size,
        domainsWithAliases: domainsWithAliases.size,
        domainsWithCanonicals: domainsWithCanonicals.size,
        totalSuggestions: suggestions.length,
        totalDrafts: drafts.length,
      },
      suggestionStatusCounts,
      suggestionSourceCounts,
      draftStatusCounts,
      runtimeMetrics7d: {
        totalEvents: runtimeEvents.length,
        eventCounts: runtimeEventCounts,
        sourceCounts: runtimeSourceCounts,
        topAmbiguousDomains,
      },
    };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

function normalizarAliasTaxonomia(value) {
  return limpiarTexto(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizarListaTexto(items) {
  if (!Array.isArray(items)) {
    return [];
  }
  return [...new Set(items.map(item => limpiarTexto(item)).filter(Boolean))];
}

function compararSugerenciasCluster(a, b) {
  const aOccurrences = Number(a?.occurrence_count || 1);
  const bOccurrences = Number(b?.occurrence_count || 1);
  if (bOccurrences !== aOccurrences) {
    return bOccurrences - aOccurrences;
  }

  const aConfidence = Number(a?.confidence_score || 0);
  const bConfidence = Number(b?.confidence_score || 0);
  if (bConfidence !== aConfidence) {
    return bConfidence - aConfidence;
  }

  const aLastSeen = Date.parse(a?.last_seen_at || a?.updated_at || 0) || 0;
  const bLastSeen = Date.parse(b?.last_seen_at || b?.updated_at || 0) || 0;
  return bLastSeen - aLastSeen;
}

function determinarEstadoCluster(members) {
  const statuses = new Set(
    members.map(item => limpiarTexto(item.review_status)).filter(Boolean),
  );
  if (statuses.has("approved")) return "approved";
  if (statuses.has("pending")) return "pending";
  if (statuses.has("enriched")) return "enriched";
  if (statuses.size === 1 && statuses.has("rejected")) return "rejected";
  if (statuses.size === 1 && statuses.has("superseded")) return "superseded";
  if (statuses.has("rejected")) return "rejected";
  return "pending";
}

function construirClustersTaxonomia(suggestions) {
  const buckets = new Map();
  for (const suggestion of suggestions) {
    const clusterKey = limpiarTexto(suggestion.cluster_key) || `legacy:${suggestion.id}`;
    if (!buckets.has(clusterKey)) {
      buckets.set(clusterKey, []);
    }
    buckets.get(clusterKey).push(suggestion);
  }

  return Array.from(buckets.entries())
    .map(([clusterKey, members]) => {
      const orderedMembers = [...members].sort(compararSugerenciasCluster);
      const representative = orderedMembers[0];
      const sourceCounts = {
        client: 0,
        provider: 0,
        admin: 0,
        system: 0,
      };
      const variants = [];
      let totalOccurrences = 0;
      let firstSeenAt = null;
      let lastSeenAt = null;

      for (const member of orderedMembers) {
        const source = limpiarTexto(member.source_channel);
        if (source && source in sourceCounts) {
          sourceCounts[source] += 1;
        }
        const variant = limpiarTexto(member.source_text) || limpiarTexto(member.normalized_text);
        if (variant && !variants.includes(variant)) {
          variants.push(variant);
        }
        totalOccurrences += Number(member.occurrence_count || 1);
        const first = member.first_seen_at || member.created_at || null;
        const last = member.last_seen_at || member.updated_at || null;
        if (first && (!firstSeenAt || Date.parse(first) < Date.parse(firstSeenAt))) {
          firstSeenAt = first;
        }
        if (last && (!lastSeenAt || Date.parse(last) > Date.parse(lastSeenAt))) {
          lastSeenAt = last;
        }
      }

      return {
        clusterId: clusterKey,
        clusterKey,
        representativeSuggestionId: representative.id,
        representative,
        reviewStatus: determinarEstadoCluster(orderedMembers),
        proposalType: representative.proposal_type || null,
        proposedDomainCode: representative.proposed_domain_code || null,
        proposedCanonicalName:
          representative.proposed_canonical_name ||
          representative.proposed_service_candidate ||
          null,
        confidenceScore: representative.confidence_score ?? null,
        memberCount: orderedMembers.length,
        totalOccurrences,
        sourceCounts,
        variants,
        firstSeenAt,
        lastSeenAt,
        members: orderedMembers,
      };
    })
    .sort((a, b) => {
      const aLast = Date.parse(a.lastSeenAt || 0) || 0;
      const bLast = Date.parse(b.lastSeenAt || 0) || 0;
      return bLast - aLast || b.totalOccurrences - a.totalOccurrences;
    });
}

async function obtenerSugerenciasPorClusterKey(clusterKey) {
  const key = limpiarTexto(clusterKey);
  if (!supabaseClient || !key) {
    return [];
  }

  const response = await supabaseClient.get("/service_taxonomy_suggestions", {
    params: {
      select: [
        "id",
        "source_channel",
        "source_text",
        "normalized_text",
        "context_excerpt",
        "proposed_domain_code",
        "proposed_service_candidate",
        "proposed_canonical_name",
        "missing_dimensions",
        "proposal_type",
        "confidence_score",
        "evidence_json",
        "review_status",
        "cluster_key",
        "occurrence_count",
        "first_seen_at",
        "last_seen_at",
        "created_at",
        "updated_at",
      ].join(","),
      cluster_key: `eq.${key}`,
      order: "last_seen_at.desc",
      limit: 500,
    },
  });

  return Array.isArray(response.data) ? response.data : [];
}

async function obtenerDominioTaxonomiaPorCodigo(domainCode) {
  const domain = limpiarTexto(domainCode);
  if (!supabaseClient || !domain) {
    return null;
  }

  const response = await supabaseClient.get("/service_domains", {
    params: {
      select: "id,code,display_name,status",
      code: `eq.${domain}`,
      limit: 1,
    },
  });

  return Array.isArray(response.data) ? response.data[0] : null;
}

async function obtenerReglaPrecisionPorDominio(domainId) {
  const id = limpiarTexto(domainId);
  if (!supabaseClient || !id) {
    return null;
  }

  const response = await supabaseClient.get("/service_precision_rules", {
    params: {
      select: [
        "id",
        "required_dimensions",
        "generic_examples",
        "sufficient_examples",
        "client_prompt_template",
        "provider_prompt_template",
        "draft_required_dimensions",
        "draft_generic_examples",
        "draft_sufficient_examples",
        "draft_client_prompt_template",
        "draft_provider_prompt_template",
        "draft_updated_at",
      ].join(","),
      domain_id: `eq.${id}`,
      limit: 1,
    },
  });

  return Array.isArray(response.data) ? response.data[0] : null;
}

async function obtenerServicioCanonicoPorDominio(domainId, canonicalNormalized) {
  const id = limpiarTexto(domainId);
  const normalized = limpiarTexto(canonicalNormalized);
  if (!supabaseClient || !id || !normalized) {
    return null;
  }

  const response = await supabaseClient.get("/service_canonical_services", {
    params: {
      select: "id,domain_id,canonical_name,canonical_normalized,status",
      domain_id: `eq.${id}`,
      canonical_normalized: `eq.${normalized}`,
      limit: 1,
    },
  });

  return Array.isArray(response.data) ? response.data[0] : null;
}

function construirPayloadCambioTaxonomia(suggestion, currentRule) {
  const sourceText = limpiarTexto(suggestion.source_text);
  const normalizedText = limpiarTexto(suggestion.normalized_text);
  const proposedServiceCandidate = limpiarTexto(
    suggestion.proposed_service_candidate,
  );
  const proposedCanonicalName = limpiarTexto(
    suggestion.proposed_canonical_name || proposedServiceCandidate,
  );
  const missingDimensions = normalizarListaTexto(suggestion.missing_dimensions);
  const currentRequiredDimensions = normalizarListaTexto(
    currentRule?.required_dimensions,
  );
  const proposedRequiredDimensions = normalizarListaTexto([
    ...currentRequiredDimensions,
    ...missingDimensions,
  ]);

  return {
    source_channel: suggestion.source_channel || null,
    source_text: sourceText || null,
    normalized_text: normalizedText || null,
    context_excerpt: suggestion.context_excerpt || null,
    confidence_score: suggestion.confidence_score ?? null,
    occurrence_count: suggestion.occurrence_count ?? 1,
    evidence_json: suggestion.evidence_json || {},
    proposed_service_candidate: proposedServiceCandidate || null,
    missing_dimensions: missingDimensions,
    proposed_aliases: normalizarListaTexto([
      sourceText,
      proposedCanonicalName,
      normalizedText,
    ]),
    current_rule_snapshot: currentRule
      ? {
          id: currentRule.id || null,
          required_dimensions: currentRequiredDimensions,
          generic_examples: Array.isArray(currentRule.generic_examples)
            ? currentRule.generic_examples
            : [],
          sufficient_examples: Array.isArray(currentRule.sufficient_examples)
            ? currentRule.sufficient_examples
            : [],
          client_prompt_template: currentRule.client_prompt_template || null,
          provider_prompt_template: currentRule.provider_prompt_template || null,
          draft_required_dimensions: Array.isArray(currentRule.draft_required_dimensions)
            ? currentRule.draft_required_dimensions
            : null,
        }
      : null,
    proposed_rule_update: {
      required_dimensions: proposedRequiredDimensions,
      generic_examples: Array.isArray(currentRule?.generic_examples)
        ? currentRule.generic_examples
        : [],
      sufficient_examples: Array.isArray(currentRule?.sufficient_examples)
        ? currentRule.sufficient_examples
        : [],
      client_prompt_template: currentRule?.client_prompt_template || null,
      provider_prompt_template: currentRule?.provider_prompt_template || null,
    },
    current_canonical_name: null,
    diff_summary: {
      alias_before: suggestion.evidence_json?.alias_match?.alias_text || null,
      alias_after: proposedCanonicalName || sourceText || normalizedText || null,
      required_dimensions_before: currentRequiredDimensions,
      required_dimensions_after: proposedRequiredDimensions,
    },
  };
}

async function obtenerTaxonomiaSugerenciaPorId(suggestionId) {
  const id = limpiarTexto(suggestionId);
  if (!supabaseClient || !id) {
    return null;
  }

  const suggestionResponse = await supabaseClient.get(
    `/service_taxonomy_suggestions?id=eq.${encodeURIComponent(id)}`,
    {
      params: {
        select: [
          "id",
          "source_channel",
          "source_text",
          "normalized_text",
          "context_excerpt",
          "proposed_domain_code",
          "proposed_service_candidate",
          "proposed_canonical_name",
          "missing_dimensions",
          "proposal_type",
          "confidence_score",
          "evidence_json",
          "review_status",
          "occurrence_count",
          "cluster_key",
        ].join(","),
        limit: 1,
      },
    },
  );

  return Array.isArray(suggestionResponse.data) ? suggestionResponse.data[0] : null;
}

async function aprobarTaxonomiaSugerenciaDesdeRegistro(suggestion, payload = {}) {
  const approvedBy = limpiarTexto(payload.approvedBy) || "admin-dashboard";
  const reviewNotes = limpiarTexto(payload.reviewNotes);

  const actionType = limpiarTexto(suggestion.proposal_type) || "review";
  if (!["alias", "new_canonical", "rule_update", "review"].includes(actionType)) {
    const error = new Error("proposal_type inválido para aprobación.");
    error.status = 400;
    throw error;
  }

  const domain = await obtenerDominioTaxonomiaPorCodigo(
    suggestion.proposed_domain_code,
  );
  const currentRule = domain?.id
    ? await obtenerReglaPrecisionPorDominio(domain.id)
    : null;
  const nowIso = new Date().toISOString();
  const changeResponse = await supabaseClient.post(
    "/service_taxonomy_change_queue",
    {
      suggestion_id: suggestion.id,
      action_type: actionType,
      target_domain_code: suggestion.proposed_domain_code || null,
      proposed_canonical_name: suggestion.proposed_canonical_name || null,
      payload_json: construirPayloadCambioTaxonomia(suggestion, currentRule),
      status: "draft",
      notes: reviewNotes || null,
      approved_by: approvedBy,
      approved_at: nowIso,
    },
    {
      headers: {
        Prefer: "return=representation",
      },
    },
  );

  const change = Array.isArray(changeResponse.data) ? changeResponse.data[0] : null;
  if (!change?.id) {
    const error = new Error("No se pudo crear el cambio draft.");
    error.status = 500;
    throw error;
  }

  await supabaseClient.patch(
    `/service_taxonomy_suggestions?id=eq.${encodeURIComponent(suggestion.id)}`,
    {
      review_status: "approved",
      status: "approved",
      review_notes: reviewNotes || null,
      reviewed_by: approvedBy,
      reviewed_at: nowIso,
      updated_at: nowIso,
    },
    {
      headers: {
        Prefer: "return=representation",
      },
    },
  );

  return {
    suggestionId: suggestion.id,
    reviewStatus: "approved",
    changeId: change.id,
    changeStatus: change.status || "draft",
    updatedAt: nowIso,
  };
}

async function revisarTaxonomiaSugerencia(suggestionId, payload = {}) {
  if (!supabaseClient) {
    const error = new Error(
      "Supabase REST no configurado para revisar sugerencias de taxonomía.",
    );
    error.status = 500;
    throw error;
  }

  const id = limpiarTexto(suggestionId);
  if (!id) {
    const error = new Error("Identificador de sugerencia inválido.");
    error.status = 400;
    throw error;
  }

  const reviewStatus = limpiarTexto(payload.reviewStatus);
  if (!reviewStatus || !["pending", "rejected"].includes(reviewStatus)) {
    const error = new Error("reviewStatus inválido.");
    error.status = 400;
    throw error;
  }

  const reviewNotes = limpiarTexto(payload.reviewNotes);
  const nowIso = new Date().toISOString();

  try {
    const response = await supabaseClient.patch(
      `/service_taxonomy_suggestions?id=eq.${encodeURIComponent(id)}`,
      {
        review_status: reviewStatus,
        status: reviewStatus === "pending" ? "pending" : "rejected",
        review_notes: reviewNotes || null,
        updated_at: nowIso,
      },
      {
        headers: {
          Prefer: "return=representation",
        },
      },
    );

    const updated = Array.isArray(response.data) ? response.data[0] : null;
    return {
      suggestionId: id,
      reviewStatus,
      updatedAt: updated?.updated_at ?? nowIso,
    };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function aprobarTaxonomiaSugerencia(suggestionId, payload = {}) {
  if (!supabaseClient) {
    const error = new Error(
      "Supabase REST no configurado para aprobar sugerencias de taxonomía.",
    );
    error.status = 500;
    throw error;
  }

  const id = limpiarTexto(suggestionId);
  if (!id) {
    const error = new Error("Identificador de sugerencia inválido.");
    error.status = 400;
    throw error;
  }

  try {
    const suggestion = await obtenerTaxonomiaSugerenciaPorId(id);
    if (!suggestion) {
      const error = new Error("Sugerencia no encontrada.");
      error.status = 404;
      throw error;
    }
    return await aprobarTaxonomiaSugerenciaDesdeRegistro(suggestion, payload);
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function revisarTaxonomiaCluster(clusterId, payload = {}) {
  if (!supabaseClient) {
    const error = new Error(
      "Supabase REST no configurado para revisar clusters de taxonomía.",
    );
    error.status = 500;
    throw error;
  }

  const decodedClusterId = limpiarTexto(decodeURIComponent(clusterId || ""));
  if (!decodedClusterId) {
    const error = new Error("Identificador de cluster inválido.");
    error.status = 400;
    throw error;
  }

  const reviewStatus = limpiarTexto(payload.reviewStatus);
  if (!reviewStatus || !["pending", "rejected"].includes(reviewStatus)) {
    const error = new Error("reviewStatus inválido.");
    error.status = 400;
    throw error;
  }

  const suggestions = await obtenerSugerenciasPorClusterKey(decodedClusterId);
  if (suggestions.length === 0) {
    const error = new Error("Cluster no encontrado.");
    error.status = 404;
    throw error;
  }

  const targetSuggestions = suggestions.filter(item => {
    const status = limpiarTexto(item.review_status);
    if (reviewStatus === "rejected") {
      return status === "pending" || status === "enriched";
    }
    return status === "rejected";
  });

  const nowIso = new Date().toISOString();
  const reviewNotes = limpiarTexto(payload.reviewNotes);

  await Promise.all(
    targetSuggestions.map(item =>
      supabaseClient.patch(
        `/service_taxonomy_suggestions?id=eq.${encodeURIComponent(item.id)}`,
        {
          review_status: reviewStatus,
          status: reviewStatus === "pending" ? "pending" : "rejected",
          review_notes: reviewNotes || null,
          updated_at: nowIso,
        },
        {
          headers: {
            Prefer: "return=representation",
          },
        },
      ),
    ),
  );

  return {
    clusterId: decodedClusterId,
    reviewStatus,
    updatedAt: nowIso,
  };
}

async function aprobarTaxonomiaCluster(clusterId, payload = {}) {
  if (!supabaseClient) {
    const error = new Error(
      "Supabase REST no configurado para aprobar clusters de taxonomía.",
    );
    error.status = 500;
    throw error;
  }

  const decodedClusterId = limpiarTexto(decodeURIComponent(clusterId || ""));
  if (!decodedClusterId) {
    const error = new Error("Identificador de cluster inválido.");
    error.status = 400;
    throw error;
  }

  const suggestions = await obtenerSugerenciasPorClusterKey(decodedClusterId);
  if (suggestions.length === 0) {
    const error = new Error("Cluster no encontrado.");
    error.status = 404;
    throw error;
  }

  const representative = [...suggestions].sort(compararSugerenciasCluster)[0];
  const result = await aprobarTaxonomiaSugerenciaDesdeRegistro(representative, payload);
  const reviewNotes = limpiarTexto(payload.reviewNotes);
  const nowIso = new Date().toISOString();
  const siblings = suggestions.filter(item => item.id !== representative.id);

  await Promise.all(
    siblings.map(item =>
      supabaseClient.patch(
        `/service_taxonomy_suggestions?id=eq.${encodeURIComponent(item.id)}`,
        {
          review_status: "superseded",
          status: "superseded",
          review_notes:
            reviewNotes || `Superseded by cluster representative ${representative.id}`,
          updated_at: nowIso,
        },
        {
          headers: {
            Prefer: "return=representation",
          },
        },
      ),
    ),
  );

  return {
    ...result,
    clusterId: decodedClusterId,
  };
}

async function obtenerTaxonomiaDrafts() {
  if (!supabaseClient) {
    const error = new Error(
      "Supabase REST no configurado para consultar drafts de taxonomía.",
    );
    error.status = 500;
    throw error;
  }

  try {
    const response = await supabaseClient.get("/service_taxonomy_change_queue", {
      params: {
        select: [
          "id",
          "suggestion_id",
          "action_type",
          "target_domain_code",
          "proposed_canonical_name",
          "payload_json",
          "status",
          "notes",
          "approved_by",
          "approved_at",
          "created_at",
          "updated_at",
          "applied_at",
        ].join(","),
        order: "created_at.desc",
      },
    });

    return {
      items: Array.isArray(response.data) ? response.data : [],
    };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function aplicarTaxonomiaDraft(changeId) {
  if (!supabaseClient) {
    const error = new Error(
      "Supabase REST no configurado para aplicar drafts de taxonomía.",
    );
    error.status = 500;
    throw error;
  }

  const id = limpiarTexto(changeId);
  if (!id) {
    const error = new Error("Identificador de draft inválido.");
    error.status = 400;
    throw error;
  }

  try {
    const changeResponse = await supabaseClient.get(
      `/service_taxonomy_change_queue?id=eq.${encodeURIComponent(id)}`,
      {
        params: {
          select: [
            "id",
            "action_type",
            "target_domain_code",
            "proposed_canonical_name",
            "payload_json",
            "status",
          ].join(","),
          limit: 1,
        },
      },
    );
    const change = Array.isArray(changeResponse.data) ? changeResponse.data[0] : null;
    if (!change) {
      const error = new Error("Draft no encontrado.");
      error.status = 404;
      throw error;
    }
    if (change.status !== "draft") {
      return {
        changeId: id,
        status: change.status,
        aliasId: change.payload_json?.applied_alias_id ?? null,
        updatedAt: change.payload_json?.applied_at ?? null,
      };
    }

    const domainCode = limpiarTexto(change.target_domain_code);
    if (!domainCode) {
      const error = new Error("El draft no tiene target_domain_code.");
      error.status = 400;
      throw error;
    }

    const domainResponse = await supabaseClient.get("/service_domains", {
      params: {
        select: "id,code,status",
        code: `eq.${domainCode}`,
        limit: 1,
      },
    });
    const domain = Array.isArray(domainResponse.data) ? domainResponse.data[0] : null;
    if (!domain?.id) {
      const error = new Error("No se encontró el dominio destino para el draft.");
      error.status = 404;
      throw error;
    }

    const nowIso = new Date().toISOString();
    const mergedPayload = {
      ...(change.payload_json || {}),
      applied_at: nowIso,
    };
    let aliasId = null;

    if (change.action_type === "rule_update") {
      const proposedRuleUpdate = mergedPayload.proposed_rule_update || {};
      const currentRule = await obtenerReglaPrecisionPorDominio(domain.id);

      if (currentRule?.id) {
        await supabaseClient.patch(
          `/service_precision_rules?id=eq.${encodeURIComponent(currentRule.id)}`,
          {
            draft_required_dimensions: normalizarListaTexto(
              proposedRuleUpdate.required_dimensions,
            ),
            draft_generic_examples: Array.isArray(
              proposedRuleUpdate.generic_examples,
            )
              ? proposedRuleUpdate.generic_examples
              : currentRule.generic_examples || [],
            draft_sufficient_examples: Array.isArray(
              proposedRuleUpdate.sufficient_examples,
            )
              ? proposedRuleUpdate.sufficient_examples
              : currentRule.sufficient_examples || [],
            draft_client_prompt_template:
              limpiarTexto(proposedRuleUpdate.client_prompt_template)
              || currentRule.client_prompt_template
              || null,
            draft_provider_prompt_template:
              limpiarTexto(proposedRuleUpdate.provider_prompt_template)
              || currentRule.provider_prompt_template
              || null,
            draft_updated_at: nowIso,
            updated_at: nowIso,
          },
        );
        mergedPayload.applied_rule_id = currentRule.id;
      } else {
        const insertedRuleResponse = await supabaseClient.post(
          "/service_precision_rules",
          {
            domain_id: domain.id,
            required_dimensions: [],
            generic_examples: [],
            sufficient_examples: [],
            client_prompt_template: null,
            provider_prompt_template: null,
            draft_required_dimensions: normalizarListaTexto(
              proposedRuleUpdate.required_dimensions,
            ),
            draft_generic_examples: Array.isArray(
              proposedRuleUpdate.generic_examples,
            )
              ? proposedRuleUpdate.generic_examples
              : [],
            draft_sufficient_examples: Array.isArray(
              proposedRuleUpdate.sufficient_examples,
            )
              ? proposedRuleUpdate.sufficient_examples
              : [],
            draft_client_prompt_template:
              limpiarTexto(proposedRuleUpdate.client_prompt_template) || null,
            draft_provider_prompt_template:
              limpiarTexto(proposedRuleUpdate.provider_prompt_template) || null,
            draft_updated_at: nowIso,
          },
          {
            headers: {
              Prefer: "return=representation",
            },
          },
        );
        const insertedRule = Array.isArray(insertedRuleResponse.data)
          ? insertedRuleResponse.data[0]
          : null;
        mergedPayload.applied_rule_id = insertedRule?.id || null;
      }
      mergedPayload.apply_strategy = "rule_draft";
    } else {
      const aliasText = limpiarTexto(change.proposed_canonical_name)
        || limpiarTexto(mergedPayload.proposed_service_candidate)
        || limpiarTexto(mergedPayload.source_text)
        || limpiarTexto(mergedPayload.normalized_text);
      if (!aliasText) {
        const error = new Error("No se pudo resolver el texto del alias draft.");
        error.status = 400;
        throw error;
      }

      const aliasNormalized = normalizarAliasTaxonomia(aliasText);
      let canonicalServiceId = null;

      if (change.action_type === "new_canonical") {
        const canonicalService = await obtenerServicioCanonicoPorDominio(
          domain.id,
          aliasNormalized,
        );

        canonicalServiceId = canonicalService?.id ?? null;
        if (!canonicalService) {
          const insertedCanonicalResponse = await supabaseClient.post(
            "/service_canonical_services",
            {
              domain_id: domain.id,
              canonical_name: aliasText,
              canonical_normalized: aliasNormalized,
              description: mergedPayload.context_excerpt || null,
              metadata_json: {
                source_text: mergedPayload.source_text || null,
                occurrence_count: mergedPayload.occurrence_count ?? 1,
                confidence_score: mergedPayload.confidence_score ?? null,
              },
              status: "inactive",
            },
            {
              headers: {
                Prefer: "return=representation",
              },
            },
          );
          const insertedCanonical = Array.isArray(insertedCanonicalResponse.data)
            ? insertedCanonicalResponse.data[0]
            : null;
          canonicalServiceId = insertedCanonical?.id ?? null;
        }

        mergedPayload.applied_canonical_service_id = canonicalServiceId;
        mergedPayload.applied_canonical_name = aliasText;
        mergedPayload.apply_strategy = "canonical_service";
      }

      const existingAlias = await supabaseClient.get("/service_domain_aliases", {
        params: {
          select: "id,domain_id,alias_normalized,status,canonical_service_id",
          domain_id: `eq.${domain.id}`,
          alias_normalized: `eq.${aliasNormalized}`,
          limit: 1,
        },
      });
      const existing = Array.isArray(existingAlias.data) ? existingAlias.data[0] : null;

      aliasId = existing?.id ?? null;
      if (!existing) {
        const insertedAlias = await supabaseClient.post(
          "/service_domain_aliases",
          {
            domain_id: domain.id,
            alias_text: aliasText,
            alias_normalized: aliasNormalized,
            canonical_service_id: canonicalServiceId,
            priority: 1000,
            status: "inactive",
          },
          {
            headers: {
              Prefer: "return=representation",
            },
          },
        );
        const inserted = Array.isArray(insertedAlias.data) ? insertedAlias.data[0] : null;
        aliasId = inserted?.id ?? null;
      } else if (
        change.action_type === "new_canonical"
        && canonicalServiceId
        && existing.canonical_service_id !== canonicalServiceId
      ) {
        await supabaseClient.patch(
          `/service_domain_aliases?id=eq.${encodeURIComponent(existing.id)}`,
          {
            canonical_service_id: canonicalServiceId,
            updated_at: nowIso,
          },
        );
      }

      mergedPayload.applied_alias_id = aliasId;
      mergedPayload.applied_alias_text = aliasText;
      mergedPayload.applied_alias_normalized = aliasNormalized;
      if (!mergedPayload.apply_strategy) {
        mergedPayload.apply_strategy = change.action_type || "alias";
      }
    }

    await supabaseClient.patch(
      `/service_taxonomy_change_queue?id=eq.${encodeURIComponent(id)}`,
      {
        status: "applied",
        payload_json: mergedPayload,
        applied_at: nowIso,
        updated_at: nowIso,
      },
      {
        headers: {
          Prefer: "return=representation",
        },
      },
    );

    return {
      changeId: id,
      status: "applied",
      aliasId,
      updatedAt: nowIso,
    };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function publicarTaxonomiaDrafts() {
  if (!supabaseClient) {
    const error = new Error(
      "Supabase REST no configurado para publicar taxonomía.",
    );
    error.status = 500;
    throw error;
  }

  try {
    const draftsResponse = await supabaseClient.get("/service_taxonomy_change_queue", {
      params: {
        select: "id,payload_json,status,action_type",
        status: "eq.applied",
      },
    });
    const drafts = Array.isArray(draftsResponse.data) ? draftsResponse.data : [];
    if (drafts.length === 0) {
      const error = new Error("No hay drafts aplicados pendientes de publicación.");
      error.status = 400;
      throw error;
    }
    const nowIso = new Date().toISOString();

    const aliasIds = drafts
      .filter(item => item?.action_type !== "rule_update")
      .map(item => item?.payload_json?.applied_alias_id)
      .filter(Boolean);

    const canonicalServiceIds = drafts
      .filter(item => item?.action_type === "new_canonical")
      .map(item => item?.payload_json?.applied_canonical_service_id)
      .filter(Boolean);

    for (const canonicalServiceId of canonicalServiceIds) {
      await supabaseClient.patch(
        `/service_canonical_services?id=eq.${encodeURIComponent(canonicalServiceId)}`,
        {
          status: "active",
          updated_at: nowIso,
        },
      );
    }

    for (const aliasId of aliasIds) {
      await supabaseClient.patch(
        `/service_domain_aliases?id=eq.${encodeURIComponent(aliasId)}`,
        {
          status: "active",
          updated_at: new Date().toISOString(),
        },
      );
    }

    const ruleIds = drafts
      .filter(item => item?.action_type === "rule_update")
      .map(item => item?.payload_json?.applied_rule_id)
      .filter(Boolean);

    for (const ruleId of ruleIds) {
      const rulesResponse = await supabaseClient.get(
        `/service_precision_rules?id=eq.${encodeURIComponent(ruleId)}`,
        {
          params: {
            select: [
              "id",
              "required_dimensions",
              "generic_examples",
              "sufficient_examples",
              "client_prompt_template",
              "provider_prompt_template",
              "draft_required_dimensions",
              "draft_generic_examples",
              "draft_sufficient_examples",
              "draft_client_prompt_template",
              "draft_provider_prompt_template",
            ].join(","),
            limit: 1,
          },
        },
      );
      const rule = Array.isArray(rulesResponse.data) ? rulesResponse.data[0] : null;
      if (!rule?.id) {
        continue;
      }
      await supabaseClient.patch(
        `/service_precision_rules?id=eq.${encodeURIComponent(rule.id)}`,
        {
          required_dimensions: Array.isArray(rule.draft_required_dimensions)
            ? rule.draft_required_dimensions
            : rule.required_dimensions || [],
          generic_examples: Array.isArray(rule.draft_generic_examples)
            ? rule.draft_generic_examples
            : rule.generic_examples || [],
          sufficient_examples: Array.isArray(rule.draft_sufficient_examples)
            ? rule.draft_sufficient_examples
            : rule.sufficient_examples || [],
          client_prompt_template:
            rule.draft_client_prompt_template || rule.client_prompt_template || null,
          provider_prompt_template:
            rule.draft_provider_prompt_template || rule.provider_prompt_template || null,
          draft_required_dimensions: null,
          draft_generic_examples: null,
          draft_sufficient_examples: null,
          draft_client_prompt_template: null,
          draft_provider_prompt_template: null,
          draft_updated_at: null,
          updated_at: nowIso,
        },
      );
    }

    const publicationsResponse = await supabaseClient.get(
      "/service_taxonomy_publications",
      {
        params: {
          select: "version,status",
          order: "version.desc",
          limit: 1,
        },
      },
    );
    const last = Array.isArray(publicationsResponse.data)
      ? publicationsResponse.data[0]
      : null;
    const nextVersion = Number(last?.version || 0) + 1;

    await supabaseClient.patch(
      "/service_taxonomy_publications?status=eq.published",
      {
        status: "archived",
        updated_at: nowIso,
      },
    );
    await supabaseClient.post("/service_taxonomy_publications", {
      version: nextVersion,
      status: "published",
      published_by: "admin-dashboard",
      published_at: nowIso,
      notes: `Publicación manual desde draft queue (${drafts.length} cambios aplicados).`,
    });

    for (const draft of drafts) {
      const mergedPayload = {
        ...(draft.payload_json || {}),
        published_at: nowIso,
        published_version: nextVersion,
      };
      await supabaseClient.patch(
        `/service_taxonomy_change_queue?id=eq.${encodeURIComponent(draft.id)}`,
        {
          status: "published",
          payload_json: mergedPayload,
          updated_at: nowIso,
        },
      );
    }

    return {
      version: nextVersion,
      publishedCount: drafts.length,
      publishedAt: nowIso,
    };
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
  obtenerMonetizacionProveedor,
  obtenerGovernanceReviews,
  obtenerGovernanceDomains,
  obtenerGovernanceMetrics,
  aprobarGovernanceReview,
  rechazarGovernanceReview,
  obtenerTaxonomiaCatalogo,
  obtenerTaxonomiaOverview,
  obtenerTaxonomiaSugerencias,
  obtenerTaxonomiaClusters,
  revisarTaxonomiaSugerencia,
  revisarTaxonomiaCluster,
  aprobarTaxonomiaSugerencia,
  aprobarTaxonomiaCluster,
  obtenerTaxonomiaDrafts,
  aplicarTaxonomiaDraft,
  publicarTaxonomiaDrafts,
};
