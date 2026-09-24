import { useRef, useEffect, useCallback, useState } from "react";

const money = (n: number) => (n ?? 0).toLocaleString("en-KE");

type Light = "vacant" | "unpaid" | "partial" | "paid" | "overpaid";

interface Room {
  id: string; unit_number: string; rent_light: Light;
  monthly_rent: number; tenant_name?: string; invoice_balance?: number;
}

interface Floor { rooms: Room[]; label: string; }

const LIGHT: Record<Light, string> = {
  vacant: "#1a1a2e", unpaid: "#f43f5e", partial: "#f59e0b",
  paid: "#34d399", overpaid: "#38bdf8",
};

const LIGHT_LABEL: Record<Light, string> = {
  vacant: "V", unpaid: "!", partial: "~", paid: "$", overpaid: "+",
};

interface Props {
  floors: Floor[]; counts: Record<string, number>;
  propertyName?: string; totalUnits?: number; occupied?: number;
  onRoomClick?: (room: Room) => void; activeRoomId?: string | null;
}

export default function BlueprintCanvas({
  floors, onRoomClick, activeRoomId,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hovered, setHovered] = useState<{ fi: number; ri: number } | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; room: Room } | null>(null);
  const rectsRef = useRef<Map<string, { x: number; y: number; w: number; h: number }>>(new Map());
  const sizeRef = useRef({ w: 800, h: 500 });

  const draw = useCallback((ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.clearRect(0, 0, w, h);

    /* Background — blueprint grid */
    ctx.fillStyle = "#0c1729";
    ctx.fillRect(0, 0, w, h);

    /* Grid lines */
    ctx.strokeStyle = "rgba(56,189,248,0.05)";
    ctx.lineWidth = 0.5;
    for (let x = 0; x < w; x += 30) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    }
    for (let y = 0; y < h; y += 30) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }

    if (!floors.length) return;

    const totalRooms = floors.reduce((s, f) => s + f.rooms.length, 0);
    const maxPerFloor = Math.max(...floors.map(f => f.rooms.length), 1);
    const padX = 40;
    const padY = 30;
    const availW = w - padX * 2;
    const availH = h - padY * 2 - 20;
    const floorH = Math.min(availH / floors.length, 70);
    const roomW = Math.min(availW / (maxPerFloor + 1), 65);
    const roomH = Math.max(floorH * 0.7, 24);
    const gutterH = floorH - roomH;

    rectsRef.current.clear();

    floors.forEach((floor, fi) => {
      const floorY = padY + fi * floorH + gutterH / 2;
      const roomsCount = floor.rooms.length;
      const totalW = roomsCount * roomW + (roomsCount - 1) * 4;
      const startX = (w - totalW) / 2;

      /* Floor label */
      ctx.fillStyle = "rgba(56,189,248,0.3)";
      ctx.font = "8px 'JetBrains Mono', monospace";
      ctx.textAlign = "right";
      ctx.fillText(floor.label, startX - 8, floorY + roomH / 2 + 3);

      floor.rooms.forEach((room, ri) => {
        const x = startX + ri * (roomW + 4);
        const y = floorY;
        const c = LIGHT[room.rent_light] || "#64748b";
        const isActive = activeRoomId === room.id;
        const isHov = hovered?.fi === fi && hovered?.ri === ri;

        rectsRef.current.set(`${fi}-${ri}`, { x, y, w: roomW, h: roomH });

        /* Room rect */
        ctx.fillStyle = isActive ? "rgba(52,211,153,0.15)" : isHov ? "rgba(56,189,248,0.12)" : "rgba(30,41,59,0.6)";
        ctx.strokeStyle = isActive ? "#34d399" : isHov ? "#38bdf8" : c + "60";
        ctx.lineWidth = isActive ? 2 : 1;
        ctx.beginPath();
        ctx.roundRect(x, y, roomW, roomH, 3);
        ctx.fill();
        ctx.stroke();

        /* Corner marks for blueprint feel */
        const cm = 4;
        ctx.strokeStyle = "rgba(56,189,248,0.15)";
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        ctx.moveTo(x, y + cm); ctx.lineTo(x, y); ctx.lineTo(x + cm, y);
        ctx.moveTo(x + roomW - cm, y); ctx.lineTo(x + roomW, y); ctx.lineTo(x + roomW, y + cm);
        ctx.moveTo(x + roomW, y + roomH - cm); ctx.lineTo(x + roomW, y + roomH); ctx.lineTo(x + roomW - cm, y + roomH);
        ctx.moveTo(x + cm, y + roomH); ctx.lineTo(x, y + roomH); ctx.lineTo(x, y + roomH - cm);
        ctx.stroke();

        /* Status dot */
        ctx.fillStyle = c;
        ctx.shadowColor = c + "60";
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.arc(x + 8, y + roomH / 2, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;

        /* Unit number */
        ctx.fillStyle = isActive ? "#34d399" : isHov ? "#e2e8f0" : "rgba(148,163,184,0.7)";
        ctx.font = "9px 'JetBrains Mono', monospace";
        ctx.textAlign = "left";
        ctx.fillText(room.unit_number, x + 14, y + roomH / 2 + 3);

        /* Tenant initial */
        if (room.tenant_name) {
          ctx.fillStyle = "rgba(148,163,184,0.35)";
          ctx.font = "7px 'JetBrains Mono', monospace";
          ctx.textAlign = "right";
          ctx.fillText(room.tenant_name.split(" ").map(s => s[0]).join(""), x + roomW - 4, y + roomH / 2 + 2);
        }
      });
    });

    /* Title */
    ctx.fillStyle = "rgba(56,189,248,0.15)";
    ctx.font = "7px 'JetBrains Mono', monospace";
    ctx.textAlign = "center";
    ctx.fillText("BLUEPRINT — FLOOR PLAN", w / 2, h - 8);
  }, [floors, activeRoomId, hovered]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      const w = parent.clientWidth;
      const h = Math.min(500, Math.max(350, w * 0.55));
      const dpr = window.devicePixelRatio || 1;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.scale(dpr, dpr);
      sizeRef.current = { w, h };
      draw(ctx, w, h);
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [draw]);

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !onRoomClick) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    for (const [key, r] of rectsRef.current) {
      if (mx >= r.x && mx <= r.x + r.w && my >= r.y && my <= r.y + r.h) {
        const [fi, ri] = key.split("-").map(Number);
        const room = floors[fi]?.rooms[ri];
        if (room) { onRoomClick(room); return; }
      }
    }
  }, [floors, onRoomClick]);

  const handleMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    let found: { fi: number; ri: number } | null = null;
    let room: Room | null = null;
    for (const [key, r] of rectsRef.current) {
      if (mx >= r.x && mx <= r.x + r.w && my >= r.y && my <= r.y + r.h) {
        const [fi, ri] = key.split("-").map(Number);
        found = { fi, ri };
        room = floors[fi]?.rooms[ri] || null;
        break;
      }
    }
    setHovered(found);
    canvas.style.cursor = found ? "pointer" : "default";
    setTooltip(found && room ? { x: e.clientX, y: e.clientY - 10, room } : null);
  }, [floors]);

  const handleLeave = useCallback(() => { setHovered(null); setTooltip(null); }, []);

  return (
    <div className="relative">
      <canvas ref={canvasRef} onClick={handleClick} onMouseMove={handleMove}
        onMouseLeave={handleLeave} className="block w-full rounded-xl" />
      {tooltip && (
        <div className="fixed z-50 pointer-events-none" style={{ left: tooltip.x + 14, top: tooltip.y - 10 }}>
          <div className="bg-slate-900/95 backdrop-blur-md border border-sky-700/60 rounded-xl px-3 py-2 shadow-2xl shadow-black/50 min-w-[140px]">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-bold text-white">Room {tooltip.room.unit_number}</span>
              <span className="text-[9px] font-medium px-1.5 py-0.5 rounded-full"
                style={{ background: LIGHT[tooltip.room.rent_light] + "25", color: LIGHT[tooltip.room.rent_light] }}>
                {LIGHT_LABEL[tooltip.room.rent_light]}
              </span>
            </div>
            {tooltip.room.tenant_name && <div className="text-[10px] text-slate-400">{tooltip.room.tenant_name}</div>}
            <div className="text-[10px] text-slate-500">
              KES {money(tooltip.room.monthly_rent)}/mo
              {tooltip.room.invoice_balance !== undefined && tooltip.room.invoice_balance > 0 &&
                <span className="text-rose-400 ml-1">· {money(tooltip.room.invoice_balance)} due</span>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
