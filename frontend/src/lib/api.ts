const TOKEN_KEY = "rental_token";

export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function decodeRole(): string | null {
  const t = getToken();
  if (!t) return null;
  try {
    const p = t.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = JSON.parse(atob(p));
    return json.role ?? null;
  } catch {
    return null;
  }
}

async function req(method: string, path: string, body?: any, auth = true) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const t = getToken();
  if (auth && t) headers["Authorization"] = "Bearer " + t;
  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    const detail = e.detail;
    const message = Array.isArray(detail)
      ? detail.map((item: { loc?: unknown[]; msg?: string }) => {
          const field = item.loc?.filter((part) => part !== "body").join(".");
          return field ? `${field}: ${item.msg || "Invalid value"}` : (item.msg || "Invalid value");
        }).join("; ")
      : typeof detail === "string" ? detail : "HTTP " + res.status;
    throw new Error(message);
  }
  return res.json();
}

export const loginOwner = (email: string, password: string) =>
  req("POST", "/api/v1/auth/login", { email, password }, false);
export const registerBusiness = (data: {
  business_name: string;
  owner_full_name: string;
  email: string;
  password: string;
  phone?: string;
}) => req("POST", "/api/v1/auth/register", data, false);
export const loginCaretaker = (slug: string, pin: string) =>
  req("POST", "/api/v1/auth/pin-login", { slug, pin }, false);
export const getBoard = () => req("GET", "/api/v1/dashboard/owner/board");
export const getProperties = () => req("GET", "/api/v1/properties");
export const getUnits = (pid: string) => req("GET", `/api/v1/properties/${pid}/units`);
export const getRooms = (pid: string) => req("GET", `/api/v1/properties/${pid}/rooms`);
export const enroll = (data: any) => req("POST", "/api/v1/tenants/enroll", data);
export const simulate = (invoice_id: string, amount: number) =>
  req("POST", "/api/v1/payments/simulate", { invoice_id, amount });
export const stk = (invoice_id: string, phone: string) =>
  req("POST", "/api/v1/payments/mpesa/stk", { invoice_id, phone });

// ── Books / Invoices / History ──
export const getInvoices = (status?: string) =>
  req("GET", `/api/v1/billing/invoices${status ? `?status=${status}` : ""}`);
export const getInvoiceDetail = (id: string) =>
  req("GET", `/api/v1/billing/invoices/${id}`);
export const getPaymentHistory = () =>
  req("GET", "/api/v1/payments/history");
export const getTenantDetail = (id: string) =>
  req("GET", `/api/v1/tenants/${id}`);
export const createBill = (data: any) =>
  req("POST", "/api/v1/billing/bills", data);

// ── Maintenance ──
export const getMaintenanceSummary = () =>
  req("GET", "/api/v1/maintenance/summary");
export const getTickets = (params: Record<string, any> = {}) => {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") q.set(k, String(v)); });
  const qs = q.toString();
  return req("GET", `/api/v1/maintenance/tickets${qs ? `?${qs}` : ""}`);
};
export const getTicket = (id: string) =>
  req("GET", `/api/v1/maintenance/tickets/${id}`);
export const createTicket = (data: any) =>
  req("POST", "/api/v1/maintenance/tickets", data);
export const updateTicket = (id: string, data: any) =>
  req("PATCH", `/api/v1/maintenance/tickets/${id}`, data);

// ── Expenses ──
export const getExpenses = (params: Record<string, any> = {}) => {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") q.set(k, String(v)); });
  const qs = q.toString();
  return req("GET", `/api/v1/expenses${qs ? `?${qs}` : ""}`);
};
export const getExpenseSummary = (from?: string, to?: string) =>
  req("GET", `/api/v1/expenses/summary${from ? `?from_date=${from}${to ? `&to_date=${to}` : ""}` : ""}`);
export const createExpense = (data: any) =>
  req("POST", "/api/v1/expenses", data);
/** STK push by phone + amount only — used for expense vendor payments (no invoice). */
export const stkDirect = (phone: string, amount: number, description = "Expense Payment") =>
  req("POST", "/api/v1/payments/mpesa/stk-direct", { phone, amount, description });

// ── Reports ──
export const getOwnerStatement = (from?: string, to?: string) =>
  req("GET", `/api/v1/reports/owner-statement${from ? `?from_date=${from}${to ? `&to_date=${to}` : ""}` : ""}`);
export const getCollectionTrend = (months = 6) =>
  req("GET", `/api/v1/reports/collection-trend?months=${months}`);
export const getBooksBundle = (from?: string, to?: string, property_id?: string) => {
  const q = new URLSearchParams();
  if (from) q.set("from_date", from);
  if (to) q.set("to_date", to);
  if (property_id) q.set("property_id", property_id);
  const qs = q.toString();
  return req("GET", `/api/v1/reports/books-bundle${qs ? `?${qs}` : ""}`);
};

export async function exportBooks(from?: string, to?: string, property_id?: string) {
  const q = new URLSearchParams();
  if (from) q.set("from_date", from);
  if (to) q.set("to_date", to);
  if (property_id) q.set("property_id", property_id);
  const qs = q.toString();
  const t = getToken();
  const res = await fetch(`/api/v1/reports/export-books${qs ? `?${qs}` : ""}`, {
    headers: t ? { Authorization: `Bearer ${t}` } : {},
  });
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `books_of_accounts_${from || "all"}_to_${to || "now"}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function downloadCSV(filename: string, rows: (string | number)[][]) {
  const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ── Tenant Portal ──
export const getTenantPortal = (tenantId?: string) =>
  req("GET", `/api/v1/portal/my-data${tenantId ? `?tenant_id=${tenantId}` : ""}`);

// ── Tenants directory ──
export const getTenants = (params: Record<string, any> = {}) => {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") q.set(k, String(v)); });
  const qs = q.toString();
  return req("GET", `/api/v1/tenants${qs ? `?${qs}` : ""}`);
};

// ── Caretaker Payment Recording ──
export const recordPayment = (invoice_id: string, amount: number, method: string = "cash") =>
  req("POST", "/api/v1/payments/record", { invoice_id, amount, method });

// ── Utility billing (tariffs, meter readings, shared-cost apportionment) ──
export const getUtilityRates = (property_id?: string) =>
  req("GET", `/api/v1/billing/utilities/rates${property_id ? `?property_id=${property_id}` : ""}`);
export const saveUtilityRate = (data: any) =>
  req("POST", "/api/v1/billing/utilities/rates", data);
export const getMeterReadings = (params: Record<string, any> = {}) => {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") q.set(k, String(v)); });
  const qs = q.toString();
  return req("GET", `/api/v1/billing/utilities/readings${qs ? `?${qs}` : ""}`);
};
/** Pass `unit_id` for one unit's meter, or `property_id` for the shared meter. */
export const recordMeterReading = (data: any) =>
  req("POST", "/api/v1/billing/utilities/readings", data);
/** Split one shared cost across a property's occupied units. */
export const billSharedUtility = (data: any) =>
  req("POST", "/api/v1/billing/utilities/bill-shared", data);

// ── Monthly Report Dispatch ──
export async function dispatchMonthlyReport(month: string, propertyId?: string): Promise<any> {
  const q = new URLSearchParams({ target_month: month, send_whatsapp: "true" });
  if (propertyId) q.set("property_id", propertyId);
  const t = getToken();
  const res = await fetch(`/api/v1/reports/dispatch-monthly?${q}`, {
    method: "POST",
    headers: t ? { Authorization: `Bearer ${t}` } : {},
  });
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    throw new Error(e.detail || "Dispatch failed");
  }
  return res.json();
}
