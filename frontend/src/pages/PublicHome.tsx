import { Building2, CheckCircle2, ClipboardList, CreditCard, ShieldCheck, ArrowRight } from "lucide-react";
import AnimatedBuildingBackground from "../components/AnimatedBuildingBackground";

const features = [
  { icon: Building2, title: "Know every unit", text: "See properties, units, occupancy and tenant details in one organised workspace." },
  { icon: CreditCard, title: "Track rent clearly", text: "Keep rent collection, payment history and outstanding balances easy to follow." },
  { icon: ClipboardList, title: "Stay ahead of maintenance", text: "Keep requests and day-to-day property work visible instead of buried in messages." },
];

export default function PublicHome() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-slate-950 text-slate-100">
      <div className="pointer-events-none fixed inset-0 z-0 bg-[radial-gradient(ellipse_at_top_right,_rgba(16,185,129,0.14),_transparent_42%),radial-gradient(ellipse_at_bottom_left,_rgba(14,165,233,0.10),_transparent_38%)]" />
      <AnimatedBuildingBackground />
      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8">
        <a href="/" className="flex items-center gap-3 rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400" aria-label="Rental OS home">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-400 to-sky-400 text-slate-950 shadow-lg shadow-emerald-500/20"><Building2 className="h-5 w-5" /></span>
          <span><span className="block text-base font-bold tracking-tight">Rental OS</span><span className="block text-xs text-slate-500">Property management</span></span>
        </a>
        <nav aria-label="Main navigation" className="flex items-center gap-3">
          <a href="/login" className="rounded-lg px-3 py-2 text-sm font-medium text-slate-300 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400">Sign in</a>
          <a href="/register" className="rounded-lg bg-emerald-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300">Get started</a>
        </nav>
      </header>

      <section className="relative z-10 mx-auto grid max-w-7xl items-center gap-12 px-5 pb-20 pt-12 sm:px-8 md:grid-cols-[1.05fr_0.95fr] md:pb-28 md:pt-20">
        <div>
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/[0.08] px-3 py-1.5 text-xs font-medium text-emerald-300"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> A clearer way to run rentals</div>
          <h1 className="max-w-2xl text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:text-6xl">Your properties.<br /><span className="bg-gradient-to-r from-emerald-300 to-sky-300 bg-clip-text text-transparent">One clear picture.</span></h1>
          <p className="mt-6 max-w-xl text-base leading-7 text-slate-400 sm:text-lg">Manage units, tenants, rent, maintenance and property records from one practical workspace built for everyday rental operations.</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <a href="/register" className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-400 px-5 py-3.5 font-semibold text-slate-950 shadow-lg shadow-emerald-500/15 transition hover:-translate-y-0.5 hover:bg-emerald-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300">Create your workspace <ArrowRight className="h-4 w-4" /></a>
            <a href="/login" className="inline-flex items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] px-5 py-3.5 font-medium text-slate-200 transition hover:bg-white/[0.07] focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400">I already have an account</a>
          </div>
          <div className="mt-8 flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-500"><span className="inline-flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Organised property records</span><span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-4 w-4 text-emerald-400" /> Owner-focused access</span></div>
        </div>

        <div className="relative mx-auto w-full max-w-xl">
          <div className="absolute -inset-5 rounded-[2rem] bg-gradient-to-br from-emerald-500/15 to-sky-500/10 blur-2xl" />
          <div className="relative rounded-2xl border border-white/10 bg-slate-900/85 p-4 shadow-2xl shadow-black/40 backdrop-blur-xl sm:p-6">
            <div className="flex items-center justify-between border-b border-white/[0.07] pb-4"><div><p className="text-sm font-semibold">Property overview</p><p className="mt-1 text-xs text-slate-500">A sample of your workspace</p></div><span className="rounded-lg border border-white/10 px-2.5 py-1 text-xs text-slate-400">Overview</span></div>
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {[{label:"Properties",value:"Organised",tone:"text-sky-300"},{label:"Occupancy",value:"Visible",tone:"text-emerald-300"},{label:"Rent records",value:"Trackable",tone:"text-violet-300"}].map((item) => <div key={item.label} className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-3"><p className="text-xs text-slate-500">{item.label}</p><p className={`mt-2 text-sm font-semibold ${item.tone}`}>{item.value}</p></div>)}
            </div>
            <div className="mt-4 rounded-xl border border-white/[0.07] bg-slate-950/60 p-4">
              <div className="mb-4 flex items-center justify-between"><span className="text-sm font-medium">Property workspace</span><span className="text-xs text-slate-500">Illustration</span></div>
              <div className="grid grid-cols-[auto_1fr] gap-3">
                <div className="flex w-10 flex-col items-center justify-center rounded-lg bg-emerald-400/10 text-emerald-300"><Building2 className="h-5 w-5" /></div>
                <div className="rounded-lg border border-white/[0.07] p-3"><div className="flex items-center justify-between"><span className="text-sm font-medium">Residential property</span><span className="h-2 w-2 rounded-full bg-emerald-400" /></div><div className="mt-3 grid grid-cols-4 gap-2">{Array.from({length:8},(_,i)=><div key={i} className={`h-7 rounded-md border ${i===5||i===7?"border-amber-300/20 bg-amber-300/10":"border-emerald-300/20 bg-emerald-300/10"}`} />)}</div><div className="mt-3 flex gap-4 text-[11px] text-slate-500"><span><span className="mr-1 inline-block h-2 w-2 rounded-sm bg-emerald-300/70" />Occupied</span><span><span className="mr-1 inline-block h-2 w-2 rounded-sm bg-amber-300/70" />Available</span></div></div>
              </div>
            </div>
            <p className="mt-4 text-center text-[11px] text-slate-600">Illustrative preview — no demo property data is connected.</p>
          </div>
        </div>
      </section>

      <section className="relative z-10 border-t border-white/[0.06] bg-slate-900/35">
        <div className="mx-auto max-w-7xl px-5 py-16 sm:px-8 md:py-20">
          <div className="max-w-xl"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">Made for the work behind the keys</p><h2 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Less scattered admin. More control.</h2><p className="mt-3 leading-6 text-slate-400">Keep everyday property work in one place, with a dashboard designed to make the next step easier to find.</p></div>
          <div className="mt-8 grid gap-4 md:grid-cols-3">{features.map(({icon:Icon,title,text})=><article key={title} className="rounded-2xl border border-white/[0.08] bg-slate-900/70 p-5"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-400/10 text-emerald-300"><Icon className="h-5 w-5" /></span><h3 className="mt-4 font-semibold">{title}</h3><p className="mt-2 text-sm leading-6 text-slate-400">{text}</p></article>)}</div>
        </div>
      </section>
      <footer className="relative z-10 border-t border-white/[0.06] px-5 py-6 text-center text-xs text-slate-600">Rental OS · Property management workspace</footer>
    </main>
  );
}
