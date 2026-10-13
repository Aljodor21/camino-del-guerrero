package site.servelejo.caminodelguerrero;

import androidx.annotation.NonNull;

import com.capacitorjs.plugins.pushnotifications.MessagingService;
import com.google.firebase.messaging.RemoteMessage;

import java.util.Map;

/**
 * Recibe los avisos de Firebase, con la app abierta o cerrada. Sigue avisando a la app (para que
 * refresque la bandeja) y arma la notificación con su botón de confirmar.
 */
public class AvisosMessagingService extends MessagingService {
    @Override
    public void onMessageReceived(@NonNull RemoteMessage mensaje) {
        super.onMessageReceived(mensaje);
        Map<String, String> datos = mensaje.getData();
        // Los mensajes con «notification» (de la consola de Firebase) ya los muestra el sistema.
        if (mensaje.getNotification() == null && datos.containsKey("titulo")) {
            AvisoNotificacion.mostrar(this, datos);
        }
    }
}
