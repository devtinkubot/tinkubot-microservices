#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");
const axios = require("axios");

function loadEnvFile(envPath) {
  const fullPath = path.resolve(envPath);
  const content = fs.readFileSync(fullPath, "utf8");
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const separator = trimmed.indexOf("=");
    if (separator === -1) continue;
    const key = trimmed.slice(0, separator);
    const value = trimmed.slice(separator + 1);
    if (!(key in process.env)) {
      process.env[key] = value;
    }
  }
}

function toIsoUtc(value) {
  if (!value || typeof value !== "string") return null;
  return /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
}

function parseIso(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function sameIsoMinute(left, right) {
  if (!left && !right) return true;
  const leftDate = parseIso(left);
  const rightDate = parseIso(right);
  if (!leftDate || !rightDate) return false;
  return (
    Math.abs(leftDate.getTime() - rightDate.getTime()) < 60 * 1000
  );
}

function calculateLeadMetrics(events, feedbackById) {
  let hiredYes30d = 0;
  let hiredNo30d = 0;
  let feedbackResponses30d = 0;
  let paidLeads30d = 0;
  let freeLeads30d = 0;
  let billableLeads30d = 0;

  for (const event of events) {
    if (event.is_billable === true) {
      billableLeads30d += 1;
    }

    if (event.quota_source === "paid") {
      paidLeads30d += 1;
    } else if (event.quota_source === "free") {
      freeLeads30d += 1;
    }

    const feedback = feedbackById.get(event.id);
    if (!feedback) continue;
    feedbackResponses30d += 1;
    if (feedback.hired === true) {
      hiredYes30d += 1;
    } else if (feedback.hired === false) {
      hiredNo30d += 1;
    }
  }

  return {
    leadsShared30d: events.length,
    billableLeads30d,
    paidLeads30d,
    freeLeads30d,
    feedbackResponses30d,
    hiredYes30d,
    hiredNo30d,
    feedbackCoverage30d:
      events.length > 0
        ? Number((feedbackResponses30d / events.length).toFixed(4))
        : null,
    hireRateOverSent30d:
      events.length > 0 ? Number((hiredYes30d / events.length).toFixed(4)) : null,
    hireRateOverResponded30d:
      feedbackResponses30d > 0
        ? Number((hiredYes30d / feedbackResponses30d).toFixed(4))
        : null,
  };
}

async function fetchSupabaseRows(baseUrl, headers, query) {
  const response = await axios.get(`${baseUrl}${query}`, { headers });
  return Array.isArray(response.data) ? response.data : [];
}

async function fetchSupabaseRowsPaginated(baseUrl, headers, query, pageSize = 1000) {
  const items = [];
  let offset = 0;

  while (true) {
    const response = await axios.get(
      `${baseUrl}${query}&limit=${pageSize}&offset=${offset}`,
      { headers },
    );
    const page = Array.isArray(response.data) ? response.data : [];
    items.push(...page);
    if (page.length < pageSize) {
      break;
    }
    offset += pageSize;
  }

  return items;
}

async function fetchSupabaseLatest(baseUrl, headers, table, column) {
  const rows = await fetchSupabaseRows(
    baseUrl,
    headers,
    `/${table}?select=${column}&order=${column}.desc.nullslast&limit=1`,
  );
  return toIsoUtc(rows[0]?.[column] ?? null);
}

async function fetchSupabaseReconciliation(statusFilter) {
  const supabaseBase = `${process.env.SUPABASE_URL.replace(/\/$/, "")}/rest/v1`;
  const headers = {
    apikey: process.env.SUPABASE_SERVICE_KEY,
    Authorization: `Bearer ${process.env.SUPABASE_SERVICE_KEY}`,
    Accept: "application/json",
  };

  const walletQuery =
    statusFilter === "all"
      ? "/provider_lead_wallet?select=provider_id,billing_status"
      : `/provider_lead_wallet?select=provider_id,billing_status&billing_status=eq.${statusFilter}`;
  const wallets = await fetchSupabaseRows(supabaseBase, headers, walletQuery);
  const providerIds =
    statusFilter === "all"
      ? null
      : wallets.map((wallet) => `"${wallet.provider_id}"`).join(",");

  const now = Date.now();
  const since7d = new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString();
  const since30d = new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString();

  const eventSelect =
    "select=id,provider_id,created_at,is_billable,quota_source";
  const eventBase7 =
    `/lead_events?${eventSelect}` +
    `&created_at=gte.${encodeURIComponent(since7d)}&order=created_at.desc`;
  const eventBase30 =
    `/lead_events?${eventSelect}` +
    `&created_at=gte.${encodeURIComponent(since30d)}&order=created_at.desc`;

  const scoped7 =
    providerIds && providerIds.length > 0
      ? `${eventBase7}&provider_id=in.(${providerIds})`
      : providerIds === ""
        ? null
        : eventBase7;
  const scoped30 =
    providerIds && providerIds.length > 0
      ? `${eventBase30}&provider_id=in.(${providerIds})`
      : providerIds === ""
        ? null
        : eventBase30;

  const [events7d, events30d, feedbackRows] = await Promise.all([
    scoped7 ? fetchSupabaseRowsPaginated(supabaseBase, headers, scoped7) : [],
    scoped30 ? fetchSupabaseRowsPaginated(supabaseBase, headers, scoped30) : [],
    axios
      .get(
        `${supabaseBase}/lead_feedback?select=lead_event_id,hired,rating,responded_at`,
        { headers },
      )
      .then((r) => r.data),
  ]);

  const eventIds30d = new Set(events30d.map((event) => event.id));
  const feedbackById = new Map(
    feedbackRows
      .filter((row) => eventIds30d.has(row.lead_event_id))
      .map((row) => [row.lead_event_id, row]),
  );
  const leadMetrics = calculateLeadMetrics(events30d, feedbackById);

  return {
    scopeStatus: statusFilter,
    activeWallets: wallets.filter(
      (wallet) => (wallet.billing_status || "active") === "active",
    ).length,
    pausedWallets: wallets.filter(
      (wallet) => wallet.billing_status === "paused_paywall",
    ).length,
    leadsShared7d: events7d.length,
    ...leadMetrics,
    latestWalletUpdateAt: await fetchSupabaseLatest(
      supabaseBase,
      headers,
      "provider_lead_wallet",
      "updated_at",
    ),
    latestLeadEventAt: await fetchSupabaseLatest(
      supabaseBase,
      headers,
      "lead_events",
      "created_at",
    ),
    latestFeedbackResponseAt: await fetchSupabaseLatest(
      supabaseBase,
      headers,
      "lead_feedback",
      "responded_at",
    ),
    latestProviderUpdateAt: await fetchSupabaseLatest(
      supabaseBase,
      headers,
      process.env.SUPABASE_PROVIDERS_TABLE || "providers",
      "updated_at",
    ),
    latestProviderServiceUpdateAt: await fetchSupabaseLatest(
      supabaseBase,
      headers,
      "provider_services",
      "updated_at",
    ),
  };
}

function compareOverviews(bffOverview, sourceOverview) {
  const mismatches = [];
  const numericFields = [
    "activeWallets",
    "pausedWallets",
    "leadsShared7d",
    "leadsShared30d",
    "billableLeads30d",
    "paidLeads30d",
    "freeLeads30d",
    "feedbackResponses30d",
    "hiredYes30d",
    "hiredNo30d",
  ];
  const rateFields = [
    "feedbackCoverage30d",
    "hireRateOverSent30d",
    "hireRateOverResponded30d",
  ];

  for (const field of numericFields) {
    if ((bffOverview[field] ?? null) !== (sourceOverview[field] ?? null)) {
      mismatches.push(`${field}: bff=${bffOverview[field]} source=${sourceOverview[field]}`);
    }
  }

  for (const field of rateFields) {
    if ((bffOverview[field] ?? null) !== (sourceOverview[field] ?? null)) {
      mismatches.push(`${field}: bff=${bffOverview[field]} source=${sourceOverview[field]}`);
    }
  }

  for (const field of [
    "latestWalletUpdateAt",
    "latestLeadEventAt",
    "latestFeedbackResponseAt",
    "latestProviderUpdateAt",
    "latestProviderServiceUpdateAt",
  ]) {
    if (!sameIsoMinute(bffOverview[field], sourceOverview[field])) {
      mismatches.push(`${field}: bff=${bffOverview[field]} source=${sourceOverview[field]}`);
    }
  }

  return mismatches;
}

async function main() {
  loadEnvFile(path.resolve(__dirname, "../../../.env"));
  const providers = require("../bff/providers");

  const scopes = ["all", "active"];
  let hasMismatch = false;

  for (const scope of scopes) {
    const [bffOverview, sourceOverview] = await Promise.all([
      providers.obtenerMonetizacionResumen({ status: scope }),
      fetchSupabaseReconciliation(scope),
    ]);

    const mismatches = compareOverviews(bffOverview, sourceOverview);
    console.log(`\n## Scope: ${scope}`);
    console.log(
      JSON.stringify(
        {
          bffOverview,
          sourceOverview,
          mismatches,
        },
        null,
        2,
      ),
    );

    if (mismatches.length > 0) {
      hasMismatch = true;
    }
  }

  if (hasMismatch) {
    process.exitCode = 1;
    return;
  }

  console.log("\nReconciliation OK: BFF and Supabase are aligned.");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
