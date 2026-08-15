/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./backend/app/renderer/templates/**/*.html",
    "./backend/app/renderer/highlight.py",
    "./backend/app/renderer/render.py",
    "./backend/app/renderer/static/**/*.css",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: '#080c14',
          surface: '#0e1626',
          card: '#131e33',
          border: '#1e2d4a',
          accent: '#38bdf8',
          glow: '#6366f1',
          emerald: '#10b981',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Noto Color Emoji', 'Segoe UI Emoji', 'sans-serif'],
        mono: ['"Fira Code"', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'glow-cyan': '0 0 30px -5px rgba(56, 189, 248, 0.25)',
        'glow-indigo': '0 0 30px -5px rgba(99, 102, 241, 0.25)',
        'glow-emerald': '0 0 30px -5px rgba(16, 185, 129, 0.25)',
        'card-elevated': '0 20px 40px -15px rgba(0, 0, 0, 0.7)',
      },
    },
  },
  plugins: [],
}
