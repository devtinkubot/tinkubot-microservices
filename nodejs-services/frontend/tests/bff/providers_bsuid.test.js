const test = require("node:test");
const assert = require("node:assert/strict");

process.env.SUPABASE_URL = "http://supabase.test";
process.env.SUPABASE_SERVICE_KEY = "service-key";
process.env.SUPABASE_PROVIDERS_TABLE = "providers";

const axios = require("axios");

const originalCreate = axios.create;
let supabaseGet = async () => {
  throw new Error("Supabase mock not initialized");
};

axios.create = () => ({
  get: (...args) => supabaseGet(...args),
  patch: async () => ({ data: [] }),
  post: async () => ({ data: [] }),
});

const {
  esIdentificadorMetaNoTelefonico,
  obtenerDetalleProveedor,
} = require("../../bff/providers");
axios.create = originalCreate;

test("esIdentificadorMetaNoTelefonico detecta BSUID tipo EC.401...", () => {
  assert.equal(esIdentificadorMetaNoTelefonico("EC.4017827728517538"), true);
});

test("esIdentificadorMetaNoTelefonico detecta BSUID tipo US.xxx", () => {
  assert.equal(esIdentificadorMetaNoTelefonico("US.987654321098765"), true);
});

test("esIdentificadorMetaNoTelefonico rechaza teléfono normal", () => {
  assert.equal(esIdentificadorMetaNoTelefonico("593959091325"), false);
});

test("esIdentificadorMetaNoTelefonico rechaza WhatsApp ID con @", () => {
  assert.equal(esIdentificadorMetaNoTelefonico("593959091325@s.whatsapp.net"), false);
});

test("esIdentificadorMetaNoTelefonico rechaza número con +", () => {
  assert.equal(esIdentificadorMetaNoTelefonico("+593959091325"), false);
});

test("esIdentificadorMetaNoTelefonico rechaza null/undefined", () => {
  assert.equal(esIdentificadorMetaNoTelefonico(null), false);
  assert.equal(esIdentificadorMetaNoTelefonico(undefined), false);
});

test("esIdentificadorMetaNoTelefonico rechaza string vacío", () => {
  assert.equal(esIdentificadorMetaNoTelefonico(""), false);
});

test("contactPhone usa real_phone cuando phone es BSUID", async () => {
  const llamadas = [];
  supabaseGet = async (url) => {
    llamadas.push(url);
    if (url.startsWith("providers?")) {
      return {
        data: [{
          id: "e5036789-9dfc-43ad-9a26-769bda3b33f1",
          status: "pending",
          display_name: "@DiegoUnkuch",
          phone: "EC.4017827728517538",
          real_phone: "593959091325",
          city: "Quito",
        }],
      };
    }
    if (url.startsWith("provider_service_catalog_reviews?")) {
      return { data: [] };
    }
    throw new Error(`Unexpected GET URL: ${url}`);
  };

  try {
    const provider = await obtenerDetalleProveedor("e5036789-9dfc-43ad-9a26-769bda3b33f1");
    assert.equal(provider.contactPhone, "593959091325");
    assert.equal(provider.realPhone, "593959091325");
    assert.equal(provider.phone, null); // BSUID filtrado
    assert.equal(provider.name, "@DiegoUnkuch");
  } finally {
    supabaseGet = async () => { throw new Error("Supabase mock not initialized"); };
  }
});

test("contactPhone es null cuando phone es BSUID y no hay real_phone", async () => {
  const llamadas = [];
  supabaseGet = async (url) => {
    llamadas.push(url);
    if (url.startsWith("providers?")) {
      return {
        data: [{
          id: "provider-bsuid-only",
          status: "pending",
          display_name: "Proveedor BSUID",
          phone: "EC.4017827728517538",
          real_phone: null,
          city: "Quito",
        }],
      };
    }
    if (url.startsWith("provider_service_catalog_reviews?")) {
      return { data: [] };
    }
    throw new Error(`Unexpected GET URL: ${url}`);
  };

  try {
    const provider = await obtenerDetalleProveedor("provider-bsuid-only");
    assert.equal(provider.contactPhone, null);
    assert.equal(provider.phone, null); // BSUID filtrado
  } finally {
    supabaseGet = async () => { throw new Error("Supabase mock not initialized"); };
  }
});

test("contactPhone normaliza WhatsApp ID con @s.whatsapp.net", async () => {
  const llamadas = [];
  supabaseGet = async (url) => {
    llamadas.push(url);
    if (url.startsWith("providers?")) {
      return {
        data: [{
          id: "provider-whatsapp-id",
          status: "pending",
          display_name: "Proveedor WA",
          phone: "593959091325@s.whatsapp.net",
          real_phone: null,
          city: "Quito",
        }],
      };
    }
    if (url.startsWith("provider_service_catalog_reviews?")) {
      return { data: [] };
    }
    throw new Error(`Unexpected GET URL: ${url}`);
  };

  try {
    const provider = await obtenerDetalleProveedor("provider-whatsapp-id");
    assert.equal(provider.phone, "593959091325@s.whatsapp.net");
    assert.notEqual(provider.contactPhone, null);
  } finally {
    supabaseGet = async () => { throw new Error("Supabase mock not initialized"); };
  }
});

test("contactPhone prioriza real_phone sobre contact_phone y phone", async () => {
  const llamadas = [];
  supabaseGet = async (url) => {
    llamadas.push(url);
    if (url.startsWith("providers?")) {
      return {
        data: [{
          id: "provider-all-phones",
          status: "pending",
          display_name: "Proveedor multi",
          phone: "593991234567",
          real_phone: "593959091325",
          city: "Quito",
        }],
      };
    }
    if (url.startsWith("provider_service_catalog_reviews?")) {
      return { data: [] };
    }
    throw new Error(`Unexpected GET URL: ${url}`);
  };

  try {
    const provider = await obtenerDetalleProveedor("provider-all-phones");
    assert.equal(provider.contactPhone, "593959091325");
    assert.equal(provider.realPhone, "593959091325");
    assert.equal(provider.phone, "593991234567");
  } finally {
    supabaseGet = async () => { throw new Error("Supabase mock not initialized"); };
  }
});
