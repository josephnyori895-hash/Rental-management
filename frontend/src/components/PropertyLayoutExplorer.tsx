import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownLeft,
  ArrowLeftRight,
  ArrowUpRight,
  Building2,
  Compass,
  DoorOpen,
  LayoutGrid,
  MapPinned,
  Settings2,
} from "lucide-react";
import BuildingCanvas from "./BuildingCanvas";
import PropertyLayoutEditor from "./PropertyLayoutEditor";
import { getPropertyLayout } from "../lib/api";

type RentLight = "vacant" | "unpaid" | "partial" | "paid" | "overpaid";

interface UnitRecord {
  id: string;
  unit_number: string;
  rent_light: RentLight;
  monthly_rent: number;
  tenant_name?: string;
  invoice_balance?: number;
  total_paid?: number;
  condition_notes?: string;
  status?: string;
}

interface Floor {
  rooms: UnitRecord[];
  label: string;
}

type Face = "overview" | "front" | "back" | "left" | "right" | "directory";

type SavedLayout = { version: 1; building_type: string; sections: { id: string; name: string; kind: string; levels: { id: string; label: string; order: number }[]; faces: { id: string; label: string; orientation: string }[] }[]; placements: { unit_id: string; section_id: string; level_id: string; face_id: string; position: number }[] };

interface Props {
  propertyId: string;
  floors: Floor[];
  counts: Record<string, number>;
  propertyName?: string;
  totalUnits: number;
  occupied?: number;
  rooms: UnitRecord[];
  onRoomClick: (room: UnitRecord) => void;
  activeRoomId?: string | null;
}

const FACES: { id: Face; label: string; description: string; icon: typeof Building2 }[] = [
  { id: "overview", label: "Overview", description: "Property overview", icon: Compass },
  { id: "front", label: "Front", description: "Front elevation", icon: Building2 },
  { id: "back", label: "Back", description: "Rear elevation", icon: ArrowUpRight },
  { id: "left", label: "Left side", description: "Left elevation", icon: ArrowLeftRight },
  { id: "right", label: "Right side", description: "Right elevation", icon: ArrowDownLeft },
  { id: "directory", label: "Unit directory", description: "All units", icon: LayoutGrid },
];

