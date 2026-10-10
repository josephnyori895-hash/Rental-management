import { useEffect, useMemo, useState } from "react";
import { Check, Plus, Save, Trash2, X } from "lucide-react";
import { getPropertyLayout, savePropertyLayout } from "../lib/api";

type Orientation = "front" | "back" | "left" | "right" | "interior";
type LayoutLevel = { id: string; label: string; order: number };
type LayoutFace = { id: string; label: string; orientation: Orientation };
type LayoutSection = {
  id: string;
  name: string;
  kind: "block" | "wing" | "entrance" | "standalone";
  levels: LayoutLevel[];
  faces: LayoutFace[];
};
type UnitPlacement = {
  unit_id: string;
  section_id: string;
  level_id: string;
  face_id: string;
  position: number;
};
type LayoutConfig = {
  version: 1;
  building_type: "hostel" | "apartment" | "building" | "house" | "commercial" | "mixed_use" | "compound";
  sections: LayoutSection[];
  placements: UnitPlacement[];
};
type UnitOption = { id: string; unit_number: string; tenant_name?: string };

interface Props {
  propertyId: string;
  rooms: UnitOption[];
  onClose: () => void;
  onSaved: (config: LayoutConfig) => void;
}

const newId = () => crypto.randomUUID();
const makeSection = (name: string, kind: LayoutSection["kind"] = "block"): LayoutSection => ({
  id: newId(),
  name,
  kind,
  levels: [{ id: newId(), label: "Ground floor", order: 0 }],
  faces: [
    { id: newId(), label: "Front", orientation: "front" },
    { id: newId(), label: "Back", orientation: "back" },
    { id: newId(), label: "Left side", orientation: "left" },
    { id: newId(), label: "Right side", orientation: "right" },
  ],
});

const emptyConfig: LayoutConfig = {
  version: 1,
  building_type: "building",
  sections: [],
  placements: [],
};

