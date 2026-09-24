import { useRef, useEffect, useCallback, useState } from "react";
import { createPortal } from "react-dom";
import { MessageSquare, Phone, UserCheck, ShieldCheck } from "lucide-react";

const money = (n: number) => (n ?? 0).toLocaleString("en-KE");

/* ─── Types ─── */

type Light = "vacant" | "unpaid" | "partial" | "paid" | "overpaid";

interface Room {
  id: string;
  unit_number: string;
  rent_light: Light;
  monthly_rent: number;
  tenant_name?: string;
  status?: string;
  invoice_balance?: number;
  total_paid?: number;
  invoice_status?: string;
  condition_notes?: string;
  duration_months?: number;
  lease_start?: string;
  tenant_phone?: string;
  max_occupants?: number;
}

interface Floor {
  rooms: Room[];
  label: string;
}

const LIGHT_COLORS: Record<Light, string> = {
  vacant: "#38bdf8",
  unpaid: "#f43f5e",
  partial: "#f59e0b",
  paid: "#34d399",
  overpaid: "#38bdf8",
};

const LIGHT_GLOW: Record<Light, string> = {
  vacant: "rgba(56,189,248,",
  unpaid: "rgba(244,63,94,",
  partial: "rgba(245,158,11,",
  paid: "rgba(52,211,153,",
  overpaid: "rgba(56,189,248,",
};

/* ─── Particle System ─── */

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  alpha: number;
  life: number;
  maxLife: number;
}

function createParticle(w: number, h: number): Particle {
  return {
    x: Math.random() * w,
    y: h - Math.random() * 20,
    vx: (Math.random() - 0.5) * 0.3,
    vy: -(Math.random() * 0.5 + 0.2),
    size: Math.random() * 2.5 + 1,
    alpha: Math.random() * 0.4 + 0.1,
    life: 0,
    maxLife: 400 + Math.random() * 300,
  };
}

/* ─── Star ─── */

interface Star {
  x: number;
  y: number;
  size: number;
  phase: number;
  speed: number;
}

/* ─── Props ─── */

interface Props {
  floors: Floor[];
  counts: Record<string, number>;
  propertyName?: string;
  totalUnits?: number;
  occupied?: number;
  onRoomClick?: (room: Room) => void;
  activeRoomId?: string | null;
}

