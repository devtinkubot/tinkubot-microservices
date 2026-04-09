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
  obtenerMonetizacionResumen,
  obtenerMonetizacionProveedores,
  obtenerMonetizacionProveedor,
} = require("../../bff/providers");
axios.create = originalCreate;

test("obtenerMonetizacionResumen filtra por wallet activa y calcula coberturas operativas", async () => {
  const llamadas = [];
  supabaseGet = async (url) => {
    llamadas.push(url);

    if (url.startsWith("provider_lead_wallet?")) {
      if (url.includes("select=updated_at") && url.includes("limit=1")) {
        return {
          data: [{ updated_at: "2026-04-09T10:00:00Z" }],
        };
      }
      return {
        data: [
          {
            provider_id: "provider-1",
            free_leads_remaining: 2,
            paid_leads_remaining: 3,
            billing_status: "active",
            updated_at: "2026-04-09T10:00:00Z",
          },
        ],
      };
    }

    if (url.startsWith("lead_events?")) {
      if (url.includes("select=created_at") && url.includes("limit=1")) {
        return {
          data: [{ created_at: "2026-04-09T10:00:00Z" }],
        };
      }
      return {
        data: [
          {
            id: "lead-1",
            provider_id: "provider-1",
            created_at: "2026-04-09T10:00:00Z",
            is_billable: true,
            quota_source: "paid",
          },
          {
            id: "lead-2",
            provider_id: "provider-1",
            created_at: "2026-04-08T10:00:00Z",
            is_billable: true,
            quota_source: "free",
          },
        ],
      };
    }

    if (url.startsWith("lead_feedback?")) {
      if (url.includes("select=responded_at") && url.includes("limit=1")) {
        return {
          data: [{ responded_at: "2026-04-09T12:00:00Z" }],
        };
      }
      return {
        data: [
          {
            lead_event_id: "lead-1",
            hired: true,
            rating: 5,
            responded_at: "2026-04-09T12:00:00Z",
          },
        ],
      };
    }

    if (url.startsWith("providers?") && url.includes("select=updated_at")) {
      return {
        data: [{ updated_at: "2026-04-08T08:00:00Z" }],
      };
    }

    if (url.startsWith("provider_services?") && url.includes("select=updated_at")) {
      return {
        data: [{ updated_at: "2026-04-08T09:00:00Z" }],
      };
    }

    throw new Error(`Unexpected GET URL: ${url}`);
  };

  try {
    const resumen = await obtenerMonetizacionResumen({ status: "active" });

    assert.equal(resumen.scopeStatus, "active");
    assert.equal(resumen.activeWallets, 1);
    assert.equal(resumen.pausedWallets, 0);
    assert.equal(resumen.leadsShared7d, 2);
    assert.equal(resumen.leadsShared30d, 2);
    assert.equal(resumen.billableLeads30d, 2);
    assert.equal(resumen.paidLeads30d, 1);
    assert.equal(resumen.freeLeads30d, 1);
    assert.equal(resumen.feedbackResponses30d, 1);
    assert.equal(resumen.feedbackCoverage30d, 0.5);
    assert.equal(resumen.hireRateOverSent30d, 0.5);
    assert.equal(resumen.hireRateOverResponded30d, 1);
    assert.equal(resumen.averageRating30d, 5);
    assert.equal(resumen.latestWalletUpdateAt, "2026-04-09T10:00:00Z");
    assert.equal(resumen.latestLeadEventAt, "2026-04-09T10:00:00Z");
    assert.equal(resumen.latestFeedbackResponseAt, "2026-04-09T12:00:00Z");
    assert.equal(resumen.latestProviderUpdateAt, "2026-04-08T08:00:00Z");
    assert.equal(resumen.latestProviderServiceUpdateAt, "2026-04-08T09:00:00Z");
    assert.equal(resumen.hasRecentLeadEvents30d, true);
    assert.equal(resumen.hasRecentFeedback30d, true);
    assert.ok(
      llamadas.some((url) => url.includes("billing_status=eq.active")),
    );
    assert.ok(
      llamadas.some((url) => url.includes('provider_id=in.("provider-1")')),
    );
  } finally {
    supabaseGet = async () => {
      throw new Error("Supabase mock not initialized");
    };
  }
});

