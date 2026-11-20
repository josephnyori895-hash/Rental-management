import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Wrench, Plus, Search, AlertTriangle, CheckCircle2, Clock, User,
  Building2, X, Loader2, RefreshCw, ArrowRight,
} from "lucide-react";
import {
  getTickets, getMaintenanceSummary, createTicket, updateTicket, getProperties,
} from "../lib/api";
import {
  Card, PageHeader, Badge, EmptyState, StatCard,
} from "../components/ui";

type Status = "open" | "assigned" | "in_progress" | "resolved" | "closed";

const STATUS_COLOR: Record<string, string> = {
  open: "rose", assigned: "amber", in_progress: "sky", resolved: "emerald", closed: "slate",
};
const PRIORITY_COLOR: Record<string, string> = {
  low: "slate", medium: "sky", high: "amber", urgent: "rose",
};
const STATUSES: { value: Status | ""; label: string }[] = [
  { value: "", label: "All work" },
  { value: "open", label: "Open" },
  { value: "assigned", label: "Assigned" },
  { value: "in_progress", label: "In progress" },
  { value: "resolved", label: "Resolved" },
  { value: "closed", label: "Closed" },
];

const initialForm = {
  title: "",
  description: "",
  category: "plumbing",
  priority: "medium",
  unit_number: "",
  property_id: "",
};

