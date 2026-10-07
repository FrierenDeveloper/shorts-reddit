package com.shortsreddit.mobile;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.media.*;
import android.net.Uri;
import android.os.*;
import android.provider.MediaStore;
import java.io.*;
import java.util.*;
import org.json.*;

public final class RenderService extends Service {
  static volatile boolean running = false;
  static final String CANCEL = "cancel";
  Thread worker;
  PowerManager.WakeLock wake;
  final StringBuilder log = new StringBuilder();
  File jobFile;
  NotificationManager manager;
  volatile Audio audioEngine;

  public IBinder onBind(Intent intent) {
    return null;
  }

  public int onStartCommand(Intent intent, int flags, int id) {
    if (intent != null && CANCEL.equals(intent.getAction())) {
      if (worker != null) worker.interrupt();
      else stopSelf();
      return START_NOT_STICKY;
    }
    if (running) {
      return START_NOT_STICKY;
    }
    running = true;
    manager = getSystemService(NotificationManager.class);
    manager.createNotificationChannel(
        new NotificationChannel(
            "render", "Creación de videos", NotificationManager.IMPORTANCE_LOW));
    Notification notification = notification("Preparando el proyecto");
    try {
      startForeground(
          10,
          notification,
          Build.VERSION.SDK_INT >= 35
              ? ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROCESSING
                  | ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
              : ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
    } catch (Exception e) {
      running = false;
      stopSelf();
      return START_NOT_STICKY;
    }
    wake =
        ((PowerManager) getSystemService(POWER_SERVICE))
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ShortsReddit:Render");
    wake.acquire(6 * 60 * 60 * 1000L);
    jobFile = new File(getFilesDir(), "job.json");
    worker =
        new Thread(
            () -> {
              int successes = 0, failures = 0;
              File batchLog = null;
              try {
                Store.init(this);
                JSONObject job = new JSONObject(Store.read(jobFile));
                JSONObject settings = Store.settings(this);
                JSONArray items = job.getJSONArray("items");
                batchLog = new File(Store.root(this), "registros/" + Store.name("lote") + ".txt");
                log(
                    "Lote de "
                        + items.length()
                        + " video(s). Todo el audio y el render se procesan en el teléfono.");
                for (int i = 0; i < items.length(); i++) {
                  Net.check();
                  try {
                    process(job, items.getString(i), settings, i);
                    successes++;
                  } catch (InterruptedIOException | InterruptedException cancelled) {
                    throw cancelled;
                  } catch (Exception e) {
                    failures++;
                    log("No se pudo generar el video " + (i + 1) + ": " + safe(e));
                  }
                }
                log("Finalizado: " + successes + " creado(s), " + failures + " con error.");
                state(false, failures == 0 ? "Completado" : "Terminado con errores");
              } catch (InterruptedIOException | InterruptedException e) {
                log("Trabajo cancelado. Los videos ya terminados se conservan.");
                state(false, "Cancelado");
              } catch (Exception e) {
                log("Error: " + safe(e));
                state(false, "Error");
              } finally {
                if (audioEngine != null) audioEngine.close();
                try {
                  if (batchLog != null) Store.write(batchLog, log.toString());
                } catch (Exception ignored) {
                }
                running = false;
                if (wake != null && wake.isHeld()) wake.release();
                stopForeground(STOP_FOREGROUND_REMOVE);
                stopSelf();
              }
            },
            "shorts-local-render");
    worker.start();
    return START_NOT_STICKY;
  }

  private String safe(Exception e) {
    String m = e.getMessage();
    if (m == null) return e.getClass().getSimpleName();
    return m.replaceAll("(?i)(api[_-]?key|key|token|authorization)=[^\\s&]+", "$1=[oculto]");
  }

  private void process(JSONObject job, String item, JSONObject settings, int index)
      throws Exception {
    log("Video " + (index + 1) + ": preparando guion");
    String mode = job.optString("mode", "generate");
    JSONObject cfg;
    String name, materialOriginal = item;
    if (mode.equals("render")) {
      File input = Store.resolve(this, "historias/" + item);
      cfg = new JSONObject(Store.read(input));
      Script.validate(cfg);
      name = Store.name(cfg.optString("titulo", "short"));
    } else {
      String category = job.optString("categoria_video", "reddit"), material = item;
      boolean link = item.startsWith("https://") && category.equals("reddit");
      if (link) {
        log("Leyendo Reddit");
        material = Net.reddit(item);
      }
      materialOriginal = material;
      cfg =
          mode.equals("text")
              ? Script.fromText(material, category)
              : Script.generate(this, settings, material, category);
      name = Store.name(cfg.optString("titulo", "short"));
      if (link) cfg.put("fuente_reddit", item);
      Store.write(new File(Store.root(this), "posts/" + name + ".txt"), material);
    }
    JSONObject options = job.optJSONObject("options");
    if (options != null) {
      Iterator<String> keys = options.keys();
      while (keys.hasNext()) {
        String k = keys.next();
        cfg.put(k, options.get(k));
      }
    }
    Script.validate(cfg);
    Store.write(new File(Store.root(this), "historias/" + name + ".json"), cfg.toString(2));
    String legacy = cfg.optString("motor_voz", "android");
    if (!legacy.equals("android"))
      log(
          "Voz "
              + legacy
              + " adaptada al motor local de Android. Las voces originales y la clonación CUDA no"
              + " se ejecutan en esta edición.");
    File work = new File(getCacheDir(), "trabajo-" + System.nanoTime());
    work.mkdirs();
    try {
      audioEngine = new Audio(this, settings, this::log);
      Audio.Track audio = audioEngine.prepare(cfg, work);
      audioEngine.close();
      audioEngine = null;
      for (int attempt = 0;
          mode.equals("generate") && attempt < 2 && (audio.duration < 60 || audio.duration > 70);
          attempt++) {
        log("Ajustando guion a la duración real de la voz del teléfono (" + (attempt + 1) + "/2)");
        cfg = Script.adjust(this, settings, cfg, materialOriginal, audio.duration);
        Store.write(new File(Store.root(this), "historias/" + name + ".json"), cfg.toString(2));
        audioEngine = new Audio(this, settings, this::log);
        audio = audioEngine.prepare(cfg, work);
        audioEngine.close();
        audioEngine = null;
      }
      log("Duración real: " + String.format(Locale.ROOT, "%.1f", audio.duration) + " segundos");
      if (!name.contains("demo") && (audio.duration < 60 || audio.duration > 70))
        log(
            "Duración fuera del rango sugerido 60–70 s: revisa o edita el guion si quieres"
                + " ajustarla.");
      MediaAssets assets = new MediaAssets(this, settings, this::log);
      List<MediaAssets.Asset> plan = assets.plan(cfg, audio.scenes.size());
      File audioFile = new File(work, "audio.mp4"),
          videoFile = new File(work, "video.mp4"),
          finalFile = new File(work, "final.mp4");
      Audio.encode(audio.pcm, audioFile);
      int width = settings.optBoolean("resolucion_720", false) ? 720 : 1080,
          height = width == 720 ? 1280 : 1920;
      try (Renderer renderer = new Renderer(this, cfg, audio, plan, width, height)) {
        renderer.encode(videoFile, this::log);
      }
      Renderer.mux(videoFile, audioFile, finalFile);
      MediaMetadataRetriever verify = new MediaMetadataRetriever();
      try {
        verify.setDataSource(finalFile.getPath());
        String duration = verify.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION);
        if (duration == null
            || Long.parseLong(duration) <= 0
            || !"yes".equals(verify.extractMetadata(MediaMetadataRetriever.METADATA_KEY_HAS_AUDIO)))
          throw new IOException("El archivo final no contiene video y audio válidos");
      } finally {
        verify.release();
      }
      Net.check();
      File dest =
          new File(Store.root(this), "salida/" + Script.categoryFolder(cfg) + "/" + name + ".mp4");
      dest.getParentFile().mkdirs();
      java.nio.file.Files.move(finalFile.toPath(), dest.toPath());
      Store.write(
          new File(dest.getParentFile(), name + ".txt"), Script.description(cfg, assets.credits()));
      Store.write(new File(dest.getParentFile(), name + "_creditos.txt"), assets.credits());
      JSONObject meta =
          new JSONObject()
              .put("duration", audio.duration)
              .put("word_timing", audio.approximate ? "aproximado" : "motor_o_importado")
              .put("width", width)
              .put("height", height)
              .put("published", false);
      Store.write(new File(dest.getParentFile(), name + ".meta.json"), meta.toString(2));
      try {
        publish(dest, Script.categoryFolder(cfg));
      } catch (Exception e) {
        log("Video creado en la biblioteca. La copia a Movies falló: usa Exportar video.");
      }
      log("Video creado: " + dest.getName());
    } finally {
      if (audioEngine != null) {
        audioEngine.close();
        audioEngine = null;
      }
      Store.delete(work);
    }
  }

