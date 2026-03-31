const axios = require("axios");
const {
  construirMensajeAprobacionProveedor,
  construirMensajeRechazoProveedor,
} = require("./provider_messaging");

const toPositiveInt = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
};

const requestTimeoutMs =
  toPositiveInt(process.env.PROVIDERS_SERVICE_TIMEOUT_MS) ?? 5000;
const pendingLimit = toPositiveInt(process.env.PROVIDERS_PENDING_LIMIT) ?? 100;
const ONBOARDING_STEPS = [
  "onboarding_consent",
  "onboarding_city",
  "onboarding_dni_front_photo",
  "onboarding_face_photo",
  "onboarding_experience",
  "onboarding_specialty",
  "onboarding_add_another_service",
  "onboarding_social_media",
];
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

console.warn(
  `📦 Provider data source: Supabase REST (${supabaseProvidersTable})`,
);
console.warn(`📡 WA-Gateway URL: ${WA_GATEWAY_URL}`);

const limpiarTexto = (valor) => {
  if (typeof valor === "string") {
    const trimmed = valor.trim();
    if (!trimmed) return undefined;
    const lower = trimmed.toLowerCase();
    if (["null", "none", "undefined", "n/a", "na"].includes(lower)) {
      return undefined;
    }
    return trimmed;
  }
  return undefined;
};

const limpiarTextoIdentidad = (...valores) => {
  for (const valor of valores) {
    const limpio = limpiarTexto(valor);
    if (limpio) {
      return limpio;
    }
  }
  return null;
};

const formatearTelefonoVisible = (valor) => {
  const texto = limpiarTexto(valor);
  if (!texto) return null;

  const digitos = texto.replace(/\D/g, "");
  if (!digitos) return null;

  const localDigits = digitos.startsWith("593")
    ? digitos.slice(3)
    : digitos.startsWith("0")
      ? digitos.slice(1)
      : digitos;

  if (localDigits.length === 9) {
    return `+593 ${localDigits.slice(0, 2)}-${localDigits.slice(2, 5)}-${localDigits.slice(5)}`;
  }

  if (localDigits.length === 8) {
    return `+593 ${localDigits.slice(0, 1)}-${localDigits.slice(1, 4)}-${localDigits.slice(4)}`;
  }

  if (digitos.startsWith("593")) {
    return `+${digitos}`;
  }

  if (digitos.startsWith("0")) {
    return `+593 ${localDigits}`;
  }

  return null;
};

const resolverNombreVisibleProveedor = (registro) => {
  const displayName = limpiarTexto(registro?.display_name);
  const formattedName = limpiarTexto(registro?.formatted_name);
  const nombreDocumento = [
    limpiarTexto(registro?.document_first_names),
    limpiarTexto(registro?.document_last_names),
  ]
    .filter(Boolean)
    .join(" ")
    .trim();

  return (
    nombreDocumento || formattedName || displayName || "Proveedor sin nombre"
  );
};

const construirNotasIdentidad = ({
  documentFirstNames,
  documentLastNames,
  documentIdNumber,
}) => {
  const segmentos = [];
  if (documentFirstNames) {
    segmentos.push(`Nombres: ${documentFirstNames}`);
  }
  if (documentLastNames) {
    segmentos.push(`Apellidos: ${documentLastNames}`);
  }
  if (documentIdNumber) {
    segmentos.push(`Cédula: ${documentIdNumber}`);
  }
  return segmentos.join(" | ");
};

const timestampIncluyeZona = (valor) =>
  /(?:[zZ]|[+-]\d{2}(?::?\d{2})?)$/.test(valor);

const normalizarTimestampComoUtc = (valor) => {
  const texto = limpiarTexto(valor);
  if (!texto) return undefined;
  return timestampIncluyeZona(texto) ? texto : `${texto}Z`;
};

const obtenerFechaNormalizada = (valor) => {
  const texto = normalizarTimestampComoUtc(valor);
  if (!texto) return null;
  const fecha = new Date(texto);
  return Number.isNaN(fecha.getTime()) ? null : fecha;
};

