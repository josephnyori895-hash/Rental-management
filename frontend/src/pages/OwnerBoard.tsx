import { useEffect, useState, useRef, useMemo, useCallback } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { PieChart, BarChart } from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";
import "echarts/lib/component/tooltip";
import "echarts/lib/component/legend";
import "echarts/lib/component/grid";
import {
  Building2,
  Users,
  DoorOpen,
  DollarSign,
  AlertTriangle,
  BedDouble,
  TrendingUp,
  CreditCard,
  Zap,
  Search,
  Home,
  User,
  CheckCircle2,
  Clock,
  Send,
  Loader2,
  Plus,
} from "lucide-react";
import { getBoard, dispatchMonthlyReport } from "../lib/api";
import TenantDetail from "../components/TenantDetail";

echarts.use([PieChart, BarChart, CanvasRenderer]);

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06, delayChildren: 0.08 } },
} as const;

const item = {
  hidden: { y: 20, opacity: 0 },
  show: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 120, damping: 14 } },
} as const;

function AnimatedNumber({ value, suffix = "" }: { value: number; suffix?: string }) {
  const [display, setDisplay] = useState(0);
  const prev = useRef(0);
  useEffect(() => {
    let start = prev.current;
    const end = value;
    const duration = 600;
    const step = Math.max(1, Math.ceil((end - start) / (duration / 16)));
    if (start === end) { setDisplay(end); return; }
    const timer = setInterval(() => {
      start += step;
      if ((step > 0 && start >= end) || (step < 0 && start <= end)) { start = end; clearInterval(timer); }
      setDisplay(start);
    }, 16);
    prev.current = end;
    return () => clearInterval(timer);
  }, [value]);
  return <>{display.toLocaleString()}{suffix}</>;
}

type FilterTab = "all" | "occupied" | "vacant" | "unpaid";

const FILTERS: { key: FilterTab; label: string; icon: React.ReactNode }[] = [
  { key: "all", label: "All Rooms", icon: <Home className="w-3.5 h-3.5" /> },
  { key: "occupied", label: "Occupied", icon: <User className="w-3.5 h-3.5" /> },
  { key: "vacant", label: "Vacant", icon: <DoorOpen className="w-3.5 h-3.5" /> },
  { key: "unpaid", label: "Unpaid", icon: <AlertTriangle className="w-3.5 h-3.5" /> },
];

