package com.shortsreddit.mobile;

import android.app.Instrumentation;
import android.content.ContentValues;
import android.content.Context;
import android.media.MediaMetadataRetriever;
import android.net.Uri;
import android.os.Bundle;
import android.provider.MediaStore;
import java.io.*;
import org.json.*;

public final class VoiceChecks extends Instrumentation {
  public void onCreate(Bundle args) {
    super.onCreate(args);
    start();
  }

  public void onStart() {
    Context c = getTargetContext();
    Bundle result = new Bundle();
    StringBuilder report = new StringBuilder();
    File work = new File(c.getCacheDir(), "voice-check");
    work.mkdirs();
    try {
      c.getPackageManager().getPackageInfo("com.k2fsa.sherpa.onnx.tts.engine", 0);
      JSONObject s = Store.settings(c);
      s.put("motor_android", "com.k2fsa.sherpa.onnx.tts.engine")
          .put("motor_opinion_android", "com.shortsreddit.voice.claude")
          .put("voz_android", "")
          .put("voz_opinion_android", "");
      JSONObject cfg =
          new JSONObject()
              .put("titulo", "Prueba de voces locales")
              .put("categoria_video", "reddit")
              .put("plantilla", "clasica")
              .put("volumen_musica", 0)
              .put("extras", new JSONObject().put("encuesta", false))
              .put(
                  "escenas",
                  new JSONArray()
                      .put(
                          new JSONObject()
                              .put(
                                  "texto",
                                  "Hola. Soy Daniela. Esta narración se genera en tu teléfono, en"
                                      + " español y sin conexión a internet."))
                      .put(
                          new JSONObject()
                              .put(
                                  "texto",
                                  "Esta es la voz de opinión. Puedes elegir un motor diferente"
                                      + " para cada parte del video.")
                              .put("tipo", "opinion")));
      Delivery.local(cfg);
      Audio.Track track;
      try (Audio a = new Audio(c, s, msg -> report.append(msg).append('\n'))) {
        track = a.prepare(cfg, work);
      }
      if (track.pcm.length < Audio.SR * 5) throw new IOException("Audio vacío");
      File audio = new File(work, "voces.mp4");
      Audio.encode(track.pcm, audio);
      MediaMetadataRetriever m = new MediaMetadataRetriever();
      try {
        m.setDataSource(audio.getPath());
        if (!"yes".equals(m.extractMetadata(MediaMetadataRetriever.METADATA_KEY_HAS_AUDIO)))
          throw new IOException("Falta audio en la muestra");
      } finally {
        m.release();
      }
      ContentValues v = new ContentValues();
      v.put(MediaStore.Audio.Media.DISPLAY_NAME, "Voces-Android-Daniela-y-Claude.m4a");
      v.put(MediaStore.Audio.Media.MIME_TYPE, "audio/mp4");
      v.put(MediaStore.Audio.Media.RELATIVE_PATH, "Music/ShortsReddit");
      v.put(MediaStore.Audio.Media.IS_PENDING, 1);
      Uri uri = c.getContentResolver().insert(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, v);
      try (InputStream in = new FileInputStream(audio)) {
        Store.copy(in, c.getContentResolver().openOutputStream(uri));
      }
      ContentValues done = new ContentValues();
      done.put(MediaStore.Audio.Media.IS_PENDING, 0);
      c.getContentResolver().update(uri, done, null, null);
      Store.settings(c, s);
      report
          .append("PASS Piper Daniela local + Piper Claude local para opinión. Duración: ")
          .append(track.duration)
          .append(" s.\nConfiguración guardada.\n");
      result.putString("stream", report.toString());
      finish(-1, result);
    } catch (Exception e) {
      report.append("FAIL Voz local: ").append(e.getMessage()).append('\n');
      result.putString("stream", report.toString());
      finish(0, result);
    } finally {
      Store.delete(work);
    }
  }
}
