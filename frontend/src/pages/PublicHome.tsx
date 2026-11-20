import { useState } from "react";
import {
  ArrowRight, ArrowUpRight, Building2, ChevronDown, CircleDollarSign,
  ClipboardCheck, Layers3, Menu,
  ShieldCheck, Sparkles, Users, Wrench, X,
} from "lucide-react";

const floors = [
  { name: "Ground", units: [{id:"G01",state:"occupied"},{id:"G02",state:"occupied"},{id:"G03",state:"available"},{id:"G04",state:"occupied"}] },
  { name: "First", units: [{id:"101",state:"occupied"},{id:"102",state:"due"},{id:"103",state:"occupied"},{id:"104",state:"occupied"}] },
  { name: "Second", units: [{id:"201",state:"occupied"},{id:"202",state:"available"},{id:"203",state:"occupied"},{id:"204",state:"occupied"}] },
];
const sampleRows = [
  {name:"Rent collection",detail:"Payments and outstanding balances",icon:CircleDollarSign},
  {name:"Tenant records",detail:"Leases, contacts and occupancy",icon:Users},
  {name:"Maintenance",detail:"Requests, assignments and progress",icon:Wrench},
];

function ProductPreview() {
  const [floor,setFloor] = useState(1);
  const [unit,setUnit] = useState("102");
  const activeFloor = floors[floor];
  const selected = activeFloor.units.find(x=>x.id===unit) || activeFloor.units[0];
  const statusLabel = selected.state==="occupied"?"Occupied":selected.state==="available"?"Available":"Payment due";
  const statusTone = selected.state==="occupied"?"text-emerald-300 bg-emerald-300/10":selected.state==="available"?"text-sky-300 bg-sky-300/10":"text-amber-200 bg-amber-300/10";
  return (
    <div className="relative mx-auto w-full max-w-[640px]">
      <div className="absolute -inset-8 rounded-[3rem] bg-emerald-400/[0.08] blur-3xl" />
      <div className="relative overflow-hidden rounded-[1.6rem] border border-white/10 bg-[#0b1725] shadow-[0_35px_100px_rgba(0,0,0,.55)]">
        <div className="flex items-center justify-between border-b border-white/[0.07] px-5 py-4">
          <div className="flex items-center gap-3"><div className="grid h-9 w-9 place-items-center rounded-xl bg-emerald-300 text-[#07111c]"><Building2 className="h-4 w-4"/></div><div><p className="text-sm font-semibold text-white">Portfolio overview</p><p className="text-[11px] text-slate-500">Illustrative workspace · sample data</p></div></div>
          <span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] text-slate-400">LIVE PRODUCT PREVIEW</span>
        </div>
        <div className="grid grid-cols-3 gap-2 border-b border-white/[0.06] p-4">
          {[["Properties","Portfolio"],["Rent & arrears","Receivables"],["Work orders","Maintenance"]].map(([a,b])=><div key={a} className="rounded-xl bg-white/[0.035] p-3"><p className="text-[10px] text-slate-500">{a}</p><p className="mt-1 text-xs font-semibold text-slate-200">{b}</p></div>)}
        </div>
        <div className="grid gap-4 p-4 sm:grid-cols-[1.2fr_.8fr] sm:p-5">
          <div className="rounded-xl border border-white/[0.07] bg-[#08121e] p-3">
            <div className="flex items-center justify-between gap-2"><div><p className="text-xs font-semibold text-white">Building plan</p><p className="mt-0.5 text-[10px] text-slate-500">Explore floors and units</p></div><Layers3 className="h-4 w-4 text-emerald-300"/></div>
            <div className="mt-4 flex gap-1.5 overflow-x-auto pb-1">{floors.map((f,i)=><button key={f.name} onClick={()=>{setFloor(i);setUnit(f.units[0].id)}} className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-[10px] font-medium transition ${floor===i?"bg-emerald-300 text-[#07111c]":"bg-white/[0.05] text-slate-400 hover:bg-white/10"}`}>{f.name}</button>)}</div>
            <div className="mt-3 grid grid-cols-2 gap-2">{activeFloor.units.map(u=><button key={u.id} onClick={()=>setUnit(u.id)} className={`rounded-xl border p-3 text-left transition ${unit===u.id?"border-emerald-300/60 bg-emerald-300/[0.09]":"border-white/[0.07] bg-white/[0.025] hover:border-white/20"}`}><div className="flex items-center justify-between"><span className="text-xs font-semibold text-white">{u.id}</span><span className={`h-2 w-2 rounded-full ${u.state==="occupied"?"bg-emerald-300":u.state==="available"?"bg-sky-300":"bg-amber-300"}`}/></div><p className="mt-2 text-[10px] capitalize text-slate-500">{u.state==="due"?"Payment due":u.state}</p></button>)}</div>
            <div className="mt-3 flex flex-wrap gap-3 text-[9px] text-slate-500"><span><i className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-emerald-300"/>Occupied</span><span><i className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-sky-300"/>Available</span><span><i className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-amber-300"/>Payment due</span></div>
          </div>
          <div className="space-y-3">
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-4"><p className="text-[10px] uppercase tracking-wider text-slate-500">Selected unit</p><div className="mt-2 flex items-center justify-between"><span className="text-2xl font-semibold text-white">{selected.id}</span><span className={`rounded-full px-2 py-1 text-[9px] font-medium ${statusTone}`}>{statusLabel}</span></div><p className="mt-2 text-[10px] leading-5 text-slate-500">Select a different unit to explore how property records can be organised.</p></div>
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-4"><div className="flex items-center gap-2"><CircleDollarSign className="h-4 w-4 text-emerald-300"/><p className="text-xs font-semibold text-white">Financial control</p></div><p className="mt-2 text-[10px] leading-5 text-slate-500">Review rent raised, payments received, balances and expenses in one place.</p></div>
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-4"><div className="flex items-center gap-2"><ClipboardCheck className="h-4 w-4 text-sky-300"/><p className="text-xs font-semibold text-white">Operations</p></div><p className="mt-2 text-[10px] leading-5 text-slate-500">Follow maintenance work and keep tenant activity visible.</p></div>
          </div>
        </div>
        <div className="flex items-center justify-between border-t border-white/[0.07] px-5 py-3"><span className="text-[10px] text-slate-500">Demonstration only · no customer records shown</span><span className="inline-flex items-center gap-1 text-[10px] text-emerald-300">Explore the workspace <ArrowUpRight className="h-3 w-3"/></span></div>
      </div>
    </div>
  );
}

export default function PublicHome() {
  const [menuOpen,setMenuOpen] = useState(false);
  return (
    <main className="min-h-screen overflow-hidden bg-[#07111c] text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_70%_12%,rgba(16,185,129,.12),transparent_35%),radial-gradient(ellipse_at_5%_80%,rgba(56,189,248,.07),transparent_32%)]"/>
      <header className="relative z-30 mx-auto flex max-w-[1440px] items-center justify-between px-5 py-5 sm:px-8 lg:px-12">
        <a href="/" className="flex items-center gap-3" aria-label="Rental OS home"><span className="grid h-10 w-10 place-items-center rounded-xl border border-emerald-200/20 bg-emerald-300 text-[#07111c] shadow-lg shadow-emerald-300/10"><Building2 className="h-5 w-5"/></span><span><strong className="block text-[15px] tracking-tight text-white">RENTAL OS</strong><span className="block text-[9px] font-semibold uppercase tracking-[.22em] text-slate-500">Property operations platform</span></span></a>
        <nav className="hidden items-center gap-8 md:flex"><a href="#platform" className="text-sm text-slate-400 transition hover:text-white">Platform</a><a href="#operations" className="text-sm text-slate-400 transition hover:text-white">Capabilities</a><a href="#ownership" className="text-sm text-slate-400 transition hover:text-white">Your money</a></nav>
        <div className="hidden items-center gap-3 md:flex"><a href="/login" className="rounded-xl px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:text-white">Sign in</a><a href="/register" className="inline-flex items-center gap-2 rounded-xl bg-emerald-300 px-4 py-2.5 text-sm font-semibold text-[#07111c] transition hover:bg-emerald-200">Create workspace <ArrowRight className="h-4 w-4"/></a></div>
        <button onClick={()=>setMenuOpen(v=>!v)} className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 text-slate-200 md:hidden" aria-label={menuOpen?"Close menu":"Open menu"}>{menuOpen?<X className="h-5 w-5"/>:<Menu className="h-5 w-5"/>}</button>
        {menuOpen&&<div className="absolute left-4 right-4 top-[76px] rounded-2xl border border-white/10 bg-[#101d2b] p-4 shadow-2xl md:hidden"><div className="flex flex-col gap-1"><a onClick={()=>setMenuOpen(false)} href="#platform" className="rounded-lg px-3 py-3 text-sm text-slate-200">Platform</a><a onClick={()=>setMenuOpen(false)} href="#operations" className="rounded-lg px-3 py-3 text-sm text-slate-200">Capabilities</a><a onClick={()=>setMenuOpen(false)} href="#ownership" className="rounded-lg px-3 py-3 text-sm text-slate-200">Your money</a><a href="/login" className="rounded-lg px-3 py-3 text-sm text-slate-200">Sign in</a><a href="/register" className="mt-1 rounded-lg bg-emerald-300 px-3 py-3 text-center text-sm font-semibold text-[#07111c]">Create workspace</a></div></div>}
      </header>

      <section id="platform" className="relative mx-auto grid max-w-[1440px] items-center gap-14 px-5 pb-24 pt-12 sm:px-8 md:pt-20 lg:grid-cols-[.9fr_1.1fr] lg:px-12 lg:pb-32">
        <div className="relative z-10">
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-300/[0.07] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[.18em] text-emerald-200"><Sparkles className="h-3.5 w-3.5"/> Clarity for every property</div>
          <h1 className="max-w-2xl text-[clamp(2.8rem,5.5vw,5.4rem)] font-semibold leading-[1.02] tracking-[-.055em] text-white">Run your properties with <span className="text-emerald-300">confidence.</span></h1>
          <p className="mt-7 max-w-xl text-base leading-8 text-slate-400 sm:text-lg">One connected workspace for property records, tenants, rent, maintenance and financial oversight. Built to make the work behind every property clearer.</p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row"><a href="/register" className="inline-flex min-h-13 items-center justify-center gap-2 rounded-xl bg-emerald-300 px-6 py-3.5 text-sm font-semibold text-[#07111c] shadow-[0_12px_35px_rgba(16,185,129,.16)] transition hover:-translate-y-0.5 hover:bg-emerald-200">Build your workspace <ArrowRight className="h-4 w-4"/></a><a href="#operations" className="inline-flex min-h-13 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.025] px-6 py-3.5 text-sm font-medium text-slate-200 transition hover:bg-white/[0.06]">Explore capabilities <ChevronDown className="h-4 w-4"/></a></div>
          <div className="mt-9 grid max-w-lg grid-cols-2 gap-4 border-t border-white/[0.08] pt-6"><div className="flex items-start gap-2.5"><ShieldCheck className="mt-0.5 h-4 w-4 text-emerald-300"/><div><p className="text-xs font-semibold text-slate-200">Your properties</p><p className="mt-1 text-[11px] text-slate-500">Your records and decisions</p></div></div><div className="flex items-start gap-2.5"><CircleDollarSign className="mt-0.5 h-4 w-4 text-emerald-300"/><div><p className="text-xs font-semibold text-slate-200">Your money</p><p className="mt-1 text-[11px] text-slate-500">Rent settles to your provider</p></div></div></div>
        </div>
        <div className="relative z-10 lg:pl-3"><ProductPreview/></div>
        <div className="pointer-events-none absolute -bottom-16 left-[42%] h-72 w-72 rounded-full border border-emerald-300/[0.06]"/><div className="pointer-events-none absolute -bottom-8 left-[45%] h-56 w-56 rounded-full border border-emerald-300/[0.06]"/>
      </section>

      <section id="operations" className="border-y border-white/[0.07] bg-[#0b1724]/80">
        <div className="mx-auto max-w-[1440px] px-5 py-20 sm:px-8 lg:px-12 lg:py-24">
          <div className="max-w-2xl"><p className="text-[10px] font-semibold uppercase tracking-[.22em] text-emerald-300">One connected operating system</p><h2 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">The detail behind the bigger picture.</h2><p className="mt-4 text-sm leading-7 text-slate-400 sm:text-base">Move from portfolio-wide oversight to the detail of a single unit, tenant, payment or maintenance request—without losing the context around it.</p></div>
          <div className="mt-12 grid gap-4 md:grid-cols-3">{sampleRows.map(({name,detail,icon:Icon},i)=><article key={name} className="group rounded-2xl border border-white/[0.08] bg-[#101e2d] p-6 transition duration-300 hover:-translate-y-1 hover:border-emerald-300/25"><div className="flex items-center justify-between"><span className="grid h-11 w-11 place-items-center rounded-xl bg-emerald-300/[0.09] text-emerald-300"><Icon className="h-5 w-5"/></span><span className="text-[10px] font-semibold tracking-[.18em] text-slate-600">0{i+1}</span></div><h3 className="mt-7 text-lg font-semibold text-white">{name}</h3><p className="mt-2 text-sm leading-6 text-slate-400">{detail}</p><div className="mt-6 h-px w-full bg-white/[0.07] transition group-hover:bg-emerald-300/30"/></article>)}</div>
        </div>
      </section>

      <section id="ownership" className="mx-auto grid max-w-[1440px] gap-10 px-5 py-20 sm:px-8 md:grid-cols-2 md:items-center lg:px-12 lg:py-24">
        <div><p className="text-[10px] font-semibold uppercase tracking-[.22em] text-emerald-300">A clear financial boundary</p><h2 className="mt-4 max-w-xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">Your properties. Your tenants. Your money. Our technology.</h2><p className="mt-5 max-w-xl text-sm leading-7 text-slate-400">Your rental income is paid to your own configured payment-provider account. Rental OS provides the tools to manage records, operations and financial visibility—without holding your rent.</p></div>
        <div className="rounded-2xl border border-white/[0.08] bg-[#0d1a28] p-6 sm:p-8"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-300/10 text-emerald-300"><ShieldCheck className="h-5 w-5"/></span><div><p className="text-sm font-semibold text-white">Direct landlord settlement</p><p className="text-xs text-slate-500">Your provider account remains yours</p></div></div><div className="my-6 flex items-center gap-3"><div className="flex-1 rounded-xl border border-white/10 bg-white/[0.025] p-4 text-center"><Building2 className="mx-auto h-5 w-5 text-slate-300"/><p className="mt-2 text-xs font-medium text-white">Your tenant</p><p className="mt-1 text-[10px] text-slate-500">Makes rent payment</p></div><ArrowRight className="h-4 w-4 shrink-0 text-emerald-300"/><div className="flex-1 rounded-xl border border-emerald-300/20 bg-emerald-300/[0.06] p-4 text-center"><CircleDollarSign className="mx-auto h-5 w-5 text-emerald-300"/><p className="mt-2 text-xs font-medium text-white">Your provider</p><p className="mt-1 text-[10px] text-slate-500">Receives your rent</p></div></div><p className="text-center text-[10px] leading-5 text-slate-500">Rental OS subscription billing is separate from tenant rent collection.</p></div>
      </section>

      <section className="border-t border-white/[0.07] bg-[#0b1724]"><div className="mx-auto flex max-w-[1440px] flex-col gap-6 px-5 py-14 sm:px-8 md:flex-row md:items-center md:justify-between lg:px-12"><div><h2 className="text-2xl font-semibold text-white">Bring your property operations into focus.</h2><p className="mt-2 text-sm text-slate-400">Create your workspace and build a clearer view of your portfolio.</p></div><a href="/register" className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-300 px-5 py-3 text-sm font-semibold text-[#07111c] transition hover:bg-emerald-200">Get started <ArrowRight className="h-4 w-4"/></a></div></section>
      <footer className="mx-auto flex max-w-[1440px] flex-col gap-3 px-5 py-7 text-[11px] text-slate-600 sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-12"><span>© {new Date().getFullYear()} Rental OS. Property operations, made clearer.</span><div className="flex gap-5"><a href="/login" className="hover:text-slate-300">Sign in</a><a href="/register" className="hover:text-slate-300">Create workspace</a></div></footer>
    </main>
  );
}
