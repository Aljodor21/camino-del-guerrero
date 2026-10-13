package site.servelejo.caminodelguerrero;

import android.annotation.SuppressLint;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

import java.util.Map;

/**
 * Arma las notificaciones de los avisos que llegan por Firebase. Se hace aquí, y no con la
 * notificación automática de Firebase, porque esa no admite botones: esta lleva el botón para
 * confirmar («Ya lo tomé») sin abrir la app.
 */
final class AvisoNotificacion {
    static final String CANAL = "avisos";
    private static final int COLOR = 0xFFC0392B;

    private AvisoNotificacion() {}

    static String sitio(Context c) {
        return c.getString(R.string.sitio_url);
    }

    /** Un número estable por aviso, para que uno nuevo reemplace al anterior en vez de apilarse. */
    static int idDe(String clave) {
        return clave.hashCode() & 0x7fffffff;
    }

    static void asegurarCanal(Context c) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (nm.getNotificationChannel(CANAL) != null) return;
        NotificationChannel canal = new NotificationChannel(CANAL, "Avisos", NotificationManager.IMPORTANCE_HIGH);
        canal.setDescription("Agua, proteína, comidas, entreno y dormir");
        canal.enableVibration(true);
        nm.createNotificationChannel(canal);
    }

    private static PendingIntent abrir(Context c, String ruta, int id) {
        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(sitio(c) + ruta), c, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        return PendingIntent.getActivity(c, id, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private static NotificationCompat.Builder base(Context c, String titulo, String cuerpo, String ruta, int id) {
        return new NotificationCompat.Builder(c, CANAL)
            .setSmallIcon(R.drawable.ic_stat_camino)
            .setColor(COLOR)
            .setContentTitle(titulo)
            .setContentText(cuerpo)
            .setStyle(new NotificationCompat.BigTextStyle().bigText(cuerpo))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_REMINDER)
            .setAutoCancel(true)
            .setContentIntent(abrir(c, ruta, id));
    }

    @SuppressLint("MissingPermission")
    private static void publicar(Context c, String clave, int id, NotificationCompat.Builder b) {
        NotificationManagerCompat nm = NotificationManagerCompat.from(c);
        if (!nm.areNotificationsEnabled()) return;
        asegurarCanal(c);
        nm.notify(clave, id, b.build());
    }

    /** El aviso, con su botón si se puede confirmar sin abrir la app. */
    static void mostrar(Context c, Map<String, String> d) {
        String clave = d.containsKey("clave") ? d.get("clave") : "aviso";
        String titulo = d.containsKey("titulo") ? d.get("titulo") : "Camino del Guerrero";
        String cuerpo = d.containsKey("cuerpo") ? d.get("cuerpo") : "";
        String ruta = d.containsKey("ruta") ? d.get("ruta") : "/avisos";
        int id = idDe(clave);
        NotificationCompat.Builder b = base(c, titulo, cuerpo, ruta, id);

        String accion = d.get("accion");
        String firma = d.get("firma");
        if (accion != null && !accion.isEmpty() && firma != null && !firma.isEmpty()) {
            Intent confirmar = new Intent(c, ConfirmarReceiver.class)
                .putExtra("firma", firma)
                .putExtra("clave", clave)
                .putExtra("titulo", titulo);
            b.addAction(0, accion, PendingIntent.getBroadcast(c, id, confirmar,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE));
        }
        publicar(c, clave, id, b);
    }

    /** Lo que se ve después de tocar el botón: anotado, o por qué no. */
    static void resultado(Context c, String clave, String titulo, boolean anotado) {
        int id = idDe(clave);
        NotificationCompat.Builder b = base(c, anotado ? "Anotado" : titulo,
            anotado ? titulo : "No pudimos anotarlo. Ábrela para confirmar.", "/avisos", id);
        if (anotado) b.setTimeoutAfter(4000);
        publicar(c, clave, id, b);
    }
}
