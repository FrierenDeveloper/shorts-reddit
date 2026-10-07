package com.shortsreddit.mobile;

import android.text.Html;
import android.util.Xml;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;
import org.xmlpull.v1.XmlPullParser;

final class Net {
  static void check() throws InterruptedIOException {
    if (Thread.currentThread().isInterrupted()) throw new InterruptedIOException("Cancelado");
  }

  static String q(String s) {
    try {
      return URLEncoder.encode(s, "UTF-8");
    } catch (Exception e) {
      throw new IllegalArgumentException(e);
    }
  }

  static HttpURLConnection open(String url, String method, String auth) throws Exception {
    URL u = new URL(url);
    if (!u.getProtocol().equals("https") || u.getHost().isEmpty())
      throw new IOException("Las conexiones externas requieren HTTPS");
    HttpURLConnection con = (HttpURLConnection) u.openConnection();
    con.setConnectTimeout(20000);
    con.setReadTimeout(90000);
    con.setRequestMethod(method);
    con.setInstanceFollowRedirects(false);
    con.setRequestProperty("User-Agent", "ShortsRedditAndroid/1.0 (personal mobile editor)");
    if (auth != null && !auth.isEmpty()) con.setRequestProperty("Authorization", auth);
    return con;
  }

  static JSONObject json(String url, String method, JSONObject body, String auth) throws Exception {
    return new JSONObject(text(url, method, body, auth));
  }

  static String text(String url, String method, JSONObject body, String auth) throws Exception {
    check();
    HttpURLConnection con = open(url, method, auth);
    try {
      if (body != null) {
        con.setDoOutput(true);
        con.setRequestProperty("Content-Type", "application/json");
        try (OutputStream out = con.getOutputStream()) {
          out.write(body.toString().getBytes(StandardCharsets.UTF_8));
        }
      }
      int code = con.getResponseCode();
      if (code < 200 || code >= 300)
        throw new IOException(
            "El servicio devolvió HTTP " + code + ". Revisa la clave, el modelo y el endpoint.");
      ByteArrayOutputStream b = new ByteArrayOutputStream();
      try (InputStream in = con.getInputStream()) {
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) != -1) {
          check();
          if (b.size() + n > 12 * 1024 * 1024) throw new IOException("Respuesta demasiado grande");
          b.write(buf, 0, n);
        }
      }
      return b.toString("UTF-8");
    } finally {
      con.disconnect();
    }
  }

  static void download(String url, File target) throws Exception {
    File part = new File(target.getPath() + ".part");
    target.getParentFile().mkdirs();
    HttpURLConnection con = null;
    try {
      for (int redirect = 0; redirect < 5; redirect++) {
        check();
        con = open(url, "GET", null);
        int code = con.getResponseCode();
        if (code >= 300 && code < 400) {
          String next = con.getHeaderField("Location");
          URL dest = new URL(new URL(url), next);
          url = dest.toString();
          con.disconnect();
          con = null;
          continue;
        }
        if (code != 200) throw new IOException("Descarga: HTTP " + code);
        break;
      }
      if (con == null || con.getResponseCode() != 200)
        throw new IOException("Demasiadas redirecciones");
      long max = 180L * 1024 * 1024;
      if (con.getContentLengthLong() > max) throw new IOException("Recurso mayor que 180 MB");
      try (InputStream in = con.getInputStream();
          OutputStream out = new FileOutputStream(part)) {
        byte[] b = new byte[65536];
        int n;
        long size = 0;
        while ((n = in.read(b)) != -1) {
          check();
          size += n;
          if (size > max) throw new IOException("Recurso mayor que 180 MB");
          out.write(b, 0, n);
        }
      }
      java.nio.file.Files.move(
          part.toPath(), target.toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
    } finally {
      if (con != null) con.disconnect();
      part.delete();
    }
  }

  static String reddit(String input) throws Exception {
    URI u = new URI(input.trim());
    String host = u.getHost();
    if (host == null
        || !(host.equals("reddit.com") || host.endsWith(".reddit.com"))
        || !u.getPath().contains("/comments/"))
      throw new IOException("Usa un enlace de un post de Reddit /comments/");
    String path = u.getPath().replaceAll("/+$", "");
    String url = "https://www.reddit.com" + path;
    try {
      String raw = text(url + ".json?raw_json=1", "GET", null, null);
      JSONObject post =
          new JSONArray(raw)
              .getJSONObject(0)
              .getJSONObject("data")
              .getJSONArray("children")
              .getJSONObject(0)
              .getJSONObject("data");
      String text = post.optString("selftext");
      if (text.isEmpty() || text.equals("[removed]") || text.equals("[deleted]"))
        throw new IOException("Post sin texto");
      return post.getString("title") + "\n" + text;
    } catch (Exception first) {
      check();
      try {
        String xml = text(url + "/.rss", "GET", null, null);
        XmlPullParser p = Xml.newPullParser();
        p.setInput(new StringReader(xml));
        String title = "", content = "";
        boolean entry = false;
        for (int ev = p.getEventType(); ev != XmlPullParser.END_DOCUMENT; ev = p.next()) {
          if (ev == XmlPullParser.START_TAG) {
            if (p.getName().equals("entry")) entry = true;
            else if (entry && p.getName().equals("title")) title = p.nextText();
            else if (entry && p.getName().equals("content")) {
              content =
                  Html.fromHtml(p.nextText(), Html.FROM_HTML_MODE_LEGACY)
                      .toString()
                      .replaceAll("(?s)submitted by.*$", "");
              break;
            }
          }
        }
        if (content.trim().isEmpty()) throw new IOException("Post vacío");
        return title + "\n" + content;
      } catch (Exception second) {
        throw new IOException(
            "Reddit bloqueó la lectura o el post no contiene texto. Pega su texto directamente.");
      }
    }
  }
}
