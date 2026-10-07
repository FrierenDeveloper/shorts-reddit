package com.shortsreddit.mobile;

import android.content.Context;
import java.io.*;
import java.util.*;
import java.util.regex.Pattern;
import org.json.*;

final class MediaAssets {
  static final Pattern MINORS =
      Pattern.compile(
          "(?iu)\\b(child|children|kids?|bab(y|ies)|toddler|infant|boy|girl|teen\\w*|adolescent\\w*|niñ[oa]s?|beb[ée]s?|menores?|hij[oa]s?|daughter|son|face|portrait|selfie|rostro|retrato|cara)\\b");
  final Context context;
  final JSONObject settings;
  final Audio.Progress progress;
  final File cache;
  final List<String> credits = new ArrayList<>();
  final Set<String> used = new HashSet<>();

  MediaAssets(Context c, JSONObject s, Audio.Progress p) {
    context = c;
    settings = s;
    progress = p;
    cache = new File(c.getCacheDir(), "bancos");
    cache.mkdirs();
  }

  static final class Asset {
    File file;
    boolean video;

    Asset(File f, boolean v) {
      file = f;
      video = v;
    }
  }

  List<Asset> plan(JSONObject cfg, int scenes) throws Exception {
    List<Asset> result = new ArrayList<>();
    List<File> local = Store.list(context, "videos_fondo", "");
    local.removeIf(f -> !f.getName().matches("(?i).*\\.(mp4|webm|mkv|mov)$"));
    boolean satisfactory = cfg.optBoolean("fondo_satisfactorio", false);
    List<Asset> clips = new ArrayList<>();
    if (satisfactory) {
      String source = cfg.optString("fuente_videos", "pixabay").toLowerCase(Locale.ROOT);
      String[] themes = {"kinetic sand", "soap cutting", "slime hands", "pottery hands"};
      String theme = themes[new Random().nextInt(themes.length)];
      try {
        clips = videos(theme, source);
      } catch (Exception e) {
        Net.check();
        progress.log("Banco de videos no disponible; se usa la biblioteca local.");
      }
      if (clips.isEmpty()) for (File f : local) clips.add(new Asset(f, true));
    }
    JSONArray imgs = cfg.optJSONArray("imagenes");
    List<Asset> photos = new ArrayList<>();
    if (!satisfactory || clips.isEmpty()) {
      if (imgs != null)
        for (int i = 0; i < imgs.length(); i++) {
          Net.check();
          JSONObject item = imgs.optJSONObject(i);
          if (item == null) continue;
          String path = item.optString("archivo");
          Asset a = null;
          if (!path.isEmpty()) {
            File f = Store.resolve(context, path);
            if (!f.exists())
              throw new IOException(
                  "Falta " + path + ". Importa los recursos locales antes de renderizar.");
            a = new Asset(f, f.getName().matches("(?i).*\\.(mp4|webm|mov|mkv)$"));
          } else
            try {
              String query = item.optString("buscar", "empty room");
              if (cfg.optBoolean("broll", true) && i % 2 == 0) {
                try {
                  List<Asset> found = videos(query, cfg.optString("fuente_videos", "pexels"));
                  if (!found.isEmpty()) a = found.get(0);
                } catch (Exception ignored) {
                  Net.check();
                }
              }
              if (a == null) a = image(query, item.optInt("opcion", 0));
              JSONArray alternatives = item.optJSONArray("alternativas");
              if (a == null && alternatives != null)
                for (int j = 0; j < alternatives.length() && a == null; j++)
                  a = image(alternatives.optString(j), 0);
            } catch (Exception e) {
              Net.check();
              progress.log("Imagen " + (i + 1) + ": búsqueda no disponible.");
            }
          photos.add(a);
        }
      if (photos.isEmpty()) {
        List<File> locals = Store.list(context, "imagenes", "");
        locals.removeIf(f -> !f.getName().matches("(?i).*\\.(jpg|jpeg|png|webp)$"));
        for (File f : locals) photos.add(new Asset(f, false));
      }
    }
    JSONArray json = cfg.getJSONArray("escenas");
    for (int i = 0; i < scenes; i++) {
      if (!clips.isEmpty()) result.add(clips.get(i % clips.size()));
      else if (!photos.isEmpty()) {
        int idx = json.getJSONObject(i).optInt("imagen", i);
        result.add(photos.get(Math.floorMod(idx, photos.size())));
      } else result.add(null);
    }
    if (result.stream().allMatch(Objects::isNull))
      progress.log(
          "Sin recursos visuales: se utiliza el fondo animado de la plantilla. Puedes importar"
              + " fotos o videos.");
    return result;
  }

