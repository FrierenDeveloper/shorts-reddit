package com.shortsreddit.mobile;

import java.io.IOException;
import java.util.Locale;
import org.json.*;

/** Contextual delivery annotations; narration stays unchanged and commands are never spoken. */
final class Delivery {
  static double number(JSONObject d, String key, double fallback, double min, double max) {
    double n = d == null ? fallback : d.optDouble(key, fallback);
    return Double.isFinite(n) ? Math.max(min, Math.min(max, n)) : fallback;
  }

  static JSONObject defaults(String emotion) throws Exception {
    double rate = 1, pitch = 1, gain = 1, pause = .25;
    switch (emotion) {
      case "suspenso":
        rate = .91;
        pitch = .95;
        pause = .6;
        break;
      case "tristeza":
        rate = .94;
        pitch = .97;
        pause = .4;
        break;
      case "alegria":
        rate = 1.06;
        pitch = 1.04;
        break;
      case "sorpresa":
        rate = 1.03;
        pitch = 1.04;
        pause = .4;
        break;
      case "enfasis":
        rate = .97;
        gain = 1.08;
        pause = .4;
        break;
      case "calma":
        rate = .96;
        pause = .35;
        break;
    }
    return new JSONObject()
        .put("emocion", emotion)
        .put("velocidad", rate)
        .put("tono", pitch)
        .put("intensidad", gain)
        .put("pausa_despues", pause)
        .put("pausa_antes", 0)
        .put("recalcar", new JSONArray());
  }

  static void local(JSONObject cfg) throws Exception {
    JSONArray scenes = cfg.getJSONArray("escenas");
    for (int i = 0; i < scenes.length(); i++) {
      JSONObject s = scenes.getJSONObject(i);
      String text = s.optString("hablado", s.getString("texto")).toLowerCase(Locale.ROOT);
      String emotion = "neutral";
      if (text.matches(
          "(?s).*(de repente|hasta que|sin embargo|no sabía|nadie sabía|en ese momento).*"))
        emotion = "suspenso";
      else if (text.matches("(?s).*(triste|llor|dolor|perdí|murió).*")) emotion = "tristeza";
      else if (text.matches("(?s).*(feliz|alegr|sonreí|celebr).*")) emotion = "alegria";
      else if (text.contains("!")) emotion = "enfasis";
      if (cfg.optString("categoria_video").equals("salud_mental") && emotion.equals("neutral"))
        emotion = "calma";
      s.put(
          "interpretacion",
          defaults(emotion)
              .put("motivo", "Sugerencia local por señales del texto; revisable en el JSON."));
    }
    cfg.put("analisis_voz", "local");
  }

  static void analyze(JSONObject settings, JSONObject cfg) throws Exception {
    JSONArray input = new JSONArray(), scenes = cfg.getJSONArray("escenas");
    for (int i = 0; i < scenes.length(); i++) {
      JSONObject s = scenes.getJSONObject(i);
      input.put(
          new JSONObject()
              .put("indice", i)
              .put("texto", s.optString("hablado", s.getString("texto")))
              .put("tipo", s.optString("tipo")));
    }
    String prompt =
        "Analiza el relato completo y su contexto como director de narración. No reescribas ni"
            + " agregues hechos. Devuelve SOLO JSON"
            + " {\"escenas\":[{\"indice\":0,\"emocion\":\"neutral\",\"motivo\":\"justificación"
            + " contextual"
            + " breve\",\"velocidad\":1.0,\"tono\":1.0,\"intensidad\":1.0,\"pausa_antes\":0.0,\"pausa_despues\":0.25,\"recalcar\":[\"palabra"
            + " exacta\"]}]}. Incluye TODOS los índices, uno por escena. Emociones: neutral,"
            + " suspenso, tristeza, alegria, sorpresa, enfasis, calma. Marca suspenso antes de"
            + " revelaciones, énfasis en contrastes y palabras decisivas; evita dramatizar todo."
            + " Velocidad 0.85–1.15, tono 0.9–1.1, intensidad 0.9–1.15, pausas 0–1.2 segundos."
            + " Recalcar debe contener solo palabras o frases literales presentes en la escena,"
            + " como máximo tres. En salud mental usa empatía y calma; no dramatices el sufrimiento"
            + " ni lo presentes como entretenimiento.";
    JSONObject body =
        new JSONObject()
            .put("model", settings.optString("modelo", "deepseek-chat"))
            .put("temperature", .2)
            .put(
                "messages",
                new JSONArray()
                    .put(new JSONObject().put("role", "system").put("content", prompt))
                    .put(
                        new JSONObject()
                            .put("role", "user")
                            .put(
                                "content",
                                "Categoría: "
                                    + cfg.optString("categoria_video")
                                    + "\nRelato: "
                                    + input)));
    String base = settings.optString("base_url", "https://api.deepseek.com").replaceAll("/+$", "");
    JSONObject response =
        Net.json(
            base + "/chat/completions", "POST", body, "Bearer " + settings.optString("api_key"));
    String raw =
        response
            .getJSONArray("choices")
            .getJSONObject(0)
            .getJSONObject("message")
            .getString("content")
            .replaceAll("(?s)<think>.*?</think>", "");
    int a = raw.indexOf('{'), b = raw.lastIndexOf('}');
    if (a < 0 || b < a) throw new IOException("El análisis de interpretación no devolvió JSON");
    JSONArray annotations = new JSONObject(raw.substring(a, b + 1)).getJSONArray("escenas");
    if (annotations.length() != scenes.length())
      throw new IOException("El análisis de voz debe cubrir todas las escenas");
    JSONObject[] checked = new JSONObject[scenes.length()];
    for (int i = 0; i < annotations.length(); i++) {
      JSONObject d = annotations.getJSONObject(i);
      int index = d.getInt("indice");
      if (index < 0 || index >= checked.length || checked[index] != null)
        throw new IOException("Índice duplicado o inválido en análisis de voz");
      String emotion = d.optString("emocion", "neutral");
      if (!java.util.Arrays.asList(
              "neutral", "suspenso", "tristeza", "alegria", "sorpresa", "enfasis", "calma")
          .contains(emotion)) emotion = "neutral";
      JSONObject clean = defaults(emotion).put("motivo", d.optString("motivo"));
      clean.put("velocidad", number(d, "velocidad", clean.getDouble("velocidad"), .85, 1.15));
      clean.put("tono", number(d, "tono", clean.getDouble("tono"), .9, 1.1));
      clean.put("intensidad", number(d, "intensidad", clean.getDouble("intensidad"), .9, 1.15));
      clean.put("pausa_antes", number(d, "pausa_antes", 0, 0, 1.2));
      clean.put(
          "pausa_despues", number(d, "pausa_despues", clean.getDouble("pausa_despues"), 0, 1.2));
      JSONArray words = d.optJSONArray("recalcar"), accepted = new JSONArray();
      JSONObject scene = scenes.getJSONObject(index);
      String spoken =
          scene
              .optString("hablado", scene.getString("texto"))
              .replace("*", "")
              .toLowerCase(Locale.ROOT);
      if (words != null)
        for (int j = 0; j < Math.min(3, words.length()); j++) {
          String w = words.optString(j).trim().replace("*", "");
          if (!w.isEmpty() && w.length() < 100 && spoken.contains(w.toLowerCase(Locale.ROOT)))
            accepted.put(w);
        }
      clean.put("recalcar", accepted);
      checked[index] = clean;
    }
    for (int i = 0; i < scenes.length(); i++)
      scenes.getJSONObject(i).put("interpretacion", checked[i]);
    cfg.put("analisis_voz", "ia_contextual");
  }
}
