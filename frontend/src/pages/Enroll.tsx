import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { getProperties, getUnits, enroll, simulate, stk } from "../lib/api";
import { UserPlus, Phone, Calendar, DollarSign, DoorOpen, CheckCircle, Zap, MessageCircle } from "lucide-react";

export default function Enroll() {
  const [props, setProps] = useState<any[]>([]);
  const [pid, setPid] = useState("");
  const [units, setUnits] = useState<any[]>([]);
  const [uid, setUid] = useState("");
  const [full_name, setFull] = useState("");
  const [mpesa, setMpesa] = useState("");
  const [rent, setRent] = useState("");
  const [deposit, setDeposit] = useState("");
  const [start, setStart] = useState(new Date().toISOString().slice(0, 10));
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [lastInvoice, setLastInvoice] = useState("");
  const [waSent, setWaSent] = useState(false);
  const [step, setStep] = useState<"form" | "done">("form");

  useEffect(() => {
    (async () => {
      try {
        const p = await getProperties();
        setProps(p);
        if (p[0]) setPid(p[0].id);
      } catch (e: any) {
        setErr(e.message);
      }
    })();
  }, []);

  useEffect(() => {
    if (!pid) return;
    (async () => {
      try {
        const u = await getUnits(pid);
        setUnits(u);
        const avail = u.find((x: any) => x.status === "available");
        setUid(avail ? avail.id : "");
        if (avail) {
          setRent(String(avail.monthly_rent));
          setDeposit(String(avail.monthly_rent)); // Default deposit to 1 month rent
        }
      } catch (e: any) {
        setErr(e.message);
      }
    })();
  }, [pid]);

  const onUnit = (id: string) => {
    setUid(id);
    const u = units.find((x) => x.id === id);
    if (u) {
      setRent(String(u.monthly_rent));
      setDeposit(String(u.monthly_rent)); // Default deposit to 1 month rent
    }
  };

  const refreshUnits = async () => {
    const u = await getUnits(pid);
    setUnits(u);
    const avail = u.find((x: any) => x.status === "available");
    setUid(avail ? avail.id : "");
    if (avail) {
      setRent(String(avail.monthly_rent));
      setDeposit(String(avail.monthly_rent)); // Default deposit to 1 month rent
    }
  };

  const submit = async (e: any) => {
    e.preventDefault();
    setErr("");
    setMsg("");
    if (!uid) return setErr("Pick an available room first");
    try {
      const r = await enroll({
        full_name,
        mpesa_phone: mpesa,
        whatsapp_phone: mpesa,   // mpesa number IS the WA number in most cases
        unit_id: uid,
        start_date: start,
        rent_amount: rent ? Number(rent) : undefined,
        deposit_amount: deposit ? Number(deposit) : 0,
      });
      setLastInvoice(r.invoice_id);
      setWaSent(!!r.whatsapp_sent);
      setMsg(`Enrolled ${r.unit_number}. Invoice created.`);
      setStep("done");
      await refreshUnits();
    } catch (e: any) {
      setErr(e.message);
    }
  };

  const doSimulate = async () => {
    if (!lastInvoice) return;
    try {
      const r = await simulate(lastInvoice, Number(rent) || 0);
      setMsg(`Payment recorded — ${r.status}`);
    } catch (e: any) {
      setErr(e.message);
    }
  };

  const doStk = async () => {
    if (!lastInvoice) return;
    try {
      const r = await stk(lastInvoice, mpesa || "254712345678");
      setMsg(`STK push sent to tenant's phone`);
    } catch (e: any) {
      setErr(e.message + " — use simulate instead.");
    }
  };

  const resetForm = () => {
    setStep("form");
    setFull("");
    setMpesa("");
    setRent("");
    setDeposit("");
    setLastInvoice("");
    setWaSent(false);
    setMsg("");
    setErr("");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 80, damping: 12 }}
      className="max-w-lg mx-auto space-y-4"
    >
      <div className="flex items-center gap-2 mb-2">
        <UserPlus className="w-5 h-5 text-emerald-400" />
        <h1 className="text-xl font-bold">Enroll New Tenant</h1>
      </div>

      {step === "form" ? (
        <motion.form
          key="form"
          initial={{ x: -20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          onSubmit={submit}
          className="space-y-3 bg-slate-900/80 backdrop-blur border border-slate-700/50 rounded-xl p-5"
        >
          {/* Hostel */}
          <div className="space-y-1">
            <label className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center gap-1">
              <DoorOpen className="w-3 h-3" /> Hostel
            </label>
            <select
              className="input"
              value={pid}
              onChange={(e) => setPid(e.target.value)}
            >
              {props.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* Room */}
          <div className="space-y-1">
            <label className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center gap-1">
              <DoorOpen className="w-3 h-3" /> Room
            </label>
            <select className="input" value={uid} onChange={(e) => onUnit(e.target.value)}>
              <option value="">— select available room —</option>
              {units
                .filter((u) => u.status === "available")
                .map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.unit_number} — KES {u.monthly_rent?.toLocaleString()}/mo
                  </option>
                ))}
            </select>
          </div>

          {/* Tenant name */}
          <div className="space-y-1">
            <label className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center gap-1">
              <UserPlus className="w-3 h-3" /> Tenant Name
            </label>
            <input
              className="input"
              value={full_name}
              onChange={(e) => setFull(e.target.value)}
              placeholder="Jane Doe"
            />
          </div>

          {/* M-Pesa */}
          <div className="space-y-1">
            <label className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center gap-1">
              <Phone className="w-3 h-3" /> M-Pesa Phone
            </label>
            <input
              className="input"
              value={mpesa}
              onChange={(e) => setMpesa(e.target.value)}
              placeholder="254712345678"
            />
          </div>

          {/* Rent + Deposit + Date */}
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center gap-1">
                <DollarSign className="w-3 h-3" /> Rent
              </label>
              <input
                className="input"
                value={rent}
                onChange={(e) => setRent(e.target.value)}
                type="number"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center gap-1">
                <DollarSign className="w-3 h-3" /> Deposit
              </label>
              <input
                className="input"
                value={deposit}
                onChange={(e) => setDeposit(e.target.value)}
                type="number"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-slate-400 flex items-center gap-1">
                <Calendar className="w-3 h-3" /> Start Date
              </label>
              <input
                className="input"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                type="date"
              />
            </div>
          </div>

          {err && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-rose-400 text-sm"
            >
              {err}
            </motion.p>
          )}

          <motion.button
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            className="w-full bg-gradient-to-r from-emerald-500 to-emerald-600 text-slate-950 font-semibold py-2.5 rounded-lg hover:from-emerald-400 hover:to-emerald-500 transition-all shadow-lg shadow-emerald-500/20"
          >
            Enroll & Create Invoice
          </motion.button>
        </motion.form>
      ) : (
        <motion.div
          key="done"
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="space-y-3"
        >
          {/* Success card */}
          <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 p-5 text-center">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 200, delay: 0.1 }}
            >
              <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-2" />
            </motion.div>
            <p className="text-emerald-300 font-semibold">{msg}</p>
            <p className="text-xs text-emerald-400/70 mt-1">
              Invoice: {lastInvoice?.slice(0, 8)}...
            </p>
            {/* WhatsApp status badge */}
            <div className={`inline-flex items-center gap-1.5 mt-3 px-3 py-1 rounded-full text-xs font-semibold border ${
              waSent
                ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-300"
                : "bg-slate-700/40 border-slate-600/40 text-slate-400"
            }`}>
              <MessageCircle className="w-3 h-3" />
              {waSent ? "WhatsApp welcome sent ✓" : "WhatsApp not sent (no WA number)"}
            </div>
          </div>

          {/* Payment actions */}
          <div className="flex gap-2">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={doStk}
              className="flex-1 flex items-center justify-center gap-1.5 bg-sky-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-sky-500 transition-all"
            >
              <Zap className="w-4 h-4" />
              Send M-Pesa STK
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={doSimulate}
              className="flex-1 flex items-center justify-center gap-1.5 bg-emerald-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-emerald-500 transition-all"
            >
              <CheckCircle className="w-4 h-4" />
              Mark Paid
            </motion.button>
          </div>

          <button
            onClick={resetForm}
            className="w-full text-xs text-slate-400 hover:text-white py-2 transition"
          >
            Enroll Another Tenant
          </button>
        </motion.div>
      )}
    </motion.div>
  );
}