const STATUS: Record<string, { label: string; className: string }> = {
  vacant: { label: "Vacant", className: "border-sky-500/25 bg-sky-500/10 text-sky-300" },
  unpaid: { label: "Rent due", className: "border-rose-500/25 bg-rose-500/10 text-rose-300" },
  partial: { label: "Part-paid", className: "border-amber-500/25 bg-amber-500/10 text-amber-300" },
  paid: { label: "Paid", className: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" },
  overpaid: { label: "Credit", className: "border-cyan-500/25 bg-cyan-500/10 text-cyan-300" },
};

const money = (value?: number) => (value ?? 0).toLocaleString("en-KE", { maximumFractionDigits: 0 });

export default function PropertyLayoutExplorer({
  propertyId,
  floors,
  counts,
  propertyName,
  totalUnits,
  occupied,
  rooms,
  onRoomClick,
  activeRoomId,
}: Props) {
  const [face, setFace] = useState<Face>("overview");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [editorOpen, setEditorOpen] = useState(false);
  const [layoutConfig, setLayoutConfig] = useState<SavedLayout | null>(null);

  useEffect(() => {
    let active = true;
    if (!propertyId) { setLayoutConfig(null); return; }
    getPropertyLayout(propertyId).then((result) => { if (active) setLayoutConfig(result?.layout_config ?? null); }).catch(() => { if (active) setLayoutConfig(null); });
    return () => { active = false; };
  }, [propertyId]);

  const filteredRooms = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return [...rooms]
      .filter((room) => !normalized || room.unit_number.toLowerCase().includes(normalized) || (room.tenant_name ?? "").toLowerCase().includes(normalized))
      .filter((room) => statusFilter === "all" || (room.rent_light ?? "vacant") === statusFilter)
      .sort((a, b) => a.unit_number.localeCompare(b.unit_number, undefined, { numeric: true }));
  }, [rooms, query, statusFilter]);

  const currentFace = FACES.find((item) => item.id === face) ?? FACES[0];
  const mappedUnitRows = (layoutConfig?.placements ?? []).flatMap((placement) => {
    const section = layoutConfig?.sections.find((item) => item.id === placement.section_id);
    const mappedFace = section?.faces.find((item) => item.id === placement.face_id);
    const room = rooms.find((item) => item.id === placement.unit_id);
    if (!section || mappedFace?.orientation !== face || !room) return [];
    const level = section.levels.find((item) => item.id === placement.level_id);
    return [{ placement, section, level, room, mappedFace }];
  }).sort((a, b) => a.placement.position - b.placement.position);
  const showCanvas = face === "overview" || (face === "front" && mappedUnitRows.length === 0);

  return (
    <section className="overflow-hidden">
      <div className="flex items-start justify-between gap-3 px-3 pt-3 pb-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-slate-100">{propertyName || "Selected property"}</p>
          <p className="mt-0.5 text-[10px] text-slate-500">Explore the property and open any unit's live records</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
        {propertyId && <button type="button" onClick={() => setEditorOpen(true)} className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-2 text-[10px] font-semibold text-emerald-200"><Settings2 className="h-3.5 w-3.5" /> Configure</button>}
        <div className="rounded-lg border border-slate-700/70 bg-slate-900/70 px-2.5 py-1.5 text-right">
          <p className="text-xs font-semibold text-white">{totalUnits} units</p>
          <p className="text-[10px] text-slate-500">{occupied ?? 0} occupied</p>
        </div>
        </div>
      </div>

      <div className="flex gap-1 overflow-x-auto border-y border-white/[0.05] bg-slate-950/50 px-3 py-2 scrollbar-thin" role="tablist" aria-label="Property view">
        {FACES.map((item) => {
          const Icon = item.icon;
          const active = face === item.id;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setFace(item.id)}
              className={`flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-2 text-[10px] font-medium transition ${active
                ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-200"
                : "border-transparent text-slate-400 hover:border-slate-700 hover:bg-slate-800/70 hover:text-slate-200"}`}
            >
              <Icon className="h-3.5 w-3.5" />
              {item.label}
            </button>
          );
        })}
      </div>

      {showCanvas ? (
        <BuildingCanvas
          floors={floors}
          counts={counts}
          propertyName={propertyName}
          totalUnits={totalUnits}
          occupied={occupied}
          onRoomClick={onRoomClick}
          activeRoomId={activeRoomId}
        />
      ) : face === "directory" ? (
        <div className="min-h-[250px] bg-slate-950/60 p-3 sm:p-4">
          <div className="mb-3 flex flex-col gap-2 sm:flex-row">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search unit or tenant…"
              aria-label="Search units or tenants"
              className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-100 outline-none placeholder:text-slate-600 focus:border-emerald-500/60"
            />
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              aria-label="Filter units by rent status"
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200 outline-none focus:border-emerald-500/60"
            >
              <option value="all">All rent statuses</option>
              <option value="vacant">Vacant</option>
              <option value="unpaid">Rent due</option>
              <option value="partial">Part-paid</option>
              <option value="paid">Paid</option>
              <option value="overpaid">Credit</option>
            </select>
          </div>
          {filteredRooms.length === 0 ? (
            <p className="py-10 text-center text-xs text-slate-500">No units match these filters.</p>
          ) : (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {filteredRooms.map((room) => {
                const status = STATUS[room.rent_light ?? "vacant"] ?? STATUS.vacant;
                const active = activeRoomId === room.id;
                return (
                  <button
                    key={room.id}
                    type="button"
                    onClick={() => onRoomClick(room)}
                    className={`rounded-xl border p-3 text-left transition ${active
                      ? "border-emerald-400/50 bg-emerald-500/10"
                      : "border-slate-800 bg-slate-900/70 hover:border-slate-600 hover:bg-slate-900"}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="flex min-w-0 items-center gap-2 text-sm font-semibold text-slate-100">
                        <DoorOpen className="h-4 w-4 shrink-0 text-emerald-400" />
                        <span className="truncate">{room.unit_number}</span>
                      </span>
                      <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[9px] ${status.className}`}>{status.label}</span>
                    </div>
                    <p className="mt-2 truncate text-xs text-slate-400">{room.tenant_name || "No tenant assigned"}</p>
                    <div className="mt-3 flex items-end justify-between gap-2">
                      <div>
                        <p className="text-[9px] uppercase tracking-wide text-slate-600">Monthly rent</p>
                        <p className="text-xs font-semibold text-slate-200">KES {money(room.monthly_rent)}</p>
                      </div>
                      {typeof room.invoice_balance === "number" && room.invoice_balance > 0 && (
                        <div className="text-right">
                          <p className="text-[9px] uppercase tracking-wide text-slate-600">Balance</p>
                          <p className="text-xs font-semibold text-rose-300">KES {money(room.invoice_balance)}</p>
                        </div>
                      )}
                    </div>
                    {room.condition_notes && <p className="mt-2 line-clamp-2 text-[10px] text-amber-300/80">{room.condition_notes}</p>}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        <div className="min-h-[250px] bg-slate-950/60 p-4 sm:p-6">
          <div className="mx-auto flex max-w-xl flex-col items-center text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-700 bg-slate-900 text-emerald-300">
              <MapPinned className="h-5 w-5" />
            </div>
            <h3 className="mt-3 text-sm font-semibold text-white">{currentFace.label} view</h3>
            {mappedUnitRows.length > 0 ? (
              <div className="mt-4 w-full space-y-3 text-left">
                {mappedUnitRows.map(({ placement, section, level, room, mappedFace }) => (
                  <button key={room.id} type="button" onClick={() => onRoomClick(room)} className="flex w-full items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/70 p-3 text-left hover:border-emerald-500/40">
                    <div><p className="text-xs font-semibold text-white">{room.unit_number}</p><p className="mt-1 text-[10px] text-slate-500">{section.name} · {level?.label ?? "Floor not set"} · {mappedFace.label} · position {placement.position}</p></div>
                    <span className="text-[10px] text-slate-300">{room.tenant_name || "Vacant"}</span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="mt-1 max-w-md text-xs leading-5 text-slate-400">
                This face is ready to map, but unit positions have not been configured for it yet. We won't guess which rooms belong on this side of the building.
              </p>
            )}
            <div className="mt-4 grid w-full grid-cols-3 gap-2">
              <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-[10px] text-slate-500">Units</p>
                <p className="mt-1 text-lg font-semibold text-white">{totalUnits}</p>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-[10px] text-slate-500">Rent due</p>
                <p className="mt-1 text-lg font-semibold text-rose-300">{counts.unpaid ?? 0}</p>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-[10px] text-slate-500">Part-paid</p>
                <p className="mt-1 text-lg font-semibold text-amber-300">{counts.partial ?? 0}</p>
              </div>
            </div>
            <button type="button" onClick={() => setFace("directory")} className="mt-4 inline-flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-200 hover:bg-emerald-500/15">
              <LayoutGrid className="h-3.5 w-3.5" />
              Browse the real unit records
            </button>
          </div>
        </div>
      )}
      {editorOpen && propertyId && <PropertyLayoutEditor propertyId={propertyId} rooms={rooms} onClose={() => setEditorOpen(false)} onSaved={(config) => { setLayoutConfig(config); setEditorOpen(false); }} />}
    </section>
  );
}
