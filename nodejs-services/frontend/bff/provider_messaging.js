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

const normalizarNombreCompuesto = (...partes) =>
  partes
    .map((parte) => limpiarTexto(parte))
    .filter(Boolean)
    .join(" ")
    .trim();

const resolverNombreCanonicoProveedor = (registro = {}) => {
  const nombreDocumento = normalizarNombreCompuesto(
    registro.document_first_names,
    registro.document_last_names,
    registro.documentFirstNames,
    registro.documentLastNames,
  );
  const nombreVisible =
    limpiarTexto(registro.display_name) ||
    limpiarTexto(registro.displayName) ||
    limpiarTexto(registro.formatted_name) ||
    limpiarTexto(registro.formattedName);

  return nombreDocumento || nombreVisible || "Proveedor";
};

const construirMensajeAprobacionProveedor = (registro = {}) => {
  const nombreCanonico = resolverNombreCanonicoProveedor(registro);
  const primerNombre = nombreCanonico.split(/\s+/)[0] || "Proveedor";

  return {
    message: [
      `¡Hola ${primerNombre}, ya puedes trabajar!`,
      "",
      "Tu información fue aprobada y ya puedes recibir solicitudes de clientes.",
      "",
      "Si después quieres completar más detalles de tu perfil, podrás hacerlo desde el menú.",
    ].join("\n"),
    ui: {
      type: "buttons",
      id: "provider_basic_approval_v2",
      header_type: "text",
      header_text: "✅ Aprobado",
      footer_text: "Empezar a recibir solicitudes →",
      options: [
        {
          id: "provider_menu_info_profesional",
          title: "Ir al menú",
        },
      ],
    },
  };
};

const construirMensajeRechazoProveedor = (registro = {}, motivo = "") => {
  const nombreCanonico = resolverNombreCanonicoProveedor(registro);
  const safeReason = limpiarTexto(motivo);

  if (nombreCanonico && safeReason) {
    return `❌ Hola ${nombreCanonico}, no pudimos aprobar tu registro básico. Motivo: ${safeReason}. Revisa tus datos y documentos y vuelve a intentarlo.`;
  }
  if (nombreCanonico) {
    return `❌ Hola ${nombreCanonico}, no pudimos aprobar tu registro básico con la información enviada. Revisa tus datos y documentos y vuelve a intentarlo.`;
  }
  if (safeReason) {
    return `❌ No pudimos aprobar tu registro básico. Motivo: ${safeReason}. Revisa tus datos y documentos y vuelve a intentarlo.`;
  }
  return "❌ No pudimos aprobar tu registro básico con la información enviada. Revisa tus datos y documentos y vuelve a intentarlo.";
};

module.exports = {
  construirMensajeAprobacionProveedor,
  construirMensajeRechazoProveedor,
  resolverNombreCanonicoProveedor,
};
