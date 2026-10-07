package com.shortsreddit.mobile;

import android.content.*;
import android.database.*;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.*;

public final class FilesProvider extends ContentProvider {
  public boolean onCreate() {
    return true;
  }

  private File file(Uri uri) throws IOException {
    return Store.resolve(getContext(), Uri.decode(uri.getEncodedPath().substring(1)));
  }

  public String getType(Uri uri) {
    String p = uri.toString();
    return p.endsWith(".mp4")
        ? "video/mp4"
        : p.endsWith(".json") ? "application/json" : "text/plain";
  }

  public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
    if (!mode.equals("r")) throw new FileNotFoundException("Solo lectura");
    try {
      return ParcelFileDescriptor.open(file(uri), ParcelFileDescriptor.MODE_READ_ONLY);
    } catch (IOException e) {
      throw new FileNotFoundException(e.getMessage());
    }
  }

  public Cursor query(Uri uri, String[] projection, String selection, String[] args, String sort) {
    try {
      File f = file(uri);
      String[] cols =
          projection == null
              ? new String[] {OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE}
              : projection;
      MatrixCursor c = new MatrixCursor(cols);
      Object[] values = new Object[cols.length];
      for (int i = 0; i < cols.length; i++)
        values[i] = cols[i].equals(OpenableColumns.SIZE) ? f.length() : f.getName();
      c.addRow(values);
      return c;
    } catch (IOException e) {
      return null;
    }
  }

  public Uri insert(Uri u, ContentValues v) {
    throw new UnsupportedOperationException();
  }

  public int update(Uri u, ContentValues v, String s, String[] a) {
    throw new UnsupportedOperationException();
  }

  public int delete(Uri u, String s, String[] a) {
    throw new UnsupportedOperationException();
  }
}
