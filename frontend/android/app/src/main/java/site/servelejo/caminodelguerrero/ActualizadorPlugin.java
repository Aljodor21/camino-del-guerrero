package site.servelejo.caminodelguerrero;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.FileProvider;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Actualiza la app desde adentro: baja el APK de la última versión, comprueba que sea de esta misma
 * app y abre el instalador de Android (que pide la confirmación de la persona y lo instala encima,
 * conservando la sesión y los datos). Android no deja instalar en silencio una app de fuera de la
 * Play Store: la persona siempre toca "Instalar".
 */
@CapacitorPlugin(name = "Actualizador")
public class ActualizadorPlugin extends Plugin {

    private volatile boolean descargando = false;

    @PluginMethod
    public void descargarEInstalar(PluginCall call) {
        String direccion = call.getString("url");
        if (direccion == null || !direccion.startsWith("https://")) {
            call.reject("La dirección de la actualización no es válida.");
            return;
        }
        Context contexto = getContext();

        // Desde Android 8 cada app necesita el permiso de "instalar apps desconocidas".
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                && !contexto.getPackageManager().canRequestPackageInstalls()) {
            Intent ajustes = new Intent(
                    Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + contexto.getPackageName()));
            ajustes.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            contexto.startActivity(ajustes);
            JSObject respuesta = new JSObject();
            respuesta.put("estado", "permiso");
            call.resolve(respuesta);
            return;
        }

        if (descargando) {
            call.reject("Ya se está descargando la actualización.");
            return;
        }
        descargando = true;
        new Thread(() -> descargar(direccion, call), "actualizador").start();
    }

    private void descargar(String direccion, PluginCall call) {
        File carpeta = new File(getContext().getCacheDir(), "actualizacion");
        File destino = new File(carpeta, "camino-del-guerrero.apk");
        File parcial = new File(carpeta, "camino-del-guerrero.apk.parcial");
        HttpURLConnection conexion = null;
        try {
            if (!carpeta.exists() && !carpeta.mkdirs()) {
                throw new IOException("No se pudo crear la carpeta temporal.");
            }
            conexion = (HttpURLConnection) new URL(direccion).openConnection();
            conexion.setConnectTimeout(15000);
            conexion.setReadTimeout(30000);
            int codigo = conexion.getResponseCode();
            if (codigo != HttpURLConnection.HTTP_OK) {
                throw new IOException("El servidor respondió " + codigo + ".");
            }
            long total = conexion.getContentLengthLong();
            long bytes = 0;
            long ultimoAviso = 0;
            try (InputStream entrada = conexion.getInputStream();
                    FileOutputStream salida = new FileOutputStream(parcial)) {
                byte[] buffer = new byte[64 * 1024];
                int leidos;
                while ((leidos = entrada.read(buffer)) != -1) {
                    salida.write(buffer, 0, leidos);
                    bytes += leidos;
                    long ahora = System.currentTimeMillis();
                    if (ahora - ultimoAviso > 150) {
                        ultimoAviso = ahora;
                        avisarProgreso(bytes, total);
                    }
                }
            }
            if (total > 0 && parcial.length() != total) {
                throw new IOException("La descarga quedó incompleta.");
            }
            avisarProgreso(parcial.length(), total);

            if (destino.exists() && !destino.delete()) {
                throw new IOException("No se pudo reemplazar la descarga anterior.");
            }
            if (!parcial.renameTo(destino)) {
                throw new IOException("No se pudo guardar el archivo descargado.");
            }

            // Que sea un APK de esta misma app (y no un archivo roto o cualquier otro).
            PackageInfo paquete = getContext().getPackageManager()
                    .getPackageArchiveInfo(destino.getAbsolutePath(), 0);
            if (paquete == null || !getContext().getPackageName().equals(paquete.packageName)) {
                destino.delete();
                throw new IOException("El archivo descargado no es la app de Camino del Guerrero.");
            }

            instalar(destino);
            JSObject respuesta = new JSObject();
            respuesta.put("estado", "instalando");
            call.resolve(respuesta);
        } catch (Exception e) {
            parcial.delete();
            call.reject(e.getMessage() != null ? e.getMessage() : "No se pudo descargar la actualización.", e);
        } finally {
            descargando = false;
            if (conexion != null) {
                conexion.disconnect();
            }
        }
    }

    private void instalar(File apk) {
        Context contexto = getContext();
        Uri uri = FileProvider.getUriForFile(contexto, contexto.getPackageName() + ".fileprovider", apk);
        Intent instalar = new Intent(Intent.ACTION_VIEW);
        instalar.setDataAndType(uri, "application/vnd.android.package-archive");
        instalar.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        contexto.startActivity(instalar);
    }

    private void avisarProgreso(long bytes, long total) {
        JSObject datos = new JSObject();
        datos.put("bytes", bytes);
        datos.put("total", total);
        notifyListeners("progreso", datos);
    }
}
