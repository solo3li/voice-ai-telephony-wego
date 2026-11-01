/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './django_app/templates/**/*.html',
    './django_app/**/templates/**/*.html',
    './django_app/static/**/*.html',
    './django_app/static/**/*.js',
    './django_app/staticfiles/**/*.js',
    './omnichannel/**/*.html',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans Arabic"', 'Cairo', 'Inter', '-apple-system', 'system-ui', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Tahoma', 'Arial', 'sans-serif'],
        en: ['"Plus Jakarta Sans"', 'Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        inter: ['Inter', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.75rem' }],
      },
      borderRadius: {
        'xs': '0.125rem',
      },
      colors: {
        chatwoot: {
          50: '#f5f3ff',
          100: '#ede9fe',
          200: '#ddd6fe',
          500: '#7c3aed',
          600: '#6d28d9',
          700: '#5b21b6',
          800: '#4c1d95',
          900: '#2e1065',
        },
        brand: {
          50: '#f5f3ff',
          100: '#ede9fe',
          200: '#ddd6fe',
          300: '#c4b5fd',
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
          700: '#6d28d9',
          800: '#5b21b6',
          900: '#4c1d95',
          950: '#2e1065',
          canvas: '#f8fafc',
          primary: '#7c3aed',
          primaryHover: '#6d28d9',
          gold: '#5b21b6',
          goldHover: '#4c1d95',
          dark: '#0f172a',
          muted: '#64748b',
          surface: '#FFFFFF',
          border: '#eaedf0',
        }
      },
      boxShadow: {
        '2xs': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'xs': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'card': '0 2px 8px -2px rgba(0, 0, 0, 0.05), 0 1px 4px -1px rgba(0, 0, 0, 0.03)',
      },
      backdropBlur: {
        'xs': '2px',
      },
      minHeight: {
        'calc-docs': 'calc(100vh - 140px)',
      }
    },
  },
  safelist: [
    {
      pattern: /(bg|text|border)-(emerald|rose|amber|blue|indigo|purple|violet|slate|gray|teal|cyan|red)-(50|100|200|300|400|500|600|700|800|900)/,
    },
    'active',
    'hidden',
    'opacity-0',
    'opacity-100',
    'pointer-events-none',
    'text-brand-dark',
    'text-brand-muted',
    'border-brand-border',
    'bg-brand-canvas',
    'bg-brand-surface',
    'min-h-[calc(100vh-140px)]',
    'text-2xs',
    'rounded-xs',
    'shadow-xs',
  ],
  plugins: [],
}
