import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Wrench, Plus, Search, Filter, AlertTriangle, CheckCircle2, Clock, User,
} from "lucide-react";
import { getTickets, getMaintenanceSummary, createTicket, updateTicket } from "../lib/api";
import { Card, PageHeader, Badge, EmptyState, money } from "../components/ui";

type Status = "open" | "assigned" | "in_progress" | "resolved" | "closed";

const STATUS_COLOR: Record<string, string> = {
  open: "rose", assigned: "amber", in_progress: "sky", resolved: "emerald", closed: "slate",
};
const PRIORITY_COLOR: Record<string, string> = {
  low: "slate", medium: "sky", high: "amber", urgent: "rose",
};

export default function Maintenance() {
  const [tickets, setTickets] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", category: "plumbing", priority: "medium", unit_number: "", property_id: "" });
  const [loading, setLoading] = useState(true);

  const load = () => {
    getMaintenanceSummary().then(setSummary).catch(() => {});
    getTickets(statusFilter ? { status: statusFilter } : {}).then((d) => {
      setTickets(d.tickets || []); setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(load, [statusFilter]);

  const submit = async () => {
    if (!form.title || !form.property_id) return;
    try {
      await createTicket({ ...form, property_id: form.property_id });
      setForm({ title: "", description: "", category: "plumbing", priority: "medium", unit_number: "", property_id: "" });
      setShowForm(false);
      load();
    } catch (e) { alert("Error: " + (e as Error).message); }
  };

  const cycleStatus = async (t: any) => {
    const order: Status[] = ["open", "assigned", "in_progress", "resolved", "closed"];
    const idx = order.indexOf(t.status as Status);
    const next = order[Math.min(idx + 1, order.length - 1)];
    await updateTicket(t.id, { status: next });
    load();
  };

  const filtered = tickets.filter((t) =>
    t.title?.toLowerCase().includes(search.toLowerCase()) ||
    t.unit_number?.toLowerCase().includes(search.toLowerCase()) ||
    t.property_name?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-5">
      <PageHeader title="Maintenance" sub="Tickets, assignments & resolution tracking"
        actions={
          <button onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25">
            <Plus className="w-3.5 h-3.5" /> New Ticket
          </button>
        }
      />

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card className="p-3"><div className="text-xs text-slate-500">Total</div><div className="text-lg font-bold text-white">{summary.total}</div></Card>
          <Card className="p-3"><div className="text-xs text-slate-500">Open</div><div className="text-lg font-bold text-amber-400">{summary.open}</div></Card>
          <Card className="p-3"><div className="text-xs text-slate-500">Resolved</div><div className="text-lg font-bold text-emerald-400">{summary.resolved}</div></Card>
          <Card className="p-3"><div className="text-xs text-slate-500">Urgent</div><div className="text-lg font-bold text-rose-400">{summary.urgent}</div></Card>
        </div>
      )}

      {showForm && (
        <Card className="p-4 space-y-3">
          <input placeholder="Title (e.g. Burst pipe in M12)"
            value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500" />
          <textarea placeholder="Description"
            value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm outline-none focus:border-emerald-500 h-20" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-sm outline-none">
              {["plumbing", "electrical", "structural", "appliance", "pest_control", "cleaning", "security", "other"].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}
              className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-sm outline-none">
              {["low", "medium", "high", "urgent"].map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <input placeholder="Unit (e.g. M12)" value={form.unit_number} onChange={(e) => setForm({ ...form, unit_number: e.target.value })}
              className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-sm outline-none" />
            <input placeholder="Property ID" value={form.property_id} onChange={(e) => setForm({ ...form, property_id: e.target.value })}
              className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-sm outline-none" />
          </div>
          <button onClick={submit} className="px-4 py-2 rounded-lg bg-emerald-500 text-slate-950 font-medium text-sm hover:bg-emerald-400">
            Create Ticket
          </button>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {["", "open", "assigned", "in_progress", "resolved", "closed"].map((s) => (
          <button key={s} onClick={() => setStatusFilter(s)}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition ${
              statusFilter === s ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "bg-slate-800/50 text-slate-500 border border-slate-700/50"
            }`}>
            {s === "" ? "All" : s.replace("_", " ")}
          </button>
        ))}
        <div className="relative ml-auto">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)}
            className="w-44 bg-slate-800/50 border border-slate-700/50 rounded-lg pl-7 pr-2 py-1.5 text-sm outline-none focus:border-emerald-500/50" />
        </div>
      </div>

      {loading ? <div className="text-slate-500 py-16 text-center">Loading…</div> :
        filtered.length === 0 ? <EmptyState icon={<Wrench className="w-12 h-12" />} text="No tickets" /> :
        <div className="space-y-1.5">
          {filtered.map((t, i) => (
            <motion.div key={t.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
              className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-amber-500/10 flex items-center justify-center">
                  <Wrench className="w-4 h-4 text-amber-400" />
                </div>
                <div>
                  <div className="text-sm font-medium text-slate-200">{t.title}</div>
                  <div className="flex items-center gap-2 text-[10px] text-slate-500">
                    <span>{t.property_name}</span>
                    {t.unit_number && <><span>·</span><span>{t.unit_number}</span></>}
                    {t.assigned_name && <><span>·</span><span className="flex items-center gap-0.5"><User className="w-2.5 h-2.5" />{t.assigned_name}</span></>}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge color={PRIORITY_COLOR[t.priority] || "slate"}>{t.priority}</Badge>
                <button onClick={() => cycleStatus(t)}>
                  <Badge color={STATUS_COLOR[t.status] || "slate"}>
                    {t.status === "resolved" ? <CheckCircle2 className="w-2.5 h-2.5" /> : t.status === "open" ? <AlertTriangle className="w-2.5 h-2.5" /> : <Clock className="w-2.5 h-2.5" />}
                    {t.status.replace("_", " ")}
                  </Badge>
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      }
    </div>
  );
}
