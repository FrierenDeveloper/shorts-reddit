package com.shortsreddit.mobile;

import android.content.*;
import android.media.*;
import android.os.*;
import android.speech.tts.*;
import java.io.*;
import java.nio.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

final class Audio implements AutoCloseable {
  static final int SR = 24000, MAX_SECONDS = 180;

  interface Progress {
    void log(String text);
  }

  static final class Word {
    String text;
    double a, b;
    boolean highlight;

    Word(String t, double start, double end, boolean hi) {
      text = t;
      a = start;
      b = end;
      highlight = hi;
    }
  }

  static final class Scene {
    JSONObject json;
    float[] pcm;
    double a, b, speechEnd;
    List<Word> words = new ArrayList<>();
  }

  static final class Track {
    float[] pcm;
    List<Scene> scenes = new ArrayList<>();
    double duration;
    boolean approximate;
  }

  final Context context;
  final JSONObject settings;
  final Progress progress;
  TextToSpeech tts;
  String loadedEngine = "";

  Audio(Context c, JSONObject s, Progress p) {
    context = c;
    settings = s;
    progress = p;
  }

  private void init(String engine) throws Exception {
    CountDownLatch ready = new CountDownLatch(1);
    int[] status = {TextToSpeech.ERROR};
    new Handler(Looper.getMainLooper())
        .post(
            () -> {
              tts =
                  new TextToSpeech(
                      context,
                      result -> {
                        status[0] = result;
                        ready.countDown();
                      },
                      engine.isEmpty() ? null : engine);
            });
    if (!ready.await(30, TimeUnit.SECONDS) || status[0] != TextToSpeech.SUCCESS)
      throw new IOException(
          "No se pudo iniciar la voz local. Instala los datos de voz en español en Ajustes de"
              + " Android.");
    Set<Voice> voices = tts.getVoices();
    if (voices == null) throw new IOException("No hay voces instaladas");
    if (choose(false) == null)
      throw new IOException(
          "Falta una voz local en español. Abre Instalar voces en Ajustes de la app y descarga"
              + " español.");
    loadedEngine = engine;
  }

  private Voice choose(boolean opinion) {
    String requested = settings.optString(opinion ? "voz_opinion_android" : "voz_android");
    Voice fallback = null;
    Set<Voice> voices = tts.getVoices();
    if (voices == null) return null;
    List<Voice> sorted = new ArrayList<>(voices);
    sorted.sort(Comparator.comparing(Voice::getName));
    for (Voice v : sorted) {
      if (!isSpanishLocal(v)) continue;
      if (v.getName().equals(requested)) return v;
      if (fallback == null || v.getQuality() > fallback.getQuality()) fallback = v;
    }
    return fallback;
  }

