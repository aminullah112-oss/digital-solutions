/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Panel surfaces, darkest to lightest. A control room is dark so the
        // status colours carry, not for decoration.
        panel: {
          900: '#080b10',
          850: '#0b0f16',
          800: '#10151e',
          700: '#161d28',
          600: '#1f2836',
          500: '#2b3648',
        },
        edge: '#27303f',
        // Semantic status. Never used alone — always paired with text.
        ok: '#22c55e',
        fault: '#ef4444',
        warn: '#f59e0b',
        info: '#3b82f6',
        unknown: '#6b7280',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
    },
  },
  plugins: [],
}
