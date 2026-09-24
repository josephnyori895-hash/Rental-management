import { useState, useEffect } from "react";
import { Building2, UserCog, Bell, CreditCard, Shield, Image, Plus, Trash2, RotateCcw, ExternalLink, Smartphone, MessageSquare, CheckCircle2, XCircle, Send, RefreshCw, Zap } from "lucide-react";
import { Card, PageHeader } from "../components/ui";
import { getBackgroundConfig, saveBackgroundConfig, addBackgroundUrl, removeBackgroundUrl, resetBackgrounds, type BackgroundConfig } from "../lib/backgrounds";

interface SmsConfig {
  sms_provider: string;
  sms_provider_configured: boolean;
  sms_sender_id: string;
  whatsapp_provider: string;
  whatsapp_provider_configured: boolean;
  default_channel: string;
  daily_reminders_enabled: boolean;
}

interface EnrollmentConfig {
  require_deposit: boolean;
  deposit_type: string;
  deposit_fixed_amount: number | null;
  require_first_rent: boolean;
  allow_partial: boolean;
  grace_hours: number;
}

export default function Settings() {
  const [active, setActive] = useState("business");
  const [bgConfig, setBgConfig] = useState<BackgroundConfig>(getBackgroundConfig());
  const [newUrl, setNewUrl] = useState("");
  const [bgMsg, setBgMsg] = useState("");
  const [smsConfig, setSmsConfig] = useState<SmsConfig | null>(null);
  const [enrollCfg, setEnrollCfg] = useState<EnrollmentConfig | null>(null);
  const [busCfg, setBusCfg] = useState<any>(null);
  const [reminderResult, setReminderResult] = useState<string | null>(null);
  const [loadingSms, setLoadingSms] = useState(false);

  const token = localStorage.getItem("rental_token");

  const refreshBg = () => setBgConfig(getBackgroundConfig());

  useEffect(() => {
    fetch("/api/v1/notifications/settings", {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.ok ? r.json() : null).then(setSmsConfig).catch(() => {});
    fetch("/api/v1/notifications/enrollment-config", {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.ok ? r.json() : null).then(setEnrollCfg).catch(() => {});
    fetch("/api/v1/notifications/business-config", {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.ok ? r.json() : null).then(setBusCfg).catch(() => {});
  }, []);

  const saveBusiness = async (patch: any) => {
    const updated = { ...busCfg, ...patch };
    setBusCfg(updated);
    await fetch("/api/v1/notifications/business-config", {
      method: "PUT",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(updated),
    });
  };

  const saveEnrollment = async (patch: Partial<EnrollmentConfig>) => {
    const updated = { ...enrollCfg, ...patch } as EnrollmentConfig;
    setEnrollCfg(updated);
    await fetch("/api/v1/notifications/enrollment-config", {
      method: "PUT",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(updated),
    });
  };

  const handleAddUrl = () => {
    const url = newUrl.trim();
    if (!url) return;
    if (!url.startsWith("http://") && !url.startsWith("https://")) {
      setBgMsg("Enter a valid URL starting with http:// or https://");
      return;
    }
    addBackgroundUrl(url);
    setNewUrl("");
    setBgMsg("Image added. It will appear in the background rotation.");
    refreshBg();
  };

  const handleRemove = (url: string) => {
    removeBackgroundUrl(url);
    refreshBg();
  };

  const handleReset = () => {
    resetBackgrounds();
    setBgMsg("Reset to default backgrounds.");
    refreshBg();
  };

  const triggerReminders = async () => {
    setLoadingSms(true);
    setReminderResult(null);
    try {
      const r = await fetch("/api/v1/notifications/process-reminders", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await r.json();
      setReminderResult(`Sent ${data.reminders_sent} reminders`);
    } catch {
      setReminderResult("Failed to trigger reminders");
    }
    setLoadingSms(false);
  };

  const updateConfig = (key: keyof BackgroundConfig, value: any) => {
    const updated = { ...bgConfig, [key]: value };
    saveBackgroundConfig(updated);
    setBgConfig(updated);
  };

  const tabs = [
    { id: "business", label: "Business", icon: <Building2 className="w-4 h-4" /> },
    { id: "backgrounds", label: "Backgrounds", icon: <Image className="w-4 h-4" /> },
    { id: "team", label: "Team", icon: <UserCog className="w-4 h-4" /> },
    { id: "billing", label: "Integrations", icon: <CreditCard className="w-4 h-4" /> },
    { id: "notifications", label: "Notifications", icon: <Bell className="w-4 h-4" /> },
    { id: "enrollment", label: "Enrollment", icon: <Zap className="w-4 h-4" /> },
    { id: "security", label: "Security", icon: <Shield className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-5">
      <PageHeader title="Settings" sub="Configure your business & operations" />

      <div className="flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setActive(t.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              active === t.id ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30" : "bg-slate-800/50 text-slate-400 border border-slate-700/50"
            }`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      <Card className="p-5">
        {active === "backgrounds" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">Background Images</h3>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Add your own property photos or building images. {bgConfig.urls.length} images in rotation.
                </p>
              </div>
              <button onClick={handleReset}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition">
                <RotateCcw className="w-3 h-3" /> Reset to defaults
              </button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {bgConfig.urls.map((url, i) => (
                <div key={i} className="group relative rounded-xl overflow-hidden border border-white/[0.06] bg-slate-900/60 aspect-video">
                  <img src={url} alt={`Background ${i + 1}`}
                    className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition" />
                  <div className="absolute top-1.5 left-1.5 text-[10px] font-mono text-slate-400 bg-black/50 px-1.5 py-0.5 rounded">
                    #{i + 1}
                  </div>
                  <button onClick={() => handleRemove(url)}
                    className="absolute top-1.5 right-1.5 w-6 h-6 rounded-lg bg-rose-500/80 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition hover:bg-rose-500">
                    <Trash2 className="w-3 h-3" />
                  </button>
                  <a href={url} target="_blank" rel="noopener noreferrer"
                    className="absolute bottom-1.5 right-1.5 w-5 h-5 rounded bg-black/50 text-slate-400 flex items-center justify-center opacity-0 group-hover:opacity-100 transition hover:text-white">
                    <ExternalLink className="w-2.5 h-2.5" />
                  </a>
                </div>
              ))}
              <div className="relative rounded-xl border border-dashed border-white/[0.10] bg-slate-900/30 aspect-video flex flex-col items-center justify-center gap-1 hover:border-emerald-500/30 transition group">
                <Plus className="w-5 h-5 text-slate-600 group-hover:text-emerald-400 transition" />
                <span className="text-[10px] text-slate-600 group-hover:text-emerald-400 transition">Add Image</span>
              </div>
            </div>
            <div className="flex gap-2">
              <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)}
                placeholder="Paste image URL here (e.g. https://images.unsplash.com/photo-...)"
                className="flex-1 bg-slate-800/50 border border-white/[0.06] rounded-lg px-3 py-2 text-xs outline-none focus:border-emerald-500/50 placeholder:text-slate-600"
                onKeyDown={(e) => e.key === "Enter" && handleAddUrl()}
              />
              <button onClick={handleAddUrl}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 hover:bg-emerald-500/25 transition text-xs font-medium whitespace-nowrap">
                <Plus className="w-3.5 h-3.5" /> Add
              </button>
            </div>
            {bgMsg && <p className="text-[11px] text-emerald-400/80">{bgMsg}</p>}
            <div className="border-t border-white/[0.06] pt-4 space-y-3">
              <h4 className="text-xs font-semibold text-slate-300">Display Settings</h4>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-slate-500 block mb-1">Rotate every (s)</label>
                  <input type="number" min={3} max={60} value={bgConfig.interval}
                    onChange={(e) => updateConfig("interval", Math.max(3, parseInt(e.target.value) || 10))}
                    className="w-full bg-slate-800/50 border border-white/[0.06] rounded-lg px-2.5 py-1.5 text-xs text-slate-200 outline-none focus:border-emerald-500/50"
                  />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-slate-500 block mb-1">Opacity</label>
                  <div className="flex items-center gap-2">
                    <input type="range" min={0.05} max={0.6} step={0.01} value={bgConfig.opacity}
                      onChange={(e) => updateConfig("opacity", parseFloat(e.target.value))}
                      className="flex-1 accent-emerald-500"
                    />
                    <span className="text-xs text-slate-400 w-8">{Math.round(bgConfig.opacity * 100)}%</span>
                  </div>
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-slate-500 block mb-1">Blur (px)</label>
                  <input type="number" min={0} max={60} value={bgConfig.blur}
                    onChange={(e) => updateConfig("blur", parseInt(e.target.value) || 16)}
                    className="w-full bg-slate-800/50 border border-white/[0.06] rounded-lg px-2.5 py-1.5 text-xs text-slate-200 outline-none focus:border-emerald-500/50"
                  />
                </div>
              </div>
              <p className="text-[10px] text-slate-600">Changes apply instantly — no save needed.</p>
            </div>
          </div>
        )}

        {active === "business" && busCfg && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-white">General Info</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-wider text-slate-500 block">Business Name</label>
                <input value={busCfg.business_name} onChange={(e) => saveBusiness({ business_name: e.target.value })}
                  className="w-full bg-slate-850/50 border border-slate-700/60 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-emerald-500/50" />
              </div>
              <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-wider text-slate-500 block">KRA PIN</label>
                <input value={busCfg.kra_pin || ""} onChange={(e) => saveBusiness({ kra_pin: e.target.value })}
                  className="w-full bg-slate-850/50 border border-slate-700/60 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-emerald-500/50" />
              </div>
              <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-wider text-slate-500 block">County</label>
                <input value={busCfg.county || ""} onChange={(e) => saveBusiness({ county: e.target.value })}
                  className="w-full bg-slate-850/50 border border-slate-700/60 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-emerald-500/50" />
              </div>
              <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-wider text-slate-500 block">Default Due Day</label>
                <input type="number" min={1} max={31} value={busCfg.rent_due_day} onChange={(e) => saveBusiness({ rent_due_day: parseInt(e.target.value) || 5 })}
                  className="w-full bg-slate-850/50 border border-slate-700/60 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-emerald-500/50" />
              </div>
            </div>

            <div className="border-t border-white/[0.06] pt-4">
              <h3 className="text-sm font-semibold text-white mb-3">Payment Collections</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-xs text-slate-300">Payment Collection Method</span>
                  <select value={busCfg.payment_method} onChange={(e) => saveBusiness({ payment_method: e.target.value })}
                    className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 outline-none focus:border-emerald-500/50">
                    <option value="mpesa">M-Pesa (STK Push & Paybill)</option>
                    <option value="bank">Bank Transfer</option>
                  </select>
                </div>

                {busCfg.payment_method === "mpesa" && (
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase tracking-wider text-slate-500 block">Default MPESA Paybill / Till Number</label>
                    <input value={busCfg.mpesa_paybill || ""} onChange={(e) => saveBusiness({ mpesa_paybill: e.target.value })}
                      className="w-full bg-slate-850/50 border border-slate-700/60 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-emerald-500/50" />
                  </div>
                )}

                {busCfg.payment_method === "bank" && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-3 bg-slate-900/40 rounded-xl border border-slate-800">
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase tracking-wider text-slate-500 block">Bank Name</label>
                      <input value={busCfg.bank_name || ""} onChange={(e) => saveBusiness({ bank_name: e.target.value })}
                        placeholder="e.g. Equity Bank"
                        className="w-full bg-slate-855 border border-slate-700/60 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-emerald-500/50" />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase tracking-wider text-slate-500 block">Account Number</label>
                      <input value={busCfg.bank_account || ""} onChange={(e) => saveBusiness({ bank_account: e.target.value })}
                        placeholder="e.g. 1220123456789"
                        className="w-full bg-slate-855 border border-slate-700/60 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-emerald-500/50" />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[10px] uppercase tracking-wider text-slate-500 block">Account Name</label>
                      <input value={busCfg.bank_account_name || ""} onChange={(e) => saveBusiness({ bank_account_name: e.target.value })}
                        placeholder="e.g. Nyorii Hostels"
                        className="w-full bg-slate-855 border border-slate-700/60 rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-emerald-500/50" />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {active === "team" && (
          <div className="space-y-2 text-sm text-slate-300">
            <TeamRow name="Nyorii" role="Owner" email="owner@rental.dev" />
            <TeamRow name="Caretaker John" role="Caretaker" email="+254712345678" />
            <p className="text-[11px] text-slate-500 pt-2">
              Caretaker phone number is used for WhatsApp alerts. Owner can also manage via WhatsApp commands.
            </p>
          </div>
        )}

        {active === "billing" && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-emerald-400" />
              WhatsApp Provider
            </h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                <span className="text-xs text-slate-400">Provider</span>
                <span className="text-xs font-mono text-slate-200">{smsConfig?.whatsapp_provider || "—"}</span>
              </div>
              <div className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                <span className="text-xs text-slate-400">Status</span>
                <span className={`flex items-center gap-1.5 text-xs font-medium ${smsConfig?.whatsapp_provider_configured ? "text-emerald-400" : "text-amber-400"}`}>
                  {smsConfig?.whatsapp_provider_configured
                    ? <><CheckCircle2 className="w-3 h-3" /> Connected</>
                    : <><XCircle className="w-3 h-3" /> Not configured (simulated mode)</>
                  }
                </span>
              </div>
            </div>
            {!smsConfig?.whatsapp_provider_configured && (
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-3">
                <p className="text-[11px] text-amber-300">
                  To send real WhatsApp messages, set <code className="text-[10px] bg-slate-800 px-1 py-0.5 rounded">AT_API_KEY</code>,{" "}
                  <code className="text-[10px] bg-slate-800 px-1 py-0.5 rounded">AT_USERNAME</code>, and{" "}
                  <code className="text-[10px] bg-slate-800 px-1 py-0.5 rounded">AT_WHATSAPP_NUMBER</code> in .env.
                  Messages are currently logged to console.
                </p>
              </div>
            )}

            <div className="border-t border-white/[0.06] pt-4">
              <h4 className="text-xs font-semibold text-slate-300 mb-3">SMS Provider</h4>
              <div className="space-y-2">
                <div className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-xs text-slate-400">Provider</span>
                  <span className="text-xs font-mono text-slate-200">{smsConfig?.sms_provider || "—"}</span>
                </div>
                <div className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-xs text-slate-400">Sender ID</span>
                  <span className="text-xs text-slate-200">{smsConfig?.sms_sender_id || "—"}</span>
                </div>
                <div className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-xs text-slate-400">Status</span>
                  <span className={`flex items-center gap-1.5 text-xs font-medium ${smsConfig?.sms_provider_configured ? "text-emerald-400" : "text-amber-400"}`}>
                    {smsConfig?.sms_provider_configured
                      ? <><CheckCircle2 className="w-3 h-3" /> Connected</>
                      : <><XCircle className="w-3 h-3" /> Simulated</>
                    }
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {active === "notifications" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-emerald-400" />
                Reminders
              </h3>
              <button onClick={triggerReminders} disabled={loadingSms}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 hover:bg-emerald-500/25 transition disabled:opacity-50">
                {loadingSms ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                {loadingSms ? "Sending..." : "Trigger Reminders Now"}
              </button>
            </div>
            {reminderResult && (
              <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-3">
                <p className="text-[11px] text-emerald-300">{reminderResult}</p>
              </div>
            )}
            <p className="text-[11px] text-slate-500">
              Daily automated reminders enabled. Tenants with WhatsApp receive WA messages; others receive SMS.
              {!smsConfig?.whatsapp_provider_configured && !smsConfig?.sms_provider_configured && " Currently in simulated mode."}
            </p>
            <div className="border-t border-white/[0.06] pt-4 space-y-2">
              <h4 className="text-xs font-semibold text-slate-300">Notification Preferences</h4>
              <Toggle label="Rent due reminders" on />
              <Toggle label="Payment overdue alerts" on />
              <Toggle label="Maintenance updates" on />
              <Toggle label="Weekly owner statement" on />
            </div>
          </div>
        )}

        {active === "enrollment" && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-semibold text-white">Enrollment Requirements</h3>
            </div>
            <p className="text-[11px] text-slate-500">
              Configure what tenants must pay before their lease activates. Caretaker/owner can add tenants via WhatsApp command: ADD 2547XXXXXX UNIT# Name.
            </p>
            <div className="space-y-2">
              {enrollCfg && (
                <>
                  <div className="flex justify-between items-center px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                    <span className="text-xs text-slate-300">Require deposit</span>
                    <button onClick={() => saveEnrollment({ require_deposit: !enrollCfg.require_deposit })}
                      className={`w-9 h-5 rounded-full transition relative ${enrollCfg.require_deposit ? "bg-emerald-500" : "bg-slate-700"}`}>
                      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${enrollCfg.require_deposit ? "left-4" : "left-0.5"}`} />
                    </button>
                  </div>

                  {enrollCfg.require_deposit && (
                    <div className="flex justify-between items-center px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                      <span className="text-xs text-slate-300">Deposit amount</span>
                      <select value={enrollCfg.deposit_type} onChange={(e) => saveEnrollment({ deposit_type: e.target.value })}
                        className="bg-slate-800/50 border border-slate-700 rounded-lg px-2 py-1 text-xs text-slate-200 outline-none focus:border-emerald-500/50">
                        <option value="one_month">1 month rent</option>
                        <option value="two_months">2 months rent</option>
                        <option value="fixed">Fixed amount</option>
                      </select>
                    </div>
                  )}

                  <div className="flex justify-between items-center px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                    <span className="text-xs text-slate-300">Require first month rent</span>
                    <button onClick={() => saveEnrollment({ require_first_rent: !enrollCfg.require_first_rent })}
                      className={`w-9 h-5 rounded-full transition relative ${enrollCfg.require_first_rent ? "bg-emerald-500" : "bg-slate-700"}`}>
                      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${enrollCfg.require_first_rent ? "left-4" : "left-0.5"}`} />
                    </button>
                  </div>

                  <div className="flex justify-between items-center px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                    <span className="text-xs text-slate-300">Allow partial payment (rent only, no deposit)</span>
                    <button onClick={() => saveEnrollment({ allow_partial: !enrollCfg.allow_partial })}
                      className={`w-9 h-5 rounded-full transition relative ${enrollCfg.allow_partial ? "bg-emerald-500" : "bg-slate-700"}`}>
                      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${enrollCfg.allow_partial ? "left-4" : "left-0.5"}`} />
                    </button>
                  </div>

                  <div className="flex justify-between items-center px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
                    <span className="text-xs text-slate-300">Payment grace period (hours)</span>
                    <input type="number" min={1} max={168} value={enrollCfg.grace_hours}
                      onChange={(e) => saveEnrollment({ grace_hours: parseInt(e.target.value) || 24 })}
                      className="w-20 bg-slate-800/50 border border-slate-700 rounded-lg px-2 py-1 text-xs text-slate-200 text-right outline-none focus:border-emerald-500/50"
                    />
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {active === "security" && (
          <div className="space-y-3 text-sm">
            <Field label="2FA" value="Enabled" />
            <Field label="Session" value="Active on this device" />
            <Toggle label="Require caretaker PIN" on />
            <p className="text-[11px] text-slate-500">Audit log: 142 events in last 30 days.</p>
          </div>
        )}
      </Card>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
      <span className="text-xs text-slate-400">{label}</span>
      <span className="text-sm font-medium text-slate-200">{value}</span>
    </div>
  );
}

function Toggle({ label, on }: { label: string; on: boolean }) {
  const [state, setState] = useState(on);
  return (
    <div className="flex justify-between items-center px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
      <span className="text-xs text-slate-300">{label}</span>
      <button onClick={() => setState(!state)}
        className={`w-9 h-5 rounded-full transition relative ${state ? "bg-emerald-500" : "bg-slate-700"}`}>
        <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${state ? "left-4" : "left-0.5"}`} />
      </button>
    </div>
  );
}

function TeamRow({ name, role, email }: { name: string; role: string; email: string }) {
  return (
    <div className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center text-emerald-400 text-xs font-bold">
          {name.slice(0, 2).toUpperCase()}
        </div>
        <div>
          <div className="text-sm text-slate-200">{name}</div>
          <div className="text-[10px] text-slate-500">{role}</div>
        </div>
      </div>
      <span className="text-[11px] text-slate-500">{email}</span>
    </div>
  );
}
