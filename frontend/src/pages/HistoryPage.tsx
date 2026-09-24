import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { getPaymentHistory } from "../lib/api";
import { CreditCard, Search, Clock, User, DollarSign, Building2, Hash } from "lucide-react";

const container = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.04 } } };
const item = { hidden: { x: -10, opacity: 0 }, show: { x: 0, opacity: 1 } };

export default function HistoryPage() {
  const [payments, setPayments] = useState<any[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    (async () => {
      try { const p = await getPaymentHistory(); setPayments(p.payments || []); }
      catch (e) { console.error(e); }
    })();
  }, []);

  const filtered = payments.filter((p: any) =>
    p.tenant_name?.toLowerCase().includes(search.toLowerCase()) ||
    p.unit_number?.toLowerCase().includes(search.toLowerCase()) ||
    p.reference?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-4">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-emerald-400 to-sky-400 bg-clip-text text-transparent">
            Payment History
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">{payments.length} transactions</p>
        </div>
      </div>

      {/* ── Summary ── */}
      {payments.length > 0 && (
        <div className="flex gap-3 text-xs">
          <div className="bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-2">
            <span className="text-slate-500">Total collected: </span>
            <span className="text-emerald-400 font-bold">KES {payments.reduce((s: number, p: any) => s + (p.amount || 0), 0).toLocaleString()}</span>
          </div>
          <div className="bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-2">
            <span className="text-slate-500">Transactions: </span>
            <span className="text-white font-bold">{payments.length}</span>
          </div>
        </div>
      )}

      {/* ── Search ── */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
        <input className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-8 pr-3 py-2 text-sm outline-none focus:border-emerald-500 placeholder:text-slate-500"
          placeholder="Search tenant, house number, or reference..." value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {/* ── List ── */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <CreditCard className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p className="text-sm">No payment history yet</p>
          <p className="text-xs text-slate-600 mt-1">Payments will appear here when tenants pay rent</p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {filtered.map((p: any) => (
            <motion.div key={p.id} variants={item}
              className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition"
            >
              <div className="flex items-center gap-3">
                {/* Unit badge */}
                <div className={`w-9 h-9 rounded-lg flex flex-col items-center justify-center ${
                  p.method === "mpesa" ? "bg-emerald-500/10" : "bg-sky-500/10"
                }`}>
                  <span className="text-xs font-bold text-white leading-none">{p.unit_number?.[0] || "?"}</span>
                  <span className="text-[8px] text-slate-400 leading-none">{p.unit_number?.slice(1) || "—"}</span>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-200">{p.tenant_name}</span>
                    <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">{p.unit_number}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-slate-500 mt-0.5">
                    <span className="capitalize">{p.method}</span>
                    {p.reference && <><span>·</span><span className="font-mono">{p.reference}</span></>}
                  </div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-emerald-400">KES {p.amount.toLocaleString()}</div>
                <div className="text-[10px] text-slate-500">{p.paid_at?.slice(0, 10)}</div>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
