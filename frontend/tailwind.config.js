/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f7ff',
          100: '#e0effe',
          200: '#bae0fd',
          300: '#7cc5fb',
          400: '#36a6f6',
          500: '#0c8ce9',
          600: '#016ec7',
          700: '#0258a1',
          800: '#064b85',
          900: '#0b3f6f',
          950: '#07284a',
        },
      },
    },
  },
  plugins: [],
}
