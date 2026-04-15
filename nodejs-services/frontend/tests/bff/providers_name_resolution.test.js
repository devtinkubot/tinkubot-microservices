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
});

const {
  obtenerProveedoresOnboarding,
  obtenerProveedoresPerfilProfesionalIncompleto,
  obtenerDetalleProveedor,
  obtenerResumenEstadosProveedores,
} = require("../../bff/providers");
axios.create = originalCreate;

test("obtenerDetalleProveedor conserva display_name para proveedores nuevos o pendientes", async () => {
  const llamadas = [];
  supabaseGet = async (url) => {
    llamadas.push(url);

    if (url.startsWith("providers?")) {
      return {
        data: [
          {
            id: "provider-1",
            status: "pending",
            display_name: "Ana Maria Pérez",
            formatted_name: "Ana Maria Pérez Lopez",
            document_first_names: "Ana Maria",
            document_last_names: "Perez Lopez",
            full_name: "Nombre legado",
            phone: "593912345678",
            city: "Quito",
          },
        ],
      };
    }

    if (url.startsWith("provider_service_catalog_reviews?")) {
      return { data: [] };
    }

    throw new Error(`Unexpected GET URL: ${url}`);
  };

  try {
    const provider = await obtenerDetalleProveedor("provider-1");

    assert.equal(provider.id, "provider-1");
    assert.equal(provider.name, "Ana Maria Pérez");
    assert.equal(provider.displayName, "Ana Maria Pérez");
    assert.equal(provider.formattedName, "Ana Maria Pérez Lopez");
    assert.equal(provider.fullName, "Ana Maria Pérez");
    assert.equal(provider.documentFirstNames, "Ana Maria");
    assert.equal(provider.documentLastNames, "Perez Lopez");
    assert.equal(provider.contact, "Ana Maria Pérez");
    assert.equal(provider.city, "Quito");
    assert.equal(provider.serviceReviews.length, 0);
    assert.ok(llamadas.some((url) => url.startsWith("providers?")));
    assert.ok(
      llamadas.some((url) =>
        url.startsWith("provider_service_catalog_reviews?"),
      ),
    );
  } finally {
    supabaseGet = async () => {
      throw new Error("Supabase mock not initialized");
    };
  }
});

test("obtenerDetalleProveedor usa document_first_names y document_last_names en operativos", async () => {
  const llamadas = [];
  supabaseGet = async (url) => {
    llamadas.push(url);

    if (url.startsWith("providers?")) {
      return {
        data: [
          {
            id: "provider-2",
            status: "approved",
            display_name: "Proveedor visible legado",
            formatted_name: "Proveedor visible legado",
            document_first_names: "Ana Maria",
            document_last_names: "Perez Lopez",
            full_name: "Nombre legado",
            phone: "593912345678",
            city: "Quito",
          },
        ],
      };
    }

    if (url.startsWith("provider_service_catalog_reviews?")) {
      return { data: [] };
    }

    throw new Error(`Unexpected GET URL: ${url}`);
  };

  try {
    const provider = await obtenerDetalleProveedor("provider-2");

    assert.equal(provider.id, "provider-2");
    assert.equal(provider.name, "Ana Maria Perez Lopez");
    assert.equal(provider.displayName, "Proveedor visible legado");
    assert.equal(provider.fullName, "Ana Maria Perez Lopez");
    assert.equal(provider.documentFirstNames, "Ana Maria");
    assert.equal(provider.documentLastNames, "Perez Lopez");
    assert.equal(provider.contact, "Ana Maria Perez Lopez");
    assert.equal(provider.city, "Quito");
    assert.equal(provider.serviceReviews.length, 0);
    assert.ok(llamadas.some((url) => url.startsWith("providers?")));
  } finally {
    supabaseGet = async () => {
      throw new Error("Supabase mock not initialized");
    };
  }
});

