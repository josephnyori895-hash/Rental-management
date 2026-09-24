import { useEffect, useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  Building2, Phone, Clock, Home, CheckCircle2,
  AlertTriangle, MessageCircle, Hash, ArrowLeft, Calendar,
} from "lucide-react";
import { getBoard } from "../lib/api";

const money = (n: number) => `KES ${(n ?? 0).toLocaleString("en-KE")}`;

interface TenantData {
  tenant_id?: string;
  unit_number?: string;
  tenant_name?: string;
  rent_amount?: number;
  amount_paid?: number;
  balance?: number;
  duration_months?: number;
  invoice_status?: string;
  due_date?: string;
  status?: string;
  light?: string;
  hostel_name?: string;
  property_id?: string;
  unit_id?: string;
  amount?: number;
  phone?: string;
  mpesa_phone?: string;
  whatsapp_phone?: string;
  id_number?: string;
  email?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  created_at?: string;
}

interface Props {
  tenant: TenantData | null;
  onBack: () => void;
  onNavigateToTenant: (tenant: TenantData) => void;
}

export default function TenantDetailPage({ tenant, onBack, onNavigateToTenant }: Props) {
  const [boardData, setBoardData] = useState<any>(null);

  useEffect(() => {
    getBoard().then(setBoardData).catch(() => {});
  }, []);

  if (!tenant) return null;

  const isPaid   = tenant.light === "green";
  const isUnpaid = tenant.light === "red";
  const isVacant = tenant.light === "empty";

  const rent = tenant.rent_amount ?? 0;
  const paid = tenant.amount_paid ?? tenant.amount ?? 0;
  const bal  = tenant.balance !== undefined
    ? tenant.balance
    : isUnpaid ? Math.max(0, rent - paid) : 0;

  const phone      = tenant.whatsapp_phone ?? tenant.mpesa_phone ?? tenant.phone ?? "";
  const waPhone    = phone.replace(/[^0-9]/g, "");
  const waLink     = waPhone
    ? `https://wa.me/${waPhone}?text=${encodeURIComponent(
        `Hi ${tenant.tenant_name ?? "Tenant"} (Room ${tenant.unit_number}), this is the hostel management.`
      )}`
    : null;
  const callLink = phone ? `tel:+${waPhone}` : null;

  const statusColor = isPaid   ? { bg: "bg-emerald-500/15", text: "text-emerald-300", border: "border-emerald-500/30", glow: "shadow-emerald-500/10" }
                    : isUnpaid ? { bg: "bg-rose-500/15",    text: "text-rose-300",    border: "border-rose-500/30",    glow: "shadow-rose-500/10"    }
                               : { bg: "bg-slate-800/50",   text: "text-slate-400",  border: "border-slate-700/30",   glow: ""                      };

  /* ─── Build house design from board data ─── */
  const allHostelUnits = useMemo(() => {
    if (!boardData?.hostels) return [];
    const units: any[] = [];
    boardData.hostels.forEach((h: any) => {
      (h.units || []).forEach((u: any) => {
        units.push({ ...u, hostel_name: h.name, property_id: h.property_id });
      });
    });
    return units;
  }, [boardData]);

  const currentRoomIndex = useMemo(() => {
    return allHostelUnits.findIndex(
      (u: any) => u.unit_id === tenant.unit_id || u.unit_number === tenant.unit_number
    );
  }, [allHostelUnits, tenant]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6"
    >
      {/* ── Back button ── */}
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition px-1 py-1"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Dashboard
      </button>

      {/* ── Tenant Header Card ── */}
      <motion.div
        initial={{ y: 12, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className={`rounded-2xl border ${statusColor.border} ${statusColor.bg} p-6 shadow-lg ${statusColor.glow}`}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className={`w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-black text-white border-2 ${statusColor.border} ${statusColor.bg}`}>
              {tenant.tenant_name?.[0]?.toUpperCase() ?? (isVacant ? "·" : "?")}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">
                {isVacant ? "Vacant Room" : tenant.tenant_name ?? "Unknown"}
              </h1>
              <div className="flex items-center gap-3 mt-1 flex-wrap">
                <span className="text-emerald-400 font-semibold">Room {tenant.unit_number}</span>
                {tenant.hostel_name && (
                  <>
                    <span className="text-slate-600">·</span>
                    <span className="text-sm text-slate-400">{tenant.hostel_name}</span>
                  </>
                )}
              </div>
              <div className={`inline-flex items-center gap-1.5 mt-3 px-3 py-1 rounded-full text-xs font-bold border ${statusColor.bg} ${statusColor.text} ${statusColor.border}`}>
                {isPaid   && <><CheckCircle2 className="w-3.5 h-3.5" /> PAID</>}
                {isUnpaid && <><AlertTriangle className="w-3.5 h-3.5" /> UNPAID</>}
                {isVacant && <><Home className="w-3.5 h-3.5" /> VACANT</>}
              </div>
            </div>
          </div>
        </div>

        {!isVacant && (
          <div className="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-xl bg-slate-800/40 border border-slate-700/30 p-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Monthly Rent</div>
              <div className="text-lg font-bold text-white">{money(rent)}</div>
            </div>
            <div className="rounded-xl bg-slate-800/40 border border-slate-700/30 p-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Amount Paid</div>
              <div className={`text-lg font-bold ${isPaid ? "text-emerald-400" : "text-rose-400"}`}>
                {money(paid)}
              </div>
            </div>
            <div className="rounded-xl bg-slate-800/40 border border-slate-700/30 p-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Balance</div>
              <div className={`text-lg font-bold ${bal > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                {bal > 0 ? money(bal) : "KES 0"}
              </div>
            </div>
          </div>
        )}
      </motion.div>

      {/* ── House Design: Room Grid ── */}
      <motion.div
        initial={{ y: 12, opacity: 0 }}
        animate={{ y: 0, opacity: 1, transition: { delay: 0.1 } }}
        className="rounded-2xl border border-slate-700/50 bg-slate-900/60 backdrop-blur p-5"
      >
        <h2 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
          <Building2 className="w-4 h-4 text-emerald-400" />
          {tenant.hostel_name || "Property"} — Room Layout
          <span className="text-xs text-slate-500 ml-auto">
            Click any room to view tenant
          </span>
        </h2>

        {allHostelUnits.length > 0 ? (
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-2">
            {allHostelUnits.map((u: any, i: number) => {
              const isCurrent = i === currentRoomIndex;
              const uLight = u.light === "green" ? "paid" : u.light === "red" ? "unpaid" : u.light === "empty" ? "vacant" : u.light === "yellow" ? "partial" : "vacant";
              const colors: Record<string, { bg: string; border: string; text: string }> = {
                paid:    { bg: "bg-emerald-500/15", border: "border-emerald-500/40", text: "text-emerald-300" },
                unpaid:  { bg: "bg-rose-500/15",    border: "border-rose-500/40",    text: "text-rose-300" },
                partial: { bg: "bg-amber-500/15",   border: "border-amber-500/40",   text: "text-amber-300" },
                vacant:  { bg: "bg-slate-800/40",    border: "border-slate-700/40",   text: "text-slate-400" },
              };
              const c = colors[uLight] || colors.vacant;

              return (
                <button
                  key={u.unit_id || i}
                  onClick={() => u.tenant_name && onNavigateToTenant({ ...u, hostel_name: tenant.hostel_name })}
                  disabled={!u.tenant_name}
                  className={`
                    relative rounded-xl border text-left transition-all duration-200 overflow-hidden
                    ${c.bg} ${c.border}
                    ${isCurrent ? "ring-2 ring-emerald-400 ring-offset-2 ring-offset-slate-900 scale-105 z-10" : ""}
                    ${u.tenant_name ? "hover:border-emerald-500/50 hover:shadow-lg hover:shadow-emerald-500/5 cursor-pointer" : "opacity-60"}
                    p-3
                  `}
                >
                  {/* Current tenant indicator */}
                  {isCurrent && (
                    <div className="absolute top-1 right-1 w-2 h-2 rounded-full bg-emerald-400 shadow-lg shadow-emerald-500/50" />
                  )}

                  <div className={`text-xs font-bold mb-1 ${c.text}`}>
                    {u.unit_number}
                  </div>
                  <div className="text-[10px] text-slate-500 truncate leading-tight">
                    {u.tenant_name || "Vacant"}
                  </div>
                  <div className={`text-[10px] font-semibold mt-1 ${c.text}`}>
                    {uLight === "paid" ? "Paid" : uLight === "unpaid" ? "Unpaid" : uLight === "partial" ? "Partial" : "—"}
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="text-sm text-slate-500 py-8 text-center">
            No units available. Board data not loaded.
          </div>
        )}
      </motion.div>

      {/* ── Contact & Details ── */}
      {!isVacant && (
        <motion.div
          initial={{ y: 12, opacity: 0 }}
          animate={{ y: 0, opacity: 1, transition: { delay: 0.15 } }}
          className="rounded-2xl border border-slate-700/50 bg-slate-900/60 backdrop-blur p-5"
        >
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Contact & Details</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {phone && (
              <div className="flex items-center gap-3 text-sm">
                <Phone className="w-4 h-4 text-slate-500 shrink-0" />
                <span className="text-slate-300">{phone}</span>
                {waLink && (
                  <a href={waLink} target="_blank" rel="noreferrer"
                    className="ml-auto text-emerald-400 hover:text-emerald-300 text-xs font-semibold flex items-center gap-1"
                  >
                    <MessageCircle className="w-3.5 h-3.5" /> WhatsApp
                  </a>
                )}
              </div>
            )}
            {tenant.email && (
              <div className="flex items-center gap-3 text-sm">
                <span className="text-slate-400">Email:</span>
                <span className="text-slate-300">{tenant.email}</span>
              </div>
            )}
            {tenant.id_number && (
              <div className="flex items-center gap-3 text-sm">
                <Hash className="w-4 h-4 text-slate-500 shrink-0" />
                <span className="text-slate-400">ID:</span>
                <span className="text-slate-300">{tenant.id_number}</span>
              </div>
            )}
            {tenant.duration_months && (
              <div className="flex items-center gap-3 text-sm">
                <Calendar className="w-4 h-4 text-slate-500 shrink-0" />
                <span className="text-slate-400">Duration:</span>
                <span className="text-slate-300">{tenant.duration_months} months</span>
              </div>
            )}
            {tenant.due_date && (
              <div className="flex items-center gap-3 text-sm">
                <Clock className="w-4 h-4 text-slate-500 shrink-0" />
                <span className="text-slate-400">Due:</span>
                <span className="text-slate-300">{tenant.due_date}</span>
              </div>
            )}
            {tenant.emergency_contact_name && (
              <div className="flex items-center gap-3 text-sm">
                <span className="text-slate-400">Emergency:</span>
                <span className="text-slate-300">{tenant.emergency_contact_name}</span>
                {tenant.emergency_contact_phone && (
                  <span className="text-slate-400">({tenant.emergency_contact_phone})</span>
                )}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}