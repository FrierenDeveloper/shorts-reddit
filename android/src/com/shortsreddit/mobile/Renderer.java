package com.shortsreddit.mobile;

import android.content.Context;
import android.graphics.*;
import android.media.*;
import android.opengl.*;
import android.view.Surface;
import java.io.*;
import java.nio.*;
import java.util.*;
import org.json.*;

final class Renderer implements AutoCloseable {
  final Context context;
  final JSONObject cfg, extras;
  final Audio.Track audio;
  final List<MediaAssets.Asset> assets;
  final int width, height, fps = 30;
  final Bitmap frame;
  final Canvas canvas;
  final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
  final String template;
  final Typeface font;
  final int accent, active;
  final float subtitleY, fontSize;
  File current;
  Bitmap photo, videoFrame;
  MediaMetadataRetriever retriever;
  double videoDuration;
  long lastVideoFrame = -1;

  Renderer(Context c, JSONObject json, Audio.Track a, List<MediaAssets.Asset> files, int w, int h)
      throws Exception {
    context = c;
    cfg = json;
    audio = a;
    assets = files;
    width = w;
    height = h;
    extras = cfg.optJSONObject("extras");
    frame = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
    canvas = new Canvas(frame);
    String t = cfg.optString("plantilla", "aleatoria");
    String[] names = {"clasica", "impacto", "noche", "diario", "pop", "tetrica"};
    template =
        Arrays.asList(names).contains(t)
            ? t
            : names[Math.floorMod(cfg.optString("titulo").hashCode(), names.length)];
    String filename;
    switch (template) {
      case "impacto":
        filename = "Anton.ttf";
        accent = Color.rgb(255, 72, 48);
        active = Color.YELLOW;
        subtitleY = 900;
        fontSize = 100;
        break;
      case "noche":
        filename = "Montserrat-Black.ttf";
        accent = Color.CYAN;
        active = Color.MAGENTA;
        subtitleY = 1152;
        fontSize = 70;
        break;
      case "diario":
        filename = "Lora-Bold.ttf";
        accent = Color.rgb(255, 190, 90);
        active = Color.rgb(255, 130, 110);
        subtitleY = 998;
        fontSize = 74;
        break;
      case "pop":
        filename = "ArchivoBlack.ttf";
        accent = Color.rgb(230, 30, 110);
        active = Color.WHITE;
        subtitleY = 960;
        fontSize = 66;
        break;
      case "tetrica":
        filename = "Montserrat-Black.ttf";
        accent = Color.rgb(150, 60, 210);
        active = Color.rgb(80, 220, 190);
        subtitleY = 1382;
        fontSize = 68;
        break;
      default:
        filename = "Poppins-Bold.ttf";
        accent = Color.rgb(255, 206, 84);
        active = Color.rgb(92, 255, 140);
        subtitleY = 960;
        fontSize = 76;
    }
    font = Typeface.createFromAsset(c.getAssets(), "fonts/" + filename);
    paint.setTypeface(font);
  }

  boolean on(String name) {
    boolean educational = !cfg.optString("categoria_video", "reddit").equals("reddit");
    boolean def =
        !(educational
            && (name.equals("tarjeta") || name.equals("loop") || name.equals("encuesta")));
    return extras == null ? def : extras.optBoolean(name, def);
  }

