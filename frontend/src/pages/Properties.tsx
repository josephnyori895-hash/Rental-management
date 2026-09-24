import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Building2, User, Phone, CalendarDays, Receipt,
  CheckCircle2, Droplets, Sparkles, X, Home, ShieldCheck, RotateCcw,
  Layers, Grid3X3, Square, PanelBottom,
} from "lucide-react";
import { getBoard, getRooms } from "../lib/api";
import { Card, Badge, PageHeader, money, EmptyState } from "../components/ui";
import BuildingCanvas from "../components/BuildingCanvas";
import BlueprintCanvas from "../components/BlueprintCanvas";
import IsometricCanvas from "../components/IsometricCanvas";
import PanelGrid from "../components/PanelGrid";

type Light = "vacant" | "unpaid" | "partial" | "paid" | "overpaid";

const LIGHT: Record<Light, { color: string; glow: string; label: string }> = {
  vacant:   { color: "#1a1a2e", glow: "0 0 0 rgba(0,0,0,0)",                label: "Vacant" },
  unpaid:   { color: "#f43f5e", glow: "0 0 14px 2px rgba(244,63,94,.7)",     label: "Unpaid / Overdue" },
  partial:  { color: "#f59e0b", glow: "0 0 12px 2px rgba(245,158,11,.6)",    label: "Partial" },
  paid:     { color: "#34d399", glow: "0 0 12px 2px rgba(52,211,153,.55)",   label: "Paid" },
  overpaid: { color: "#38bdf8", glow: "0 0 14px 2px rgba(56,189,248,.7)",    label: "Overpaid" },
};

const VIEWS = [
  { id: "building",  label: "Building",  icon: <Building2 className="w-3.5 h-3.5" /> },
  { id: "blueprint", label: "Blueprint", icon: <Layers className="w-3.5 h-3.5" /> },
  { id: "isometric", label: "Isometric", icon: <Grid3X3 className="w-3.5 h-3.5" /> },
  { id: "panels",    label: "Panels",    icon: <Square className="w-3.5 h-3.5" /> },
];

