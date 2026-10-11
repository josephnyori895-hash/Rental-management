import { motion } from "framer-motion";

export default function LoginMarketing() {
  return (
    <div className="relative mx-auto w-full max-w-[620px]" aria-label="Illustration of a modern rental property">
      <div className="absolute left-1/2 top-1/2 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full bg-emerald-400/10 blur-3xl" />
      <svg viewBox="0 0 680 470" role="img" aria-label="Isometric apartment building with rental management metrics" className="relative z-10 w-full overflow-visible drop-shadow-2xl">
        <defs>
          <linearGradient id="ground" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#1e3a5f" />
            <stop offset="100%" stopColor="#0f766e" />
          </linearGradient>
          <linearGradient id="front" x1="0" y1="0" x2="0.9" y2="1">
            <stop offset="0%" stopColor="#f8fafc" />
            <stop offset="100%" stopColor="#cbd5e1" />
          </linearGradient>
          <linearGradient id="side" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#94a3b8" />
            <stop offset="100%" stopColor="#475569" />
          </linearGradient>
          <linearGradient id="roof" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#38bdf8" />
            <stop offset="100%" stopColor="#2563eb" />
          </linearGradient>
          <linearGradient id="window" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#a7f3d0" />
            <stop offset="100%" stopColor="#34d399" />
          </linearGradient>
          <filter id="shadow" x="-30%" y="-30%" width="160%" height="180%">
            <feDropShadow dx="0" dy="12" stdDeviation="10" floodColor="#020617" floodOpacity=".28" />
          </filter>
        </defs>

        {/* floating ambient dots */}
        <circle cx="106" cy="116" r="4" fill="#6ee7b7" opacity=".8" />
        <circle cx="556" cy="112" r="5" fill="#7dd3fc" opacity=".8" />
        <circle cx="516" cy="310" r="3" fill="#a7f3d0" opacity=".9" />
        <path d="M85 175 C60 130 88 93 126 98" fill="none" stroke="#34d399" strokeOpacity=".35" strokeWidth="2" strokeDasharray="5 7" />
        <path d="M542 160 C594 178 599 222 567 248" fill="none" stroke="#60a5fa" strokeOpacity=".45" strokeWidth="2" strokeDasharray="5 7" />

        {/* isometric landscaped base */}
        <g filter="url(#shadow)">
          <path d="M108 332 L354 192 L594 328 L347 466 Z" fill="url(#ground)" />
          <path d="M108 332 L347 466 L347 445 L108 312 Z" fill="#0f3f4d" opacity=".8" />
          <path d="M347 466 L594 328 L594 350 L347 466 Z" fill="#0b3347" opacity=".9" />
          <path d="M141 333 L354 212 L560 330 L347 451 Z" fill="#334155" opacity=".75" />
          <path d="M171 334 L354 230 L527 331 L347 432 Z" fill="#64748b" opacity=".55" />
          <path d="M196 335 L354 246 L502 332 L347 420 Z" fill="#0f766e" opacity=".45" />
        </g>

        {/* apartment building side */}
        <path d="M354 106 L480 177 L480 334 L354 262 Z" fill="url(#side)" />
        <path d="M354 106 L480 177 L480 198 L354 127 Z" fill="#334155" />
        {/* apartment building front */}
        <path d="M232 177 L354 106 L354 262 L232 333 Z" fill="url(#front)" />
        <path d="M232 177 L354 106 L480 177 L357 248 Z" fill="url(#roof)" />
        <path d="M232 177 L357 248 L357 264 L232 193 Z" fill="#1d4ed8" />
        <path d="M357 248 L480 177 L480 193 L357 264 Z" fill="#1e40af" />
        {/* rooftop terrace */}
        <path d="M260 174 L354 120 L449 174 L355 228 Z" fill="#dbeafe" />
        <path d="M260 174 L355 228 L355 240 L260 186 Z" fill="#94a3b8" />
        <path d="M355 228 L449 174 L449 186 L355 240 Z" fill="#64748b" />

        {/* front windows / balconies */}
        {[0,1,2].map((i) => (
          <g key={i} transform={`translate(0 ${i * 43})`}>
            <path d={`M250 ${203+i*0} L279 186 L279 214 L250 231 Z`} fill="#334155" opacity=".65" />
            <path d="M253 202 L276 189 L276 211 L253 224 Z" fill="url(#window)" />
            <path d="M290 181 L320 164 L320 192 L290 209 Z" fill="#334155" opacity=".65" />
            <path d="M293 180 L317 167 L317 189 L293 202 Z" fill="url(#window)" />
            <path d="M329 159 L347 149 L347 177 L329 187 Z" fill="#334155" opacity=".65" />
            <path d="M332 158 L344 151 L344 173 L332 180 Z" fill="url(#window)" />
            <path d={`M250 ${231+i*0} L279 214 L279 219 L250 236 Z`} fill="#94a3b8" />
            <path d="M290 209 L320 192 L320 197 L290 214 Z" fill="#94a3b8" />
            <path d="M329 187 L347 177 L347 182 L329 192 Z" fill="#94a3b8" />
          </g>
        ))}

        {/* side windows */}
        {[0,1,2].map((i) => (
          <g key={i} transform={`translate(0 ${i * 43})`}>
            <path d={`M374 ${137+i*0} L399 151 L399 179 L374 165 Z`} fill="#334155" />
            <path d="M377 142 L396 153 L396 172 L377 161 Z" fill="#7dd3fc" />
            <path d="M414 160 L439 174 L439 202 L414 188 Z" fill="#334155" />
            <path d="M417 165 L436 176 L436 195 L417 184 Z" fill="#7dd3fc" />
            <path d="M374 165 L399 179 L399 184 L374 170 Z" fill="#64748b" />
            <path d="M414 188 L439 202 L439 207 L414 193 Z" fill="#64748b" />
          </g>
        ))}

        {/* entrance and walkway */}
        <path d="M286 302 L316 285 L316 320 L286 337 Z" fill="#334155" />
        <path d="M291 304 L311 293 L311 317 L291 328 Z" fill="#0f172a" />
        <path d="M300 309 L304 307 L304 311 L300 313 Z" fill="#fbbf24" />
        <path d="M301 335 L301 352 L347 379 L347 362 Z" fill="#cbd5e1" opacity=".8" />

        {/* small landscaping */}
        <g>
          <path d="M175 348 L175 373" stroke="#a16207" strokeWidth="5" strokeLinecap="round" />
          <circle cx="175" cy="338" r="19" fill="#16a34a" />
          <circle cx="161" cy="346" r="13" fill="#22c55e" />
          <circle cx="188" cy="348" r="12" fill="#15803d" />
          <path d="M519 329 L519 351" stroke="#a16207" strokeWidth="5" strokeLinecap="round" />
          <circle cx="519" cy="318" r="17" fill="#16a34a" />
          <circle cx="506" cy="326" r="12" fill="#22c55e" />
          <circle cx="532" cy="328" r="11" fill="#15803d" />
          <path d="M150 369 L192 369 L201 382 L143 382 Z" fill="#64748b" />
          <path d="M495 347 L539 347 L548 360 L486 360 Z" fill="#64748b" />
        </g>

        {/* rent collection card */}
        <g filter="url(#shadow)" transform="translate(32 194)">
          <rect width="172" height="96" rx="15" fill="#ffffff" fillOpacity=".97" />
          <rect x="14" y="14" width="31" height="31" rx="9" fill="#dcfce7" />
          <path d="M21 28 L29.5 20 L38 28 V37 H32 V31 H27 V37 H21 Z" fill="#059669" />
          <text x="54" y="26" fontSize="10" fill="#64748b" fontWeight="600">RENT COLLECTED</text>
          <text x="14" y="61" fontSize="21" fill="#0f172a" fontWeight="700">KES 845K</text>
          <path d="M15 78 L39 72 L60 75 L81 60 L102 65 L124 47 L151 41" fill="none" stroke="#10b981" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M15 82 L39 76 L60 79 L81 64 L102 69 L124 51 L151 45 L151 83 L15 83 Z" fill="#6ee7b7" opacity=".18" />
        </g>

        {/* occupancy card */}
        <g filter="url(#shadow)" transform="translate(464 55)">
          <rect width="174" height="75" rx="15" fill="#ffffff" fillOpacity=".97" />
          <rect x="12" y="13" width="38" height="38" rx="11" fill="#dbeafe" />
          <path d="M21 31 L31 22 L41 31 V41 H34 V34 H28 V41 H21 Z" fill="#2563eb" />
          <text x="60" y="28" fontSize="10" fill="#64748b" fontWeight="600">OCCUPANCY</text>
          <text x="60" y="49" fontSize="19" fill="#0f172a" fontWeight="700">94%</text>
          <rect x="12" y="60" width="150" height="4" rx="2" fill="#e2e8f0" />
          <rect x="12" y="60" width="141" height="4" rx="2" fill="#10b981" />
        </g>

        {/* payments card */}
        <g filter="url(#shadow)" transform="translate(490 255)">
          <rect width="148" height="67" rx="14" fill="#ffffff" fillOpacity=".97" />
          <rect x="12" y="13" width="39" height="39" rx="11" fill="#d1fae5" />
          <rect x="20" y="23" width="23" height="16" rx="3" fill="#059669" />
          <path d="M20 28 H43" stroke="#d1fae5" strokeWidth="3" />
          <text x="61" y="28" fontSize="10" fill="#64748b" fontWeight="600">PAYMENTS</text>
          <text x="61" y="46" fontSize="13" fill="#0f172a" fontWeight="700">On track</text>
          <circle cx="132" cy="14" r="4" fill="#10b981" />
        </g>

        {/* decorative floating glints */}
        <path d="M575 182 L579 193 L590 197 L579 201 L575 212 L571 201 L560 197 L571 193 Z" fill="#6ee7b7" />
        <path d="M117 144 L120 151 L127 154 L120 157 L117 164 L114 157 L107 154 L114 151 Z" fill="#7dd3fc" />
      </svg>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.5 }}
        className="relative mx-auto -mt-3 flex w-fit items-center gap-2 rounded-full border border-white/10 bg-slate-900/70 px-4 py-2 text-xs text-slate-300 shadow-xl backdrop-blur-xl"
      >
        <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,.8)]" />
        Better properties. Happier tenants.
      </motion.div>
    </div>
  );
}
