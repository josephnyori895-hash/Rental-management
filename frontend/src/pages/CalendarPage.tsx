import { useEffect, useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getInvoices, downloadCSV } from "../lib/api";
import {
  Calendar, ChevronLeft, ChevronRight, DollarSign, AlertTriangle,
  CheckCircle2, Clock, Search, Download, X, TrendingUp, TrendingDown, Wallet,
} from "lucide-react";
import { Card, AnimatedNumber, money } from "../components/ui";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

type StatusFilter = "all" | "paid" | "pending" | "overdue";

const statusColors: Record<string, string> = {
  paid: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  pending: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  overdue: "bg-rose-500/20 text-rose-300 border-rose-500/30",
  partial: "bg-sky-500/20 text-sky-300 border-sky-500/30",
};

const statusIcons: Record<string, React.ReactNode> = {
  paid: <CheckCircle2 className="w-2.5 h-2.5" />,
  pending: <Clock className="w-2.5 h-2.5" />,
  overdue: <AlertTriangle className="w-2.5 h-2.5" />,
  partial: <Clock className="w-2.5 h-2.5" />,
};

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.03 } },
};
const item = {
  hidden: { y: 12, opacity: 0 },
  show: { y: 0, opacity: 1, transition: { type: "spring" as const, stiffness: 200, damping: 22 } },
};

