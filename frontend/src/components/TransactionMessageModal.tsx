import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X, Smartphone, User, Phone, DollarSign, Receipt,
  Calendar, Building2, Hash, ExternalLink, Copy, CheckCircle2,
} from "lucide-react";
import { Card } from "./ui";

interface Props {
  paymentId: string | null;
  onClose: () => void;
}

interface MessageData {
  full_message: string;
  customer_name: string;
  phone: string;
  amount: number;
  receipt: string;
  transaction_date: string;
  raw: Record<string, any>;
}

export default function TransactionMessageModal({ paymentId, onClose }: Props) {
  const [data, setData] = useState<MessageData | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!paymentId) return;
    setLoading(true);
    fetch(`/api/v1/payments/${paymentId}/message`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("rental_token")}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error("No M-Pesa data");
        return r.json();
      })
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [paymentId]);

  const copyMessage = () => {
    if (!data?.full_message) return;
    navigator.clipboard.writeText(data.full_message);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!paymentId) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[9999] bg-black/60 backdrop-blur-sm flex items-start justify-center pt-10 pb-10 overflow-y-auto"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.97 }}
          transition={{ type: "spring", stiffness: 400, damping: 35 }}
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-md mx-4 rounded-2xl border border-slate-700/50 bg-slate-900/95 backdrop-blur-xl shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                <Smartphone className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <span className="text-sm font-semibold text-white">M-Pesa Transaction</span>
            </div>
            <div className="flex items-center gap-1">
              {data && (
                <button onClick={copyMessage}
                  className="w-7 h-7 rounded-lg bg-slate-800 flex items-center justify-center hover:bg-slate-700 transition">
                  {copied
                    ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    : <Copy className="w-3.5 h-3.5 text-slate-400" />
                  }
                </button>
              )}
              <button onClick={onClose} className="w-7 h-7 rounded-lg bg-slate-800 flex items-center justify-center hover:bg-slate-700 transition">
                <X className="w-3.5 h-3.5 text-slate-400" />
              </button>
            </div>
          </div>

          {loading ? (
            <div className="p-12 text-center text-slate-500">Loading transaction details…</div>
          ) : !data ? (
            <div className="p-12 text-center">
              <Smartphone className="w-12 h-12 text-slate-700 mx-auto mb-3" />
              <div className="text-slate-400 text-sm font-medium mb-1">No M-Pesa Data</div>
              <div className="text-xs text-slate-600">This payment was not made via M-Pesa or the callback data is not available.</div>
            </div>
          ) : (
            <div className="p-4 space-y-3">
              {/* Customer Identity */}
              <Card className="p-4 border-emerald-500/30 bg-emerald-500/5">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-emerald-500/15 flex items-center justify-center">
                    <User className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div className="flex-1">
                    <div className="text-base font-bold text-white">{data.customer_name}</div>
                    <div className="flex items-center gap-1.5 text-xs text-slate-400">
                      <Phone className="w-3 h-3" />
                      {data.phone}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] text-slate-500">Amount</div>
                    <div className="text-lg font-bold text-emerald-400">
                      KES {data.amount.toLocaleString()}
                    </div>
                  </div>
                </div>
              </Card>

              {/* Transaction Details */}
              <Card className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Receipt className="w-3.5 h-3.5 text-sky-400" />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-sky-400">
                    Transaction Receipt
                  </span>
                </div>
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <Hash className="w-3 h-3" />
                      Receipt No
                    </div>
                    <span className="text-xs font-mono font-medium text-slate-200">{data.receipt || "—"}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <Calendar className="w-3 h-3" />
                      Date & Time
                    </div>
                    <span className="text-xs font-medium text-slate-200">{data.transaction_date}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <Building2 className="w-3 h-3" />
                      Business Code
                    </div>
                    <span className="text-xs font-mono font-medium text-slate-200">
                      {data.raw.BusinessShortCode || data.raw.BusinessShortCode || "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <DollarSign className="w-3 h-3" />
                      Transaction Type
                    </div>
                    <span className="text-xs font-medium text-slate-200">
                      {data.raw.TransactionType || "—"}
                    </span>
                  </div>
                  {data.raw.BillRefNumber && (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-xs text-slate-400">
                        <ExternalLink className="w-3 h-3" />
                        Account Ref
                      </div>
                      <span className="text-xs font-mono font-medium text-slate-200">{data.raw.BillRefNumber}</span>
                    </div>
                  )}
                  {data.raw.OrgAccountBalance !== undefined && (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-xs text-slate-400">
                        <Building2 className="w-3 h-3" />
                        Org Balance
                      </div>
                      <span className="text-xs font-medium text-emerald-400">
                        KES {Number(data.raw.OrgAccountBalance).toLocaleString()}
                      </span>
                    </div>
                  )}
                </div>
              </Card>

              {/* Full Message Block */}
              <Card className="p-4 border-slate-700/50">
                <div className="flex items-center gap-2 mb-2">
                  <Smartphone className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
                    Full Transaction Message
                  </span>
                </div>
                <div className="bg-slate-950 rounded-xl p-3 border border-slate-800">
                  <pre className="text-[11px] text-slate-300 font-mono leading-relaxed whitespace-pre-wrap">
                    {data.full_message}
                  </pre>
                </div>
              </Card>

              {/* Raw JSON (collapsible) */}
              <details className="group">
                <summary className="text-[10px] text-slate-600 cursor-pointer hover:text-slate-400 transition select-none">
                  Raw callback data
                </summary>
                <pre className="mt-2 text-[9px] text-slate-600 font-mono leading-relaxed overflow-x-auto max-h-40 overflow-y-auto">
                  {JSON.stringify(data.raw, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