export default function PropertyLayoutEditor({ propertyId, rooms, onClose, onSaved }: Props) {
  const [config, setConfig] = useState<LayoutConfig>(emptyConfig);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [savedMessage, setSavedMessage] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    getPropertyLayout(propertyId)
      .then((result) => {
        if (!active) return;
        setConfig(result?.layout_config ?? emptyConfig);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Could not load saved layout.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [propertyId]);

  const placementsByUnit = useMemo(
    () => new Map(config.placements.map((placement) => [placement.unit_id, placement])),
    [config.placements],
  );

  const updateSection = (sectionId: string, update: (section: LayoutSection) => LayoutSection) => {
    setConfig((current) => ({
      ...current,
      sections: current.sections.map((section) => section.id === sectionId ? update(section) : section),
    }));
  };

  const addSection = () => {
    const section = makeSection(`Block ${config.sections.length + 1}`);
    setConfig((current) => ({ ...current, sections: [...current.sections, section] }));
    setSavedMessage("");
  };

  const removeSection = (sectionId: string) => {
    const section = config.sections.find((item) => item.id === sectionId);
    setConfig((current) => ({
      ...current,
      sections: current.sections.filter((item) => item.id !== sectionId),
      placements: current.placements.filter((item) => item.section_id !== sectionId),
    }));
    if (section) setSavedMessage("");
  };

  const assignUnit = (unitId: string, sectionId: string) => {
    if (!sectionId) {
      setConfig((current) => ({ ...current, placements: current.placements.filter((p) => p.unit_id !== unitId) }));
      return;
    }
    const section = config.sections.find((item) => item.id === sectionId);
    if (!section?.levels.length || !section.faces.length) {
      setError("Add at least one floor and one face to this section before assigning units.");
      return;
    }
    const existing = placementsByUnit.get(unitId);
    const placement: UnitPlacement = {
      unit_id: unitId,
      section_id: sectionId,
      level_id: existing?.section_id === sectionId ? existing.level_id : section.levels[0].id,
      face_id: existing?.section_id === sectionId ? existing.face_id : section.faces[0].id,
      position: existing?.position ?? config.placements.length,
    };
    setConfig((current) => ({
      ...current,
      placements: [...current.placements.filter((p) => p.unit_id !== unitId), placement],
    }));
    setError("");
    setSavedMessage("");
  };

  const updatePlacement = (unitId: string, field: "level_id" | "face_id" | "position", value: string) => {
    setConfig((current) => ({
      ...current,
      placements: current.placements.map((p) => p.unit_id === unitId
        ? { ...p, [field]: field === "position" ? Number(value) || 0 : value }
        : p),
    }));
    setSavedMessage("");
  };

  const addLevel = (sectionId: string) => updateSection(sectionId, (section) => ({
    ...section,
    levels: [...section.levels, {
      id: newId(),
      label: `Floor ${section.levels.length}`,
      order: section.levels.length,
    }],
  }));

  const addFace = (sectionId: string) => updateSection(sectionId, (section) => ({
    ...section,
    faces: [...section.faces, {
      id: newId(),
      label: `Face ${section.faces.length + 1}`,
      orientation: "interior",
    }],
  }));

  const save = async () => {
    setSaving(true);
    setError("");
    setSavedMessage("");
    try {
      await savePropertyLayout(propertyId, config);
      onSaved(config);
      setSavedMessage("Layout saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save layout.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-3 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="layout-editor-title">
      <div className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl">
        <header className="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3 sm:px-6">
          <div>
            <h2 id="layout-editor-title" className="text-sm font-semibold text-white">Configure property layout</h2>
            <p className="mt-1 text-xs text-slate-400">Map existing units to blocks, floors and faces. Rental records stay unchanged.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close layout editor" className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"><X className="h-4 w-4" /></button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-6">
          {loading ? <p className="py-12 text-center text-sm text-slate-400">Loading saved layout…</p> : (
            <>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <label className="flex flex-col gap-1 text-xs text-slate-400">
                  Property structure
                  <select value={config.building_type} onChange={(event) => setConfig((current) => ({ ...current, building_type: event.target.value as LayoutConfig["building_type"] }))} className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100">
                    <option value="hostel">Hostel / bedsitters</option>
                    <option value="apartment">Apartment block</option>
                    <option value="building">Building</option>
                    <option value="house">House</option>
                    <option value="commercial">Commercial</option>
                    <option value="mixed_use">Mixed-use</option>
                    <option value="compound">Compound / multiple buildings</option>
                  </select>
                </label>
                <button type="button" onClick={addSection} className="inline-flex items-center justify-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-200 hover:bg-emerald-500/15"><Plus className="h-4 w-4" /> Add block or wing</button>
              </div>

              {config.sections.length === 0 && (
                <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center">
                  <p className="text-sm font-medium text-slate-200">Start with the real structure</p>
                  <p className="mt-1 text-xs text-slate-500">Add a block or wing, then assign units to its floors and faces.</p>
                  <button type="button" onClick={addSection} className="mt-4 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-semibold text-slate-950">Create first block</button>
                </div>
              )}

              {config.sections.map((section) => (
                <section key={section.id} className="space-y-3 rounded-xl border border-slate-800 bg-slate-900/60 p-3 sm:p-4">
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <input value={section.name} aria-label="Block or wing name" onChange={(event) => updateSection(section.id, (current) => ({ ...current, name: event.target.value }))} className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" />
                    <select value={section.kind} aria-label="Section type" onChange={(event) => updateSection(section.id, (current) => ({ ...current, kind: event.target.value as LayoutSection["kind"] }))} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200">
                      <option value="block">Building block</option><option value="wing">Wing</option><option value="entrance">Entrance</option><option value="standalone">Standalone building</option>
                    </select>
                    <button type="button" onClick={() => removeSection(section.id)} className="inline-flex items-center justify-center gap-1 rounded-lg border border-rose-500/20 px-3 py-2 text-xs text-rose-300 hover:bg-rose-500/10"><Trash2 className="h-3.5 w-3.5" /> Remove</button>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between"><p className="text-xs font-semibold text-slate-300">Floors / levels</p><button type="button" onClick={() => addLevel(section.id)} className="text-xs text-emerald-300">+ Add floor</button></div>
                      {section.levels.map((level) => <div key={level.id} className="flex gap-2"><input value={level.label} aria-label="Floor label" onChange={(event) => updateSection(section.id, (current) => ({ ...current, levels: current.levels.map((item) => item.id === level.id ? { ...item, label: event.target.value } : item) }))} className="min-w-0 flex-1 rounded-lg border border-slate-800 bg-slate-950 px-2.5 py-2 text-xs text-slate-200" /><span className="self-center text-[10px] text-slate-600">Order {level.order}</span></div>)}
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between"><p className="text-xs font-semibold text-slate-300">Faces / entrances</p><button type="button" onClick={() => addFace(section.id)} className="text-xs text-emerald-300">+ Add face</button></div>
                      {section.faces.map((face) => <div key={face.id} className="grid grid-cols-[1fr_110px] gap-2"><input value={face.label} aria-label="Face label" onChange={(event) => updateSection(section.id, (current) => ({ ...current, faces: current.faces.map((item) => item.id === face.id ? { ...item, label: event.target.value } : item) }))} className="min-w-0 rounded-lg border border-slate-800 bg-slate-950 px-2.5 py-2 text-xs text-slate-200" /><select value={face.orientation} aria-label="Face orientation" onChange={(event) => updateSection(section.id, (current) => ({ ...current, faces: current.faces.map((item) => item.id === face.id ? { ...item, orientation: event.target.value as Orientation } : item) }))} className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-2 text-xs text-slate-300"><option value="front">Front</option><option value="back">Back</option><option value="left">Left</option><option value="right">Right</option><option value="interior">Interior</option></select></div>)}
                    </div>
                  </div>
                </section>
              ))}

              <section className="space-y-3">
                <div><h3 className="text-sm font-semibold text-white">Assign units</h3><p className="mt-1 text-xs text-slate-500">Each unit can be mapped once. Existing tenant and rent data is read-only here.</p></div>
                {rooms.length === 0 ? <p className="rounded-lg border border-slate-800 p-4 text-xs text-slate-500">No units are available for this property yet.</p> : rooms.map((room) => {
                  const placement = placementsByUnit.get(room.id);
                  const section = config.sections.find((item) => item.id === placement?.section_id);
                  return <div key={room.id} className="grid gap-2 rounded-lg border border-slate-800 bg-slate-900/50 p-3 md:grid-cols-[minmax(110px,0.7fr)_minmax(130px,1fr)_minmax(130px,1fr)_minmax(130px,1fr)] md:items-center">
                    <div><p className="text-xs font-semibold text-white">{room.unit_number}</p><p className="truncate text-[10px] text-slate-500">{room.tenant_name || "Vacant"}</p></div>
                    <select value={placement?.section_id ?? ""} onChange={(event) => assignUnit(room.id, event.target.value)} aria-label={`Block for unit ${room.unit_number}`} className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-2 text-xs text-slate-200"><option value="">Not mapped</option>{config.sections.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
                    <select value={placement?.level_id ?? ""} disabled={!section} onChange={(event) => updatePlacement(room.id, "level_id", event.target.value)} aria-label={`Floor for unit ${room.unit_number}`} className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-2 text-xs text-slate-200"><option value="">Choose floor</option>{section?.levels.map((level) => <option key={level.id} value={level.id}>{level.label}</option>)}</select>
                    <select value={placement?.face_id ?? ""} disabled={!section} onChange={(event) => updatePlacement(room.id, "face_id", event.target.value)} aria-label={`Face for unit ${room.unit_number}`} className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-2 text-xs text-slate-200"><option value="">Choose face</option>{section?.faces.map((face) => <option key={face.id} value={face.id}>{face.label}</option>)}</select>
                    {placement && <label className="flex items-center gap-2 text-[10px] text-slate-500 md:col-span-4">Position on face<input type="number" min="0" max="10000" value={placement.position} onChange={(event) => updatePlacement(room.id, "position", event.target.value)} className="w-24 rounded-lg border border-slate-800 bg-slate-950 px-2 py-1.5 text-xs text-white" /></label>}
                  </div>;
                })}
              </section>
            </>
          )}
          {error && <p role="alert" className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-200">{error}</p>}
          {savedMessage && <p role="status" className="flex items-center gap-2 text-xs text-emerald-300"><Check className="h-4 w-4" />{savedMessage}</p>}
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-slate-800 bg-slate-950 px-4 py-3 sm:px-6">
          <p className="text-[10px] text-slate-500">{config.placements.length} of {rooms.length} units mapped</p>
          <div className="flex gap-2"><button type="button" onClick={onClose} className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800">Cancel</button><button type="button" disabled={loading || saving} onClick={save} className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50"><Save className="h-3.5 w-3.5" />{saving ? "Saving…" : "Save layout"}</button></div>
        </footer>
      </div>
    </div>
  );
}
