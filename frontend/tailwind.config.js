/** @type {import('tailwindcss').Config} */
import preset from './tailwind.preset.js';

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  presets: [preset],
  theme: {
    extend: {
      fontFamily: {
        ui: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["Fira Code", "Menlo", "Monaco", "monospace"],
      },
      animation: {
        'ken-burns': 'kenBurns 20s ease-in-out infinite alternate',
      },
      keyframes: {
        kenBurns: {
          '0%': { transform: 'scale(1) translate(0, 0)' },
          '100%': { transform: 'scale(1.12) translate(-1%, -1%)' },
        },
      },
    },
  },
  plugins: [],
};
