import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Smartphone, Home, Receipt, Wrench, Wallet, Bell, FileText, PenSquare, CheckCircle2 } from "lucide-react";
import { getTenantPortal } from "../lib/api";
import { Card, PageHeader, Badge, money } from "../components/ui";

export default function TenantPortal() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [lookup, setLookup] = useState("");
  const [signing, setSigning] = useState(false);
  const [signMsg, setSignMsg] = useState("");

  useEffect(() => {
    // demo tenant id 1 (Grace Kiprono) — load by default to preview
    getTenantPortal("1").then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const lookupTenant = async () => {
    if (!lookup) return;
    setLoading(true);
    try { const d = await getTenantPortal(lookup); setData(d); } catch (e) { alert("Not found"); }
    setLoading(false);
  };

  return (
    <div className="space-y-5">
      <PageHeader title="Tenant Portal" sub="What your tenants see on their app"
        actions={
          <div className="flex items-center gap-2">
            <input placeholder="Tenant ID" value={lookup} onChange={(e) => setLookup(e.target.value)}
              className="w-28 bg-slate-800/50 border border-slate-700/50 rounded-lg px-2 py-1.5 text-sm outline-none focus:border-emerald-500/50" />
            <button onClick={lookupTenant} className="px-3 py-1.5 rounded-lg text-xs bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">View</button>
          </div>
        }
      />

      <div className="flex items-center gap-2 text-xs text-slate-500 bg-slate-900/40 border border-slate-800 rounded-lg px-3 py-2">
        <Smartphone className="w-4 h-4 text-emerald-400" />
        Preview of the mobile tenant experience — balance, payments, maintenance requests & notices.
      </div>

      {loading ? <div className="text-slate-500 py-16 text-center">Loading…</div> : data && (
        <div className="grid md:grid-cols-2 gap-4">
          <Card className="p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-emerald-500/15 flex items-center justify-center text-emerald-400 font-bold">
                  {data.tenant?.full_name?.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <div className="text-sm font-bold text-white">{data.tenant?.full_name}</div>
                  <div className="text-[11px] text-slate-500 flex items-center gap-1"><Home className="w-3 h-3" /> {data.tenant?.unit_number}</div>
                </div>
              </div>
              {data.balance > 0 ? <Badge color="rose">Due KES {money(data.balance)}</Badge>
                : <Badge color="emerald">All Paid</Badge>}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <Mini icon={<Wallet className="w-4 h-4" />} label="Rent" value={`KES ${money(data.tenant?.rent_amount)}`} />
              <Mini icon={<Receipt className="w-4 h-4" />} label="Last Paid" value={data.payments?.[0]?.paid_at || "—"} />
              <Mini icon={<Wrench className="w-4 h-4" />} label="Tickets" value={`${data.tickets?.length || 0} open`} />
              <Mini icon={<Bell className="w-4 h-4" />} label="Notices" value={`${data.notices?.length || 0} new`} />
            </div>
          </Card>

          {/* Lease e-sign */}
          {data.lease && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <PenSquare className="w-3.5 h-3.5 text-sky-400" />
                <span className="text-[10px] font-semibold uppercase tracking-wider text-sky-400">Lease Agreement</span>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs text-slate-400">
                    Status: {data.lease.tenant_signed ? "Signed ✅" : "Pending signature"}
                  </div>
                  {data.lease.owner_signed && (
                    <div className="text-[10px] text-emerald-400 mt-0.5">Landlord has signed</div>
                  )}
                </div>
                {!data.lease.tenant_signed && (
                  <button onClick={async () => {
                    setSigning(true); setSignMsg("");
                    try {
                      const r = await fetch(`/api/v1/tenants/${data.tenant.id}/sign-lease?signer=tenant`, {
                        method: "POST",
                        headers: { Authorization: `Bearer ${localStorage.getItem("rental_token")}` },
                      });
                      const res = await r.json();
                      if (res.fully_signed) setSignMsg("Lease fully signed by both parties!");
                      else setSignMsg("Your signature recorded. Waiting for landlord.");
                      setData({ ...data, lease: { ...data.lease, tenant_signed: true } });
                    } catch { setSignMsg("Failed to sign"); }
                    setSigning(false);
                  }} disabled={signing}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-medium bg-sky-500/15 text-sky-300 border border-sky-500/25 hover:bg-sky-500/25 transition disabled:opacity-50">
                    <CheckCircle2 className="w-3 h-3" />
                    {signing ? "Signing..." : "Sign Lease"}
                  </button>
                )}
              </div>
              {signMsg && <p className="text-[10px] text-emerald-400 mt-2">{signMsg}</p>}
            </Card>
          )}

          {/* Documents */}
          {data.documents && data.documents.length > 0 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <FileText className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400">Documents</span>
              </div>
              <div className="space-y-1">
                {data.documents.map((d: any, i: number) => (
                  <a key={i} href={`/api/v1/documents/${d.id}/download`} target="_blank" rel="noopener noreferrer"
                    className="flex items-center justify-between px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-800 hover:border-emerald-500/30 transition">
                    <span className="text-xs text-slate-300">{d.original_name}</span>
                    <span className="text-[10px] text-slate-500">{d.category.replace("_", " ")}</span>
                  </a>
                ))}
              </div>
            </Card>
          )}

          <div className="space-y-3">
            <div>
              <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-1 flex items-center gap-1"><Receipt className="w-3 h-3" /> Recent Payments</div>
              <div className="space-y-1">
                {(data.payments || []).slice(0, 4).map((p: any, i: number) => (
                  <div key={i} className="flex justify-between text-xs px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-800">
                    <span className="text-slate-300">{p.paid_at}</span>
                    <span className="text-emerald-400 font-medium">KES {money(p.amount)}</span>
                  </div>
                ))}
                {(!data.payments || data.payments.length === 0) && <p className="text-slate-600 text-xs">No payments</p>}
              </div>
            </div>

            <div>
              <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-1 flex items-center gap-1"><Wrench className="w-3 h-3" /> My Tickets</div>
              <div className="space-y-1">
                {(data.tickets || []).map((t: any, i: number) => (
                  <div key={i} className="flex justify-between text-xs px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-800">
                    <span className="text-slate-300">{t.title}</span>
                    <Badge color={t.status === "resolved" ? "emerald" : t.status === "open" ? "rose" : "amber"}>{t.status.replace("_", " ")}</Badge>
                  </div>
                ))}
                {(!data.tickets || data.tickets.length === 0) && <p className="text-slate-600 text-xs">No tickets</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Mini({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-slate-900/60 border border-slate-800">
      <div className="text-emerald-400">{icon}</div>
      <div>
        <div className="text-[10px] text-slate-500">{label}</div>
        <div className="text-xs font-semibold text-slate-200">{value}</div>
      </div>
    </div>
  );
}
