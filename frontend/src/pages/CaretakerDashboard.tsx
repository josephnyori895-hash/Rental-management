import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users,
  CreditCard,
  AlertTriangle,
  Search,
  Building2,
  UserPlus,
  ChevronDown,
  Home,
  DollarSign,
  CheckCircle,
  X,
} from "lucide-react";
import { getBoard, recordPayment, getPaymentHistory } from "../lib/api";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05, delayChildren: 0.1 } },
} as const;

const item = {
  hidden: { y: 20, opacity: 0 },
  show: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 12 } },
} as const;

type FilterMode = "all" | "paid" | "unpaid";

export default function CaretakerDashboard({ onEnroll }: { onEnroll?: () => void }) {
  const [board, setBoard] = useState<any>(null);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<FilterMode>("all");
  const [search, setSearch] = useState("");
  const [expandedHostel, setExpandedHostel] = useState<string | null>(null);
  const [payModal, setPayModal] = useState<{
    tenant_name: string;
    unit_number: string;
    hostel_name: string;
    invoice_id: string;
    rent_amount: number;
    amount_paid: number;
    balance: number;
    light: string;
  } | null>(null);
  const [payAmount, setPayAmount] = useState(0);
  const [payMethod, setPayMethod] = useState("cash");
  const [paying, setPaying] = useState(false);
  const [payDone, setPayDone] = useState("");
  const [recentPayments, setRecentPayments] = useState<any[]>([]);

  const load = async () => {
    try {
      const data = await getBoard();
      setBoard(data);
    } catch (e: any) {
      setErr(e.message);
    }
  };

  const loadRecent = async () => {
    try {
      const h = await getPaymentHistory();
      setRecentPayments((h.payments || []).slice(0, 5));
    } catch {
      /* non-critical */
    }
  };

  useEffect(() => {
    load();
    loadRecent();
    const id = setInterval(() => { load(); loadRecent(); }, 10000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => { loadRecent(); }, [payDone]);

  const openPayModal = (t: any) => {
    const bal = Math.max(0, (t.rent_amount || 0) - (t.amount_paid || 0));
    setPayModal({
      tenant_name: t.tenant_name,
      unit_number: t.unit_number,
      hostel_name: t.hostel_name,
      invoice_id: t.invoice_id,
      rent_amount: t.rent_amount || 0,
      amount_paid: t.amount_paid || 0,
      balance: bal,
      light: t.light,
    });
    setPayAmount(bal > 0 ? bal : t.rent_amount || 0);
    setPayMethod("cash");
    setPayDone("");
  };

  const handlePay = async () => {
    if (!payModal || payAmount <= 0) return;
    setPaying(true);
    try {
      const r = await recordPayment(payModal.invoice_id, payAmount, payMethod);
      setPayDone(`Recorded KES ${payAmount.toLocaleString()} via ${payMethod} — ${r.status}`);
      setPayModal(null);
      load();
    } catch (e: any) {
      setPayDone(`Error: ${e.message}`);
    }
    setPaying(false);
  };

  if (err) return <p className="text-rose-400 text-sm">{err}</p>;
  if (!board) return (
    <div className="flex items-center justify-center h-64">
      <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}>
        <Home className="w-8 h-8 text-emerald-400" />
      </motion.div>
    </div>
  );

  const allTenants = board.hostels.flatMap((h: any) =>
    h.units
      .filter((u: any) => u.light !== "empty")
      .map((u: any) => ({ ...u, hostel_name: h.name, property_id: h.property_id }))
  );

  const filtered = allTenants.filter((u: any) => {
    const matchSearch =
      u.tenant_name?.toLowerCase().includes(search.toLowerCase()) ||
      u.unit_number?.toLowerCase().includes(search.toLowerCase());
    if (!matchSearch) return false;
    if (filter === "paid") return u.light === "green";
    if (filter === "unpaid") return u.light === "red";
    return true;
  });

  const paidCount = allTenants.filter((u: any) => u.light === "green").length;
  const unpaidCount = allTenants.filter((u: any) => u.light === "red").length;

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-5 p-4 md:p-6">
      {/* Header */}
      <motion.div variants={item} className="flex items-center justify-between py-2">
        <div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-emerald-400 to-sky-400 bg-clip-text text-transparent">
            Caretaker Console
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            {board.hostels.length} hostel{board.hostels.length > 1 ? "s" : ""} · {allTenants.length} tenants
          </p>
        </div>
        <motion.div
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="flex items-center gap-1.5 text-[10px] text-emerald-400"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          Live
        </motion.div>
      </motion.div>

      {/* Quick Stats */}
      <motion.div variants={item} className="grid grid-cols-3 gap-3">
        <StatusCard
          icon={<Users className="w-4 h-4" />}
          label="Tenants"
          value={allTenants.length}
          color="text-emerald-400"
          bg="bg-slate-900/80"
        />
        <StatusCard
          icon={<CreditCard className="w-4 h-4" />}
          label="Paid"
          value={paidCount}
          color="text-green-400"
          bg="bg-slate-900/80"
        />
        <StatusCard
          icon={<AlertTriangle className="w-4 h-4" />}
          label="Unpaid"
          value={unpaidCount}
          color="text-rose-400"
          bg="bg-slate-900/80"
          pulse
        />
      </motion.div>

      {/* Status Bar */}
      <motion.div variants={item} className="rounded-xl bg-slate-900/80 backdrop-blur border border-slate-800 p-3">
        <div className="flex justify-between text-xs text-slate-400 mb-1.5">
          <span className="text-green-400">{paidCount} paid</span>
          <span className="text-rose-400">{unpaidCount} unpaid</span>
        </div>
        <div className="h-2.5 bg-slate-800 rounded-full overflow-hidden flex">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${allTenants.length > 0 ? (paidCount / allTenants.length) * 100 : 0}%` }}
            transition={{ duration: 1, ease: "easeOut" }}
            className="h-full bg-gradient-to-r from-emerald-500 to-green-400 rounded-l-full"
          />
          {unpaidCount > 0 && (
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${(unpaidCount / allTenants.length) * 100}%` }}
              transition={{ duration: 1, ease: "easeOut", delay: 0.3 }}
              className="h-full bg-gradient-to-r from-rose-500 to-red-400 rounded-r-full"
            />
          )}
        </div>
      </motion.div>

      {/* Filters + Search */}
      <motion.div variants={item} className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[160px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-8 pr-3 py-2 text-sm outline-none focus:border-emerald-500 placeholder:text-slate-500 transition"
            placeholder="Search tenant or room..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-1">
          {(["all", "paid", "unpaid"] as FilterMode[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                filter === f
                  ? f === "paid"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    : f === "unpaid"
                    ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                    : "bg-slate-700 text-white border border-slate-600"
                  : "text-slate-400 hover:bg-slate-800 border border-transparent"
              }`}
            >
              {f === "all" ? `All (${allTenants.length})` : f === "paid" ? `Paid (${paidCount})` : `Unpaid (${unpaidCount})`}
            </button>
          ))}
        </div>
        {onEnroll && (
          <button
            onClick={onEnroll}
            className="ml-auto flex items-center gap-1.5 px-4 py-2 bg-emerald-500 text-slate-950 rounded-lg text-xs font-semibold hover:bg-emerald-400 transition-all shadow-lg shadow-emerald-500/20"
          >
            <UserPlus className="w-3.5 h-3.5" />
            Enroll Tenant
          </button>
        )}
      </motion.div>

      {/* Tenant List */}
      {filtered.length === 0 ? (
        <motion.div variants={item} className="text-center py-10 text-slate-500">
          <Users className="w-10 h-10 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No tenants match your filter</p>
        </motion.div>
      ) : (
        <motion.div variants={item} className="space-y-1.5">
          {filtered.map((tenant: any, i: number) => (
            <motion.div
              key={tenant.unit_id}
              initial={{ x: -10, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ delay: i * 0.02 }}
              className={`rounded-xl border px-3.5 py-2.5 flex items-center gap-3 transition-all duration-200 hover:shadow-md ${
                tenant.light === "green"
                  ? "bg-emerald-500/[0.04] border-emerald-500/15 hover:border-emerald-500/30"
                  : "bg-rose-500/[0.04] border-rose-500/15 hover:border-rose-500/30"
              }`}
            >
              <div
                className={`w-3 h-3 rounded-full flex-shrink-0 ${
                  tenant.light === "green"
                    ? "bg-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.5)]"
                    : "bg-rose-400 shadow-[0_0_10px_rgba(244,63,94,0.5)]"
                }`}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-white truncate">
                    {tenant.tenant_name || "Unknown"}
                  </span>
                  <span className="text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded font-mono">
                    {tenant.unit_number}
                  </span>
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">{tenant.hostel_name}</div>
              </div>
              <div className="flex items-center gap-1.5">
                <div
                  className={`text-[11px] font-bold px-2.5 py-1 rounded-md ${
                    tenant.light === "green"
                      ? "bg-emerald-500/15 text-emerald-300"
                      : "bg-rose-500/15 text-rose-300"
                  }`}
                >
                  {tenant.light === "green" ? "PAID" : "UNPAID"}
                </div>
                {tenant.invoice_id && (
                  <button
                    onClick={() => openPayModal(tenant)}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 hover:bg-emerald-500/20 hover:border-emerald-500/40 transition-all whitespace-nowrap"
                  >
                    <DollarSign className="w-3 h-3" />
                    Record
                  </button>
                )}
              </div>
            </motion.div>
          ))}
        </motion.div>
      )}

      {/* Per-Hostel Breakdown */}
      <motion.div variants={item} className="space-y-2">
        <h3 className="text-xs uppercase text-slate-500 font-semibold tracking-wider flex items-center gap-1.5">
          <Building2 className="w-3 h-3" />
          Hostels
        </h3>
        {board.hostels.map((h: any) => (
          <motion.div
            key={h.property_id}
            className="rounded-xl bg-slate-900/50 border border-slate-800 overflow-hidden"
          >
            <button
              onClick={() => setExpandedHostel(expandedHostel === h.property_id ? null : h.property_id)}
              className="w-full flex items-center justify-between p-3 hover:bg-slate-800/50 transition-all duration-200"
            >
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-medium">{h.name}</span>
                <span className="text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">
                  {h.total_units} units
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-green-400">{h.paid_count} paid</span>
                {h.unpaid_count > 0 && (
                  <span className="text-[10px] text-rose-400">{h.unpaid_count} unpaid</span>
                )}
                <ChevronDown
                  className={`w-3.5 h-3.5 text-slate-500 transition-transform duration-200 ${
                    expandedHostel === h.property_id ? "rotate-180" : ""
                  }`}
                />
              </div>
            </button>
            {expandedHostel === h.property_id && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="px-3 pb-3 space-y-1 border-t border-slate-800 pt-2"
              >
                {h.units
                  .filter((u: any) => u.light !== "empty")
                  .map((u: any) => (
                    <div key={u.unit_id} className="flex items-center justify-between text-xs py-1.5 px-1">
                      <div className="flex items-center gap-2">
                        <div
                          className={`w-2 h-2 rounded-full ${
                            u.light === "green" ? "bg-emerald-400" : "bg-rose-400"
                          }`}
                        />
                        <span className="text-slate-300">{u.unit_number}</span>
                        <span className="text-slate-500 truncate max-w-[140px]">{u.tenant_name}</span>
                      </div>
                      {u.invoice_id && (
                        <button
                          onClick={() => openPayModal({ ...u, hostel_name: h.name })}
                          className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 transition-all"
                        >
                          <DollarSign className="w-2.5 h-2.5" />
                          Pay
                        </button>
                      )}
                    </div>
                  ))}
              </motion.div>
            )}
          </motion.div>
        ))}
      </motion.div>

      {/* Recent Activity */}
      {recentPayments.length > 0 && (
        <motion.div variants={item} className="space-y-2">
          <h3 className="text-xs uppercase text-slate-500 font-semibold tracking-wider flex items-center gap-1.5">
            <CreditCard className="w-3 h-3" />
            Recent Payments
          </h3>
          <div className="space-y-1">
            {recentPayments.map((p: any) => (
              <div
                key={p.id}
                className="flex items-center justify-between px-3 py-2 rounded-lg bg-slate-900/40 border border-slate-800 text-xs"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <CheckCircle className="w-3 h-3 text-emerald-400 shrink-0" />
                  <span className="text-slate-300 truncate">{p.tenant_name}</span>
                  <span className="text-slate-600 font-mono">{p.unit_number}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 uppercase">
                    {p.method}
                  </span>
                </div>
                <span className="text-emerald-400 font-medium shrink-0 ml-2">
                  KES {p.amount?.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Record Payment Modal */}
      <AnimatePresence>
        {payModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={() => setPayModal(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              transition={{ type: "spring", stiffness: 200, damping: 20 }}
              className="bg-slate-900 border border-slate-700 rounded-2xl p-5 w-full max-w-sm mx-4 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <DollarSign className="w-5 h-5 text-emerald-400" />
                  <span className="text-sm font-bold text-white">Record Payment</span>
                </div>
                <button
                  onClick={() => setPayModal(null)}
                  className="w-7 h-7 rounded-lg bg-slate-800 flex items-center justify-center hover:bg-slate-700 transition"
                >
                  <X className="w-3.5 h-3.5 text-slate-400" />
                </button>
              </div>
              <div className="rounded-xl bg-slate-800/50 border border-slate-700 p-3 mb-4 space-y-1">
                <div className="text-sm font-semibold text-white">{payModal.tenant_name}</div>
                <div className="text-[11px] text-slate-400">
                  {payModal.unit_number} · {payModal.hostel_name}
                </div>
                {payModal.balance > 0 && (
                  <div className="flex items-center gap-2 pt-1">
                    <span className="text-[10px] uppercase text-slate-500">Balance:</span>
                    <span className="text-sm font-bold text-rose-400">
                      KES {payModal.balance.toLocaleString()}
                    </span>
                  </div>
                )}
              </div>
              <div className="space-y-1.5 mb-4">
                <label className="text-[10px] uppercase tracking-wider text-slate-400">Amount (KES)</label>
                <input
                  type="number"
                  value={payAmount}
                  onChange={(e) => setPayAmount(Number(e.target.value))}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-lg font-bold text-center outline-none focus:border-emerald-500"
                  min={1}
                  step={100}
                />
              </div>
              <div className="space-y-1.5 mb-4">
                <label className="text-[10px] uppercase tracking-wider text-slate-400">Method</label>
                <div className="grid grid-cols-3 gap-1.5">
                  {[
                    { v: "cash", label: "Cash" },
                    { v: "mpesa", label: "M-Pesa" },
                    { v: "bank", label: "Bank" },
                    { v: "airtel", label: "Airtel" },
                    { v: "equity", label: "Equity" },
                    { v: "card", label: "Card" },
                  ].map((m) => (
                    <button
                      key={m.v}
                      onClick={() => setPayMethod(m.v)}
                      className={`px-2 py-2 rounded-lg text-[11px] font-medium border transition-all ${
                        payMethod === m.v
                          ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                          : "bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700"
                      }`}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>
              <motion.button
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={handlePay}
                disabled={paying || payAmount <= 0}
                className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-500 to-emerald-600 text-slate-950 font-semibold py-2.5 rounded-lg hover:from-emerald-400 hover:to-emerald-500 transition-all shadow-lg shadow-emerald-500/20 disabled:opacity-50"
              >
                {paying ? (
                  <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }}>
                    <DollarSign className="w-4 h-4" />
                  </motion.div>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    Record KES {payAmount.toLocaleString()}
                  </>
                )}
              </motion.button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Payment success toast */}
      <AnimatePresence>
        {payDone && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 shadow-2xl flex items-center gap-2 text-sm"
          >
            <CheckCircle className="w-4 h-4 text-emerald-400" />
            <span className="text-slate-200">{payDone}</span>
            <button
              onClick={() => setPayDone("")}
              className="ml-2 w-5 h-5 rounded bg-slate-800 flex items-center justify-center hover:bg-slate-700"
            >
              <X className="w-3 h-3 text-slate-400" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function StatusCard({
  icon,
  label,
  value,
  color,
  bg,
  pulse,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  color: string;
  bg: string;
  pulse?: boolean;
}) {
  return (
    <motion.div
      whileHover={{ y: -2, transition: { type: "spring", stiffness: 200 } }}
      className={`relative rounded-xl ${bg} border border-slate-700/50 p-3 overflow-hidden`}
    >
      {pulse && (
        <motion.div
          animate={{ opacity: [0, 0.3, 0] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="absolute inset-0 bg-rose-500/10 rounded-xl"
        />
      )}
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] uppercase tracking-wider text-slate-400">{label}</span>
        <span className={color}>{icon}</span>
      </div>
      <motion.div
        key={value}
        initial={{ scale: 0.5 }}
        animate={{ scale: 1 }}
        className={`text-xl font-bold ${color}`}
      >
        {value}
      </motion.div>
    </motion.div>
  );
}