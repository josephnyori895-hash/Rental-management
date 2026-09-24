/**
 * Rental OS — Real-time payment notification polling
 *
 * Polls GET /api/v1/payments/notifications?since=<timestamp>
 * every N seconds and fires callbacks when new payments appear.
 */

import { getToken } from "./api";

export interface PaymentNotification {
  id: string;
  tenant_id: string;
  tenant_name: string;
  unit_number: string;
  amount: number;
  method: string;
  reference: string | null;
  paid_at: string;
  invoice_status: string;
  invoice_balance: number;
  message: string;
  payment_method_label: string;
}

interface PollResponse {
  notifications: PaymentNotification[];
  server_time: string;
}

type Callback = (n: PaymentNotification) => void;

/**
 * Starts polling the notifications endpoint.
 * Returns an unsubscribe function.
 */
export function startNotificationPolling(
  onNotification: Callback,
  intervalMs = 10000,
): () => void {
  let lastPoll: string | null = null;
  let timer: ReturnType<typeof setInterval> | null = null;
  let running = true;

  async function poll() {
    if (!running) return;
    const token = getToken();
    if (!token) return;

    const params = lastPoll ? `?since=${encodeURIComponent(lastPoll)}` : "";
    try {
      const res = await fetch(
        `/api/v1/payments/notifications${params}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!res.ok) return;
      const data: PollResponse = await res.json();
      lastPoll = data.server_time;
      for (const n of data.notifications) {
        onNotification(n);
      }
    } catch {
      // Silently retry on next interval
    }
  }

  // First poll immediately
  poll();
  timer = setInterval(poll, intervalMs);

  return () => {
    running = false;
    if (timer) clearInterval(timer);
  };
}
