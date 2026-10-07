package com.shortsreddit.mobile;

import android.app.Instrumentation;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.media.MediaExtractor;
import android.media.MediaMetadataRetriever;
import android.net.Uri;
import android.os.Bundle;
import android.provider.MediaStore;
import java.io.*;
import java.util.*;
import org.json.*;

public final class DeviceChecks extends Instrumentation {
  final StringBuilder report = new StringBuilder();
  int passed = 0, failed = 0;

  interface Checked {
    void run() throws Exception;
  }

  void test(String title, Checked call) {
    Bundle stage = new Bundle();
    stage.putString("stream", "Comprobando: " + title + "\n");
    sendStatus(0, stage);
    try {
      call.run();
      passed++;
      report.append("PASS ").append(title).append('\n');
    } catch (Exception e) {
      failed++;
      report.append("FAIL ").append(title).append(": ").append(e.getMessage()).append('\n');
    }
  }

  void require(boolean b, String msg) throws IOException {
    if (!b) throw new IOException(msg);
  }

  public void onCreate(Bundle args) {
    super.onCreate(args);
    start();
  }

  public void onStart() {
    Context c = getTargetContext();
    File work = new File(c.getCacheDir(), "device-check");
    work.mkdirs();
    long begin = System.currentTimeMillis();
    test(
        "Guiones y protección de rutas",
        () -> {
          Store.init(c);
          Script.validate(
              new JSONObject(Store.read(new File(Store.root(c), "historias/demo.json"))));
          boolean rejects = false;
          try {
            Script.validate(new JSONObject("{\"escenas\":[{\"texto\":\"\"}]}"));
          } catch (Exception expected) {
            rejects = true;
          }
          require(rejects, "Aceptó una escena vacía");
          rejects = false;
          try {
            Store.resolve(c, "../../fuera");
          } catch (IOException expected) {
            rejects = true;
          }
          require(rejects, "Aceptó una ruta fuera del proyecto");
        });
    test(
        "Cifrado y persistencia de ajustes",
        () -> {
          JSONObject old = Store.settings(c);
          try {
            Store.settings(c, new JSONObject().put("api_key", "check-only").put("modelo", "check"));
            require(
                Store.settings(c).getString("api_key").equals("check-only"),
                "No recuperó la configuración");
          } finally {
            Store.settings(c, old);
          }
        });
    // ZIP roundtrip was checked before transferring the user's large media library.
    // Keep repeat render checks small and leave those personal files untouched.
    test(
        "Render nativo 1080p + voz local + AAC + MP4",
        () -> {
          JSONObject cfg =
              new JSONObject(Store.read(new File(Store.root(c), "historias/demo.json")));
          JSONObject settings = Store.settings(c);
          Audio.Track track;
          try (Audio audio = new Audio(c, settings, t -> report.append(t).append('\n'))) {
            track = audio.prepare(cfg, work);
          }
          require(track.duration > 5, "Narración vacía");
          MediaAssets assets = new MediaAssets(c, settings, t -> report.append(t).append('\n'));
          List<MediaAssets.Asset> plan = assets.plan(cfg, track.scenes.size());
          File v = new File(work, "video.mp4"),
              a = new File(work, "audio.mp4"),
              out = new File(work, "demo.mp4");
          Audio.encode(track.pcm, a);
          try (Renderer r = new Renderer(c, cfg, track, plan, 1080, 1920)) {
            r.encode(v, t -> report.append(t).append('\n'));
          }
          Renderer.mux(v, a, out);
          MediaMetadataRetriever m = new MediaMetadataRetriever();
          try {
            m.setDataSource(out.getPath());
            require(
                "1080".equals(m.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)),
                "Ancho incorrecto");
            require(
                "1920".equals(m.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)),
                "Alto incorrecto");
            require(
                "yes".equals(m.extractMetadata(MediaMetadataRetriever.METADATA_KEY_HAS_AUDIO)),
                "Falta audio");
            long duration =
                Long.parseLong(m.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION));
            require(
                Math.abs(duration / 1000.0 - track.duration) < .4, "Duración final incoherente");
            Bitmap b = m.getFrameAtTime(3000000, MediaMetadataRetriever.OPTION_CLOSEST);
            require(b != null, "No se pudo decodificar el MP4");
            try (OutputStream image =
                new FileOutputStream(new File(c.getFilesDir(), "device-check-frame.png"))) {
              b.compress(Bitmap.CompressFormat.PNG, 100, image);
            }
            b.recycle();
          } finally {
            m.release();
          }
          MediaExtractor e = new MediaExtractor();
          try {
            e.setDataSource(out.getPath());
            require(e.getTrackCount() == 2, "El MP4 no tiene dos pistas");
          } finally {
            e.release();
          }
          String name = Store.name("Ejemplo_verificado_en_15T_Pro");
          File dest = new File(Store.root(c), "salida/Reddit/" + name + ".mp4");
          dest.getParentFile().mkdirs();
          java.nio.file.Files.copy(out.toPath(), dest.toPath());
          Store.write(new File(dest.getParentFile(), name + ".txt"), Script.description(cfg, ""));
          Store.write(
              new File(dest.getParentFile(), name + ".meta.json"),
              new JSONObject()
                  .put("published", false)
                  .put("duration", track.duration)
                  .put("word_timing", track.approximate ? "aproximado" : "motor")
                  .toString());
          publish(
              c,
              dest,
              MediaStore.Video.Media.EXTERNAL_CONTENT_URI,
              "Movies/ShortsReddit",
              "verificacion-android.mp4",
              "video/mp4");
          publish(
              c,
              new File(c.getFilesDir(), "device-check-frame.png"),
              MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
              "Pictures/ShortsReddit",
              "verificacion-android.png",
              "image/png");
          report
              .append("Video: ")
              .append(dest.getName())
              .append("\nDuración: ")
              .append(track.duration)
              .append(" s\n");
        });
    test(
        "Foto local, clip MP4, decodificación AAC y render 720p",
        () -> {
          List<File> videos = Store.list(c, "salida", ".mp4");
          require(!videos.isEmpty(), "Falta el MP4 de prueba");
          File source = videos.get(0);
          float[] decoded = Audio.decode(source);
          require(decoded.length > 24000, "Audio AAC vacío");
          File photoFile = new File(work, "foto.jpg");
          Bitmap bitmap = Bitmap.createBitmap(600, 900, Bitmap.Config.ARGB_8888);
          Canvas canvas = new Canvas(bitmap);
          canvas.drawColor(0xff274c40);
          Paint p = new Paint();
          p.setColor(0xfff9d575);
          canvas.drawCircle(300, 400, 140, p);
          try (OutputStream out = new FileOutputStream(photoFile)) {
            bitmap.compress(Bitmap.CompressFormat.JPEG, 90, out);
          }
          bitmap.recycle();
          JSONObject cfg =
              Script.fromText(
                  "Prueba de fondos\nUna foto local. Un video local.", "psicologia_diaria");
          cfg.put("plantilla", "pop");
          cfg.put("extras", new JSONObject().put("tarjeta", false).put("encuesta", false));
          Audio.Track track = new Audio.Track();
          track.duration = 4;
          track.pcm = new float[Audio.SR * 4];
          List<MediaAssets.Asset> plan = new ArrayList<>();
          for (int i = 0; i < 2; i++) {
            Audio.Scene s = new Audio.Scene();
            s.json = new JSONObject().put("texto", i == 0 ? "Foto local" : "Video local");
            s.a = i * 2;
            s.b = s.a + 2;
            s.speechEnd = s.b;
            s.words.add(new Audio.Word(i == 0 ? "Foto local" : "Video local", s.a, s.b, true));
            track.scenes.add(s);
            plan.add(new MediaAssets.Asset(i == 0 ? photoFile : source, i == 1));
          }
          File out = new File(work, "fondos.mp4");
          try (Renderer r = new Renderer(c, cfg, track, plan, 720, 1280)) {
            r.encode(out, t -> {});
          }
          MediaMetadataRetriever m = new MediaMetadataRetriever();
          try {
            m.setDataSource(out.getPath());
            require(
                "720".equals(m.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)),
                "Ancho 720p incorrecto");
            require(
                m.getFrameAtTime(3000000, MediaMetadataRetriever.OPTION_CLOSEST) != null,
                "Falló la extracción del fondo de video");
          } finally {
            m.release();
          }
        });
    test(
        "Servicio de render, notificación y exportación a Movies",
        () -> {
          startActivitySync(
              new Intent(c, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
          Thread.sleep(500);
          int before = Store.list(c, "salida", ".mp4").size();
          JSONObject job =
              new JSONObject().put("mode", "render").put("items", new JSONArray().put("demo.json"));
          Store.write(new File(c.getFilesDir(), "job.json"), job.toString());
          c.startForegroundService(new Intent(c, RenderService.class));
          long deadline = System.currentTimeMillis() + 120000;
          while (!RenderService.running && System.currentTimeMillis() < deadline) Thread.sleep(100);
          require(RenderService.running, "No inició el servicio");
          while (RenderService.running && System.currentTimeMillis() < deadline) Thread.sleep(200);
          require(!RenderService.running, "El servicio no terminó");
          require(
              Store.list(c, "salida", ".mp4").size() == before + 1,
              "El servicio no produjo un video");
          JSONObject status = new JSONObject(Store.read(new File(c.getFilesDir(), "status.json")));
          require(!status.getBoolean("active"), "Estado activo después de terminar");
          report.append(status.optString("status")).append('\n');
        });
    report
        .append("Checks: ")
        .append(passed)
        .append(" correctos, ")
        .append(failed)
        .append(" fallidos. Tiempo: ")
        .append((System.currentTimeMillis() - begin) / 1000)
        .append(" s\n");
    try {
      Store.write(new File(c.getFilesDir(), "device-check-report.txt"), report.toString());
    } catch (Exception ignored) {
    }
    Store.delete(work);
    Bundle result = new Bundle();
    result.putString("stream", report.toString());
    finish(failed == 0 ? -1 : 0, result);
  }

  void publish(Context c, File file, Uri collection, String folder, String name, String mime)
      throws Exception {
    ContentValues v = new ContentValues();
    v.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
    v.put(MediaStore.MediaColumns.MIME_TYPE, mime);
    v.put(MediaStore.MediaColumns.RELATIVE_PATH, folder);
    v.put(MediaStore.MediaColumns.IS_PENDING, 1);
    Uri uri = c.getContentResolver().insert(collection, v);
    if (uri == null) throw new IOException("No se creó el archivo de verificación");
    try (InputStream in = new FileInputStream(file)) {
      Store.copy(in, c.getContentResolver().openOutputStream(uri));
    }
    ContentValues done = new ContentValues();
    done.put(MediaStore.MediaColumns.IS_PENDING, 0);
    c.getContentResolver().update(uri, done, null, null);
  }
}
