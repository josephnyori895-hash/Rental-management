import { useState, type FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { loginOwner, setToken } from "../lib/api";
import { ArrowLeft, Building2, Check, Eye, EyeOff, Loader2, ShieldCheck } from "lucide-react";

export default function Login({ onLogin }: { onLogin: (t: string) => void }) {
  const [email,setEmail] = useState("");
  const [password,setPassword] = useState("");
  const [showPassword,setShowPassword] = useState(false);
  const [err,setErr] = useState("");
  const [loading,setLoading] = useState(false);
  const registered = new URLSearchParams(window.location.search).get("registered")==="1";

  const submit = async (event:FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setErr(""); setLoading(true);
    try {
      const result=await loginOwner(email.trim(),password);
      setToken(result.access_token); onLogin(result.access_token);
    } catch(cause) {
      setErr(cause instanceof Error?cause.message:"Sign in failed. Please try again.");
    } finally { setLoading(false); }
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#07111c] text-slate-100">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_15%_20%,rgba(16,185,129,.12),transparent_35%),radial-gradient(ellipse_at_90%_85%,rgba(56,189,248,.07),transparent_32%)]"/>
      <div className="relative mx-auto grid min-h-screen max-w-[1440px] lg:grid-cols-[1.05fr_.95fr]">
        <section className="relative hidden flex-col justify-between overflow-hidden border-r border-white/[0.06] px-12 py-10 lg:flex xl:px-20">
          <a href="/" className="inline-flex w-fit items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-300 text-[#07111c]"><Building2 className="h-5 w-5"/></span><span><strong className="block text-sm tracking-tight text-white">RENTAL OS</strong><span className="text-[9px] uppercase tracking-[.2em] text-slate-500">Property operations platform</span></span></a>
          <div className="relative z-10 max-w-xl py-16">
            <p className="mb-6 text-[10px] font-semibold uppercase tracking-[.22em] text-emerald-300">Welcome to your workspace</p>
            <h1 className="text-5xl font-semibold leading-[1.05] tracking-[-.045em] text-white xl:text-6xl">A clearer view of everything you manage.</h1>
            <p className="mt-7 max-w-lg text-base leading-8 text-slate-400">Bring properties, tenants, rent records, maintenance and financial oversight into one connected operating space.</p>
            <div className="mt-10 grid gap-4 sm:grid-cols-2">
              {["Property and unit visibility","Tenant and lease records","Rent and payment tracking","Maintenance coordination"].map(x=><div key={x} className="flex items-center gap-2.5 text-xs text-slate-300"><span className="grid h-5 w-5 place-items-center rounded-full bg-emerald-300/10 text-emerald-300"><Check className="h-3 w-3"/></span>{x}</div>)}
            </div>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-slate-600"><ShieldCheck className="h-4 w-4 text-emerald-300/70"/> Your workspace. Your records. Your control.</div>
          <div className="pointer-events-none absolute -bottom-32 -right-28 h-[520px] w-[520px] rounded-full border border-emerald-300/[0.07]"/><div className="pointer-events-none absolute -bottom-16 -right-12 h-[360px] w-[360px] rounded-full border border-emerald-300/[0.07]"/>
        </section>

        <section className="relative flex min-h-screen flex-col justify-center px-5 py-10 sm:px-10 lg:px-14 xl:px-20">
          <a href="/" className="mb-12 inline-flex w-fit items-center gap-2 text-xs text-slate-500 transition hover:text-white lg:absolute lg:left-14 lg:top-10 xl:left-20"><ArrowLeft className="h-3.5 w-3.5"/> Back to Rental OS</a>
          <div className="mx-auto w-full max-w-[420px]">
            <div className="mb-9 lg:hidden"><a href="/" className="inline-flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-300 text-[#07111c]"><Building2 className="h-5 w-5"/></span><span><strong className="block text-sm text-white">RENTAL OS</strong><span className="text-[9px] uppercase tracking-[.2em] text-slate-500">Property operations platform</span></span></a></div>
            <p className="text-[10px] font-semibold uppercase tracking-[.22em] text-emerald-300">Owner workspace</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Welcome back.</h2>
            <p className="mt-3 text-sm leading-6 text-slate-400">Sign in to continue managing your property operations.</p>
            {registered&&<p role="status" className="mt-6 rounded-xl border border-emerald-300/20 bg-emerald-300/[0.07] px-4 py-3 text-sm text-emerald-100">Your workspace was created. Sign in with your new account.</p>}
            <form onSubmit={submit} aria-describedby={err?"login-error":undefined} className="mt-8 space-y-5">
              <div className="space-y-2"><label htmlFor="login-email" className="block text-xs font-medium text-slate-300">Email address</label><input id="login-email" name="email" className="input min-h-12 rounded-xl border-white/10 bg-[#0c1a28] px-4 placeholder:text-slate-600 focus:border-emerald-300/60 focus:ring-2 focus:ring-emerald-300/10" type="email" autoComplete="username" inputMode="email" placeholder="you@example.com" value={email} onChange={e=>setEmail(e.target.value)} required/></div>
              <div className="space-y-2"><div className="flex items-center justify-between"><label htmlFor="login-password" className="block text-xs font-medium text-slate-300">Password</label></div><div className="relative"><input id="login-password" name="password" className="input min-h-12 rounded-xl border-white/10 bg-[#0c1a28] px-4 pr-12 placeholder:text-slate-600 focus:border-emerald-300/60 focus:ring-2 focus:ring-emerald-300/10" type={showPassword?"text":"password"} autoComplete="current-password" placeholder="Enter your password" value={password} onChange={e=>setPassword(e.target.value)} required/><button type="button" onClick={()=>setShowPassword(v=>!v)} aria-label={showPassword?"Hide password":"Show password"} className="absolute inset-y-0 right-0 grid w-12 place-items-center text-slate-500 transition hover:text-slate-200">{showPassword?<EyeOff className="h-4 w-4"/>:<Eye className="h-4 w-4"/>}</button></div></div>
              <AnimatePresence>{err&&<motion.p id="login-error" role="alert" aria-live="polite" initial={{opacity:0,y:-5}} animate={{opacity:1,y:0}} exit={{opacity:0}} className="rounded-xl border border-rose-400/20 bg-rose-400/[0.07] px-4 py-3 text-sm text-rose-200">{err}</motion.p>}</AnimatePresence>
              <button type="submit" disabled={loading} className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-emerald-300 px-4 py-3 text-sm font-semibold text-[#07111c] shadow-[0_12px_35px_rgba(16,185,129,.12)] transition hover:bg-emerald-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300 disabled:cursor-not-allowed disabled:opacity-60">{loading?<><Loader2 className="h-4 w-4 animate-spin"/> Signing in…</>:"Sign in to your workspace"}</button>
            </form>
            <div className="mt-8 border-t border-white/[0.07] pt-6 text-center"><p className="text-sm text-slate-500">New to Rental OS? <a href="/register" className="font-semibold text-emerald-300 transition hover:text-emerald-200">Create an owner account</a></p><p className="mt-4 text-[10px] leading-5 text-slate-600">Caretaker and staff access is managed by your workspace owner.</p></div>
          </div>
        </section>
      </div>
    </main>
  );
}
