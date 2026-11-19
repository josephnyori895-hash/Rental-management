import { useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, ArrowUpRight, Building2, Check, CheckCircle2, Eye, EyeOff, Home, KeyRound, Layers3, LoaderCircle, LockKeyhole, Mail, Phone, ShieldCheck, Sparkles, UserRound, Wallet } from "lucide-react";
import { loginOwner, registerBusiness, setToken } from "../lib/api";

type Mode = "login" | "signup";
const features = [
  { icon: Building2, title: "Every property, one view", body: "See buildings, units and occupancy without losing the detail." },
  { icon: Wallet, title: "Know your numbers", body: "Rent, collections and operating costs connected to the same records." },
  { icon: ShieldCheck, title: "Your business stays yours", body: "A private workspace built around your properties and your team." }
];

export default function Welcome({ onLogin }: { onLogin: (token: string) => void }) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [confirm, setConfirm] = useState("");
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  const changeMode = (next: Mode) => { setMode(next); setError(""); setNotice(""); };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setError(""); setNotice("");
    if (mode === "signup" && password.length < 8) { setError("Use a password with at least 8 characters."); return; }
    if (mode === "signup" && password !== confirm) { setError("Your passwords do not match."); return; }
    setLoading(true);
    try {
      if (mode === "signup") {
        await registerBusiness({ business_name: businessName.trim(), owner_full_name: fullName.trim(), email: email.trim(), password, phone: phone.trim() || undefined });
        setMode("login"); setPassword(""); setConfirm("");
        setNotice("Your business workspace has been created. Sign in with your new account to continue.");
      } else {
        const result = await loginOwner(email.trim(), password);
        setToken(result.access_token); onLogin(result.access_token);
      }
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong. Please try again."); }
    finally { setLoading(false); }
  };

  return <div className="rental-public min-h-screen bg-[#f6f7f3] text-[#17251f]">
    <header className="mx-auto flex max-w-[1440px] items-center justify-between px-5 py-5 sm:px-8 lg:px-12">
      <a href="#home" className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#1b7652] text-white shadow-lg shadow-emerald-900/15"><Building2 size={21}/></span>
        <span><strong className="block text-[15px] tracking-[-.04em]">Rental<span className="text-[#26825d]">OS</span></strong><small className="block text-[9px] font-semibold uppercase tracking-[.19em] text-[#87948b]">Property operations</small></span>
      </a>
      <nav className="hidden items-center gap-8 md:flex"><a href="#platform" className="text-[13px] font-medium text-[#627168] hover:text-[#1b7652]">Platform</a><a href="#benefits" className="text-[13px] font-medium text-[#627168] hover:text-[#1b7652]">What you can manage</a></nav>
      <div className="flex items-center gap-2"><button onClick={()=>changeMode("login")} className="rounded-xl px-4 py-2.5 text-[13px] font-semibold text-[#34463b] hover:bg-white">Log in</button><button onClick={()=>changeMode("signup")} className="hidden items-center gap-2 rounded-xl bg-[#1b7652] px-4 py-2.5 text-[13px] font-semibold text-white shadow-lg shadow-emerald-900/10 transition hover:-translate-y-0.5 hover:bg-[#155f42] sm:flex">Create account <ArrowUpRight size={15}/></button></div>
    </header>

    <main id="home" className="mx-auto grid max-w-[1440px] grid-cols-1 items-start gap-10 px-5 pb-16 pt-7 sm:px-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(410px,.9fr)] lg:gap-16 lg:px-12 lg:pb-24 lg:pt-12">
      <section className="min-w-0">
        <motion.div initial={{opacity:0,y:18}} animate={{opacity:1,y:0}} transition={{duration:.65}}>
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[#dce9df] bg-white/80 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[.15em] text-[#377b5c] shadow-sm"><Sparkles size={13}/> A clearer way to run rentals</div>
          <h1 className="max-w-[720px] text-[clamp(2.8rem,5.6vw,5.6rem)] font-semibold leading-[.99] tracking-[-.075em] text-[#17251f]">Your properties.<br/><span className="text-[#23815a]">Under control.</span></h1>
          <p className="mt-6 max-w-[540px] text-[15px] leading-7 text-[#69786f] sm:text-[17px] sm:leading-8">One thoughtful workspace for the buildings you own, the people who live in them, and the business behind every rent payment.</p>
          <div className="mt-7 flex flex-wrap items-center gap-3"><button onClick={()=>changeMode("signup")} className="group inline-flex items-center gap-3 rounded-xl bg-[#1b7652] px-5 py-3.5 text-sm font-semibold text-white shadow-xl shadow-emerald-900/15 transition hover:-translate-y-0.5 hover:bg-[#155f42]">Get started <ArrowRight size={16} className="transition group-hover:translate-x-1"/></button><button onClick={()=>changeMode("login")} className="rounded-xl border border-[#dce5dd] bg-white/70 px-5 py-3.5 text-sm font-semibold text-[#35483d] hover:bg-white">I already have an account</button></div>
        </motion.div>

        <motion.div initial={{opacity:0,y:28}} animate={{opacity:1,y:0}} transition={{duration:.75,delay:.16}} className="relative mt-12 overflow-hidden rounded-[28px] border border-white bg-[#dce9df] p-3 shadow-[0_28px_80px_-38px_rgba(31,74,49,.35)] sm:mt-14">
          <div className="relative min-h-[270px] overflow-hidden rounded-[21px] bg-[#193c2d] sm:min-h-[350px]">
            <div className="absolute inset-0 bg-[linear-gradient(105deg,rgba(13,43,30,.9)_0%,rgba(13,43,30,.56)_55%,rgba(13,43,30,.12)_100%),url('https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=1400&q=85')] bg-cover bg-center"/>
            <div className="absolute inset-0 opacity-25" style={{backgroundImage:"linear-gradient(rgba(255,255,255,.12) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.12) 1px,transparent 1px)",backgroundSize:"42px 42px"}}/>
            <div className="absolute left-6 top-7 max-w-[300px] text-white sm:left-9 sm:top-9"><div className="text-[9px] font-bold uppercase tracking-[.22em] text-emerald-200/80">One connected portfolio</div><div className="mt-3 text-2xl font-semibold leading-tight tracking-[-.05em] sm:text-3xl">From the front gate<br/>to the final ledger.</div><div className="mt-4 flex items-center gap-2 text-[11px] text-white/70"><span className="h-1.5 w-1.5 rounded-full bg-emerald-300"/> Properties, people and payments in sync</div></div>
            <motion.div animate={{y:[0,-7,0]}} transition={{duration:5,repeat:Infinity,ease:"easeInOut"}} className="absolute bottom-5 right-5 hidden w-[205px] rounded-2xl border border-white/35 bg-white/90 p-4 shadow-2xl backdrop-blur-xl sm:block"><div className="flex items-center justify-between text-[9px] font-semibold uppercase tracking-[.13em] text-[#718078]"><span>Property overview</span><span className="h-2 w-2 rounded-full bg-[#269567]"/></div><div className="mt-3 text-[24px] font-semibold tracking-[-.06em] text-[#1c3025]">Your portfolio</div><div className="mt-3 flex gap-1.5">{[0,1,2,3,4,5,6,7].map(i=><span key={i} className={"h-7 flex-1 rounded-md "+(i===6?"bg-[#e7b66e]":"bg-[#d8e9dd")}/>)}</div><div className="mt-2 text-[9px] text-[#819087]">A live view of the records you manage</div></motion.div>
          </div>
        </motion.div>

        <div id="platform" className="mt-9 grid gap-5 sm:grid-cols-3">{features.map((item,index)=><motion.div key={item.title} initial={{opacity:0,y:16}} animate={{opacity:1,y:0}} transition={{delay:.25+index*.09,duration:.5}} className="group"><div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-[#e5f0e8] text-[#247b55] transition duration-300 group-hover:-translate-y-1 group-hover:bg-[#d7eadc]"><item.icon size={17}/></div><h3 className="text-[13px] font-semibold tracking-[-.02em] text-[#26382e]">{item.title}</h3><p className="mt-1.5 text-[11px] leading-5 text-[#78867e]">{item.body}</p></motion.div>)}</div>
      </section>

      <section className="relative lg:sticky lg:top-8" aria-label={mode==="login"?"Log in":"Create account"}>
        <motion.div layout className="relative overflow-hidden rounded-[28px] border border-white bg-white/90 p-6 shadow-[0_28px_90px_-42px_rgba(30,64,44,.28)] backdrop-blur-xl sm:p-8 lg:p-9">
          <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-[#e8f4eb] blur-3xl"/>
          <div className="relative">
            <div className="mb-7 flex items-center justify-between gap-3"><div><div className="text-[10px] font-bold uppercase tracking-[.18em] text-[#6f8a79]">{mode==="login"?"Welcome back":"Start your workspace"}</div><h2 className="mt-2 text-[27px] font-semibold tracking-[-.06em] text-[#1c2c22]">{mode==="login"?"Sign in to Rental OS":"Create your account"}</h2><p className="mt-1.5 text-[12px] leading-5 text-[#7b8980]">{mode==="login"?"Pick up where you left off.":"Set up your rental business in a few steps."}</p></div><div className="hidden h-12 w-12 items-center justify-center rounded-2xl bg-[#edf5ef] text-[#247b55] sm:flex"><KeyRound size={21}/></div></div>
            <div className="mb-6 grid grid-cols-2 rounded-xl bg-[#f2f5f1] p-1"><button onClick={()=>changeMode("login")} className={"rounded-lg py-2.5 text-[12px] font-semibold transition "+(mode==="login"?"bg-white text-[#205c40] shadow-sm":"text-[#829087] hover:text-[#405348]")}>Log in</button><button onClick={()=>changeMode("signup")} className={"rounded-lg py-2.5 text-[12px] font-semibold transition "+(mode==="signup"?"bg-white text-[#205c40] shadow-sm":"text-[#829087] hover:text-[#405348]")}>Sign up</button></div>
            <AnimatePresence mode="wait">
              <motion.form key={mode} onSubmit={submit} initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-7}} transition={{duration:.2}} className="space-y-4">
                {mode==="signup" && <><div><label htmlFor="businessName" className="rental-auth-label">Business or portfolio name</label><div className="relative"><Home size={15} className="rental-auth-icon"/><input id="businessName" required minLength={2} maxLength={160} autoComplete="organization" value={businessName} onChange={e=>setBusinessName(e.target.value)} placeholder="e.g. Greenview Properties" className="rental-auth-input"/></div></div><div><label htmlFor="fullName" className="rental-auth-label">Your full name</label><div className="relative"><UserRound size={15} className="rental-auth-icon"/><input id="fullName" required minLength={2} maxLength={160} autoComplete="name" value={fullName} onChange={e=>setFullName(e.target.value)} placeholder="Full name" className="rental-auth-input"/></div></div></>}
                <div><label htmlFor="email" className="rental-auth-label">Email address</label><div className="relative"><Mail size={15} className="rental-auth-icon"/><input id="email" required type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@yourbusiness.com" className="rental-auth-input"/></div></div>
                {mode==="signup" && <div><label htmlFor="phone" className="rental-auth-label">Phone number <span className="font-normal text-[#9aa69e]">· optional</span></label><div className="relative"><Phone size={15} className="rental-auth-icon"/><input id="phone" type="tel" autoComplete="tel" value={phone} onChange={e=>setPhone(e.target.value)} placeholder="+254 7..." className="rental-auth-input"/></div></div>}
                <div><label htmlFor="password" className="rental-auth-label">Password</label><div className="relative"><LockKeyhole size={15} className="rental-auth-icon"/><input id="password" required minLength={mode==="signup"?8:1} type={visible?"text":"password"} autoComplete={mode==="login"?"current-password":"new-password"} value={password} onChange={e=>setPassword(e.target.value)} placeholder={mode==="signup"?"At least 8 characters":"Enter your password"} className="rental-auth-input pr-11"/><button type="button" onClick={()=>setVisible(v=>!v)} className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-[#91a097] hover:text-[#315d43]" aria-label={visible?"Hide password":"Show password"}>{visible?<EyeOff size={16}/>:<Eye size={16}/>}</button></div></div>
                {mode==="signup" && <div><label htmlFor="confirmPassword" className="rental-auth-label">Confirm password</label><div className="relative"><CheckCircle2 size={15} className="rental-auth-icon"/><input id="confirmPassword" required type={visible?"text":"password"} autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} placeholder="Enter password again" className="rental-auth-input"/></div></div>}
                {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-3 text-[12px] leading-5 text-rose-700">{error}</div>}
                {notice && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-3 text-[12px] leading-5 text-emerald-800"><span className="mb-1 flex items-center gap-2 font-semibold"><Check size={14}/> Account created</span>{notice}</div>}
                <button type="submit" disabled={loading} className="group mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-[#1b7652] px-4 py-3.5 text-[13px] font-semibold text-white shadow-lg shadow-emerald-900/10 transition hover:-translate-y-0.5 hover:bg-[#155f42] disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-65">{loading?<><LoaderCircle size={16} className="animate-spin"/>{mode==="login"?"Signing you in…":"Creating your workspace…"}</>:<>{mode==="login"?"Sign in to your workspace":"Create my workspace"}<ArrowRight size={16}/></>}</button>
              </motion.form>
            </AnimatePresence>
            <div className="mt-6 flex items-start gap-2.5 border-t border-[#edf0ec] pt-5"><ShieldCheck size={16} className="mt-0.5 shrink-0 text-[#6b9b7c]"/><p className="text-[10px] leading-5 text-[#89958d]">Your account opens a private business workspace. Your properties and records are kept within your business account.</p></div>
          </div>
        </motion.div>
        <div className="mt-5 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-[10px] text-[#8b9890]"><span className="inline-flex items-center gap-1.5"><CheckCircle2 size={12}/> Built for property operators</span><span className="inline-flex items-center gap-1.5"><Layers3 size={12}/> One connected workspace</span></div>
      </section>
    </main>
    <footer id="benefits" className="border-t border-[#e5ebe5] bg-white/60"><div className="mx-auto flex max-w-[1440px] flex-col gap-4 px-5 py-7 sm:px-8 md:flex-row md:items-center md:justify-between lg:px-12"><div><div className="text-[12px] font-semibold text-[#43564a]">The essentials, connected.</div><div className="mt-1 text-[10px] text-[#8a968e]">A single place for your property operations.</div></div><div className="flex flex-wrap gap-x-5 gap-y-2">{["Property and unit management","Rent collection and payment history","Tenant, lease and maintenance workflows"].map(item=><span key={item} className="flex items-center gap-1.5 text-[10px] text-[#738178]"><Check size={12} className="text-[#33845c]"/>{item}</span>)}</div><span className="text-[10px] text-[#a0aaa3]">© {new Date().getFullYear()} Rental OS</span></div></footer>
  </div>;
}