export default function OwnerBoard() {
  const [board, setBoard] = useState<any>(null);
  const [err, setErr] = useState("");
  const [selectedTenant, setSelectedTenant] = useState<any>(null);
  const [quickView, setQuickView] = useState<{ unit: any; x: number; y: number } | null>(null);
  const [filter, setFilter] = useState<FilterTab>("all");
  const [search, setSearch] = useState("");
  const [dispatching, setDispatching] = useState(false);
  const [dispatchMsg, setDispatchMsg] = useState<{ ok: boolean; msg: string } | null>(null);

  const load = async () => {
    try { const data = await getBoard(); setBoard(data); }
    catch (e: any) { setErr(e.message); }
  };

  const handleSendReport = useCallback(async () => {
    setDispatching(true);
    setDispatchMsg(null);
    try {
      const now = new Date();
      const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
      const result = await dispatchMonthlyReport(month);
      setDispatchMsg({
        ok: result?.success ?? false,
        msg: result?.success
          ? `Monthly report sent for ${result.period ?? month}. WhatsApp: ${result.dispatch?.whatsapp ? "✓" : "⚠ check config"}`
          : result?.error || "Report generation failed",
      });
    } catch (e: any) {
      setDispatchMsg({ ok: false, msg: e.message || "Dispatch failed" });
    } finally {
      setDispatching(false);
      setTimeout(() => setDispatchMsg(null), 6000);
    }
  }, []);

  useEffect(() => { load(); const id = setInterval(load, 10000); return () => clearInterval(id); }, []);

  if (err) return <p className="text-rose-400">{err}</p>;
  if (!board) return (
    <div className="flex items-center justify-center h-64">
      <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}>
        <Zap className="w-8 h-8 text-emerald-400" />
      </motion.div>
    </div>
  );

  const t = board.totals;

  // ── Filter units across all hostels ──
  const allUnits = useMemo(() => {
    const units: any[] = [];
    board.hostels.forEach((h: any) => {
      h.units.forEach((u: any) => {
        units.push({ ...u, hostel_name: h.name });
      });
    });
    return units;
  }, [board]);

  const filteredUnits = useMemo(() => {
    let list = allUnits;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((u: any) =>
        u.unit_number?.toLowerCase().includes(q) ||
        u.tenant_name?.toLowerCase().includes(q)
      );
    }
    if (filter === "occupied") return list.filter((u: any) => u.light !== "empty");
    if (filter === "vacant") return list.filter((u: any) => u.light === "empty");
    if (filter === "unpaid") return list.filter((u: any) => u.light === "red");
    return list;
  }, [allUnits, filter, search]);

  const occupancyOption = {
    tooltip: { trigger: "item" as const, backgroundColor: "#0f172a", borderColor: "#334155", textStyle: { color: "#e2e8f0" } },
    legend: { bottom: 0, textStyle: { color: "#94a3b8" } },
    series: [{
      type: "pie", radius: ["45%", "70%"], avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: "#0f172a", borderWidth: 2 },
      label: { show: false },
      data: [
        { value: t.occupied, name: "Occupied", itemStyle: { color: "#10b981" } },
        { value: t.vacant, name: "Vacant", itemStyle: { color: "#475569" } },
      ],
    }],
  };

  const revenueOption = {
    tooltip: { trigger: "axis" as const, backgroundColor: "#0f172a", borderColor: "#334155", textStyle: { color: "#e2e8f0" } },
    grid: { left: "3%", right: "4%", bottom: "3%", top: "10%", containLabel: true },
    xAxis: { type: "category" as const, data: ["Expected", "Collected", "Outstanding"], axisLabel: { color: "#94a3b8" } },
    yAxis: {
      type: "value" as const,
      axisLabel: { color: "#64748b", formatter: (v: number) => `KES ${(v / 1000).toFixed(0)}k` },
      splitLine: { lineStyle: { color: "#1e293b", type: "dashed" as const } },
    },
    series: [{
      type: "bar" as const, barWidth: "40%",
      itemStyle: { borderRadius: [6, 6, 0, 0], color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "#10b981" }, { offset: 1, color: "#047857" }]) },
      data: [t.expected, t.collected, t.outstanding].map((v, i) => ({
        value: v,
        itemStyle: i === 2 ? { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "#f43f5e" }, { offset: 1, color: "#9f1239" }]) } : undefined,
      })),
    }],
  };

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-6">
      {/* ── Header ── */}
      <motion.div variants={item} className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-sky-400 bg-clip-text text-transparent">
            Nyorii Hostels
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {t.occupied} occupied · {t.vacant} vacant · {t.paid} paid · {t.unpaid} unpaid
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleSendReport}
            disabled={dispatching}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-violet-500/15 text-violet-300 border border-violet-500/30 hover:bg-violet-500/25 disabled:opacity-50 transition"
          >
            {dispatching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
            Send Monthly Report
          </button>
          <motion.div animate={{ opacity: [0.5, 1, 0.5] }} transition={{ repeat: Infinity, duration: 2 }}
            className="flex items-center gap-2 text-xs text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400" /> Live
          </motion.div>
        </div>
      </motion.div>

      {/* ── Dispatch banner ── */}
      <AnimatePresence>
        {dispatchMsg && (
          <motion.div
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            className={`flex items-center gap-2 p-3 rounded-xl border text-xs ${
              dispatchMsg.ok
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                : "bg-rose-500/10 border-rose-500/30 text-rose-300"
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
            {dispatchMsg.msg}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Stats Row ── */}
      <motion.div variants={item} className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <StatCard icon={<Building2 className="w-4 h-4" />} label="Occupied" value={t.occupied} color="emerald" gradient="from-emerald-500/20 to-emerald-600/5" />
        <StatCard icon={<DoorOpen className="w-4 h-4" />} label="Vacant" value={t.vacant} color="slate" gradient="from-slate-500/20 to-slate-600/5" />
        <StatCard icon={<CreditCard className="w-4 h-4" />} label="Paid" value={t.paid} color="emerald" gradient="from-green-500/20 to-green-600/5" />
        <StatCard icon={<AlertTriangle className="w-4 h-4" />} label="Unpaid" value={t.unpaid} color="rose" gradient="from-rose-500/20 to-rose-600/5" pulse />
        <StatCard icon={<BedDouble className="w-4 h-4" />} label="Total rooms" value={t.occupied + t.vacant} color="white" gradient="from-blue-500/20 to-blue-600/5" />
        <StatCard icon={<Users className="w-4 h-4" />} label="Occupancy" value={t.occupied + t.vacant > 0 ? Math.round((t.occupied / (t.occupied + t.vacant)) * 100) : 0} suffix="%" color="sky" gradient="from-sky-500/20 to-sky-600/5" />
      </motion.div>

      {/* ── Charts ── */}
      <motion.div variants={item} className="grid md:grid-cols-2 gap-4">
        <div className="rounded-xl bg-slate-900/80 backdrop-blur border border-slate-800 p-4">
          <h3 className="text-sm font-semibold text-slate-300 mb-1">Occupancy Split</h3>
          <p className="text-xs text-slate-500 mb-2">{t.occupied} occupied · {t.vacant} vacant</p>
          <ReactEChartsCore echarts={echarts} option={occupancyOption} style={{ height: 200 }} />
        </div>
        <div className="rounded-xl bg-slate-900/80 backdrop-blur border border-slate-800 p-4">
          <h3 className="text-sm font-semibold text-slate-300 mb-1">Revenue Overview</h3>
          <p className="text-xs text-slate-500 mb-2">KES {t.expected.toLocaleString()} expected · KES {t.collected.toLocaleString()} collected</p>
          <ReactEChartsCore echarts={echarts} option={revenueOption} style={{ height: 200 }} />
        </div>
      </motion.div>

      {/* ── Revenue Summary Bar ── */}
      <motion.div variants={item} className="rounded-xl bg-slate-900/80 backdrop-blur border border-slate-800 p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-300">Revenue Summary</h3>
          <TrendingUp className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-xs text-slate-500">Expected / mo</div>
            <div className="text-lg font-bold text-emerald-400">KES <AnimatedNumber value={t.expected} /></div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Collected / mo</div>
            <div className="text-lg font-bold text-green-400">KES <AnimatedNumber value={t.collected} /></div>
          </div>
          <div>
            <div className="text-xs text-slate-500">Outstanding</div>
            <div className="text-lg font-bold text-rose-400">KES <AnimatedNumber value={t.outstanding} /></div>
          </div>
        </div>
        <div className="mt-3 h-2 bg-slate-800 rounded-full overflow-hidden">
          <motion.div initial={{ width: 0 }} animate={{ width: `${t.expected > 0 ? Math.min((t.collected / t.expected) * 100, 100) : 0}%` }}
            transition={{ duration: 1, ease: "easeOut" }} className="h-full bg-gradient-to-r from-emerald-500 to-green-400 rounded-full" />
        </div>
        <div className="text-xs text-slate-500 mt-1">{t.expected > 0 ? Math.round((t.collected / t.expected) * 100) : 0}% collection rate</div>
      </motion.div>

      {/* ── Filter Tabs ── */}
      <motion.div variants={item} className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button key={f.key}
            onClick={() => setFilter(f.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              filter === f.key
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.15)]"
                : "bg-slate-800/50 text-slate-400 border border-slate-700/50 hover:bg-slate-700/50"
            }`}
          >
            {f.icon} {f.label}
          </button>
        ))}
        <div className="relative ml-auto">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-500" />
          <input
            placeholder="Search room or tenant..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-44 bg-slate-800/50 border border-slate-700/50 rounded-lg pl-7 pr-2 py-1.5 text-xs outline-none focus:border-emerald-500/50 placeholder:text-slate-600"
          />
        </div>
      </motion.div>

      {/* ── Unified Room Grid ── */}
      <motion.div variants={item}>
        {filter === "all" ? (
          /* Group by hostel */
          board.hostels.map((h: any, idx: number) => (
            <motion.div key={h.property_id} variants={item}
              className="rounded-xl bg-slate-900/80 backdrop-blur border border-slate-700/50 p-5 mb-4"
            >
              <HostelHeader h={h} />
              <RoomGrid
                units={h.units.filter((u: any) => !search || u.unit_number?.toLowerCase().includes(search.toLowerCase()) || u.tenant_name?.toLowerCase().includes(search.toLowerCase()))}
                hostelName={h.name}
                onQuickView={(u, el) => {
                  const rect = el.getBoundingClientRect();
                  setQuickView({ unit: u, x: rect.right + 8, y: rect.top });
                }}
                onFullView={setSelectedTenant}
              />
              <PaidVacantSplit h={h} onSelect={setSelectedTenant} />
            </motion.div>
          ))
        ) : (
          /* Flat view: show filtered units across all hostels */
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
            {filteredUnits.map((u: any, i: number) => (
              <RoomCard key={u.unit_id || i} unit={u}
                onQuickView={(unit, el) => {
                  const rect = el.getBoundingClientRect();
                  setQuickView({ unit, x: rect.right + 8, y: rect.top });
                }}
                onFullView={setSelectedTenant}
              />
            ))}
          </div>
        )}
      </motion.div>

      {/* ── Quick View Popover (portal to body) ── */}
      <AnimatePresence>
        {quickView && createPortal(
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40"
              onClick={() => setQuickView(null)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.92, y: -6 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.92, y: -6 }}
              transition={{ type: "spring", stiffness: 350, damping: 25 }}
              style={{
                left: Math.min(quickView.x, window.innerWidth - 280),
                top: Math.min(quickView.y, window.innerHeight - 240),
              }}
              className="fixed z-50 w-64 rounded-xl bg-slate-900/95 backdrop-blur-xl border border-slate-700/70 shadow-2xl shadow-black/50 overflow-hidden"
            >
              <QuickViewPopover
                unit={quickView.unit}
                onClose={() => setQuickView(null)}
                onFullView={() => {
                  setSelectedTenant(quickView.unit);
                  setQuickView(null);
                }}
              />
            </motion.div>
          </>,
          document.body
        )}
      </AnimatePresence>

      {/* ── Full Tenant Detail Modal ── */}
      <TenantDetail open={!!selectedTenant} tenant={selectedTenant} onClose={() => setSelectedTenant(null)} />
    </motion.div>
  );
}

