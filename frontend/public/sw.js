/* Notificaciones al celular. No guarda nada en caché: solo muestra los avisos y deja
   confirmarlos desde el botón de la notificación, sin abrir la app. */

const CONFIRMAR = '/api/agenda/avisos/confirmar-firmado/';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (evento) => evento.waitUntil(self.clients.claim()));

self.addEventListener('push', (evento) => {
  let aviso;
  try {
    aviso = evento.data.json();
  } catch {
    return;
  }
  const opciones = {
    body: aviso.cuerpo,
    lang: 'es',
    icon: '/icono-192.png',
    // Android pinta este ícono en la barra de estado: tiene que ser una silueta de un solo color.
    badge: '/badge.png',
    // La hora en que tocaba el aviso (no la de cuando el celular lo recibió).
    timestamp: aviso.momento ? Date.parse(aviso.momento) : Date.now(),
    vibrate: [140, 70, 140],
    // Un aviso nuevo del mismo tipo no apila: reemplaza al anterior sin confirmar.
    tag: `${aviso.tipo}-${aviso.id}`,
    renotify: true,
    requireInteraction: true,
    data: { id: aviso.id, firma: aviso.firma, url: aviso.url },
    actions: aviso.accion ? [{ action: 'confirmar', title: aviso.accion }] : [],
  };
  evento.waitUntil(self.registration.showNotification(aviso.titulo, opciones));
});

self.addEventListener('notificationclick', (evento) => {
  const { firma, url } = evento.notification.data || {};
  evento.notification.close();

  if (evento.action === 'confirmar' && firma) {
    evento.waitUntil(
      fetch(CONFIRMAR, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ firma }),
      })
        .then((r) => {
          if (!r.ok) throw new Error('No se pudo confirmar');
        })
        // Si falla (sin red, firma vencida) el aviso sigue pendiente en la app.
        .catch(() => abrir(url || '/avisos')),
    );
    return;
  }
  evento.waitUntil(abrir(url || '/avisos'));
});

async function abrir(ruta) {
  const abiertas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  for (const cliente of abiertas) {
    if ('focus' in cliente) {
      await cliente.navigate(ruta).catch(() => undefined);
      return cliente.focus();
    }
  }
  return self.clients.openWindow(ruta);
}
