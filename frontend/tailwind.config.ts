import type { Config } from 'tailwindcss';

export default {
  theme: {
    extend: {
      colors: {
        carbon: '#2B2B2B',
        brick: { DEFAULT: '#C2C4C3', light: '#E8E8E6' },
        sand: { DEFAULT: '#FFD9A0', light: '#FFF5E6' },
        paprika: '#E66A32',
        saffron: '#FF8C42',
      },
    },
  },
} satisfies Config;
