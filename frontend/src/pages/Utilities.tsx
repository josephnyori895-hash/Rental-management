import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Droplet, Gauge, Plus, Loader2, Split, AlertTriangle, CheckCircle2,
  FileText, Percent,
} from "lucide-react";
import {
  getProperties, getUnits,
  getUtilityRates, saveUtilityRate,
  getMeterReadings, recordMeterReading, billSharedUtility,
} from "../lib/api";
import { Card, PageHeader, StatCard, Badge, EmptyState, money } from "../components/ui";

const UTILITIES: { value: string; label: string }[] = [
  { value: "water", label: "Water" },
  { value: "electricity", label: "Electricity" },
  { value: "gas", label: "Gas" },
  { value: "wifi", label: "Wi-Fi" },
  { value: "garbage", label: "Garbage" },
  { value: "service_charge", label: "Service charge" },
  { value: "other", label: "Other" },
];

const SPLITS: { value: string; label: string; hint: string }[] = [
  { value: "metered", label: "By each unit's own meter", hint: "every occupied unit needs a reading this period" },
  { value: "equal", label: "Equally", hint: "the same share for each unit" },
  { value: "occupancy", label: "By occupancy", hint: "weighted by each unit's max occupants" },
  { value: "rent", label: "By rent", hint: "weighted by each unit's monthly rent" },
];

const utilityLabel = (value: string) =>
  UTILITIES.find((u) => u.value === value)?.label ?? value.replace(/_/g, " ");

const TABS = [
  { key: "readings" as const, label: "Meter readings" },
  { key: "tariffs" as const, label: "Tariffs" },
  { key: "shared" as const, label: "Shared bill" },
];

const input =
  "bg-slate-800 border border-slate-700 focus:border-emerald-500/60 rounded-lg px-2.5 py-2 text-sm text-white outline-none transition";

type Tab = "readings" | "tariffs" | "shared";

/** A reading or a tariff form shares this select for picking a unit. */
function UnitSelect({
  units, value, onChange, sharedLabel,
}: {
  units: any[]; value: string; onChange: (v: string) => void; sharedLabel: string;
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={input}>
      <option value="">{sharedLabel}</option>
      {units.map((u) => (
        <option key={u.id} value={u.id}>
          {u.unit_number} · {u.status}
        </option>
      ))}
    </select>
  );
}

