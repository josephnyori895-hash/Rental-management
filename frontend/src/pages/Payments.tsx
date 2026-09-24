import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Search, CreditCard, DollarSign, Download, MessageSquare } from "lucide-react";
import { getPaymentHistory, getInvoices } from "../lib/api";
import { Card, PageHeader, Badge, EmptyState, money } from "../components/ui";
import TransactionMessageModal from "../components/TransactionMessageModal";

export default function Payments() {
  const [payments, setPayments] = useState<any[]>([]);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<"payments" | "invoices">("payments");
  const [loading, setLoading] = useState(true);
  const [messagePaymentId, setMessagePaymentId] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      getPaymentHistory().then((d) => setPayments(d.payments || [])).catch(() => {}),
      getInvoices().then((d) => setInvoices(d.invoices || [])).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const filteredPay = payments.filter((p) =>
    p.tenant_name?.toLowerCase().includes(search.toLowerCase()) ||
    p.unit_number?.toLowerCase().includes(search.toLowerCase())
  );
  const filteredInv = invoices.filter((inv: any) =>
    (inv.tenant_name || "").toLowerCase().includes(search.toLowerCase()) ||
    (inv.unit_number || "").toLowerCase().includes(search.toLowerCase())
  );

  const totalCollected = payments.reduce((s, p) => s + (p.amount || 0), 0);
  const totalBilled = invoices.reduce((s: number, inv: any) => s + (inv.amount || 0), 0);
  const totalOutstanding = invoices.reduce((s: number, inv: any) => s + (inv.balance || 0), 0);

  return (
    <div className="space-y-5">
      <PageHeader title="Payments" sub="Collections, transactions & invoices"
        actions={
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
            <input placeholder="Search..."
              value={search} onChange={(e) => setSearch(e.target.value)}
              className="w-52 bg-slate-800/50 border border-slate-700/50 rounded-lg pl-7 pr-2 py-1.5 text-sm outline-none focus:border-emerald-500/50 placeholder:text-slate-600" />
          </div>
        }
      />

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4">
          <div className="text-xs text-slate-500">Collected</div>
          <div className="text-xl font-bold text-emerald-400">KES {money(totalCollected)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-slate-500">Billed</div>
          <div className="text-xl font-bold text-sky-400">KES {money(totalBilled)}</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-slate-500">Outstanding</div>
          <div className="text-xl font-bold text-rose-400">KES {money(totalOutstanding)}</div>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {(["payments", "invoices"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              tab === t ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30" : "bg-slate-800/50 text-slate-400 border border-slate-700/50"
            }`}>
            {t === "payments" ? "Transactions" : "Invoices"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-slate-500 py-16 text-center">Loading…</div>
      ) : tab === "payments" ? (
        filteredPay.length === 0 ? <EmptyState icon={<CreditCard className="w-12 h-12" />} text="No payments yet" /> :
        <div className="space-y-1.5">
          {filteredPay.map((p, i) => (
            <motion.div key={p.id} initial={{ x: -10, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: i * 0.03 }}
              className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                </div>
                <div>
                  <div className="text-sm font-medium text-slate-200">{p.tenant_name}</div>
                  <div className="flex items-center gap-2 text-[10px] text-slate-500">
                    <span>{p.unit_number}</span><span>·</span><span className="capitalize">{p.method}</span>
                    {p.reference && <><span>·</span><span className="font-mono">{p.reference}</span></>}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {(p.method === "mpesa" || p.method === "airtel") && (
                  <button onClick={() => setMessagePaymentId(p.id)}
                    className="w-7 h-7 rounded-lg bg-slate-800 flex items-center justify-center hover:bg-emerald-500/15 hover:text-emerald-400 transition text-slate-500"
                    title="View transaction message">
                    <MessageSquare className="w-3.5 h-3.5" />
                  </button>
                )}
                <div className="text-right">
                  <div className="text-sm font-bold text-emerald-400">KES {money(p.amount)}</div>
                  <div className="text-[10px] text-slate-500">{p.paid_at?.slice(0, 10)}</div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      ) : (
        filteredInv.length === 0 ? <EmptyState icon={<CreditCard className="w-12 h-12" />} text="No invoices" /> :
        <div className="space-y-1.5">
          {filteredInv.map((inv: any, i: number) => (
            <motion.div key={inv.id} initial={{ x: -10, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: i * 0.02 }}
              className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-slate-800 flex items-center justify-center text-slate-400 text-xs font-bold">
                  {inv.unit_number}
                </div>
                <div>
                  <div className="text-sm font-medium text-slate-200">{inv.tenant_name || "—"}</div>
                  <div className="text-[10px] text-slate-500">{inv.invoice_type} · {inv.period_start} → {inv.period_end}</div>
                </div>
              </div>
              <div className="text-right flex items-center gap-3">
                <div>
                  <div className="text-sm font-bold text-white">KES {money(inv.amount)}</div>
                  {inv.balance > 0 && <div className="text-[10px] text-rose-400">Bal: KES {money(inv.balance)}</div>}
                </div>
                <Badge color={inv.status === "paid" ? "emerald" : inv.status === "overdue" ? "rose" : "amber"}>{inv.status}</Badge>
              </div>
            </motion.div>
          ))}
        </div>
      )}
      <TransactionMessageModal paymentId={messagePaymentId} onClose={() => setMessagePaymentId(null)} />
    </div>
  );
}
