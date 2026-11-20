import { useRef, type PointerEvent } from "react";

export type LayoutGeometry = {
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
};

export type LayoutCanvasItem = LayoutGeometry & {
  id: string;
  label: string;
  kind: "unit" | "space";
};

interface Props {
  items: LayoutCanvasItem[];
  onGeometryChange: (id: string, geometry: Partial<LayoutGeometry>) => void;
}

type Gesture = {
  id: string;
  mode: "move" | "resize";
  pointerId: number;
  startX: number;
  startY: number;
  initial: LayoutGeometry;
};

export default function PropertyLayoutCanvas({ items, onGeometryChange }: Props) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const gesture = useRef<Gesture | null>(null);

  const begin = (
    event: PointerEvent<HTMLElement>,
    item: LayoutCanvasItem,
    mode: Gesture["mode"],
  ) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    gesture.current = {
      id: item.id,
      mode,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      initial: {
        x: item.x, y: item.y, width: item.width,
        height: item.height, rotation: item.rotation,
      },
    };
  };

  const move = (event: PointerEvent<HTMLElement>) => {
    const active = gesture.current;
    const bounds = canvasRef.current?.getBoundingClientRect();
    if (!active || active.pointerId !== event.pointerId || !bounds?.width || !bounds.height) return;
    const dx = Math.round((event.clientX - active.startX) / bounds.width * 1000);
    const dy = Math.round((event.clientY - active.startY) / bounds.height * 1000);
    if (active.mode === "move") {
      onGeometryChange(active.id, {
        x: Math.max(0, Math.min(1000 - active.initial.width, active.initial.x + dx)),
        y: Math.max(0, Math.min(1000 - active.initial.height, active.initial.y + dy)),
      });
    } else {
      onGeometryChange(active.id, {
        width: Math.max(10, Math.min(1000 - active.initial.x, active.initial.width + dx)),
        height: Math.max(10, Math.min(1000 - active.initial.y, active.initial.height + dy)),
      });
    }
  };

  const end = (event: PointerEvent<HTMLElement>) => {
    if (gesture.current?.pointerId === event.pointerId) gesture.current = null;
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Arrange this floor</p>
        <p className="text-[10px] text-slate-500">Drag a room to move · drag its corner to resize</p>
      </div>
      <div ref={canvasRef} className="relative aspect-square w-full touch-none overflow-hidden rounded-xl border border-slate-700 bg-[linear-gradient(rgba(148,163,184,.08)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,.08)_1px,transparent_1px)] bg-[size:5%_5%]">
        {items.length === 0 && <p className="absolute inset-0 flex items-center justify-center px-5 text-center text-xs text-slate-600">Assign units or add internal rooms to begin arranging this floor.</p>}
        {items.map((item) => (
          <div
            key={item.id}
            className={`absolute flex min-h-0 min-w-0 flex-col overflow-hidden rounded-md border shadow-sm ${item.kind === "unit" ? "border-emerald-400/50 bg-emerald-950/80" : "border-sky-400/40 bg-sky-950/80"}`}
            style={{
              left: `${item.x / 10}%`,
              top: `${item.y / 10}%`,
              width: `${item.width / 10}%`,
              height: `${item.height / 10}%`,
              transform: `rotate(${item.rotation}deg)`,
              transformOrigin: "center",
            }}
          >
            <div
              role="group"
              tabIndex={0}
              aria-label={`Move ${item.label}`}
              onPointerDown={(event) => begin(event, item, "move")}
              onPointerMove={move}
              onPointerUp={end}
              onPointerCancel={end}
              onKeyDown={(event) => {
                const step = event.shiftKey ? 25 : 5;
                const delta = event.key === "ArrowLeft" ? { x: -step } : event.key === "ArrowRight" ? { x: step } : event.key === "ArrowUp" ? { y: -step } : event.key === "ArrowDown" ? { y: step } : null;
                if (delta) {
                  event.preventDefault();
                  onGeometryChange(item.id, {
                    x: Math.max(0, Math.min(1000 - item.width, item.x + (delta.x ?? 0))),
                    y: Math.max(0, Math.min(1000 - item.height, item.y + (delta.y ?? 0))),
                  });
                }
              }}
              className="flex min-h-0 flex-1 cursor-grab select-none items-center justify-center overflow-hidden px-1 text-center text-[9px] font-medium leading-tight text-slate-100 active:cursor-grabbing"
              title="Drag to move. Use arrow keys to move precisely."
            >
              {item.label}
            </div>
            <button
              type="button"
              aria-label={`Resize ${item.label}`}
              onPointerDown={(event) => begin(event, item, "resize")}
              onPointerMove={move}
              onPointerUp={end}
              onPointerCancel={end}
              onKeyDown={(event) => {
                const step = event.shiftKey ? 25 : 5;
                const delta = event.key === "ArrowLeft" ? { width: -step } : event.key === "ArrowRight" ? { width: step } : event.key === "ArrowUp" ? { height: -step } : event.key === "ArrowDown" ? { height: step } : null;
                if (delta) {
                  event.preventDefault();
                  onGeometryChange(item.id, {
                    width: Math.max(10, Math.min(1000 - item.x, item.width + (delta.width ?? 0))),
                    height: Math.max(10, Math.min(1000 - item.y, item.height + (delta.height ?? 0))),
                  });
                }
              }}
              className="absolute bottom-0 right-0 h-4 w-4 cursor-nwse-resize rounded-tl border-l border-t border-white/30 bg-white/20"
              title="Drag to resize or use arrow keys"
            />
          </div>
        ))}
      </div>
    </div>
  );
}
