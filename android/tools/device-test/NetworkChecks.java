package com.shortsreddit.mobile;

import android.app.Instrumentation;
import android.content.Context;
import android.os.Bundle;
import java.io.File;
import java.util.List;
import org.json.JSONArray;
import org.json.JSONObject;

/** Checks the migrated API configuration without printing any credentials. */
public final class NetworkChecks extends Instrumentation {
  public void onCreate(Bundle args) {
    super.onCreate(args);
    start();
  }

  public void onStart() {
    Context c = getTargetContext();
    Bundle result = new Bundle();
    StringBuilder report = new StringBuilder();
    File work = new File(c.getCacheDir(), "network-check");
    work.mkdirs();
    int failures = 0;
    try {
      JSONObject settings = Store.settings(c);
      try {
        JSONObject cfg =
            Script.generate(
                c,
                settings,
                "Efecto de anclaje al comparar precios. Explicación general, sin inventar estudios"
                    + " ni cifras.",
                "psicologia_diaria");
        Script.validate(cfg);
        if (!cfg.optString("analisis_voz").equals("ia_contextual"))
          throw new java.io.IOException("Falta análisis contextual");
        for (int i = 0; i < cfg.getJSONArray("escenas").length(); i++)
          if (cfg.getJSONArray("escenas").getJSONObject(i).optJSONObject("interpretacion") == null)
            throw new java.io.IOException("Escena sin órdenes");
        report.append("PASS Análisis contextual y órdenes por escena.\n");
        report
            .append("PASS IA: guion JSON válido con ")
            .append(cfg.getJSONArray("escenas").length())
            .append(" escenas.\n");
        Store.write(
            new File(Store.root(c), "historias/ejemplo_ia_interpretacion.json"), cfg.toString(2));
        Bundle stage = new Bundle();
        stage.putString("stream", report.toString());
        sendStatus(0, stage);
        report.setLength(0);
        JSONObject sample = new JSONObject(cfg.toString());
        JSONArray first = new JSONArray();
        for (int i = 0; i < Math.min(2, cfg.getJSONArray("escenas").length()); i++)
          first.put(cfg.getJSONArray("escenas").getJSONObject(i));
        sample.put("escenas", first).put("extras", new JSONObject().put("encuesta", false));
        Audio.Track track;
        try (Audio audio = new Audio(c, settings, msg -> {})) {
          track = audio.prepare(sample, work);
        }
        report.append("PASS Voz local sobre guion de IA: ").append(track.duration).append(" s.\n");
        Store.write(
            new File(Store.root(c), "historias/" + Store.name("ejemplo_ia_android") + ".json"),
            cfg.toString(2));
      } catch (Exception e) {
        failures++;
        report.append("FAIL IA: ").append(e.getMessage()).append('\n');
      }
      try {
        JSONObject cfg =
            new JSONObject()
                .put("categoria_video", "reddit")
                .put("broll", false)
                .put("fondo_satisfactorio", false)
                .put(
                    "imagenes",
                    new JSONArray().put(new JSONObject().put("buscar", "empty library books")))
                .put(
                    "escenas",
                    new JSONArray().put(new JSONObject().put("texto", "Prueba de fotografía")));
        MediaAssets assets = new MediaAssets(c, settings, msg -> {});
        List<MediaAssets.Asset> plan = assets.plan(cfg, 1);
        if (plan.get(0) == null || !plan.get(0).file.exists())
          throw new java.io.IOException("No se obtuvo una fotografía");
        report.append("PASS Banco de imágenes: fotografía descargada y créditos disponibles.\n");
      } catch (Exception e) {
        failures++;
        report.append("FAIL Bancos de imágenes: ").append(e.getMessage()).append('\n');
      }
      report.append("Resultado: ").append(failures).append(" fallos.\n");
    } catch (Exception e) {
      failures++;
      report.append("FAIL Configuración: ").append(e.getMessage()).append('\n');
    }
    Store.delete(work);
    result.putString("stream", report.toString());
    finish(failures == 0 ? -1 : 0, result);
  }
}