export default function Utilities() {
  const [tab, setTab] = useState<Tab>("readings");
  const [properties, setProperties] = useState<any[]>([]);
  const [propertyId, setPropertyId] = useState("");
  const [units, setUnits] = useState<any[]>([]);
  const [rates, setRates] = useState<any[]>([]);
  const [readings, setReadings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [readingForm, setReadingForm] = useState({
    unit_id: "", utility_type: "water", current_reading: "", bill: true,
  });
  const [rateForm, setRateForm] = useState({
    unit_id: "", utility_type: "water", rate_per_unit: "", fixed_charge: "0", split_method: "metered",
  });
  const [sharedForm, setSharedForm] = useState({
    utility_type: "water", total_amount: "", split_method: "equal",
  });
  const [breakdown, setBreakdown] = useState<any>(null);

  const load = useCallback(async (pid?: string) => {
    try {
      const [props, reads, rts] = await Promise.all([
        getProperties(),
        getMeterReadings(pid ? { property_id: pid } : {}),
        getUtilityRates(pid || undefined),
      ]);
      setProperties(props);
      setReadings(reads.readings || []);
      setRates(rts.rates || []);
      setPropertyId((current) => current || props[0]?.id || "");
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!propertyId) { setUnits([]); return; }
    getUnits(propertyId).then(setUnits).catch(() => setUnits([]));
  }, [propertyId]);

  const onProperty = (pid: string) => {
    setPropertyId(pid);
    setBreakdown(null);
    setNotice("");
    load(pid);
  };

  const withBusy = async (fn: () => Promise<void>) => {
    setBusy(true); setError(""); setNotice("");
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  const submitReading = () => withBusy(async () => {
    if (!propertyId) throw new Error("Pick a property first.");
    if (readingForm.current_reading === "") throw new Error("Enter the meter reading.");
    const payload: any = {
      utility_type: readingForm.utility_type,
      current_reading: parseFloat(readingForm.current_reading),
      bill: readingForm.bill,
    };
    if (readingForm.unit_id) payload.unit_id = readingForm.unit_id;
    else payload.property_id = propertyId;

    const result = await recordMeterReading(payload);
    const where = result.reading?.unit_number ? `Unit ${result.reading.unit_number}` : "the shared meter";
    setNotice(
      result.note
        ? result.note
        : `${where}: ${result.consumed} consumed — KES ${money(result.amount)}${result.billed ? " invoiced to the tenant." : "."}`
    );
    setReadingForm((f) => ({ ...f, current_reading: "" }));
    await load(propertyId);
  });

  const submitRate = () => withBusy(async () => {
    if (!propertyId) throw new Error("Pick a property first.");
    await saveUtilityRate({
      property_id: propertyId,
      unit_id: rateForm.unit_id || null,
      utility_type: rateForm.utility_type,
      rate_per_unit: parseFloat(rateForm.rate_per_unit || "0"),
      fixed_charge: parseFloat(rateForm.fixed_charge || "0"),
      split_method: rateForm.split_method,
    });
    setNotice(
      `${utilityLabel(rateForm.utility_type)} tariff saved for ${rateForm.unit_id ? "the unit" : "the whole property"}.`
    );
    await load(propertyId);
  });

  const submitShared = () => withBusy(async () => {
    if (!propertyId) throw new Error("Pick a property first.");
    if (sharedForm.total_amount === "") throw new Error("Enter the total amount to split.");
    const result = await billSharedUtility({
      property_id: propertyId,
      utility_type: sharedForm.utility_type,
      total_amount: parseFloat(sharedForm.total_amount),
      split_method: sharedForm.split_method,
    });
    setBreakdown(result);
    await load(propertyId);
  });

  const stats = useMemo(() => {
    const billed = readings.filter((r) => r.invoice_id).reduce((sum, r) => sum + (r.amount || 0), 0);
    const unbilled = readings.filter((r) => !r.invoice_id && r.amount > 0).length;
    return { billed, unbilled, count: readings.length };
  }, [readings]);

  if (loading) return <div className="text-slate-500 py-16 text-center">Loading…</div>;

  if (properties.length === 0) {
    return (
      <div className="space-y-5">
        <PageHeader title="Utilities" sub="Tariffs, meter readings & shared-cost billing" />
        <EmptyState
          icon={<Gauge className="w-12 h-12" />}
          text="No properties yet"
          sub="Add a property before setting up utilities."
        />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Utilities"
        sub="Tariffs, meter readings & shared-cost billing"
        actions={
          <select value={propertyId} onChange={(e) => onProperty(e.target.value)} className={input}>
            {properties.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        }
      />

      <div className="grid md:grid-cols-3 gap-4">
        <StatCard
          icon={<FileText className="w-4 h-4" />}
          label="Billed from meter readings"
          value={`KES ${money(stats.billed)}`}
          color="emerald"
          delay={0}
        />
        <StatCard icon={<Gauge className="w-4 h-4" />} label="Readings logged" value={stats.count} color="sky" delay={0.05} />
        <StatCard
          icon={<AlertTriangle className="w-4 h-4" />}
          label="Charged but not invoiced"
          value={stats.unbilled}
          sub={stats.unbilled > 0 ? "vacant units, or no tariff set" : undefined}
          color={stats.unbilled > 0 ? "amber" : "slate"}
          delay={0.1}
        />
      </div>

      {(error || notice) && (
        <Card className="p-3 flex items-start gap-2 border-slate-700/60">
          {error
            ? <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            : <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />}
          <p className={`text-xs ${error ? "text-rose-300" : "text-emerald-300"}`}>{error || notice}</p>
        </Card>
      )}

      {/* Tabs */}
      <div className="flex gap-1.5 border-b border-slate-800 pb-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              tab === t.key
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] border border-transparent"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Meter readings ── */}
      {tab === "readings" && (
        <>
          <Card className="p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Gauge className="w-4 h-4 text-sky-400" />
              <div>
                <div className="text-sm font-semibold text-slate-200">Record a meter reading</div>
                <div className="text-[11px] text-slate-500">
                  Prices the charge from the tariff and invoices the tenant. A first reading is
                  stored as a baseline; a reading lower than the last one is refused.
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <UnitSelect
                units={units}
                value={readingForm.unit_id}
                onChange={(v) => setReadingForm({ ...readingForm, unit_id: v })}
                sharedLabel="Whole property (shared meter)"
              />
              <select
                value={readingForm.utility_type}
                onChange={(e) => setReadingForm({ ...readingForm, utility_type: e.target.value })}
                className={input}
              >
                {UTILITIES.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
              <input
                type="number"
                step="0.001"
                placeholder="Current reading"
                value={readingForm.current_reading}
                onChange={(e) => setReadingForm({ ...readingForm, current_reading: e.target.value })}
                onKeyDown={(e) => e.key === "Enter" && submitReading()}
                className={input}
              />
              <button
                onClick={submitReading}
                disabled={busy}
                className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-500 text-slate-950 font-semibold text-sm hover:bg-emerald-400 disabled:opacity-50 transition"
              >
                {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                Log reading
              </button>
            </div>

            <label className="flex items-center gap-2 text-[11px] text-slate-400">
              <input
                type="checkbox"
                checked={readingForm.bill}
                onChange={(e) => setReadingForm({ ...readingForm, bill: e.target.checked })}
                className="accent-emerald-500"
              />
              Invoice the tenant when this reading produces a charge
            </label>
          </Card>

          {readings.length === 0 ? (
            <EmptyState icon={<Gauge className="w-12 h-12" />} text="No readings yet" sub="Log one above, or from WhatsApp with METER <unit> <reading>." />
          ) : (
            <div className="space-y-1.5">
              {readings.map((r, i) => (
                <motion.div
                  key={r.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.02 }}
                  className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-sky-500/10 flex items-center justify-center shrink-0">
                      <Droplet className="w-4 h-4 text-sky-400" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-slate-200 truncate">
                        {utilityLabel(r.utility_type)} · {r.is_bulk ? "shared meter" : `Unit ${r.unit_number ?? "—"}`}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        {r.reading_date} · read {money(r.current_reading)} · used {r.units_consumed}
                        {r.source === "whatsapp" && " · via WhatsApp"}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-sm font-bold text-white">KES {money(r.amount)}</span>
                    {r.invoice_id
                      ? <Badge color="emerald">invoiced</Badge>
                      : <Badge color={r.amount > 0 ? "amber" : "slate"}>{r.amount > 0 ? "not billed" : "baseline"}</Badge>}
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </>
      )}

      {/* ── Tariffs ── */}
      {tab === "tariffs" && (
        <>
          <Card className="p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Percent className="w-4 h-4 text-violet-400" />
              <div>
                <div className="text-sm font-semibold text-slate-200">Set a tariff</div>
                <div className="text-[11px] text-slate-500">
                  Saving again for the same property and utility updates the existing tariff. A
                  unit-specific tariff beats the property-wide one.
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              <UnitSelect
                units={units}
                value={rateForm.unit_id}
                onChange={(v) => setRateForm({ ...rateForm, unit_id: v })}
                sharedLabel="Whole property"
              />
              <select
                value={rateForm.utility_type}
                onChange={(e) => setRateForm({ ...rateForm, utility_type: e.target.value })}
                className={input}
              >
                {UTILITIES.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
              <input
                type="number"
                step="0.0001"
                placeholder="Rate per unit (KES)"
                value={rateForm.rate_per_unit}
                onChange={(e) => setRateForm({ ...rateForm, rate_per_unit: e.target.value })}
                className={input}
              />
              <input
                type="number"
                placeholder="Fixed charge (KES)"
                value={rateForm.fixed_charge}
                onChange={(e) => setRateForm({ ...rateForm, fixed_charge: e.target.value })}
                className={input}
              />
              <select
                value={rateForm.split_method}
                onChange={(e) => setRateForm({ ...rateForm, split_method: e.target.value })}
                className={input}
              >
                {SPLITS.map((s) => <option key={s.value} value={s.value}>Split: {s.label}</option>)}
              </select>
              <button
                onClick={submitRate}
                disabled={busy}
                className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-violet-500 text-slate-950 font-semibold text-sm hover:bg-violet-400 disabled:opacity-50 transition"
              >
                {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                Save tariff
              </button>
            </div>
          </Card>

          {rates.length === 0 ? (
            <EmptyState
              icon={<Percent className="w-12 h-12" />}
              text="No tariffs set"
              sub="Readings can still be logged, but nothing can be priced until a tariff exists."
            />
          ) : (
            <div className="space-y-1.5">
              {rates.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-900/60 border border-slate-800"
                >
                  <div>
                    <div className="text-sm font-medium text-slate-200">
                      {utilityLabel(r.utility_type)}
                      {r.label ? ` — ${r.label}` : ""}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      {r.unit_id ? "This unit only" : "Property-wide"} ·{" "}
                      {SPLITS.find((s) => s.value === r.split_method)?.label ?? r.split_method}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-400">
                      KES {money(r.rate_per_unit)}/unit
                      {r.fixed_charge > 0 && ` + KES ${money(r.fixed_charge)} fixed`}
                    </span>
                    {r.is_active ? <Badge color="emerald">active</Badge> : <Badge color="slate">inactive</Badge>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* ── Shared bill ── */}
      {tab === "shared" && (
        <>
          <Card className="p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Split className="w-4 h-4 text-amber-400" />
              <div>
                <div className="text-sm font-semibold text-slate-200">Split one bill across the block</div>
                <div className="text-[11px] text-slate-500">
                  For a bill that covers the whole property (one water main, one garbage contract).
                  Each occupied unit gets its own invoice.
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <select
                value={sharedForm.utility_type}
                onChange={(e) => setSharedForm({ ...sharedForm, utility_type: e.target.value })}
                className={input}
              >
                {UTILITIES.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
              <input
                type="number"
                placeholder="Total amount (KES)"
                value={sharedForm.total_amount}
                onChange={(e) => setSharedForm({ ...sharedForm, total_amount: e.target.value })}
                className={input}
              />
              <select
                value={sharedForm.split_method}
                onChange={(e) => setSharedForm({ ...sharedForm, split_method: e.target.value })}
                className={input}
              >
                {SPLITS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
              <button
                onClick={submitShared}
                disabled={busy}
                className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-amber-500 text-slate-950 font-semibold text-sm hover:bg-amber-400 disabled:opacity-50 transition"
              >
                {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Split className="w-3.5 h-3.5" />}
                Split & invoice
              </button>
            </div>

            <p className="text-[11px] text-slate-500">
              {SPLITS.find((s) => s.value === sharedForm.split_method)?.hint}
              . Shares always add up to the total exactly.
            </p>
          </Card>

          {breakdown && (
            <Card className="p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-slate-200">
                  {utilityLabel(breakdown.utility_type)} · {breakdown.units_billed} unit
                  {breakdown.units_billed === 1 ? "" : "s"} invoiced
                </div>
                <span className="text-sm font-bold text-white">KES {money(breakdown.total)}</span>
              </div>
              <div className="text-[10px] text-slate-500">
                {breakdown.split_method} · {breakdown.period_start} to {breakdown.period_end}
              </div>
              <div className="divide-y divide-slate-800">
                {breakdown.breakdown?.map((row: any) => (
                  <div key={row.unit_id} className="flex items-center justify-between py-2 text-xs">
                    <span className="text-slate-300">Unit {row.unit_number}</span>
                    <span className="flex items-center gap-3">
                      <span className="text-slate-500">weight {row.weight}</span>
                      <span className="text-slate-200 font-medium">KES {money(row.share)}</span>
                      {row.billed
                        ? <Badge color="emerald">invoiced</Badge>
                        : <Badge color="amber">not invoiced</Badge>}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
