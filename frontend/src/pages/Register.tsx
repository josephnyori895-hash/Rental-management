import { useState, type FormEvent } from "react";
import { ArrowLeft, Building2, Check, Eye, EyeOff, Loader2, ShieldCheck } from "lucide-react";

export default function Register() {
  const [businessName,setBusinessName]=useState("");
  const [fullName,setFullName]=useState("");
  const [email,setEmail]=useState("");
  const [phone,setPhone]=useState("");
  const [password,setPassword]=useState("");
  const [confirmPassword,setConfirmPassword]=useState("");
  const [showPassword,setShowPassword]=useState(false);
  const [showConfirm,setShowConfirm]=useState(false);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);

  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    if(password.length<8){setError("Use a password with at least 8 characters.");return;}
    if(password!==confirmPassword){setError("The passwords do not match.");return;}
    setLoading(true);
    try {
      const {registerBusiness}=await import("../lib/api");
      await registerBusiness({business_name:businessName.trim(),owner_full_name:fullName.trim(),email:email.trim(),password,...(phone.trim()?{phone:phone.trim()}:{})});
      window.location.assign("/login?registered=1");
    } catch(cause) {
      setError(cause instanceof Error?cause.message:"Registration could not be completed. Please try again.");
    } finally {setLoading(false);}
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#07111c] text-slate-100">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_15%_20%,rgba(16,185,129,.12),transparent_35%),radial-gradient(ellipse_at_90%_85%,rgba(56,189,248,.07),transparent_32%)]"/>
      <div className="relative mx-auto grid min-h-screen max-w-[1440px] lg:grid-cols-[.9fr_1.1fr]">
        <section className="relative hidden flex-col justify-between overflow-hidden border-r border-white/[0.06] px-12 py-10 lg:flex xl:px-20">
          <a href="/" className="inline-flex w-fit items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-300 text-[#07111c]"><Building2 className="h-5 w-5"/></span><span><strong className="block text-sm text-white">RENTAL OS</strong><span className="text-[9px] uppercase tracking-[.2em] text-slate-500">Property operations platform</span></span></a>
          <div className="relative z-10 max-w-lg py-16"><p className="text-[10px] font-semibold uppercase tracking-[.22em] text-emerald-300">Start with a clear foundation</p><h1 className="mt-6 text-5xl font-semibold leading-[1.05] tracking-[-.045em] text-white xl:text-6xl">Your portfolio deserves a better operating system.</h1><p className="mt-7 text-base leading-8 text-slate-400">Create your workspace and bring property records, tenants, rent and day-to-day operations together.</p><div className="mt-10 space-y-4">{["Set up your property business","Organise buildings, floors and units","Manage tenants and payment records","Keep maintenance and finances visible"].map(x=><div key={x} className="flex items-center gap-3 text-sm text-slate-300"><span className="grid h-6 w-6 place-items-center rounded-full bg-emerald-300/10 text-emerald-300"><Check className="h-3.5 w-3.5"/></span>{x}</div>)}</div></div>
          <div className="flex items-center gap-2 text-[11px] text-slate-600"><ShieldCheck className="h-4 w-4 text-emerald-300/70"/> Your property records remain in your workspace.</div>
          <div className="pointer-events-none absolute -bottom-32 -right-28 h-[520px] w-[520px] rounded-full border border-emerald-300/[0.07]"/>
        </section>
        <section className="flex items-center justify-center px-5 py-10 sm:px-10 lg:px-14 xl:px-20">
          <div className="w-full max-w-[520px]">
            <div className="mb-8 flex items-center justify-between gap-3"><a href="/" className="inline-flex items-center gap-2 text-xs text-slate-500 transition hover:text-white"><ArrowLeft className="h-3.5 w-3.5"/> Back to home</a><p className="text-xs text-slate-500">Already registered? <a href="/login" className="font-semibold text-emerald-300 hover:text-emerald-200">Sign in</a></p></div>
            <div className="mb-8 lg:hidden"><span className="inline-flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-300 text-[#07111c]"><Building2 className="h-5 w-5"/></span><strong className="text-sm text-white">RENTAL OS</strong></span></div>
            <p className="text-[10px] font-semibold uppercase tracking-[.22em] text-emerald-300">Create your workspace</p><h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Let's get you set up.</h2><p className="mt-3 text-sm leading-6 text-slate-400">Start with your business and owner details. You can add properties and units after signing in.</p>
            <form onSubmit={submit} className="mt-8 space-y-4" aria-describedby={error?"register-error":undefined}>
              <div className="space-y-2"><label htmlFor="business-name" className="block text-xs font-medium text-slate-300">Business or property name</label><input id="business-name" name="business_name" className="input min-h-12 rounded-xl border-white/10 bg-[#0c1a28] px-4 placeholder:text-slate-600 focus:border-emerald-300/60 focus:ring-2 focus:ring-emerald-300/10" autoComplete="organization" required minLength={2} maxLength={160} value={businessName} onChange={e=>setBusinessName(e.target.value)} placeholder="e.g. Greenview Rentals"/></div>
              <div className="space-y-2"><label htmlFor="owner-name" className="block text-xs font-medium text-slate-300">Your full name</label><input id="owner-name" name="owner_full_name" className="input min-h-12 rounded-xl border-white/10 bg-[#0c1a28] px-4 placeholder:text-slate-600 focus:border-emerald-300/60 focus:ring-2 focus:ring-emerald-300/10" autoComplete="name" required minLength={2} maxLength={160} value={fullName} onChange={e=>setFullName(e.target.value)} placeholder="Full name"/></div>
              <div className="grid gap-4 sm:grid-cols-2"><div className="space-y-2"><label htmlFor="register-email" className="block text-xs font-medium text-slate-300">Email address</label><input id="register-email" name="email" className="input min-h-12 rounded-xl border-white/10 bg-[#0c1a28] px-4 placeholder:text-slate-600 focus:border-emerald-300/60 focus:ring-2 focus:ring-emerald-300/10" type="email" autoComplete="email" inputMode="email" required value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com"/></div><div className="space-y-2"><label htmlFor="register-phone" className="block text-xs font-medium text-slate-300">Phone <span className="text-slate-600">(optional)</span></label><input id="register-phone" name="phone" className="input min-h-12 rounded-xl border-white/10 bg-[#0c1a28] px-4 placeholder:text-slate-600 focus:border-emerald-300/60 focus:ring-2 focus:ring-emerald-300/10" type="tel" autoComplete="tel" value={phone} onChange={e=>setPhone(e.target.value)} placeholder="+254…"/></div></div>
              <div className="grid gap-4 sm:grid-cols-2"><div className="space-y-2"><label htmlFor="register-password" className="block text-xs font-medium text-slate-300">Password</label><div className="relative"><input id="register-password" name="password" className="input min-h-12 rounded-xl border-white/10 bg-[#0c1a28] px-4 pr-11 placeholder:text-slate-600 focus:border-emerald-300/60 focus:ring-2 focus:ring-emerald-300/10" type={showPassword?"text":"password"} autoComplete="new-password" required minLength={8} value={password} onChange={e=>setPassword(e.target.value)} placeholder="At least 8 characters"/><button type="button" onClick={()=>setShowPassword(v=>!v)} aria-label={showPassword?"Hide password":"Show password"} className="absolute inset-y-0 right-0 grid w-11 place-items-center text-slate-500 hover:text-white">{showPassword?<EyeOff className="h-4 w-4"/>:<Eye className="h-4 w-4"/>}</button></div></div><div className="space-y-2"><label htmlFor="confirm-password" className="block text-xs font-medium text-slate-300">Confirm password</label><div className="relative"><input id="confirm-password" name="confirm_password" className="input min-h-12 rounded-xl border-white/10 bg-[#0c1a28] px-4 pr-11 placeholder:text-slate-600 focus:border-emerald-300/60 focus:ring-2 focus:ring-emerald-300/10" type={showConfirm?"text":"password"} autoComplete="new-password" required minLength={8} value={confirmPassword} onChange={e=>setConfirmPassword(e.target.value)} placeholder="Repeat password"/><button type="button" onClick={()=>setShowConfirm(v=>!v)} aria-label={showConfirm?"Hide confirmation":"Show confirmation"} className="absolute inset-y-0 right-0 grid w-11 place-items-center text-slate-500 hover:text-white">{showConfirm?<EyeOff className="h-4 w-4"/>:<Eye className="h-4 w-4"/>}</button></div></div></div>
              {error&&<p id="register-error" role="alert" aria-live="polite" className="rounded-xl border border-rose-400/20 bg-rose-400/[0.07] px-4 py-3 text-sm text-rose-200">{error}</p>}
              <button type="submit" disabled={loading} className="mt-2 flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-emerald-300 px-4 py-3 text-sm font-semibold text-[#07111c] shadow-[0_12px_35px_rgba(16,185,129,.12)] transition hover:bg-emerald-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300 disabled:cursor-not-allowed disabled:opacity-60">{loading?<><Loader2 className="h-4 w-4 animate-spin"/> Creating workspace…</>:"Create owner account"}</button>
            </form>
            <p className="mt-6 text-center text-[10px] leading-5 text-slate-600">Your Rental OS subscription is separate from rent payments made by your tenants.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
