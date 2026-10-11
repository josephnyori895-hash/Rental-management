import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { loginOwner, setToken } from "../lib/api";
import { Building2, Key, Loader2, CheckCircle2, ShieldCheck } from "lucide-react";
import LoginMarketing from "../components/LoginMarketing";

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

  const benefits = [
    "Track rent and payments in one place",
    "Manage tenants and properties easily",
    "Stay ahead of maintenance requests",
  ];

  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950 text-white lg:grid lg:grid-cols-[1.08fr_0.92fr]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_15%_10%,rgba(16,185,129,0.13),transparent_40%),radial-gradient(ellipse_at_85%_85%,rgba(14,165,233,0.12),transparent_35%)]" />

      <section className="relative flex min-w-0 flex-col justify-center overflow-hidden px-5 pb-3 pt-10 sm:px-8 lg:min-h-screen lg:px-10 lg:py-10 xl:px-14">
        <div className="mx-auto w-full max-w-2xl">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="mb-3 flex items-center gap-3 sm:mb-5"
          >
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-emerald-300/20 bg-gradient-to-br from-emerald-400 to-sky-400 shadow-lg shadow-emerald-500/20">
              <Building2 className="h-5 w-5 text-slate-950" />
            </div>
            <div>
              <div className="text-sm font-bold tracking-wide text-white">Rental OS</div>
              <div className="mt-0.5 text-[10px] uppercase tracking-[0.2em] text-slate-500">Property management, simplified</div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08, duration: 0.55 }}
          >
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.24em] text-emerald-300">A better way to manage rentals</p>
            <h1 className="max-w-xl text-3xl font-bold leading-tight tracking-tight text-white sm:text-4xl xl:text-5xl">
              Your properties.
              <span className="block bg-gradient-to-r from-emerald-300 via-emerald-400 to-sky-300 bg-clip-text text-transparent">All under control.</span>
            </h1>
            <p className="mt-3 max-w-lg text-sm leading-6 text-slate-400 sm:text-base">
              Keep rent collection, tenant records, and property operations moving smoothly from one simple workspace.
            </p>
          </motion.div>

          <div className="mt-4 grid gap-2 sm:mt-5 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
            {benefits.map((benefit, i) => (
              <motion.div
                key={benefit}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.15 + i * 0.08 }}
                className="flex items-center gap-2 text-xs text-slate-300 sm:rounded-xl sm:border sm:border-white/[0.06] sm:bg-white/[0.025] sm:px-3 sm:py-2.5"
              >
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                <span>{benefit}</span>
              </motion.div>
            ))}
          </div>

          <div className="mt-1 sm:mt-2 lg:mt-4">
            <LoginMarketing />
          </div>
        </div>
        <div className="relative mt-2 hidden items-center gap-2 text-[10px] text-slate-600 sm:flex lg:mt-auto lg:pt-6">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-500/70" />
          Built to keep your property operations organised and transparent.
        </div>
      </section>

      <section className="relative flex min-w-0 items-center justify-center px-4 pb-10 pt-5 sm:px-8 lg:min-h-screen lg:border-l lg:border-white/[0.06] lg:bg-slate-900/35 lg:px-8 lg:py-12 xl:px-14">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/[0.025] via-transparent to-sky-500/[0.04]" />
        <motion.form
          onSubmit={submit}
          initial={{ opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ type: "spring", stiffness: 100, damping: 18, delay: 0.1 }}
          className="relative w-full max-w-md space-y-5 overflow-hidden rounded-3xl border border-white/[0.09] bg-slate-900/80 p-6 shadow-2xl shadow-black/40 backdrop-blur-2xl sm:p-8"
        >
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/[0.045] via-transparent to-emerald-500/[0.035]" />
          <div className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-emerald-400/60 to-transparent" />

          <div className="relative">
            <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl border border-emerald-400/20 bg-emerald-400/10">
              <Building2 className="h-6 w-6 text-emerald-300" />
            </div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-emerald-300">Owner workspace</p>
            <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Welcome back</h2>
            <p className="mt-2 text-sm text-slate-400">Sign in to continue managing your properties.</p>
          </div>

          <div className="relative space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="login-email" className="text-xs font-medium text-slate-300">Email address</label>
              <input
                id="login-email"
                className="input"
                type="email"
                autoComplete="username"
                placeholder="owner@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="login-password" className="text-xs font-medium text-slate-300">Password</label>
              <input
                id="login-password"
                className="input"
                type="password"
                autoComplete="current-password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </div>

          <AnimatePresence>
            {err && (
              <motion.p
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="relative flex items-center gap-1.5 rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-300"
              >
                <Key className="h-3.5 w-3.5 shrink-0" /> {err}
              </motion.p>
            )}
          </AnimatePresence>

          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            disabled={loading}
            className="relative flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-400 to-emerald-500 py-3 text-sm font-bold text-slate-950 shadow-lg shadow-emerald-500/20 transition-all duration-200 hover:from-emerald-300 hover:to-emerald-400 disabled:opacity-60"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Signing in...
              </>
            ) : (
              "Sign in to Rental OS"
            )}
          </motion.button>

          <div className="relative border-t border-white/[0.06] pt-4">
            <div className="flex items-start gap-2 rounded-xl bg-slate-800/55 p-3">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
              <div className="text-[11px] leading-5 text-slate-400">
                <span className="font-semibold text-slate-300">Secure owner access.</span> Caretakers and tenants sign in via WhatsApp.
              </div>
            </div>
            <p className="mt-3 text-center text-[10px] text-slate-600">Demo account: owner@rental.dev / rental1234</p>
          </div>
        </motion.form>
      </section>
    </div>
  );
}