  private boolean safe(JSONObject hit) {
    return !MINORS.matcher(hit.toString().replace('_', ' ').replace('-', ' ')).find();
  }

  private File fetch(String url, String ext) throws Exception {
    if (used.contains(url)) throw new IOException("Recurso repetido");
    used.add(url);
    String hash =
        hex(java.security.MessageDigest.getInstance("SHA-256").digest(url.getBytes("UTF-8")));
    File f = new File(cache, hash + ext);
    if (!f.exists() || System.currentTimeMillis() - f.lastModified() > 86400000L)
      Net.download(url, f);
    return f;
  }

  private String hex(byte[] b) {
    StringBuilder s = new StringBuilder();
    for (byte x : b) s.append(String.format(Locale.ROOT, "%02x", x));
    return s.toString();
  }

  private Asset image(String query, int option) throws Exception {
    query = MINORS.matcher(query).replaceAll(" ").trim();
    if (query.isEmpty()) query = "empty room";
    List<JSONObject> candidates = new ArrayList<>();
    String key = settings.optString("pexels");
    if (!key.isEmpty())
      try {
        JSONArray hits =
            Net.json(
                    "https://api.pexels.com/v1/search?query="
                        + Net.q(query)
                        + "&per_page=15&orientation=portrait",
                    "GET",
                    null,
                    key)
                .getJSONArray("photos");
        for (int i = 0; i < hits.length(); i++) {
          JSONObject h = hits.getJSONObject(i);
          if (safe(h) && h.optInt("width") >= 1080)
            candidates.add(
                new JSONObject()
                    .put("url", h.getJSONObject("src").getString("large2x"))
                    .put(
                        "credit",
                        "Pexels · " + h.optString("photographer") + " · " + h.optString("url")));
        }
      } catch (Exception ignored) {
        Net.check();
      }
    key = settings.optString("pixabay");
    if (candidates.isEmpty() && !key.isEmpty())
      try {
        JSONArray hits =
            Net.json(
                    "https://pixabay.com/api/?key="
                        + Net.q(key)
                        + "&q="
                        + Net.q(query)
                        + "&image_type=photo&orientation=vertical&safesearch=true&per_page=20",
                    "GET",
                    null,
                    null)
                .getJSONArray("hits");
        for (int i = 0; i < hits.length(); i++) {
          JSONObject h = hits.getJSONObject(i);
          if (safe(h) && h.optInt("imageWidth") >= 1080)
            candidates.add(
                new JSONObject()
                    .put("url", h.getString("largeImageURL"))
                    .put(
                        "credit",
                        "Pixabay · " + h.optString("user") + " · " + h.optString("pageURL")));
        }
      } catch (Exception ignored) {
        Net.check();
      }
    if (candidates.isEmpty())
      try {
        JSONArray hits =
            Net.json(
                    "https://api.openverse.org/v1/images/?q="
                        + Net.q(query)
                        + "&license=cc0,pdm&page_size=20",
                    "GET",
                    null,
                    null)
                .getJSONArray("results");
        for (int i = 0; i < hits.length(); i++) {
          JSONObject h = hits.getJSONObject(i);
          if (safe(h) && Arrays.asList("cc0", "pdm").contains(h.optString("license")))
            candidates.add(
                new JSONObject()
                    .put("url", h.getString("url"))
                    .put(
                        "credit",
                        "Openverse · "
                            + h.optString("creator")
                            + " · "
                            + h.optString("license")
                            + " · "
                            + h.optString("foreign_landing_url")));
        }
      } catch (Exception ignored) {
        Net.check();
      }
    if (candidates.isEmpty())
      try {
        JSONObject pages =
            Net.json(
                    "https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrsearch="
                        + Net.q(query + " filetype:bitmap")
                        + "&gsrlimit=15&prop=imageinfo&iiprop=url%7Cextmetadata&iiurlwidth=1080",
                    "GET",
                    null,
                    null)
                .getJSONObject("query")
                .getJSONObject("pages");
        Iterator<String> it = pages.keys();
        while (it.hasNext()) {
          JSONObject p = pages.getJSONObject(it.next());
          JSONObject info = p.getJSONArray("imageinfo").getJSONObject(0);
          String license =
              info.getJSONObject("extmetadata").optJSONObject("LicenseShortName") == null
                  ? ""
                  : info.getJSONObject("extmetadata")
                      .getJSONObject("LicenseShortName")
                      .optString("value");
          if (safe(p) && (license.equals("CC0") || license.equals("Public domain")))
            candidates.add(
                new JSONObject()
                    .put("url", info.optString("thumburl", info.getString("url")))
                    .put(
                        "credit",
                        "Wikimedia Commons · "
                            + p.optString("title")
                            + " · "
                            + license
                            + " · "
                            + info.optString("descriptionurl")));
        }
      } catch (Exception ignored) {
        Net.check();
      }
    for (int i = 0; i < candidates.size(); i++) {
      JSONObject h = candidates.get(Math.floorMod(i + option, candidates.size()));
      try {
        File f = fetch(h.getString("url"), ".jpg");
        credits.add(h.getString("credit"));
        return new Asset(f, false);
      } catch (Exception ignored) {
        Net.check();
      }
    }
    return null;
  }