export default function BuildingCanvas({
  floors,
  counts,
  propertyName,
  totalUnits,
  occupied,
  onRoomClick,
  activeRoomId,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hovered, setHovered] = useState<{ fi: number; ri: number } | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; room: Room } | null>(null);
  const [mouse, setMouse] = useState({ x: 0, y: 0 });
  const animRef = useRef<number>(0);
  const frameRef = useRef(0);
  const starsRef = useRef<Star[]>([]);
  const particlesRef = useRef<Particle[]>([]);
  const windowRectsRef = useRef<Map<string, { x: number; y: number; w: number; h: number }>>(new Map());
  const sizeRef = useRef({ w: 800, h: 600 });
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    starsRef.current = Array.from({ length: 50 }, () => ({
      x: Math.random() * 800,
      y: Math.random() * 250,
      size: Math.random() * 1.8 + 0.4,
      phase: Math.random() * Math.PI * 2,
      speed: Math.random() * 0.02 + 0.005,
    }));
    particlesRef.current = Array.from({ length: 24 }, () => createParticle(800, 600));
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const onMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      setMouse({ x, y });
    };
    container.addEventListener("mousemove", onMove);
    return () => container.removeEventListener("mousemove", onMove);
  }, []);

  /* ─── Drawing ─── */
  const draw = useCallback(
    (ctx: CanvasRenderingContext2D, w: number, h: number, frame: number) => {
      ctx.clearRect(0, 0, w, h);

      /* ===== SKY ===== */
      const skyGrad = ctx.createLinearGradient(0, 0, 0, h * 0.75);
      skyGrad.addColorStop(0, "#0f172a");
      skyGrad.addColorStop(0.35, "#1e293b");
      skyGrad.addColorStop(0.75, "#25334e");
      skyGrad.addColorStop(1, "#1e293b");
      ctx.fillStyle = skyGrad;
      ctx.fillRect(0, 0, w, h * 0.75);

      /* ===== STARS & NEBULA ===== */
      starsRef.current.forEach((s) => {
        const flicker = 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(frame * s.speed + s.phase));
        ctx.globalAlpha = flicker * 0.9;
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1;

      /* ===== MOON & AMBIENT GLOW ===== */
      const moonX = w - 90;
      const moonY = 45;
      const moonGlow = ctx.createRadialGradient(moonX, moonY, 0, moonX, moonY, 80);
      moonGlow.addColorStop(0, "rgba(52,211,153,0.22)");
      moonGlow.addColorStop(0.5, "rgba(56,189,248,0.08)");
      moonGlow.addColorStop(1, "transparent");
      ctx.fillStyle = moonGlow;
      ctx.beginPath();
      ctx.arc(moonX, moonY, 80, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#f8fafc";
      ctx.shadowColor = "#38bdf8";
      ctx.shadowBlur = 20;
      ctx.beginPath();
      ctx.arc(moonX, moonY, 16, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      /* ===== BUILDING PARAMETERS ===== */
      const buildingW = Math.min(650, w * 0.82);
      const buildingH = Math.min(430, h * 0.72);
      const buildingX = (w - buildingW) / 2;
      const buildingY = h * 0.14;
      const groundY = buildingY + buildingH;

      /* ===== GROUND SHADOW ===== */
      const shadowGrad = ctx.createRadialGradient(
        w / 2,
        groundY + 5,
        0,
        w / 2,
        groundY + 5,
        buildingW * 0.75
      );
      shadowGrad.addColorStop(0, "rgba(0,0,0,0.15)");
      shadowGrad.addColorStop(1, "transparent");
      ctx.fillStyle = shadowGrad;
      ctx.beginPath();
      ctx.ellipse(w / 2, groundY + 5, buildingW * 0.75, 18, 0, 0, Math.PI * 2);
      ctx.fill();

      /* ===== BUILDING FACADE ===== */
      const wallGrad = ctx.createLinearGradient(buildingX, buildingY, buildingX, groundY);
      wallGrad.addColorStop(0, "#334155");
      wallGrad.addColorStop(0.5, "#243044");
      wallGrad.addColorStop(1, "#192336");
      ctx.fillStyle = wallGrad;
      ctx.fillRect(buildingX, buildingY, buildingW, buildingH);

      // Architectural Glass Reflection Diagonal Band
      ctx.fillStyle = "rgba(255,255,255,0.06)";
      ctx.beginPath();
      ctx.moveTo(buildingX + 40, buildingY);
      ctx.lineTo(buildingX + 220, buildingY);
      ctx.lineTo(buildingX + 100, groundY);
      ctx.lineTo(buildingX, groundY);
      ctx.closePath();
      ctx.fill();

      // Border glow
      ctx.strokeStyle = "rgba(52,211,153,0.45)";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(buildingX, buildingY, buildingW, buildingH);

      /* ===== ROOF & CROWN ===== */
      const roofGrad = ctx.createLinearGradient(0, buildingY - 18, 0, buildingY);
      roofGrad.addColorStop(0, "#3b82f6");
      roofGrad.addColorStop(0.5, "#1d4ed8");
      roofGrad.addColorStop(1, "#1e293b");
      ctx.fillStyle = roofGrad;
      ctx.fillRect(buildingX - 10, buildingY - 18, buildingW + 20, 18);

      // Roof Neon Strip
      ctx.fillStyle = "#10b981";
      ctx.shadowColor = "#10b981";
      ctx.shadowBlur = 15;
      ctx.fillRect(buildingX - 8, buildingY - 3, buildingW + 16, 3);
      ctx.shadowBlur = 0;

      // Building Label Badge
      ctx.fillStyle = "#34d399";
      ctx.font = "bold 12px 'Inter', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText((propertyName || "LUXURY HOSTEL RESIDENCES").toUpperCase(), w / 2, buildingY - 26);

      /* ===== FLOORS & WINDOWS ===== */
      const floorH = buildingH / (floors.length + 1.4);
      const maxRooms = Math.max(...floors.map((f) => f.rooms.length), 1);
      const roomW = buildingW / (maxRooms + 1);
      const windowW = roomW * 0.58;
      const windowH = floorH * 0.58;

      windowRectsRef.current.clear();

      floors.forEach((floor, fi) => {
        const roomCount = floor.rooms.length;
        const totalGap = buildingW - roomCount * windowW;
        const gap = totalGap / (roomCount + 1);
        const yCenter = buildingY + fi * floorH + (floorH - windowH) / 2;
        const labelY = yCenter + windowH + 9;

        floor.rooms.forEach((room, ri) => {
          const xCenter = buildingX + gap + ri * (windowW + gap);

          windowRectsRef.current.set(`${fi}-${ri}`, {
            x: xCenter - 2,
            y: yCenter - 2,
            w: windowW + 4,
            h: windowH + 4,
          });

          const isActive = activeRoomId === room.id;
          const isHovered = hovered?.fi === fi && hovered?.ri === ri;
          const lightColor = LIGHT_COLORS[room.rent_light];
          const glowBase = LIGHT_GLOW[room.rent_light];
          const isVacant = room.rent_light === "vacant";
          const isUnpaid = room.rent_light === "unpaid";

          // Window Frame
          const frameColor = isActive
            ? "#34d399"
            : isHovered
            ? "#38bdf8"
            : "rgba(100,116,139,0.55)";

          ctx.strokeStyle = frameColor;
          ctx.lineWidth = isActive ? 2.5 : isHovered ? 2 : 1;
          ctx.fillStyle = isVacant ? "#1e293b" : "#111c30";

          ctx.beginPath();
          ctx.roundRect(xCenter, yCenter, windowW, windowH, 4);
          ctx.fill();
          ctx.stroke();

          /* Window Light & Interior */
          if (!isVacant) {
            const glowIntensity = isUnpaid
              ? 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(frame * 0.09))
              : 0.75 + 0.25 * Math.sin(frame * 0.03 + ri * 0.7);

            // Room Interior Glow
            const innerGlow = ctx.createRadialGradient(
              xCenter + windowW / 2,
              yCenter + windowH / 2,
              0,
              xCenter + windowW / 2,
              yCenter + windowH / 2,
              windowW * 0.65
            );
            innerGlow.addColorStop(0, `${glowBase}${glowIntensity * 0.7})`);
            innerGlow.addColorStop(0.5, `${glowBase}${glowIntensity * 0.3})`);
            innerGlow.addColorStop(1, `${glowBase}0.06)`);
            ctx.fillStyle = innerGlow;
            ctx.fillRect(xCenter + 2, yCenter + 2, windowW - 4, windowH - 4);

            // Lamp Warmth
            ctx.fillStyle = `${glowBase}${glowIntensity * 0.45})`;
            ctx.fillRect(
              xCenter + windowW * 0.22,
              yCenter + windowH * 0.15,
              windowW * 0.56,
              windowH * 0.7
            );

            // TENANT SILHOUETTE INSIDE WINDOW
            if (room.tenant_name) {
              const headRadius = windowH * 0.12;
              const headX = xCenter + windowW * 0.5;
              const headY = yCenter + windowH * 0.42;

              ctx.fillStyle = "rgba(15,23,42,0.85)";
              // Head
              ctx.beginPath();
              ctx.arc(headX, headY, headRadius, 0, Math.PI * 2);
              ctx.fill();
              // Shoulders / Torso
              ctx.beginPath();
              ctx.ellipse(headX, headY + headRadius * 2.2, windowW * 0.22, windowH * 0.28, 0, Math.PI, 0);
              ctx.fill();

              // Tenant Phone indicator dot
              ctx.fillStyle = "#34d399";
              ctx.beginPath();
              ctx.arc(xCenter + windowW * 0.8, yCenter + windowH * 0.25, 2, 0, Math.PI * 2);
              ctx.fill();
            }

            // Downward Light Beam
            ctx.globalAlpha = glowIntensity * 0.14;
            const beamGrad = ctx.createLinearGradient(0, yCenter + windowH, 0, yCenter + windowH + 32);
            beamGrad.addColorStop(0, `${glowBase}0.6)`);
            beamGrad.addColorStop(1, `${glowBase}0)`);
            ctx.fillStyle = beamGrad;
            ctx.beginPath();
            ctx.moveTo(xCenter + windowW * 0.15, yCenter + windowH);
            ctx.lineTo(xCenter + windowW * 0.85, yCenter + windowH);
            ctx.lineTo(xCenter + windowW * 0.95, yCenter + windowH + 30);
            ctx.lineTo(xCenter + windowW * 0.05, yCenter + windowH + 30);
            ctx.closePath();
            ctx.fill();
            ctx.globalAlpha = 1;
          }

          /* Status Bar */
          const barH = 3;
          const barY = yCenter + windowH - barH - 1;
          ctx.fillStyle = lightColor;
          ctx.beginPath();
          ctx.roundRect(xCenter + 2, barY, windowW - 4, barH, 1.5);
          ctx.fill();

          /* Mullions */
          ctx.strokeStyle = "rgba(51,65,85,0.6)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(xCenter, yCenter + windowH / 2);
          ctx.lineTo(xCenter + windowW, yCenter + windowH / 2);
          ctx.stroke();

          /* Unit Pill */
          const lx = xCenter + windowW / 2;
          const ly = labelY - 1;
          ctx.fillStyle = isActive
            ? "rgba(52,211,153,0.3)"
            : isHovered
            ? "rgba(56,189,248,0.25)"
            : "rgba(15,23,42,0.7)";
          ctx.beginPath();
          ctx.roundRect(lx - 16, ly - 6, 32, 13, 3);
          ctx.fill();
          ctx.strokeStyle = lightColor;
          ctx.lineWidth = 0.8;
          ctx.stroke();

          ctx.fillStyle = isHovered || isActive ? "#ffffff" : lightColor;
          ctx.font = "bold 9px 'JetBrains Mono', monospace";
          ctx.textAlign = "center";
          ctx.fillText(room.unit_number, lx, ly + 3);
        });
      });

      /* ===== ENTRANCE DOOR ===== */
      const doorW = 44;
      const doorH = 58;
      const doorX = (w - doorW) / 2;
      const doorY = groundY - doorH - 2;

      const doorGlow = ctx.createRadialGradient(
        doorX + doorW / 2,
        doorY + doorH,
        0,
        doorX + doorW / 2,
        doorY + doorH,
        60
      );
      doorGlow.addColorStop(0, "rgba(52,211,153,0.12)");
      doorGlow.addColorStop(1, "transparent");
      ctx.fillStyle = doorGlow;
      ctx.beginPath();
      ctx.arc(doorX + doorW / 2, doorY + doorH, 60, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#0f172a";
      ctx.strokeStyle = "rgba(52,211,153,0.5)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(doorX, doorY, doorW, doorH, 4);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = "rgba(52,211,153,0.8)";
      ctx.font = "bold 7px 'Inter', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("RECEPTION", doorX + doorW / 2, doorY + 16);

      /* ===== STREET & REFLECTION ===== */
      const streetY = groundY + 8;
      const streetGrad = ctx.createLinearGradient(0, streetY, 0, h);
      streetGrad.addColorStop(0, "#0f172a");
      streetGrad.addColorStop(1, "#030712");
      ctx.fillStyle = streetGrad;
      ctx.fillRect(0, streetY, w, h - streetY);

      // Fireflies
      particlesRef.current.forEach((p, i) => {
        p.x += p.vx;
        p.y += p.vy;
        p.life++;
        if (p.life > p.maxLife || p.y < -10 || p.x < -10 || p.x > w + 10) {
          particlesRef.current[i] = createParticle(w, h);
          return;
        }
        const flickerP = 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(frame * 0.02 + i));
        const alpha = p.alpha * flickerP * (1 - p.life / p.maxLife);

        ctx.globalAlpha = alpha;
        ctx.fillStyle = "#34d399";
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1;
    },
    [floors, counts, propertyName, activeRoomId, hovered]
  );

  /* ─── Animation loop ─── */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      const w = parent.clientWidth;
      const h = Math.min(560, Math.max(400, w * 0.6));
      const dpr = window.devicePixelRatio || 1;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.scale(dpr, dpr);
      sizeRef.current = { w, h };
    };

    resize();
    window.addEventListener("resize", resize);

    let running = true;
    const loop = () => {
      if (!running) return;
      frameRef.current++;
      const { w, h } = sizeRef.current;
      draw(ctx, w, h, frameRef.current);
      animRef.current = requestAnimationFrame(loop);
    };
    loop();

    return () => {
      running = false;
      cancelAnimationFrame(animRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [draw]);

  /* ─── Click handler ─── */
  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas || !onRoomClick) return;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      for (const [key, r] of windowRectsRef.current) {
        if (mx >= r.x && mx <= r.x + r.w && my >= r.y && my <= r.y + r.h) {
          const [fi, ri] = key.split("-").map(Number);
          const room = floors[fi]?.rooms[ri];
          if (room) {
            onRoomClick(room);
            return;
          }
        }
      }
    },
    [floors, onRoomClick]
  );

  /* ─── Mouse move for hover + tooltip ─── */
  const handleMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      let found: { fi: number; ri: number } | null = null;
      let room: Room | null = null;
      for (const [key, r] of windowRectsRef.current) {
        if (mx >= r.x && mx <= r.x + r.w && my >= r.y && my <= r.y + r.h) {
          const [fi, ri] = key.split("-").map(Number);
          found = { fi, ri };
          room = floors[fi]?.rooms[ri] || null;
          break;
        }
      }
      setHovered(found);
      canvas.style.cursor = found ? "pointer" : "default";
      setTooltip(
        found && room ? { x: e.clientX, y: e.clientY - 10, room } : null
      );
    },
    [floors]
  );

  const handleLeave = useCallback(() => {
    setHovered(null);
    setTooltip(null);
  }, []);

  const LIGHT_LABELS: Record<Light, { label: string; color: string }> = {
    vacant: { label: "Vacant", color: "#64748b" },
    unpaid: { label: "Unpaid", color: "#f43f5e" },
    partial: { label: "Partial", color: "#f59e0b" },
    paid: { label: "Paid", color: "#34d399" },
    overpaid: { label: "Overpaid", color: "#38bdf8" },
  };

  const getWhatsAppLink = (phone?: string, name?: string, unit?: string) => {
    const p = phone ? phone.replace(/[^0-9]/g, "") : "254700000000";
    const msg = encodeURIComponent(
      `Hi ${name || "Tenant"} (Unit ${unit}), this is the caretaker catching up on your stay.`
    );
    return `https://wa.me/${p}?text=${msg}`;
  };

  return (
    <div ref={containerRef} className="relative" style={{ perspective: 1000 }}>
      <canvas
        ref={canvasRef}
        onClick={handleClick}
        onMouseMove={handleMove}
        onMouseLeave={handleLeave}
        className="block w-full rounded-2xl transform-gpu transition-transform duration-300 border border-white/10 shadow-2xl shadow-emerald-950/40"
        style={{
          transform: `perspective(1000px) rotateY(${mouse.x * 2.5}deg) rotateX(${-mouse.y * 2.5}deg)`,
          transformStyle: "preserve-3d",
        }}
      />
      {/* Interactive Glass Tooltip with WhatsApp Catch-Up */}
      {tooltip && createPortal(
        <div
          className="fixed z-[9999] pointer-events-auto transition-all duration-150"
          style={{
            left: Math.min(window.innerWidth - 240, Math.max(0, tooltip.x - 110)),
            top: Math.min(window.innerHeight - 180, Math.max(10, tooltip.y - 180)),
          }}
        >
          <div className="bg-slate-900/95 backdrop-blur-xl border border-white/15 rounded-2xl p-3.5 shadow-2xl shadow-black/80 min-w-[220px]">
            <div className="flex items-center justify-between mb-2 pb-2 border-b border-white/10">
              <div className="flex items-center gap-2">
                <span className="text-sm font-extrabold text-white">Unit {tooltip.room.unit_number}</span>
                <span
                  className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                  style={{
                    background: LIGHT_COLORS[tooltip.room.rent_light] + "25",
                    color: LIGHT_COLORS[tooltip.room.rent_light],
                    border: `1px solid ${LIGHT_COLORS[tooltip.room.rent_light]}50`,
                  }}
                >
                  {LIGHT_LABELS[tooltip.room.rent_light]?.label || tooltip.room.rent_light}
                </span>
              </div>
            </div>

            {tooltip.room.tenant_name ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <img
                    src="/tenant_avatar.jpg"
                    alt="Tenant Avatar"
                    className="w-8 h-8 rounded-full object-cover border border-emerald-400/40 shadow-sm"
                  />
                  <div>
                    <div className="text-xs font-semibold text-white">{tooltip.room.tenant_name}</div>
                    <div className="text-[10px] text-emerald-400 flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3" /> Active Lease
                    </div>
                  </div>
                </div>

                <div className="text-[11px] text-slate-300 space-y-0.5 pt-1">
                  <div>Rent: <span className="font-semibold text-white">KES {money(tooltip.room.monthly_rent)}/mo</span></div>
                  {tooltip.room.invoice_balance !== undefined && tooltip.room.invoice_balance > 0 && (
                    <div className="text-rose-400 font-medium">Due Balance: KES {money(tooltip.room.invoice_balance)}</div>
                  )}
                </div>

                {/* WhatsApp Catch Up Button */}
                <a
                  href={getWhatsAppLink(tooltip.room.tenant_phone, tooltip.room.tenant_name, tooltip.room.unit_number)}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2.5 flex items-center justify-center gap-2 w-full py-1.5 px-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs shadow-lg shadow-emerald-500/25 transition-all"
                >
                  <MessageSquare className="w-3.5 h-3.5 fill-slate-950" /> WhatsApp Catch-up
                </a>
              </div>
            ) : (
              <div className="text-xs text-slate-400 py-1">
                Vacant Unit — Ready for Onboarding
              </div>
            )}
          </div>
        </div>, document.body
      )}
    </div>
  );
}
