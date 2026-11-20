import { useEffect, useMemo, useState } from "react";

const TOKEN_KEY = "rental_os_platform_admin_token";
const API = "/api/v1";

type CatalogItem = {
  id: string; code: string; name: string; description?: string | null;
  item_type: "package" | "addon"; pricing_model: string; active: boolean;
  currency?: string | null; amount?: string | null; included_units?: number | null;
  per_unit_amount?: string | null; effective_from?: string | null;
};

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path: string, token: string, method = "GET", body?: unknown) {
  const response = await fetch(API + path, {
    method,
    headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(data.detail || `Request failed (${response.status})`, response.status);
  return data;
}

export default function PlatformAdminConsole() {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [admin, setAdmin] = useState<any>(null);
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [overview, setOverview] = useState<any>(null);
  const [platformSubscriptions, setPlatformSubscriptions] = useState<any[]>([]);
  const [platformInvoices, setPlatformInvoices] = useState<any[]>([]);
  const [platformPayments, setPlatformPayments] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [busy, setBusy] = useState(false);\n  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [newItem, setNewItem] = useState({ code: "", name: "", item_type: "package", pricing_model: "flat_recurring", description: "", features: "{\n  \n}" });
  const [editItem, setEditItem] = useState({ name: "", description: "", features: "{}", active: true, display_order: 0 });
  const [price, setPrice] = useState({ currency: "KES", billing_interval: "monthly", amount: "0.00", included_units: "0", per_unit_amount: "0.00", effective_from: new Date(Date.now() + 60000).toISOString().slice(0, 16) });

  const selected = useMemo(() => items.find((item) => item.id === selectedId), [items, selectedId]);

  useEffect(() => { if (selected) setEditItem({ name: selected.name, description: selected.description || "", features: JSON.stringify(selected.features || {}, null, 2), active: selected.active, display_order: selected.display_order || 0 }); }, [selected]);

  async function loadCatalogue(activeToken: string) {
    const [profile, catalogue, stats, subscriptions, invoices, payments] = await Promise.all([
      request("/platform-admin/auth/me", activeToken),
      request("/subscriptions/admin/catalogue", activeToken),
      request("/platform-admin/overview", activeToken),
      request("/platform-admin/subscriptions", activeToken),
      request("/platform-admin/invoices", activeToken),
      request("/platform-admin/payments", activeToken),
    ]);
    setAdmin(profile);
    setItems(catalogue.items || []);
    setOverview(stats);
    setPlatformSubscriptions(subscriptions.subscriptions || []);
    setPlatformInvoices(invoices.invoices || []);
    setPlatformPayments(payments.payments || []);
    setSelectedId((current) => current || catalogue.items?.[0]?.id || "");
  }

  useEffect(() => {
    if (!token) return;
    let mounted = true;
    setLoading(true);
    setError("");
    loadCatalogue(token).catch((e: unknown) => {
      if (!mounted) return;
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
        sessionStorage.removeItem(TOKEN_KEY);
        setToken("");
        setAdmin(null);
        setError("Your platform administrator session has expired. Please sign in again.");
      } else {
        setError(e instanceof Error ? e.message : "Could not load platform data. Your session has been kept.");
      }
    }).finally(() => {
      if (mounted) setLoading(false);
    });
    return () => { mounted = false; };
  }, [token]);

  async function login(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const response = await fetch(API + "/platform-admin/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Login failed");
      sessionStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token); setPassword("");
    } catch (e: any) { setError(e.message || "Login failed"); }
    finally { setBusy(false); }
  }

  async function createItem(e: React.FormEvent) {
    e.preventDefault(); if (!token) return;
    setBusy(true); setError(""); setNotice("");
    try {
      let features: Record<string, unknown>;
      try { features = JSON.parse(newItem.features || "{}"); }
      catch { throw new Error("Feature entitlements must be valid JSON."); }
      if (!features || Array.isArray(features) || typeof features !== "object") throw new Error("Feature entitlements must be a JSON object.");
      await request("/subscriptions/admin/catalogue", token, "POST", {
        code: newItem.code, name: newItem.name, item_type: newItem.item_type,
        pricing_model: newItem.pricing_model, description: newItem.description,
        features, display_order: 0,
      });
      setNewItem({ code: "", name: "", item_type: "package", pricing_model: "flat_recurring", description: "", features: "{\n}" });
      const data = await request("/subscriptions/admin/catalogue", token);
      setItems(data.items || []);
      setNotice("Catalogue item created. Add an effective price before landlords can select it.");
    } catch (e: any) { setError(e.message || "Could not create catalogue item"); }
    finally { setBusy(false); }
  }

  async function addPrice(e: React.FormEvent) {
    e.preventDefault(); if (!token || !selectedId) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await request(`/subscriptions/admin/catalogue/${selectedId}/prices`, token, "POST", {
        currency: price.currency, billing_interval: selected?.pricing_model === "one_time" ? "one_time" : price.billing_interval, amount: price.amount,
        included_units: Number(price.included_units), per_unit_amount: price.per_unit_amount,
        effective_from: new Date(price.effective_from).toISOString(),
      });
      const data = await request("/subscriptions/admin/catalogue", token);
      setItems(data.items || []);
      setNotice("Price version saved. Existing subscription price snapshots are unchanged.");
    } catch (e: any) { setError(e.message || "Could not save price version"); }
    finally { setBusy(false); }
  }

  function logout() {
    sessionStorage.removeItem(TOKEN_KEY); setToken(""); setAdmin(null); setItems([]);
    setSelectedId(""); setError(""); setNotice("");
  }

  if (!token) return (
    <main className="min-h-screen bg-[#07111f] text-white flex items-center justify-center p-6">
      <form onSubmit={login} className="w-full max-w-md rounded-3xl border border-white/10 bg-slate-900/80 p-8 shadow-2xl">
        <div className="mb-8 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-emerald-400 text-slate-950 font-black">R</div>
          <div><p className="font-semibold tracking-wide">RENTAL OS</p><p className="text-xs text-slate-400">Platform administration</p></div>
        </div>
        <h1 className="text-2xl font-semibold">Administrator sign in</h1>
        <p className="mt-2 text-sm text-slate-400">This is a separate staff console, not a landlord account.</p>
        <label className="mt-7 block text-sm text-slate-300">Work email</label>
        <input className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3 outline-none focus:border-emerald-400" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <label className="mt-4 block text-sm text-slate-300">Password</label>
        <input className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3 outline-none focus:border-emerald-400" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <p className="mt-4 text-sm text-rose-300">{error}</p>}
        <button disabled={busy} className="mt-6 w-full rounded-xl bg-emerald-400 px-4 py-3 font-semibold text-slate-950 disabled:opacity-50">{busy ? "Signing in…" : "Sign in securely"}</button>
      </form>
    </main>
  );

  return (
    <main className="min-h-screen bg-[#07111f] text-slate-100">
      <header className="border-b border-white/10 bg-slate-950/70 px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div><p className="font-semibold tracking-wide">RENTAL OS <span className="ml-2 text-xs font-normal text-emerald-300">PLATFORM</span></p><p className="text-xs text-slate-500">Subscription catalogue and pricing</p></div>
          <div className="flex items-center gap-4"><span className="hidden text-sm text-slate-400 sm:block">{admin?.full_name || admin?.email}</span><button onClick={logout} className="rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-white/5">Sign out</button></div>
        </div>
      </header>
      <div className="mx-auto max-w-7xl p-6">
        <div className="mb-8"><p className="text-sm text-emerald-300">PLATFORM CONTROL</p><h1 className="mt-1 text-3xl font-semibold">Subscription catalogue</h1><p className="mt-2 max-w-3xl text-sm text-slate-400">Configure the Basic package and optional add-ons. Prices are effective-dated; changes do not rewrite existing subscription snapshots.</p></div>
        {error && <p role="alert" className="mb-4 rounded-xl border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>}
        {notice && <p role="status" className="mb-4 rounded-xl border border-emerald-400/20 bg-emerald-400/10 p-3 text-sm text-emerald-200">{notice}</p>}
        <section className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["Businesses", overview?.businesses ?? "—"],
            ["Active subscriptions", overview?.active_subscriptions ?? "—"],
            ["Trials", overview?.trialing_subscriptions ?? "—"],
            ["Open platform invoices", overview?.open_subscription_invoices ?? "—"],
          ].map(([label, value]) => <div key={label} className="rounded-2xl border border-white/10 bg-slate-900/60 p-4"><p className="text-xs text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold">{value}</p></div>)}
        </section>
        <section className="mb-6 grid gap-6 xl:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-5"><h2 className="font-semibold">Recent subscriptions</h2><div className="mt-3 space-y-2">{platformSubscriptions.slice(0, 6).map((sub) => <div key={sub.id} className="flex items-center justify-between gap-3 border-b border-white/5 py-2 text-sm"><span className="min-w-0"><strong className="block truncate">{sub.business_name}</strong><span className="text-xs text-slate-500">{sub.billing_interval} · {sub.currency}</span></span><span className="rounded-full bg-white/5 px-2 py-1 text-xs capitalize text-slate-300">{sub.status}</span></div>)}{!platformSubscriptions.length && <p className="text-sm text-slate-500">No subscriptions recorded yet.</p>}</div></div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-5"><h2 className="font-semibold">Recent platform invoices</h2><div className="mt-3 space-y-2">{platformInvoices.slice(0, 6).map((invoice) => <div key={invoice.id} className="flex items-center justify-between gap-3 border-b border-white/5 py-2 text-sm"><span className="min-w-0"><strong className="block truncate">{invoice.business_name}</strong><span className="text-xs text-slate-500">{invoice.invoice_number}</span></span><span className="text-right"><strong>{invoice.currency} {invoice.total}</strong><span className="block text-xs capitalize text-slate-500">{invoice.status}</span></span></div>)}{!platformInvoices.length && <p className="text-sm text-slate-500">No platform invoices yet.</p>}</div></div>
        </section>
        <section className="mb-6 rounded-2xl border border-white/10 bg-slate-900/60 p-5"><h2 className="font-semibold">Platform subscription receipts</h2><p className="mt-1 text-xs text-slate-500">Only verified Rental OS subscription payments appear here; landlord rent collections are excluded.</p><div className="mt-3 flex flex-wrap gap-3">{platformPayments.slice(0, 6).map((payment) => <div key={payment.id} className="rounded-xl border border-white/10 bg-slate-950/50 px-3 py-2"><p className="text-sm font-medium">{payment.currency} {payment.amount}</p><p className="text-xs text-slate-500">{payment.business_name} · ••••{payment.reference_suffix}</p></div>)}{!platformPayments.length && <p className="text-sm text-slate-500">No platform subscription payments received.</p>}</div></section>
        <div className="grid gap-6 lg:grid-cols-[1.1fr_.9fr]">
          <section className="rounded-2xl border border-white/10 bg-slate-900/60 p-5">
            <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">Current catalogue</h2><span className="text-xs text-slate-500">{items.length} items</span></div>
            <div className="space-y-3">
              {items.map((item) => <button key={item.id} onClick={() => setSelectedId(item.id)} className={`w-full rounded-xl border p-4 text-left transition ${selectedId === item.id ? "border-emerald-400/60 bg-emerald-400/10" : "border-white/10 bg-slate-950/50 hover:border-white/20"}`}>
                <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-medium">{item.name}</span><span className="rounded-full bg-white/5 px-2 py-1 text-[10px] uppercase tracking-wide text-slate-400">{item.item_type} · {item.pricing_model}</span></div>
                <p className="mt-1 text-xs text-slate-500">{item.code} · {item.amount ? `${item.currency} ${item.amount} / ${item.billing_interval}` : "Price not configured"}</p>
              </button>)}
              {!items.length && <p className="rounded-xl border border-dashed border-white/10 p-6 text-sm text-slate-500">No catalogue items yet. Create your Basic package first.</p>}
            </div>
          </section>
          <div className="space-y-6">
            <form onSubmit={createItem} className="rounded-2xl border border-white/10 bg-slate-900/60 p-5">
              <h2 className="text-lg font-semibold">Create package or add-on</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <input required placeholder="Code e.g. basic" value={newItem.code} onChange={(e) => setNewItem({ ...newItem, code: e.target.value })} className="rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm" />
                <input required placeholder="Display name" value={newItem.name} onChange={(e) => setNewItem({ ...newItem, name: e.target.value })} className="rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm" />
                <select value={newItem.item_type} onChange={(e) => setNewItem({ ...newItem, item_type: e.target.value, pricing_model: e.target.value === "package" && newItem.pricing_model === "one_time" ? "flat_recurring" : newItem.pricing_model })} className="rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm"><option value="package">Base package</option><option value="addon">Optional add-on</option></select>
                <select value={newItem.pricing_model} onChange={(e) => setNewItem({ ...newItem, pricing_model: e.target.value })} className="rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm"><option value="flat_recurring">Flat recurring</option><option value="per_billable_unit">Per billable unit</option><option value="one_time" disabled={newItem.item_type === "package"}>One time</option></select>
                <textarea placeholder="Description (optional)" value={newItem.description} onChange={(e) => setNewItem({ ...newItem, description: e.target.value })} className="min-h-20 rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm sm:col-span-2" />
                <label className="text-xs text-slate-400 sm:col-span-2">Feature entitlements (JSON)<textarea value={newItem.features} onChange={(e) => setNewItem({ ...newItem, features: e.target.value })} placeholder={'{"reports_advanced": true, "staff_limit": 5}'} className="mt-1 min-h-24 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 font-mono text-xs text-white" /></label>
              </div>
              <button disabled={busy} className="mt-4 rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50">Create catalogue item</button>
            </form>
            <form onSubmit={async (e) => {
              e.preventDefault(); if (!token || !selectedId) return;
              setBusy(true); setError(""); setNotice("");
              try {
                let features: Record<string, unknown>;
                try { features = JSON.parse(editItem.features || "{}"); }
                catch { throw new Error("Feature entitlements must be valid JSON."); }
                if (!features || Array.isArray(features) || typeof features !== "object") throw new Error("Feature entitlements must be a JSON object.");
                await request(`/subscriptions/admin/catalogue/${selectedId}`, token, "PUT", {
                  name: editItem.name, description: editItem.description, features,
                  active: editItem.active, display_order: Number(editItem.display_order),
                });
                const data = await request("/subscriptions/admin/catalogue", token);
                setItems(data.items || []);
                setNotice("Catalogue item updated.");
              } catch (e: any) { setError(e.message || "Could not update catalogue item"); }
              finally { setBusy(false); }
            }} className="rounded-2xl border border-white/10 bg-slate-900/60 p-5">
              <h2 className="text-lg font-semibold">Edit selected item</h2>
              <p className="mt-1 text-xs text-slate-500">Deactivating an item prevents new selections; existing snapshots remain intact.</p>
              <div className="mt-4 space-y-3">
                <input required minLength={2} value={editItem.name} onChange={(e) => setEditItem({ ...editItem, name: e.target.value })} placeholder="Display name" className="w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm" />
                <textarea value={editItem.description} onChange={(e) => setEditItem({ ...editItem, description: e.target.value })} placeholder="Description" className="min-h-16 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm" />
                <label className="block text-xs text-slate-400">Feature entitlements (JSON)<textarea value={editItem.features} onChange={(e) => setEditItem({ ...editItem, features: e.target.value })} className="mt-1 min-h-24 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 font-mono text-xs text-white" /></label>
                <div className="flex flex-wrap items-center gap-4"><label className="text-xs text-slate-400">Display order<input type="number" value={editItem.display_order} onChange={(e) => setEditItem({ ...editItem, display_order: Number(e.target.value) })} className="mt-1 block w-24 rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white" /></label><label className="mt-4 flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={editItem.active} onChange={(e) => setEditItem({ ...editItem, active: e.target.checked })} /> Active for new selections</label></div>
              </div>
              <button disabled={busy || !selectedId} className="mt-4 rounded-lg border border-white/15 px-4 py-2 text-sm disabled:opacity-40">Save catalogue changes</button>
            </form>
            <form onSubmit={addPrice} className="rounded-2xl border border-white/10 bg-slate-900/60 p-5">
              <h2 className="text-lg font-semibold">Add price version</h2>
              <label className="mt-4 block text-xs text-slate-400">Catalogue item</label>
              <select required value={selectedId} onChange={(e) => setSelectedId(e.target.value)} className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm"><option value="">Select item</option>{items.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.code})</option>)}</select>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <label className="text-xs text-slate-400">Currency<input required maxLength={3} value={price.currency} onChange={(e) => setPrice({ ...price, currency: e.target.value.toUpperCase() })} className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white" /></label>
                <label className="text-xs text-slate-400">Base amount<input required type="number" min="0" step="0.01" value={price.amount} onChange={(e) => setPrice({ ...price, amount: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white" /></label>
                {selected?.pricing_model !== "one_time" && <label className="text-xs text-slate-400">Billing interval<select value={price.billing_interval} onChange={(e) => setPrice({ ...price, billing_interval: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"><option value="monthly">Monthly</option><option value="quarterly">Quarterly</option><option value="annual">Annual</option></select></label>}
                {selected?.pricing_model === "per_billable_unit" && <><label className="text-xs text-slate-400">Included units<input type="number" min="0" value={price.included_units} onChange={(e) => setPrice({ ...price, included_units: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white" /></label><label className="text-xs text-slate-400">Per extra unit<input type="number" min="0" step="0.01" value={price.per_unit_amount} onChange={(e) => setPrice({ ...price, per_unit_amount: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white" /></label></>}
                <label className="col-span-2 text-xs text-slate-400">Effective from<input required type="datetime-local" value={price.effective_from} onChange={(e) => setPrice({ ...price, effective_from: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white" /></label>
              </div>
              <button disabled={busy || !selectedId} className="mt-4 rounded-lg border border-emerald-400/40 px-4 py-2 text-sm font-semibold text-emerald-300 disabled:opacity-40">Save effective price</button>
              <p className="mt-3 text-xs text-slate-500">A price cannot be backdated over an existing version. No tenant rent settings are changed here.</p>
            </form>
          </div>
        </div>
      </div>
    </main>
  );
}