  private List<Asset> videos(String query, String source) throws Exception {
    List<Asset> out = new ArrayList<>();
    boolean pexels = source.equals("pexels");
    String key = settings.optString(pexels ? "pexels" : "pixabay");
    if (key.isEmpty()) return out;
    String url =
        pexels
            ? "https://api.pexels.com/videos/search?query=" + Net.q(query) + "&per_page=15"
            : "https://pixabay.com/api/videos/?key="
                + Net.q(key)
                + "&q="
                + Net.q(query)
                + "&safesearch=true&per_page=20";
    JSONArray hits =
        Net.json(url, "GET", null, pexels ? key : null).getJSONArray(pexels ? "videos" : "hits");
    for (int i = 0; i < hits.length() && out.size() < 4; i++) {
      JSONObject h = hits.getJSONObject(i);
      if (!safe(h) || h.optInt("duration") < 15) continue;
      String download = "";
      int best = 0;
      if (pexels) {
        JSONArray files = h.getJSONArray("video_files");
        for (int j = 0; j < files.length(); j++) {
          JSONObject f = files.getJSONObject(j);
          int w = f.optInt("width"), height = f.optInt("height"), pixels = w * height;
          if (w > 0
              && w <= 1920
              && height <= 1920
              && pixels > best
              && f.optString("file_type").equals("video/mp4")) {
            download = f.optString("link");
            best = pixels;
          }
        }
      } else {
        JSONObject files = h.getJSONObject("videos");
        for (String quality : new String[] {"medium", "small", "tiny"}) {
          JSONObject f = files.optJSONObject(quality);
          if (f != null
              && !f.optString("url").isEmpty()
              && f.optLong("size") < 180L * 1024 * 1024) {
            download = f.getString("url");
            break;
          }
        }
      }
      if (download.isEmpty()) continue;
      try {
        out.add(new Asset(fetch(download, ".mp4"), true));
        credits.add(
            (pexels ? "Pexels" : "Pixabay") + " · " + h.optString(pexels ? "url" : "pageURL"));
      } catch (Exception ignored) {
        Net.check();
      }
    }
    return out;
  }

  String credits() {
    return String.join("\n", new LinkedHashSet<>(credits));
  }
}
