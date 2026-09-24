import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X, Phone, MapPin, Calendar, DollarSign, CreditCard,
  Building2, User, ArrowLeft, Receipt, CheckCircle2,
  AlertTriangle, Clock, Banknote, Smartphone, Wallet,
  ShieldCheck, RotateCcw, MessageSquare, FileText, Upload,
} from "lucide-react";
import { getInvoiceDetail } from "../lib/api";
import { Card, Badge, money } from "./ui";
import TransactionMessageModal from "./TransactionMessageModal";

interface Props {
  tenantId: string | null;
  onClose: () => void;
}

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function formatPeriod(period: string | null): string {
  if (!period) return "—";
  // period format: "2026-07-01 - 2026-07-31"
  const start = period.split(" - ")[0];
  if (!start) return period;
  const parts = start.split("-");
  if (parts.length < 3) return period;
  const month = parseInt(parts[1], 10);
  const year = parts[0];
  return `${MONTHS[month - 1] || parts[1]} ${year}`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  const parts = dateStr.split("-");
  if (parts.length < 3) return dateStr;
  const month = parseInt(parts[1], 10);
  const year = parts[0];
  return `${MONTHS[month - 1] || parts[1]} ${year}`;
}

interface TenantDetail {
  id: string;
  full_name: string;
  id_number: string | null;
  phone: string | null;
  whatsapp_phone: string | null;
  mpesa_phone: string | null;
  email: string | null;
  created_at: string | null;
  current_lease: {
    id: string;
    unit_number: string;
    monthly_rent: number;
    deposit_amount: number;
    start_date: string;
    duration_months: number;
    status: string;
  } | null;
  deposit: {
    amount: number;
    paid: number;
    balance: number;
    status: "paid" | "partial" | "pending" | "refunded";
    refund: {
      amount: number;
      method: string;
      reason: string | null;
      refunded_at: string;
    } | null;
  } | null;
  invoices: any[];
  payments: any[];
  total_paid: number;
  total_invoiced: number;
}

function methodIcon(method: string) {
  switch (method) {
    case "mpesa": return <Smartphone className="w-3 h-3" />;
    case "airtel": return <Smartphone className="w-3 h-3" />;
    case "bank": return <Banknote className="w-3 h-3" />;
    case "equity": return <Banknote className="w-3 h-3" />;
    case "cash": return <Wallet className="w-3 h-3" />;
    case "card": return <CreditCard className="w-3 h-3" />;
    default: return <DollarSign className="w-3 h-3" />;
  }
}

function methodColor(method: string) {
  switch (method) {
    case "mpesa": return "text-emerald-400 bg-emerald-500/10";
    case "airtel": return "text-amber-400 bg-amber-500/10";
    case "bank": return "text-sky-400 bg-sky-500/10";
    case "equity": return "text-purple-400 bg-purple-500/10";
    case "cash": return "text-lime-400 bg-lime-500/10";
    case "card": return "text-violet-400 bg-violet-500/10";
    default: return "text-slate-400 bg-slate-500/10";
  }
}

function methodLabel(method: string) {
  const labels: Record<string, string> = {
    mpesa: "M-Pesa", airtel: "Airtel Money", bank: "Bank Transfer",
    equity: "Equity Bank", cash: "Cash", card: "Card",
  };
  return labels[method] || method;
}

