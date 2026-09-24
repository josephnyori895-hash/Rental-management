import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Search, Users, Phone, MapPin, AlertTriangle, CheckCircle2 } from "lucide-react";
import { getTenants } from "../lib/api";
import { Card, PageHeader, Badge, EmptyState, money } from "../components/ui";

export default function Tenants() {
  const [tenants, setTenants] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTenants().then((d) => { setTenants(d.tenants || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const filtered = tenants.filter((t) =>
    t.full_name?.toLowerCase().includes(search.toLowerCase()) ||
    t.unit_number?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-5">
      <PageHeader title="Tenants" sub={`${tenants.length} active tenants`}
        actions={
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
            <input placeholder="Search tenant or unit..."
              value={search} onChange={(e) => setSearch(e.target.value)}
              className="w-52 bg-slate-800/50 border border-slate-700/50 rounded-lg pl-7 pr-2 py-1.5 text-sm outline-none focus:border-emerald-500/50 placeholder:text-slate-600" />
          </div>
        }
      />

      {loading ? (
        <div className="text-slate-500 py-16 text-center">Loading…</div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={<Users className="w-12 h-12" />} text="No tenants found" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((t, i) => (
            <motion.div key={t.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
              <Card className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className="w-9 h-9 rounded-lg bg-emerald-500/15 flex items-center justify-center text-emerald-400 font-bold text-sm">
                      {t.full_name?.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-white">{t.full_name}</div>
                      <div className="text-[10px] text-slate-500 flex items-center gap-1">
                        <MapPin className="w-2.5 h-2.5" /> {t.unit_number || "—"}
                      </div>
                    </div>
                  </div>
                  {t.status === "paid" ? (
                    <Badge color="emerald"><CheckCircle2 className="w-2.5 h-2.5" /> Paid</Badge>
                  ) : t.status === "pending" || t.status === "partial" ? (
                    <Badge color="amber"><AlertTriangle className="w-2.5 h-2.5" /> {t.status}</Badge>
                  ) : (
                    <Badge color="rose"><AlertTriangle className="w-2.5 h-2.5" /> {t.status}</Badge>
                  )}
                </div>
                <div className="space-y-1 text-[11px] text-slate-400">
                  <div className="flex items-center gap-1.5"><Phone className="w-3 h-3" /> {t.phone || t.mpesa_phone || "—"}</div>
                  <div className="flex justify-between">
                    <span>Rent: <span className="text-slate-200">KES {money(t.rent_amount)}</span></span>
                    {t.balance > 0 && <span className="text-rose-400">Due: KES {money(t.balance)}</span>}
                  </div>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
