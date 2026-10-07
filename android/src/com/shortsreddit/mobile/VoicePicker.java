package com.shortsreddit.mobile;

import android.content.Intent;
import android.content.pm.ResolveInfo;
import android.speech.tts.TextToSpeech;
import android.speech.tts.Voice;
import android.view.View;
import android.widget.*;
import java.util.*;
import org.json.JSONObject;

/** Selects installed engines per role without changing Android's system default. */
final class VoicePicker implements AutoCloseable {
  final MainActivity activity;
  final JSONObject settings;
  final List<String> ids = new ArrayList<>();
  final Spinner[] engines = new Spinner[2], voices = new Spinner[2];
  final TextToSpeech[] probes = new TextToSpeech[2];
  final List<List<Voice>> available = Arrays.asList(new ArrayList<>(), new ArrayList<>());
  boolean closed;

  VoicePicker(MainActivity a, JSONObject cfg) {
    activity = a;
    settings = cfg;
    ids.add("");
    List<String> labels = new ArrayList<>();
    labels.add("Predeterminado de Android");
    for (ResolveInfo item :
        a.getPackageManager()
            .queryIntentServices(new Intent(TextToSpeech.Engine.INTENT_ACTION_TTS_SERVICE), 0)) {
      String id = item.serviceInfo.packageName;
      if (!ids.contains(id)) {
        ids.add(id);
        labels.add(friendly(id, item.loadLabel(a.getPackageManager()).toString()));
      }
    }
    for (int role = 0; role < 2; role++) {
      final int r = role;
      String saved = cfg.optString(role == 0 ? "motor_android" : "motor_opinion_android");
      engines[r] =
          a.spinner(
              role == 0 ? "Motor del narrador" : "Motor para opinión",
              labels.toArray(new String[0]),
              Math.max(0, ids.indexOf(saved)));
      voices[r] =
          a.spinner(
              role == 0 ? "Voz del narrador" : "Voz de opinión",
              new String[] {"Buscando voces locales…"},
              0);
      engines[r].setOnItemSelectedListener(
          new AdapterView.OnItemSelectedListener() {
            public void onNothingSelected(AdapterView<?> p) {}

            public void onItemSelected(AdapterView<?> p, View v, int n, long id) {
              scan(r);
            }
          });
      a.secondaryButton(
          role == 0 ? "Escuchar voz del narrador" : "Escuchar voz de opinión", () -> preview(r));
    }
    a.hint(
        "Piper y Kokoro ofrecen voces neuronales sin internet. Elige motores distintos para"
            + " narrador y opinión; Kokoro requiere instalar su APK por separado.");
    a.secondaryButton(
        "Instalar otra voz local",
        () -> {
          Intent web =
              new Intent(
                  Intent.ACTION_VIEW,
                  android.net.Uri.parse(
                      "https://k2-fsa.github.io/sherpa/onnx/tts/apk-engine.html"));
          a.startActivity(web);
        });
  }

  static String friendly(String id, String label) {
    String s = id.toLowerCase(Locale.ROOT);
    if (s.contains("shortsreddit.voice.kokoro")) return "Kokoro · Español";
    if (s.contains("claude")) return "Piper · Claude · México";
    if (s.contains("daniela")) return "Piper · Daniela · Argentina";
    if (s.contains("sharvard")) return "Piper · Sharvard · España";
    if (s.equals("com.k2fsa.sherpa.onnx.tts.engine")) return "Piper · voz local instalada";
    if (s.contains("google")) return "Google · voces descargadas";
    return label;
  }

  void scan(int role) {
    if (closed) return;
    release(probes[role]);
    available.get(role).clear();
    String id = ids.get(engines[role].getSelectedItemPosition());
    TextToSpeech[] holder = new TextToSpeech[1];
    holder[0] =
        new TextToSpeech(
            activity,
            result ->
                activity.handler.post(
                    () -> {
                      if (closed || probes[role] != holder[0]) return;
                      List<String> names = new ArrayList<>();
                      names.add("Automática en español");
                      if (result == TextToSpeech.SUCCESS) {
                        Set<Voice> all = holder[0].getVoices();
                        if (all != null)
                          for (Voice v : all)
                            if (Audio.isSpanishLocal(v)) available.get(role).add(v);
                        available.get(role).sort(Comparator.comparing(Voice::getName));
                        for (Voice v : available.get(role)) names.add(v.getName());
                      }
                      if (available.get(role).isEmpty())
                        names.set(0, "Sin voz española descargada");
                      voices[role].setAdapter(
                          new ArrayAdapter<>(
                              activity, android.R.layout.simple_spinner_dropdown_item, names));
                      String saved =
                          settings.optString(role == 0 ? "voz_android" : "voz_opinion_android");
                      voices[role].setSelection(Math.max(0, names.indexOf(saved)));
                    }),
            id.isEmpty() ? null : id);
    probes[role] = holder[0];
  }

  void preview(int role) {
    if (probes[role] == null || available.get(role).isEmpty()) {
      activity.toast("Selecciona un motor con voz española instalada");
      return;
    }
    int index = voices[role].getSelectedItemPosition();
    Voice voice = available.get(role).get(Math.max(0, index - 1));
    probes[role].setVoice(voice);
    probes[role].setSpeechRate(1);
    probes[role].speak(
        "Hola. Esta es una prueba de narración en español para tus historias y videos.",
        TextToSpeech.QUEUE_FLUSH,
        null,
        "preview-" + role);
  }

  void save(JSONObject cfg) throws Exception {
    for (int role = 0; role < 2; role++) {
      String id = ids.get(engines[role].getSelectedItemPosition());
      cfg.put(role == 0 ? "motor_android" : "motor_opinion_android", id);
      int index = voices[role].getSelectedItemPosition();
      cfg.put(
          role == 0 ? "voz_android" : "voz_opinion_android",
          index > 0 && index <= available.get(role).size()
              ? available.get(role).get(index - 1).getName()
              : "");
    }
  }

  public void close() {
    closed = true;
    for (TextToSpeech t : probes) release(t);
  }

  static void release(TextToSpeech t) {
    if (t == null) return;
    Thread thread =
        new Thread(
            () -> {
              try {
                t.stop();
                t.shutdown();
              } catch (Exception ignored) {
              }
            },
            "voice-preview-release");
    thread.setDaemon(true);
    thread.start();
  }
}
