import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { PieChart } from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";
import "echarts/lib/component/tooltip";
import "echarts/lib/component/legend";
import {
  Receipt, Plus, Search, Smartphone, Loader2,
  CheckCircle2, XCircle, X,
} from "lucide-react";
import { getExpenses, getExpenseSummary, createExpense, stkDirect } from "../lib/api";
import { Card, PageHeader, Badge, EmptyState, money } from "../components/ui";

echarts.use([PieChart, CanvasRenderer]);

const CAT_COLORS: Record<string, string> = {
  repairs: "#f43f5e", utilities: "#f59e0b", water: "#38bdf8", electricity: "#fbbf24",
  wifi: "#a78bfa", cleaning: "#34d399", security: "#fb7185", garbage: "#94a3b8",
  supplies: "#22d3ee", salary: "#f472b6", tax: "#facc15", insurance: "#60a5fa",
  marketing: "#c084fc", legal: "#2dd4bf", misc: "#64748b",
};

/* ── STK Push Modal ────────────────────────────────────────────── */
function StkModal({
  expense,
  onClose,
}: {
  expense: any;
  onClose: () => void;
}) {
  const [phone, setPhone] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "err">("idle");
  const [msg, setMsg] = useState("");

  const send = async () => {
    if (!phone.trim()) return;
    setStatus("loading");
    try {
      await stkDirect(phone.trim(), expense.amount, expense.description || expense.category);
      setStatus("ok");
      setMsg("STK push sent! Check your phone and enter your M-Pesa PIN.");
    } catch (e: any) {
      setStatus("err");
      setMsg(e.message || "Failed to send STK push.");
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4"
        onClick={(e) => e.target === e.currentTarget && onClose()}
      >
        <motion.div
          initial={{ scale: 0.9, y: 20 }}
          animate={{ scale: 1, y: 0 }}
          exit={{ scale: 0.9, y: 20 }}
          transition={{ type: "spring", stiffness: 280, damping: 24 }}
          className="w-full max-w-sm bg-[#0d1929] border border-slate-700/60 rounded-2xl shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between bg-emerald-500/5">
            <div className="flex items-center gap-2">
              <Smartphone className="w-5 h-5 text-emerald-400" />
              <span className="font-bold text-white">Pay via M-Pesa</span>
            </div>
            <button onClick={onClose} className="w-7 h-7 rounded-lg bg-slate-800 hover:bg-slate-700 flex items-center justify-center transition">
              <X className="w-4 h-4 text-slate-400" />
            </button>
          </div>

          {/* Expense summary */}
          <div className="px-5 py-4 border-b border-slate-800">
            <div className="text-xs text-slate-500 mb-1">Paying for</div>
            <div className="text-sm font-semibold text-slate-200">{expense.description || expense.category}</div>
            <div className="text-2xl font-black text-emerald-400 mt-1">KES {money(expense.amount)}</div>
            {expense.vendor && <div className="text-xs text-slate-500 mt-0.5">Vendor: {expense.vendor}</div>}
          </div>

          {/* Phone input */}
          <div className="px-5 py-4 space-y-4">
            {status === "idle" || status === "loading" ? (
              <>
                <div>
                  <label className="text-xs text-slate-400 mb-1.5 block">Phone number to charge</label>
                  <input
                    type="tel"
                    placeholder="e.g. 0712345678 or 254712345678"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && send()}
                    className="w-full bg-slate-800 border border-slate-700 focus:border-emerald-500/60 rounded-xl px-4 py-3 text-sm text-white outline-none placeholder:text-slate-600 transition"
                    disabled={status === "loading"}
                  />
                  <p className="text-[10px] text-slate-600 mt-1.5">
                    The M-Pesa PIN prompt will appear on this number.
                  </p>
                </div>
                <button
                  onClick={send}
                  disabled={!phone.trim() || status === "loading"}
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed text-slate-950 font-bold text-sm transition-all shadow-lg shadow-emerald-500/25"
                >
                  {status === "loading"
                    ? <><Loader2 className="w-4 h-4 animate-spin" /> Sending STK Push…</>
                    : <><Smartphone className="w-4 h-4" /> Send STK Push</>
                  }
                </button>
              </>
            ) : status === "ok" ? (
              <div className="flex flex-col items-center gap-3 py-4 text-center">
                <CheckCircle2 className="w-10 h-10 text-emerald-400" />
                <p className="text-sm font-semibold text-emerald-300">{msg}</p>
                <button onClick={onClose} className="px-6 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition">
                  Done
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 py-4 text-center">
                <XCircle className="w-10 h-10 text-rose-400" />
                <p className="text-sm font-semibold text-rose-300">{msg}</p>
                <button onClick={() => setStatus("idle")} className="px-6 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition">
                  Try Again
                </button>
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

/* ── Main Page ─────────────────────────────────────────────────── */
export default function Expenses() {
  const [expenses, setExpenses] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ category: "repairs", amount: "", description: "", vendor: "", property_id: "" });
  const [loading, setLoading] = useState(true);
  const [payingExpense, setPayingExpense] = useState<any>(null);

  const load = () => {
    getExpenseSummary().then(setSummary).catch(() => {});
    getExpenses().then((d) => { setExpenses(d.expenses || []); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(load, []);

  const submit = async () => {
    if (!form.amount) return;
    try {
      await createExpense({ ...form, amount: parseFloat(form.amount), property_id: form.property_id || undefined });
      setForm({ category: "repairs", amount: "", description: "", vendor: "", property_id: "" });
      setShowForm(false);
      load();
    } catch (e) { alert("Error: " + (e as Error).message); }
  };

  const filtered = expenses.filter((e) =>
    e.description?.toLowerCase().includes(search.toLowerCase()) ||
    e.vendor?.toLowerCase().includes(search.toLowerCase()) ||
    e.category?.includes(search.toLowerCase())
  );

  return (
    <div className="space-y-5">
      <PageHeader title="Expenses" sub="Operational costs & P&L"
        actions={
          <button onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25">
            <Plus className="w-3.5 h-3.5" /> Add Expense
          </button>
        }
      />

      {summary && (
        <div className="grid md:grid-cols-3 gap-4">
          <Card className="p-4 md:col-span-2">
            <div className="text-xs text-slate-500 mb-2">Total: KES {money(summary.total)} · {summary.count} entries</div>
            <ReactEChartsCore echarts={echarts} option={{
              tooltip: { trigger: "item", backgroundColor: "#0f172a", borderColor: "#334155", textStyle: { color: "#e2e8f0" } },
              legend: { bottom: 0, textStyle: { color: "#94a3b8", fontSize: 10 }, type: "scroll" },
              series: [{
                type: "pie", radius: ["40%", "70%"], avoidLabelOverlap: true,
                itemStyle: { borderRadius: 6, borderColor: "#0f172a", borderWidth: 2 },
                label: { show: false },
                data: Object.entries(summary.by_category).map(([k, v]) => ({
                  name: k, value: v, itemStyle: { color: CAT_COLORS[k] || "#64748b" },
                })),
              }],
            }} style={{ height: 240 }} />
          </Card>
          <Card className="p-4">
            <div className="text-xs text-slate-500 mb-2">By Category</div>
            <div className="space-y-1.5 max-h-56 overflow-y-auto">
              {Object.entries(summary.by_category).map(([k, v]: any) => (
                <div key={k} className="flex justify-between items-center text-xs">
                  <span className="flex items-center gap-1.5 text-slate-300">
                    <span className="w-2 h-2 rounded-full" style={{ background: CAT_COLORS[k] || "#64748b" }} />
                    {k}
                  </span>
                  <span className="text-slate-200 font-medium">KES {money(v)}</span>
                </div>
              ))}
              {Object.keys(summary.by_category).length === 0 && <p className="text-slate-600 text-xs">No expenses recorded</p>}
            </div>
          </Card>
        </div>
      )}

      {showForm && (
        <Card className="p-4 space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-sm outline-none">
              {Object.keys(CAT_COLORS).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <input type="number" placeholder="Amount" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })}
              className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-sm outline-none" />
            <input placeholder="Vendor" value={form.vendor} onChange={(e) => setForm({ ...form, vendor: e.target.value })}
              className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-sm outline-none" />
            <input placeholder="Property ID (opt)" value={form.property_id} onChange={(e) => setForm({ ...form, property_id: e.target.value })}
              className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-sm outline-none" />
          </div>
          <input placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none" />
          <button onClick={submit} className="px-4 py-2 rounded-lg bg-emerald-500 text-slate-950 font-medium text-sm hover:bg-emerald-400">
            Save Expense
          </button>
        </Card>
      )}

      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
        <input placeholder="Search expenses..." value={search} onChange={(e) => setSearch(e.target.value)}
          className="w-52 bg-slate-800/50 border border-slate-700/50 rounded-lg pl-7 pr-2 py-1.5 text-sm outline-none focus:border-emerald-500/50" />
      </div>

      {loading ? <div className="text-slate-500 py-16 text-center">Loading…</div> :
        filtered.length === 0 ? <EmptyState icon={<Receipt className="w-12 h-12" />} text="No expenses recorded" /> :
        <div className="space-y-1.5">
          {filtered.map((e, i) => (
            <motion.div key={e.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
              className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition group">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: (CAT_COLORS[e.category] || "#64748b") + "22" }}>
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: CAT_COLORS[e.category] || "#64748b" }} />
                </div>
                <div>
                  <div className="text-sm font-medium text-slate-200">{e.description || e.category}</div>
                  <div className="text-[10px] text-slate-500">{e.vendor || "—"} · {e.paid_at}</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm font-bold text-white">KES {money(e.amount)}</span>
                <Badge color="slate">{e.category}</Badge>
                {/* ── Pay via M-Pesa ── */}
                <button
                  onClick={() => setPayingExpense(e)}
                  title="Pay this expense via M-Pesa STK Push"
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-bold
                    bg-emerald-500/10 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/25
                    hover:border-emerald-500/50 transition opacity-0 group-hover:opacity-100"
                >
                  <Smartphone className="w-3.5 h-3.5" /> Pay
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      }

      {/* STK Push Modal */}
      {payingExpense && (
        <StkModal expense={payingExpense} onClose={() => setPayingExpense(null)} />
      )}
    </div>
  );
}
