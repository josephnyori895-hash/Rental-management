import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  createProperty,
  createUnit,
  getProperties,
  getUnits,
  enroll,
} from "../lib/api";
import {
  Rocket,
  Building2,
  DoorOpen,
  UserPlus,
  CheckCircle,
  ArrowRight,
  ArrowLeft,
  Plus,
} from "lucide-react";

type Step = 0 | 1 | 2 | 3 | 4;

export default function Onboarding() {
  const token = localStorage.getItem("token") || "";
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const [step, setStep] = useState<Step>(0);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  // Step 0 — business
  const [businessName, setBusinessName] = useState("");

  // Step 1 — property
  const [propertyName, setPropertyName] = useState("");
  const [propertyAddress, setPropertyAddress] = useState("");
  const [propertyType, setPropertyType] = useState("hostel");
  const [propertyId, setPropertyId] = useState("");

  // Step 2 — units
  const [unitNumber, setUnitNumber] = useState("");
  const [unitType, setUnitType] = useState("room");
  const [monthlyRent, setMonthlyRent] = useState("");
  const [depositAmount, setDepositAmount] = useState("");
  const [maxOccupants, setMaxOccupants] = useState("1");
  const [createdUnits, setCreatedUnits] = useState<any[]>([]);

  // Step 3 — tenant
  const [tenantName, setTenantName] = useState("");
  const [tenantPhone, setTenantPhone] = useState("");
  const [tenantRent, setTenantRent] = useState("");
  const [tenantDeposit, setTenantDeposit] = useState("");
  const [tenantStart, setTenantStart] = useState(new Date().toISOString().slice(0, 10));
  const [invoiceId, setInvoiceId] = useState("");
  const [waSent, setWaSent] = useState(false);

  // If the business already has properties, jump straight to adding a tenant.
  useEffect(() => {
    (async () => {
      try {
        const ps = await getProperties();
        if (ps && ps.length > 0) {
          setPropertyId(ps[0].id);
          const us = await getUnits(ps[0].id);
          setCreatedUnits(us.filter((u: any) => u.status === "available"));
          setStep(2);
        }
      } catch {
        /* ignore — stay on step 0 */
      }
    })();
  }, []);

  const go = (s: Step) => { setErr(""); setStep(s); };

  const submitBusiness = async (e: any) => {
    e.preventDefault();
    if (!businessName.trim()) return setErr("Business name is required");
    setBusy(true); setErr("");
    try {
      const res = await fetch("/api/v1/notifications/business-config", {
        method: "PUT",
        headers,
        body: JSON.stringify({
          business_name: businessName.trim(),
          payment_methods: ["bank"],
          payment_method: "bank",
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d?.detail || "Could not save business");
      }
      go(1);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const submitProperty = async (e: any) => {
    e.preventDefault();
    if (!propertyName.trim()) return setErr("Property name is required");
    setBusy(true); setErr("");
    try {
      const p = await createProperty({
        name: propertyName.trim(),
        address: propertyAddress.trim() || null,
        property_type: propertyType,
      });
      setPropertyId(p.id);
      go(2);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const addUnit = async (e: any) => {
    e.preventDefault();
    if (!unitNumber.trim()) return setErr("Unit number is required");
    if (!monthlyRent) return setErr("Monthly rent is required");
    setBusy(true); setErr("");
    try {
      const u = await createUnit(propertyId, {
        unit_number: unitNumber.trim(),
        unit_type: unitType,
        monthly_rent: Number(monthlyRent),
        deposit_amount: Number(depositAmount || monthlyRent),
        max_occupants: Number(maxOccupants || 1),
      });
      setCreatedUnits((prev) => [...prev, u]);
      setUnitNumber("");
      setMonthlyRent("");
      setDepositAmount("");
      setMaxOccupants("1");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const submitTenant = async (e: any) => {
    e.preventDefault();
    if (!tenantName.trim()) return setErr("Tenant name is required");
    if (!tenantPhone.trim()) return setErr("Phone number is required");
    if (createdUnits.length === 0) return setErr("Add at least one unit first");
    setBusy(true); setErr("");
    try {
      const u = createdUnits[0];
      const r = await enroll({
        full_name: tenantName.trim(),
        mpesa_phone: tenantPhone.trim(),
        whatsapp_phone: tenantPhone.trim(),
        unit_id: u.id,
        start_date: tenantStart,
        rent_amount: tenantRent ? Number(tenantRent) : Number(u.monthly_rent),
        deposit_amount: tenantDeposit ? Number(tenantDeposit) : Number(u.monthly_rent),
      });
      setInvoiceId(r.invoice_id);
      setWaSent(!!r.whatsapp_sent);
      go(4);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const skipTenant = () => go(4);

  const reset = () => {
    setStep(0);
    setBusinessName("");
    setPropertyName("");
    setPropertyAddress("");
    setPropertyId("");
    setCreatedUnits([]);
    setTenantName("");
    setTenantPhone("");
    setInvoiceId("");
    setErr("");
  };

  const steps = ["Business", "Property", "Units", "Tenant", "Done"];

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-2">
        <Rocket className="w-5 h-5 text-emerald-400" />
        <h1 className="text-xl font-bold">Set up your rental business</h1>
      </div>

      {/* progress */}
      <div className="flex items-center gap-2">
        {steps.map((s, i) => (
          <div key={s} className="flex items-center gap-2 flex-1">
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border ${
                i <= step
                  ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                  : "bg-slate-800 border-slate-700 text-slate-500"
              }`}
            >
              {i < step ? "✓" : i + 1}
            </div>
            {i < steps.length - 1 && (
              <div className={`flex-1 h-0.5 ${i < step ? "bg-emerald-500/40" : "bg-slate-800"}`} />
            )}
          </div>
        ))}
      </div>

      {err && <p className="text-rose-400 text-sm">{err}</p>}

      <AnimatePresence mode="wait">
        {step === 0 && (
          <motion.form
            key="biz"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            onSubmit={submitBusiness}
            className="space-y-4 bg-slate-900/80 border border-slate-700/50 rounded-xl p-5"
          >
            <h2 className="font-semibold text-slate-200">1. Your business</h2>
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-slate-400">Business name</label>
              <input
                className="input"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                placeholder="Alpha Homes Ltd"
                autoFocus
              />
            </div>
            <p className="text-xs text-slate-500">
              You can fine-tune payment rails, bank details and tax settings later in Settings.
            </p>
            <button
              type="submit"
              disabled={busy}
              className="w-full bg-gradient-to-r from-emerald-500 to-emerald-600 text-slate-950 font-semibold py-2.5 rounded-lg hover:from-emerald-400 hover:to-emerald-500 transition-all disabled:opacity-50"
            >
              {busy ? "Saving…" : "Continue"}
            </button>
          </motion.form>
        )}

        {step === 1 && (
          <motion.form
            key="prop"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            onSubmit={submitProperty}
            className="space-y-4 bg-slate-900/80 border border-slate-700/50 rounded-xl p-5"
          >
            <h2 className="font-semibold text-slate-200 flex items-center gap-2">
              <Building2 className="w-4 h-4" /> 2. First property
            </h2>
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-slate-400">Property name</label>
              <input
                className="input"
                value={propertyName}
                onChange={(e) => setPropertyName(e.target.value)}
                placeholder="Sunset Hostel"
                autoFocus
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-slate-400">Address</label>
              <input
                className="input"
                value={propertyAddress}
                onChange={(e) => setPropertyAddress(e.target.value)}
                placeholder="Kasarani, Nairobi"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-slate-400">Type</label>
              <select className="input" value={propertyType} onChange={(e) => setPropertyType(e.target.value)}>
                <option value="hostel">Hostel</option>
                <option value="apartment">Apartment</option>
                <option value="building">Building</option>
                <option value="house">House</option>
                <option value="commercial">Commercial</option>
                <option value="mixed_use">Mixed-use property</option>
                <option value="compound">Compound / multi-building site</option>
              </select>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => go(0)}
                className="px-4 py-2.5 rounded-lg text-sm text-slate-300 bg-slate-800 hover:bg-slate-700 transition"
              >
                <ArrowLeft className="w-4 h-4 inline" />
              </button>
              <button
                type="submit"
                disabled={busy}
                className="flex-1 bg-gradient-to-r from-emerald-500 to-emerald-600 text-slate-950 font-semibold py-2.5 rounded-lg hover:from-emerald-400 hover:to-emerald-500 transition-all disabled:opacity-50"
              >
                {busy ? "Creating…" : "Continue"}
              </button>
            </div>
          </motion.form>
        )}

        {step === 2 && (
          <motion.div
            key="units"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="space-y-4"
          >
            <div className="bg-slate-900/80 border border-slate-700/50 rounded-xl p-5 space-y-4">
              <h2 className="font-semibold text-slate-200 flex items-center gap-2">
                <DoorOpen className="w-4 h-4" /> 3. Add rooms / units
              </h2>

              {createdUnits.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs text-slate-400">Added so far:</p>
                  <ul className="text-sm text-slate-200 space-y-1">
                    {createdUnits.map((u) => (
                      <li key={u.id} className="flex justify-between bg-slate-800/60 rounded px-3 py-1.5">
                        <span>{u.unit_number} ({u.unit_type})</span>
                        <span className="text-emerald-300">KES {Number(u.monthly_rent).toLocaleString()}/mo</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <form onSubmit={addUnit} className="space-y-3 border-t border-slate-700/40 pt-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase tracking-wider text-slate-400">Unit number</label>
                    <input
                      className="input"
                      value={unitNumber}
                      onChange={(e) => setUnitNumber(e.target.value)}
                      placeholder="A1"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase tracking-wider text-slate-400">Type</label>
                    <select className="input" value={unitType} onChange={(e) => setUnitType(e.target.value)}>
                      <option value="room">Room</option>
                      <option value="bedspace">Bedspace</option>
                      <option value="studio">Studio</option>
                      <option value="1_bedroom">1 Bedroom</option>
                      <option value="2_bedroom">2 Bedroom</option>
                      <option value="shop">Shop</option>
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase tracking-wider text-slate-400">Monthly rent</label>
                    <input
                      className="input"
                      type="number"
                      value={monthlyRent}
                      onChange={(e) => setMonthlyRent(e.target.value)}
                      placeholder="8000"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase tracking-wider text-slate-400">Deposit</label>
                    <input
                      className="input"
                      type="number"
                      value={depositAmount}
                      onChange={(e) => setDepositAmount(e.target.value)}
                      placeholder="8000"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] uppercase tracking-wider text-slate-400">Max occupants</label>
                    <input
                      className="input"
                      type="number"
                      value={maxOccupants}
                      onChange={(e) => setMaxOccupants(e.target.value)}
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={busy}
                  className="w-full flex items-center justify-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 py-2 rounded-lg text-sm transition disabled:opacity-50"
                >
                  <Plus className="w-4 h-4" /> {busy ? "Adding…" : "Add unit"}
                </button>
              </form>
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => go(1)}
                className="px-4 py-2.5 rounded-lg text-sm text-slate-300 bg-slate-800 hover:bg-slate-700 transition"
              >
                <ArrowLeft className="w-4 h-4 inline" />
              </button>
              <button
                type="button"
                disabled={createdUnits.length === 0}
                onClick={() => go(3)}
                className="flex-1 flex items-center justify-center gap-1.5 bg-gradient-to-r from-emerald-500 to-emerald-600 text-slate-950 font-semibold py-2.5 rounded-lg hover:from-emerald-400 hover:to-emerald-500 transition-all disabled:opacity-50"
              >
                Continue <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </motion.div>
        )}

        {step === 3 && (
          <motion.form
            key="tenant"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            onSubmit={submitTenant}
            className="space-y-4 bg-slate-900/80 border border-slate-700/50 rounded-xl p-5"
          >
            <h2 className="font-semibold text-slate-200 flex items-center gap-2">
              <UserPlus className="w-4 h-4" /> 4. Enroll your first tenant
            </h2>
            <p className="text-xs text-slate-500">
              This raises the first rent and deposit invoice and sends a WhatsApp welcome.
            </p>
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-slate-400">Tenant name</label>
              <input
                className="input"
                value={tenantName}
                onChange={(e) => setTenantName(e.target.value)}
                placeholder="Jane Doe"
                autoFocus
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-slate-400">M-Pesa / WhatsApp phone</label>
              <input
                className="input"
                value={tenantPhone}
                onChange={(e) => setTenantPhone(e.target.value)}
                placeholder="254712345678"
              />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-wider text-slate-400">Rent</label>
                <input
                  className="input"
                  type="number"
                  value={tenantRent}
                  onChange={(e) => setTenantRent(e.target.value)}
                  placeholder={createdUnits[0] ? String(createdUnits[0].monthly_rent) : ""}
                />
              </div>
              <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-wider text-slate-400">Deposit</label>
                <input
                  className="input"
                  type="number"
                  value={tenantDeposit}
                  onChange={(e) => setTenantDeposit(e.target.value)}
                  placeholder={createdUnits[0] ? String(createdUnits[0].monthly_rent) : ""}
                />
              </div>
              <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-wider text-slate-400">Start date</label>
                <input
                  className="input"
                  type="date"
                  value={tenantStart}
                  onChange={(e) => setTenantStart(e.target.value)}
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => go(2)}
                className="px-4 py-2.5 rounded-lg text-sm text-slate-300 bg-slate-800 hover:bg-slate-700 transition"
              >
                <ArrowLeft className="w-4 h-4 inline" />
              </button>
              <button
                type="button"
                onClick={skipTenant}
                className="px-4 py-2.5 rounded-lg text-sm text-slate-400 bg-slate-800 hover:bg-slate-700 transition"
              >
                Skip
              </button>
              <button
                type="submit"
                disabled={busy}
                className="flex-1 bg-gradient-to-r from-emerald-500 to-emerald-600 text-slate-950 font-semibold py-2.5 rounded-lg hover:from-emerald-400 hover:to-emerald-500 transition-all disabled:opacity-50"
              >
                {busy ? "Enrolling…" : "Enroll & invoice"}
              </button>
            </div>
          </motion.form>
        )}

        {step === 4 && (
          <motion.div
            key="done"
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="space-y-4"
          >
            <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 p-6 text-center">
              <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
              <p className="text-emerald-300 font-semibold text-lg">You're set up</p>
              <p className="text-xs text-emerald-400/70 mt-1">
                {createdUnits.length} unit{createdUnits.length !== 1 ? "s" : ""} added
                {invoiceId ? " · first invoice created" : ""}
              </p>
              {waSent && (
                <p className="text-xs text-emerald-400/70 mt-1">WhatsApp welcome sent to tenant</p>
              )}
            </div>
            <div className="text-sm text-slate-400 space-y-1">
              <p>Next steps:</p>
              <ul className="list-disc list-inside text-slate-300">
                <li>Open <strong>Properties</strong> to configure your buildings, floors, rental units and internal rooms.</li>
                <li>Open <strong>Settings</strong> to enable M-Pesa / Airtel / card rails.</li>
                <li>Run <strong>Rent run</strong> each month to raise rent invoices.</li>
              </ul>
            </div>
            <button
              onClick={reset}
              className="w-full text-xs text-slate-400 hover:text-white py-2 transition"
            >
              Set up another business
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}