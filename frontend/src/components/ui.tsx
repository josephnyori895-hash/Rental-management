import { motion, useMotionValue, useSpring, animate } from "framer-motion";
import { useEffect, useRef, useState } from "react";

const spring = { type: "spring" as const, stiffness: 200, damping: 22 };

export function Card({ children, className = "", delay = 0, onClick, hover = true }: {
  children: React.ReactNode; className?: string; delay?: number; onClick?: () => void; hover?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, ...spring }}
      whileHover={hover ? { y: -3, transition: { duration: 0.2 } } : undefined}
      onClick={onClick}
      className={`group relative rounded-2xl bg-slate-900/60 backdrop-blur-xl border border-white/[0.06] overflow-hidden
        ${hover ? "cursor-pointer hover:border-emerald-500/20 hover:shadow-lg hover:shadow-emerald-500/[0.03] transition-all duration-300" : ""}
        ${onClick ? "cursor-pointer" : ""}
        ${className}
      `}
    >
      {hover && (
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.03] to-transparent translate-x-[-200%] group-hover:translate-x-[200%] transition-transform duration-700 pointer-events-none" />
      )}
      <div className="relative z-10">{children}</div>
    </motion.div>
  );
}

export function GlassCard({ children, className = "", delay = 0, onClick }: {
  children: React.ReactNode; className?: string; delay?: number; onClick?: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, ...spring }}
      whileHover={onClick ? { y: -3, transition: { duration: 0.2 } } : undefined}
      onClick={onClick}
      className={`relative rounded-2xl overflow-hidden
        bg-gradient-to-br from-white/[0.06] to-white/[0.02]
        backdrop-blur-2xl border border-white/[0.08]
        shadow-xl shadow-black/20
        ${onClick ? "cursor-pointer hover:border-white/20 transition-all duration-300" : ""}
        ${className}
      `}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-white/[0.02] to-transparent pointer-events-none" />
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute inset-y-0 -left-full w-full bg-gradient-to-r from-transparent via-white/[0.04] to-transparent group-hover:translate-x-[200%] transition-transform duration-1000" />
      </div>
      <div className="relative z-10">{children}</div>
    </motion.div>
  );
}

export function StatCard({
  icon, label, value, suffix = "", sub, color = "emerald", pulse, delay = 0, sparkline,
}: {
  icon: React.ReactNode; label: string; value: string | number;
  suffix?: string; sub?: string; color?: string; pulse?: boolean; delay?: number;
  sparkline?: number[];
}) {
  const colorMap: Record<string, string> = {
    emerald: "text-emerald-400", rose: "text-rose-400", slate: "text-slate-400",
    white: "text-white", sky: "text-sky-400", amber: "text-amber-400",
    violet: "text-violet-400",
  };
  const gradMap: Record<string, string> = {
    emerald: "from-emerald-500/10 to-emerald-600/[0.02]",
    rose: "from-rose-500/10 to-rose-600/[0.02]",
    slate: "from-slate-500/10 to-slate-600/[0.02]",
    sky: "from-sky-500/10 to-sky-600/[0.02]",
    amber: "from-amber-500/10 to-amber-600/[0.02]",
    violet: "from-violet-500/10 to-violet-600/[0.02]",
  };
  const borderMap: Record<string, string> = {
    emerald: "border-emerald-500/15", rose: "border-rose-500/15",
    slate: "border-slate-500/15", sky: "border-sky-500/15", amber: "border-amber-500/15",
    violet: "border-violet-500/15",
  };
  const glowMap: Record<string, string> = {
    emerald: "rgba(52,211,153,0.15)", rose: "rgba(244,63,94,0.15)",
    slate: "rgba(148,163,184,0.1)", sky: "rgba(56,189,248,0.15)",
    amber: "rgba(245,158,11,0.15)", violet: "rgba(167,139,250,0.15)",
  };
  const isObj = typeof value === "object" && value !== null;

  return (
    <Card className={`relative p-4 overflow-hidden bg-gradient-to-br ${gradMap[color] || gradMap.emerald} border ${borderMap[color] || borderMap.emerald}`} delay={delay} hover>
      {pulse && <div className="absolute -top-4 -right-4 w-16 h-16 rounded-full blur-2xl" style={{ background: glowMap[color] || glowMap.emerald }} />}
      <div className="flex items-start justify-between mb-1 relative z-10">
        <div className={`p-1.5 rounded-lg bg-white/[0.04] backdrop-blur ${colorMap[color] || colorMap.emerald}`}>
          {icon}
        </div>
        {pulse && (
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[8px] uppercase tracking-wider text-slate-500 font-medium">Live</span>
          </div>
        )}
      </div>
      {isObj ? (
        <>{value}</>
      ) : (
        <>
          <div className={`text-2xl font-bold font-heading tracking-tight ${colorMap[color] || colorMap.emerald}`} style={{ animation: "number-pop 0.5s ease-out" }}>
            <AnimatedNumber value={value} />{suffix && <span className="text-sm font-normal text-slate-500 ml-1">{suffix}</span>}
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5">{label}</div>
          {sub && <div className="text-[10px] text-slate-600 mt-0.5">{sub}</div>}
          {sparkline && <Sparkline data={sparkline} color={color} />}
        </>
      )}
    </Card>
  );
}