export default function TenantDetailModal({ tenantId, onClose }: Props) {
  const [detail, setDetail] = useState<TenantDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [messagePaymentId, setMessagePaymentId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (!tenantId) return;
    setLoading(true);
    Promise.all([
      fetch(`/api/v1/tenants/${tenantId}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("rental_token")}` },
      }).then((r) => r.json()),
      fetch(`/api/v1/documents/list?tenant_id=${tenantId}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("rental_token")}` },
      }).then((r) => r.json()).then(d => setDocuments(d.documents || [])).catch(() => {}),
    ])
      .then(([detail]) => setDetail(detail))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [tenantId]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !tenantId) return;
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    form.append("category", "other");
    form.append("tenant_id", tenantId);
    try {
      const r = await fetch("/api/v1/documents/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("rental_token")}` },
        body: form,
      });
      const doc = await r.json();
      setDocuments((prev) => [doc, ...prev]);
    } catch {}
    setUploading(false);
  };

  if (!tenantId) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[9998] bg-black/60 backdrop-blur-sm flex items-start justify-center pt-10 pb-10 overflow-y-auto"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.97 }}
          transition={{ type: "spring", stiffness: 400, damping: 35 }}
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-2xl mx-4 rounded-2xl border border-slate-700/50 bg-slate-900/95 backdrop-blur-xl shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <button onClick={onClose} className="w-7 h-7 rounded-lg bg-slate-800 flex items-center justify-center hover:bg-slate-700 transition">
                <ArrowLeft className="w-3.5 h-3.5 text-slate-400" />
              </button>
              <span className="text-sm font-semibold text-white">Tenant Details</span>
            </div>
            <button onClick={onClose} className="w-7 h-7 rounded-lg bg-slate-800 flex items-center justify-center hover:bg-slate-700 transition">
              <X className="w-3.5 h-3.5 text-slate-400" />
            </button>
          </div>

          {loading ? (
            <div className="p-12 text-center text-slate-500">Loading tenant details…</div>
          ) : !detail ? (
            <div className="p-12 text-center text-rose-400">Failed to load tenant details</div>
          ) : (
            <div className="p-4 space-y-4">
              {/* ── Tenant Identity Card ── */}
              <Card className="p-4">
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 rounded-xl bg-emerald-500/15 flex items-center justify-center text-emerald-400 font-bold text-lg">
                    {detail.full_name?.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="flex-1">
                    <h2 className="text-lg font-bold text-white">{detail.full_name}</h2>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-xs text-slate-400">
                      {detail.current_lease && (
                        <span className="flex items-center gap-1">
                          <Building2 className="w-3 h-3" />
                          House {detail.current_lease.unit_number}
                        </span>
                      )}
                      {detail.phone && (
                        <span className="flex items-center gap-1">
                          <Phone className="w-3 h-3" />
                          {detail.phone}
                        </span>
                      )}
                      {detail.mpesa_phone && detail.mpesa_phone !== detail.phone && (
                        <span className="flex items-center gap-1 text-emerald-400">
                          <Smartphone className="w-3 h-3" />
                          {detail.mpesa_phone}
                        </span>
                      )}
                      {detail.whatsapp_phone && (
                        <span className="flex items-center gap-1 text-sky-400">
                          <MessageSquare className="w-3 h-3" />
                          {detail.whatsapp_phone}
                        </span>
                      )}
                      {detail.current_lease && (
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          Since {formatDate(detail.current_lease.start_date)}
                        </span>
                      )}
                    </div>
                  </div>
                  {detail.current_lease && (
                    <div className="text-right">
                      <div className="text-xs text-slate-500">Monthly Rent</div>
                      <div className="text-lg font-bold text-emerald-400">
                        KES {money(detail.current_lease.monthly_rent)}
                      </div>
                      <Badge color={detail.current_lease.status === "active" ? "emerald" : "slate"}>
                        {detail.current_lease.status}
                      </Badge>
                    </div>
                  )}
                </div>
              </Card>

              {/* ── DEPOSIT STATUS ── */}
              {detail.deposit && (
                <Card className="p-4 border-slate-700/50">
                  <div className="flex items-center gap-2 mb-3">
                    <ShieldCheck className="w-3.5 h-3.5 text-sky-400" />
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-sky-400">
                      Security Deposit
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-lg font-bold text-white">
                        KES {money(detail.deposit.amount)}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge color={
                          detail.deposit.status === "paid" ? "emerald" :
                          detail.deposit.status === "refunded" ? "sky" :
                          detail.deposit.status === "partial" ? "amber" : "slate"
                        }>
                          {detail.deposit.status === "paid" ? "Held" :
                           detail.deposit.status === "refunded" ? "Refunded" :
                           detail.deposit.status === "partial" ? "Partial" : "Pending"}
                        </Badge>
                        {detail.deposit.paid > 0 && (
                          <span className="text-[10px] text-slate-500">
                            · {detail.deposit.status === "refunded" ? "Refunded" : "Paid"}: KES {money(detail.deposit.paid)}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-right">
                      {detail.deposit.refund && (
                        <div className="flex flex-col items-end gap-1">
                          <div className="flex items-center gap-1 text-[10px] text-sky-400">
                            <RotateCcw className="w-3 h-3" />
                            Refunded KES {money(detail.deposit.refund.amount)}
                          </div>
                          <div className="text-[9px] text-slate-600">
                            via {detail.deposit.refund.method} · {detail.deposit.refund.refunded_at?.slice(0, 10)}
                          </div>
                          {detail.deposit.refund.reason && (
                            <div className="text-[9px] text-slate-600 italic">
                              "{detail.deposit.refund.reason}"
                            </div>
                          )}
                        </div>
                      )}
                      {detail.deposit.balance > 0 && detail.deposit.status !== "refunded" && (
                        <div className="text-[10px] text-amber-400">
                          Balance: KES {money(detail.deposit.balance)}
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              )}

              {/* ── LATEST TRANSACTION (highlighted) ── */}
              {detail.payments.length > 0 && (
                <Card className="p-4 border-emerald-500/30 bg-emerald-500/5">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
                      Latest Payment
                    </span>
                  </div>
                  {(() => {
                    const p = detail.payments[0];
                    const inv = detail.invoices.find((i) => i.id === p.invoice_id);
                    return (
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-lg font-bold text-white">
                            KES {money(p.amount)}
                          </div>
                          <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5">
                            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${methodColor(p.method)}`}>
                              {methodIcon(p.method)}
                              {methodLabel(p.method)}
                            </span>
                            {p.reference && <span className="font-mono text-[10px]">Ref: {p.reference}</span>}
                            <span>{p.paid_at?.slice(0, 10)}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {(p.method === "mpesa" || p.method === "airtel") && (
                            <button onClick={() => setMessagePaymentId(p.id)}
                              className="w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center hover:bg-emerald-500/15 hover:text-emerald-400 transition text-slate-500"
                              title="View transaction message">
                              <MessageSquare className="w-3 h-3" />
                            </button>
                          )}
                          {inv && (
                            <Badge color={inv.status === "paid" ? "emerald" : inv.status === "partial" ? "amber" : "rose"}>
                              {inv.status === "paid" ? "✅ Full Payment" : inv.status === "partial" ? "⚠ Partial" : "❌ Unpaid"}
                            </Badge>
                          )}
                        </div>
                      </div>
                    );
                  })()}
                </Card>
              )}

              {/* ── All Payments ── */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-1.5">
                    <Receipt className="w-3.5 h-3.5 text-emerald-400" />
                    Payment History
                    <span className="text-[10px] text-slate-500 font-normal">({detail.payments.length})</span>
                  </h3>
                  <div className="text-xs text-slate-400">
                    Total Paid: <span className="text-emerald-400 font-semibold">KES {money(detail.total_paid)}</span>
                  </div>
                </div>

                {detail.payments.length === 0 ? (
                  <div className="text-center py-8 text-slate-500 text-sm">No payments recorded</div>
                ) : (
                  <div className="space-y-1">
                    {detail.payments.map((p, i) => {
                      const isLatest = i === 0;
                      return (
                        <motion.div
                          key={p.id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: i * 0.02 }}
                          className={`flex items-center justify-between px-3 py-2.5 rounded-xl ${
                            isLatest
                              ? "bg-emerald-500/10 border border-emerald-500/20"
                              : "bg-slate-800/40 border border-slate-800"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${methodColor(p.method)}`}>
                              {methodIcon(p.method)}
                            </div>
                            <div>
                              <div className="text-sm font-medium text-slate-200">
                                KES {money(p.amount)}
                              </div>
                              <div className="flex items-center gap-2 text-[10px] text-slate-500">
                                <span className={`inline-flex items-center gap-0.5 capitalize ${methodColor(p.method).split(" ")[0]}`}>
                                  {methodLabel(p.method)}
                                </span>
                                {p.reference && (
                                  <>
                                    <span>·</span>
                                    <span className="font-mono">{p.reference}</span>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {(p.method === "mpesa" || p.method === "airtel") && (
                              <button onClick={() => setMessagePaymentId(p.id)}
                                className="w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center hover:bg-emerald-500/15 hover:text-emerald-400 transition text-slate-500"
                                title="View transaction message">
                                <MessageSquare className="w-3 h-3" />
                              </button>
                            )}
                            <div className="text-right">
                              <div className="text-[10px] text-slate-500">
                                {p.paid_at?.slice(0, 10)}
                              </div>
                              {isLatest && (
                                <div className="text-[9px] text-emerald-400 font-medium mt-0.5">Just now</div>
                              )}
                            </div>
                          </div>
                        </motion.div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* ── Invoices ── */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-1.5">
                    <Receipt className="w-3.5 h-3.5 text-sky-400" />
                    Invoices
                    <span className="text-[10px] text-slate-500 font-normal">({detail.invoices.length})</span>
                  </h3>
                </div>
                <div className="space-y-1">
                  {detail.invoices.map((inv, i) => (
                    <div key={inv.id} className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-800/40 border border-slate-800">
                      <div className="flex items-center gap-2">
                        <div className="text-xs font-bold text-slate-300 w-20">{formatPeriod(inv.period)}</div>
                        <Badge color={inv.status === "paid" ? "emerald" : inv.status === "partial" ? "amber" : inv.status === "overdue" ? "rose" : "slate"}>
                          {inv.status}
                        </Badge>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-medium text-white">KES {money(inv.amount)}</div>
                        {inv.balance > 0 && <div className="text-[10px] text-rose-400">Bal: KES {money(inv.balance)}</div>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* ── Documents ── */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-emerald-400" />
                    Documents
                    <span className="text-[10px] text-slate-500 font-normal">({documents.length})</span>
                  </h3>
                  <label className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 hover:bg-emerald-500/25 transition cursor-pointer">
                    <Upload className="w-3 h-3" />
                    {uploading ? "Uploading..." : "Upload"}
                    <input type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
                  </label>
                </div>
                {documents.length === 0 ? (
                  <div className="text-center py-6 text-slate-600 text-xs">No documents uploaded</div>
                ) : (
                  <div className="space-y-1">
                    {documents.map((d, i) => (
                      <a key={i} href={`/api/v1/documents/${d.id}/download`}
                        target="_blank" rel="noopener noreferrer"
                        className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-800/40 border border-slate-800 hover:border-emerald-500/30 transition">
                        <div className="flex items-center gap-2">
                          <FileText className="w-3.5 h-3.5 text-slate-500" />
                          <span className="text-xs text-slate-300">{d.original_name}</span>
                        </div>
                        <span className="text-[10px] text-slate-500">{d.category.replace("_", " ")}</span>
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </motion.div>
      </motion.div>
      <TransactionMessageModal paymentId={messagePaymentId} onClose={() => setMessagePaymentId(null)} />
    </AnimatePresence>
  );
}
