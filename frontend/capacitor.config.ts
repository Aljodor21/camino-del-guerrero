import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'site.servelejo.caminodelguerrero',
  appName: 'Camino del Guerrero',
  webDir: 'dist/frontend/browser',
  android: { backgroundColor: '#100d0b' },
  server: { androidScheme: 'https' },
};

export default config;
