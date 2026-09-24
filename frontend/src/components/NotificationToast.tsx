import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Bell, DollarSign, Building2 } from "lucide-react";
import type { PaymentNotification } from "../lib/notifications";

interface ToastItem {
  id: string;
  notification: PaymentNotification;
  dismissed: boolean;
}

interface Props {
  /** Push a new notification into the toast stack */
  onPush: (cb: (n: PaymentNotification) => void) => void;
  /** Called when user clicks a toast — opens tenant detail */
  onTenantClick: (tenantId: string) => void;
}

export default function NotificationToast({ onPush, onTenantClick }: Props) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    onPush((n: PaymentNotification) => {
      const item: ToastItem = { id: crypto.randomUUID(), notification: n, dismissed: false };
      setToasts((prev) => [item, ...prev].slice(0, 5)); // keep max 5
      // Auto-dismiss after 8 seconds
      setTimeout(() => {
        setToasts((prev) => prev.map((t) => (t.id === item.id ? { ...t, dismissed: true } : t)));
        // Remove from DOM after animation
        setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== item.id));
        }, 300);
      }, 8000);
    });
  }, [onPush]);

  return (
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 w-96 pointer-events-none">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, x: 100, scale: 0.9 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 100, scale: 0.9 }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            className="pointer-events-auto cursor-pointer"
            onClick={() => {
              setToasts((prev) => prev.filter((item) => item.id !== t.id));
              onTenantClick(t.notification.tenant_id);
            }}
          >
            <div className="relative rounded-xl border border-emerald-500/30 bg-slate-900/95 backdrop-blur-xl p-3 shadow-2xl shadow-emerald-500/10 overflow-hidden">
              {/* Green accent bar */}
              <div className="absolute left-0 top-0 bottom-0 w-1 bg-emerald-400 rounded-l-xl" />

              <div className="flex items-start gap-3">
                {/* Icon */}
                <div className="w-9 h-9 rounded-lg bg-emerald-500/15 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
                      Payment Received
                    </span>
                    <span className="text-[10px] text-slate-600">·</span>
                    <span className="text-[10px] text-slate-500">
                      {t.notification.payment_method_label}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-white leading-snug">
                    {t.notification.message}
                  </p>
                  <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-500">
                    <Building2 className="w-2.5 h-2.5" />
                    <span>{t.notification.unit_number}</span>
                    <span>·</span>
                    <span>{t.notification.tenant_name}</span>
                    <span>·</span>
                    <span className="capitalize">{t.notification.method}</span>
                  </div>
                </div>

                {/* Close button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setToasts((prev) => prev.filter((item) => item.id !== t.id));
                  }}
                  className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center hover:bg-slate-700 transition flex-shrink-0 mt-0.5"
                >
                  <X className="w-3 h-3 text-slate-400" />
                </button>
              </div>

              {/* Progress bar */}
              <motion.div
                initial={{ width: "100%" }}
                animate={{ width: "0%" }}
                transition={{ duration: 8, ease: "linear" }}
                className="absolute bottom-0 left-0 h-0.5 bg-emerald-500/30 rounded-full"
              />
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
