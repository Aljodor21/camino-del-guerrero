import { definePreset } from '@primeuix/themes';
import Lara from '@primeuix/themes/lara';

export const GuerreroPreset = definePreset(Lara, {
  semantic: {
    primary: {
      50:  '#fdf2f1',
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
          0:   '#ffffff',
          50:  '#f5f5f5',
          100: '#e8e8e8',
          200: '#d4d4d4',
          300: '#b0b0b0',
          400: '#8a8a8a',
          500: '#666666',
          600: '#4a4a4a',
          700: '#2d2d2d',
          800: '#1e1e1e',
          900: '#121212',
          950: '#0a0a0a',
        },
      },
      dark: {
        surface: {
          0:   '#ffffff',
          50:  '#2d2d2d',
          100: '#272727',
          200: '#222222',
          300: '#1e1e1e',
          400: '#1a1a1a',
          500: '#161616',
          600: '#121212',
          700: '#0e0e0e',
          800: '#0a0a0a',
          900: '#060606',
          950: '#030303',
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
