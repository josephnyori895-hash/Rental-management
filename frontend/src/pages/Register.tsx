import { useState, type FormEvent } from "react";
import { ArrowLeft, Building2, Loader2 } from "lucide-react";
import { registerBusiness } from "../lib/api";
import AnimatedBuildingBackground from "../components/AnimatedBuildingBackground";

export default function Register() {
  const [businessName, setBusinessName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("Use a password with at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await registerBusiness({
        business_name: businessName.trim(),
        owner_full_name: fullName.trim(),
        email: email.trim(),
        password,
        ...(phone.trim() ? { phone: phone.trim() } : {}),
      });
      window.location.assign("/login?registered=1");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Registration could not be completed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 px-4 py-10 text-slate-100">
      <div className="pointer-events-none fixed inset-0 z-0 bg-[radial-gradient(ellipse_at_top,_rgba(16,185,129,0.13),_transparent_45%)]" />
      <AnimatedBuildingBackground />
      <section className="relative z-10 w-full max-w-lg rounded-2xl border border-white/[0.09] bg-slate-900/85 p-6 shadow-2xl shadow-black/40 backdrop-blur-xl sm:p-8">
        <a href="/" className="mb-7 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"><ArrowLeft className="h-4 w-4" /> Back to home</a>
        <div className="mb-6 flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-400 to-sky-400 text-slate-950"><Building2 className="h-5 w-5" /></span><div><h1 className="text-xl font-bold">Create your workspace</h1><p className="mt-1 text-sm text-slate-400">Set up your rental business and owner account.</p></div></div>
        <form onSubmit={submit} className="space-y-4" aria-describedby={error ? "register-error" : undefined}>
          <div className="space-y-1.5"><label htmlFor="business-name" className="block text-sm font-medium text-slate-300">Business or property name</label><input id="business-name" name="business_name" className="input min-h-11" autoComplete="organization" required minLength={2} maxLength={160} value={businessName} onChange={e=>setBusinessName(e.target.value)} placeholder="e.g. Greenview Rentals" /></div>
          <div className="space-y-1.5"><label htmlFor="owner-name" className="block text-sm font-medium text-slate-300">Your full name</label><input id="owner-name" name="owner_full_name" className="input min-h-11" autoComplete="name" required minLength={2} maxLength={160} value={fullName} onChange={e=>setFullName(e.target.value)} placeholder="Full name" /></div>
          <div className="space-y-1.5"><label htmlFor="register-email" className="block text-sm font-medium text-slate-300">Email address</label><input id="register-email" name="email" className="input min-h-11" type="email" autoComplete="email" inputMode="email" required value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com" /></div>
          <div className="space-y-1.5"><label htmlFor="register-phone" className="block text-sm font-medium text-slate-300">Phone number <span className="font-normal text-slate-500">(optional)</span></label><input id="register-phone" name="phone" className="input min-h-11" type="tel" autoComplete="tel" value={phone} onChange={e=>setPhone(e.target.value)} placeholder="+254..." /></div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5"><label htmlFor="register-password" className="block text-sm font-medium text-slate-300">Password</label><input id="register-password" name="password" className="input min-h-11" type="password" autoComplete="new-password" required minLength={8} value={password} onChange={e=>setPassword(e.target.value)} /></div>
            <div className="space-y-1.5"><label htmlFor="confirm-password" className="block text-sm font-medium text-slate-300">Confirm password</label><input id="confirm-password" name="confirm_password" className="input min-h-11" type="password" autoComplete="new-password" required minLength={8} value={confirmPassword} onChange={e=>setConfirmPassword(e.target.value)} /></div>
          </div>
          {error && <p id="register-error" role="alert" aria-live="polite" className="rounded-lg border border-rose-400/20 bg-rose-400/[0.07] px-3 py-2.5 text-sm text-rose-300">{error}</p>}
          <button type="submit" disabled={loading} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-emerald-400 px-4 py-3 font-semibold text-slate-950 transition hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300 disabled:cursor-not-allowed disabled:opacity-60">{loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Creating workspace…</> : "Create workspace"}</button>
          <p className="text-center text-sm text-slate-500">Already registered? <a href="/login" className="font-medium text-emerald-300 hover:text-emerald-200 underline-offset-4 hover:underline">Sign in</a></p>
          <p className="text-xs leading-5 text-slate-600">Creating an account sets up an owner workspace. Staff and caretaker access is managed separately by the business owner.</p>
        </form>
      </section>
    </main>
  );
}
