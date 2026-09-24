import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { loginOwner, setToken } from "../lib/api";
import { Building2, Key, Loader2 } from "lucide-react";

export default function Login({ onLogin }: { onLogin: (t: string) => void }) {
  const [email, setEmail] = useState("owner@rental.dev");
  const [password, setPassword] = useState("rental1234");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: any) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const r = await loginOwner(email, password);
      setToken(r.access_token);
      onLogin(r.access_token);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative">
      <motion.form
        onSubmit={submit}
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 100, damping: 15 }}
        className="relative w-full max-w-sm bg-slate-900/60 backdrop-blur-2xl border border-white/[0.08] rounded-2xl p-6 space-y-4 shadow-2xl shadow-black/50 overflow-hidden"
      >
        <div className="absolute inset-0 bg-gradient-to-br from-white/[0.04] to-transparent pointer-events-none" />
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-emerald-400/50 to-transparent" />

        <div className="relative text-center mb-2">
          <motion.div
            initial={{ scale: 0, rotate: -180 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ type: "spring", stiffness: 200, delay: 0.1 }}
            className="w-14 h-14 bg-gradient-to-br from-emerald-400 to-sky-400 rounded-xl flex items-center justify-center mx-auto mb-3 shadow-lg shadow-emerald-500/30 relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-transparent via-white/20 to-transparent animate-aurora-shift" />
            <Building2 className="w-7 h-7 text-slate-950 relative z-10" />
          </motion.div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-emerald-400 to-sky-400 bg-clip-text text-transparent">
            Rental OS
          </h1>
          <p className="text-[11px] text-slate-500 mt-0.5">Owner Console · Property Management</p>
        </div>

        <div className="relative space-y-3">
          <div className="space-y-1">
            <label className="text-[10px] uppercase tracking-wider text-slate-500">Email</label>
            <input
              className="input"
              placeholder="owner@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] uppercase tracking-wider text-slate-500">Password</label>
            <input
              className="input"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
        </div>

        <AnimatePresence>
          {err && (
            <motion.p
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="relative text-rose-400 text-sm flex items-center gap-1.5"
            >
              <Key className="w-3 h-3" /> {err}
            </motion.p>
          )}
        </AnimatePresence>

        <motion.button
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          disabled={loading}
          className="relative w-full bg-gradient-to-r from-emerald-500 to-emerald-600 text-slate-950 font-semibold py-2.5 rounded-lg hover:from-emerald-400 hover:to-emerald-500 transition-all duration-200 shadow-lg shadow-emerald-500/20 disabled:opacity-60 flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Signing in...
            </>
          ) : (
            "Sign in"
          )}
        </motion.button>

        <p className="relative text-[10px] text-slate-600 text-center leading-relaxed">
          Demo: owner@rental.dev / rental1234
          <br />
          <span className="text-slate-700">Caretakers & tenants sign in via WhatsApp.</span>
        </p>
      </motion.form>
    </div>
  );
}