const MINIMO_SERVICIOS_OPERATIVOS = 1;
const tienePerfilProfesionalCompleto = (proveedor) => {
  if (!proveedor) return false;
  const serviciosValidos = Array.isArray(proveedor.servicesList)
    ? proveedor.servicesList.filter(
        (item) => typeof item === "string" && item.trim().length > 0,
      )
    : [];
  const experiencia =
    typeof proveedor.experienceRange === "string" &&
    proveedor.experienceRange.trim().length > 0;
  return experiencia && serviciosValidos.length >= MINIMO_SERVICIOS_OPERATIVOS;
};

const tieneNombreLegibleProveedor = (proveedor) => {
  if (!proveedor) return false;
  const nombreCompuesto = [proveedor.firstName, proveedor.lastName]
    .filter(Boolean)
    .join(" ")
    .trim();
  return Boolean(
    proveedor.displayName?.trim() ||
    proveedor.formattedName?.trim() ||
    nombreCompuesto,
  );
};

const esProveedorOperativo = (proveedor) =>
  Boolean(
    proveedor &&
    proveedor.status === "approved" &&
    tienePerfilProfesionalCompleto(proveedor) &&
    tieneNombreLegibleProveedor(proveedor) &&
    typeof proveedor.city === "string" &&
    proveedor.city.trim().length > 0 &&
    proveedor.hasConsent === true,
  );

const esProveedorPerfilProfesionalPendiente = (proveedor) =>
  Boolean(
    proveedor &&
    proveedor.status === "approved" &&
    !tienePerfilProfesionalCompleto(proveedor),
  );

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
  // Derivar el estado visible desde status/verified y tolerar aliases legacy.
  const estadoCrudo = limpiarTexto(registro?.status);
  const estado = estadoCrudo ? estadoCrudo.toLowerCase() : "";

  if (
    ["approved_basic", "aprobado_basico", "basic_approved"].includes(estado)
  ) {
    return "approved";
  }
  if (
    [
      "profile_pending_review",
      "perfil_pendiente_revision",
      "professional_review_pending",
      "interview_required",
      "entrevista",
      "auditoria",
      "needs_info",
      "falta_info",
      "faltainfo",
    ].includes(estado)
  ) {
    return "approved";
  }
  if (estado === "pending_verification") {
    return "pending";
  }
  if (["approved", "aprobado", "ok"].includes(estado)) {
    return "approved";
  }
  if (["rejected", "rechazado", "denied"].includes(estado)) {
    return "rejected";
  }
  if (["pending", "pendiente", "new"].includes(estado)) {
    return "pending";
  }
  return registro?.verified ? "approved" : "pending";
};

