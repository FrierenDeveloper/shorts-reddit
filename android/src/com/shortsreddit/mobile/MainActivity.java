package com.shortsreddit.mobile;

import android.app.*;
import android.content.*;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.*;
import android.provider.OpenableColumns;
import android.speech.tts.*;
import android.text.InputType;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

public final class MainActivity extends Activity {
  final int BG = Color.rgb(17, 29, 27),
      INK = Color.rgb(235, 239, 229),
      SAGE = Color.rgb(169, 213, 190),
      MUTED = Color.rgb(172, 188, 179);
  LinearLayout page;
  TextView status, log;
  ProgressBar progress;
  Spinner category, template, source;
  EditText input, volume;
  CheckBox satisfactory;
  Map<String, CheckBox> extras = new LinkedHashMap<>();
  final Handler handler = new Handler(Looper.getMainLooper());
  final ExecutorService io = Executors.newSingleThreadExecutor();
  String importing = "";
  File exporting;
  boolean exportProject;
  VoicePicker voicePicker;
  int tab = 0;
  JSONObject draft = new JSONObject();
  final Runnable poll =
      new Runnable() {
        public void run() {
          refreshStatus();
          handler.postDelayed(this, 1500);
        }
      };

  public void onCreate(Bundle state) {
    super.onCreate(state);
    getWindow().setStatusBarColor(BG);
    getWindow().setNavigationBarColor(BG);
    try {
      Store.init(this);
      File d = new File(getFilesDir(), "draft.json");
      if (d.exists()) draft = new JSONObject(Store.read(d));
    } catch (Exception e) {
      toast(e.getMessage());
    }
    if (Build.VERSION.SDK_INT >= 33
        && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
            != android.content.pm.PackageManager.PERMISSION_GRANTED)
      requestPermissions(new String[] {android.Manifest.permission.POST_NOTIFICATIONS}, 100);
    show(0);
  }

  public void onResume() {
    super.onResume();
    handler.post(poll);
  }

  public void onPause() {
    handler.removeCallbacks(poll);
    saveDraft();
    super.onPause();
  }

  public void onDestroy() {
    handler.removeCallbacks(poll);
    if (voicePicker != null) voicePicker.close();
    io.shutdown();
    super.onDestroy();
  }

  int dp(float n) {
    return (int) (n * getResources().getDisplayMetrics().density + .5f);
  }

  TextView label(String s, int size, int color) {
    TextView v = new TextView(this);
    v.setText(s);
    v.setTextColor(color);
    v.setTextSize(size);
    v.setPadding(0, dp(7), 0, dp(7));
    return v;
  }

  void title(String s) {
    page.addView(label(s, 23, INK));
  }

  void hint(String s) {
    page.addView(label(s, 14, MUTED));
  }

