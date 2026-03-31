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

const resolverPrimerNombreCanonicoProveedor = (registro = {}) => {
  const nombreDocumento = normalizarNombreCompuesto(
    registro.document_first_names,
    registro.documentFirstNames,
  );
  const primerNombre = limpiarTexto(nombreDocumento)?.split(/\s+/)?.[0];
  return primerNombre || "Proveedor";
};

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
  const primerNombre = resolverPrimerNombreCanonicoProveedor(registro);

  return {
    message: [
      `Bienvenido ${primerNombre}.`,
      "",
      "*Tu cuenta fue aprobada.*",
      "El sistema ya habilitó tu acceso para recibir solicitudes.",
      "",
      "Presiona *Menú* para ver opciones.",
    ].join("\n"),
    ui: {
      type: "template",
      id: "provider_approval_v1",
      template_name: "provider_approval_v1",
      template_language: "es",
      template_components: [
        {
          type: "header",
          parameters: [
            {
              type: "text",
              text: primerNombre,
            },
          ],
        },
        {
          type: "button",
          sub_type: "quick_reply",
          index: "0",
          parameters: [
            {
              type: "payload",
              payload: "menu",
            },
          ],
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
  resolverPrimerNombreCanonicoProveedor,
};
