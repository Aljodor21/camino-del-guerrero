package site.servelejo.caminodelguerrero;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Los plugins propios se registran antes de iniciar el puente.
        registerPlugin(ActualizadorPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