// ── Hostel Header ──
function HostelHeader({ h }: { h: any }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <Building2 className="w-5 h-5 text-emerald-400" />
        <h2 className="text-lg font-semibold">{h.name}</h2>
        <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full">{h.property_type}</span>
      </div>
      <div className="flex gap-3 text-xs">
        <span className="text-emerald-400">{h.occupied} occ</span>
        <span className="text-slate-500">{h.vacant} vac</span>
        <span className="text-green-400">{h.paid_count} paid</span>
        {h.unpaid_count > 0 && (
          <motion.span animate={{ opacity: [1, 0.4, 1] }} transition={{ repeat: Infinity, duration: 1.5 }} className="text-rose-400">
            {h.unpaid_count} unpaid
          </motion.span>
        )}
      </div>
    </div>
  );
}

// ── Room Grid ──
function RoomGrid({ units, hostelName, onQuickView, onFullView }: {
  units: any[];
  hostelName: string;
  onQuickView: (unit: any, el: HTMLElement) => void;
  onFullView: (unit: any) => void;
}) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2 mb-4">
      {units.map((u: any) => (
        <RoomCard key={u.unit_id} unit={{ ...u, hostel_name: hostelName }}
          onQuickView={(unit, el) => onQuickView(unit, el)}
          onFullView={() => onFullView({ ...u, hostel_name: hostelName })}
        />
      ))}
    </div>
  );
}