  Button button(String s, Runnable fn) {
    Button b = new Button(this);
    b.setText(s);
    b.setTextColor(BG);
    b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(SAGE));
    b.setAllCaps(false);
    LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, dp(50));
    p.setMargins(0, dp(6), 0, dp(6));
    page.addView(b, p);
    b.setOnClickListener(v -> fn.run());
    return b;
  }

  EditText field(String label, String initial, boolean secret, int lines) {
    page.addView(this.label(label, 14, MUTED));
    EditText v = new EditText(this);
    v.setTextColor(INK);
    v.setHintTextColor(MUTED);
    v.setText(initial);
    v.setTextSize(15);
    v.setMinLines(lines);
    v.setGravity(Gravity.TOP);
    v.setPadding(dp(12), dp(10), dp(12), dp(10));
    v.setBackgroundTintList(android.content.res.ColorStateList.valueOf(SAGE));
    v.setInputType(
        secret
            ? InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD
            : InputType.TYPE_CLASS_TEXT
                | (lines > 1
                    ? InputType.TYPE_TEXT_FLAG_MULTI_LINE
                    : InputType.TYPE_TEXT_FLAG_CAP_SENTENCES));
    page.addView(v, new LinearLayout.LayoutParams(-1, -2));
    return v;
  }

  Spinner spinner(String label, String[] entries, int position) {
    page.addView(this.label(label, 14, MUTED));
    Spinner s = new Spinner(this);
    ArrayAdapter<String> adapter =
        new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, entries);
    s.setAdapter(adapter);
    s.setSelection(Math.max(0, Math.min(entries.length - 1, position)));
    page.addView(s, new LinearLayout.LayoutParams(-1, dp(48)));
    return s;
  }

  CheckBox check(String text, boolean initial) {
    CheckBox c = new CheckBox(this);
    c.setText(text);
    c.setTextColor(INK);
    c.setChecked(initial);
    c.setButtonTintList(android.content.res.ColorStateList.valueOf(SAGE));
    page.addView(c);
    return c;
  }

  void show(int index) {
    saveDraft();
    if (voicePicker != null) {
      voicePicker.close();
      voicePicker = null;
    }
    tab = index;
    ScrollView scroll = new ScrollView(this);
    scroll.setFillViewport(true);
    scroll.setBackgroundColor(BG);
    scroll.setOnApplyWindowInsetsListener(
        (view, insets) -> {
          view.setPadding(
              insets.getSystemWindowInsetLeft(),
              insets.getSystemWindowInsetTop(),
              insets.getSystemWindowInsetRight(),
              insets.getSystemWindowInsetBottom());
          return insets.consumeSystemWindowInsets();
        });
    page = new LinearLayout(this);
    page.setOrientation(LinearLayout.VERTICAL);
    page.setPadding(dp(20), dp(22), dp(20), dp(32));
    scroll.addView(page);
    setContentView(scroll);
    title("Shorts Reddit");
    hint("Crea tus videos en el teléfono");
    LinearLayout nav = new LinearLayout(this);
    String[] names = {"Crear", "Guiones", "Videos", "Ajustes"};
    for (int i = 0; i < names.length; i++) {
      final int n = i;
      Button b = new Button(this);
      b.setText(names[i]);
      b.setTextSize(12);
      b.setAllCaps(false);
      b.setTextColor(index == i ? BG : INK);
      b.setBackgroundTintList(
          android.content.res.ColorStateList.valueOf(index == i ? SAGE : Color.rgb(40, 58, 52)));
      nav.addView(b, new LinearLayout.LayoutParams(0, dp(48), 1));
      b.setOnClickListener(v -> show(n));
    }
    page.addView(nav);
    input = null;
    category = null;
    template = null;
    source = null;
    satisfactory = null;
    volume = null;
    extras.clear();
    if (index == 0) newPage();
    else if (index == 1) scriptsPage();
    else if (index == 2) videosPage();
    else settingsPage();
    title("Trabajo actual");
    status = label("Sin trabajos activos", 15, SAGE);
    page.addView(status);
    progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
    page.addView(progress, new LinearLayout.LayoutParams(-1, dp(8)));
    log = label("", 13, MUTED);
    log.setTextIsSelectable(true);
    page.addView(log);
    button(
        "Cancelar trabajo",
        () -> {
          if (RenderService.running)
            startService(new Intent(this, RenderService.class).setAction(RenderService.CANCEL));
        });
    refreshStatus();
  }

  void newPage() {
    title("1 · Elige el contenido");
    category =
        spinner(
            "Temática",
            new String[] {"Historias de Reddit", "Salud mental", "Psicología cotidiana"},
            draft.optInt("category", 0));
    input =
        field(
            "Texto completo, tema o enlaces de Reddit (uno por línea)",
            draft.optString("input"),
            false,
            6);
    hint(
        "Para texto sin IA, escribe el título en la primera línea y la narración debajo. Para"
            + " lotes de temas o enlaces, usa un elemento por línea.");
    button(
        "Ideas para un tema",
        () -> {
          String[] ideas = {
            "Ansiedad social",
            "TDAH en adultos",
            "Burnout",
            "El costo hundido",
            "Sesgo de confirmación",
            "Por qué recordamos lo último"
          };
          new AlertDialog.Builder(this)
              .setTitle("Ideas")
              .setItems(ideas, (d, w) -> input.setText(ideas[w]))
              .show();
        });
    title("2 · Voz y estilo");
    template =
        spinner(
            "Plantilla",
            new String[] {"aleatoria", "clasica", "impacto", "noche", "diario", "pop", "tetrica"},
            draft.optInt("template", 0));
    satisfactory =
        check(
            "Fondos satisfactorios (clips online o locales)",
            draft.optBoolean("satisfactory", true));
    source =
        spinner("Banco de videos", new String[] {"pixabay", "pexels"}, draft.optInt("source", 0));
    TextView pexels = label("Recursos de Pexels · pexels.com", 13, SAGE);
    pexels.setOnClickListener(
        v -> startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://www.pexels.com/"))));
    page.addView(pexels);
    volume = field("Volumen de música (0 a 2)", draft.optString("volume", "0.7"), false, 1);
    volume.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
    String[][] options = {
      {"tarjeta", "Tarjeta inicial"},
      {"barra", "Barra de progreso"},
      {"karaoke", "Palabra actual"},
      {"encuesta", "Encuesta final"},
      {"zoom", "Zoom al cambiar de escena"},
      {"sonidos", "Efectos de sonido"},
      {"loop", "Cierre para volver al inicio"}
    };
    JSONObject flags = draft.optJSONObject("extras");
    for (String[] o : options)
      extras.put(o[0], check(o[1], flags == null || flags.optBoolean(o[0], true)));
    final int[] previous = {draft.optInt("category", 0)};
    category.setOnItemSelectedListener(
        new AdapterView.OnItemSelectedListener() {
          public void onNothingSelected(AdapterView<?> p) {}

          public void onItemSelected(AdapterView<?> p, View view, int n, long id) {
            if (n == previous[0]) return;
            previous[0] = n;
            template.setSelection(n == 1 ? 6 : n == 2 ? 2 : 0);
            for (String k : extras.keySet())
              extras
                  .get(k)
                  .setChecked(
                      n == 0 || !(k.equals("tarjeta") || k.equals("encuesta") || k.equals("loop")));
          }
        });
    hint(
        "Se utiliza una voz de Android descargada en español. Las voces de PC se sustituyen por la"
            + " voz local elegida en Ajustes.");
    title("3 · Genera");
    button("Crear guion con IA y renderizar", () -> submit(false));
    button("Convertir texto sin IA y renderizar", () -> submit(true));
    button(
        "Renderizar ejemplo sin conexión",
        () -> {
          try {
            startJob(
                new JSONObject()
                    .put("mode", "render")
                    .put("items", new JSONArray().put("demo.json")));
          } catch (Exception e) {
            toast(e.getMessage());
          }
        });
  }

  void saveDraft() {
    if (input == null) return;
    try {
      draft
          .put("input", input.getText().toString())
          .put("category", category.getSelectedItemPosition())
          .put("template", template.getSelectedItemPosition())
          .put("source", source.getSelectedItemPosition())
          .put("satisfactory", satisfactory.isChecked())
          .put("volume", volume.getText().toString());
      JSONObject flags = new JSONObject();
      for (String k : extras.keySet()) flags.put(k, extras.get(k).isChecked());
      draft.put("extras", flags);
      Store.write(new File(getFilesDir(), "draft.json"), draft.toString());
    } catch (Exception ignored) {
    }
  }

  JSONObject options() throws Exception {
    saveDraft();
    return new JSONObject()
        .put("plantilla", template.getSelectedItem().toString())
        .put("motor_voz", "android")
        .put("volumen_musica", Double.parseDouble(volume.getText().toString()))
        .put("fondo_satisfactorio", satisfactory.isChecked())
        .put("fuente_videos", source.getSelectedItem().toString())
        .put("extras", draft.getJSONObject("extras"));
  }

  void submit(boolean plain) {
    try {
      String text = input.getText().toString().trim();
      if (text.isEmpty()) throw new IOException("Escribe el contenido primero");
      String cat =
          new String[] {"reddit", "salud_mental", "psicologia_diaria"}
              [category.getSelectedItemPosition()];
      JSONArray items = new JSONArray();
      if (!plain && (!cat.equals("reddit") || text.startsWith("https://"))) {
        for (String line : text.split("\\n")) if (!line.trim().isEmpty()) items.put(line.trim());
      } else items.put(text);
      if (items.length() > 20) throw new IOException("Máximo 20 videos por lote");
      JSONObject opts = options();
      double vol = opts.getDouble("volumen_musica");
      if (!Double.isFinite(vol) || vol < 0 || vol > 2)
        throw new IOException("El volumen debe estar entre 0 y 2");
      startJob(
          new JSONObject()
              .put("mode", plain ? "text" : "generate")
              .put("categoria_video", cat)
              .put("items", items)
              .put("options", opts));
    } catch (Exception e) {
      error(e);
    }
  }

  void startJob(JSONObject job) throws Exception {
    if (RenderService.running) throw new IOException("Ya hay un trabajo activo");
    Store.write(new File(getFilesDir(), "job.json"), job.toString(2));
    startForegroundService(new Intent(this, RenderService.class));
    status.setText("Iniciando…");
  }

  void scriptsPage() {
    title("Guiones y recursos");
    button(
        "Importar guiones JSON",
        () -> pick("script", "application/json", "text/plain", "application/octet-stream"));
    button(
        "Importar proyecto ZIP del PC",
        () -> pick("zip", "application/zip", "application/octet-stream"));
    button("Añadir fotos", () -> pick("image", "image/*"));
    button("Añadir videos de fondo", () -> pick("video", "video/*"));
    button("Añadir música", () -> pick("music", "audio/*"));
    button("Añadir narración propia", () -> pick("voice", "audio/*"));
    hint(
        "Los guiones importados conservan sus opciones. Las rutas locales del JSON deben coincidir"
            + " con los archivos importados.");
    List<File> scripts = Store.list(this, "historias", ".json");
    for (File f : scripts) button(f.getName(), () -> scriptActions(f));
  }

  void scriptActions(File f) {
    String[] actions = {"Editar y revisar JSON", "Renderizar con sus opciones", "Compartir guion"};
    new AlertDialog.Builder(this)
        .setTitle(f.getName())
        .setItems(
            actions,
            (d, n) -> {
              if (n == 0) edit(f);
              else if (n == 1)
                try {
                  String rel =
                      new File(Store.root(this), "historias")
                          .toPath()
                          .relativize(f.toPath())
                          .toString()
                          .replace('\\', '/');
                  startJob(
                      new JSONObject()
                          .put("mode", "render")
                          .put("items", new JSONArray().put(rel)));
                } catch (Exception e) {
                  error(e);
                }
              else share(f, "application/json");
            })
        .show();
  }

  void edit(File f) {
    try {
      EditText text = new EditText(this);
      text.setText(Store.read(f));
      text.setTextColor(INK);
      text.setTextSize(14);
      text.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
      text.setMinLines(10);
      ScrollView scroll = new ScrollView(this);
      scroll.addView(text);
      AlertDialog dialog =
          new AlertDialog.Builder(this)
              .setTitle("Revisar guion")
              .setView(scroll)
              .setPositiveButton("Guardar", null)
              .setNegativeButton("Cerrar", null)
              .create();
      dialog.setOnShowListener(
          d ->
              dialog
                  .getButton(AlertDialog.BUTTON_POSITIVE)
                  .setOnClickListener(
                      v -> {
                        if (RenderService.running) {
                          toast("Espera a que termine el trabajo para editar");
                          return;
                        }
                        try {
                          JSONObject cfg = new JSONObject(text.getText().toString());
                          Script.validate(cfg);
                          Store.write(f, cfg.toString(2));
                          dialog.dismiss();
                          toast("Guion guardado");
                        } catch (Exception e) {
                          error(e);
                        }
                      }));
      dialog.show();
    } catch (Exception e) {
      error(e);
    }
  }

  void videosPage() {
    title("Biblioteca");
    hint(
        "Los videos terminados también se copian a Movies/ShortsReddit. Desde aquí puedes verlos,"
            + " compartirlos y marcar los publicados.");
    button("Exportar proyecto completo a ZIP", () -> exportProject());
    button(
        "Limpiar caché temporal",
        () -> {
          if (RenderService.running) {
            toast("Espera al final del trabajo");
            return;
          }
          Store.delete(getCacheDir());
          getCacheDir().mkdirs();
          toast("Caché vacía");
        });
    List<File> videos = Store.list(this, "salida", ".mp4");
    if (videos.isEmpty()) hint("Todavía no hay videos. Empieza con el ejemplo en Crear.");
    for (File f : videos) {
      boolean published = f.getPath().contains(File.separator + "subidos" + File.separator);
      try {
        File meta = metadata(f);
        if (meta.exists())
          published = new JSONObject(Store.read(meta)).optBoolean("published", published);
      } catch (Exception ignored) {
      }
      button((published ? "✓ " : "") + f.getName(), () -> videoActions(f));
    }
  }

  File metadata(File f) {
    return new File(f.getParentFile(), f.getName().replace(".mp4", ".meta.json"));
  }

  void videoActions(File f) {
    String[] actions = {
      "Reproducir",
      "Compartir video",
      "Exportar video",
      "Ver y copiar descripción",
      "Marcar como publicado / pendiente"
    };
    new AlertDialog.Builder(this)
        .setTitle(f.getName())
        .setItems(
            actions,
            (d, n) -> {
              if (n == 0)
                try {
                  Intent view =
                      new Intent(Intent.ACTION_VIEW)
                          .setDataAndType(Store.uri(this, f), "video/mp4")
                          .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                  startActivity(view);
                } catch (Exception e) {
                  error(e);
                }
              else if (n == 1) share(f, "video/mp4");
              else if (n == 2) {
                exporting = f;
                exportProject = false;
                createDocument("video/mp4", f.getName());
              } else if (n == 3) {
                try {
                  File description =
                      new File(f.getParentFile(), f.getName().replace(".mp4", ".txt"));
                  if (!description.exists())
                    description =
                        new File(
                            f.getParentFile(), f.getName().replace(".mp4", "_descripcion.txt"));
                  String desc = Store.read(description);
                  TextView text = label(desc, 15, INK);
                  text.setTextIsSelectable(true);
                  ScrollView scroll = new ScrollView(this);
                  scroll.addView(text);
                  new AlertDialog.Builder(this)
                      .setTitle("Descripción")
                      .setView(scroll)
                      .setPositiveButton(
                          "Copiar",
                          (a, b) -> {
                            ((ClipboardManager) getSystemService(CLIPBOARD_SERVICE))
                                .setPrimaryClip(ClipData.newPlainText("Descripción", desc));
                            toast("Copiada");
                          })
                      .setNegativeButton("Cerrar", null)
                      .show();
                } catch (Exception e) {
                  error(e);
                }
              } else
                try {
                  File meta = metadata(f);
                  JSONObject j =
                      meta.exists() ? new JSONObject(Store.read(meta)) : new JSONObject();
                  j.put(
                      "published",
                      !j.optBoolean(
                          "published",
                          f.getPath().contains(File.separator + "subidos" + File.separator)));
                  Store.write(meta, j.toString(2));
                  show(2);
                } catch (Exception e) {
                  error(e);
                }
            })
        .show();
  }

  void share(File f, String type) {
    try {
      Uri uri = Store.uri(this, f);
      Intent share =
          new Intent(Intent.ACTION_SEND)
              .setType(type)
              .putExtra(Intent.EXTRA_STREAM, uri)
              .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
      share.setClipData(ClipData.newRawUri("Archivo", uri));
      startActivity(Intent.createChooser(share, "Compartir"));
    } catch (Exception e) {
      error(e);
    }
  }

  void settingsPage() {
    title("Configuración");
    JSONObject settings;
    try {
      settings = Store.settings(this);
    } catch (Exception e) {
      error(e);
      return;
    }
    hint(
        "El render y la voz local funcionan sin servidor. La IA y los bancos de imágenes necesitan"
            + " internet. Tus claves se guardan cifradas en este dispositivo.");
    EditText
        base =
            field(
                "Endpoint compatible con OpenAI (HTTPS)",
                settings.optString("base_url", "https://api.deepseek.com"),
                false,
                1),
        key = field("Clave de IA", settings.optString("api_key"), true, 1),
        model = field("Modelo", settings.optString("modelo", "deepseek-chat"), false, 1),
        pexels = field("Clave de Pexels", settings.optString("pexels"), true, 1),
        pixabay = field("Clave de Pixabay", settings.optString("pixabay"), true, 1);
    CheckBox low =
        check(
            "Exportar a 720 × 1280 para ahorrar tiempo",
            settings.optBoolean("resolucion_720", false));
    VoicePicker picker = new VoicePicker(this, settings);
    voicePicker = picker;
    button(
        "Instalar voces / ajustes de síntesis",
        () -> {
          try {
            startActivity(new Intent("com.android.settings.TTS_SETTINGS"));
          } catch (Exception e) {
            try {
              startActivity(new Intent(TextToSpeech.Engine.ACTION_INSTALL_TTS_DATA));
            } catch (Exception x) {
              toast("Abre Ajustes → Texto a voz y descarga español");
            }
          }
        });
    button(
        "Guardar ajustes",
        () -> {
          try {
            String url = base.getText().toString().trim();
            if (!url.startsWith("https://")) throw new IOException("El endpoint debe usar HTTPS");
            settings
                .put("base_url", url)
                .put("api_key", key.getText().toString().trim())
                .put("modelo", model.getText().toString().trim())
                .put("pexels", pexels.getText().toString().trim())
                .put("pixabay", pixabay.getText().toString().trim())
                .put("resolucion_720", low.isChecked());
            picker.save(settings);
            Store.settings(this, settings);
            toast("Ajustes guardados");
          } catch (Exception e) {
            error(e);
          }
        });
    button(
        "Importar llm.json o claves.json",
        () -> pick("config", "application/json", "text/plain", "application/octet-stream"));
    hint(
        "Esta edición sustituye Edge, Kokoro, XTTS y Chatterbox por TTS local de Android o"
            + " narraciones importadas. No clona voces. Las marcas de karaoke son aproximadas si el"
            + " motor no proporciona tiempos; puedes importar marcas exactas en el JSON.");
  }

  void pick(String kind, String... mime) {
    if (RenderService.running) {
      toast("Espera al final del trabajo para importar recursos");
      return;
    }
    importing = kind;
    Intent intent =
        new Intent(Intent.ACTION_OPEN_DOCUMENT)
            .setType(mime[0])
            .addCategory(Intent.CATEGORY_OPENABLE)
            .putExtra(Intent.EXTRA_MIME_TYPES, mime)
            .putExtra(Intent.EXTRA_ALLOW_MULTIPLE, !kind.equals("zip") && !kind.equals("config"));
    startActivityForResult(intent, 20);
  }

  String filename(Uri uri) {
    String name = "archivo";
    try (Cursor c =
        getContentResolver()
            .query(uri, new String[] {OpenableColumns.DISPLAY_NAME}, null, null, null)) {
      if (c != null && c.moveToFirst()) name = c.getString(0);
    }
    return name.replaceAll("[\\\\/:*?\"<>|]", "_");
  }

  void createDocument(String mime, String name) {
    startActivityForResult(
        new Intent(Intent.ACTION_CREATE_DOCUMENT)
            .addCategory(Intent.CATEGORY_OPENABLE)
            .setType(mime)
            .putExtra(Intent.EXTRA_TITLE, name),
        21);
  }

  void exportProject() {
    if (RenderService.running) {
      toast("Espera al final del trabajo para exportar");
      return;
    }
    exportProject = true;
    exporting = null;
    createDocument("application/zip", "shorts-reddit-proyecto.zip");
  }

  protected void onActivityResult(int request, int result, Intent data) {
    super.onActivityResult(request, result, data);
    if (result != RESULT_OK || data == null) return;
    if (request == 20) {
      List<Uri> uris = new ArrayList<>();
      if (data.getClipData() != null)
        for (int i = 0; i < data.getClipData().getItemCount(); i++)
          uris.add(data.getClipData().getItemAt(i).getUri());
      else if (data.getData() != null) uris.add(data.getData());
      String kind = importing;
      if (RenderService.running) {
        toast("Hay un trabajo activo. Importa cuando termine.");
        return;
      }
      io.execute(
          () -> {
            try {
              for (Uri uri : uris) importFile(uri, kind);
              handler.post(
                  () -> {
                    toast("Importación terminada");
                    show(tab);
                  });
            } catch (Exception e) {
              handler.post(() -> error(e));
            }
          });
    } else if (request == 21 && data.getData() != null) {
      Uri uri = data.getData();
      File f = exporting;
      boolean all = exportProject;
      io.execute(
          () -> {
            try {
              OutputStream out = getContentResolver().openOutputStream(uri);
              if (out == null) throw new IOException("No se pudo abrir el destino");
              if (all) Store.export(this, out);
              else
                try (InputStream in = new FileInputStream(f)) {
                  Store.copy(in, out);
                }
              handler.post(() -> toast("Archivo exportado"));
            } catch (Exception e) {
              handler.post(() -> error(e));
            }
          });
    }
  }

  void importFile(Uri uri, String kind) throws Exception {
    String name = filename(uri);
    try (InputStream in = getContentResolver().openInputStream(uri)) {
      if (in == null) throw new IOException("No se pudo abrir el archivo");
      if (kind.equals("zip")) {
        Store.unzip(this, in);
        return;
      }
      if (kind.equals("config") || kind.equals("script")) {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        byte[] bytes = new byte[8192];
        int n;
        while ((n = in.read(bytes)) != -1) {
          if (buf.size() + n > 4 * 1024 * 1024) throw new IOException("JSON demasiado grande");
          buf.write(bytes, 0, n);
        }
        JSONObject obj = new JSONObject(buf.toString("UTF-8"));
        if (kind.equals("config")) {
          JSONObject existing = Store.settings(this);
          for (String key : new String[] {"base_url", "api_key", "modelo", "pexels", "pixabay"})
            if (obj.has(key)) existing.put(key, obj.get(key));
          Store.settings(this, existing);
        } else {
          Script.validate(obj);
          File dest =
              new File(
                  Store.root(this),
                  "historias/" + (name.endsWith(".json") ? name : name + ".json"));
          if (dest.exists()) dest = new File(dest.getParentFile(), Store.name(name) + ".json");
          Store.write(dest, obj.toString(2));
        }
        return;
      }
      String folder =
          kind.equals("image")
              ? "imagenes"
              : kind.equals("video") ? "videos_fondo" : kind.equals("music") ? "musica" : "voces";
      File dest = new File(Store.root(this), folder + "/" + name);
      if (dest.exists())
        dest = new File(dest.getParentFile(), System.currentTimeMillis() + "_" + name);
      File tmp = new File(dest.getPath() + ".tmp");
      try (OutputStream out = new FileOutputStream(tmp)) {
        byte[] b = new byte[65536];
        int n;
        long total = 0;
        while ((n = in.read(b)) != -1) {
          total += n;
          if (total > 1024L * 1024 * 1024)
            throw new IOException("Máximo 1 GB por archivo importado");
          out.write(b, 0, n);
        }
      } catch (Exception e) {
        tmp.delete();
        throw e;
      }
      java.nio.file.Files.move(tmp.toPath(), dest.toPath());
    }
  }

  void refreshStatus() {
    if (status == null) return;
    File file = new File(getFilesDir(), "status.json");
    if (!file.exists()) {
      progress.setProgress(0);
      return;
    }
    try {
      JSONObject s = new JSONObject(Store.read(file));
      String msg = s.optString("status");
      if (s.optBoolean("active")
          && !RenderService.running
          && System.currentTimeMillis() - s.optLong("updated") > 10000)
        msg = "Trabajo interrumpido. Puedes volver a renderizar su guion desde Guiones.";
      status.setText(msg);
      log.setText(s.optString("log"));
      progress.setIndeterminate(RenderService.running && !msg.startsWith("Render "));
      if (msg.matches("Render \\d+ %")) {
        progress.setIndeterminate(false);
        progress.setProgress(Integer.parseInt(msg.replaceAll("\\D", "")));
      } else if (!RenderService.running) {
        progress.setIndeterminate(false);
        progress.setProgress(msg.startsWith("Completado") ? 100 : 0);
      }
    } catch (Exception ignored) {
    }
  }

  void toast(String msg) {
    Toast.makeText(this, msg == null ? "Error" : msg, Toast.LENGTH_LONG).show();
  }

  void error(Exception e) {
    new AlertDialog.Builder(this)
        .setTitle("Revisa este detalle")
        .setMessage(e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage())
        .setPositiveButton("Entendido", null)
        .show();
  }
}
