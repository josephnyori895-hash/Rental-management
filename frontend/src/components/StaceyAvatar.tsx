import { motion } from "framer-motion";

interface Props {
  size?: number;
  glowing?: boolean;
  pulse?: boolean;
}

export default function StaceyAvatar({ size = 48, glowing = true, pulse = true }: Props) {
  return (
    <div className="relative" style={{ width: size, height: size }}>
      {/* Glow ring */}
      {glowing && (
        <motion.div
          className="absolute inset-0 rounded-full"
          style={{
            background: "radial-gradient(circle, rgba(52,211,153,0.2) 0%, transparent 70%)",
            filter: "blur(8px)",
          }}
          animate={pulse ? { scale: [1, 1.15, 1], opacity: [0.6, 1, 0.6] } : {}}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        />
      )}

      {/* Avatar circle */}
      <div
        className="relative rounded-full flex items-center justify-center overflow-hidden"
        style={{
          width: size,
          height: size,
          background: "linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)",
          border: "1px solid rgba(52,211,153,0.3)",
          boxShadow: glowing ? "0 0 20px rgba(52,211,153,0.15), inset 0 0 20px rgba(52,211,153,0.05)" : "none",
        }}
      >
        {/* Inner ring */}
        <div className="absolute inset-1 rounded-full border border-emerald-500/10" />

        {/* Stacey "S" letterform */}
        <svg
          viewBox="0 0 40 40"
          className="relative z-10"
          style={{ width: size * 0.55, height: size * 0.55 }}
        >
          <defs>
            <linearGradient id="stacey-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#34d399" />
              <stop offset="50%" stopColor="#38bdf8" />
              <stop offset="100%" stopColor="#34d399" />
            </linearGradient>
          </defs>

          {/* Stylized S — flowing curve */}
          <motion.path
            d="M 12 28 C 12 28, 10 24, 14 22 C 18 20, 24 24, 26 22 C 28 20, 28 16, 26 14 C 24 12, 18 12, 14 14"
            fill="none"
            stroke="url(#stacey-grad)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1.5, ease: "easeInOut" }}
          />

          {/* Accent dot */}
          <motion.circle
            cx="26" cy="28" r="2"
            fill="#34d399"
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
        </svg>

        {/* Scanning line effect */}
        <motion.div
          className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-400/40 to-transparent"
          animate={{ top: ["0%", "100%", "0%"] }}
          transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
        />
      </div>

      {/* Status dot */}
      <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 border-2 border-slate-900 shadow-[0_0_6px_rgba(52,211,153,0.6)]" />
    </div>
  );
}

/* ─── Full Assistant Panel ─── */

interface PanelProps {
  open: boolean;
  onClose: () => void;
}

export function StaceyPanel({ open, onClose }: PanelProps) {
  if (!open) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.95 }}
      className="absolute bottom-full right-0 mb-3 w-72 rounded-2xl border border-slate-700/50 bg-slate-900/95 backdrop-blur-2xl shadow-2xl shadow-black/40 overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800">
        <StaceyAvatar size={32} />
        <div>
          <div className="text-sm font-semibold text-white">Stacey</div>
          <div className="text-[10px] text-emerald-400/80 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Active · AI Assistant
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-2">
        <p className="text-xs text-slate-400 leading-relaxed">
          At your service, sir. Monitoring {87} payments, {12} tenants, and {2} properties.
        </p>
        <div className="flex flex-wrap gap-1.5">
          <span className="px-2 py-0.5 rounded-full bg-slate-800 text-[10px] text-slate-400 border border-slate-700/50">BTC · 67,432</span>
          <span className="px-2 py-0.5 rounded-full bg-slate-800 text-[10px] text-slate-400 border border-slate-700/50">XRP · 0.4821</span>
          <span className="px-2 py-0.5 rounded-full bg-slate-800 text-[10px] text-slate-400 border border-slate-700/50">System OK</span>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-slate-800 px-4 py-2.5 flex justify-between items-center">
        <span className="text-[9px] text-slate-600">
          v2.0 · Jarvis Protocol
        </span>
        <span className="text-[10px] text-slate-500 font-mono">
          {new Date().toLocaleTimeString()}
        </span>
      </div>
    </motion.div>
  );
}
