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

interface Props {
  floors: Floor[]; counts: Record<string, number>;
  propertyName?: string; totalUnits?: number; occupied?: number;
  onRoomClick?: (room: Room) => void; activeRoomId?: string | null;
}

export default function IsometricCanvas({
  floors, onRoomClick, activeRoomId,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hovered, setHovered] = useState<{ fi: number; ri: number } | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; room: Room } | null>(null);
  const rectsRef = useRef<Map<string, { x: number; y: number; w: number; h: number }>>(new Map());
  const sizeRef = useRef({ w: 800, h: 500 });

  const draw = useCallback((ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.clearRect(0, 0, w, h);

    /* Background */
    const grad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w * 0.7);
    grad.addColorStop(0, "#0f172a");
    grad.addColorStop(1, "#020617");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);

    if (!floors.length) return;

    /* Isometric parameters */
    const isoAngle = 0.5;
    const maxPerFloor = Math.max(...floors.map(f => f.rooms.length), 1);
    const blockW = Math.min((w * 0.7) / (maxPerFloor + 2), 40);
    const blockD = blockW * 0.5;
    const blockH = blockW * 0.6;
    const floorGap = blockH * 1.2;

    /* Center X for each floor so the building is centered */
    const floorWidth = (maxPerFloor) * (blockW + 3);
    const centerX = w / 2;
    const baseY = h - 30;

    rectsRef.current.clear();

    floors.forEach((floor, fi) => {
      const roomsCount = floor.rooms.length;
      const rowW = roomsCount * (blockW + 3);
      const startX = centerX - rowW / 2;
      const floorY = baseY - (floors.length - fi) * floorGap;

      floor.rooms.forEach((room, ri) => {
        const x = startX + ri * (blockW + 3);
        const y = floorY;
        const c = LIGHT[room.rent_light] || "#64748b";
        const isActive = activeRoomId === room.id;
        const isHov = hovered?.fi === fi && hovered?.ri === ri;

        /* Convert 2D coords to isometric */
        const isoX = x + (y * isoAngle);
        const isoY = (y * 0.3) + 20;

        /* Store clickable rect (approximate) */
        rectsRef.current.set(`${fi}-${ri}`, {
          x: isoX, y: isoY - blockH, w: blockW, h: blockH + blockD,
        });

        /* Top face */
        ctx.beginPath();
        ctx.moveTo(isoX, isoY - blockH);
        ctx.lineTo(isoX + blockW / 2, isoY - blockH - blockD / 2);
        ctx.lineTo(isoX + blockW, isoY - blockH);
        ctx.lineTo(isoX + blockW / 2, isoY - blockH + blockD / 2);
        ctx.closePath();
        ctx.fillStyle = isActive ? "#34d399" : isHov ? lighten(c, 20) : c;
        ctx.globalAlpha = 0.7;
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.strokeStyle = isActive ? "#34d399" : "rgba(255,255,255,0.08)";
        ctx.lineWidth = isActive ? 2 : 0.5;
        ctx.stroke();

        /* Right face */
        ctx.beginPath();
        ctx.moveTo(isoX + blockW / 2, isoY - blockH + blockD / 2);
        ctx.lineTo(isoX + blockW, isoY - blockH);
        ctx.lineTo(isoX + blockW, isoY);
        ctx.lineTo(isoX + blockW / 2, isoY + blockD / 2);
        ctx.closePath();
        ctx.fillStyle = isActive ? "#1a7a5c" : isHov ? lighten(c, -15) : darken(c, 30);
        ctx.globalAlpha = 0.8;
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.strokeStyle = isActive ? "#34d399" : "rgba(255,255,255,0.04)";
        ctx.lineWidth = isActive ? 1.5 : 0.5;
        ctx.stroke();

        /* Left face */
        ctx.beginPath();
        ctx.moveTo(isoX + blockW / 2, isoY - blockH + blockD / 2);
        ctx.lineTo(isoX, isoY - blockH);
        ctx.lineTo(isoX, isoY);
        ctx.lineTo(isoX + blockW / 2, isoY + blockD / 2);
        ctx.closePath();
        ctx.fillStyle = isActive ? "#22553d" : isHov ? lighten(c, -30) : darken(c, 50);
        ctx.globalAlpha = 0.9;
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.strokeStyle = isActive ? "#34d399" : "rgba(255,255,255,0.03)";
        ctx.lineWidth = isActive ? 1.5 : 0.5;
        ctx.stroke();

        /* Unit number on top face */
        ctx.fillStyle = "rgba(255,255,255,0.5)";
        ctx.font = "6px 'JetBrains Mono', monospace";
        ctx.textAlign = "center";
        ctx.save();
        ctx.translate(isoX + blockW / 2, isoY - blockH + blockD / 4);
        ctx.rotate(-0.15);
        ctx.scale(1, 0.6);
        ctx.fillText(room.unit_number, 0, 0);
        ctx.restore();
      });
    });

    /* Ground shadow */
    const groundY = baseY + 5;
    const shadowGrad = ctx.createRadialGradient(w / 2, groundY, 0, w / 2, groundY, w * 0.4);
    shadowGrad.addColorStop(0, "rgba(0,0,0,0.3)");
    shadowGrad.addColorStop(1, "transparent");
    ctx.fillStyle = shadowGrad;
    ctx.beginPath();
    ctx.ellipse(w / 2, groundY, w * 0.4, 15, 0, 0, Math.PI * 2);
    ctx.fill();
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
          <div className="bg-slate-900/95 backdrop-blur-md border border-slate-700/60 rounded-xl px-3 py-2 shadow-2xl shadow-black/50 min-w-[140px]">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-bold text-white">Room {tooltip.room.unit_number}</span>
              <span className="text-[9px] font-medium px-1.5 py-0.5 rounded-full"
                style={{ background: LIGHT[tooltip.room.rent_light] + "25", color: LIGHT[tooltip.room.rent_light] }}>
                {tooltip.room.rent_light}
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

/* Helpers */
function lighten(hex: string, amt: number): string {
  const num = parseInt(hex.slice(1), 16);
  const r = Math.min(255, (num >> 16) + amt);
  const g = Math.min(255, ((num >> 8) & 0x00FF) + amt);
  const b = Math.min(255, (num & 0x0000FF) + amt);
  return `rgb(${r},${g},${b})`;
}

function darken(hex: string, amt: number): string {
  const num = parseInt(hex.slice(1), 16);
  const r = Math.max(0, (num >> 16) - amt);
  const g = Math.max(0, ((num >> 8) & 0x00FF) - amt);
  const b = Math.max(0, (num & 0x0000FF) - amt);
  return `rgb(${r},${g},${b})`;
}
