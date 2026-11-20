import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Search, Users, Phone, MapPin, AlertTriangle, CheckCircle2,
  Wallet, UserRound, X,
} from "lucide-react";
import { getTenants } from "../lib/api";
import { Card, PageHeader, Badge, EmptyState, StatCard, money } from "../components/ui";

type TenantFilter = "all" | "paid" | "due";

export default function Tenants() {
  const [tenants, setTenants] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<TenantFilter>("all");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let active = true;
    getTenants()
      .then((d) => {
        if (active) setTenants(Array.isArray(d?.tenants) ? d.tenants : []);
      })
      .catch((error) => {
        if (active) setLoadError(error?.message || "Could not load tenant records.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const summary = useMemo(() => {
    const due = tenants.filter((t) => Number(t.balance || 0) > 0);
    const collected = tenants.reduce((sum, t) => sum + Number(t.rent_amount || 0), 0);
    return {
      total: tenants.length,
      paid: tenants.filter((t) => t.status === "paid").length,
      due: due.length,
      balance: due.reduce((sum, t) => sum + Number(t.balance || 0), 0),
      rent: collected,
    };
  }, [tenants]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return tenants.filter((t) => {
      const matchesSearch = !term || [
        t.full_name, t.unit_number, t.phone, t.mpesa_phone, t.property_name,
      ].some((value) => String(value || "").toLowerCase().includes(term));
      const matchesFilter = filter === "all"
        || (filter === "paid" && t.status === "paid")
        || (filter === "due" && Number(t.balance || 0) > 0);
      return matchesSearch && matchesFilter;
    });
  }, [tenants, search, filter]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tenant directory"
        sub="A clear view of residents, their units and current rent position"
        actions={
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              aria-label="Search tenants"
              placeholder="Name, unit or phone"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full min-h-11 bg-[#0c1a28] border border-white/10 rounded-xl pl-10 pr-10 py-2.5 text-sm text-slate-200 outline-none transition focus:border-emerald-300/50 focus:ring-2 focus:ring-emerald-300/10 placeholder:text-slate-600"
            />
            {search && (
              <button
                type="button"
                aria-label="Clear tenant search"
                onClick={() => setSearch("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-slate-500 hover:text-white hover:bg-white/5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
        <StatCard icon={<Users className="w-4 h-4" />} label="Registered tenants" value={summary.total} color="white" sub="Across your managed portfolio" />
        <StatCard icon={<CheckCircle2 className="w-4 h-4" />} label="Paid this period" value={summary.paid} color="emerald" sub="Tenant records marked paid" />
        <StatCard icon={<AlertTriangle className="w-4 h-4" />} label="With a balance due" value={summary.due} color="amber" sub="Based on recorded balances" />
        <StatCard icon={<Wallet className="w-4 h-4" />} label="Outstanding balance" value={`KES ${money(summary.balance)}`} color="rose" sub="Across tenants with a balance" />
      </div>

      <Card className="p-4 sm:p-5" hover={false}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-sm font-semibold text-white">Residents</h2>
            <p className="text-xs text-slate-500 mt-1">
              {loading ? "Loading tenant records…" : `Showing ${filtered.length} of ${tenants.length} tenants`}
            </p>
          </div>
          <div className="flex items-center gap-1 rounded-xl bg-slate-950/70 border border-white/[0.06] p-1 w-full sm:w-auto">
            {([
              ["all", "All tenants", summary.total],
              ["paid", "Paid", summary.paid],
              ["due", "Balance due", summary.due],
            ] as const).map(([key, label, count]) => (
              <button
                key={key}
                type="button"
                onClick={() => setFilter(key)}
                aria-pressed={filter === key}
                className={`flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition ${filter === key
                  ? "bg-emerald-400/12 text-emerald-200 border border-emerald-300/20"
                  : "text-slate-500 border border-transparent hover:text-slate-200 hover:bg-white/[0.04]"}`}
              >
                {label}
                <span className="text-[10px] tabular-nums opacity-70">{count}</span>
              </button>
            ))}
          </div>
        </div>

        {loadError ? (
          <div role="alert" className="rounded-xl border border-rose-400/20 bg-rose-400/5 px-4 py-3 text-sm text-rose-200">
            {loadError}
          </div>
        ) : loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((item) => (
              <div key={item} className="h-[76px] rounded-xl bg-white/[0.025] animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<Users className="w-10 h-10" />}
            text={search || filter !== "all" ? "No tenants match this view" : "No tenant records yet"}
            sub={search || filter !== "all" ? "Try a different search or clear the selected filter." : "Tenant records will appear here when they are added to your properties."}
          />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {filtered.map((t, i) => {
              const balance = Number(t.balance || 0);
              const paid = t.status === "paid";
              const due = balance > 0;
              return (
                <motion.article
                  key={t.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(i * 0.025, 0.2) }}
                  className="rounded-xl border border-white/[0.07] bg-gradient-to-br from-white/[0.035] to-transparent p-4 transition hover:border-emerald-300/20 hover:bg-white/[0.025]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-11 h-11 shrink-0 rounded-xl bg-emerald-300/10 border border-emerald-300/10 flex items-center justify-center text-emerald-200 font-semibold text-sm">
                        {t.full_name?.trim()?.slice(0, 2).toUpperCase() || <UserRound className="w-5 h-5" />}
                      </div>
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold text-slate-100 truncate">{t.full_name || "Unnamed tenant"}</h3>
                        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1 text-[11px] text-slate-500">
                          <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" /> Unit {t.unit_number || "—"}</span>
                          {t.property_name && <span className="truncate">{t.property_name}</span>}
                        </div>
                      </div>
                    </div>
                    <Badge color={paid ? "emerald" : due ? "amber" : t.status === "partial" ? "sky" : "slate"}>
                      {paid ? <CheckCircle2 className="w-3 h-3" /> : due ? <AlertTriangle className="w-3 h-3" /> : null}
                      {t.status || "Unclassified"}
                    </Badge>
                  </div>

                  <div className="mt-4 pt-3 border-t border-white/[0.06] grid grid-cols-2 gap-3">
                    <div className="min-w-0">
                      <div className="text-[10px] uppercase tracking-wider text-slate-600">Monthly rent</div>
                      <div className="mt-1 text-sm font-semibold text-slate-200 tabular-nums">KES {money(t.rent_amount)}</div>
                    </div>
                    <div className="min-w-0 text-right">
                      <div className="text-[10px] uppercase tracking-wider text-slate-600">Balance due</div>
                      <div className={`mt-1 text-sm font-semibold tabular-nums ${due ? "text-rose-300" : "text-emerald-300"}`}>
                        KES {money(balance)}
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center gap-2 text-xs text-slate-500 min-w-0">
                    <Phone className="w-3.5 h-3.5 shrink-0" />
                    <span className="truncate">{t.phone || t.mpesa_phone || "No phone number recorded"}</span>
                  </div>
                </motion.article>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
