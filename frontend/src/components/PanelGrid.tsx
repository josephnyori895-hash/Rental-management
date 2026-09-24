import { useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, Clock, Plus } from "lucide-react";

const money = (n: number) => (n ?? 0).toLocaleString("en-KE");

type Light = "vacant" | "unpaid" | "partial" | "paid" | "overpaid";

interface Room {
  id: string; unit_number: string; rent_light: Light;
  monthly_rent: number; tenant_name?: string; invoice_balance?: number;
  status?: string;
}

interface Floor { rooms: Room[]; label: string; }

interface Props {
  floors: Floor[]; counts: Record<string, number>;
  propertyName?: string; totalUnits?: number; occupied?: number;
  onRoomClick?: (room: Room) => void; activeRoomId?: string | null;
}

export default function PanelGrid({
  floors, counts, propertyName, totalUnits, occupied,
  onRoomClick, activeRoomId,
}: Props) {
  const allRooms = floors.flatMap(f => f.rooms);

  return (
    <div className="p-4 bg-slate-950 rounded-xl border border-slate-800/50">
      {/* Header stats */}
      <div className="flex items-center gap-3 mb-4 text-[11px] text-slate-500">
        {propertyName && <span className="font-semibold text-slate-300">{propertyName}</span>}
        <span className="text-slate-700">·</span>
        <span>{totalUnits || allRooms.length} rooms</span>
        <span className="text-slate-700">·</span>
        <span className="text-emerald-400">{occupied ?? counts.paid} occupied</span>
      </div>

      {/* Room grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
        {allRooms.map((room, i) => {
          const isActive = activeRoomId === room.id;
          const isVacant = room.rent_light === "vacant";
          const isUnpaid = room.rent_light === "unpaid" && (room.invoice_balance || 0) > 0;
          const isPaid = room.rent_light === "paid";
          const isPartial = room.rent_light === "partial";
          return (
            <motion.button
              key={room.id}
              initial={{ opacity: 0, scale: 0.3 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.015, duration: 0.2 }}
              whileHover={{
                scale: 1.06,
                y: -3,
                transition: { type: "spring", stiffness: 300, damping: 12 },
              }}
              onClick={() => onRoomClick?.(room)}
              className={`relative text-left p-2.5 rounded-xl border cursor-pointer overflow-hidden backdrop-blur-sm group select-none transition-all duration-200
                ${isActive
                  ? "border-emerald-500/60 shadow-[0_0_12px_rgba(52,211,153,0.15)]"
                  : isPaid
                  ? "border-emerald-500/30 shadow-sm shadow-emerald-500/10 hover:border-emerald-400/60 hover:shadow-lg hover:shadow-emerald-500/15"
                  : isUnpaid
                  ? "border-rose-500/30 shadow-sm shadow-rose-500/10 hover:border-rose-400/60 hover:shadow-lg hover:shadow-rose-500/15"
                  : isPartial
                  ? "border-amber-500/30 shadow-sm shadow-amber-500/10 hover:border-amber-400/60 hover:shadow-lg hover:shadow-amber-500/15"
                  : "border-slate-700/60 hover:border-sky-400/40 hover:shadow-lg hover:shadow-sky-500/10 hover:bg-slate-800/80"
                }`}
            >
              {/* Glow overlays */}
              {isPaid && <div className="absolute inset-0 bg-gradient-to-t from-emerald-500/10 to-transparent pointer-events-none" />}
              {isUnpaid && (
                <motion.div
                  animate={{ opacity: [0.15, 0.35, 0.15] }}
                  transition={{ repeat: Infinity, duration: 2 }}
                  className="absolute inset-0 bg-gradient-to-t from-rose-500/15 to-transparent pointer-events-none"
                />
              )}
              {isPartial && <div className="absolute inset-0 bg-gradient-to-t from-amber-500/10 to-transparent pointer-events-none" />}
              {isVacant && (
                <div className="absolute inset-0 bg-gradient-to-br from-sky-500/0 via-transparent to-transparent pointer-events-none
                  group-hover:from-sky-500/10 transition-all duration-300" />
              )}

              {/* Status icon — top right */}
              <div className="absolute top-1.5 right-1.5 z-10">
                {isPaid && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
                {isUnpaid && <Clock className="w-3 h-3 text-rose-400" />}
                {isVacant && (
                  <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                    <Plus className="w-3 h-3 text-sky-400" />
                  </div>
                )}
              </div>

              {/* Room number */}
              <div className={`relative text-sm font-bold z-10 ${isActive ? "text-emerald-300" : "text-white"}`}>
                {room.unit_number}
              </div>

              {/* Rent */}
              <div className="relative text-[10px] text-slate-500 mt-0.5 z-10">
                KES {money(room.monthly_rent)}
              </div>

              {/* Status + tenant */}
              <div className="mt-1 relative z-10">
                {isVacant ? (
                  <span className="text-[9px] text-slate-400 group-hover:text-sky-300 font-medium transition-colors duration-200">Vacant</span>
                ) : (
                  <>
                    <div className={`text-[9px] font-medium ${
                      isPaid ? "text-emerald-300" : isUnpaid ? "text-rose-300" : isPartial ? "text-amber-300" : "text-slate-400"
                    }`}>
                      {isPaid ? "PAID" : isUnpaid ? `KES ${money(room.invoice_balance || 0)} DUE` : isPartial ? "PARTIAL" : room.rent_light}
                    </div>
                    {room.tenant_name && (
                      <div className="text-[8px] text-slate-500 mt-0.5 truncate">{room.tenant_name}</div>
                    )}
                  </>
                )}
              </div>
            </motion.button>
          );
        })}
      </div>

      {allRooms.length === 0 && (
        <div className="text-center py-12 text-xs text-slate-500">No rooms to display</div>
      )}
    </div>
  );
}
