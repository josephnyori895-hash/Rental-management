import { useState, type FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { loginOwner, setToken } from "../lib/api";
import { Building2, Key, Loader2 } from "lucide-react";

export default function Login({ onLogin }: { onLogin: (t: string) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const registered = new URLSearchParams(window.location.search).get("registered") === "1";

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const result = await loginOwner(email.trim(), password);
      setToken(result.access_token);
      onLogin(result.access_token);
    } catch (cause) {
      setErr(cause instanceof Error ? cause.message : "Sign in failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-8">
      <motion.form
        onSubmit={submit}
        aria-describedby={err ? "login-error" : undefined}
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ type: "spring", stiffness: 100, damping: 16 }}
        className="relative w-full max-w-sm space-y-5 overflow-hidden rounded-2xl border border-white/[0.08] bg-slate-900/80 p-6 shadow-2xl shadow-black/50 backdrop-blur-2xl sm:p-7"
      >
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/[0.04] to-transparent" />
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-emerald-400/50 to-transparent" />
        <div className="relative mb-2 text-center">
          <motion.div initial={{ scale: 0.85 }} animate={{ scale: 1 }} className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-400 to-sky-400 shadow-lg shadow-emerald-500/20">
            <Building2 className="h-7 w-7 text-slate-950" />
          </motion.div>
          <h1 className="text-xl font-bold tracking-tight">Welcome back</h1>
          <p className="mt-1 text-xs text-slate-400">Rental OS · Owner workspace</p>
        </div>

        {registered && <p role="status" className="relative rounded-lg border border-emerald-400/20 bg-emerald-400/[0.08] px-3 py-2.5 text-sm text-emerald-200">Your workspace was created. Sign in with your new account.</p>}

        <div className="relative space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="login-email" className="block text-sm font-medium text-slate-300">Email address</label>
            <input id="login-email" name="email" className="input min-h-11" type="email" autoComplete="username" inputMode="email" placeholder="you@example.com" value={email} onChange={event => setEmail(event.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="login-password" className="block text-sm font-medium text-slate-300">Password</label>
            <input id="login-password" name="password" className="input min-h-11" type="password" autoComplete="current-password" placeholder="Enter your password" value={password} onChange={event => setPassword(event.target.value)} required />
          </div>
        </div>

        <AnimatePresence>
          {err && <motion.p id="login-error" role="alert" aria-live="polite" initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="relative flex items-start gap-2 rounded-lg border border-rose-400/20 bg-rose-400/[0.06] px-3 py-2.5 text-sm text-rose-300"><Key className="mt-0.5 h-4 w-4 shrink-0" />{err}</motion.p>}
        </AnimatePresence>

        <button type="submit" disabled={loading} className="relative flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-emerald-500 to-emerald-600 px-4 py-3 font-semibold text-slate-950 shadow-lg shadow-emerald-500/15 transition hover:from-emerald-400 hover:to-emerald-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300 disabled:cursor-not-allowed disabled:opacity-60">
          {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Signing in…</> : "Sign in"}
        </button>
        <div className="relative space-y-3 text-center">
          <p className="text-sm text-slate-500">New to Rental OS? <a href="/register" className="font-medium text-emerald-300 underline-offset-4 hover:text-emerald-200 hover:underline">Create an owner account</a></p>
          <a href="/" className="inline-block text-xs text-slate-600 underline-offset-4 hover:text-slate-300 hover:underline">Back to home</a>
          <p className="text-xs leading-5 text-slate-600">Caretaker and staff access is managed separately by the workspace owner.</p>
        </div>
      </motion.form>
    </div>
  );
}