  static boolean isSpanishLocal(Voice v) {
    String lang = v.getLocale().getLanguage();
    return (lang.equals("es") || lang.equals("spa"))
        && !v.isNetworkConnectionRequired()
        && !v.getFeatures().contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED);
  }

  Track prepare(JSONObject cfg, File work) throws Exception {
    JSONArray json = cfg.getJSONArray("escenas");
    Track track = new Track();
    List<float[]> pieces = new ArrayList<>();
    int total = 0;
    for (int i = 0; i < json.length(); i++) {
      Net.check();
      Scene scene = new Scene();
      scene.json = json.getJSONObject(i);
      String spoken =
          scene.json.optString("hablado", scene.json.getString("texto")).replace("*", "").trim();
      String audio = scene.json.optString("audio");
      List<int[]> ranges = new ArrayList<>();
      int originalRate = SR;
      JSONObject delivery = scene.json.optJSONObject("interpretacion");
      if (!audio.isEmpty()) {
        scene.pcm = decode(Store.resolve(context, audio));
        progress.log("Audio importado · escena " + (i + 1));
      } else {
        boolean isOpinion = scene.json.optString("tipo").equals("opinion");
        String engine = settings.optString(isOpinion ? "motor_opinion_android" : "motor_android");
        if (isOpinion && engine.isEmpty()) engine = settings.optString("motor_android");
        if (tts == null || !loadedEngine.equals(engine)) {
          close();
          init(engine);
        }
        Voice voice = choose(isOpinion);
        if (voice == null)
          throw new IOException("El motor seleccionado no ofrece una voz española local");
        tts.setVoice(voice);
        String rate = cfg.optString("velocidad", "+6%").replace("%", "").replace("+", "");
        try {
          tts.setSpeechRate(
              (float)
                  Math.max(
                      .6,
                      Math.min(
                          1.8,
                          (1 + Float.parseFloat(rate) / 100)
                              * Delivery.number(delivery, "velocidad", 1, .85, 1.15))));
        } catch (Exception ex) {
          tts.setSpeechRate(1.06f);
        }
        tts.setPitch((float) Delivery.number(delivery, "tono", 1, .9, 1.1));
        CountDownLatch done = new CountDownLatch(1);
        int[] error = {0};
        String id = "scene-" + i + "-" + System.nanoTime();
        tts.setOnUtteranceProgressListener(
            new UtteranceProgressListener() {
              public void onStart(String u) {}

              public void onDone(String u) {
                if (u.equals(id)) done.countDown();
              }

              public void onError(String u) {
                if (u.equals(id)) {
                  error[0] = -1;
                  done.countDown();
                }
              }

              public void onError(String u, int code) {
                if (u.equals(id)) {
                  error[0] = code;
                  done.countDown();
                }
              }

              public void onRangeStart(String u, int start, int end, int frame) {
                if (u.equals(id))
                  synchronized (ranges) {
                    ranges.add(new int[] {start, end, frame});
                  }
              }
            });
        if (spoken.length() > TextToSpeech.getMaxSpeechInputLength())
          throw new IOException("Escena demasiado larga para TTS: divide su texto");
        File wav = new File(work, "voz-" + i + ".wav");
        Bundle params = new Bundle();
        params.putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, id);
        if (tts.synthesizeToFile(spoken, params, wav, id) != TextToSpeech.SUCCESS)
          throw new IOException("La voz no pudo sintetizar la escena " + (i + 1));
        if (!done.await(120, TimeUnit.SECONDS))
          throw new IOException("La síntesis de voz tardó demasiado");
        Net.check();
        if (error[0] != 0)
          throw new IOException(
              "Error de voz local "
                  + error[0]
                  + ". Comprueba que los datos de español están descargados.");
        MediaMetadataRetriever meta = new MediaMetadataRetriever();
        try {
          meta.setDataSource(wav.getPath());
          String sr = meta.extractMetadata(MediaMetadataRetriever.METADATA_KEY_SAMPLERATE);
          if (sr != null) originalRate = Integer.parseInt(sr);
        } catch (Exception ignored) {
        } finally {
          meta.release();
        }
        scene.pcm = decode(wav);
        wav.delete();
        progress.log("Voz local · escena " + (i + 1) + "/" + json.length());
      }
      double gain = Delivery.number(delivery, "intensidad", 1, .9, 1.15);
      for (int sample = 0; sample < scene.pcm.length; sample++)
        scene.pcm[sample] = (float) Math.max(-.98, Math.min(.98, scene.pcm[sample] * gain));
      int before = (int) (SR * Delivery.number(delivery, "pausa_antes", 0, 0, 1.2));
      pieces.add(new float[before]);
      total += before;
      if (delivery != null)
        progress.log(
            "Interpretación · escena "
                + (i + 1)
                + " · "
                + delivery.optString("emocion", "neutral"));
      scene.a = total / (double) SR;
      scene.speechEnd = scene.a + scene.pcm.length / (double) SR;
      double pause =
          Math.max(
              Delivery.number(delivery, "pausa_despues", 0, 0, 1.2),
              Math.max(0, Math.min(10, scene.json.optDouble("pausa", .25))));
      int silence = (int) (pause * SR);
      scene.b = scene.speechEnd + pause;
      words(scene, spoken, ranges, originalRate);
      if (delivery != null && delivery.optJSONArray("recalcar") != null) {
        for (Word word : scene.words)
          if (word.highlight) {
            int first = Math.max(0, (int) ((word.a - scene.a) * SR)),
                last = Math.min(scene.pcm.length, (int) ((word.b - scene.a) * SR));
            for (int sample = first; sample < last; sample++)
              scene.pcm[sample] = (float) Math.max(-.98, Math.min(.98, scene.pcm[sample] * 1.08));
          }
      }
      if (scene.json.optJSONArray("palabras") == null
          && (ranges.isEmpty() || ranges.size() != scene.words.size())) track.approximate = true;
      pieces.add(scene.pcm);
      pieces.add(new float[silence]);
      total += scene.pcm.length + silence;
      if (total > SR * MAX_SECONDS)
        throw new IOException("El video supera 180 segundos. Divide el guion en varios videos.");
      track.scenes.add(scene);
    }
    JSONObject extras = cfg.optJSONObject("extras");
    boolean defPoll = cfg.optString("categoria_video", "reddit").equals("reddit");
    boolean poll = extras == null ? defPoll : extras.optBoolean("encuesta", defPoll);
    if (poll) {
      pieces.add(new float[SR * 3]);
      total += SR * 3;
    }
    track.pcm = new float[total];
    int pos = 0;
    for (float[] a : pieces) {
      System.arraycopy(a, 0, track.pcm, pos, a.length);
      pos += a.length;
    }
    track.duration = total / (double) SR;
    mix(track, cfg);
    if (track.approximate)
      progress.log(
          "Subtítulos: tiempos por palabra aproximados donde el motor no entrega marcas. Las"
              + " escenas usan la duración real del audio.");
    return track;
  }

  private void words(Scene scene, String spoken, List<int[]> ranges, int originalRate)
      throws Exception {
    String visible = scene.json.getString("texto");
    JSONObject delivery = scene.json.optJSONObject("interpretacion");
    JSONArray emphasis = delivery == null ? null : delivery.optJSONArray("recalcar");
    if (emphasis != null)
      for (int i = 0; i < emphasis.length(); i++) {
        String term = emphasis.optString(i);
        if (!term.isEmpty())
          visible =
              visible.replaceAll(
                  "(?iu)(?<![\\p{L}\\p{N}*])("
                      + java.util.regex.Pattern.quote(term)
                      + ")(?![\\p{L}\\p{N}*])",
                  "*$1*");
      }
    List<String> tokens = new ArrayList<>();
    List<Boolean> marks = new ArrayList<>();
    boolean highlight = false;
    for (String token : visible.split("\\s+")) {
      int stars = 0;
      for (int k = 0; k < token.length(); k++) if (token.charAt(k) == '*') stars++;
      tokens.add(token.replace("*", ""));
      marks.add(highlight || stars > 0);
      if (stars % 2 == 1) highlight = !highlight;
    }
    JSONArray explicit = scene.json.optJSONArray("palabras");
    if (explicit != null) {
      for (int i = 0; i < explicit.length(); i++) {
        JSONObject w = explicit.getJSONObject(i);
        double a = w.getDouble("inicio"), b = w.getDouble("fin");
        if (!Double.isFinite(a)
            || !Double.isFinite(b)
            || a < 0
            || b <= a
            || b > scene.speechEnd - scene.a + .1)
          throw new IOException("Marcas de palabras inválidas");
        scene.words.add(
            new Word(
                w.getString("texto"), scene.a + a, scene.a + b, w.optBoolean("resalte", false)));
      }
      return;
    }
    List<double[]> boundaries = new ArrayList<>();
    synchronized (ranges) {
      ranges.sort(Comparator.comparingInt(x -> x[2]));
      for (int[] r : ranges)
        if (r[2] >= 0) boundaries.add(new double[] {r[2] / (double) originalRate});
    }
    boolean exact = boundaries.size() == tokens.size();
    double weight = 0;
    for (String t : tokens) weight += Math.max(1, t.length());
    double pos = 0, length = scene.speechEnd - scene.a;
    for (int i = 0; i < tokens.size(); i++) {
      double start = exact ? Math.min(length, boundaries.get(i)[0]) : pos / weight * length;
      pos += Math.max(1, tokens.get(i).length());
      double end =
          exact
              ? (i + 1 < boundaries.size() ? Math.min(length, boundaries.get(i + 1)[0]) : length)
              : pos / weight * length;
      scene.words.add(
          new Word(
              tokens.get(i), scene.a + start, scene.a + Math.max(start + .01, end), marks.get(i)));
    }
  }

  private void mix(Track track, JSONObject cfg) throws Exception {
    float[] music = null;
    String path = cfg.optString("musica");
    if (!path.isEmpty()) music = decode(Store.resolve(context, path));
    else {
      List<File> files = Store.list(context, "musica", "");
      if (!files.isEmpty())
        try {
          music =
              decode(
                  files.get(new Random(cfg.optString("titulo").hashCode()).nextInt(files.size())));
        } catch (Exception e) {
          progress.log("Música importada no compatible; se genera música local.");
        }
    }
    double vol = Math.max(0, Math.min(2, cfg.optDouble("volumen_musica", 1)));
    String style = cfg.optString("plantilla", "clasica");
    double base = style.equals("tetrica") ? 110 : style.equals("pop") ? 261.63 : 164.81;
    double envelope = 0, duck = .14;
    for (int i = 0; i < track.pcm.length; i++) {
      if (i % 24000 == 0) Net.check();
      double t = i / (double) SR;
      double m;
      if (music != null && music.length > 0) m = music[i % music.length];
      else {
        int chord = ((int) t / 8) % 4;
        double root = base * new double[] {1, .7937, .8909, .7492}[chord];
        m =
            .4 * Math.sin(2 * Math.PI * root * t)
                + .23 * Math.sin(2 * Math.PI * root * 1.5 * t)
                + .17 * Math.sin(2 * Math.PI * root * 2 * t);
        m *= .5 + .5 * Math.sin(2 * Math.PI * .125 * t);
        if (style.equals("impacto"))
          m += .12 * Math.sin(2 * Math.PI * 60 * t) * Math.exp(-18 * (t % .5));
      }
      double fade = Math.min(1, Math.min(t / 1.5, (track.duration - t) / 1.5));
      envelope = .995 * envelope + .005 * Math.abs(track.pcm[i]);
      duck += .002 * ((envelope > .012 ? .08 : .14) - duck);
      track.pcm[i] += (float) (m * duck * vol * fade);
    }
    JSONObject extras = cfg.optJSONObject("extras");
    if (extras == null || extras.optBoolean("sonidos", true))
      for (Scene scene : track.scenes) {
        int at = (int) (scene.a * SR);
        for (int k = 0; k < SR * .1 && at + k < track.pcm.length; k++)
          track.pcm[at + k] +=
              (float)
                  (.035
                      * Math.sin(2 * Math.PI * (650 + 600 * k / (double) SR) * k / SR)
                      * Math.exp(-45 * k / (double) SR));
      }
    float peak = 0;
    for (float x : track.pcm) peak = Math.max(peak, Math.abs(x));
    if (peak > 0) {
      float gain = Math.min(2.5f, .88f / peak);
      for (int i = 0; i < track.pcm.length; i++) track.pcm[i] *= gain;
    }
  }

  static float[] decode(File file) throws Exception {
    MediaExtractor ex = new MediaExtractor();
    MediaCodec codec = null;
    ByteArrayOutputStream pcm = new ByteArrayOutputStream();
    int rate = SR, channels = 1, encoding = AudioFormat.ENCODING_PCM_16BIT;
    try {
      ex.setDataSource(file.getPath());
      int track = -1;
      MediaFormat f = null;
      for (int i = 0; i < ex.getTrackCount(); i++) {
        MediaFormat t = ex.getTrackFormat(i);
        if (t.getString(MediaFormat.KEY_MIME).startsWith("audio/")) {
          track = i;
          f = t;
          break;
        }
      }
      if (track < 0) throw new IOException("El archivo no contiene audio");
      ex.selectTrack(track);
      rate = f.getInteger(MediaFormat.KEY_SAMPLE_RATE);
      channels = f.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
      String mime = f.getString(MediaFormat.KEY_MIME);
      if (mime.equals("audio/raw")) {
        if (f.containsKey(MediaFormat.KEY_PCM_ENCODING))
          encoding = f.getInteger(MediaFormat.KEY_PCM_ENCODING);
        ByteBuffer data = ByteBuffer.allocate(1024 * 1024);
        int n;
        while ((n = ex.readSampleData(data, 0)) >= 0) {
          Net.check();
          byte[] b = new byte[n];
          data.position(0);
          data.get(b);
          pcm.write(b);
          data.clear();
          if (pcm.size() > 100 * 1024 * 1024) throw new IOException("Audio demasiado largo");
          ex.advance();
        }
      } else {
        codec = MediaCodec.createDecoderByType(mime);
        codec.configure(f, null, null, 0);
        codec.start();
        boolean inputEnd = false, outputEnd = false;
        MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
        long last = System.nanoTime();
        while (!outputEnd) {
          Net.check();
          if (System.nanoTime() - last > 30_000_000_000L)
            throw new IOException("El decodificador de audio dejó de responder");
          if (!inputEnd) {
            int idx = codec.dequeueInputBuffer(10000);
            if (idx >= 0) {
              ByteBuffer in = codec.getInputBuffer(idx);
              int n = ex.readSampleData(in, 0);
              if (n < 0) {
                codec.queueInputBuffer(idx, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                inputEnd = true;
              } else {
                codec.queueInputBuffer(idx, 0, n, Math.max(0, ex.getSampleTime()), 0);
                ex.advance();
              }
            }
          }
          int idx = codec.dequeueOutputBuffer(info, 10000);
          if (idx == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
            MediaFormat out = codec.getOutputFormat();
            rate = out.getInteger(MediaFormat.KEY_SAMPLE_RATE);
            channels = out.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
            if (out.containsKey(MediaFormat.KEY_PCM_ENCODING))
              encoding = out.getInteger(MediaFormat.KEY_PCM_ENCODING);
          } else if (idx >= 0) {
            last = System.nanoTime();
            ByteBuffer out = codec.getOutputBuffer(idx);
            out.position(info.offset);
            out.limit(info.offset + info.size);
            byte[] b = new byte[info.size];
            out.get(b);
            pcm.write(b);
            codec.releaseOutputBuffer(idx, false);
            outputEnd = (info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0;
            if (pcm.size() > 100 * 1024 * 1024) throw new IOException("Audio demasiado largo");
          }
        }
      }
    } finally {
      ex.release();
      if (codec != null) {
        try {
          codec.stop();
        } catch (Exception ignored) {
        }
        codec.release();
      }
    }
    int bytes = encoding == AudioFormat.ENCODING_PCM_FLOAT ? 4 : 2;
    if (encoding != AudioFormat.ENCODING_PCM_FLOAT && encoding != AudioFormat.ENCODING_PCM_16BIT)
      throw new IOException("Usa audio PCM 16 bits o MP3/AAC");
    byte[] raw = pcm.toByteArray();
    ByteBuffer b = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);
    int frames = raw.length / bytes / channels;
    int n = (int) ((long) frames * SR / rate);
    if (n > SR * MAX_SECONDS) throw new IOException("Audio mayor que 180 segundos");
    if (n == 0) throw new IOException("Audio vacío");
    float[] mono = new float[frames];
    for (int i = 0; i < frames; i++) {
      float v = 0;
      for (int j = 0; j < channels; j++) v += bytes == 4 ? b.getFloat() : b.getShort() / 32768f;
      mono[i] = v / channels;
    }
    float[] resampled = new float[n];
    for (int i = 0; i < n; i++) {
      double p = i * (double) rate / SR;
      int a = Math.min(frames - 1, (int) p), z = Math.min(frames - 1, a + 1);
      resampled[i] = (float) (mono[a] + (mono[z] - mono[a]) * (p - a));
    }
    return resampled;
  }

  static void encode(float[] pcm, File file) throws Exception {
    MediaCodec codec = MediaCodec.createEncoderByType("audio/mp4a-latm");
    MediaMuxer mux = null;
    boolean started = false;
    try {
      MediaFormat fmt = MediaFormat.createAudioFormat("audio/mp4a-latm", SR, 1);
      fmt.setInteger(MediaFormat.KEY_AAC_PROFILE, MediaCodecInfo.CodecProfileLevel.AACObjectLC);
      fmt.setInteger(MediaFormat.KEY_BIT_RATE, 192000);
      fmt.setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 16384);
      codec.configure(fmt, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
      codec.start();
      mux = new MediaMuxer(file.getPath(), MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
      int pos = 0, track = -1;
      boolean endIn = false, endOut = false;
      MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
      long last = System.nanoTime();
      while (!endOut) {
        Net.check();
        if (System.nanoTime() - last > 30_000_000_000L)
          throw new IOException("El codificador de audio dejó de responder");
        if (!endIn) {
          int idx = codec.dequeueInputBuffer(10000);
          if (idx >= 0) {
            ByteBuffer b = codec.getInputBuffer(idx);
            b.clear();
            b.order(ByteOrder.LITTLE_ENDIAN);
            int n = Math.min(b.remaining() / 2, pcm.length - pos);
            for (int i = 0; i < n; i++)
              b.putShort((short) (Math.max(-1, Math.min(1, pcm[pos + i])) * 32767));
            codec.queueInputBuffer(
                idx,
                0,
                n * 2,
                pos * 1000000L / SR,
                pos + n == pcm.length ? MediaCodec.BUFFER_FLAG_END_OF_STREAM : 0);
            pos += n;
            endIn = pos == pcm.length;
          }
        }
        int idx = codec.dequeueOutputBuffer(info, 10000);
        if (idx == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
          track = mux.addTrack(codec.getOutputFormat());
          mux.start();
          started = true;
        } else if (idx >= 0) {
          last = System.nanoTime();
          ByteBuffer b = codec.getOutputBuffer(idx);
          if (info.size > 0 && (info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) == 0) {
            b.position(info.offset);
            b.limit(info.offset + info.size);
            mux.writeSampleData(track, b, info);
          }
          endOut = (info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0;
          codec.releaseOutputBuffer(idx, false);
        }
      }
    } finally {
      try {
        codec.stop();
      } catch (Exception ignored) {
      }
      codec.release();
      if (mux != null) {
        if (started)
          try {
            mux.stop();
          } catch (Exception ignored) {
          }
        mux.release();
      }
    }
  }

  public void close() {
    TextToSpeech old = tts;
    tts = null;
    if (old != null) {
      Thread release =
          new Thread(
              () -> {
                try {
                  old.stop();
                  old.shutdown();
                } catch (Exception ignored) {
                }
              },
              "tts-release");
      release.setDaemon(true);
      release.start();
    }
  }
}