export default function CalendarPage() {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [date, setDate] = useState(new Date());
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [search, setSearch] = useState("");
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const year = date.getFullYear();
  const month = date.getMonth();

  useEffect(() => {
    getInvoices().then((d) => setInvoices(d.invoices || [])).catch(() => {});
  }, []);

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDay = new Date(year, month, 1).getDay();
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);

  const dueMap = useMemo(() => {
    const map: Record<string, any[]> = {};
    invoices.forEach((inv: any) => {
      if (inv.due_date) {
        const key = inv.due_date.slice(0, 10);
        const invStatus = inv.status || "pending";
        if (statusFilter !== "all" && invStatus !== statusFilter) return;
        if (search && !inv.unit_number?.toLowerCase().includes(search.toLowerCase()) && !inv.tenant_name?.toLowerCase().includes(search.toLowerCase())) return;
        if (!map[key]) map[key] = [];
        map[key].push(inv);
      }
    });
    return map;
  }, [invoices, statusFilter, search]);

  const prevMonth = () => { setSelectedDay(null); setDate(new Date(year, month - 1, 1)); };
  const nextMonth = () => { setSelectedDay(null); setDate(new Date(year, month + 1, 1)); };

  const monthInvoices = useMemo(() => {
    const prefix = `${year}-${String(month + 1).padStart(2, "0")}`;
    return invoices.filter((inv: any) => inv.due_date?.startsWith(prefix));
  }, [invoices, year, month]);

  const monthPaid = monthInvoices.filter((i: any) => i.status === "paid");
  const monthPending = monthInvoices.filter((i: any) => i.status === "pending");
  const monthOverdue = monthInvoices.filter((i: any) => i.status === "overdue");

  const monthExpected = monthInvoices.reduce((s: number, i: any) => s + (i.amount || 0), 0);
  const monthCollected = monthInvoices.reduce((s: number, i: any) => s + (i.paid_amount || 0), 0);
  const monthOutstanding = monthInvoices.reduce((s: number, i: any) => s + (i.balance || 0), 0);

  const handleExportMonth = () => {
    const rows: (string | number)[][] = [
      [`RENT CALENDAR — ${MONTHS[month]} ${year}`],
      [],
      ["Date", "Tenant", "Unit", "Type", "Amount", "Paid", "Balance", "Status", "Invoice #"],
    ];
    monthInvoices.sort((a, b) => (a.due_date || "").localeCompare(b.due_date || ""));
    monthInvoices.forEach((inv: any) => {
      rows.push([
        inv.due_date?.slice(0, 10) || "",
        inv.tenant_name || "",
        inv.unit_number || "",
        inv.invoice_type || "",
        inv.amount || 0,
        inv.paid_amount || 0,
        inv.balance || 0,
        inv.status || "",
        inv.invoice_number || inv.id?.slice(0, 8) || "",
      ]);
    });
    downloadCSV(`calendar_${MONTHS[month]}_${year}.csv`, rows);
  };

  const selectedDayInvoices = selectedDay ? dueMap[selectedDay] || [] : [];

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-4">

      <motion.div variants={item} className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-emerald-400 to-sky-400 bg-clip-text text-transparent">
            Rent Calendar
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {monthInvoices.length} invoices · {monthPaid.length} paid · {monthPending.length} pending · {monthOverdue.length} overdue
          </p>
        </div>
        <button onClick={handleExportMonth}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 hover:bg-emerald-500/25 transition text-xs font-medium">
          <Download className="w-3.5 h-3.5" />
          Export Month (CSV)
        </button>
      </motion.div>

      <motion.div variants={item} className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MonthStat icon={<TrendingUp className="w-4 h-4" />} label="Expected" value={monthExpected} color="text-slate-300" bg="bg-slate-500/10" delay={0} />
        <MonthStat icon={<CheckCircle2 className="w-4 h-4" />} label="Collected" value={monthCollected} color="text-emerald-400" bg="bg-emerald-500/10" delay={0.05} />
        <MonthStat icon={<AlertTriangle className="w-4 h-4" />} label="Outstanding" value={monthOutstanding} color="text-rose-400" bg="bg-rose-500/10" delay={0.1} />
        <MonthStat icon={<Wallet className="w-4 h-4" />} label="Collection Rate" value={monthCollected / (monthExpected || 1) * 100} suffix="%" color="text-sky-400" bg="bg-sky-500/10" delay={0.15} />
      </motion.div>

      <motion.div variants={item} className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1 bg-slate-900/60 border border-white/[0.06] rounded-xl px-2 py-1.5 backdrop-blur">
          <button onClick={prevMonth} className="p-1 hover:bg-white/[0.06] rounded-lg transition"><ChevronLeft className="w-3.5 h-3.5 text-slate-400" /></button>
          <div className="text-center min-w-[100px]">
            <div className="text-sm font-semibold text-white">{MONTHS[month]} {year}</div>
          </div>
          <button onClick={nextMonth} className="p-1 hover:bg-white/[0.06] rounded-lg transition"><ChevronRight className="w-3.5 h-3.5 text-slate-400" /></button>
        </div>

        <div className="flex gap-1">
          {[
            { key: "all", label: "All" },
            { key: "paid", label: "Paid" },
            { key: "pending", label: "Pending" },
            { key: "overdue", label: "Overdue" },
          ].map((f) => (
            <button key={f.key}
              onClick={() => setStatusFilter(f.key as StatusFilter)}
              className={`px-2.5 py-1.5 rounded-lg text-[10px] font-medium transition-all ${
                statusFilter === f.key
                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                  : "bg-slate-800/50 text-slate-500 border border-slate-700/50 hover:bg-slate-700/50"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="relative ml-auto">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-500" />
          <input placeholder="Search room..." value={search} onChange={(e) => setSearch(e.target.value)}
            className="w-32 bg-slate-800/50 border border-white/[0.06] rounded-lg pl-7 pr-2 py-1.5 text-xs outline-none focus:border-emerald-500/50 placeholder:text-slate-600"
          />
        </div>
      </motion.div>

      <motion.div variants={item} className="rounded-xl bg-slate-900/60 backdrop-blur border border-white/[0.06] overflow-hidden">
        <div className="grid grid-cols-7 border-b border-white/[0.06]">
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
            <div key={d} className="text-center text-[10px] uppercase text-slate-500 py-2 font-medium">{d}</div>
          ))}
        </div>

        <motion.div variants={{ show: { transition: { staggerChildren: 0.01 } } }} initial="hidden" animate="show"
          className="grid grid-cols-7">
          {Array.from({ length: firstDay }).map((_, i) => (
            <div key={`e-${i}`} className="h-24 bg-slate-900/30" />
          ))}
          {days.map((d) => {
            const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
            const dayInvoices = dueMap[dateStr] || [];
            const today = new Date();
            const isToday = d === today.getDate() && month === today.getMonth() && year === today.getFullYear();
            const dayAmount = dayInvoices.reduce((s: number, i: any) => s + (i.amount || 0), 0);
            const dayCollected = dayInvoices.reduce((s: number, i: any) => s + (i.paid_amount || 0), 0);
            const allPaid = dayInvoices.length > 0 && dayInvoices.every((i: any) => i.status === "paid");
            const isSelected = selectedDay === dateStr;

            return (
              <motion.div key={d}
                variants={{ hidden: { scale: 0.8, opacity: 0 }, show: { scale: 1, opacity: 1 } }}
                onClick={() => setSelectedDay(isSelected ? null : dateStr)}
                className={`h-24 border border-white/[0.04] p-1.5 transition cursor-pointer relative ${
                  isSelected ? "bg-emerald-500/10 border-emerald-500/40" :
                  isToday ? "bg-emerald-500/5 border-emerald-500/20" :
                  allPaid ? "bg-emerald-500/[0.02] hover:bg-white/[0.03]" :
                  dayInvoices.length > 0 ? "bg-amber-500/[0.02] hover:bg-white/[0.03]" :
                  "hover:bg-white/[0.02]"
                }`}
              >
                <div className={`text-[11px] font-semibold mb-1 flex items-center justify-between ${isToday ? "text-emerald-400" : "text-slate-500"}`}>
                  {d}
                  {dayInvoices.length > 0 && (
                    <span className="text-[8px] text-slate-600 font-mono">{dayInvoices.length}</span>
                  )}
                </div>
                <div className="space-y-0.5 overflow-hidden">
                  {dayInvoices.slice(0, 3).map((inv: any, i: number) => {
                    const s = inv.status || "pending";
                    return (
                      <div key={i}
                        className={`text-[8px] px-1 py-0.5 rounded flex items-center gap-1 font-medium border ${statusColors[s] || statusColors.pending}`}
                      >
                        {statusIcons[s] || statusIcons.pending}
                        <span className="truncate">{inv.unit_number}</span>
                      </div>
                    );
                  })}
                  {dayInvoices.length > 3 && (
                    <div className="text-[8px] text-slate-500 pl-1 font-medium">+{dayInvoices.length - 3} more</div>
                  )}
                </div>
                {dayInvoices.length > 0 && dayAmount > 0 && (
                  <div className="absolute bottom-1 right-1 text-[7px] text-slate-600 font-mono">
                    {dayCollected === dayAmount ? (
                      <span className="text-emerald-500">✓{money(dayAmount).split(".")[0]}</span>
                    ) : (
                      <span>K{money(dayAmount).split(".")[0]}</span>
                    )}
                  </div>
                )}
              </motion.div>
            );
          })}
        </motion.div>
      </motion.div>

      <div className="flex items-center gap-4 text-[10px] text-slate-500">
        <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-emerald-500" /> Paid</div>
        <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-amber-500" /> Pending</div>
        <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-rose-500" /> Overdue</div>
        <div className="flex items-center gap-1"><div className="w-2.5 h-2.5 rounded-full border-2 border-emerald-400 bg-emerald-500/20" /> Today</div>
      </div>

      <AnimatePresence>
        {selectedDay && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
          >
            <Card className="p-4" hover={false}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-emerald-400" />
                  <h2 className="text-sm font-semibold text-white">
                    {new Date(selectedDay).toLocaleDateString("en-KE", { weekday: "long", day: "numeric", month: "long" })}
                  </h2>
                  <span className="text-[10px] text-slate-500">{selectedDayInvoices.length} invoices due</span>
                </div>
                <button onClick={() => setSelectedDay(null)} className="text-slate-500 hover:text-slate-300 transition">
                  <X className="w-4 h-4" />
                </button>
              </div>

              {selectedDayInvoices.length === 0 ? (
                <div className="text-center py-6">
                  <CheckCircle2 className="w-8 h-8 text-slate-700 mx-auto mb-2" />
                  <p className="text-xs text-slate-500">No invoices due this day</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {selectedDayInvoices.map((inv: any, i: number) => (
                    <motion.div key={i}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      whileHover={{ x: 2 }}
                      className="flex items-center justify-between px-3 py-2.5 rounded-xl bg-slate-800/40 border border-white/[0.04] hover:bg-slate-800/70 transition cursor-pointer"
                      onClick={() => window.dispatchEvent(new CustomEvent("open-tenant", { detail: inv.tenant_id }))}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-2 h-2 rounded-full ${inv.status === "paid" ? "bg-emerald-400" : inv.status === "overdue" ? "bg-rose-400" : "bg-amber-400"}`} />
                        <div>
                          <div className="text-xs text-slate-200 font-medium">{inv.tenant_name}</div>
                          <div className="flex items-center gap-2 text-[10px] text-slate-500 mt-0.5">
                            <span className="font-mono font-semibold text-slate-400">House {inv.unit_number}</span>
                            <span>·</span>
                            <span className="capitalize">{inv.invoice_type}</span>
                            <span>·</span>
                            <span className="font-mono">{inv.invoice_number || inv.id?.slice(0, 8)}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <div className="text-xs text-emerald-400 font-mono">KES {money(inv.amount)}</div>
                          {inv.balance > 0 && (
                            <div className="text-[10px] text-rose-400 font-mono">Bal: KES {money(inv.balance)}</div>
                          )}
                        </div>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium uppercase ${statusColors[inv.status || "pending"] || statusColors.pending}`}>
                          {inv.status || "pending"}
                        </span>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function MonthStat({ icon, label, value, suffix, color, bg, delay }: {
  icon: React.ReactNode; label: string; value: number; suffix?: string; color: string; bg: string; delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, type: "spring", stiffness: 200, damping: 22 }}
      whileHover={{ y: -2 }}
      className={`rounded-xl ${bg} border border-white/[0.06] p-3 backdrop-blur`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] uppercase tracking-wider text-slate-400">{label}</span>
        <span className={color}>{icon}</span>
      </div>
      <div className={`text-lg font-bold ${color}`}>
        {suffix === "%" ? (
          <><AnimatedNumber value={Math.round(value)} />%</>
        ) : (
          <>KES <AnimatedNumber value={money(value)} /></>
        )}
      </div>
    </motion.div>
  );
}
