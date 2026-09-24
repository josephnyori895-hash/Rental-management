module.exports = {
  theme: {
    extend: {
      /* ---------- 2026 Modern Morphism Tokens ---------- */
      colors: {
        /* Primary Accent (emerald×sky pivot) */
        primary: {
          DEFAULT: "#a7f3d0", // emerald-200 -> 2026 mint glass
          50:   "#ecfdf5",
          100:  "#d1fae5",
          200:  "#a7f3d0",
          300:  "#6ee7b7",
          400:  "#34d399",
          500:  "#10b981",
          600:  "#059669",
          700:  "#047857",
          800:  "#065f46",
          900:  "#064e3b",
        },
        /* Secondary Accent (sky cool overlay) */
        secondary: {
          DEFAULT: "#bae6fd", // sky-200
          50:   "#f0f9ff",
          100:  "#e0f2fe",
          200:  "#bae6fd",
          300:  "#7dd3fc",
          400:  "#38bdf8",
          500:  "#0ea5e9",
          600:  "#0284c7",
          700:  "#0369a1",
          800:  "#075985",
          900:  "#0c4a6e",
        },
        /* Semantic Status Radix */
        success: "#10b981",
        successLight: "#d1fae5",
        warn:   "#fbbf24",
        error:  "#f87171",
        info:   "#60a5fa",
        /* Glass / Transparent bg tokens */
        glass: {
          50:  "rgba(248, 250, 252, 0.10)",
          100: "rgba(248, 250, 252, 0.16)",
          200: "rgba(248, 250, 252, 0.22)",
          300: "rgba(248, 250, 252, 0.28)",
          500: "rgba(248, 250, 252, 0.50)",
          900: "rgba(255, 255, 255, 0.92)",
        },
        slate: {
          925: "#111827", // ui bg base
          900:  "#18181b",
          850:  "#1f2937",
          800:  "#27272a",
          700:  "#3f3f46",
          600:  "#525252",
          400:  "#9ca3af",
          300:  "#d1d5db",
          200:  "#e5e7eb",
          100:  "#f3f4f6",
          50:   "#f9fafb",
        },
      },
      /* ---------- 2026 Glass Morphism & Layout ---------- */
      backdropFilter: {
        // Tailwind classes map to these tokens at build time
      },
      boxShadow: {
        morph: "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.08)",
        glow:   "0 0 20px 2px rgba(16, 185, 129, 0.25)",
        glass:  "0 8px 32px rgba(0, 0, 0, 0.28)",
        insetShadow:
          "inset 0 0 0 1px rgba(255,255,255,0.04), inset 0 1px 2px rgba(0,0,0,0.08)",
      },
      borderRadius: {
        xl: "1.125rem", // 18px
        lg: "0.875rem", // 14px
        md: "0.75rem",  // 12px
        sm: "0.625rem", // 10px
      },
      fontFamily: {
        sans: '"Inter", ui-sans-serif, system-ui, sans-serif',
        mono: '"Fira Code", Menlo, Monaco, monospace',
      },
      fontSize: {
        xs:   ["0.75rem",    { lineHeight: "1.25rem" }],
        sm:   ["0.875rem",   { lineHeight: "1.25rem" }],
        base: ["1rem",       { lineHeight: "1.5rem" }],
        lg:   ["1.125rem",   { lineHeight: "1.75rem" }],
        xl:   ["1.25rem",    { lineHeight: "1.75rem" }],
        "2xl": ["1.5rem",    { lineHeight: "2rem" }],
        "3xl": ["1.75rem",   { lineHeight: "2.25rem" }],
        "4xl": ["2rem",      { lineHeight: "2.5rem" }],
      },
      opacity: {
        15: "0.15",
        25: "0.25",
      },
    },
  },
  plugins: [
    function ({ addUtilities }) {
      addUtilities({
        /* ---------- 2026 Morph Backdrop Glow ---------- */
        '.glass-backdrop': {
          '@apply backdrop-blur-lg backdrop-saturate-200 bg-glass-50': "",
        },
        '.glass-border': {
          '@apply backdrop-filter backdrop-blur-lg': "",
          '@apply border border-white/12 ring-1 ring-white/20': "",
        },
        /* ---------- 2026 Unified Button Morph ---------- */
        '.btn': {
          '@apply inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200': "",
        },
        '.btn-primary': {
          '@apply btn bg-primary-400 text-slate-950 hover:bg-primary-300 shadow-morph': "",
        },
        '.btn-secondary': {
          '@apply btn text-secondary-200 hover:text-white hover:bg-white/12': "",
        },
        '.btn-accent': {
          '@apply btn bg-primary-600/80 hover:bg-primary-500 text-white': "",
        },
        '.btn-danger': {
          '@apply btn bg-error/20 hover:bg-error/30 text-error hover:text-white': "",
        },
        /* ---------- 2026 Glass Card Morph (overhauled for reuse) ---------- */
        '.glass-card': {
          '@apply rounded-xl bg-glass-100 border border-white/10 p-6': "",
        },
        /* ---------- 2026 Status Torch Glow (green🟢/red🔴, rings) ---------- */
        '.status-light.gl-true': {
          '@apply ring-glow ring-2 ring-emerald-500/20 shadow-glow': "",
        },
        '.status-light.err-true': {
          '@apply ring-1 ring-error/40 shadow-lg': "",
        },
        /* ---------- 2026 Compact Motion Lift ---------- */
        '.morph-hover': {
          '@apply transition-all duration-150 ease-out': "",
        },
        '.morph-lift': {
          '@apply transform hover:-translate-y-0.5': "",
        },
      });
    },
  ],
};