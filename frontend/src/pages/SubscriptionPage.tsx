import { useEffect, useMemo, useState } from "react";
import { getToken } from "../lib/api";
import {
  ArrowRight, BadgeCheck, Building2, CalendarDays, Check, CircleHelp,
  Clock3, CreditCard, FileText, Layers3, LoaderCircle, ShieldCheck, Sparkles,
} from "lucide-react";

type Item = {
  id: string;
  code: string;
  name: string;
  description?: string | null;
  item_type: "package" | "addon";
  pricing_model: string;
  currency: string;
  amount: string;
  billing_interval: string;
  features: Record<string, unknown>;
};

type Invoice = {
  id: string;
  invoice_number: string;
  status: string;
  due_at?: string | null;
  currency: string;
  total: string | number;
};

const API = "/api/v1";

async function api(path: string, method = "GET", body?: unknown) {
  const token = getToken();
  const response = await fetch(API + path, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "";
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return data;
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(date);
}

function statusTone(status?: string) {
  if (status === "active" || status === "trialing" || status === "paid") {
    return "border-emerald-400/20 bg-emerald-400/10 text-emerald-300";
  }
  if (status === "past_due" || status === "draft" || status === "open") {
    return "border-amber-400/20 bg-amber-400/10 text-amber-200";
  }
  return "border-white/10 bg-white/[0.04] text-slate-400";
}

function Price({ item }: { item: Item }) {
  return (
    <span className="whitespace-nowrap text-right">
      <strong className="text-base font-semibold tracking-tight text-white">{item.currency} {item.amount}</strong>
      <small className="ml-1 text-xs font-normal text-slate-500">/ {item.billing_interval.replaceAll("_", " ")}</small>
    </span>
  );
}

export default function SubscriptionPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [current, setCurrent] = useState<any>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [packageCode, setPackageCode] = useState("");
  const [addons, setAddons] = useState<string[]>([]);
  const [quote, setQuote] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const packages = useMemo(() => items.filter((item) => item.item_type === "package"), [items]);
  const addonItems = useMemo(() => items.filter((item) => item.item_type === "addon"), [items]);
  const selectedPackage = packages.find((item) => item.code === packageCode);
  const selectedSubscription = current?.subscription;
  const hasScheduledCancellation = Boolean(selectedSubscription?.cancel_at_period_end);
  const canCancel = Boolean(
    selectedSubscription?.id &&
    !["cancelled", "expired"].includes(selectedSubscription.status) &&
    !hasScheduledCancellation
  );

  async function refresh() {
    const [catalogue, subscription, invoiceList] = await Promise.all([
      api("/subscriptions/catalogue"),
      api("/subscriptions/current"),
      api("/subscriptions/invoices"),
    ]);
    const availableItems: Item[] = catalogue.items || [];
    setItems(availableItems);
    setCurrent(subscription);
    setInvoices(invoiceList.invoices || []);
    setPackageCode((previous) =>
      availableItems.some((item) => item.item_type === "package" && item.code === previous)
        ? previous
        : availableItems.find((item) => item.item_type === "package")?.code || ""
    );
  }

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    Promise.all([
      api("/subscriptions/catalogue"),
      api("/subscriptions/current"),
      api("/subscriptions/invoices"),
    ]).then(([catalogue, subscription, invoiceList]) => {
      if (!mounted) return;
      const availableItems: Item[] = catalogue.items || [];
      setItems(availableItems);
      setCurrent(subscription);
      setInvoices(invoiceList.invoices || []);
      setPackageCode(availableItems.find((item) => item.item_type === "package")?.code || "");
    }).catch((e: unknown) => {
      if (mounted) setError(e instanceof Error ? e.message : "Could not load subscription details.");
    }).finally(() => {
      if (mounted) setLoading(false);
    });
    return () => { mounted = false; };
  }, []);

  function toggleAddon(code: string) {
    setAddons((old) => old.includes(code) ? old.filter((item) => item !== code) : [...old, code]);
    setQuote(null);
  }

  async function getQuote() {
    if (!packageCode || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      setQuote(await api("/subscriptions/quote", "POST", { package_code: packageCode, addon_codes: addons }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not calculate your quote.");
    } finally {
      setBusy(false);
    }
  }

  async function cancelSubscription() {
    if (!selectedSubscription?.id || busy || !canCancel) return;
    const message = selectedSubscription.status === "draft"
      ? "Cancel this unpaid plan selection and void its open Rental OS invoice?"
      : "Schedule this subscription to end at the end of the current paid period?";
    if (!window.confirm(message)) return;

    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api(`/subscriptions/${selectedSubscription.id}/cancel`, "POST");
      setNotice(result.notice || "Your cancellation request has been saved.");
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not cancel this subscription.");
    } finally {
      setBusy(false);
    }
  }

  async function choosePlan() {
    if (!packageCode || !quote || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const selection = await api("/subscriptions/select", "POST", {
        package_code: packageCode,
        addon_codes: addons,
      });
      const invoice = await api(`/subscriptions/${selection.subscription_id}/invoice`, "POST");
      setNotice(
        `Rental OS invoice ${invoice.invoice_number} has been created. Payment integration is not enabled yet, so no payment has been taken and this selection is not active.`
      );
      setQuote(null);
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not create your subscription invoice.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="grid min-h-[55vh] place-items-center text-slate-400">
        <div className="flex items-center gap-3 text-sm"><LoaderCircle className="h-5 w-5 animate-spin text-emerald-300" /> Loading your plan details…</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-7 pb-10 text-slate-100">
      <header className="relative overflow-hidden rounded-3xl border border-white/[0.08] bg-[radial-gradient(ellipse_at_top_right,_rgba(16,185,129,0.16),_transparent_48%),linear-gradient(135deg,rgba(15,23,42,0.96),rgba(8,18,31,0.96))] p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-12 -top-20 h-64 w-64 rounded-full border border-emerald-300/10" />
        <div className="pointer-events-none absolute -right-2 -top-10 h-44 w-44 rounded-full border border-emerald-300/[0.07]" />
        <div className="relative max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-300/[0.08] px-3 py-1 text-[11px] font-semibold uppercase tracking-[.18em] text-emerald-200">
            <Sparkles className="h-3.5 w-3.5" /> Your Rental OS workspace
          </div>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">The right tools for every property.</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
            Start with the Basic package, then add capabilities as your portfolio grows. Your tenants pay rent directly to your own payment provider account—Rental OS never holds your rental income.
          </p>
          <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-400">
            <span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-300" /> Your money stays yours</span>
            <span className="inline-flex items-center gap-2"><Layers3 className="h-4 w-4 text-emerald-300" /> Modular packages</span>
            <span className="inline-flex items-center gap-2"><CreditCard className="h-4 w-4 text-emerald-300" /> Transparent platform billing</span>
          </div>
        </div>
      </header>

      {error && (
        <div role="alert" className="flex items-start gap-3 rounded-2xl border border-rose-400/20 bg-rose-400/[0.08] p-4 text-sm text-rose-200">
          <CircleHelp className="mt-0.5 h-4 w-4 shrink-0" /><span>{error}</span>
        </div>
      )}
      {notice && (
        <div role="status" className="flex items-start gap-3 rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.08] p-4 text-sm text-emerald-100">
          <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0" /><span>{notice}</span>
        </div>
      )}

      <section className="grid gap-4 lg:grid-cols-[1.3fr_.7fr]">
        <div className="rounded-2xl border border-white/[0.08] bg-slate-900/60 p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[.16em] text-slate-500">Account overview</p>
              <h2 className="mt-1 text-lg font-semibold text-white">Your current plan</h2>
            </div>
            <span className={`rounded-full border px-3 py-1 text-xs font-medium capitalize ${statusTone(selectedSubscription?.status)}`}>
              {selectedSubscription?.status || "No subscription"}
            </span>
          </div>
          <div className="mt-5 grid gap-5 sm:grid-cols-3">
            <div><p className="text-xs text-slate-500">Account tier</p><p className="mt-1 font-medium text-slate-100">{current?.legacy_tier || "Basic account"}</p></div>
            <div><p className="text-xs text-slate-500">Current period ends</p><p className="mt-1 font-medium text-slate-100">{formatDate(selectedSubscription?.current_period_end)}</p></div>
            <div><p className="text-xs text-slate-500">Trial ends</p><p className="mt-1 font-medium text-slate-100">{formatDate(current?.legacy_trial_ends_at)}</p></div>
          </div>
          {hasScheduledCancellation && (
            <div className="mt-5 flex items-start gap-2 rounded-xl border border-amber-300/20 bg-amber-300/[0.07] p-3 text-sm text-amber-100">
              <Clock3 className="mt-0.5 h-4 w-4 shrink-0" />
              Cancellation is scheduled for {formatDate(selectedSubscription?.current_period_end)}. Your paid access remains in place until then.
            </div>
          )}
        </div>
        <div className="rounded-2xl border border-white/[0.08] bg-slate-900/60 p-5 sm:p-6">
          <div className="flex items-center gap-2 text-slate-400"><Building2 className="h-4 w-4 text-emerald-300" /><span className="text-xs font-semibold uppercase tracking-[.16em]">Built around your portfolio</span></div>
          <p className="mt-3 text-2xl font-semibold tracking-tight text-white">One workspace.</p>
          <p className="mt-1 text-sm text-slate-400">Properties, tenants, rent records and operations stay together as your business grows.</p>
          {canCancel && (
            <button disabled={busy} onClick={cancelSubscription} className="mt-5 text-xs font-medium text-rose-300 underline decoration-rose-300/30 underline-offset-4 hover:text-rose-200 disabled:opacity-40">
              {busy ? "Please wait…" : "Schedule cancellation"}
            </button>
          )}
        </div>
      </section>

      <section>
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div><p className="text-xs font-semibold uppercase tracking-[.16em] text-emerald-300">01 · Foundation</p><h2 className="mt-1 text-xl font-semibold text-white">Choose your base package</h2><p className="mt-1 text-sm text-slate-400">Every workspace starts with a core package.</p></div>
          <span className="text-xs text-slate-500">{packages.length} {packages.length === 1 ? "package" : "packages"} available</span>
        </div>
        {packages.length ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {packages.map((item) => {
              const active = packageCode === item.code;
              return (
                <button key={item.code} type="button" aria-pressed={active} onClick={() => { setPackageCode(item.code); setQuote(null); }} className={`group relative rounded-2xl border p-5 text-left transition duration-200 hover:-translate-y-0.5 ${active ? "border-emerald-300/60 bg-emerald-300/[0.08] shadow-[0_12px_40px_rgba(16,185,129,0.08)]" : "border-white/[0.08] bg-slate-900/50 hover:border-white/20 hover:bg-slate-900/80"}`}>
                  {active && <span className="absolute right-4 top-4 grid h-6 w-6 place-items-center rounded-full bg-emerald-300 text-slate-950"><Check className="h-4 w-4" /></span>}
                  <span className="text-[11px] font-semibold uppercase tracking-[.16em] text-emerald-300">{item.code}</span>
                  <span className="mt-3 block text-lg font-semibold text-white">{item.name}</span>
                  <span className="mt-2 block min-h-10 text-sm leading-5 text-slate-400">{item.description || "Core property-management tools for your business."}</span>
                  <span className="mt-5 block border-t border-white/[0.08] pt-4"><Price item={item} /></span>
                  <span className={`mt-4 inline-flex items-center gap-1 text-xs font-semibold ${active ? "text-emerald-200" : "text-slate-400 group-hover:text-slate-200"}`}>{active ? "Selected package" : "Select package"} <ArrowRight className="h-3.5 w-3.5" /></span>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-white/10 bg-slate-900/30 p-8 text-center">
            <Layers3 className="mx-auto h-7 w-7 text-slate-600" />
            <p className="mt-3 font-medium text-slate-300">Packages are being prepared</p>
            <p className="mt-1 text-sm text-slate-500">There are no priced packages available right now. Please contact Rental OS support.</p>
          </div>
        )}
      </section>

      <section>
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div><p className="text-xs font-semibold uppercase tracking-[.16em] text-emerald-300">02 · Flexibility</p><h2 className="mt-1 text-xl font-semibold text-white">Add optional capabilities</h2><p className="mt-1 text-sm text-slate-400">Choose only the extras your team needs. You can leave this section empty.</p></div>
          <span className="text-xs text-slate-500">{addons.length} selected</span>
        </div>
        {addonItems.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {addonItems.map((item) => {
              const checked = addons.includes(item.code);
              return (
                <label key={item.code} className={`flex cursor-pointer items-start gap-3 rounded-2xl border p-4 transition ${checked ? "border-emerald-300/40 bg-emerald-300/[0.06]" : "border-white/[0.08] bg-slate-900/40 hover:border-white/20"}`}>
                  <input type="checkbox" checked={checked} onChange={() => toggleAddon(item.code)} className="mt-1 h-4 w-4 accent-emerald-300" />
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-start justify-between gap-2"><strong className="text-sm text-white">{item.name}</strong><Price item={item} /></span>
                    <span className="mt-1 block text-xs leading-5 text-slate-400">{item.description || item.pricing_model.replaceAll("_", " ")}</span>
                  </span>
                </label>
              );
            })}
          </div>
        ) : (
          <p className="rounded-2xl border border-dashed border-white/10 p-6 text-sm text-slate-500">No optional add-ons have been published yet.</p>
        )}
      </section>

      <section className="overflow-hidden rounded-3xl border border-emerald-300/20 bg-[linear-gradient(120deg,rgba(6,78,59,0.2),rgba(15,23,42,0.92)_45%)]">
        <div className="grid gap-6 p-5 sm:p-7 lg:grid-cols-[1fr_.85fr]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[.16em] text-emerald-200">03 · Review</p>
            <h2 className="mt-1 text-xl font-semibold text-white">A clear price before you commit.</h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-slate-400">Your quote is calculated from the published catalogue and your current billable property-unit count. Requesting an invoice does not charge you or activate the plan.</p>
            <div className="mt-5 flex flex-wrap gap-3">
              <button disabled={busy || !packageCode} onClick={getQuote} className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/[0.04] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-40">
                {busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />} Calculate my quote
              </button>
              <button disabled={busy || !quote} onClick={choosePlan} className="inline-flex items-center gap-2 rounded-xl bg-emerald-300 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:opacity-40">
                Request subscription invoice <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-5">
            <div className="flex items-center justify-between gap-3"><span className="text-sm font-medium text-slate-300">Quote summary</span><span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] uppercase tracking-wider text-slate-500">Estimate</span></div>
            {quote ? (
              <>
                <p className="mt-4 text-xs text-slate-500">{quote.billing_interval} · {quote.billable_units} billable units</p>
                <p className="mt-1 text-3xl font-semibold tracking-tight text-white">{quote.currency} {quote.total}</p>
                <div className="mt-4 space-y-2 border-t border-white/10 pt-4">
                  {(quote.items || []).map((line: any) => <div key={line.code || line.name} className="flex justify-between gap-3 text-sm"><span className="text-slate-400">{line.name}</span><span className="whitespace-nowrap text-slate-200">{quote.currency} {line.amount}</span></div>)}
                </div>
              </>
            ) : (
              <div className="mt-4 rounded-xl border border-dashed border-white/10 p-5 text-center">
                <CalendarDays className="mx-auto h-6 w-6 text-slate-600" />
                <p className="mt-2 text-sm font-medium text-slate-300">{selectedPackage?.name || "Select a package"}</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">Calculate a quote to see the full price and itemised breakdown here.</p>
              </div>
            )}
          </div>
        </div>
        <div className="border-t border-white/[0.08] px-5 py-3 text-xs text-slate-500 sm:px-7">Rental OS subscription billing is separate from rent collection. Tenant payments continue to settle directly to your configured provider.</div>
      </section>

      <section className="rounded-2xl border border-white/[0.08] bg-slate-900/50 p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><h2 className="text-lg font-semibold text-white">Rental OS invoices</h2><p className="mt-1 text-xs text-slate-500">Platform subscription invoices only—not tenant rent invoices or landlord payment records.</p></div>
          <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-400">{invoices.length} records</span>
        </div>
        {invoices.length ? (
          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead><tr className="border-b border-white/[0.08] text-[11px] uppercase tracking-wider text-slate-500"><th className="pb-3 font-medium">Invoice</th><th className="pb-3 font-medium">Status</th><th className="pb-3 font-medium">Due date</th><th className="pb-3 text-right font-medium">Total</th></tr></thead>
              <tbody>{invoices.map((invoice) => (
                <tr key={invoice.id} className="border-b border-white/[0.05] last:border-0">
                  <td className="py-4 font-medium text-slate-200">{invoice.invoice_number}</td>
                  <td className="py-4"><span className={`rounded-full border px-2.5 py-1 text-[11px] capitalize ${statusTone(invoice.status)}`}>{invoice.status}</span></td>
                  <td className="py-4 text-slate-400">{formatDate(invoice.due_at)}</td>
                  <td className="py-4 text-right font-medium text-white">{invoice.currency} {invoice.total}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : (
          <div className="mt-5 rounded-xl border border-dashed border-white/10 p-6 text-center text-sm text-slate-500">No Rental OS subscription invoices yet.</div>
        )}
      </section>
    </div>
  );
}
