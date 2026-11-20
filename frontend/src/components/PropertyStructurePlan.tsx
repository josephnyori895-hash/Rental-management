import { Building2, DoorOpen, Home, Layers3, Users } from "lucide-react";

type RentalUnit = {
  id: string;
  unit_number: string;
  unit_type?: string;
  rent_light?: "vacant" | "unpaid" | "partial" | "paid" | "overpaid";
  tenant_name?: string | null;
  monthly_rent?: number;
};

type InternalSpace = {
  id: string;
  label: string;
  kind: string;
  rentable_unit_id?: string | null;
};

type Level = {
  id: string;
  label: string;
  order?: number;
  spaces?: InternalSpace[];
};

type Section = {
  id: string;
  name: string;
  kind?: string;
  levels?: Level[];
};

type Placement = {
  unit_id: string;
  section_id: string;
  level_id: string;
  position: number;
};

interface Props {
  propertyName?: string;
  sections: Section[];
  placements: Placement[];
  units: RentalUnit[];
  onUnitClick?: (unit: RentalUnit) => void;
  activeUnitId?: string | null;
}

const statusStyles: Record<string, string> = {
  vacant: "border-sky-500/25 bg-sky-500/5 text-sky-200",
  unpaid: "border-rose-500/25 bg-rose-500/5 text-rose-200",
  partial: "border-amber-500/25 bg-amber-500/5 text-amber-200",
  paid: "border-emerald-500/25 bg-emerald-500/5 text-emerald-200",
  overpaid: "border-cyan-500/25 bg-cyan-500/5 text-cyan-200",
};

const statusLabel: Record<string, string> = {
  vacant: "Vacant", unpaid: "Payment due", partial: "Part-paid",
  paid: "Paid", overpaid: "Credit",
};

const kindLabel = (kind: string) => kind.replaceAll("_", " ").replace(/\\b\\w/g, (letter) => letter.toUpperCase());

