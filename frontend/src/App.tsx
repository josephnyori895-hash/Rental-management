import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import Properties from "./pages/Properties";
import Tenants from "./pages/Tenants";
import Payments from "./pages/Payments";
import Maintenance from "./pages/Maintenance";
import Expenses from "./pages/Expenses";
import Reports from "./pages/Reports";
import BooksPage from "./pages/BooksPage";
import CalendarPage from "./pages/CalendarPage";
import HistoryPage from "./pages/HistoryPage";
import TenantPortal from "./pages/TenantPortal";
import Settings from "./pages/Settings";
import Enroll from "./pages/Enroll";
import TenantDetailPage from "./pages/TenantDetailPage";
import { getToken, decodeRole, clearToken } from "./lib/api";
import { startNotificationPolling, type PaymentNotification } from "./lib/notifications";
import NotificationToast from "./components/NotificationToast";
import NotificationDropdown from "./components/NotificationDropdown";
import TenantDetailModal from "./components/TenantDetailModal";
import Background from "./components/Background";
import LoginBackground from "./components/LoginBackground";

import {
  LayoutDashboard, Building2, Users, CreditCard, Wrench, Receipt,
  BarChart3, BookOpen, Calendar, History, UserCircle, Settings as Cog,
  LogOut, Menu, X, Zap, Bell, ChevronLeft,
} from "lucide-react";

type View =
  | "overview" | "properties" | "tenants" | "payments" | "maintenance"
  | "expenses" | "reports" | "books" | "calendar" | "history"
  | "portal" | "settings" | "enroll" | "tenant";

const NAV: { key: View; label: string; icon: React.ReactNode }[] = [
  { key: "overview", label: "Overview", icon: <LayoutDashboard className="w-4 h-4" /> },
  { key: "properties", label: "Properties", icon: <Building2 className="w-4 h-4" /> },
  { key: "tenants", label: "Tenants", icon: <Users className="w-4 h-4" /> },
  { key: "payments", label: "Payments", icon: <CreditCard className="w-4 h-4" /> },
  { key: "maintenance", label: "Maintenance", icon: <Wrench className="w-4 h-4" /> },
  { key: "expenses", label: "Expenses", icon: <Receipt className="w-4 h-4" /> },
  { key: "reports", label: "Reports", icon: <BarChart3 className="w-4 h-4" /> },
  { key: "books", label: "Books", icon: <BookOpen className="w-4 h-4" /> },
  { key: "calendar", label: "Calendar", icon: <Calendar className="w-4 h-4" /> },
  { key: "history", label: "History", icon: <History className="w-4 h-4" /> },
  { key: "portal", label: "Tenant Portal", icon: <UserCircle className="w-4 h-4" /> },
  { key: "enroll", label: "Enroll", icon: <Users className="w-4 h-4" /> },
  { key: "settings", label: "Settings", icon: <Cog className="w-4 h-4" /> },
];

const pageVariants = {
  initial: { opacity: 0, y: 12, filter: "blur(4px)" },
  animate: { opacity: 1, y: 0, filter: "blur(0px)" },
  exit: { opacity: 0, y: -8, filter: "blur(4px)" },
};

const pageTransition = { duration: 0.3, ease: [0.22, 1, 0.36, 1] as const };