  void publish(File file, String category) throws Exception {
    ContentValues v = new ContentValues();
    v.put(MediaStore.Video.Media.DISPLAY_NAME, file.getName());
    v.put(MediaStore.Video.Media.MIME_TYPE, "video/mp4");
    v.put(MediaStore.Video.Media.RELATIVE_PATH, "Movies/ShortsReddit/" + category);
    v.put(MediaStore.Video.Media.IS_PENDING, 1);
    Uri uri = getContentResolver().insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, v);
    if (uri == null) throw new IOException("No se pudo guardar en Movies");
    try (InputStream in = new FileInputStream(file)) {
      Store.copy(in, getContentResolver().openOutputStream(uri));
      ContentValues done = new ContentValues();
      done.put(MediaStore.Video.Media.IS_PENDING, 0);
      getContentResolver().update(uri, done, null, null);
    } catch (Exception e) {
      getContentResolver().delete(uri, null, null);
      throw e;
    }
  }

  void log(String message) {
    synchronized (log) {
      log.append(message).append('\n');
      if (log.length() > 32000) log.delete(0, log.length() - 24000);
    }
    state(true, message);
    if (manager != null) manager.notify(10, notification(message));
  }

  void state(boolean active, String status) {
    try {
      JSONObject s =
          new JSONObject()
              .put("active", active)
              .put("status", status)
              .put("log", log.toString())
              .put("updated", System.currentTimeMillis());
      Store.write(new File(getFilesDir(), "status.json"), s.toString());
    } catch (Exception ignored) {
    }
  }

  Notification notification(String msg) {
    Intent view = new Intent(this, MainActivity.class);
    PendingIntent show =
        PendingIntent.getActivity(
            this, 0, view, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    Intent cancel = new Intent(this, RenderService.class).setAction(CANCEL);
    PendingIntent stop =
        PendingIntent.getService(
            this, 1, cancel, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    return new Notification.Builder(this, "render")
        .setContentTitle("Shorts Reddit · render local")
        .setContentText(msg)
        .setSmallIcon(android.R.drawable.ic_media_play)
        .setContentIntent(show)
        .setOngoing(true)
        .addAction(new Notification.Action.Builder(null, "Cancelar", stop).build())
        .build();
  }

  public void onTimeout(int startId, int type) {
    if (worker != null) worker.interrupt();
    stopSelf();
  }

  public void onDestroy() {
    if (worker != null && worker.isAlive()) worker.interrupt();
    if (audioEngine != null) audioEngine.close();
    if (wake != null && wake.isHeld()) wake.release();
    super.onDestroy();
  }
}
