package site.servelejo.caminodelguerrero;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * El botón de la notificación («Ya lo tomé»): manda al servidor la firma del aviso, que reemplaza
 * a la sesión, y anota el dato sin abrir la app.
 */
public class ConfirmarReceiver extends BroadcastReceiver {
    private static final int ESPERA_MS = 8000;

    @Override
    public void onReceive(Context contexto, Intent intent) {
        final PendingResult pendiente = goAsync();
        final Context app = contexto.getApplicationContext();
        final String firma = intent.getStringExtra("firma");
        final String clave = intent.getStringExtra("clave");
        final String titulo = intent.getStringExtra("titulo");
        new Thread(() -> {
            try {
                AvisoNotificacion.resultado(app, clave, titulo, confirmar(app, firma));
            } finally {
                pendiente.finish();
            }
        }).start();
    }

    private static boolean confirmar(Context app, String firma) {
        HttpURLConnection conexion = null;
        try {
            URL url = new URL(AvisoNotificacion.sitio(app) + "/api/agenda/avisos/confirmar-firmado/");
            conexion = (HttpURLConnection) url.openConnection();
            conexion.setRequestMethod("POST");
            conexion.setConnectTimeout(ESPERA_MS);
            conexion.setReadTimeout(ESPERA_MS);
            conexion.setDoOutput(true);
            conexion.setRequestProperty("Content-Type", "application/json");
            conexion.setRequestProperty("X-Cliente", "app");
            byte[] cuerpo = new JSONObject().put("firma", firma).toString().getBytes(StandardCharsets.UTF_8);
            try (OutputStream salida = conexion.getOutputStream()) {
                salida.write(cuerpo);
            }
            int codigo = conexion.getResponseCode();
            return codigo >= 200 && codigo < 300;
        } catch (Exception e) {
            return false;
        } finally {
            if (conexion != null) conexion.disconnect();
        }
    }
}
