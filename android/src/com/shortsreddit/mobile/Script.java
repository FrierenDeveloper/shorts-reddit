package com.shortsreddit.mobile;

import android.content.Context;
import java.io.*;
import java.util.*;
import org.json.*;

final class Script {
  static void validate(JSONObject cfg) throws Exception {
    if (!cfg.has("categoria_video"))
      cfg.put(
          "categoria_video",
          cfg.optString("plantilla").equals("tetrica") ? "salud_mental" : "reddit");
    JSONArray scenes = cfg.optJSONArray("escenas");
    if (scenes == null || scenes.length() == 0 || scenes.length() > 100)
      throw new IOException("El guion debe contener entre 1 y 100 escenas");
    int chars = 0;
    for (int i = 0; i < scenes.length(); i++) {
      JSONObject s = scenes.getJSONObject(i);
      String t = s.optString("texto").trim();
      if (t.isEmpty()) throw new IOException("Escena " + (i + 1) + ": falta texto");
      chars += s.optString("hablado", t).length();
      double p = s.optDouble("pausa", .2);
      if (!Double.isFinite(p) || p < 0 || p > 10)
        throw new IOException("Pausa inválida en escena " + (i + 1));
    }
    if (chars > 18000)
      throw new IOException("Divide este guion: el máximo por video es 18.000 caracteres");
    double volume = cfg.optDouble("volumen_musica", 1);
    if (!Double.isFinite(volume) || volume < 0 || volume > 2)
      throw new IOException("Volumen de música: usa 0 a 2");
    JSONArray imgs = cfg.optJSONArray("imagenes");
    if (imgs != null && imgs.length() > 40) throw new IOException("Máximo 40 imágenes por guion");
    String cat = cfg.optString("categoria_video", "reddit");
    if (!Arrays.asList("reddit", "salud_mental", "psicologia_diaria").contains(cat))
      throw new IOException("Categoría desconocida");
  }

  static JSONObject fromText(String raw, String category) throws Exception {
    String[] parts = raw.trim().split("\\n", 2);
    String title = parts[0].trim();
    String text = parts.length > 1 ? parts[1].trim() : title;
    JSONArray scenes = new JSONArray();
    StringBuilder s = new StringBuilder();
    for (String sentence : text.split("(?<=[.!?])\\s+")) {
      if (s.length() > 200) {
        scenes.put(new JSONObject().put("texto", s.toString().trim()).put("pausa", .25));
        s.setLength(0);
      }
      s.append(sentence).append(' ');
    }
    if (s.length() > 0)
      scenes.put(new JSONObject().put("texto", s.toString().trim()).put("pausa", .25));
    JSONObject cfg =
        new JSONObject()
            .put("titulo", title)
            .put("descripcion", title)
            .put("escenas", scenes)
            .put("categoria_video", category)
            .put("motor_voz", "android");
    validate(cfg);
    Delivery.local(cfg);
    return cfg;
  }

  static JSONObject generate(Context c, JSONObject settings, String input, String category)
      throws Exception {
    String fname =
        category.equals("salud_mental")
            ? "prompt_guion_salud_mental.md"
            : category.equals("psicologia_diaria")
                ? "prompt_guion_psicologia_diaria.md"
                : "prompt_guion.md";
    String prompt;
    try (InputStream in = c.getAssets().open("prompts/" + fname)) {
      ByteArrayOutputStream b = new ByteArrayOutputStream();
      Store.copy(in, b);
      prompt = b.toString("UTF-8");
    }
    String base = settings.optString("base_url", "https://api.deepseek.com").replaceAll("/+$", "");
    String key = settings.optString("api_key");
    String model = settings.optString("modelo", "deepseek-chat");
    if (key.trim().isEmpty())
      throw new IOException("Configura la clave de IA o usa Convertir texto sin IA");
    JSONObject body =
        new JSONObject()
            .put("model", model)
            .put("temperature", .7)
            .put(
                "messages",
                new JSONArray()
                    .put(new JSONObject().put("role", "system").put("content", prompt))
                    .put(
                        new JSONObject()
                            .put("role", "user")
                            .put(
                                "content",
                                (category.equals("reddit")
                                        ? "POST DE REDDIT:\n"
                                        : "TEMA EDUCATIVO:\n")
                                    + input
                                    + "\nDevuelve SOLO el JSON.")));
    JSONObject response = Net.json(base + "/chat/completions", "POST", body, "Bearer " + key);
    String raw =
        response
            .getJSONArray("choices")
            .getJSONObject(0)
            .getJSONObject("message")
            .getString("content")
            .replaceAll("(?s)<think>.*?</think>", "");
    int start = raw.indexOf('{'), end = raw.lastIndexOf('}');
    if (start < 0 || end < start) throw new IOException("La IA no devolvió un guion JSON");
    JSONObject cfg = new JSONObject(raw.substring(start, end + 1));
    cfg.put("categoria_video", category);
    validate(cfg);
    Delivery.analyze(settings, cfg);
    return cfg;
  }

  static JSONObject adjust(
      Context c, JSONObject settings, JSONObject cfg, String material, double duration)
      throws Exception {
    int words = 0;
    JSONArray scenes = cfg.getJSONArray("escenas");
    for (int i = 0; i < scenes.length(); i++) {
      JSONObject s = scenes.getJSONObject(i);
      words += s.optString("hablado", s.getString("texto")).trim().split("\\s+").length;
    }
    int target = Math.max(25, (int) Math.round(words * 65.0 / duration));
    String instruction =
        "MATERIAL ORIGINAL:\n"
            + material
            + "\n\nGUION ACTUAL:\n"
            + cfg.toString()
            + "\n\n"
            + "Reescribe el JSON completo para una duración narrada de 62 a 68 segundos. La voz"
            + " REAL del teléfono midió "
            + duration
            + " segundos con "
            + words
            + " palabras. Apunta aproximadamente a "
            + target
            + " palabras habladas, ajustando también las pausas. Conserva el gancho, la"
            + " categoría, las opciones visuales y los hechos. Usa solo hechos del material"
            + " original; no inventes ejemplos, diálogos, cifras, diagnósticos ni desenlaces."
            + " Mantén un monólogo natural y conectado. No uses silencio ni repeticiones para"
            + " llegar a la duración.";
    JSONObject revised =
        generate(c, settings, instruction, cfg.optString("categoria_video", "reddit"));
    JSONObject merged = new JSONObject(cfg.toString());
    for (String k :
        new String[] {"escenas", "titulo", "descripcion", "hashtags", "imagenes", "portada"})
      if (revised.has(k)) merged.put(k, revised.get(k));
    validate(merged);
    return merged;
  }

  static String description(JSONObject cfg, String credits) {
    JSONArray tags = cfg.optJSONArray("hashtags");
    StringBuilder h = new StringBuilder();
    if (tags != null)
      for (int i = 0; i < tags.length(); i++) h.append(tags.optString(i)).append(' ');
    return cfg.optString("titulo")
        + "\n\n"
        + cfg.optString("descripcion")
        + "\n\n"
        + h
        + "\n\n"
        + credits;
  }

  static String categoryFolder(JSONObject cfg) {
    switch (cfg.optString("categoria_video", "reddit")) {
      case "salud_mental":
        return "Salud_Mental";
      case "psicologia_diaria":
        return "Psicologia_Diaria";
      default:
        return "Reddit";
    }
  }
}
