export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'], mono: ['JetBrains Mono', 'monospace'], serif: ['Fraunces', 'Georgia', 'serif'] },
      colors: { ink: { 950: '#f4ecda', 900: '#fbf5e6', 800: '#fffaf0', 700: '#efe4cc', 600: '#e2d3b3' } },
    },
  },
}
