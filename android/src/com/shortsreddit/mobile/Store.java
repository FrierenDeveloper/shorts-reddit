package com.shortsreddit.mobile;

import android.content.*;
import android.net.Uri;
import android.os.*;
import android.security.keystore.*;
import android.util.Base64;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.*;
import java.util.zip.*;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;
import org.json.*;

final class Store {
  static final String[] DIRS = {
    "historias", "posts", "musica", "voces", "videos_fondo", "imagenes", "salida", "registros"
  };

  static File root(Context c) {
    return new File(c.getFilesDir(), "proyecto");
  }

  static void init(Context c) throws Exception {
    for (String d : DIRS) new File(root(c), d).mkdirs();
    File demo = new File(root(c), "historias/demo.json");
    if (!demo.exists())
      try (InputStream in = c.getAssets().open("examples/demo.json")) {
        copy(in, new FileOutputStream(demo));
      }
  }

  static void copy(InputStream in, OutputStream out) throws IOException {
    try (OutputStream close = out) {
      byte[] b = new byte[65536];
      int n;
      while ((n = in.read(b)) != -1) close.write(b, 0, n);
    }
  }

  static String read(File f) throws IOException {
    return new String(java.nio.file.Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8);
  }

  static void write(File f, String s) throws IOException {
    f.getParentFile().mkdirs();
    File tmp = new File(f.getParentFile(), f.getName() + ".tmp");
    try (FileOutputStream out = new FileOutputStream(tmp)) {
      out.write(s.getBytes(StandardCharsets.UTF_8));
      out.getFD().sync();
    }
    java.nio.file.Files.move(
        tmp.toPath(), f.toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
  }

  static String slug(String s) {
    String x =
        s.toLowerCase(Locale.ROOT).replaceAll("[^\\p{L}\\p{N}]+", "_").replaceAll("^_|_$", "");
    return x.isEmpty() ? "historia" : x.substring(0, Math.min(60, x.length()));
  }

  static String name(String title) {
    return new java.text.SimpleDateFormat("yyyyMMdd_HHmmss_SSS", Locale.ROOT).format(new Date())
        + "_"
        + slug(title);
  }

  static List<File> list(Context c, String dir, String ext) {
    File[] all = new File(root(c), dir).listFiles();
    List<File> r = new ArrayList<>();
    if (all != null)
      for (File f : all) {
        if (f.isDirectory()) r.addAll(listIn(f, ext));
        else if (f.getName().endsWith(ext)) r.add(f);
      }
    r.sort((a, b) -> Long.compare(b.lastModified(), a.lastModified()));
    return r;
  }

  private static List<File> listIn(File dir, String ext) {
    List<File> r = new ArrayList<>();
    File[] all = dir.listFiles();
    if (all != null)
      for (File f : all) {
        if (f.isDirectory()) r.addAll(listIn(f, ext));
        else if (f.getName().endsWith(ext)) r.add(f);
      }
    return r;
  }

  static File resolve(Context c, String path) throws IOException {
    File f = new File(root(c), path);
    String prefix = root(c).getCanonicalPath() + File.separator;
    if (!f.getCanonicalPath().startsWith(prefix))
      throw new IOException("Ruta fuera del proyecto: importa el archivo al teléfono.");
    return f;
  }

  static JSONObject settings(Context c) throws Exception {
    String raw = c.getSharedPreferences("settings", 0).getString("encrypted", "");
    if (raw.isEmpty()) return new JSONObject();
    byte[] pack = Base64.decode(raw, Base64.NO_WRAP);
    if (pack.length < 13) throw new IOException("Configuración dañada");
    Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
    cipher.init(
        Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, Arrays.copyOfRange(pack, 0, 12)));
    return new JSONObject(
        new String(
            cipher.doFinal(Arrays.copyOfRange(pack, 12, pack.length)), StandardCharsets.UTF_8));
  }

  static void settings(Context c, JSONObject obj) throws Exception {
    Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
    cipher.init(Cipher.ENCRYPT_MODE, key());
    byte[] body = cipher.doFinal(obj.toString().getBytes(StandardCharsets.UTF_8));
    byte[] pack = new byte[12 + body.length];
    System.arraycopy(cipher.getIV(), 0, pack, 0, 12);
    System.arraycopy(body, 0, pack, 12, body.length);
    if (!c.getSharedPreferences("settings", 0)
        .edit()
        .putString("encrypted", Base64.encodeToString(pack, Base64.NO_WRAP))
        .commit()) throw new IOException("No se pudo guardar la configuración");
  }