  private void source(MediaAssets.Asset a) throws Exception {
    File file = a == null ? null : a.file;
    if (Objects.equals(file, current)) return;
    if (retriever != null) {
      retriever.release();
      retriever = null;
    }
    if (photo != null) {
      photo.recycle();
      photo = null;
    }
    if (videoFrame != null) {
      videoFrame.recycle();
      videoFrame = null;
    }
    current = file;
    lastVideoFrame = -1;
    if (file == null) return;
    if (a.video) {
      retriever = new MediaMetadataRetriever();
      retriever.setDataSource(file.getPath());
      String dur = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION);
      videoDuration = dur == null ? 1 : Math.max(.01, Long.parseLong(dur) / 1000.0);
    } else {
      BitmapFactory.Options info = new BitmapFactory.Options();
      info.inJustDecodeBounds = true;
      BitmapFactory.decodeFile(file.getPath(), info);
      if (info.outWidth <= 0) throw new IOException("Imagen no compatible: " + file.getName());
      int sample = 1;
      while (info.outWidth / sample > 2160 || info.outHeight / sample > 3840) sample *= 2;
      BitmapFactory.Options opt = new BitmapFactory.Options();
      opt.inSampleSize = sample;
      photo = BitmapFactory.decodeFile(file.getPath(), opt);
      if (photo == null) throw new IOException("No se pudo abrir " + file.getName());
    }
  }

  Bitmap draw(double t) throws Exception {
    Audio.Scene scene = audio.scenes.get(audio.scenes.size() - 1);
    int si = audio.scenes.size() - 1;
    for (int i = 0; i < audio.scenes.size(); i++)
      if (t < audio.scenes.get(i).b) {
        si = i;
        scene = audio.scenes.get(i);
        break;
      }
    source(assets.get(si));
    canvas.save();
    canvas.scale(width / 1080f, height / 1920f);
    canvas.drawColor(Color.rgb(16, 24, 28));
    Bitmap image = photo;
    if (retriever != null) {
      long n = (long) (t * 15);
      if (n != lastVideoFrame) {
        if (videoFrame != null) videoFrame.recycle();
        videoFrame =
            retriever.getScaledFrameAtTime(
                (long) ((t % videoDuration) * 1000000),
                MediaMetadataRetriever.OPTION_CLOSEST,
                Math.min(width, 1080),
                Math.min(height, 1920));
        lastVideoFrame = n;
      }
      image = videoFrame;
    }
    if (image != null) {
      float zoom = 1.03f + (float) (.05 * Math.sin(t * .08));
      if (on("zoom")) zoom += (float) (.04 * Math.exp(-5 * Math.max(0, t - scene.a)));
      float scale = Math.max(1080f / image.getWidth(), 1920f / image.getHeight()) * zoom;
      float iw = image.getWidth() * scale, ih = image.getHeight() * scale;
      paint.setShader(null);
      paint.setColor(Color.WHITE);
      canvas.drawBitmap(
          image,
          null,
          new RectF((1080 - iw) / 2, (1920 - ih) / 2, (1080 + iw) / 2, (1920 + ih) / 2),
          paint);
      paint.setColor(Color.argb(template.equals("tetrica") ? 100 : 65, 0, 0, 0));
      canvas.drawRect(0, 0, 1080, 1920, paint);
    } else {
      int bottom = template.equals("diario") ? Color.rgb(70, 45, 30) : Color.rgb(40, 35, 65);
      paint.setShader(
          new LinearGradient(
              0,
              0,
              1080,
              1920,
              new int[] {Color.rgb(20, 45, 55), bottom},
              null,
              Shader.TileMode.CLAMP));
      canvas.drawRect(0, 0, 1080, 1920, paint);
      paint.setShader(null);
      paint.setColor(Color.argb(35, Color.red(accent), Color.green(accent), Color.blue(accent)));
      for (int j = 0; j < 4; j++)
        canvas.drawCircle(
            (float) (540 + 400 * Math.sin(t * .13 + j * 2)),
            (float) (900 + 550 * Math.cos(t * .09 + j)),
            260 + j * 30,
            paint);
    }
    if (on("barra")) {
      paint.setColor(Color.argb(90, 255, 255, 255));
      canvas.drawRect(0, 0, 1080, 12, paint);
      paint.setColor(accent);
      canvas.drawRect(0, 0, (float) (1080 * t / audio.duration), 12, paint);
    }
    if (on("tarjeta") && t < 2.6) {
      panel(64, 140, 1016, 470);
      text(cfg.optString("subreddit", "r/historias"), 100, 210, 38, accent);
      paragraph(cfg.optString("titulo"), 100, 290, 880, 50, Color.WHITE, 3);
    }
    String aviso = cfg.optString("aviso");
    if (!aviso.isEmpty()) paragraph(aviso, 70, 1770, 940, 30, Color.LTGRAY, 2);
    boolean outro = t >= audio.scenes.get(audio.scenes.size() - 1).b;
    if (outro && on("encuesta")) {
      JSONArray choices = cfg.optJSONArray("encuesta");
      paragraph("¿Tú qué opinas?", 80, 780, 920, 70, Color.WHITE, 2);
      button(
          choices == null ? "TIENE RAZÓN" : choices.optString(0, "TIENE RAZÓN"),
          850,
          Color.rgb(39, 174, 96));
      button(
          choices == null ? "SE PASÓ" : choices.optString(1, "SE PASÓ"),
          1020,
          Color.rgb(214, 48, 49));
    } else if (t < scene.speechEnd) {
      if (scene.json.optString("tipo").equals("opinion")) {
        panel(330, subtitleY - 180, 750, subtitleY - 100);
        text("MI OPINIÓN", 370, subtitleY - 125, 38, accent);
      }
      subtitles(scene, t);
    }
    if (on("loop") && outro) {
      paragraph("Vuelve al inicio…", 150, 1600, 780, 40, accent, 1);
    }
    JSONObject cover = cfg.optJSONObject("portada");
    if ((cfg.optBoolean("portada_titulo") || cover != null) && t < 1.2) {
      panel(60, 550, 1020, 1160);
      String title =
          cover == null
              ? cfg.optString("titulo")
              : cover.optString("texto", cover.optString("pregunta", cfg.optString("titulo")));
      paragraph(title, 100, 680, 880, 78, Color.WHITE, 4);
      if (cover == null || !cover.optString("dibujo").equals("ninguno")) doodle(540, 1080);
    }
    canvas.restore();
    return frame;
  }

  void doodle(float x, float y) {
    paint.setColor(accent);
    paint.setStrokeWidth(7);
    paint.setStyle(Paint.Style.STROKE);
    canvas.drawCircle(x, y, 55, paint);
    canvas.drawCircle(x - 26, y - 10, 15, paint);
    canvas.drawCircle(x + 26, y - 10, 15, paint);
    canvas.drawArc(x - 26, y, x + 26, y + 32, 0, 180, false, paint);
    paint.setStyle(Paint.Style.FILL);
  }

  void panel(float l, float top, float r, float bottom) {
    paint.setColor(Color.argb(200, 18, 26, 28));
    canvas.drawRoundRect(l, top, r, bottom, 28, 28, paint);
  }

  void button(String title, float y, int color) {
    paint.setColor(color);
    canvas.drawRoundRect(100, y, 980, y + 130, 24, 24, paint);
    paint.setTextSize(48);
    float w = paint.measureText(title);
    text(title, 540 - w / 2, y + 82, 48, Color.WHITE);
  }

  void text(String s, float x, float y, float size, int color) {
    paint.setTextSize(size);
    paint.setColor(color);
    paint.setStyle(Paint.Style.FILL);
    canvas.drawText(s, x, y, paint);
  }

  void paragraph(String value, float x, float y, float max, float size, int color, int lines) {
    paint.setTextSize(size);
    String line = "";
    int row = 0;
    for (String w : value.replace("*", "").split("\\s+")) {
      if (paint.measureText(line + w) > max && !line.isEmpty()) {
        text(line.trim(), x, y + row * size * 1.35f, size, color);
        if (++row >= lines) return;
        line = "";
      }
      line += w + " ";
    }
    if (row < lines) text(line.trim(), x, y + row * size * 1.35f, size, color);
  }

  void subtitles(Audio.Scene scene, double t) {
    List<Audio.Word> words = scene.words;
    if (words.isEmpty()) return;
    int current = 0;
    for (int i = 0; i < words.size(); i++) if (t >= words.get(i).a) current = i;
    int count = template.equals("impacto") ? 3 : template.equals("pop") ? 5 : 6;
    int start = (current / count) * count, end = Math.min(words.size(), start + count);
    float size = fontSize;
    paint.setTextSize(size);
    List<List<Integer>> lines = new ArrayList<>();
    List<Integer> row = new ArrayList<>();
    float sum = 0;
    for (int i = start; i < end; i++) {
      String word = words.get(i).text;
      if (template.equals("impacto")) word = word.toUpperCase(Locale.ROOT);
      float w = paint.measureText(word) + paint.measureText(" ");
      if (sum + w > 900 && !row.isEmpty()) {
        lines.add(row);
        row = new ArrayList<>();
        sum = 0;
      }
      row.add(i);
      sum += w;
    }
    if (!row.isEmpty()) lines.add(row);
    double entry = Math.min(1, Math.max(0, (t - words.get(start).a) / .2));
    canvas.save();
    canvas.translate(540, subtitleY);
    float scale = (float) (.9 + .1 * entry);
    canvas.scale(scale, scale);
    canvas.translate(-540, -subtitleY);
    for (int r = 0; r < lines.size(); r++) {
      row = lines.get(r);
      float total = 0;
      for (int i : row)
        total +=
            paint.measureText(
                    template.equals("impacto")
                        ? words.get(i).text.toUpperCase(Locale.ROOT)
                        : words.get(i).text)
                + paint.measureText(" ");
      float x = (1080 - total) / 2;
      float y = subtitleY + (r - (lines.size() - 1) / 2f) * size * 1.35f;
      for (int i : row) {
        Audio.Word w = words.get(i);
        String str = template.equals("impacto") ? w.text.toUpperCase(Locale.ROOT) : w.text;
        float len = paint.measureText(str);
        boolean isActive = on("karaoke") && i == current;
        if (template.equals("pop")) {
          paint.setColor(isActive ? accent : Color.WHITE);
          canvas.drawRoundRect(x - 8, y - size, x + len + 8, y + 14, 10, 10, paint);
        } else {
          paint.setStyle(Paint.Style.STROKE);
          paint.setStrokeWidth(9);
          paint.setColor(Color.rgb(12, 10, 18));
          canvas.drawText(str, x, y, paint);
          paint.setStyle(Paint.Style.FILL);
        }
        paint.setColor(
            isActive
                ? active
                : w.highlight
                    ? accent
                    : template.equals("pop") ? Color.rgb(20, 20, 20) : Color.WHITE);
        canvas.drawText(str, x, y, paint);
        x += len + paint.measureText(" ");
      }
    }
    canvas.restore();
  }

  void encode(File output, Audio.Progress progress) throws Exception {
    MediaFormat fmt = MediaFormat.createVideoFormat("video/avc", width, height);
    fmt.setInteger(
        MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface);
    fmt.setInteger(MediaFormat.KEY_BIT_RATE, width >= 1080 ? 10000000 : 6000000);
    fmt.setInteger(MediaFormat.KEY_FRAME_RATE, fps);
    fmt.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 2);
    fmt.setInteger(MediaFormat.KEY_COLOR_STANDARD, MediaFormat.COLOR_STANDARD_BT709);
    fmt.setInteger(MediaFormat.KEY_COLOR_RANGE, MediaFormat.COLOR_RANGE_LIMITED);
    fmt.setInteger(MediaFormat.KEY_COLOR_TRANSFER, MediaFormat.COLOR_TRANSFER_SDR_VIDEO);
    String codecName = null;
    for (MediaCodecInfo info : new MediaCodecList(MediaCodecList.REGULAR_CODECS).getCodecInfos()) {
      if (info.isEncoder() && info.isHardwareAccelerated())
        for (String type : info.getSupportedTypes())
          if (type.equals("video/avc")
              && info.getCapabilitiesForType(type).isFormatSupported(fmt)) {
            codecName = info.getName();
            break;
          }
      if (codecName != null) break;
    }
    MediaCodec codec =
        codecName == null
            ? MediaCodec.createEncoderByType("video/avc")
            : MediaCodec.createByCodecName(codecName);
    MediaMuxer mux = null;
    GL gl = null;
    Surface surface = null;
    boolean[] started = {false};
    int[] track = {-1};
    try {
      codec.configure(fmt, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
      surface = codec.createInputSurface();
      gl = new GL(surface, width, height);
      codec.start();
      mux = new MediaMuxer(output.getPath(), MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
      int total = (int) Math.ceil(audio.duration * fps);
      progress.log("Render local · " + width + " × " + height + " · " + codec.getName());
      for (int n = 0; n < total; n++) {
        Net.check();
        drain(codec, mux, started, track, false);
        gl.draw(draw(n / (double) fps), n * 1000000000L / fps);
        drain(codec, mux, started, track, false);
        if (n % 30 == 0) progress.log("Render " + (n * 100 / total) + " %");
      }
      codec.signalEndOfInputStream();
      drain(codec, mux, started, track, true);
    } finally {
      try {
        codec.stop();
      } catch (Exception ignored) {
      }
      codec.release();
      if (gl != null) gl.close();
      if (surface != null) surface.release();
      if (mux != null) {
        if (started[0])
          try {
            mux.stop();
          } catch (Exception ignored) {
          }
        mux.release();
      }
    }
  }

  static void drain(MediaCodec codec, MediaMuxer mux, boolean[] started, int[] track, boolean eos)
      throws Exception {
    MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
    long deadline = System.nanoTime() + 30_000_000_000L;
    while (true) {
      Net.check();
      int idx = codec.dequeueOutputBuffer(info, eos ? 10000 : 0);
      if (idx == MediaCodec.INFO_TRY_AGAIN_LATER) {
        if (!eos) return;
        if (System.nanoTime() > deadline)
          throw new IOException("El codificador de video dejó de responder");
      } else if (idx == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
        track[0] = mux.addTrack(codec.getOutputFormat());
        mux.start();
        started[0] = true;
      } else if (idx >= 0) {
        ByteBuffer b = codec.getOutputBuffer(idx);
        if (info.size > 0 && (info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) == 0) {
          if (!started[0]) throw new IOException("Video sin formato de salida");
          b.position(info.offset);
          b.limit(info.offset + info.size);
          mux.writeSampleData(track[0], b, info);
        }
        boolean end = (info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0;
        codec.releaseOutputBuffer(idx, false);
        if (end) return;
      }
    }
  }

  static void mux(File video, File audio, File output) throws Exception {
    MediaExtractor v = new MediaExtractor(), a = new MediaExtractor();
    MediaMuxer m = null;
    boolean started = false;
    try {
      v.setDataSource(video.getPath());
      a.setDataSource(audio.getPath());
      v.selectTrack(0);
      a.selectTrack(0);
      m = new MediaMuxer(output.getPath(), MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
      int vt = m.addTrack(v.getTrackFormat(0)), at = m.addTrack(a.getTrackFormat(0));
      m.start();
      started = true;
      ByteBuffer b = ByteBuffer.allocateDirect(4 * 1024 * 1024);
      MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
      while (v.getSampleTime() >= 0 || a.getSampleTime() >= 0) {
        Net.check();
        boolean videoNext =
            a.getSampleTime() < 0
                || (v.getSampleTime() >= 0 && v.getSampleTime() <= a.getSampleTime());
        MediaExtractor e = videoNext ? v : a;
        b.clear();
        int n = e.readSampleData(b, 0);
        if (n < 0) break;
        info.set(
            0,
            n,
            e.getSampleTime(),
            (e.getSampleFlags() & MediaExtractor.SAMPLE_FLAG_SYNC) != 0
                ? MediaCodec.BUFFER_FLAG_KEY_FRAME
                : 0);
        m.writeSampleData(videoNext ? vt : at, b, info);
        e.advance();
      }
    } finally {
      v.release();
      a.release();
      if (m != null) {
        if (started)
          try {
            m.stop();
          } catch (Exception ignored) {
          }
        m.release();
      }
    }
  }

  public void close() {
    if (retriever != null)
      try {
        retriever.release();
      } catch (Exception ignored) {
      }
    if (photo != null) photo.recycle();
    if (videoFrame != null) videoFrame.recycle();
    frame.recycle();
  }

  static final class GL implements AutoCloseable {
    android.opengl.EGLDisplay display;
    android.opengl.EGLContext context;
    android.opengl.EGLSurface surface;
    int program, texture;
    FloatBuffer points;
    final int w, h;

    GL(Surface input, int width, int height) throws Exception {
      w = width;
      h = height;
      display = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);
      int[] ver = new int[2];
      if (!EGL14.eglInitialize(display, ver, 0, ver, 1))
        throw new IOException("No se pudo iniciar EGL");
      int[] attrs = {
        EGL14.EGL_RED_SIZE,
        8,
        EGL14.EGL_GREEN_SIZE,
        8,
        EGL14.EGL_BLUE_SIZE,
        8,
        EGL14.EGL_RENDERABLE_TYPE,
        EGL14.EGL_OPENGL_ES2_BIT,
        0x3142,
        1,
        EGL14.EGL_NONE
      };
      android.opengl.EGLConfig[] configs = new android.opengl.EGLConfig[1];
      int[] n = new int[1];
      if (!EGL14.eglChooseConfig(display, attrs, 0, configs, 0, 1, n, 0) || n[0] == 0)
        throw new IOException("No hay una superficie de grabación EGL");
      context =
          EGL14.eglCreateContext(
              display,
              configs[0],
              EGL14.EGL_NO_CONTEXT,
              new int[] {EGL14.EGL_CONTEXT_CLIENT_VERSION, 2, EGL14.EGL_NONE},
              0);
      surface =
          EGL14.eglCreateWindowSurface(display, configs[0], input, new int[] {EGL14.EGL_NONE}, 0);
      if (!EGL14.eglMakeCurrent(display, surface, surface, context))
        throw new IOException("No se pudo activar EGL");
      int vs =
          shader(
              GLES20.GL_VERTEX_SHADER,
              "attribute vec2 p;attribute vec2 uv;varying vec2 v;void"
                  + " main(){gl_Position=vec4(p,0.0,1.0);v=uv;}");
      int fs =
          shader(
              GLES20.GL_FRAGMENT_SHADER,
              "precision mediump float;varying vec2 v;uniform sampler2D image;void"
                  + " main(){gl_FragColor=texture2D(image,v);}");
      program = GLES20.glCreateProgram();
      GLES20.glAttachShader(program, vs);
      GLES20.glAttachShader(program, fs);
      GLES20.glLinkProgram(program);
      int[] ok = new int[1];
      GLES20.glGetProgramiv(program, GLES20.GL_LINK_STATUS, ok, 0);
      if (ok[0] == 0) throw new IOException("Falló el compositor GPU");
      GLES20.glDeleteShader(vs);
      GLES20.glDeleteShader(fs);
      int[] tex = new int[1];
      GLES20.glGenTextures(1, tex, 0);
      texture = tex[0];
      GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, texture);
      GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MIN_FILTER, GLES20.GL_LINEAR);
      GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MAG_FILTER, GLES20.GL_LINEAR);
      GLES20.glTexParameteri(
          GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_S, GLES20.GL_CLAMP_TO_EDGE);
      GLES20.glTexParameteri(
          GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_T, GLES20.GL_CLAMP_TO_EDGE);
      points = ByteBuffer.allocateDirect(16 * 4).order(ByteOrder.nativeOrder()).asFloatBuffer();
      points.put(new float[] {-1, -1, 0, 1, 1, -1, 1, 1, -1, 1, 0, 0, 1, 1, 1, 0}).position(0);
    }

    int shader(int type, String code) throws IOException {
      int s = GLES20.glCreateShader(type);
      GLES20.glShaderSource(s, code);
      GLES20.glCompileShader(s);
      int[] ok = new int[1];
      GLES20.glGetShaderiv(s, GLES20.GL_COMPILE_STATUS, ok, 0);
      if (ok[0] == 0) throw new IOException("Falló un shader del render");
      return s;
    }

    boolean allocated;

    void draw(Bitmap bitmap, long time) throws IOException {
      GLES20.glViewport(0, 0, w, h);
      GLES20.glUseProgram(program);
      GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
      GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, texture);
      if (!allocated) {
        GLUtils.texImage2D(GLES20.GL_TEXTURE_2D, 0, bitmap, 0);
        allocated = true;
      } else GLUtils.texSubImage2D(GLES20.GL_TEXTURE_2D, 0, 0, 0, bitmap);
      int pos = GLES20.glGetAttribLocation(program, "p"),
          uv = GLES20.glGetAttribLocation(program, "uv");
      points.position(0);
      GLES20.glVertexAttribPointer(pos, 2, GLES20.GL_FLOAT, false, 16, points);
      GLES20.glEnableVertexAttribArray(pos);
      points.position(2);
      GLES20.glVertexAttribPointer(uv, 2, GLES20.GL_FLOAT, false, 16, points);
      GLES20.glEnableVertexAttribArray(uv);
      GLES20.glUniform1i(GLES20.glGetUniformLocation(program, "image"), 0);
      GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4);
      if (GLES20.glGetError() != GLES20.GL_NO_ERROR)
        throw new IOException("Error al componer el fotograma");
      EGLExt.eglPresentationTimeANDROID(display, surface, time);
      if (!EGL14.eglSwapBuffers(display, surface))
        throw new IOException("Error al enviar el fotograma al codificador");
    }

    public void close() {
      if (display == null) return;
      GLES20.glDeleteTextures(1, new int[] {texture}, 0);
      GLES20.glDeleteProgram(program);
      EGL14.eglMakeCurrent(
          display, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_CONTEXT);
      EGL14.eglDestroySurface(display, surface);
      EGL14.eglDestroyContext(display, context);
      EGL14.eglReleaseThread();
      EGL14.eglTerminate(display);
    }
  }
}
