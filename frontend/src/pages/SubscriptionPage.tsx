import { useEffect, useMemo, useState } from "react";
import { getToken } from "../lib/api";

type Item = {
  id: string; code: string; name: string; description?: string | null;
  item_type: "package" | "addon"; pricing_model: string; currency: string;
  amount: string; billing_interval: string; features: Record<string, unknown>;
};

const API = "/api/v1";
async function api(path: string, method = "GET", body?: unknown) {
  const token = getToken();
  const response = await fetch(API + path, {
    method, headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body ? { "Content-Type": "application/json" } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

export default function SubscriptionPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [current, setCurrent] = useState<any>(null);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [packageCode, setPackageCode] = useState("");
  const [addons, setAddons] = useState<string[]>([]);
  const [quote, setQuote] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const packages = useMemo(() => items.filter((item) => item.item_type === "package"), [items]);
  const addonItems = useMemo(() => items.filter((item) => item.item_type === "addon"), [items]);

  async function refresh() {
    const [catalogue, subscription, invoiceList] = await Promise.all([
      api("/subscriptions/catalogue"), api("/subscriptions/current"), api("/subscriptions/invoices"),
    ]);
    setItems(catalogue.items || []);
    setCurrent(subscription);
    setInvoices(invoiceList.invoices || []);
    if (!packageCode && catalogue.items?.length) setPackageCode(catalogue.items.find((x: Item) => x.item_type === "package")?.code || "");
  }

  useEffect(() => { refresh().catch((e) => setError(e.message || "Could not load subscriptions")); }, []);

  function toggleAddon(code: string) {
    setAddons((old) => old.includes(code) ? old.filter((x) => x !== code) : [...old, code]);
    setQuote(null);
  }

  async function getQuote() {
    if (!packageCode) return;
    setBusy(true); setError(""); setNotice("");
    try { setQuote(await api("/subscriptions/quote", "POST", { package_code: packageCode, addon_codes: addons })); }
    catch (e: any) { setError(e.message || "Could not calculate quote"); }
    finally { setBusy(false); }
  }

  async function cancelSubscription() {
    const sub = current?.subscription;
    if (!sub?.id || busy) return;
    if (!window.confirm(sub.status === "draft" ? "Cancel this unpaid plan selection and void its open Rental OS invoice?" : "Schedule this subscription to end at the end of the current paid period?")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api(\`/subscriptions/\${sub.id}/cancel\`, "POST");
      setNotice(result.notice || "Cancellation request saved.");
      await refresh();
    } catch (e: any) { setError(e.message || "Could not cancel subscription"); }
    finally { setBusy(false); }
  }

  async function choosePlan() {
    if (!packageCode) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const selection = await api("/subscriptions/select", "POST", { package_code: packageCode, addon_codes: addons });
      const invoice = await api(`/subscriptions/${selection.subscription_id}/invoice`, "POST");
      setNotice(`Subscription invoice ${invoice.invoice_number} has been created. It is payable to Rental OS; no payment has been taken and your plan is not active yet.`);
      setQuote(null);
      await refresh();
    } catch (e: any) { setError(e.message || "Could not create subscription invoice"); }
    finally { setBusy(false); }
  }

  return (
    <div className="space-y-6 text-slate-100">
      <div><p className="text-xs font-semibold uppercase tracking-[.2em] text-emerald-300">Rental OS account</p><h1 className="mt-1 text-2xl font-semibold">Plan & add-ons</h1><p className="mt-2 max-w-2xl text-sm text-slate-400">Choose the Basic package and add only the tools your business needs. Rental income continues to settle directly to your own payment provider account.</p></div>
      {error && <p role="alert" className="rounded-xl border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>}
      {notice && <p role="status" className="rounded-xl border border-emerald-400/20 bg-emerald-400/10 p-3 text-sm text-emerald-200">{notice}</p>}
      <section className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
        <h2 className="font-semibold">Current subscription</h2>
        <div className="mt-3 flex flex-wrap gap-6 text-sm">
          <div><p className="text-xs text-slate-500">Legacy account tier</p><p className="mt-1 font-medium">{current?.legacy_tier || "—"}</p></div>
          <div><p className="text-xs text-slate-500">Subscription status</p><p className="mt-1 font-medium">{current?.subscription?.status || "No active subscription"}</p></div>
          <div><p className="text-xs text-slate-500">Trial end</p><p className="mt-1 font-medium">{current?.legacy_trial_ends_at ? new Date(current.legacy_trial_ends_at).toLocaleDateString() : "—"}</p></div>
          {current?.subscription?.cancel_at_period_end && <div><p className="text-xs text-amber-300">Cancellation scheduled</p><p className="mt-1 font-medium">{current.subscription.current_period_end ? new Date(current.subscription.current_period_end).toLocaleDateString() : "—"}</p></div>}
          {current?.subscription?.id && !["cancelled", "expired"].includes(current.subscription.status) && <div className="ml-auto"><button disabled={busy || current.subscription.cancel_at_period_end} onClick={cancelSubscription} className="rounded-lg border border-rose-400/30 px-3 py-2 text-xs text-rose-300 disabled:opacity-40">{current.subscription.cancel_at_period_end ? "Cancellation scheduled" : "Cancel subscription"}</button></div>}
        </div>
      </section>
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
          <h2 className="text-lg font-semibold">1. Choose your base package</h2>
          <div className="mt-4 space-y-3">
            {packages.map((item) => <label key={item.code} className={`flex cursor-pointer gap-3 rounded-xl border p-4 ${packageCode === item.code ? "border-emerald-400/50 bg-emerald-400/10" : "border-white/10 bg-slate-950/40"}`}>
              <input type="radio" name="base-package" checked={packageCode === item.code} onChange={() => { setPackageCode(item.code); setQuote(null); }} className="mt-1 accent-emerald-400" />
              <span className="min-w-0 flex-1"><span className="flex flex-wrap items-center justify-between gap-2"><strong>{item.name}</strong><strong>{item.currency} {item.amount} <small className="font-normal text-slate-500">/ {item.billing_interval}</small></strong></span><span className="mt-1 block text-xs text-slate-400">{item.description || "Core Rental OS property-management tools"}</span></span>
            </label>)}
            {!packages.length && <p className="text-sm text-slate-500">No priced packages are currently published. Please contact Rental OS support.</p>}
          </div>
        </section>
        <section className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
          <h2 className="text-lg font-semibold">2. Add optional tools</h2>
          <div className="mt-4 space-y-3">
            {addonItems.map((item) => <label key={item.code} className="flex cursor-pointer items-start gap-3 rounded-xl border border-white/10 bg-slate-950/40 p-4">
              <input type="checkbox" checked={addons.includes(item.code)} onChange={() => toggleAddon(item.code)} className="mt-1 accent-emerald-400" />
              <span className="min-w-0 flex-1"><span className="flex flex-wrap justify-between gap-2"><strong>{item.name}</strong><strong>{item.currency} {item.amount} <small className="font-normal text-slate-500">/ {item.billing_interval}</small></strong></span><span className="mt-1 block text-xs text-slate-400">{item.description || item.pricing_model.replaceAll("_", " ")}</span></span>
            </label>)}
            {!addonItems.length && <p className="text-sm text-slate-500">No optional add-ons are published yet.</p>}
          </div>
        </section>
      </div>
      <section className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
        <h2 className="font-semibold">3. Review and request an invoice</h2>
        <p className="mt-1 text-sm text-slate-400">We calculate the quote from the current catalogue and your active property-unit count. Nothing is charged at this step.</p>
        <div className="mt-4 flex flex-wrap gap-3"><button disabled={busy || !packageCode} onClick={getQuote} className="rounded-lg border border-white/15 px-4 py-2 text-sm hover:bg-white/5 disabled:opacity-40">{busy ? "Working…" : "Calculate quote"}</button><button disabled={busy || !quote} onClick={choosePlan} className="rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40">Confirm selection & issue invoice</button></div>
        {quote && <div className="mt-5 rounded-xl border border-emerald-400/20 bg-emerald-400/5 p-4"><div className="flex flex-wrap justify-between gap-3"><span className="text-sm text-slate-300">Estimated total · {quote.billing_interval}</span><strong className="text-xl">{quote.currency} {quote.total}</strong></div><p className="mt-1 text-xs text-slate-500">{quote.billable_units} billable units counted</p><ul className="mt-3 space-y-1 text-sm">{quote.items.map((line: any) => <li key={line.code || line.name} className="flex justify-between gap-3"><span>{line.name}</span><span>{quote.currency} {line.amount}</span></li>)}</ul></div>}
      </section>
      <section className="rounded-2xl border border-white/10 bg-slate-900/50 p-5">
        <h2 className="font-semibold">Rental OS subscription invoices</h2>
        <p className="mt-1 text-xs text-slate-500">These are platform subscription invoices only, not tenant rent invoices.</p>
        <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[540px] text-left text-sm"><thead className="text-xs text-slate-500"><tr><th className="pb-2">Invoice</th><th className="pb-2">Status</th><th className="pb-2">Due</th><th className="pb-2 text-right">Total</th></tr></thead><tbody>{invoices.map((invoice) => <tr key={invoice.id} className="border-t border-white/5"><td className="py-3">{invoice.invoice_number}</td><td className="py-3 capitalize">{invoice.status}</td><td className="py-3">{invoice.due_at ? new Date(invoice.due_at).toLocaleDateString() : "—"}</td><td className="py-3 text-right">{invoice.currency} {invoice.total}</td></tr>)}</tbody></table>{!invoices.length && <p className="py-4 text-sm text-slate-500">No Rental OS subscription invoices yet.</p>}</div>
      </section>
    </div>
  );
}
