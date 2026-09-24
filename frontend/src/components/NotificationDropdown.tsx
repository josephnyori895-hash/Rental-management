import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Bell, X, Smartphone, Banknote, Wallet, CreditCard, DollarSign,
  CheckCircle2, Clock,
} from "lucide-react";
import type { PaymentNotification } from "../lib/notifications";
import { getToken } from "../lib/api";

/* ─── Constants ─── */

const METHOD_LABEL: Record<string, string> = {
  mpesa: "M-Pesa", airtel: "Airtel Money", bank: "Bank Transfer",
  equity: "Equity Bank", cash: "Cash", card: "Card",
};

const METHOD_ICON: Record<string, React.ReactNode> = {
  mpesa: <Smartphone className="w-3.5 h-3.5" />,
  airtel: <Smartphone className="w-3.5 h-3.5" />,
  bank: <Banknote className="w-3.5 h-3.5" />,
  equity: <Banknote className="w-3.5 h-3.5" />,
  cash: <Wallet className="w-3.5 h-3.5" />,
  card: <CreditCard className="w-3.5 h-3.5" />,
};

const METHOD_COLOR: Record<string, string> = {
  mpesa: "bg-emerald-500/15 text-emerald-400",
  airtel: "bg-amber-500/15 text-amber-400",
  bank: "bg-sky-500/15 text-sky-400",
  equity: "bg-purple-500/15 text-purple-400",
  cash: "bg-lime-500/15 text-lime-400",
  card: "bg-violet-500/15 text-violet-400",
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 2) return `${days}d ago`;
  return `${days}d ago`;
}

function dateLabel(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
  if (sameDay(d, today)) return "Today";
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (sameDay(d, yesterday)) return "Yesterday";
  return d.toLocaleDateString("en-KE", { month: "short", day: "numeric" });
}

/* ─── Props ─── */

interface Props {
  open: boolean;
  onClose: () => void;
  onTenantClick: (tenantId: string) => void;
  unreadCount: number;
  onMarkRead: () => void;
}