export default function PropertyStructurePlan({
  propertyName, sections, placements, units, onUnitClick, activeUnitId,
}: Props) {
  const unitById = new Map(units.map((unit) => [unit.id, unit]));
  const placedIds = new Set(placements.map((placement) => placement.unit_id));
  const assigned = new Set<string>();

  const unitCard = (unit: RentalUnit) => (
    <button
      key={unit.id}
      type="button"
      onClick={() => onUnitClick?.(unit)}
      className={`min-w-0 rounded-xl border p-3 text-left transition hover:-translate-y-0.5 hover:border-emerald-400/50 hover:bg-slate-800/80 ${statusStyles[unit.rent_light ?? "vacant"] ?? statusStyles.vacant} ${activeUnitId === unit.id ? "ring-2 ring-emerald-400/70" : ""}`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2 text-xs font-semibold text-slate-100">
          <Home className="h-3.5 w-3.5 shrink-0 text-emerald-300" />
          <span className="truncate">{unit.unit_number}</span>
        </span>
        <span className="shrink-0 text-[9px] uppercase tracking-wide opacity-80">{statusLabel[unit.rent_light ?? "vacant"] ?? "Status unknown"}</span>
      </div>
      <p className="mt-1 truncate text-[10px] text-slate-400">{kindLabel(unit.unit_type ?? "rental unit")}</p>
      <p className="mt-2 truncate text-[10px] text-slate-300">{unit.tenant_name || "No active tenant"}</p>
    </button>
  );

  return (
    <div className="space-y-4 p-3 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-300/80">Property structure map</p>
          <h3 className="mt-1 text-sm font-semibold text-white">{propertyName || "Your property"}</h3>
          <p className="mt-1 text-[11px] text-slate-500">A schematic of your saved structure, not a measured architectural drawing</p>
        </div>
        <div className="flex flex-wrap gap-2 text-[10px] text-slate-400">
          <span className="rounded-full border border-slate-700 px-2 py-1">{sections.length} {sections.length === 1 ? "structure" : "structures"}</span>
          <span className="rounded-full border border-slate-700 px-2 py-1">{units.length} rentable units</span>
        </div>
      </div>

      {sections.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 px-5 py-10 text-center">
          <Building2 className="mx-auto h-8 w-8 text-slate-600" />
          <p className="mt-3 text-sm font-medium text-slate-300">Your layout is ready to be configured</p>
          <p className="mx-auto mt-1 max-w-md text-xs leading-5 text-slate-500">Add the real buildings, wings and floors for this property. Rental units remain available below until you place them in the structure.</p>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {sections.map((section) => {
            const levels = [...(section.levels ?? [])].sort((a, b) => (b.order ?? 0) - (a.order ?? 0));
            return (
              <section key={section.id} className="min-w-0 overflow-hidden rounded-2xl border border-slate-700/80 bg-slate-900/60">
                <header className="flex items-center justify-between gap-3 border-b border-slate-700/70 bg-slate-800/50 px-4 py-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <Layers3 className="h-4 w-4 shrink-0 text-emerald-300" />
                    <div className="min-w-0">
                      <h4 className="truncate text-xs font-semibold text-slate-100">{section.name}</h4>
                      <p className="text-[10px] capitalize text-slate-500">{section.kind ?? "building"} · {levels.length} levels</p>
                    </div>
                  </div>
                  <Building2 className="h-4 w-4 shrink-0 text-slate-600" />
                </header>
                <div className="space-y-3 p-3">
                  {levels.map((level) => {
                    const levelPlacements = placements
                      .filter((placement) => placement.section_id === section.id && placement.level_id === level.id)
                      .sort((a, b) => a.position - b.position);
                    const levelUnits = levelPlacements.map((placement) => unitById.get(placement.unit_id)).filter((unit): unit is RentalUnit => Boolean(unit));
                    levelUnits.forEach((unit) => assigned.add(unit.id));
                    const spaces = level.spaces ?? [];
                    const commonSpaces = spaces.filter((space) => !space.rentable_unit_id);
                    return (
                      <article key={level.id} className="rounded-xl border border-slate-700/60 bg-slate-950/60 p-3">
                        <div className="mb-3 flex items-center justify-between gap-2">
                          <h5 className="text-[11px] font-semibold text-emerald-200">{level.label}</h5>
                          <span className="text-[9px] text-slate-500">{levelUnits.length} units · {spaces.length} spaces</span>
                        </div>
                        {levelUnits.length > 0 ? (
                          <div className="grid gap-2 sm:grid-cols-2">{levelUnits.map(unitCard)}</div>
                        ) : (
                          <p className="rounded-lg border border-dashed border-slate-800 px-3 py-3 text-[10px] text-slate-600">No rentable units placed on this level</p>
                        )}
                        {spaces.length > 0 && (
                          <div className="mt-3 border-t border-slate-800 pt-3">
                            <p className="mb-2 flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-wide text-slate-500"><DoorOpen className="h-3 w-3" /> Internal and shared spaces</p>
                            <div className="flex flex-wrap gap-1.5">
                              {spaces.map((space) => {
                                const containingUnit = space.rentable_unit_id ? unitById.get(space.rentable_unit_id) : undefined;
                                return <span key={space.id} className="rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-[10px] text-slate-300">
                                  {space.label}<span className="ml-1 text-slate-500">· {kindLabel(space.kind)}{containingUnit ? ` · ${containingUnit.unit_number}` : " · shared"}</span>
                                </span>;
                              })}
                            </div>
                          </div>
                        )}
                        {commonSpaces.length > 0 && <p className="mt-2 flex items-center gap-1 text-[9px] text-slate-500"><Users className="h-3 w-3" /> Shared facilities are not separately rentable</p>}
                      </article>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      )}

      {units.filter((unit) => !placedIds.has(unit.id)).length > 0 && (
        <section className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/30 p-3 sm:p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h4 className="text-xs font-semibold text-slate-200">Unassigned rentable units</h4>
            <span className="text-[10px] text-slate-500">{units.filter((unit) => !placedIds.has(unit.id)).length} not yet placed</span>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {units.filter((unit) => !placedIds.has(unit.id)).map(unitCard)}
          </div>
        </section>
      )}
    </div>
  );
}