function PageWrapper({ children, viewKey }: { children: React.ReactNode; viewKey: string }) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={viewKey}
        variants={pageVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={pageTransition}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  const [token, setToken] = useState<string | null>(getToken());
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const role = token ? decodeRole() : null;

  useEffect(() => {
    if (token && role && role !== "owner") {
      clearToken();
      setToken(null);
    }
  }, [token, role]);

  const [view, setView] = useState<View>("overview");

  const [tenantDetailId, setTenantDetailId] = useState<string | null>(null);
  const [selectedTenant, setSelectedTenant] = useState<any>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifDropdownOpen, setNotifDropdownOpen] = useState(false);
  const [recentNotification, setRecentNotification] = useState<PaymentNotification | null>(null);
  const notificationCallbackRef = useRef<((n: PaymentNotification) => void) | null>(null);

  const onNotification = useCallback((n: PaymentNotification) => {
    setUnreadCount((c) => c + 1);
    setRecentNotification(n);
    window.dispatchEvent(new CustomEvent("new-notification", { detail: n }));
    if (notificationCallbackRef.current) {
      notificationCallbackRef.current(n);
    }
  }, []);

  const handleToastPush = useCallback((cb: (n: PaymentNotification) => void) => {
    notificationCallbackRef.current = cb;
  }, []);

  const handleTenantClick = useCallback((tenantId: string) => {
    setTenantDetailId(tenantId);
    setUnreadCount(0);
  }, []);

  const handleTenantPageView = useCallback((tenant: any) => {
    setSelectedTenant(tenant);
    setView("tenant");
    setUnreadCount(0);
  }, []);

  useEffect(() => {
    if (!token) return;
    const stop = startNotificationPolling(onNotification, 10000);
    return stop;
  }, [token, onNotification]);

  useEffect(() => {
    const onNavigate = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail === "payments") setView("payments");
      else if (detail === "tenants") setView("tenants");
      else if (detail === "reports") setView("reports");
      else if (detail === "books") setView("books");
    };
    const onOpenTenant = (e: Event) => {
      const tid = (e as CustomEvent).detail;
      setTenantDetailId(tid);
    };
    const onOpenTenantPage = (e: Event) => {
      const tenant = (e as CustomEvent).detail;
      setSelectedTenant(tenant);
      setView("tenant");
    };
    window.addEventListener("navigate", onNavigate);
    window.addEventListener("open-tenant", onOpenTenant);
    window.addEventListener("open-tenant-page", onOpenTenantPage);
    return () => {
      window.removeEventListener("navigate", onNavigate);
      window.removeEventListener("open-tenant", onOpenTenant);
      window.removeEventListener("open-tenant-page", onOpenTenantPage);
    };
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const { check } = await import("@tauri-apps/plugin-updater");
        const update = await check();
        if (update?.available) {
          await update.downloadAndInstall();
        }
      } catch { }
    })();
  }, []);

  if (!token) {
    return (
      <div className="min-h-screen bg-slate-950">
        <LoginBackground />
        <Login
          onLogin={(t) => {
            setToken(t);
            setView("overview");
          }}
        />
      </div>
    );
  }

  const logout = () => { clearToken(); setToken(null); };

  const goTo = (v: View) => { setView(v); setSidebarOpen(true); };

  const sidebarWidth = sidebarCollapsed ? 64 : 240;

  return (
    <div className="min-h-screen bg-slate-950 flex">
      <Background />

      <AnimatePresence>
        {sidebarOpen && (
          <motion.aside
            initial={{ x: -240, opacity: 0 }}
            animate={{ x: 0, opacity: 1, width: sidebarWidth }}
            exit={{ x: -240, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="shrink-0 bg-slate-900/80 backdrop-blur-2xl border-r border-white/[0.06] flex flex-col fixed h-full z-40"
          >
            <div className="px-3 py-4 flex items-center gap-2.5 border-b border-white/[0.04] h-14">
              <div className="w-8 h-8 shrink-0 rounded-lg bg-gradient-to-br from-emerald-400 to-sky-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                <Zap className="w-4 h-4 text-slate-950" />
              </div>
              <AnimatePresence>
                {!sidebarCollapsed && (
                  <motion.div
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    transition={{ duration: 0.15 }}
                    className="flex-1 overflow-hidden"
                  >
                    <div className="font-bold text-white text-sm leading-none">Rental OS</div>
                    <div className="text-[10px] text-slate-500 mt-0.5">v0.2.0 · Owner Console</div>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="relative shrink-0">
                <button
                  onClick={() => setNotifDropdownOpen((o) => !o)}
                  className="relative w-7 h-7 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] flex items-center justify-center transition group"
                  title="Notifications"
                >
                  <Bell className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-200 transition" />
                  {unreadCount > 0 && (
                    <motion.span
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-emerald-500 text-[8px] font-bold text-white flex items-center justify-center"
                    >
                      {unreadCount > 9 ? "9+" : unreadCount}
                    </motion.span>
                  )}
                </button>
                <NotificationDropdown
                  open={notifDropdownOpen}
                  onClose={() => setNotifDropdownOpen(false)}
                  onTenantClick={handleTenantClick}
                  unreadCount={unreadCount}
                  onMarkRead={() => setUnreadCount(0)}
                />
              </div>

              <button
                onClick={() => setSidebarCollapsed((c) => !c)}
                className="w-6 h-6 rounded-lg hover:bg-white/[0.08] flex items-center justify-center text-slate-500 hover:text-slate-300 transition shrink-0"
                title={sidebarCollapsed ? "Expand" : "Collapse"}
              >
                <ChevronLeft className={`w-3.5 h-3.5 transition-transform duration-300 ${sidebarCollapsed ? "rotate-180" : ""}`} />
              </button>
            </div>

            <nav className="flex-1 overflow-y-auto overflow-x-hidden px-2 py-3 space-y-0.5 scrollbar-thin">
              {NAV.map((n, i) => {
                const isActive = view === n.key;
                return (
                  <motion.button
                    key={n.key}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.03 }}
                    onClick={() => goTo(n.key)}
                    whileHover={{ x: 2 }}
                    className={`relative w-full flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm transition-all duration-200 group ${
                      isActive
                        ? "text-emerald-300"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {isActive && (
                      <motion.div
                        layoutId="active-nav"
                        className="absolute inset-0 rounded-lg bg-emerald-500/10 border border-emerald-500/15"
                        transition={{ type: "spring", stiffness: 400, damping: 30 }}
                      />
                    )}
                    {isActive && (
                      <motion.div
                        layoutId="active-nav-bar"
                        className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-full bg-emerald-400"
                        transition={{ type: "spring", stiffness: 400, damping: 30 }}
                      />
                    )}
                    <span className="relative z-10 shrink-0">{n.icon}</span>
                    <AnimatePresence>
                      {!sidebarCollapsed && (
                        <motion.span
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          transition={{ duration: 0.1 }}
                          className="relative z-10 text-[13px] font-medium whitespace-nowrap"
                        >
                          {n.label}
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </motion.button>
                );
              })}
            </nav>

            <div className="px-2 py-3 border-t border-white/[0.04]">
              <div className="flex items-center justify-between px-2 mb-2">
                <AnimatePresence>
                  {!sidebarCollapsed && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="text-[10px] uppercase tracking-wider text-slate-600"
                    >
                      Owner
                    </motion.span>
                  )}
                </AnimatePresence>
                <button onClick={() => setSidebarOpen(false)}
                  className="text-slate-600 hover:text-slate-300 transition">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <button
                onClick={logout}
                className="w-full flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm text-rose-400 hover:bg-rose-500/10 transition"
              >
                <LogOut className="w-4 h-4 shrink-0" />
                <AnimatePresence>
                  {!sidebarCollapsed && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="text-[13px]"
                    >
                      Logout
                    </motion.span>
                  )}
                </AnimatePresence>
              </button>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      <div className="flex-1 min-w-0" style={{ marginLeft: sidebarOpen ? sidebarWidth : 0 }}>
        {!sidebarOpen && (
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            onClick={() => setSidebarOpen(true)}
            className="fixed top-3 left-3 z-50 w-9 h-9 rounded-lg bg-slate-900/80 backdrop-blur border border-white/[0.08] flex items-center justify-center text-slate-300 hover:bg-slate-800 transition"
          >
            <Menu className="w-4 h-4" />
          </motion.button>
        )}
        <main className="p-4 md:p-6 max-w-7xl mx-auto">
          <PageWrapper viewKey={view}>
            {view === "overview" && <Overview />}
            {view === "properties" && <Properties />}
            {view === "tenants" && <Tenants />}
            {view === "payments" && <Payments />}
            {view === "maintenance" && <Maintenance />}
            {view === "expenses" && <Expenses />}
            {view === "reports" && <Reports />}
            {view === "books" && <BooksPage />}
            {view === "calendar" && <CalendarPage />}
            {view === "history" && <HistoryPage />}
            {view === "portal" && <TenantPortal />}
            {view === "settings" && <Settings />}
            {view === "enroll" && <Enroll />}
            {view === "tenant" && selectedTenant && (
              <TenantDetailPage
                tenant={selectedTenant}
                onBack={() => setView("overview")}
                onNavigateToTenant={handleTenantPageView}
              />
            )}
          </PageWrapper>
        </main>
      </div>

      <NotificationToast onPush={handleToastPush} onTenantClick={handleTenantClick} />

      <TenantDetailModal tenantId={tenantDetailId} onClose={() => setTenantDetailId(null)} />
    </div>
  );
}
