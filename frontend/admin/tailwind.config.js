/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: '#1B6EF3',
          dk: '#0D4DB5',
          lt: '#EBF2FF',
        },
        accent2: {
          DEFAULT: '#7C3AED',
          dk: '#5B21B6',
          lt: '#F5F3FF',
        },
        sc: {
          green: '#12A564',
          'green-lt': '#E8F8F1',
          'green-dk': '#0A7347',
          red: '#E03A3A',
          'red-lt': '#FEECEC',
          'red-dk': '#B02626',
          orange: '#E87722',
          'orange-lt': '#FEF3E8',
          'orange-dk': '#B85A10',
          yellow: '#D4960A',
          'yellow-lt': '#FEF9E7',
        },
        bg: '#F5F6F8',
        surface: '#FFFFFF',
        surface2: '#F7F8FA',
        surface3: '#EFF1F4',
        border: '#E2E5EA',
        text1: '#1A1D23',
        text2: '#4B5563',
        text3: '#9AA0AF',
      },
      fontFamily: {
        sans: ['DM Sans', 'sans-serif'],
        mono: ['DM Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
