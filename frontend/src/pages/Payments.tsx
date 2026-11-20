import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Search, CreditCard, DollarSign, MessageSquare, CalendarDays,
  Eye, Play, Loader2, ReceiptText, ArrowDownLeft, Wallet,
} from "lucide-react";
import { getPaymentHistory, getInvoices, runRent } from "../lib/api";
import {
  Card, PageHeader, Badge, EmptyState, StatCard, money,
} from "../components/ui";
import TransactionMessageModal from "../components/TransactionMessageModal";

type Tab = "payments" | "invoices";

export default function Payments() {
  const [payments, setPayments] = useState<any[]>([]);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<Tab>("payments");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [messagePaymentId, setMessagePaymentId] = useState<string | null>(null);
  const [rentMonth, setRentMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });
  const [rentBusy, setRentBusy] = useState(false);
  const [rentNotice, setRentNotice] = useState("");
  const [rentError, setRentError] = useState("");

  const loadData = useCallback(async () => {
    setLoadError("");
    const [paymentResult, invoiceResult] = await Promise.allSettled([
      getPaymentHistory(),
      getInvoices(),
    ]);
    if (paymentResult.status === "fulfilled") {
      setPayments(Array.isArray(paymentResult.value?.payments) ? paymentResult.value.payments : []);
    }
    if (invoiceResult.status === "fulfilled") {
      setInvoices(Array.isArray(invoiceResult.value?.invoices) ? invoiceResult.value.invoices : []);
    }
    const errors = [paymentResult, invoiceResult]
      .filter((r): r is PromiseRejectedResult => r.status === "rejected")
      .map((r) => r.reason?.message || "A financial record could not be loaded.");
    if (errors.length) setLoadError(errors.join(" "));
    setLoading(false);
  }, []);

  useEffect(() => { void loadData(); }, [loadData]);

  const monthLabel = useMemo(() => {
    const [year, month] = rentMonth.split("-").map(Number);
    return year && month
      ? new Date(year, month - 1, 1).toLocaleString("en-KE", { month: "long", year: "numeric" })
      : rentMonth;
  }, [rentMonth]);

  const runMonthlyRent = async (dryRun: boolean) => {
    const [year, month] = rentMonth.split("-").map(Number);
    if (!year || !month || month < 1 || month > 12) {
      setRentError("Choose a valid billing month.");
      return;
    }
    if (!dryRun && !window.confirm(
      `Raise rent invoices for ${monthLabel}? Leases already billed for the month are skipped.`
    )) return;

    setRentBusy(true);
    setRentNotice("");
    setRentError("");
    try {
      const result = await runRent(year, month, dryRun);
      const created = result.created_count ?? 0;
      const skipped = result.skipped_count ?? 0;
      const invoiceLabel = `${created} invoice${created === 1 ? "" : "s"}`;
      const leaseLabel = `${skipped} lease${skipped === 1 ? "" : "s"}`;
      const total = `KES ${money(result.total_billed ?? 0)}`;
      setRentNotice(dryRun
        ? `Preview only: ${invoiceLabel} · ${total}. ${leaseLabel} already billed. No records were written.`
        : `${invoiceLabel} raised · ${total}. ${leaseLabel} already billed.`);
      if (!dryRun) await loadData();
    } catch (error) {
      setRentError((error as Error).message || "The rent run could not be completed.");
    } finally {
      setRentBusy(false);
    }
  };

  const query = search.trim().toLowerCase();
  const filteredPayments = payments.filter((p) =>
    [p.tenant_name, p.unit_number, p.reference, p.method]
      .some((value) => String(value || "").toLowerCase().includes(query))
  );
  const filteredInvoices = invoices.filter((inv) =>
    [inv.tenant_name, inv.unit_number, inv.invoice_type, inv.status]
      .some((value) => String(value || "").toLowerCase().includes(query))
  );

  const totalCollected = payments.reduce((sum, p) => sum + Number(p.amount || 0), 0);
  const totalBilled = invoices.reduce((sum, inv) => sum + Number(inv.amount || 0), 0);
  const totalOutstanding = invoices.reduce((sum, inv) => sum + Number(inv.balance || 0), 0);
  const paidInvoices = invoices.filter((inv) => inv.status === "paid").length;
  const outstandingInvoices = invoices.filter((inv) => Number(inv.balance || 0) > 0).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Payments & billing"
        sub="Track rent collections, reconcile transactions and manage monthly invoices"
        actions={
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              aria-label="Search financial records"
              placeholder="Tenant, unit, reference…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="w-full min-h-11 bg-[#0c1a28] border border-white/10 rounded-xl pl-10 pr-3 py-2.5 text-sm text-slate-200 outline-none transition focus:border-emerald-300/50 focus:ring-2 focus:ring-emerald-300/10 placeholder:text-slate-600"
            />
          </div>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        <StatCard icon={<ArrowDownLeft className="w-4 h-4" />} label="Recorded collections" value={`KES ${money(totalCollected)}`} color="emerald" sub={`${payments.length} recorded transactions`} />
        <StatCard icon={<ReceiptText className="w-4 h-4" />} label="Invoices raised" value={`KES ${money(totalBilled)}`} color="sky" sub={`${invoices.length} invoices · ${paidInvoices} paid`} />
        <StatCard icon={<Wallet className="w-4 h-4" />} label="Outstanding balance" value={`KES ${money(totalOutstanding)}`} color="rose" sub={`${outstandingInvoices} invoices with a balance`} />
      </div>

      <Card className="p-4 sm:p-5" hover={false}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Financial activity</h2>
            <p className="text-xs text-slate-500 mt-1">Switch between incoming transactions and tenant invoices</p>
          </div>
          <div className="grid grid-cols-2 gap-1 rounded-xl bg-slate-950/70 border border-white/[0.06] p-1">
            {(["payments", "invoices"] as const).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setTab(item)}
                aria-pressed={tab === item}
                className={`min-h-10 px-4 rounded-lg text-xs font-semibold transition ${
                  tab === item
                    ? "bg-emerald-400/12 text-emerald-200 border border-emerald-300/20"
                    : "text-slate-500 border border-transparent hover:text-slate-200"
                }`}
              >
                {item === "payments" ? `Transactions · ${payments.length}` : `Invoices · ${invoices.length}`}
              </button>
            ))}
          </div>
        </div>

        {tab === "invoices" && (
          <div className="mt-5 rounded-2xl border border-sky-300/10 bg-gradient-to-br from-sky-300/[0.06] to-transparent p-4 sm:p-5">
            <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4">
              <div className="flex items-start gap-3 min-w-0">
                <div className="w-10 h-10 shrink-0 rounded-xl bg-sky-300/10 border border-sky-300/10 flex items-center justify-center">
                  <CalendarDays className="w-5 h-5 text-sky-200" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">Monthly rent run</h3>
                  <p className="text-xs text-slate-400 mt-1 max-w-xl">
                    Preview invoices before raising them. Leases already billed for the selected month are skipped, so the run can be safely repeated.
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(150px,1fr)_auto_auto] gap-2 w-full xl:w-auto">
                <input
                  aria-label="Rent billing month"
                  type="month"
                  value={rentMonth}
                  onChange={(event) => {
                    setRentMonth(event.target.value);
                    setRentNotice("");
                    setRentError("");
                  }}
                  className="min-h-10 bg-slate-950/70 border border-white/10 focus:border-sky-300/40 rounded-xl px-3 py-2 text-sm text-white outline-none"
                />
                <button
                  type="button"
                  onClick={() => void runMonthlyRent(true)}
                  disabled={rentBusy}
                  className="inline-flex items-center justify-center gap-2 min-h-10 px-4 rounded-xl text-xs font-semibold bg-white/[0.05] text-slate-200 border border-white/10 hover:bg-white/[0.09] disabled:opacity-50 transition"
                >
                  {rentBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
                  Preview
                </button>
                <button
                  type="button"
                  onClick={() => void runMonthlyRent(false)}
                  disabled={rentBusy}
                  className="inline-flex items-center justify-center gap-2 min-h-10 px-4 rounded-xl text-xs font-semibold bg-emerald-300 text-slate-950 hover:bg-emerald-200 disabled:opacity-50 transition"
                >
                  {rentBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  Raise invoices
                </button>
              </div>
            </div>
            {(rentNotice || rentError) && (
              <div role={rentError ? "alert" : "status"} className={`mt-4 rounded-xl px-3 py-2.5 text-xs ${rentError
                ? "bg-rose-400/10 border border-rose-300/15 text-rose-200"
                : "bg-emerald-300/10 border border-emerald-300/15 text-emerald-200"}`}>
                {rentError || rentNotice}
              </div>
            )}
          </div>
        )}

        {loadError && (
          <div role="alert" className="mt-4 rounded-xl border border-rose-300/20 bg-rose-300/[0.06] px-4 py-3 text-xs text-rose-200">
            Some financial data could not be loaded: {loadError}
          </div>
        )}

        {loading ? (
          <div className="mt-5 space-y-2">
            {[1, 2, 3].map((n) => <div key={n} className="h-16 rounded-xl bg-white/[0.025] animate-pulse" />)}
          </div>
        ) : tab === "payments" ? (
          filteredPayments.length === 0 ? (
            <div className="mt-5">
              <EmptyState
                icon={<CreditCard className="w-10 h-10" />}
                text={query ? "No transactions match this search" : "No transactions recorded yet"}
                sub={query ? "Try another tenant, unit or payment reference." : "When tenant payments are recorded, they will appear here."}
              />
            </div>
          ) : (
            <div className="mt-5 space-y-2">
              {filteredPayments.map((payment, index) => (
                <motion.article
                  key={payment.id}
                  initial={{ opacity: 0, y: 7 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(index * 0.02, 0.18) }}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 sm:px-4 py-3 hover:border-emerald-300/15 transition"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 shrink-0 rounded-xl bg-emerald-300/10 border border-emerald-300/10 flex items-center justify-center">
                      <DollarSign className="w-4 h-4 text-emerald-200" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-sm font-semibold text-slate-100 truncate">{payment.tenant_name || "Tenant payment"}</h3>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1 text-[11px] text-slate-500">
                        <span>Unit {payment.unit_number || "—"}</span>
                        <span>·</span>
                        <span className="capitalize">{payment.method || "Unspecified method"}</span>
                        {payment.reference && <><span>·</span><span className="font-mono truncate max-w-36">{payment.reference}</span></>}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between sm:justify-end gap-4 sm:gap-5 pl-[52px] sm:pl-0">
                    <div className="text-left sm:text-right">
                      <div className="text-sm font-semibold text-emerald-200 tabular-nums">KES {money(payment.amount)}</div>
                      <div className="text-[10px] text-slate-500">{payment.paid_at?.slice(0, 10) || "Date not recorded"}</div>
                    </div>
                    {(payment.method === "mpesa" || payment.method === "airtel") && (
                      <button
                        type="button"
                        onClick={() => setMessagePaymentId(payment.id)}
                        aria-label={`View transaction message for ${payment.tenant_name || "tenant"}`}
                        className="w-10 h-10 shrink-0 rounded-xl border border-white/10 bg-white/[0.04] flex items-center justify-center text-slate-400 hover:text-emerald-200 hover:border-emerald-300/20 transition"
                      >
                        <MessageSquare className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </motion.article>
              ))}
            </div>
          )
        ) : filteredInvoices.length === 0 ? (
          <div className="mt-5">
            <EmptyState
              icon={<ReceiptText className="w-10 h-10" />}
              text={query ? "No invoices match this search" : "No invoices raised yet"}
              sub={query ? "Try another tenant, unit or invoice status." : "Raise monthly rent invoices to start tracking billed amounts and balances."}
            />
          </div>
        ) : (
          <div className="mt-5 space-y-2">
            {filteredInvoices.map((invoice, index) => (
              <motion.article
                key={invoice.id}
                initial={{ opacity: 0, y: 7 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(index * 0.02, 0.18) }}
                className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 sm:p-4 hover:border-sky-300/15 transition"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 shrink-0 rounded-xl bg-sky-300/10 border border-sky-300/10 flex items-center justify-center text-sky-100 text-xs font-semibold">
                      {invoice.unit_number || "—"}
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-sm font-semibold text-slate-100 truncate">{invoice.tenant_name || "Tenant not linked"}</h3>
                      <p className="text-[11px] text-slate-500 mt-1 capitalize">
                        {invoice.invoice_type || "Invoice"} · {invoice.period_start || "Period not set"}{invoice.period_end ? ` → ${invoice.period_end}` : ""}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between sm:justify-end gap-4 pl-[52px] sm:pl-0">
                    <div className="sm:text-right">
                      <div className="text-sm font-semibold text-white tabular-nums">KES {money(invoice.amount)}</div>
                      <div className={`text-[10px] mt-1 tabular-nums ${Number(invoice.balance || 0) > 0 ? "text-rose-300" : "text-emerald-300"}`}>
                        {Number(invoice.balance || 0) > 0 ? `Balance KES ${money(invoice.balance)}` : "No balance due"}
                      </div>
                    </div>
                    <Badge color={invoice.status === "paid" ? "emerald" : invoice.status === "overdue" ? "rose" : "amber"}>
                      {invoice.status || "pending"}
                    </Badge>
                  </div>
                </div>
              </motion.article>
            ))}
          </div>
        )}
      </Card>

      <div className="flex items-start gap-2.5 rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3">
        <Wallet className="w-4 h-4 shrink-0 text-emerald-200 mt-0.5" />
        <p className="text-[11px] leading-relaxed text-slate-500">
          Tenant rent is processed through the payment account configured by the property owner. Rental OS subscription billing is separate; this page reports property rent activity and does not represent platform subscription revenue.
        </p>
      </div>

      <TransactionMessageModal paymentId={messagePaymentId} onClose={() => setMessagePaymentId(null)} />
    </div>
  );
}