export default function Maintenance() {
  const [tickets, setTickets] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [properties, setProperties] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState<Status | "">("");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState("");
  const [formError, setFormError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoadError("");
    const [ticketResult, summaryResult] = await Promise.allSettled([
      getTickets(statusFilter ? { status: statusFilter } : {}),
      getMaintenanceSummary(),
    ]);
    if (ticketResult.status === "fulfilled") {
      setTickets(Array.isArray(ticketResult.value?.tickets) ? ticketResult.value.tickets : []);
    } else {
      setLoadError(ticketResult.reason?.message || "Maintenance tickets could not be loaded.");
    }
    if (summaryResult.status === "fulfilled") setSummary(summaryResult.value);
    setLoading(false);
  }, [statusFilter]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    getProperties()
      .then((data) => setProperties(Array.isArray(data?.properties) ? data.properties : []))
      .catch(() => setProperties([]));
  }, []);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return tickets;
    return tickets.filter((ticket) =>
      [ticket.title, ticket.unit_number, ticket.property_name, ticket.assigned_name, ticket.category]
        .some((value) => String(value || "").toLowerCase().includes(term))
    );
  }, [tickets, search]);

  const submit = async () => {
    setFormError("");
    setNotice("");
    if (!form.title.trim()) {
      setFormError("Add a short title describing the maintenance issue.");
      return;
    }
    if (!form.property_id) {
      setFormError("Select the property where the issue was reported.");
      return;
    }
    setSaving(true);
    try {
      await createTicket({ ...form, title: form.title.trim(), property_id: form.property_id });
      setForm(initialForm);
      setShowForm(false);
      setNotice("Maintenance ticket created.");
      setLoading(true);
      await load();
    } catch (error) {
      setFormError((error as Error).message || "The ticket could not be created.");
    } finally {
      setSaving(false);
    }
  };

  const advanceStatus = async (ticket: any) => {
    const order: Status[] = ["open", "assigned", "in_progress", "resolved", "closed"];
    const index = order.indexOf(ticket.status as Status);
    if (index < 0 || index === order.length - 1) return;
    const next = order[index + 1];
    setUpdatingId(ticket.id);
    setNotice("");
    try {
      await updateTicket(ticket.id, { status: next });
      setNotice(`“${ticket.title}” moved to ${next.replace("_", " ")}.`);
      await load();
    } catch (error) {
      setLoadError((error as Error).message || "The ticket status could not be updated.");
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Maintenance & operations"
        sub="Keep property issues visible, prioritised and moving towards resolution"
        actions={
          <button
            type="button"
            onClick={() => { setShowForm((value) => !value); setFormError(""); }}
            className="inline-flex items-center justify-center gap-2 min-h-11 px-4 rounded-xl bg-emerald-300 text-slate-950 text-xs font-semibold hover:bg-emerald-200 transition"
          >
            {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
            {showForm ? "Close form" : "New work order"}
          </button>
        }
      />

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <StatCard icon={<Wrench className="w-4 h-4" />} label="All work orders" value={summary?.total ?? tickets.length} color="white" sub="Recorded maintenance tickets" />
        <StatCard icon={<AlertTriangle className="w-4 h-4" />} label="Open" value={summary?.open ?? 0} color="amber" sub="Awaiting further action" />
        <StatCard icon={<CheckCircle2 className="w-4 h-4" />} label="Resolved" value={summary?.resolved ?? 0} color="emerald" sub="Marked as resolved" />
        <StatCard icon={<Clock className="w-4 h-4" />} label="Urgent priority" value={summary?.urgent ?? 0} color="rose" sub="Needs prompt attention" />
      </div>

      {notice && (
        <div role="status" className="rounded-xl border border-emerald-300/15 bg-emerald-300/[0.06] px-4 py-3 text-xs text-emerald-200">
          {notice}
        </div>
      )}
      {loadError && (
        <div role="alert" className="rounded-xl border border-rose-300/20 bg-rose-300/[0.06] px-4 py-3 text-xs text-rose-200">
          {loadError}
        </div>
      )}

      {showForm && (
        <Card className="p-4 sm:p-5" hover={false}>
          <div className="flex items-start justify-between gap-3 mb-4">
            <div>
              <h2 className="text-sm font-semibold text-white">Create a work order</h2>
              <p className="text-xs text-slate-500 mt-1">Record the issue and link it to the correct property and unit.</p>
            </div>
            <div className="w-9 h-9 rounded-xl bg-emerald-300/10 flex items-center justify-center">
              <Wrench className="w-4 h-4 text-emerald-200" />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="md:col-span-2 block">
              <span className="block text-[11px] font-medium text-slate-400 mb-1.5">Issue title</span>
              <input
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
                placeholder="e.g. Burst pipe in apartment M12"
                maxLength={160}
                className="w-full min-h-11 bg-slate-950/60 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white outline-none focus:border-emerald-300/40"
              />
            </label>
            <label className="md:col-span-2 block">
              <span className="block text-[11px] font-medium text-slate-400 mb-1.5">Description</span>
              <textarea
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
                placeholder="Add useful details about the issue, access requirements or reported symptoms…"
                rows={3}
                className="w-full bg-slate-950/60 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white outline-none focus:border-emerald-300/40 resize-y"
              />
            </label>
            <label className="block">
              <span className="block text-[11px] font-medium text-slate-400 mb-1.5">Property</span>
              <select
                value={form.property_id}
                onChange={(event) => setForm({ ...form, property_id: event.target.value })}
                className="w-full min-h-11 bg-slate-950/60 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white outline-none focus:border-emerald-300/40"
              >
                <option value="">Select a property</option>
                {properties.map((property) => (
                  <option key={property.id} value={property.id}>{property.name}</option>
                ))}
              </select>
              {properties.length === 0 && <span className="block text-[10px] text-amber-300 mt-1">No properties are available to select.</span>}
            </label>
            <label className="block">
              <span className="block text-[11px] font-medium text-slate-400 mb-1.5">Unit (optional)</span>
              <input
                value={form.unit_number}
                onChange={(event) => setForm({ ...form, unit_number: event.target.value })}
                placeholder="e.g. M12"
                className="w-full min-h-11 bg-slate-950/60 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white outline-none focus:border-emerald-300/40"
              />
            </label>
            <label className="block">
              <span className="block text-[11px] font-medium text-slate-400 mb-1.5">Category</span>
              <select
                value={form.category}
                onChange={(event) => setForm({ ...form, category: event.target.value })}
                className="w-full min-h-11 bg-slate-950/60 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white outline-none focus:border-emerald-300/40"
              >
                {["plumbing", "electrical", "structural", "appliance", "pest_control", "cleaning", "security", "other"].map((category) => (
                  <option key={category} value={category}>{category.replace("_", " ")}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="block text-[11px] font-medium text-slate-400 mb-1.5">Priority</span>
              <select
                value={form.priority}
                onChange={(event) => setForm({ ...form, priority: event.target.value })}
                className="w-full min-h-11 bg-slate-950/60 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white outline-none focus:border-emerald-300/40"
              >
                {["low", "medium", "high", "urgent"].map((priority) => (
                  <option key={priority} value={priority}>{priority}</option>
                ))}
              </select>
            </label>
          </div>
          {formError && <p role="alert" className="mt-3 text-xs text-rose-300">{formError}</p>}
          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 mt-4">
            <button type="button" onClick={() => setShowForm(false)} className="min-h-10 px-4 rounded-xl border border-white/10 text-xs text-slate-300 hover:bg-white/[0.04]">
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void submit()}
              disabled={saving || properties.length === 0}
              className="inline-flex items-center justify-center gap-2 min-h-10 px-4 rounded-xl bg-emerald-300 text-slate-950 text-xs font-semibold hover:bg-emerald-200 disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              {saving ? "Creating…" : "Create work order"}
            </button>
          </div>
        </Card>
      )}

      <Card className="p-4 sm:p-5" hover={false}>
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-sm font-semibold text-white">Work order board</h2>
            <p className="text-xs text-slate-500 mt-1">{loading ? "Loading tickets…" : `${filtered.length} tickets in this view`}</p>
          </div>
          <div className="relative w-full lg:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              aria-label="Search maintenance tickets"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search issue, property, unit…"
              className="w-full min-h-10 bg-slate-950/60 border border-white/10 rounded-xl pl-10 pr-3 py-2 text-xs text-slate-200 outline-none focus:border-emerald-300/40"
            />
          </div>
        </div>
        <div className="flex gap-1.5 overflow-x-auto pb-2 mb-3">
          {STATUSES.map((status) => (
            <button
              key={status.value || "all"}
              type="button"
              onClick={() => { setStatusFilter(status.value); setLoading(true); }}
              aria-pressed={statusFilter === status.value}
              className={`shrink-0 min-h-9 px-3 rounded-lg text-[11px] font-medium transition ${
                statusFilter === status.value
                  ? "bg-emerald-300/10 text-emerald-200 border border-emerald-300/20"
                  : "bg-white/[0.025] text-slate-500 border border-white/[0.05] hover:text-slate-200"
              }`}
            >
              {status.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((item) => <div key={item} className="h-20 rounded-xl bg-white/[0.025] animate-pulse" />)}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<Wrench className="w-10 h-10" />}
            text={search || statusFilter ? "No work orders match this view" : "No maintenance work orders yet"}
            sub={search || statusFilter ? "Try another search or status filter." : "Create a work order when a property issue needs attention."}
          />
        ) : (
          <div className="space-y-2">
            {filtered.map((ticket, index) => {
              const order: Status[] = ["open", "assigned", "in_progress", "resolved", "closed"];
              const current = order.indexOf(ticket.status as Status);
              const next = current >= 0 && current < order.length - 1 ? order[current + 1] : null;
              return (
                <motion.article
                  key={ticket.id}
                  initial={{ opacity: 0, y: 7 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(index * 0.02, 0.16) }}
                  className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 sm:p-4 hover:border-emerald-300/15 transition"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="w-10 h-10 shrink-0 rounded-xl bg-amber-300/10 border border-amber-300/10 flex items-center justify-center">
                        <Wrench className="w-4 h-4 text-amber-200" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold text-slate-100">{ticket.title || "Maintenance issue"}</h3>
                        {ticket.description && <p className="text-xs text-slate-500 mt-1 line-clamp-2">{ticket.description}</p>}
                        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-2 text-[11px] text-slate-500">
                          <span className="inline-flex items-center gap-1"><Building2 className="w-3 h-3" />{ticket.property_name || "Property not specified"}</span>
                          {ticket.unit_number && <span>· Unit {ticket.unit_number}</span>}
                          {ticket.assigned_name && <span className="inline-flex items-center gap-1">· <User className="w-3 h-3" />{ticket.assigned_name}</span>}
                          {ticket.category && <span>· {String(ticket.category).replace("_", " ")}</span>}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between sm:justify-end gap-2 pl-[52px] sm:pl-0">
                      <Badge color={PRIORITY_COLOR[ticket.priority] || "slate"}>{ticket.priority || "normal"} priority</Badge>
                      <Badge color={STATUS_COLOR[ticket.status] || "slate"}>{String(ticket.status || "unknown").replace("_", " ")}</Badge>
                      {next && (
                        <button
                          type="button"
                          disabled={updatingId === ticket.id}
                          onClick={() => void advanceStatus(ticket)}
                          aria-label={`Move ${ticket.title} to ${next.replace("_", " ")}`}
                          title={`Move to ${next.replace("_", " ")}`}
                          className="w-9 h-9 rounded-lg border border-white/10 bg-white/[0.04] text-slate-400 hover:text-emerald-200 hover:border-emerald-300/20 flex items-center justify-center disabled:opacity-50"
                        >
                          {updatingId === ticket.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                        </button>
                      )}
                    </div>
                  </div>
                </motion.article>
              );
            })}
          </div>
        )}
        <div className="flex justify-end pt-3">
          <button type="button" onClick={() => { setLoading(true); void load(); }} className="inline-flex items-center gap-1.5 text-[11px] text-slate-500 hover:text-emerald-200">
            <RefreshCw className="w-3 h-3" /> Refresh work orders
          </button>
        </div>
      </Card>
    </div>
  );
}