  private static java.security.Key key() throws Exception {
    KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
    ks.load(null);
    String alias = "shorts-settings";
    if (!ks.containsAlias(alias)) {
      KeyGenerator gen = KeyGenerator.getInstance("AES", "AndroidKeyStore");
      gen.init(
          new KeyGenParameterSpec.Builder(
                  alias, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
              .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
              .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
              .build());
      gen.generateKey();
    }
    return ks.getKey(alias, null);
  }

  static void unzip(Context c, InputStream stream) throws Exception {
    // Stage first: a malformed archive never overwrites existing scripts.
    File stage = new File(c.getCacheDir(), "import-" + System.nanoTime());
    stage.mkdirs();
    long total = 0;
    int count = 0;
    try (ZipInputStream zip = new ZipInputStream(stream)) {
      ZipEntry e;
      byte[] buffer = new byte[65536];
      while ((e = zip.getNextEntry()) != null) {
        String p = e.getName().replace('\\', '/');
        if (e.isDirectory()) continue;
        String folder = p.contains("/") ? p.substring(0, p.indexOf('/')) : "";
        if (!Arrays.asList(DIRS).contains(folder)) continue;
        File dst = new File(stage, p);
        if (!dst.getCanonicalPath().startsWith(stage.getCanonicalPath() + File.separator))
          throw new IOException("ZIP con ruta inválida");
        if (++count > 10000) throw new IOException("ZIP con demasiados archivos");
        dst.getParentFile().mkdirs();
        try (OutputStream out = new FileOutputStream(dst)) {
          int n;
          while ((n = zip.read(buffer)) != -1) {
            total += n;
            if (total > 8L * 1024 * 1024 * 1024) throw new IOException("ZIP mayor que 8 GB");
            out.write(buffer, 0, n);
          }
        }
        if (folder.equals("historias") && p.endsWith(".json"))
          Script.validate(new JSONObject(read(dst)));
      }
      merge(stage, root(c));
    } finally {
      delete(stage);
    }
  }

  private static void merge(File stage, File target) throws Exception {
    List<File> files = listIn(stage, "");
    Map<String, String> paths = new HashMap<>();
    String prefix = "importado_" + System.currentTimeMillis() + "_";
    for (File src : files) {
      String rel = stage.toPath().relativize(src.toPath()).toString().replace('\\', '/');
      File dest = new File(target, rel);
      if (dest.exists() && !same(src, dest)) {
        String parent = rel.substring(0, rel.lastIndexOf('/') + 1);
        paths.put(rel, parent + prefix + src.getName());
      }
    }
    for (File src : files) {
      String rel = stage.toPath().relativize(src.toPath()).toString().replace('\\', '/');
      File dest = new File(target, paths.getOrDefault(rel, rel));
      if (!paths.isEmpty() && rel.startsWith("historias/") && rel.endsWith(".json")) {
        JSONObject cfg = new JSONObject(read(src));
        String before = cfg.toString();
        remap(cfg, paths);
        if (!before.equals(cfg.toString())) write(src, cfg.toString(2));
      }
      if (dest.exists() && same(src, dest)) continue;
      if (dest.exists()) {
        dest = new File(dest.getParentFile(), prefix + dest.getName());
      }
      dest.getParentFile().mkdirs();
      java.nio.file.Files.move(src.toPath(), dest.toPath());
    }
  }

  private static boolean same(File a, File b) throws Exception {
    if (a.length() != b.length()) return false;
    java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
    byte[] first = hash(a, digest), second = hash(b, digest);
    return Arrays.equals(first, second);
  }

  private static byte[] hash(File f, java.security.MessageDigest digest) throws IOException {
    digest.reset();
    try (InputStream in = new FileInputStream(f)) {
      byte[] b = new byte[65536];
      int n;
      while ((n = in.read(b)) != -1) digest.update(b, 0, n);
    }
    return digest.digest();
  }

  private static void remap(Object node, Map<String, String> paths) throws JSONException {
    if (node instanceof JSONObject) {
      JSONObject obj = (JSONObject) node;
      Iterator<String> keys = obj.keys();
      while (keys.hasNext()) {
        String key = keys.next();
        Object value = obj.get(key);
        if (value instanceof String) {
          String path = ((String) value).replace('\\', '/');
          if (paths.containsKey(path)) obj.put(key, paths.get(path));
        } else remap(value, paths);
      }
    } else if (node instanceof JSONArray) {
      JSONArray arr = (JSONArray) node;
      for (int i = 0; i < arr.length(); i++) remap(arr.get(i), paths);
    }
  }

  static void export(Context c, OutputStream out) throws Exception {
    try (ZipOutputStream z = new ZipOutputStream(out)) {
      zip(root(c), root(c), z);
    }
  }

  private static void zip(File root, File dir, ZipOutputStream z) throws IOException {
    File[] files = dir.listFiles();
    if (files == null) return;
    for (File f : files) {
      if (f.isDirectory()) zip(root, f, z);
      else if (!f.getName().endsWith(".tmp")) {
        z.putNextEntry(
            new ZipEntry(root.toPath().relativize(f.toPath()).toString().replace('\\', '/')));
        java.nio.file.Files.copy(f.toPath(), z);
        z.closeEntry();
      }
    }
  }

  static void delete(File f) {
    if (f.isDirectory()) {
      File[] fs = f.listFiles();
      if (fs != null) for (File a : fs) delete(a);
    }
    f.delete();
  }

  static Uri uri(Context c, File f) throws IOException {
    return Uri.parse(
        "content://com.shortsreddit.mobile.files/"
            + Uri.encode(root(c).toPath().relativize(f.toPath()).toString().replace('\\', '/')));
  }
}
