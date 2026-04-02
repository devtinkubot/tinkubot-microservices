const test = require("node:test");
const assert = require("node:assert/strict");

process.env.AI_PROVEEDORES_URL = "http://ai-proveedores:8002";
process.env.AI_PROVEEDORES_INTERNAL_TOKEN = "token-test";

const axios = require("axios");
const { resetearProveedorOnboarding } = require("../../bff/providers");

test("resetearProveedorOnboarding envía el token interno como header", async () => {
  const llamadas = [];
  const originalPost = axios.post;

  axios.post = async (...args) => {
    llamadas.push(args);
    return { data: { success: true, providerId: "prov-1" } };
  };

  try {
    const resultado = await resetearProveedorOnboarding("prov-1", "req-123");

    assert.deepEqual(resultado, { success: true, providerId: "prov-1" });
    assert.equal(llamadas.length, 1);
    assert.equal(
      llamadas[0][0],
      "http://ai-proveedores:8002/admin/provider-onboarding/prov-1/reset",
    );
    assert.deepEqual(llamadas[0][1], {});
    assert.deepEqual(llamadas[0][2], {
      headers: {
        "x-request-id": "req-123",
        "x-internal-token": "token-test",
      },
    });
  } finally {
    axios.post = originalPost;
  }
});