export default function Properties() {
  const [board, setBoard] = useState<any>(null);
  const [rooms, setRooms] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("building");

  useEffect(() => {
    getBoard().then((d) => {
      setBoard(d);
      if (d.hostels?.length) setSelected(d.hostels[0].property_id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    getRooms(selected).then((d) => { setRooms(Array.isArray(d) ? d : d.rooms || []); setLoading(false); }).catch(() => setLoading(false));
  }, [selected]);

  const hostel = board?.hostels.find((h: any) => h.property_id === selected) || board?.hostels[0];

  const perFloor = Math.ceil(Math.sqrt(rooms.length || 1)) + 2;
  const floors = useMemo(() => {
    const sorted = [...rooms].sort((a, b) =>
      a.unit_number.localeCompare(b.unit_number, undefined, { numeric: true }));
    const rows: any[][] = [];
    for (let i = 0; i < sorted.length; i += perFloor) rows.push(sorted.slice(i, i + perFloor));
    return rows.reverse().map((r, i) => ({ rooms: r, label: `${rows.length - i}F` }));
  }, [rooms, perFloor]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { vacant: 0, unpaid: 0, partial: 0, paid: 0, overpaid: 0 };
    rooms.forEach((r) => { c[r.rent_light] = (c[r.rent_light] || 0) + 1; });
    return c;
  }, [rooms]);

  const openRoom = (r: any) => {
    setActive(r.id);
    setDrawer(r);
  };

  if (!board) return <div className="text-slate-500 py-16 text-center">Loading properties…</div>;

  return (
    <div className="space-y-5">
      <PageHeader title="Properties" sub="Live building view — every room, lit by rent status" />

      {/* Property selector */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {board.hostels.map((h: any) => (
          <Card key={h.property_id}
            className={`p-4 cursor-pointer border transition-all duration-300 ${
              selected === h.property_id
                ? "border-emerald-500/50 shadow-[0_0_20px_rgba(52,211,153,0.08)]"
                : "border-slate-800 hover:border-slate-600 hover:shadow-[0_0_15px_rgba(148,163,184,0.04)]"
            }`}
            onClick={() => setSelected(h.property_id)}>
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 ${
                selected === h.property_id
                  ? "bg-emerald-500/20 shadow-[0_0_12px_rgba(52,211,153,0.15)]"
                  : "bg-emerald-500/10"
              }`}>
                <Building2 className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <div className="text-sm font-semibold text-white">{h.name}</div>
                <div className="text-[11px] text-slate-500">{h.total_units} rooms · {h.occupied} occupied</div>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-2">
        {(Object.keys(LIGHT) as Light[]).map((k) => (
          <div key={k} className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/60 border border-slate-800 backdrop-blur-sm">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: LIGHT[k].color, boxShadow: LIGHT[k].glow }} />
            <span className="text-[10px] text-slate-400">{LIGHT[k].label}</span>
            <span className="text-[10px] font-bold text-slate-300">{counts[k]}</span>
          </div>
        ))}
      </div>

      {/* ════════ VIEW SWITCHER ════════ */}
      <div className="flex items-center gap-1 px-1 py-1 rounded-xl bg-slate-900/80 border border-slate-800 w-fit">
        {VIEWS.map((v) => (
          <button key={v.id} onClick={() => setView(v.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-medium transition-all duration-200 ${
              view === v.id
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 shadow-[0_0_10px_rgba(52,211,153,0.05)]"
                : "text-slate-400 hover:text-slate-200 border border-transparent"
            }`}>
            {v.icon}
            {v.label}
          </button>
        ))}
      </div>

      {/* ════════ ROOM DISPLAY ════════ */}
      {loading ? (
        <div className="text-slate-500 py-16 text-center">Rendering building…</div>
      ) : rooms.length === 0 ? (
        <EmptyState icon={<Building2 className="w-12 h-12" />} text="No rooms in this hostel" />
      ) : (
        <div className="rounded-2xl overflow-hidden border border-slate-800/50 bg-slate-950">
          {view === "building" && (
            <>
              <BuildingCanvas floors={floors} counts={counts} propertyName={hostel?.name}
                totalUnits={rooms.length} occupied={hostel?.occupied}
                onRoomClick={openRoom} activeRoomId={active} />
              <div className="border-t border-slate-800/40 bg-slate-900/60 backdrop-blur-sm px-5 py-2.5 flex items-center justify-between text-[10px]">
                <span className="text-slate-500 font-mono">{hostel?.name} · {rooms.length} units · {hostel?.occupied || 0} occupied</span>
                <span className="text-slate-600">Click any window to inspect the room</span>
              </div>
            </>
          )}
          {view === "blueprint" && (
            <BlueprintCanvas floors={floors} counts={counts} propertyName={hostel?.name}
              totalUnits={rooms.length} occupied={hostel?.occupied}
              onRoomClick={openRoom} activeRoomId={active} />
          )}
          {view === "isometric" && (
            <IsometricCanvas floors={floors} counts={counts} propertyName={hostel?.name}
              totalUnits={rooms.length} occupied={hostel?.occupied}
              onRoomClick={openRoom} activeRoomId={active} />
          )}
          {view === "panels" && (
            <PanelGrid floors={floors} counts={counts} propertyName={hostel?.name}
              totalUnits={rooms.length} occupied={hostel?.occupied}
              onRoomClick={openRoom} activeRoomId={active} />
          )}
        </div>
      )}

      {/* Room detail drawer */}
      <AnimatePresence>
        {drawer && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40" onClick={() => setDrawer(null)} />
            <motion.div initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
              transition={{ type: "spring", stiffness: 260, damping: 30 }}
              className="fixed right-0 top-0 bottom-0 w-full max-w-sm bg-slate-950/95 backdrop-blur-xl border-l border-slate-800/80 z-50 overflow-y-auto shadow-[-10px_0_40px_rgba(0,0,0,0.5)]">
              <RoomDetail room={drawer} onClose={() => setDrawer(null)} />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ─── ROOM DETAIL PANEL ─── */
function RoomDetail({ room, onClose }: { room: any; onClose: () => void }) {
  const lt = LIGHT[room.rent_light as Light];
  const occupied = room.status === "occupied";
  return (
    <div className="space-y-4 p-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ background: lt.color + "18", boxShadow: `0 0 15px ${lt.color}22` }}>
            <Home className="w-4.5 h-4.5" style={{ color: lt.color }} />
          </div>
          <div>
            <div className="text-lg font-bold text-white">Room {room.unit_number}</div>
            <div className="text-[11px] text-slate-500">KES {money(room.monthly_rent)} / month</div>
          </div>
        </div>
        <button onClick={onClose}
          className="p-2 rounded-xl bg-slate-800/60 hover:bg-slate-700/60 border border-slate-700/30 transition-all duration-200">
          <X className="w-3.5 h-3.5 text-slate-400" />
        </button>
      </div>

      {/* Status badge */}
      <Badge color={room.rent_light === "unpaid" ? "rose" : room.rent_light === "partial" ? "amber" : room.rent_light === "paid" ? "emerald" : room.rent_light === "overpaid" ? "sky" : "slate"}>
        {lt.label}
      </Badge>

      {/* Content */}
      {!occupied ? (
        <Card className="p-6 text-center">
          <Sparkles className="w-8 h-8 text-slate-500 mx-auto mb-3" />
          <div className="text-sm text-slate-300 font-medium">Vacant</div>
          <div className="text-[11px] text-slate-500 mt-1">Ready to lease · Max {room.max_occupants} occupant{room.max_occupants !== 1 ? "s" : ""}</div>
        </Card>
      ) : (
        <>
          <Card className="p-4 space-y-3">
            <div className="text-[10px] uppercase tracking-wider text-emerald-400/80 font-semibold flex items-center gap-1.5">
              <User className="w-3.5 h-3.5" /> Tenant
            </div>
            <div className="text-sm font-semibold text-white">{room.tenant_name}</div>
            {room.tenant_phone && (
              <div className="flex items-center gap-1.5 text-xs text-slate-400"><Phone className="w-3 h-3" /> {room.tenant_phone}</div>
            )}
            {room.duration_months !== null && (
              <div className="flex items-center gap-1.5 text-xs text-slate-400">
                <CalendarDays className="w-3 h-3" /> {room.duration_months} month{room.duration_months !== 1 ? "s" : ""} · since {room.lease_start}
              </div>
            )}
          </Card>

          <Card className="p-4 space-y-2">
            <div className="text-[10px] uppercase tracking-wider text-sky-400/80 font-semibold flex items-center gap-1.5">
              <Receipt className="w-3.5 h-3.5" /> Rent Status
            </div>
            <Row label="Invoice" value={room.invoice_status || "—"} />
            <Row label="Balance" value={`KES ${money(room.invoice_balance)}`} accent={room.invoice_balance > 0 ? "rose" : "emerald"} />
            <Row label="Total Paid" value={`KES ${money(room.total_paid)}`} />
          </Card>

          <Card className="p-4 space-y-2">
            <div className="text-[10px] uppercase tracking-wider text-amber-400/80 font-semibold flex items-center gap-1.5">
              <Droplets className="w-3.5 h-3.5" /> Condition
            </div>
            {room.condition_notes ? (
              <p className="text-xs text-slate-300 leading-relaxed">{room.condition_notes}</p>
            ) : (
              <p className="text-xs text-slate-500 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400/60" /> No issues — unit in good condition.
              </p>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function Row({ label, value, accent = "slate" }: { label: string; value: string; accent?: string }) {
  const c = accent === "rose" ? "text-rose-400" : accent === "emerald" ? "text-emerald-400" : "text-slate-200";
  return (
    <div className="flex justify-between text-xs py-1">
      <span className="text-slate-500 capitalize">{label}</span>
      <span className={`font-medium ${c}`}>{value}</span>
    </div>
  );
}
