import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";
import "echarts/lib/component/tooltip";
import "echarts/lib/component/legend";
import "echarts/lib/component/grid";
import {
  FileText, Download, TrendingUp, FileDown, Send, CheckCircle2,
  AlertTriangle, Loader2, Building2,
} from "lucide-react";
import { getOwnerStatement, getCollectionTrend, getProperties } from "../lib/api";
import { Card, PageHeader, Badge, money } from "../components/ui";

echarts.use([BarChart, LineChart, CanvasRenderer]);

// ── Helper: dispatch monthly report ──────────────────────────────────────────
async function sendMonthlyReport(month: string, propertyId?: string): Promise<any> {
  const token = localStorage.getItem("rental_token");
  const q = new URLSearchParams({ target_month: month, send_whatsapp: "true" });
  if (propertyId) q.set("property_id", propertyId);
  const res = await fetch(`/api/v1/reports/dispatch-monthly?${q}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("Dispatch failed");
  return res.json();
}

export default function Reports() {
  const [statement, setStatement] = useState<any>(null);
  const [trend, setTrend] = useState<any[]>([]);
  const [properties, setProperties] = useState<any[]>([]);
  const [month, setMonth] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
  const [selectedProp, setSelectedProp] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [dispatching, setDispatching] = useState(false);
  const [dispatchResult, setDispatchResult] = useState<{ ok: boolean; msg: string } | null>(null);

  // Load properties for filter
  useEffect(() => {
    getProperties().then((d) => setProperties(d.properties || [])).catch(() => {});
  }, []);

  // Load statement when month or property changes
  useEffect(() => {
    if (!month) return;
    setLoading(true);
    setStatement(null);
    const [y, m] = month.split("-").map(Number);
    const from = `${y}-${String(m).padStart(2, "0")}-01`;
    // Last day of month
    const lastDay = new Date(y, m, 0).getDate();
    const to = `${y}-${String(m).padStart(2, "0")}-${lastDay}`;
    const propParam = selectedProp || undefined;

    Promise.all([
      getOwnerStatement(from, to),
      getCollectionTrend(12),
    ])
      .then(([stmt, tr]) => {
        setStatement(stmt);
        setTrend(tr || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [month, selectedProp]);

  // ── Export PDF ────────────────────────────────────────────────────────────
  const exportPdf = async () => {
    const token = localStorage.getItem("rental_token");
    const [y, m] = month.split("-").map(Number);
    const from = `${y}-${String(m).padStart(2, "0")}-01`;
    const lastDay = new Date(y, m, 0).getDate();
    const to = `${y}-${String(m).padStart(2, "0")}-${lastDay}`;
    try {
      const r = await fetch(`/api/v1/reports/export-statement-pdf?from_date=${from}&to_date=${to}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!r.ok) return;
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `owner-statement-${month}.pdf`; a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {}
  };

  // ── Export CSV ────────────────────────────────────────────────────────────
  const exportCsv = () => {
    if (!statement) return;
    const inc = statement.income || {};
    const exp = statement.expenses || {};
    const ops = statement.operations || {};
    const rows: (string | number)[][] = [
      ["Owner Financial Statement", month],
      [],
      ["INCOME"],
      ["Rental Income Collected", inc.rental_income ?? 0],
      ["Outstanding Rent", inc.outstanding ?? 0],
      ["Total Expected", inc.total_expected ?? 0],
      [],
      ["EXPENSES"],
      ["Total Expenses", exp.total ?? 0],
      ...Object.entries(exp.by_category || {}).map(([k, v]) => [`  ${k}`, v as number]),
      [],
      ["PROFIT & LOSS"],
      ["Gross Profit", statement.profit_loss?.gross_profit ?? 0],
      ["Margin %", statement.profit_loss?.margin_percent ?? 0],
      [],
      ["OPERATIONS"],
      ["Total Units", ops.total_units ?? 0],
      ["Occupied", ops.occupied ?? 0],
      ["Vacant", ops.vacant ?? 0],
      ["Occupancy Rate %", ops.occupancy_rate ?? 0],
      ["Active Leases", ops.active_leases ?? 0],
      ["Payments Received", ops.payment_count ?? 0],
      ["Open Maintenance", ops.open_maintenance_tickets ?? 0],
    ];
    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `owner-statement-${month}.csv`; a.click();
  };

  // ── Send Monthly Report ───────────────────────────────────────────────────
  const handleSendReport = async () => {
    setDispatching(true);
    setDispatchResult(null);
    try {
      const result = await sendMonthlyReport(month, selectedProp || undefined);
      const wa = result?.dispatch?.whatsapp;
      setDispatchResult({
        ok: result?.success ?? false,
        msg: result?.success
          ? `Report for ${result.period} sent! WhatsApp: ${wa ? "✓ delivered" : "⚠ check WhatsApp config"}`
          : result?.error || "Failed to generate report",
      });
    } catch (e: any) {
      setDispatchResult({ ok: false, msg: e.message || "Dispatch failed" });
    } finally {
      setDispatching(false);
    }
  };

  // ── Trend chart ───────────────────────────────────────────────────────────
  const trendOption = {
    tooltip: {
      trigger: "axis" as const,
      backgroundColor: "#0f172a", borderColor: "#334155",
      textStyle: { color: "#e2e8f0" },
    },
    legend: { textStyle: { color: "#94a3b8", fontSize: 10 }, bottom: 0 },
    grid: { left: 50, right: 10, top: 20, bottom: 40 },
    xAxis: {
      type: "category" as const,
      data: trend.map((t: any) => t.label || t.month),
      axisLabel: { color: "#94a3b8", fontSize: 9 },
      axisLine: { lineStyle: { color: "#334155" } },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: {
        color: "#94a3b8", fontSize: 9,
        formatter: (v: number) => `${(v / 1000).toFixed(0)}k`,
      },
      splitLine: { lineStyle: { color: "#1e293b", type: "dashed" as const } },
    },
    series: [
      {
        name: "Expected", type: "line" as const,
        data: trend.map((t: any) => t.expected),
        itemStyle: { color: "#38bdf8" }, smooth: true,
        lineStyle: { width: 2 },
      },
      {
        name: "Collected", type: "bar" as const,
        data: trend.map((t: any) => t.collected),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "#34d399" }, { offset: 1, color: "#059669" },
          ]),
          borderRadius: [4, 4, 0, 0],
        },
      },
    ],
  };

  const inc = statement?.income || {};
  const exp = statement?.expenses || {};
  const pl  = statement?.profit_loss || {};
  const ops = statement?.operations || {};

  return (
    <div className="space-y-5">
      <PageHeader
        title="Reports"
        sub="Owner statements, P&L & monthly financial dispatch"
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={handleSendReport}
              disabled={dispatching}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-violet-500/15 text-violet-300 border border-violet-500/30 hover:bg-violet-500/25 disabled:opacity-50 transition"
            >
              {dispatching
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <Send className="w-3.5 h-3.5" />}
              Send Monthly Report
            </button>
            <button
              onClick={exportPdf}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-sky-500/15 text-sky-300 border border-sky-500/30 hover:bg-sky-500/25 transition"
            >
              <FileDown className="w-3.5 h-3.5" /> Export PDF
            </button>
            <button
              onClick={exportCsv}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25 transition"
            >
              <Download className="w-3.5 h-3.5" /> Export CSV
            </button>
          </div>
        }
      />

      {/* Dispatch result banner */}
      {dispatchResult && (
        <motion.div
          initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
          className={`flex items-start gap-2 p-3 rounded-xl border text-sm ${
            dispatchResult.ok
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
              : "bg-rose-500/10 border-rose-500/30 text-rose-300"
          }`}
        >
          {dispatchResult.ok
            ? <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
            : <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />}
          <span>{dispatchResult.msg}</span>
        </motion.div>
      )}

      {/* Filters row */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Month:</span>
          <input
            type="month" value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-sm outline-none focus:border-emerald-500/50"
          />
        </div>
        {properties.length > 1 && (
          <div className="flex items-center gap-2">
            <Building2 className="w-3.5 h-3.5 text-slate-500" />
            <select
              value={selectedProp}
              onChange={(e) => setSelectedProp(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-sm outline-none focus:border-emerald-500/50"
            >
              <option value="">All Properties</option>
              {properties.map((p: any) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {loading && (
        <div className="flex items-center justify-center h-40 text-slate-500">
          <Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading statement…
        </div>
      )}

      {/* KPI cards */}
      {statement && (
        <motion.div
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-3"
        >
          <KpiCard label="Rental Income" value={inc.rental_income ?? 0} color="emerald" />
          <KpiCard label="Outstanding" value={inc.outstanding ?? 0} color="rose" />
          <KpiCard label="Total Expenses" value={exp.total ?? 0} color="orange" />
          <KpiCard label="Net Profit" value={pl.gross_profit ?? 0} color="sky" />
        </motion.div>
      )}

      {/* Operations row */}
      {statement && (
        <motion.div
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-3"
        >
          <OpsCard label="Occupancy Rate" value={`${ops.occupancy_rate ?? 0}%`} />
          <OpsCard label="Occupied / Total" value={`${ops.occupied ?? 0} / ${ops.total_units ?? 0}`} />
          <OpsCard label="Payments This Period" value={ops.payment_count ?? 0} />
          <OpsCard label="Open Maintenance" value={ops.open_maintenance_tickets ?? 0} />
        </motion.div>
      )}

      {/* P&L breakdown + trend chart */}
      {statement && (
        <motion.div
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="grid md:grid-cols-2 gap-4"
        >
          {/* P&L detail */}
          <Card className="p-4">
            <div className="text-xs text-slate-500 mb-3 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5" /> P&L Breakdown — {month}
            </div>
            <div className="space-y-1.5">
              <SectionLabel label="INCOME" color="emerald" />
              <Row label="Rental Collected" value={inc.rental_income ?? 0} color="emerald" />
              <Row label="Outstanding Rent" value={inc.outstanding ?? 0} color="rose" />
              <Row label="Total Expected" value={inc.total_expected ?? 0} />

              <SectionLabel label="EXPENSES" color="rose" />
              {Object.entries(exp.by_category || {}).map(([k, v]) => (
                <Row key={k} label={k} value={v as number} color="slate" />
              ))}
              <Row label="Total Expenses" value={exp.total ?? 0} color="rose" />

              <div className="border-t border-slate-700 pt-2 flex justify-between text-sm font-bold mt-2">
                <span className="text-slate-300">Net Profit</span>
                <span className={pl.gross_profit >= 0 ? "text-sky-400" : "text-rose-400"}>
                  KES {money(pl.gross_profit ?? 0)}
                  <span className="text-xs font-normal text-slate-500 ml-1">({pl.margin_percent ?? 0}%)</span>
                </span>
              </div>
            </div>
          </Card>

          {/* 12-month collection trend */}
          <Card className="p-4">
            <div className="text-xs text-slate-500 mb-3 flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5" /> 12-Month Collection Trend
            </div>
            {trend.length > 0
              ? <ReactEChartsCore echarts={echarts} option={trendOption} style={{ height: 240 }} />
              : <div className="h-40 flex items-center justify-center text-slate-600 text-sm">No trend data</div>
            }
          </Card>
        </motion.div>
      )}
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function KpiCard({ label, value, color = "white" }: { label: string; value: number; color?: string }) {
  const colors: Record<string, string> = {
    emerald: "text-emerald-400", rose: "text-rose-400",
    sky: "text-sky-400", orange: "text-orange-400", white: "text-white",
  };
  return (
    <Card className="p-4">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      <div className={`text-lg font-bold ${colors[color] || "text-white"}`}>
        KES {money(value)}
      </div>
    </Card>
  );
}

function OpsCard({ label, value }: { label: string; value: number | string }) {
  return (
    <Card className="p-4">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      <div className="text-xl font-bold text-white">{value}</div>
    </Card>
  );
}

function SectionLabel({ label, color }: { label: string; color: string }) {
  const cls = color === "emerald" ? "text-emerald-400" : "text-rose-400";
  return <div className={`text-[10px] uppercase tracking-wider font-semibold pt-2 ${cls}`}>{label}</div>;
}

function Row({ label, value, color = "slate" }: { label: string; value: number; color?: string }) {
  const c = color === "emerald" ? "text-emerald-400" : color === "rose" ? "text-rose-400" : "text-slate-200";
  return (
    <div className="flex justify-between text-xs">
      <span className="text-slate-400 capitalize">{label}</span>
      <span className={c}>KES {money(value)}</span>
    </div>
  );
}
