/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    screens: {
      xs: '420px',
      sm: '640px',
      md: '768px',
      lg: '1024px',
      xl: '1280px',
      '2xl': '1536px',
    },
    extend: {
      colors: {
        graphite: {
          950: '#07090c',
          900: '#0b0e13',
          800: '#12161d',
          700: '#1a2029',
          600: '#252d3a',
          border: 'rgba(255,255,255,0.08)',
        },
        cyan: {
          DEFAULT: '#4dd8e6',
          soft: '#8be9f2',
          dim: 'rgba(77,216,230,0.14)',
        },
        violet: {
          DEFAULT: '#a78bfa',
          dim: 'rgba(167,139,250,0.14)',
        },
        ink: {
          0: '#f4f6f8',
          1: '#c3ccd6',
          2: '#8891a0',
          3: '#5b6472',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['"Inter"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      letterSpacing: {
        widest2: '0.22em',
      },
      maxWidth: {
        content: '1440px',
      },
      transitionTimingFunction: {
        swift: 'cubic-bezier(.16,1,.3,1)',
      },
    },
  },
  plugins: [],
};