test("obtenerMonetizacionProveedores expone mix free/paid y cobertura por proveedor", async () => {
  supabaseGet = async (url) => {
    if (url.startsWith("provider_lead_wallet?")) {
      if (url.includes("select=updated_at") && url.includes("limit=1")) {
        return {
          data: [{ updated_at: "2026-04-09T10:00:00Z" }],
        };
      }
      return {
        data: [
          {
            provider_id: "provider-2",
            free_leads_remaining: 1,
            paid_leads_remaining: 4,
            billing_status: "paused_paywall",
            updated_at: "2026-04-09T10:00:00Z",
          },
        ],
      };
    }

    if (url.startsWith("providers?")) {
      if (url.includes("select=updated_at")) {
        return {
          data: [{ updated_at: "2026-04-08T08:00:00Z" }],
        };
      }
      return {
        data: [
          {
            id: "provider-2",
            document_first_names: "Ana Maria",
            document_last_names: "Perez",
            phone: "593912345678",
            city: "Cuenca",
          },
        ],
      };
    }

    if (url.startsWith("lead_events?")) {
      if (url.includes("select=created_at") && url.includes("limit=1")) {
        return {
          data: [{ created_at: "2026-04-09T10:00:00Z" }],
        };
      }
      return {
        data: [
          {
            id: "lead-11",
            provider_id: "provider-2",
            created_at: "2026-04-09T10:00:00Z",
            is_billable: true,
            quota_source: "paid",
          },
          {
            id: "lead-12",
            provider_id: "provider-2",
            created_at: "2026-04-08T10:00:00Z",
            is_billable: true,
            quota_source: "free",
          },
          {
            id: "lead-13",
            provider_id: "provider-2",
            created_at: "2026-04-07T10:00:00Z",
            is_billable: false,
            quota_source: null,
          },
        ],
      };
    }

    if (url.startsWith("lead_feedback?")) {
      if (url.includes("select=responded_at") && url.includes("limit=1")) {
        return {
          data: [{ responded_at: "2026-04-09T12:00:00Z" }],
        };
      }
      return {
        data: [
          {
            lead_event_id: "lead-11",
            hired: true,
            rating: 4,
            responded_at: "2026-04-09T12:00:00Z",
          },
          {
            lead_event_id: "lead-12",
            hired: false,
            rating: 3,
            responded_at: "2026-04-08T12:00:00Z",
          },
        ],
      };
    }

    if (url.startsWith("provider_services?") && url.includes("select=updated_at")) {
      return {
        data: [{ updated_at: "2026-04-08T09:00:00Z" }],
      };
    }

    throw new Error(`Unexpected GET URL: ${url}`);
  };

  try {
    const resultado = await obtenerMonetizacionProveedores({
      status: "paused_paywall",
      limit: 10,
      offset: 0,
    });

    assert.equal(resultado.items.length, 1);
    const item = resultado.items[0];
    assert.equal(item.billingStatus, "paused_paywall");
    assert.equal(item.hasWallet, true);
    assert.equal(item.leadsShared30d, 3);
    assert.equal(item.billableLeads30d, 2);
    assert.equal(item.paidLeads30d, 1);
    assert.equal(item.freeLeads30d, 1);
    assert.equal(item.feedbackResponses30d, 2);
    assert.equal(item.feedbackCoverage30d, 0.6667);
    assert.equal(item.hireRateOverSent30d, 0.3333);
    assert.equal(item.averageRating30d, 3.5);
    assert.equal(resultado.pagination.total, 1);
  } finally {
    supabaseGet = async () => {
      throw new Error("Supabase mock not initialized");
    };
  }
});

test("obtenerMonetizacionProveedor no inventa wallets activas cuando no existe wallet", async () => {
  supabaseGet = async (url) => {
    if (url.startsWith("provider_lead_wallet?")) {
      if (url.includes("select=updated_at") && url.includes("limit=1")) {
        return {
          data: [{ updated_at: "2026-04-09T10:00:00Z" }],
        };
      }
      return { data: [] };
    }

    if (url.startsWith("providers?")) {
      if (url.includes("select=updated_at")) {
        return {
          data: [{ updated_at: "2026-04-08T08:00:00Z" }],
        };
      }
      return {
        data: [
          {
            id: "provider-3",
            document_first_names: "Luis",
            document_last_names: "Mena",
            phone: "593987654321",
            city: "Quito",
          },
        ],
      };
    }

    if (url.startsWith("lead_events?")) {
      if (url.includes("select=created_at") && url.includes("limit=1")) {
        return {
          data: [{ created_at: "2026-04-09T10:00:00Z" }],
        };
      }
      return {
        data: [
          {
            id: "lead-21",
            provider_id: "provider-3",
            created_at: "2026-04-09T10:00:00Z",
            is_billable: true,
            quota_source: "paid",
          },
        ],
      };
    }

    if (url.startsWith("lead_feedback?")) {
      if (url.includes("select=responded_at") && url.includes("limit=1")) {
        return { data: [] };
      }
      return { data: [] };
    }

    if (url.startsWith("provider_services?") && url.includes("select=updated_at")) {
      return {
        data: [{ updated_at: "2026-04-08T09:00:00Z" }],
      };
    }

    throw new Error(`Unexpected GET URL: ${url}`);
  };

  try {
    const detalle = await obtenerMonetizacionProveedor("provider-3");

    assert.equal(detalle.providerId, "provider-3");
    assert.equal(detalle.hasWallet, false);
    assert.equal(detalle.billingStatus, "missing");
    assert.equal(detalle.freeLeadsRemaining, 0);
    assert.equal(detalle.paidLeadsRemaining, 0);
    assert.equal(detalle.paidLeads30d, 1);
    assert.equal(detalle.leadsShared30d, 1);
  } finally {
    supabaseGet = async () => {
      throw new Error("Supabase mock not initialized");
    };
  }
});