// ── Single Room Card ──
function RoomCard({ unit: u, onQuickView, onFullView }: {
  unit: any;
  onQuickView: (unit: any, el: HTMLElement) => void;
  onFullView: (unit: any) => void;
}) {
  const isVacant = u.light === "empty";
  const isUnpaid = u.light === "red";
  const isPaid = u.light === "green";
  const rent = u.rent_amount || 0;
  const paid = u.amount_paid || 0;
  const bal = u.balance !== undefined ? u.balance : (isUnpaid ? Math.max(0, rent - paid) : 0);
  const clickTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleClick = (e: React.MouseEvent) => {
    if (clickTimer.current) {
      // Second click within timer → double-click
      clearTimeout(clickTimer.current);
      clickTimer.current = null;
      onFullView(u);
    } else {
      // First click → wait to see if double-click follows
      clickTimer.current = setTimeout(() => {
        clickTimer.current = null;
        onQuickView(u, e.currentTarget as HTMLElement);
      }, 250);
    }
  };

  return (
    <motion.div
      layout
      initial={{ scale: 0.3, opacity: 0 }}
      animate={{
        scale: 1, opacity: 1,
        backgroundColor: isPaid ? "rgba(16, 185, 129, 0.12)"
          : isUnpaid ? "rgba(244, 63, 94, 0.12)"
          : "rgba(30, 41, 59, 0.6)",
      }}
      whileHover={{
        scale: 1.06,
        y: -3,
        transition: { type: "spring", stiffness: 300, damping: 12 },
      }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      onClick={handleClick}
      className={`relative rounded-xl p-2.5 flex flex-col items-center text-center
        border cursor-pointer overflow-hidden backdrop-blur-sm group select-none
        ${isPaid
          ? "border-emerald-500/40 shadow-sm shadow-emerald-500/10 hover:border-emerald-400/60 hover:shadow-lg hover:shadow-emerald-500/15"
          : isUnpaid
          ? "border-rose-500/40 shadow-sm shadow-rose-500/10 hover:border-rose-400/60 hover:shadow-lg hover:shadow-rose-500/15"
          : "border-slate-700/60 hover:border-sky-400/40 hover:shadow-lg hover:shadow-sky-500/10 hover:bg-slate-800/80"
        }`}
    >
      {/* Animated glow for unpaid */}
      {isUnpaid && (
        <motion.div
          animate={{ opacity: [0.15, 0.35, 0.15] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="absolute inset-0 bg-gradient-to-t from-rose-500/15 to-transparent pointer-events-none"
        />
      )}

      {/* Static glow for paid */}
      {isPaid && (
        <div className="absolute inset-0 bg-gradient-to-t from-emerald-500/10 to-transparent pointer-events-none" />
      )}

      {/* Vacant subtle hover glow */}
      {isVacant && (
        <div className="absolute inset-0 bg-gradient-to-br from-sky-500/0 via-transparent to-transparent pointer-events-none
          group-hover:from-sky-500/10 transition-all duration-300" />
      )}

      {/* Status icon — top right */}
      <div className="absolute top-1.5 right-1.5 z-10">
        {isPaid && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
        {isUnpaid && <Clock className="w-3.5 h-3.5 text-rose-400" />}
        {isVacant && (
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            <Plus className="w-3 h-3 text-sky-400" />
          </div>
        )}
      </div>

      {/* Unit number — big */}
      <span className="relative text-base font-bold text-white z-10 leading-none mt-0.5">
        {u.unit_number}
      </span>

      {/* Tenant name */}
      {!isVacant && u.tenant_name && (
        <span className="relative text-[10px] text-slate-200 font-medium truncate w-full mt-1 z-10 leading-tight">
          {u.tenant_name}
        </span>
      )}
      {isVacant && (
        <span className="relative text-[9px] text-slate-500 group-hover:text-sky-300 font-medium mt-1 z-10 leading-tight transition-colors duration-200">
          Vacant
        </span>
      )}

      {/* KES Balance Pill / Status Badge */}
      {isVacant ? (
        <span className="relative text-[9px] text-slate-400 group-hover:text-sky-300 font-mono mt-1.5 z-10 px-1.5 py-0.5 rounded bg-slate-800/80 border border-slate-700/60 group-hover:border-sky-400/40 transition-colors duration-200">
          {rent > 0 ? `KES ${rent.toLocaleString()}/mo` : "VACANT"}
        </span>
      ) : isUnpaid ? (
        <motion.div
          animate={{ scale: [1, 1.04, 1] }}
          transition={{ repeat: Infinity, duration: 1.8 }}
          className="relative text-[9.5px] text-rose-200 font-bold font-mono mt-1.5 z-10 px-1.5 py-0.5 rounded bg-rose-500/25 border border-rose-500/40"
        >
          KES {(bal > 0 ? bal : rent).toLocaleString()} DUE
        </motion.div>
      ) : (
        <span className="relative text-[9.5px] text-emerald-300 font-bold font-mono mt-1.5 z-10 px-1.5 py-0.5 rounded bg-emerald-500/20 border border-emerald-500/30">
          KES {(paid > 0 ? paid : rent).toLocaleString()} PAID
        </span>
      )}
    </motion.div>
  );
}

// ── Paid / Vacant split ──
function PaidVacantSplit({ h, onSelect }: { h: any; onSelect: (t: any) => void }) {
  return (
    <div className="grid md:grid-cols-2 gap-4 pt-2 border-t border-slate-800">
      <div>
        <h3 className="text-xs uppercase text-emerald-400 mb-2 flex items-center gap-1">
          <DollarSign className="w-3 h-3" /> Paid Tenants
        </h3>
        <div className="space-y-1">
          {h.paid_tenants.length === 0 && <p className="text-xs text-slate-500">No payments this month</p>}
          {h.paid_tenants.map((p: any, i: number) => (
            <motion.div key={i} initial={{ x: -10, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: i * 0.03 }}
              onClick={() => onSelect({ ...p, status: "occupied", light: "green", hostel_name: h.name })}
              className="flex justify-between items-center text-xs bg-slate-800/50 rounded-lg px-3 py-1.5 cursor-pointer hover:bg-slate-700/50 transition"
            >
              <div className="flex items-center gap-2">
                <span className="text-emerald-400 font-mono text-[10px]">{p.unit_number}</span>
                <span className="text-slate-300">{p.tenant_name}</span>
              </div>
              <span className="text-emerald-300 font-medium">KES {p.amount.toLocaleString()}</span>
            </motion.div>
          ))}
        </div>
      </div>
      <div>
        <h3 className="text-xs uppercase text-slate-400 mb-2 flex items-center gap-1">
          <DoorOpen className="w-3 h-3" /> Vacant Rooms
        </h3>
        <div className="flex flex-wrap gap-1.5">
          {h.vacant_units.length === 0 && <p className="text-xs text-slate-500">All rooms occupied</p>}
          {h.vacant_units.map((v: any, i: number) => (
            <motion.span key={i} initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: i * 0.03, type: "spring" }}
              className="text-xs bg-slate-800 text-slate-300 rounded-md px-2 py-1 border border-slate-700"
            >
              {v.unit_number}
            </motion.span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Quick View Popover ──
function QuickViewPopover({ unit, onClose, onFullView }: {
  unit: any;
  onClose: () => void;
  onFullView: () => void;
}) {
  const isVacant = unit.light === "empty" || !unit.tenant_name;
  const isUnpaid = unit.light === "red";
  const rent = unit.rent_amount || 0;
  const paid = unit.amount_paid || 0;
  const bal = unit.balance !== undefined ? unit.balance : (isUnpaid ? Math.max(0, rent - paid) : 0);

  return (
    <div>
      {/* Header */}
      <div className={`px-4 py-3 border-b ${isVacant ? "border-slate-700/50" : "border-emerald-500/20"}`}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-lg font-bold text-white">{unit.unit_number}</div>
            {!isVacant && unit.tenant_name && (
              <div className="text-xs text-slate-300 font-medium mt-0.5">{unit.tenant_name}</div>
            )}
            {unit.hostel_name && (
              <div className="text-[10px] text-slate-500 mt-0.5">{unit.hostel_name}</div>
            )}
          </div>
          <div className={`w-2 h-2 rounded-full ${isVacant ? "bg-slate-500" : isUnpaid ? "bg-rose-400" : "bg-emerald-400"}`} />
        </div>
      </div>

      {/* Body */}
      <div className="px-4 py-3 space-y-2">
        {isVacant ? (
          <div className="text-xs text-slate-400">Vacant room · KES {rent.toLocaleString()}/mo</div>
        ) : (
          <>
            <div className="flex justify-between text-xs">
              <span className="text-slate-400">Rent</span>
              <span className="text-white font-medium">KES {rent.toLocaleString()}/mo</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-slate-400">Status</span>
              <span className={isUnpaid ? "text-rose-400 font-medium" : "text-emerald-400 font-medium"}>
                {isUnpaid ? `KES ${bal.toLocaleString()} DUE` : "PAID"}
              </span>
            </div>
            {unit.phone && (
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Phone</span>
                <span className="text-slate-300">{unit.phone}</span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Actions */}
      <div className="px-4 py-2.5 border-t border-slate-700/50 flex gap-2">
        {!isVacant && (
          <button onClick={onFullView}
            className="flex-1 text-xs font-medium py-1.5 rounded-lg bg-sky-500/15 text-sky-300 border border-sky-500/25 hover:bg-sky-500/25 transition"
          >
            View Details
          </button>
        )}
        {isVacant && (
          <button onClick={onFullView}
            className="flex-1 text-xs font-medium py-1.5 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 hover:bg-emerald-500/25 transition"
          >
            Assign Tenant
          </button>
        )}
        <button onClick={onClose}
          className="px-3 text-xs py-1.5 rounded-lg bg-slate-800 text-slate-400 border border-slate-700/50 hover:bg-slate-700/50 transition"
        >
          Close
        </button>
      </div>
    </div>
  );
}

// ── Stat Card ──
function StatCard({ icon, label, value, suffix = "", color, gradient, pulse }: {
  icon: React.ReactNode; label: string; value: number; suffix?: string; color: string; gradient: string; pulse?: boolean;
}) {
  const colorMap: Record<string, string> = { emerald: "text-emerald-400", rose: "text-rose-400", slate: "text-slate-400", white: "text-white", sky: "text-sky-400" };
  return (
    <motion.div whileHover={{ y: -2, transition: { type: "spring", stiffness: 300 } }}
      className={`relative rounded-xl bg-gradient-to-br ${gradient} border border-slate-700/50 backdrop-blur p-4 overflow-hidden`}>
      {pulse && <motion.div animate={{ opacity: [0, 0.2, 0] }} transition={{ repeat: Infinity, duration: 2 }} className="absolute inset-0 bg-rose-500/10 rounded-xl" />}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-wider text-slate-400">{label}</span>
        <span className={colorMap[color] || "text-slate-400"}>{icon}</span>
      </div>
      <div className={`text-2xl font-bold ${colorMap[color] || "text-white"}`}>
        <AnimatedNumber value={value} suffix={suffix} />
      </div>
    </motion.div>
  );
}
