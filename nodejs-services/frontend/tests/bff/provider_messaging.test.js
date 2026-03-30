const test = require("node:test");
const assert = require("node:assert/strict");

const {
  construirMensajeAprobacionProveedor,
  construirMensajeRechazoProveedor,
  resolverNombreCanonicoProveedor,
} = require("../../bff/provider_messaging");

test("resuelve el nombre desde los campos canónicos de supabase", () => {
  const registro = {
    full_name: "Legacy Name",
    document_first_names: "Ana Maria",
    document_last_names: "Perez Lopez",
    display_name: "Nombre Visible",
  };

  assert.equal(
    resolverNombreCanonicoProveedor(registro),
    "Ana Maria Perez Lopez",
  );
});

test("no depende de full_name para construir el mensaje de aprobación", () => {
  const registro = {
    full_name: "",
    document_first_names: "Ana Maria",
    document_last_names: "Perez Lopez",
  };

  const mensaje = construirMensajeAprobacionProveedor(registro);

  assert.match(mensaje.message, /Hola Ana/);
  assert.doesNotThrow(() => construirMensajeAprobacionProveedor(registro));
});

test("usa proveedor como fallback seguro cuando no hay nombres canónicos", () => {
  const mensaje = construirMensajeAprobacionProveedor({});

  assert.match(mensaje.message, /Hola Proveedor/);
});

test("rechazo también usa campos canónicos y no full_name", () => {
  const mensaje = construirMensajeRechazoProveedor(
    {
      full_name: "Legacy Name",
      display_name: "Nombre Visible",
    },
    "datos incompletos",
  );

  assert.match(mensaje, /Hola Nombre Visible/);
  assert.doesNotThrow(() =>
    construirMensajeRechazoProveedor({ full_name: "" }, "motivo"),
  );
});