export function Sparkline({ data, color = "emerald", height = 30 }: { data: number[]; color?: string; height?: number }) {
  const colorMap: Record<string, string> = {
    emerald: "#34d399", rose: "#f43f5e", slate: "#94a3b8",
    sky: "#38bdf8", amber: "#f59e0b", violet: "#a78bfa",
  };
  const c = colorMap[color] || colorMap.emerald;
  if (data.length < 2) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const w = 100;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = height - ((v - min) / range) * height;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" className="mt-2">
      <defs>
        <linearGradient id={`spark-${color}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={c} stopOpacity="0.3" />
          <stop offset="100%" stopColor={c} stopOpacity="0" />
        </linearGradient>
      </defs>
      <motion.polyline
        points={`0,${height} ${points} ${w},${height}`}
        fill={`url(#spark-${color})`}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      />
      <motion.polyline
        points={points}
        fill="none"
        stroke={c}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1, ease: "easeInOut" }}
      />
    </svg>
  );
}

export function AnimatedNumber({ value, duration = 1 }: { value: string | number; duration?: number }) {
  const isNum = typeof value === "number" || (typeof value === "string" && !isNaN(parseFloat(value)) && !value.includes(","));
  const [display, setDisplay] = useState("0");
  const prevRef = useRef(0);

  useEffect(() => {
    if (!isNum) { setDisplay(String(value)); return; }
    const target = typeof value === "string" ? parseFloat(value) : value;
    const prev = prevRef.current;
    const controls = animate(prev, target, {
      duration,
      ease: "easeOut",
      onUpdate: (v) => {
        setDisplay(v.toLocaleString("en-KE", { minimumFractionDigits: 0, maximumFractionDigits: 2 }));
      },
    });
    prevRef.current = target;
    return () => controls.stop();
  }, [value, duration, isNum]);

  if (!isNum) return <>{value}</>;
  return <>{display}</>;
}

export function SectionTitle({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-1">
      <h3 className="text-sm font-semibold text-slate-200 font-heading">{title}</h3>
      {sub && <p className="text-[11px] text-slate-500">{sub}</p>}
    </div>
  );
}

export function Badge({ children, color = "emerald" }: { children: React.ReactNode; color?: string }) {
  const colors: Record<string, string> = {
    emerald: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/25",
    rose: "bg-rose-500/15 text-rose-300 border border-rose-500/25",
    amber: "bg-amber-500/15 text-amber-300 border border-amber-500/25",
    sky: "bg-sky-500/15 text-sky-300 border border-sky-500/25",
    slate: "bg-slate-500/15 text-slate-300 border border-slate-500/25",
    violet: "bg-violet-500/15 text-violet-300 border border-violet-500/25",
    white: "bg-white/10 text-white border border-white/20",
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium ${colors[color] || colors.slate}`}>
      {children}
    </span>
  );
}

export function PageHeader({ title, sub, actions }: { title: string; sub?: string; actions?: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="flex items-center justify-between flex-wrap gap-2"
    >
      <div>
        <h1 className="text-xl font-bold text-white font-heading tracking-tight">{title}</h1>
        {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </motion.div>
  );
}

export function EmptyState({ icon, text, sub }: { icon: React.ReactNode; text: string; sub?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="text-slate-700 mb-4 opacity-60">{icon}</div>
      <p className="text-sm text-slate-500">{text}</p>
      {sub && <p className="text-xs text-slate-600 mt-1">{sub}</p>}
    </div>
  );
}

export function money(v: string | number | undefined | null): string {
  const n = typeof v === "string" ? parseFloat(v) : (v ?? 0);
  return n.toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