test("obtenerResumenEstadosProveedores toma las cantidades de Nuevos y Operativos", async () => {
  const llamadas = [];
  supabaseGet = async (url) => {
    llamadas.push(url);

    if (url.includes("onboarding_step=in.(pending_verification,review_pending_verification)")) {
      return {
        data: [
          {
            id: "provider-new-1",
            status: "pending",
            display_name: "Proveedor Nuevo 1",
            onboarding_step: "review_pending_verification",
          },
          {
            id: "provider-new-2",
            status: "pending",
            display_name: "Proveedor Nuevo 2",
            onboarding_step: "pending_verification",
          },
        ],
      };
    }

    if (url.includes("status=eq.approved")) {
      return {
        data: [
          {
            id: "provider-op-1",
            status: "approved",
            onboarding_complete: true,
            display_name: "Proveedor Operativo",
            document_first_names: "Ana Maria",
            document_last_names: "Perez Lopez",
            city: "Quito",
            has_consent: true,
            experience_range: "1-3 años",
            provider_services: [{ service_name: "Plomería", display_order: 0 }],
          },
          {
            id: "provider-op-2",
            status: "approved",
            onboarding_complete: false,
            display_name: "Proveedor Incompleto",
            document_first_names: "Ana Maria",
            document_last_names: "Perez Lopez",
            city: "Quito",
            has_consent: true,
            experience_range: "",
            provider_services: [{ service_name: "Electricidad", display_order: 0 }],
          },
        ],
      };
    }

    throw new Error(`Unexpected GET URL: ${url}`);
  };

  try {
    const resumen = await obtenerResumenEstadosProveedores();

    assert.equal(resumen.summary.newPending, 2);
    assert.equal(resumen.summary.profileComplete, 1);
    assert.ok(
      llamadas.some((url) => url.includes("onboarding_step=in.(pending_verification,review_pending_verification)")),
    );
    assert.ok(
      llamadas.some(
        (url) =>
          url.includes("status=eq.approved") &&
          url.includes("onboarding_complete=eq.true"),
      ),
    );
  } finally {
    supabaseGet = async () => {
      throw new Error("Supabase mock not initialized");
    };
  }
});

test("obtenerProveedoresOnboarding incluye onboarding_real_phone en la cola", async () => {
  const llamadas = [];
  supabaseGet = async (url) => {
    llamadas.push(url);

    if (url.includes("onboarding_step=in.")) {
      return {
        data: [
          {
            id: "provider-phone-step",
            status: "pending",
            display_name: "Proveedor Real Phone",
            onboarding_step: "onboarding_real_phone",
          },
        ],
      };
    }

    throw new Error(`Unexpected GET URL: ${url}`);
  };

  try {
    const proveedores = await obtenerProveedoresOnboarding();

    assert.equal(proveedores.length, 1);
    assert.equal(proveedores[0].onboardingStep, "onboarding_real_phone");
    assert.ok(
      llamadas.some((url) => url.includes("onboarding_real_phone")),
    );
    assert.ok(
      llamadas.some((url) => url.includes("onboarding_social_media")),
    );
  } finally {
    supabaseGet = async () => {
      throw new Error("Supabase mock not initialized");
    };
  }
});

test(
  "obtenerProveedoresPerfilProfesionalIncompleto solo incluye aprobados incompletos fuera de onboarding, revisión y operación",
  async () => {
    const llamadas = [];
    supabaseGet = async (url) => {
      llamadas.push(url);

      if (url.startsWith("providers?")) {
        return {
          data: [
            {
              id: "provider-irregular",
              status: "approved",
              onboarding_complete: false,
              display_name: "Proveedor sin nombres",
              city: "Cuenca",
              has_consent: true,
              experience_range: "Más de 10 años",
              provider_services: [{ service_name: "Plomería", display_order: 0 }],
              document_first_names: null,
              document_last_names: null,
            },
            {
              id: "provider-onboarding",
              status: "pending",
              display_name: "Proveedor onboarding",
              onboarding_step: "onboarding_city",
            },
            {
              id: "provider-review",
              status: "pending",
              display_name: "Proveedor revisión",
              onboarding_step: "pending_verification",
            },
            {
              id: "provider-operativo",
              status: "approved",
              onboarding_complete: true,
              display_name: "Proveedor operativo",
              document_first_names: "Ana Maria",
              document_last_names: "Perez Lopez",
              city: "Quito",
              has_consent: true,
              experience_range: "1-3 años",
              provider_services: [{ service_name: "Electricidad", display_order: 0 }],
            },
            {
              id: "provider-rejected",
              status: "rejected",
              onboarding_complete: true,
              display_name: "Proveedor rechazado",
              city: "Loja",
              has_consent: true,
            },
          ],
        };
      }

      throw new Error(`Unexpected GET URL: ${url}`);
    };

    try {
      const proveedores = await obtenerProveedoresPerfilProfesionalIncompleto();

      assert.equal(proveedores.length, 1);
      assert.equal(proveedores[0].id, "provider-irregular");
      assert.equal(proveedores[0].name, "Proveedor sin nombres");
      assert.ok(llamadas.some((url) => url.startsWith("providers?")));
      assert.ok(
        !llamadas.some((url) => url.includes("status=eq.approved")),
      );
    } finally {
      supabaseGet = async () => {
        throw new Error("Supabase mock not initialized");
      };
    }
  },
);