export default function NotificationDropdown({
  open, onClose, onTenantClick, unreadCount, onMarkRead,
}: Props) {
  const [notifications, setNotifications] = useState<PaymentNotification[]>([]);
  const [loading, setLoading] = useState(false);
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const dropdownRef = useRef<HTMLDivElement>(null);

  /* Click outside to close */
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    setTimeout(() => document.addEventListener("mousedown", handler), 0);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, onClose]);

  /* Mark all current as read when dropdown opens */
  useEffect(() => {
    if (!open) return;
    // Mark current notifications as read
    setReadIds((prev) => {
      const next = new Set(prev);
      notifications.forEach((n) => next.add(n.id));
      return next;
    });
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  /* Fetch initial history */
  useEffect(() => {
    if (!open) return;
    const token = getToken();
    if (!token) return;

    setLoading(true);
    const since = new Date(Date.now() - 7 * 86400000).toISOString();
    fetch(`/api/v1/payments/notifications?since=${encodeURIComponent(since)}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => {
        const items = (data.notifications || []) as PaymentNotification[];
        setNotifications(items);
        // Auto-mark these as read too
        setReadIds((prev) => {
          const next = new Set(prev);
          items.forEach((n) => next.add(n.id));
          return next;
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));

    /* Listen for live notifications from polling */
    const handler = (e: Event) => {
      const n = (e as CustomEvent).detail as PaymentNotification;
      setNotifications((prev) => {
        if (prev.some((p) => p.id === n.id)) return prev;
        return [n, ...prev].slice(0, 50);
      });
    };
    window.addEventListener("new-notification", handler);
    return () => window.removeEventListener("new-notification", handler);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  /* Mark one notification as read */
  const markRead = useCallback((id: string) => {
    setReadIds((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  }, []);

  const handleClick = useCallback((n: PaymentNotification) => {
    markRead(n.id);
    onTenantClick(n.tenant_id);
    onClose();
  }, [markRead, onTenantClick, onClose]);

  /* Group by date */
  const groups = notifications.reduce<{ label: string; items: PaymentNotification[] }[]>((acc, n) => {
    const label = dateLabel(n.paid_at);
    let g = acc.find((g) => g.label === label);
    if (!g) {
      g = { label, items: [] };
      acc.push(g);
    }
    g.items.push(n);
    return acc;
  }, []);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={dropdownRef}
          initial={{ opacity: 0, y: -6, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -6, scale: 0.95 }}
          transition={{ type: "spring", stiffness: 400, damping: 30 }}
          className="absolute left-0 top-full mt-1.5 w-[28rem] rounded-xl border border-slate-700/60 bg-slate-900/95 backdrop-blur-2xl shadow-2xl shadow-black/50 overflow-hidden z-50"
          style={{ transformOrigin: "top left" }}
        >
          {/* ── Header ── */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800/80">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-slate-800 flex items-center justify-center">
                <Bell className="w-3.5 h-3.5 text-slate-400" />
              </div>
              <span className="text-sm font-semibold text-white">Notifications</span>
              {unreadCount > 0 && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold text-emerald-400 bg-emerald-500/15">
                  {unreadCount} new
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              {unreadCount > 0 && (
                <button
                  onClick={() => { onMarkRead(); setReadIds((prev) => {
                    const next = new Set(prev);
                    notifications.forEach((n) => next.add(n.id));
                    return next;
                  }); }}
                  className="text-[11px] text-slate-500 hover:text-emerald-400 px-2 py-1 rounded-lg hover:bg-slate-800/60 transition"
                >
                  Mark all read
                </button>
              )}
              <button onClick={onClose}
                className="w-6 h-6 rounded-lg bg-slate-800 hover:bg-slate-700 flex items-center justify-center transition">
                <X className="w-3 h-3 text-slate-400" />
              </button>
            </div>
          </div>

          {/* ── Body ── */}
          <div className="max-h-[28rem] overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-12 gap-2">
                <div className="w-4 h-4 border-2 border-emerald-400/30 border-t-emerald-400 rounded-full animate-spin" />
                <span className="text-xs text-slate-500">Loading...</span>
              </div>
            ) : notifications.length === 0 ? (
              <div className="py-14 text-center">
                <div className="w-12 h-12 mx-auto rounded-full bg-slate-800/60 flex items-center justify-center mb-3">
                  <Bell className="w-6 h-6 text-slate-600" />
                </div>
                <div className="text-sm font-medium text-slate-400">No notifications</div>
                <div className="text-[11px] text-slate-600 mt-1">Payment alerts will show up here</div>
              </div>
            ) : (
              <div>
                {groups.map((group) => (
                  <div key={group.label}>
                    {/* Date header */}
                    <div className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 bg-slate-900/40">
                      {group.label}
                    </div>

                    {group.items.map((n) => {
                      const isRead = readIds.has(n.id);
                      const bal = n.invoice_balance || 0;
                      return (
                        <button
                          key={n.id}
                          onClick={() => handleClick(n)}
                          onMouseEnter={() => markRead(n.id)}
                          className={`w-full flex items-start gap-3 px-4 py-3 text-left transition-all duration-150
                            ${isRead
                              ? "bg-transparent hover:bg-slate-800/30"
                              : "bg-emerald-500/[0.03] hover:bg-emerald-500/[0.06]"
                            }`}
                        >
                          {/* Unread dot indicator */}
                          <div className="pt-1.5 w-2 shrink-0">
                            {!isRead && (
                              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]" />
                            )}
                          </div>

                          {/* Method icon */}
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${METHOD_COLOR[n.method] || "bg-slate-700 text-slate-400"}`}>
                            {METHOD_ICON[n.method] || <DollarSign className="w-3.5 h-3.5" />}
                          </div>

                          {/* Content */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-2">
                              <span className={`text-sm truncate ${isRead ? "text-slate-300" : "text-white font-medium"}`}>
                                {n.tenant_name}
                              </span>
                              <span className="text-[10px] text-slate-500 shrink-0 font-mono">
                                {timeAgo(n.paid_at)}
                              </span>
                            </div>

                            <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                              <span className={`text-xs font-semibold ${isRead ? "text-emerald-400" : "text-emerald-300"}`}>
                                KES {n.amount.toLocaleString()}
                              </span>
                              <span className="text-[10px] text-slate-600">·</span>
                              <span className="text-[10px] text-slate-500">{METHOD_LABEL[n.method] || n.method}</span>
                              <span className="text-[10px] text-slate-600">·</span>
                              <span className="text-[10px] text-slate-500">{n.unit_number}</span>
                            </div>

                            {/* Balance status */}
                            {bal <= 0 ? (
                              <div className="flex items-center gap-1 mt-1">
                                <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400/70" />
                                <span className="text-[10px] text-emerald-400/70">Paid in full</span>
                              </div>
                            ) : (
                              <div className="flex items-center gap-1 mt-0.5">
                                <Clock className="w-2.5 h-2.5 text-amber-400/70" />
                                <span className="text-[10px] text-amber-400/70">
                                  Balance: KES {bal.toLocaleString()}
                                </span>
                              </div>
                            )}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Footer ── */}
          <div className="border-t border-slate-800/80 px-4 py-2.5 flex justify-center">
            <button
              onClick={() => { window.dispatchEvent(new CustomEvent("navigate", { detail: "payments" })); onClose(); }}
              className="text-[11px] text-slate-500 hover:text-emerald-400 transition"
            >
              View all payments →
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