const normalizarProveedorSupabase = (registro) => {
  const displayName = resolverNombreVisibleProveedor(registro);
  const formattedName = limpiarTexto(registro?.formatted_name) || null;
  const onboardingStep = limpiarTexto(registro?.onboarding_step) || null;
  const onboardingStepUpdatedAt =
    normalizarTimestampComoUtc(registro?.onboarding_step_updated_at) || null;
  const nombre = displayName || "Proveedor sin nombre";
  const documentFirstNames = limpiarTextoIdentidad(
    registro?.document_first_names,
  );
  const documentLastNames = limpiarTextoIdentidad(
    registro?.document_last_names,
  );
  const nombreDocumento = [documentFirstNames, documentLastNames]
    .filter(Boolean)
    .join(" ")
    .trim();
  const firstName = documentFirstNames
    ? documentFirstNames.split(/\s+/)[0]
    : null;
  const lastName = documentLastNames || null;
  const fullName = nombreDocumento || formattedName || displayName || null;
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
        .map((item) => ({
          serviceName: limpiarTexto(item.service_name) || null,
          serviceNameNormalized:
            limpiarTexto(item.service_name_normalized) || null,
          rawServiceText: limpiarTexto(item.raw_service_text) || null,
          serviceSummary: limpiarTexto(item.service_summary) || null,
          domainCode: limpiarTexto(item.domain_code) || null,
          categoryName: limpiarTexto(item.category_name) || null,
          classificationConfidence:
            typeof item.classification_confidence === "number"
              ? item.classification_confidence
              : Number.isFinite(Number(item.classification_confidence))
                ? Number(item.classification_confidence)
                : null,
          requiresReview:
            typeof item.requires_review === "boolean"
              ? item.requires_review
              : null,
        }))
        .filter((item) => Boolean(item.serviceName))
    : [];
  const servicesFromRelation = providerServicesDetailed.map(
    (item) => item.serviceName,
  );
  const servicesRaw =
    limpiarTexto(registro?.services) ||
    providerServicesDetailed
      .map((item) => item.rawServiceText || item.serviceName)
      .filter(Boolean)
      .join(" | ") ||
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
  const experienceRange =
    limpiarTexto(registro?.experience_range) ||
    limpiarTexto(registro?.experienceRange) ||
    null;
  const socialMediaUrl =
    limpiarTexto(registro?.social_media_url) ||
    limpiarTexto(registro?.social_media_link) ||
    null;
  const socialMediaType =
    limpiarTexto(registro?.social_media_type) ||
    limpiarTexto(registro?.social_media_platform) ||
    null;
  const facebookUsername = limpiarTexto(registro?.facebook_username) || null;
  const instagramUsername = limpiarTexto(registro?.instagram_username) || null;
  const documentIdNumber = limpiarTextoIdentidad(
    registro?.document_id_number,
    registro?.identity_document_number,
    registro?.id_number,
    registro?.dni_number,
    registro?.cedula_number,
    registro?.cedula,
  );
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
  const identityNotes = construirNotasIdentidad({
    documentFirstNames,
    documentLastNames,
    documentIdNumber,
  });
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
  const approvedBasicAt =
    normalizarTimestampComoUtc(registro?.approved_notified_at) ||
    verificationReviewedAt ||
    registeredAt;
  const certificates = Array.isArray(registro?.provider_certificates)
    ? registro.provider_certificates
        .filter((item) => item && typeof item.file_url === "string")
        .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0))
        .map((item) => ({
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
        .filter(
          (item) => typeof item.fileUrl === "string" && item.fileUrl.length > 0,
        )
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
    displayName,
    formattedName,
    fullName,
    firstName,
    lastName,
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
    servicesAudit: providerServicesDetailed,
    experienceRange,
    socialMediaUrl,
    socialMediaType,
    facebookUsername,
    instagramUsername,
    hasConsent,
    rating,
    onboardingStep,
    onboardingStepUpdatedAt,
    documentFirstNames,
    documentLastNames,
    documentIdNumber,
    documents: {
      dniFront: dniFrontPhotoUrl,
      dniBack: dniBackPhotoUrl,
      face: facePhotoUrl,
    },
    certificates,
    verificationReviewer,
    verificationReviewedAt,
    approvedBasicAt,
    professionalProfileComplete: tienePerfilProfesionalCompleto({
      servicesList,
      experienceRange,
    }),
    identityNotes: identityNotes || null,
  };
};

const normalizarReviewServicioCatalogo = (registro) => {
  if (!registro || typeof registro !== "object") {
    return null;
  }

  const reviewStatus = limpiarTexto(registro?.review_status) || null;
  return {
    id: limpiarTexto(registro?.id) || null,
    providerId: limpiarTexto(registro?.provider_id) || null,
    rawServiceText: limpiarTexto(registro?.raw_service_text) || null,
    serviceName: limpiarTexto(registro?.service_name) || null,
    serviceNameNormalized:
      limpiarTexto(registro?.service_name_normalized) || null,
    suggestedDomainCode: limpiarTexto(registro?.suggested_domain_code) || null,
    proposedCategoryName:
      limpiarTexto(registro?.proposed_category_name) || null,
    proposedServiceSummary:
      limpiarTexto(registro?.proposed_service_summary) || null,
    reviewReason: limpiarTexto(registro?.review_reason) || null,
    reviewStatus,
    assignedDomainCode: limpiarTexto(registro?.assigned_domain_code) || null,
    assignedCategoryName:
      limpiarTexto(registro?.assigned_category_name) || null,
    assignedServiceName: limpiarTexto(registro?.assigned_service_name) || null,
    assignedServiceSummary:
      limpiarTexto(registro?.assigned_service_summary) || null,
    reviewedBy: limpiarTexto(registro?.reviewed_by) || null,
    reviewedAt: normalizarTimestampComoUtc(registro?.reviewed_at) || null,
    reviewNotes: limpiarTexto(registro?.review_notes) || null,
    publishedProviderServiceId:
      limpiarTexto(registro?.published_provider_service_id) || null,
    createdAt: normalizarTimestampComoUtc(registro?.created_at) || null,
    updatedAt: normalizarTimestampComoUtc(registro?.updated_at) || null,
  };
};

const obtenerReviewsServicioCatalogoPorProveedorSupabase = async (
  providerId,
) => {
  if (!supabaseClient || !providerId) {
    return [];
  }

  const encodedId = encodeURIComponent(providerId);
  const ruta = [
    "select=id,provider_id,raw_service_text,service_name,service_name_normalized,suggested_domain_code,proposed_category_name,proposed_service_summary,review_reason,review_status,assigned_domain_code,assigned_category_name,assigned_service_name,assigned_service_summary,reviewed_by,reviewed_at,review_notes,published_provider_service_id,created_at,updated_at",
    `provider_id=eq.${encodedId}`,
    "review_status=eq.pending",
    "order=created_at.desc",
  ].join("&");

  const response = await supabaseClient.get(
    `provider_service_catalog_reviews?${ruta}`,
    {
      headers: {
        Accept: "application/json",
      },
    },
  );

  return Array.isArray(response.data)
    ? response.data
        .map((item) => normalizarReviewServicioCatalogo(item))
        .filter(Boolean)
    : [];
};

const obtenerDetalleProveedorSupabase = async (providerId) => {
  if (!supabaseClient) {
    return null;
  }

  const ruta = construirRutaSupabasePorId(providerId);
  const response = await supabaseClient.get(ruta, {
    headers: {
      Accept: "application/json",
    },
  });
  const registro = Array.isArray(response.data)
    ? response.data[0]
    : normalizarListaProveedores(response.data)[0];

  if (!registro) {
    return null;
  }

  const provider = normalizarProveedorSupabase(registro);
  const serviceReviews =
    provider.id != null
      ? await obtenerReviewsServicioCatalogoPorProveedorSupabase(provider.id)
      : [];
  return {
    ...provider,
    serviceReviews,
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
    "select=*,provider_services(service_name,service_name_normalized,raw_service_text,service_summary,domain_code,category_name,classification_confidence,display_order),provider_certificates(id,file_url,display_order,status,created_at,updated_at)",
  ];

  if (incluirEstado) {
    parametrosBase.push("onboarding_step=eq.pending_verification");
  }

  return `${supabaseProvidersTable}?${parametrosBase.join("&")}`;
};

const construirRutaSupabaseOnboarding = () => {
  const parametrosBase = [
    `limit=${pendingLimit}`,
    `order=onboarding_step_updated_at.desc.nullslast,created_at.desc`,
    "select=*,provider_services(service_name,service_name_normalized,raw_service_text,service_summary,domain_code,category_name,classification_confidence,display_order),provider_certificates(id,file_url,display_order,status,created_at,updated_at)",
    "or=(status.is.null,status.eq.pending)",
    `onboarding_step=in.(${ONBOARDING_STEPS.join(",")})`,
  ];

  return `${supabaseProvidersTable}?${parametrosBase.join("&")}`;
};

const obtenerProveedoresOnboardingSupabase = async () => {
  if (!supabaseClient) {
    return [];
  }

  const ruta = construirRutaSupabaseOnboarding();
  const response = await supabaseClient.get(ruta, {
    headers: {
      Accept: "application/json",
    },
  });
  const lista = Array.isArray(response.data)
    ? response.data.map((item) => normalizarProveedorSupabase(item))
    : normalizarListaProveedores(response.data).map((item) =>
        normalizarProveedorSupabase(item),
      );
  return lista.filter((provider) =>
    ONBOARDING_STEPS.includes(provider.onboardingStep || ""),
  );
};

const obtenerProveedoresPendientesSupabase = async () => {
  if (!supabaseClient) {
    return [];
  }

  const ruta = construirRutaSupabasePendientes(true);
  const response = await supabaseClient.get(ruta, {
    headers: {
      Accept: "application/json",
    },
  });
  const lista = Array.isArray(response.data)
    ? response.data.map((item) => normalizarProveedorSupabase(item))
    : normalizarListaProveedores(response.data).map((item) =>
        normalizarProveedorSupabase(item),
      );
  return lista;
};

const construirRutaSupabasePostRevision = () => {
  const parametrosBase = [
    `limit=${pendingLimit}`,
    `order=created_at.desc`,
    "select=*,provider_services(service_name,service_name_normalized,raw_service_text,service_summary,domain_code,category_name,classification_confidence,display_order),provider_certificates(id,file_url,display_order,status,created_at,updated_at)",
    "status=eq.rejected",
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
    ? response.data.map((item) => normalizarProveedorSupabase(item))
    : normalizarListaProveedores(response.data).map((item) =>
        normalizarProveedorSupabase(item),
      );
  return lista;
};

const construirRutaSupabaseResumenEstadosProveedores = () => {
  const parametrosBase = [
    "limit=5000",
    "order=created_at.asc",
    "select=*,provider_services(service_name,service_name_normalized,raw_service_text,service_summary,domain_code,category_name,classification_confidence,display_order)",
    "status=in.(pending,approved,rejected)",
  ];

  return `${supabaseProvidersTable}?${parametrosBase.join("&")}`;
};

const obtenerResumenEstadosProveedoresSupabase = async () => {
  if (!supabaseClient) {
    return {
      summary: {
        newPending: 0,
        profileComplete: 0,
      },
    };
  }

  const ruta = construirRutaSupabaseResumenEstadosProveedores();
  const response = await supabaseClient.get(ruta, {
    headers: {
      Accept: "application/json",
    },
  });
  const lista = Array.isArray(response.data)
    ? response.data.map((item) => normalizarProveedorSupabase(item))
    : normalizarListaProveedores(response.data).map((item) =>
        normalizarProveedorSupabase(item),
      );

  const summary = {
    newPending: 0,
    profileComplete: 0,
  };

  for (const provider of lista) {
    if (provider.onboardingStep === "pending_verification") {
      summary.newPending += 1;
      continue;
    }

    if (provider.status === "approved") {
      if (provider.professionalProfileComplete) {
        summary.profileComplete += 1;
      }
    }
  }

  return { summary };
};

const construirRutaSupabasePerfilProfesionalIncompleto = () => {
  const parametrosBase = [
    `limit=${pendingLimit}`,
    `order=approved_notified_at.asc.nullslast,created_at.asc`,
    "select=*,provider_services(service_name,service_name_normalized,raw_service_text,service_summary,domain_code,category_name,classification_confidence,display_order),provider_certificates(id,file_url,display_order,status,created_at,updated_at)",
    "status=eq.approved",
  ];

  return `${supabaseProvidersTable}?${parametrosBase.join("&")}`;
};

const obtenerProveedoresPerfilProfesionalIncompletoSupabase = async () => {
  if (!supabaseClient) {
    return [];
  }

  const ruta = construirRutaSupabasePerfilProfesionalIncompleto();
  const response = await supabaseClient.get(ruta, {
    headers: {
      Accept: "application/json",
    },
  });
  const lista = Array.isArray(response.data)
    ? response.data.map((item) => normalizarProveedorSupabase(item))
    : normalizarListaProveedores(response.data).map((item) =>
        normalizarProveedorSupabase(item),
      );

  return lista.filter(esProveedorPerfilProfesionalPendiente).sort((a, b) => {
    const fechaA =
      obtenerFechaNormalizada(a.approvedBasicAt) ||
      obtenerFechaNormalizada(a.registeredAt) ||
      new Date(0);
    const fechaB =
      obtenerFechaNormalizada(b.approvedBasicAt) ||
      obtenerFechaNormalizada(b.registeredAt) ||
      new Date(0);
    return fechaA.getTime() - fechaB.getTime();
  });
};

const construirRutaSupabaseOperativos = () => {
  const parametrosBase = [
    `limit=${pendingLimit}`,
    `order=approved_notified_at.desc.nullslast,created_at.desc`,
    "select=*,provider_services(service_name,service_name_normalized,raw_service_text,service_summary,domain_code,category_name,classification_confidence,display_order),provider_certificates(id,file_url,display_order,status,created_at,updated_at)",
    "status=eq.approved",
  ];

  return `${supabaseProvidersTable}?${parametrosBase.join("&")}`;
};

const obtenerProveedoresOperativosSupabase = async () => {
  if (!supabaseClient) {
    return [];
  }

  const ruta = construirRutaSupabaseOperativos();
  const response = await supabaseClient.get(ruta, {
    headers: {
      Accept: "application/json",
    },
  });
  const lista = Array.isArray(response.data)
    ? response.data.map((item) => normalizarProveedorSupabase(item))
    : normalizarListaProveedores(response.data).map((item) =>
        normalizarProveedorSupabase(item),
      );

  return lista.filter(esProveedorOperativo).sort((a, b) => {
    const fechaA =
      obtenerFechaNormalizada(a.approvedBasicAt) ||
      obtenerFechaNormalizada(a.registeredAt) ||
      new Date(0);
    const fechaB =
      obtenerFechaNormalizada(b.approvedBasicAt) ||
      obtenerFechaNormalizada(b.registeredAt) ||
      new Date(0);
    return fechaB.getTime() - fechaA.getTime();
  });
};

const construirRutaSupabasePorId = (providerId) => {
  const encodedId = encodeURIComponent(providerId);
  return `${supabaseProvidersTable}?id=eq.${encodedId}&select=*,provider_services(service_name,service_name_normalized,raw_service_text,service_summary,domain_code,category_name,classification_confidence,display_order),provider_certificates(id,file_url,display_order,status,created_at,updated_at)`;
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

async function obtenerProveedoresOnboarding(_requestId = null) {
  try {
    return await obtenerProveedoresOnboardingSupabase();
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

async function obtenerProveedoresOperativos(_requestId = null) {
  try {
    return await obtenerProveedoresOperativosSupabase();
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerProveedoresPerfilProfesionalIncompleto(
  _requestId = null,
) {
  try {
    return await obtenerProveedoresPerfilProfesionalIncompletoSupabase();
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function obtenerDetalleProveedor(providerId, _requestId = null) {
  try {
    const id = limpiarTexto(providerId);
    if (!id) {
      return null;
    }

    return await obtenerDetalleProveedorSupabase(id);
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
      status: "approved",
      updated_at: timestamp,
      approved_notified_at: timestamp,
      onboarding_step: "awaiting_menu_option",
      onboarding_step_updated_at: timestamp,
    };

    const datosActualizados = await intentarActualizacionSupabase(
      providerId,
      payloadPrincipal,
      {
        verified: false,
        updated_at: timestamp,
        approved_notified_at: timestamp,
        onboarding_step: "awaiting_menu_option",
        onboarding_step_updated_at: timestamp,
      },
    );

    const registro =
      Array.isArray(datosActualizados) && datosActualizados.length > 0
        ? datosActualizados[0]
        : null;

    const mensaje = "Proveedor aprobado correctamente.";

    const approvalResult = construirMensajeAprobacionProveedor(registro || {});
    const telefonoBruto = registro?.real_phone || registro?.phone;
    const telefonoNotificacion = formatearTelefonoWhatsApp(telefonoBruto);
    if (telefonoNotificacion) {
      await enviarNotificacionWhatsapp({
        to: telefonoNotificacion,
        message: approvalResult.message,
        ui: approvalResult.ui,
        requestId,
      });
    }

    await invalidarCacheProveedor(registro?.phone, requestId);

    return construirRespuestaAccion(providerId, "approved", mensaje, registro);
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

    const rejectionMessage = construirMensajeRechazoProveedor(
      registro || {},
      payload.notes,
    );
    const telefonoRechazoBruto = registro?.real_phone || registro?.phone;
    const telefonoRechazo = formatearTelefonoWhatsApp(telefonoRechazoBruto);
    if (telefonoRechazo) {
      await enviarNotificacionWhatsapp({
        to: telefonoRechazo,
        message: rejectionMessage,
        requestId,
      });
    }

    return construirRespuestaAccion(providerId, "rejected", mensaje, registro);
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function revisarProveedor(providerId, payload = {}, requestId = null) {
  try {
    const estadoSolicitado = limpiarTexto(payload.status);
    const estadoFinal =
      estadoSolicitado && ["approved", "rejected"].includes(estadoSolicitado)
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

    const documentFirstNames = limpiarTexto(
      payload.documentFirstNames || payload.document_first_names,
    );
    const documentLastNames = limpiarTexto(
      payload.documentLastNames || payload.document_last_names,
    );
    const documentIdNumber = limpiarTexto(
      payload.documentIdNumber || payload.document_id_number,
    );
    const identityNotes = construirNotasIdentidad({
      documentFirstNames,
      documentLastNames,
      documentIdNumber,
    });

    if (
      estadoFinal === "approved" &&
      (!documentFirstNames || !documentLastNames || !documentIdNumber)
    ) {
      return {
        providerId,
        status: "pending",
        updatedAt: timestamp,
        message:
          "Completa nombres, apellidos y cédula antes de aprobar el proveedor.",
      };
    }

    if (estadoFinal === "approved") {
      payloadBase.approved_notified_at = timestamp;
      payloadBase.onboarding_step = "awaiting_menu_option";
      payloadBase.onboarding_step_updated_at = timestamp;
    } else if (estadoFinal === "rejected") {
      payloadBase.rejected_notified_at = timestamp;
    }

    if (documentFirstNames) {
      payloadBase.document_first_names = documentFirstNames;
    }
    if (documentLastNames) {
      payloadBase.document_last_names = documentLastNames;
    }
    if (documentIdNumber) {
      payloadBase.document_id_number = documentIdNumber;
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
    if (estadoFinal === "approved") {
      payloadFallback.onboarding_step = "awaiting_menu_option";
      payloadFallback.onboarding_step_updated_at = timestamp;
    }
    if (identityNotes) {
      payloadFallback.notes = payloadBase.notes
        ? `${payloadBase.notes}\n${identityNotes}`
        : identityNotes;
    } else if (payloadBase.notes) {
      payloadFallback.notes = payloadBase.notes;
    }

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
    if (estadoFinal === "approved") {
      const resultado = construirMensajeAprobacionProveedor(
        registro || {
          document_first_names: documentFirstNames,
          document_last_names: documentLastNames,
        },
      );
      mensajeProveedor = resultado.message;
      uiProveedor = resultado.ui;
    } else if (!mensajeProveedor) {
      mensajeProveedor = construirMensajeRechazoProveedor(
        registro || {
          document_first_names: documentFirstNames,
          document_last_names: documentLastNames,
        },
        payload.notes,
      );
    }

    const telefonoRevisarBruto =
      registro?.real_phone || registro?.phone || payload.phone;
    const telefonoRevisar = formatearTelefonoWhatsApp(telefonoRevisarBruto);
    if (telefonoRevisar) {
      await enviarNotificacionWhatsapp({
        to: telefonoRevisar,
        message: mensajeProveedor,
        ui: uiProveedor,
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

async function resetearProveedorOnboarding(providerId, requestId = null) {
  try {
    const id = limpiarTexto(providerId);
    if (!id) {
      return {
        success: false,
        providerId: "",
        message: "providerId es requerido",
      };
    }

    if (!aiProveedoresUrl) {
      return {
        success: false,
        providerId: id,
        message: "Servicio de proveedores no configurado.",
      };
    }

    const headers = {};
    if (requestId) headers["x-request-id"] = requestId;
    if (aiProveedoresInternalToken) {
      headers["x-internal-token"] = aiProveedoresInternalToken;
    }

    const response = await axios.post(
      `${aiProveedoresUrl.replace(/\/$/, "")}/admin/provider-onboarding/${encodeURIComponent(id)}/reset`,
      { headers },
    );
    return response.data;
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function actualizarPerfilProfesional(
  providerId,
  payload = {},
  requestId = null,
) {
  try {
    const id = limpiarTexto(providerId);
    if (!id) {
      return {
        ok: false,
        providerId: "",
        errorReason: "providerId es requerido",
      };
    }

    if (!aiProveedoresUrl) {
      return {
        ok: false,
        providerId: id,
        errorReason: "Servicio de proveedores no configurado.",
      };
    }

    const headers = { "Content-Type": "application/json" };
    if (requestId) headers["x-request-id"] = requestId;
    if (aiProveedoresInternalToken) {
      headers["x-internal-token"] = aiProveedoresInternalToken;
    }

    const response = await axios.post(
      `${aiProveedoresUrl.replace(/\/$/, "")}/internal/admin/providers/professional-profile/update`,
      {
        provider_id: id,
        services: Array.isArray(payload.services) ? payload.services : [],
        experience_range: payload.experienceRange ?? payload.experience_range,
        social_media_url: payload.socialMediaUrl ?? payload.social_media_url,
        social_media_type: payload.socialMediaType ?? payload.social_media_type,
        facebook_username:
          payload.facebookUsername ?? payload.facebook_username,
        instagram_username:
          payload.instagramUsername ?? payload.instagram_username,
      },
      {
        headers,
        timeout: requestTimeoutMs,
      },
    );
    const data = response.data || {};
    return {
      ok: Boolean(data.ok),
      providerId: data.provider_id || data.providerId || id,
      services: Array.isArray(data.services) ? data.services : [],
      experienceRange: data.experience_range || data.experienceRange || null,
      socialMediaUrl: data.social_media_url || data.socialMediaUrl || null,
      socialMediaType: data.social_media_type || data.socialMediaType || null,
      facebookUsername: data.facebook_username || data.facebookUsername || null,
      instagramUsername:
        data.instagram_username || data.instagramUsername || null,
      verified:
        typeof data.verified === "boolean"
          ? data.verified
          : (data.verified ?? null),
      message: data.message || null,
      errorReason: data.error_reason || data.errorReason || null,
    };
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function aprobarReviewServicioCatalogo(
  reviewId,
  payload = {},
  requestId = null,
) {
  try {
    const id = limpiarTexto(reviewId);
    if (!id) {
      return {
        reviewId: "",
        providerId: null,
        reviewStatus: "pending",
        message: "reviewId es requerido",
      };
    }

    if (!aiProveedoresUrl) {
      return {
        reviewId: id,
        providerId: null,
        reviewStatus: "pending",
        message: "Servicio de proveedores no configurado.",
      };
    }

    const headers = { "Content-Type": "application/json" };
    if (requestId) headers["x-request-id"] = requestId;
    if (aiProveedoresInternalToken) {
      headers["x-internal-token"] = aiProveedoresInternalToken;
    }

    const response = await axios.post(
      `${aiProveedoresUrl.replace(/\/$/, "")}/admin/service-governance/reviews/${encodeURIComponent(id)}/approve`,
      payload,
      {
        headers,
        timeout: requestTimeoutMs,
      },
    );
    return response.data;
  } catch (error) {
    throw gestionarErrorAxios(error);
  }
}

async function rechazarReviewServicioCatalogo(
  reviewId,
  payload = {},
  requestId = null,
) {
  try {
    const id = limpiarTexto(reviewId);
    if (!id) {
      return {
        reviewId: "",
        providerId: null,
        reviewStatus: "pending",
        message: "reviewId es requerido",
      };
    }

    if (!aiProveedoresUrl) {
      return {
        reviewId: id,
        providerId: null,
        reviewStatus: "pending",
        message: "Servicio de proveedores no configurado.",
      };
    }

    const headers = { "Content-Type": "application/json" };
    if (requestId) headers["x-request-id"] = requestId;
    if (aiProveedoresInternalToken) {
      headers["x-internal-token"] = aiProveedoresInternalToken;
    }

    const response = await axios.post(
      `${aiProveedoresUrl.replace(/\/$/, "")}/admin/service-governance/reviews/${encodeURIComponent(id)}/reject`,
      payload,
      {
        headers,
        timeout: requestTimeoutMs,
      },
    );
    return response.data;
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
    `${supabaseProvidersTable}?select=id,display_name,document_first_names,document_last_names,phone,city&limit=500&id=in.(${encodedIds})`,
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
      limpiarTexto(provider?.document_first_names) ||
      limpiarTexto(provider?.document_last_names) ||
      limpiarTexto(provider?.display_name) ||
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

async function obtenerResumenEstadosProveedores() {
  try {
    return await obtenerResumenEstadosProveedoresSupabase();
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

module.exports = {
  obtenerProveedoresOnboarding,
  obtenerProveedoresPendientes,
  obtenerProveedoresNuevos,
  obtenerProveedoresOperativos,
  obtenerProveedoresPostRevision,
  obtenerProveedoresPerfilProfesionalIncompleto,
  obtenerDetalleProveedor,
  obtenerResumenEstadosProveedores,
  aprobarProveedor,
  rechazarProveedor,
  revisarProveedor,
  actualizarPerfilProfesional,
  resetearProveedorOnboarding,
  aprobarReviewServicioCatalogo,
  rechazarReviewServicioCatalogo,
  obtenerMonetizacionResumen,
  obtenerMonetizacionProveedores,
  obtenerMonetizacionProveedor,
};
