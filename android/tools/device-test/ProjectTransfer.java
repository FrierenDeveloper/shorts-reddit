package com.shortsreddit.mobile;

import android.app.Instrumentation;
import android.content.Context;
import android.os.Bundle;
import java.io.*;
import java.net.*;
import org.json.*;

/** Temporary USB-only migration helper; not included in the production APK. */
public final class ProjectTransfer extends Instrumentation {
  public void onCreate(Bundle args) {
    super.onCreate(args);
    start();
  }

  public void onStart() {
    Context c = getTargetContext();
    File file = new File(c.getCacheDir(), "usb-transfer.zip");
    Bundle result = new Bundle();
    try (ServerSocket server = new ServerSocket(8877, 1, InetAddress.getByName("127.0.0.1"))) {
      server.setSoTimeout(120000);
      Bundle ready = new Bundle();
      ready.putString("stream", "Listo para transferencia USB local\n");
      sendStatus(1, ready);
      try (Socket socket = server.accept()) {
        socket.setSoTimeout(120000);
        DataInputStream in = new DataInputStream(new BufferedInputStream(socket.getInputStream()));
        long length = in.readLong();
        if (length < 0 || length > 8L * 1024 * 1024 * 1024)
          throw new IOException("Tamaño de ZIP inválido");
        byte[] bytes = new byte[65536];
        try (OutputStream out = new FileOutputStream(file)) {
          long remaining = length;
          while (remaining > 0) {
            int n = in.read(bytes, 0, (int) Math.min(bytes.length, remaining));
            if (n < 0) throw new EOFException("Transferencia interrumpida");
            out.write(bytes, 0, n);
            remaining -= n;
          }
        }
        int settingsLength = in.readInt();
        if (settingsLength < 0 || settingsLength > 65536)
          throw new IOException("Configuración demasiado grande");
        byte[] config = new byte[settingsLength];
        in.readFully(config);
        Store.init(c);
        try (InputStream zip = new FileInputStream(file)) {
          Store.unzip(c, zip);
        }
        JSONObject merged = Store.settings(c),
            incoming = new JSONObject(new String(config, "UTF-8"));
        for (String k : new String[] {"base_url", "api_key", "modelo", "pexels", "pixabay"})
          if (incoming.has(k)) merged.put(k, incoming.get(k));
        Store.settings(c, merged);
        result.putString(
            "stream",
            "Transferencia completa. Guiones: "
                + Store.list(c, "historias", ".json").size()
                + ". Videos: "
                + Store.list(c, "salida", ".mp4").size()
                + ". Claves guardadas cifradas.\n");
      }
      finish(-1, result);
    } catch (Exception e) {
      result.putString("stream", "Error de transferencia: " + e.getMessage() + "\n");
      finish(0, result);
    } finally {
      file.delete();
    }
  }
}
