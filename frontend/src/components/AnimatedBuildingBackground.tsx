import { motion, useReducedMotion } from "framer-motion";

const windowRows = [
  { y: 72, count: 4 },
  { y: 100, count: 4 },
  { y: 128, count: 4 },
  { y: 156, count: 4 },
  { y: 184, count: 4 },
];

export default function AnimatedBuildingBackground() {
  const reduceMotion = useReducedMotion();

  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      <motion.div
        className="absolute -right-24 top-12 h-72 w-72 rounded-full bg-emerald-400/[0.08] blur-3xl sm:right-8 sm:top-20 sm:h-96 sm:w-96"
        animate={reduceMotion ? undefined : { x: [0, -12, 0], y: [0, 14, 0], scale: [1, 1.05, 1] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute -left-28 bottom-8 h-64 w-64 rounded-full bg-sky-400/[0.07] blur-3xl"
        animate={reduceMotion ? undefined : { x: [0, 14, 0], y: [0, -10, 0] }}
        transition={{ duration: 19, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.svg
        viewBox="0 0 900 640"
        preserveAspectRatio="xMidYMax slice"
        className="absolute inset-x-0 bottom-0 h-[72%] min-h-[360px] w-full opacity-50 sm:h-[88%] sm:opacity-65"
        initial={false}
        animate={reduceMotion ? undefined : { y: [0, -5, 0] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
      >
        <defs>
          <linearGradient id="rental-building-glass" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#1e3a4b" />
            <stop offset="55%" stopColor="#0f2535" />
            <stop offset="100%" stopColor="#081522" />
          </linearGradient>
          <linearGradient id="rental-building-edge" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#34d399" stopOpacity=".5" />
            <stop offset="100%" stopColor="#38bdf8" stopOpacity=".12" />
          </linearGradient>
          <linearGradient id="rental-building-ground" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0f2636" stopOpacity="0" />
            <stop offset="100%" stopColor="#020617" stopOpacity=".95" />
          </linearGradient>
        </defs>

        <g opacity=".5" fill="#102537" stroke="#284357" strokeWidth="1">
          <path d="M0 360V220H75V360Z" /><path d="M65 360V175H135V360Z" />
          <path d="M730 360V190H805V360Z" /><path d="M800 360V245H900V360Z" />
        </g>
        <g fill="#38bdf8" opacity=".35">
          {Array.from({ length: 18 }, (_, i) => <rect key={i} x={12 + (i % 3) * 20} y={242 + Math.floor(i / 3) * 17} width="7" height="9" rx="1" />)}
          {Array.from({ length: 18 }, (_, i) => <rect key={i} x={746 + (i % 3) * 19} y={213 + Math.floor(i / 3) * 19} width="7" height="10" rx="1" />)}
        </g>

        <g>
          <path d="M220 360V118L244 92H566L590 118V360Z" fill="url(#rental-building-glass)" stroke="url(#rental-building-edge)" strokeWidth="1.5" />
          <path d="M244 92H566L590 118H220Z" fill="#254457" fillOpacity=".72" stroke="#4adeb5" strokeOpacity=".45" />
          <path d="M270 92V65H540V92" fill="#122a3a" stroke="#38bdf8" strokeOpacity=".32" />
          <path d="M405 65V47H480V65" fill="#122a3a" stroke="#38bdf8" strokeOpacity=".25" />
          <path d="M242 120H568M232 232H578M225 290H585" stroke="#5eead4" strokeOpacity=".16" />
          <path d="M330 110V360M480 110V360" stroke="#5eead4" strokeOpacity=".13" />
          {windowRows.map((row, rowIndex) =>
            Array.from({ length: row.count }, (_, colIndex) => (
              <motion.rect
                key={`${rowIndex}-${colIndex}`}
                x={260 + colIndex * 75}
                y={row.y}
                width="35"
                height="16"
                rx="2"
                fill={((rowIndex * 3 + colIndex) % 5 === 0) ? "#fcdba7" : "#67e8f9"}
                initial={{ opacity: .3 }}
                animate={reduceMotion ? undefined : { opacity: [.24, ((rowIndex + colIndex) % 3 === 0) ? .8 : .48, .24] }}
                transition={{ duration: 4 + ((rowIndex + colIndex) % 4), delay: (rowIndex * 4 + colIndex) * .22, repeat: Infinity, ease: "easeInOut" }}
              />
            ))
          )}
          <path d="M374 360V306Q405 270 436 306V360Z" fill="#061421" stroke="#34d399" strokeOpacity=".4" />
          <path d="M390 360V315H420V360" fill="#164e63" fillOpacity=".55" />
          <path d="M220 360H590" stroke="#6ee7b7" strokeOpacity=".45" strokeWidth="2" />
        </g>

        <g fill="#122b3b" stroke="#28475b" strokeWidth="1">
          <path d="M115 360V285H205V360Z" /><path d="M600 360V270H700V360Z" />
          <path d="M150 285V258H188V285Z" /><path d="M625 270V245H673V270Z" />
        </g>
        <g fill="#67e8f9" opacity=".42">
          {Array.from({ length: 8 }, (_, i) => <rect key={i} x={128 + (i % 3) * 23} y={302 + Math.floor(i / 3) * 22} width="9" height="12" rx="1" />)}
          {Array.from({ length: 8 }, (_, i) => <rect key={i} x={615 + (i % 3) * 25} y={288 + Math.floor(i / 3) * 22} width="9" height="12" rx="1" />)}
        </g>
        <path d="M0 350Q220 330 450 350T900 345V640H0Z" fill="url(#rental-building-ground)" />
        <path d="M0 362H900" stroke="#38bdf8" strokeOpacity=".12" />
      </motion.svg>
      <div className="absolute inset-0 bg-gradient-to-b from-slate-950/30 via-slate-950/45 to-slate-950/85" />
    </div>
  );
}
