import { motion, AnimatePresence } from "framer-motion";
import {
  X, DollarSign, Calendar, CreditCard,
  Building2, Phone, Clock, Home, CheckCircle2,
  AlertTriangle, MessageCircle, PhoneCall, Wifi,
  WifiOff, Hash,
} from "lucide-react";

interface TenantDetailProps {
  open: boolean;
  onClose: () => void;
  tenant: {
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
  } | null;
}

const money = (n: number) => `KES ${(n ?? 0).toLocaleString("en-KE")}`;

export default function TenantDetail({ open, onClose, tenant }: TenantDetailProps) {
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

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* ── Backdrop ── */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50"
            onClick={onClose}
          />

          {/* ── Modal ── */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 30 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 30 }}
            transition={{ type: "spring", stiffness: 280, damping: 24 }}
            className="fixed inset-4 md:inset-auto md:top-1/2 md:left-1/2 md:-translate-x-1/2 md:-translate-y-1/2 md:w-full md:max-w-lg z-50 overflow-hidden"
          >
            <div className="bg-[#0d1929] border border-slate-700/60 rounded-2xl shadow-2xl shadow-black/60 overflow-hidden flex flex-col max-h-[90vh]">

              {/* ── Coloured Header Band ── */}
              <div className={`relative px-5 pt-5 pb-4 border-b border-slate-800 ${statusColor.bg}`}>
                {/* Close */}
                <button
                  onClick={onClose}
                  className="absolute top-4 right-4 w-8 h-8 rounded-lg bg-slate-800/80 hover:bg-slate-700 flex items-center justify-center transition"
                >
                  <X className="w-4 h-4 text-slate-400" />
                </button>

                <div className="flex items-center gap-4">
                  {/* Avatar circle */}
                  <div className={`w-14 h-14 rounded-2xl flex items-center justify-center text-xl font-black text-white border-2 ${statusColor.border} ${statusColor.bg}`}>
                    {tenant.tenant_name?.[0]?.toUpperCase() ?? (isVacant ? "·" : "?")}
                  </div>

                  <div className="flex-1 min-w-0">
                    <h2 className="text-lg font-bold text-white truncate leading-tight">
                      {isVacant ? "Vacant Room" : (tenant.tenant_name ?? "Unknown")}
                    </h2>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span className={`text-sm font-semibold ${statusColor.text}`}>
                        Room {tenant.unit_number}
                      </span>
                      {tenant.hostel_name && (
                        <>
                          <span className="text-slate-600">·</span>
                          <span className="text-xs text-slate-400 truncate">{tenant.hostel_name}</span>
                        </>
                      )}
                    </div>

                    {/* Status pill */}
                    <div className={`inline-flex items-center gap-1.5 mt-2 px-2.5 py-1 rounded-full text-[11px] font-bold border ${statusColor.bg} ${statusColor.text} ${statusColor.border}`}>
                      {isPaid   && <><CheckCircle2 className="w-3 h-3" /> PAID</>}
                      {isUnpaid && <><AlertTriangle className="w-3 h-3" /> UNPAID</>}
                      {isVacant && <><Home className="w-3 h-3" /> VACANT — Ready for Move-in</>}
                    </div>
                  </div>
                </div>
              </div>

              {/* ── Scrollable body ── */}
              <div className="overflow-y-auto flex-1">

                {/* ── Balance Hero (only for occupied) ── */}
                {!isVacant && (
                  <div className={`mx-5 mt-4 rounded-2xl p-4 border ${statusColor.border} ${statusColor.bg} shadow-lg ${statusColor.glow}`}>
                    <div className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">
                      {isUnpaid ? "Outstanding Balance" : "Amount Paid"}
                    </div>
                    <div className={`text-3xl font-black ${statusColor.text} mb-0.5`}>
                      {isUnpaid ? money(bal > 0 ? bal : rent) : money(paid > 0 ? paid : rent)}
                    </div>
                    <div className="text-xs text-slate-500">
                      Monthly rent: {money(rent)}
                      {tenant.due_date && ` · Due: ${tenant.due_date}`}
                    </div>
                  </div>
                )}

                {/* ── Details Grid ── */}
                <div className="px-5 pt-4 pb-2 grid grid-cols-2 gap-3">
                  <Field icon={<Hash className="w-3.5 h-3.5" />}  label="Room"      value={tenant.unit_number ?? "—"} />
                  <Field icon={<Building2 className="w-3.5 h-3.5" />} label="Hostel" value={tenant.hostel_name ?? "—"} />
                  <Field icon={<CreditCard className="w-3.5 h-3.5" />} label="Rent / Month" value={rent > 0 ? money(rent) : "—"} />
                  <Field icon={<Calendar className="w-3.5 h-3.5" />} label="Due Date" value={tenant.due_date ?? "—"} />
                  {tenant.duration_months != null && (
                    <Field icon={<Clock className="w-3.5 h-3.5" />} label="Tenure" value={`${tenant.duration_months} months`} />
                  )}
                  {phone && (
                    <Field icon={<Phone className="w-3.5 h-3.5" />} label="Phone" value={phone} />
                  )}
                  {tenant.invoice_status && (
                    <Field icon={<DollarSign className="w-3.5 h-3.5" />} label="Invoice" value={tenant.invoice_status.toUpperCase()} />
                  )}
                  {tenant.id_number && (
                    <Field icon={<Hash className="w-3.5 h-3.5" />} label="ID Number" value={tenant.id_number} />
                  )}
                </div>

                {/* ── Emergency / Email ── */}
                {(tenant.email || tenant.emergency_contact_name) && (
                  <div className="px-5 pb-4">
                    <div className="text-[10px] uppercase tracking-widest text-slate-600 mb-2 mt-1">
                      Additional Info
                    </div>
                    <div className="space-y-1 text-xs text-slate-400 bg-slate-800/40 rounded-xl p-3 border border-slate-700/30">
                      {tenant.email && <div>Email: {tenant.email}</div>}
                      {tenant.emergency_contact_name && (
                        <div>
                          Emergency: {tenant.emergency_contact_name}
                          {tenant.emergency_contact_phone && ` · ${tenant.emergency_contact_phone}`}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* ── Action Buttons (only for occupied) ── */}
              {!isVacant && (
                <div className="px-5 py-4 border-t border-slate-800 flex gap-3">
                  {waLink ? (
                    <a
                      href={waLink}
                      target="_blank"
                      rel="noreferrer"
                      className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm transition-all shadow-lg shadow-emerald-500/20"
                    >
                      <MessageCircle className="w-4 h-4 fill-slate-950" />
                      WhatsApp
                    </a>
                  ) : (
                    <button
                      disabled
                      className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-slate-700/50 text-slate-500 font-bold text-sm cursor-not-allowed"
                    >
                      <WifiOff className="w-4 h-4" />
                      No WA
                    </button>
                  )}
                  {callLink ? (
                    <a
                      href={callLink}
                      className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 font-bold text-sm border border-sky-500/30 transition-all"
                    >
                      <PhoneCall className="w-4 h-4" />
                      Call
                    </a>
                  ) : (
                    <button
                      disabled
                      className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-slate-700/50 text-slate-500 font-bold text-sm border border-slate-700/30 cursor-not-allowed"
                    >
                      <Wifi className="w-4 h-4" />
                      No phone
                    </button>
                  )}
                </div>
              )}

              {/* Vacant CTA */}
              {isVacant && (
                <div className="px-5 py-4 border-t border-slate-800">
                  <div className="w-full py-2.5 rounded-xl bg-sky-500/10 border border-sky-500/25 text-sky-300 font-semibold text-sm text-center">
                    Room available — assign a tenant to activate
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function Field({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="bg-slate-800/40 rounded-xl p-3 border border-slate-700/30">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">
        {icon} {label}
      </div>
      <div className="text-sm font-semibold text-slate-200 truncate">{value}</div>
    </div>
  );
}
