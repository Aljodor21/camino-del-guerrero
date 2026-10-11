import { definePreset } from '@primeuix/themes';
import Lara from '@primeuix/themes/lara';

export const GuerreroPreset = definePreset(Lara, {
  semantic: {
    primary: {
      50: '#fdf2f1',
      100: '#fbe5e3',
      200: '#f6cbc8',
      300: '#f0a7a3',
      400: '#e5746e',
      500: '#C0392B',
      600: '#a83224',
      700: '#8e2a1e',
      800: '#74231a',
      900: '#5c1c15',
      950: '#3d1210',
    },
    colorScheme: {
      light: {
        surface: {
          0: '#ffffff',
          50: '#faf8f5',
          100: '#f2ede7',
          200: '#e5ddd4',
          300: '#d2c8bd',
          400: '#a3988d',
          500: '#7b7067',
          600: '#5b524a',
          700: '#433b34',
          800: '#2c2621',
          900: '#1c1814',
          950: '#110e0c',
        },
      },
      dark: {
        surface: {
          0: '#ffffff',
          50: '#3a2f27',
          100: '#322820',
          200: '#2b221c',
          300: '#1b1511',
          400: '#18120f',
          500: '#15100d',
          600: '#100d0b',
          700: '#0c0a08',
          800: '#080706',
          900: '#050404',
          950: '#020202',
        },
      },
    },
  },
  components: {
    card: {
      colorScheme: {
        dark: {
          root: {
            background: '{surface.300}',
            color: '{surface.0}',
          },
        },
      },
    },
  },
});
