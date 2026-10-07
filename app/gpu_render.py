"""Composición de fotogramas en GPU (PyTorch + CUDA). Mismo resultado visual que el render en CPU.
Optimizado: fp16 para las capas grandes (fotos, fotograma, subtítulos) en CUDA, inference_mode, y
separación en dos etapas (gpu → cpu) para que el dibujo de overlays en CPU corra en paralelo con la GPU.
Desactivar fp16: SHORTS_GPU_FP32=1."""
import os
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

import make_short as M


class GPURenderer:
    def __init__(self, state, device="cuda"):
        self.d = dev = torch.device(device)
        self.S = state
        self.dt = torch.float16 if (dev.type == "cuda" and os.getenv("SHORTS_GPU_FP32") != "1") else torch.float32
        sw, sh = 216, 384
        yy, xx = torch.meshgrid(torch.arange(sh, device=dev, dtype=torch.float32) / sh,
                                torch.arange(sw, device=dev, dtype=torch.float32) / sw, indexing="ij")
        self.xx, self.yy, self.sw, self.sh = xx, yy, sw, sh
        self.P = torch.tensor(np.random.default_rng(3).random((40, 4)), dtype=torch.float32, device=dev)
        self.vig = 1 - 0.55 * ((xx - 0.5) ** 2 * 1.4 + (yy - 0.5) ** 2)
        self.pal = M.palette_fn(state["moods"])
        ys = torch.linspace(0, 1, M.PH, device=dev)[:, None]
        self.band = (1 - 0.35 * torch.exp(-((ys - 0.5) ** 2) / 0.02))[None].to(self.dt)   # 1×PH×1
        self.photos = [torch.tensor(np.asarray(Image.open(p).convert("RGB")), dtype=self.dt, device=dev)
                       .permute(2, 0, 1).contiguous() for p in state["photos"]]   # 3×h×w
        self.video_bg_frames = state.get("video_bg_frames", [])
        self.video_bg_fps = state.get("video_bg_fps", 0)
        self.video_bg_index = -1
        self.video_bg_image = None
        self.sprites = {}

    # ---- fondo
    def background(self, t):
        xx, yy, s = self.xx, self.yy, t * 0.06
        f = torch.stack([0.5 + 0.5 * torch.sin(2.2 * xx + 1.3 * yy + s * 2.0),
                         0.45 + 0.45 * torch.sin(-1.7 * xx + 2.6 * yy - s * 1.5 + 1.0),
                         0.4 + 0.4 * torch.sin(3.0 * yy - 0.8 * xx + s * 1.1 + 2.0)]) ** 2
        f = f / f.sum(0)
        cols = torch.tensor(np.array(self.pal(t)), dtype=torch.float32, device=self.d)       # 3 colores × RGB
        img = torch.einsum("khw,kc->chw", f, cols)
        wave = 0.04 * torch.exp(-((yy - 0.78 - 0.02 * torch.sin(xx * 6 + t * 0.4)) ** 2) / 0.0015)
        img = img * ((0.9 + 0.1 * np.sin(t * 0.5)) * self.vig) + wave * 255
        px, py, pv, ph = self.P.T
        y = (py - t * 0.006 * (0.5 + pv)) % 1
        x = px + 0.015 * torch.sin(t * 0.3 + ph * 6)
        keep = ~((y > 0.36) & (y < 0.64))
        g = 18 * torch.exp(-(((xx[None] - x[keep, None, None]) * self.sw) ** 2
                              + ((yy[None] - y[keep, None, None]) * self.sh) ** 2) / 6)
        img = img + g.sum(0)
        return F.interpolate(img.clamp(0, 255)[None], size=(M.PH, M.PW), mode="bilinear", align_corners=False)[0].to(self.dt)

    # ---- fotos
    def photo_at(self, p, a, b, t):
        im = self.photos[p]
        H0, W0 = im.shape[1:]
        if self.S.get("visual_dinamico"):
            x0, y0, x1, y1 = M._camera_crop(W0, H0, p, a, b, t, self.S.get("motion_seed", 0))
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            cw, ch = x1 - x0, y1 - y0
        else:
            pr = min(max((t - a) / (b - a), 0), 1); z = 1 + 0.12 * pr
            cw, ch = M.PW * 1.12 / z, M.PH * 1.12 / z
            cx = W0 / 2 + (pr - 0.5) * 30 * (1 if p % 2 else -1); cy = H0 / 2
        # recorte sub-píxel con grid_sample (zoom suave)
        gx = torch.linspace(cx - cw / 2, cx + cw / 2, M.PW, device=self.d) / (W0 - 1) * 2 - 1
        gy = torch.linspace(cy - ch / 2, cy + ch / 2, M.PH, device=self.d) / (H0 - 1) * 2 - 1
        gyy, gxx = torch.meshgrid(gy, gx, indexing="ij")
        grid = torch.stack([gxx, gyy], -1)[None].to(self.dt)   # coordenadas en fp32 (sin temblor), muestreo en fp16
        return F.grid_sample(im[None], grid, mode="bilinear", align_corners=True)[0]

    def photo_layer(self, t):
        spans = self.S["spans"]
        for n, (p, a, b) in enumerate(spans):
            if a <= t < b:
                ph = self.photo_at(p, a, b, t)
                dt = t - a
                if self.S.get("visual_dinamico") and n and 0 <= dt < 0.14:
                    pulse = (1 - dt / 0.14) ** 2
                    accent = torch.tensor(M.TPL.get("resalte", (180, 200, 255)), dtype=self.dt, device=self.d)[:, None, None]
                    ph = ph * (1 + 0.06 * pulse) + accent * (0.035 * pulse)
                return ph
        p, a, b = min(spans, key=lambda span: min(abs(t - span[1]), abs(t - span[2])))
        return self.photo_at(p, a, b, t)

    # ---- subtítulos
    def sprite(self, i):
        if i not in self.sprites:
            import extras as X
            with X._LOCK:                       # la fuente no se comparte entre hilos a la vez
                spr, bb = M.sub_sprite(self.S["subs"][i][2])
            a = torch.tensor(np.asarray(spr), dtype=self.dt, device=self.d).permute(2, 0, 1) / 255
            self.sprites[i] = (a, bb)
        return self.sprites[i]

    def paste(self, frame, spr, x, y, alpha):
        _, h, w = spr.shape
        x0, y0 = max(x, 0), max(y, 0); x1, y1 = min(x + w, M.W), min(y + h, M.H)
        if x1 <= x0 or y1 <= y0: return
        s = spr[:, y0 - y:y1 - y, x0 - x:x1 - x]
        a = s[3:4] * alpha
        region = frame[:, y0:y1, x0:x1]
        frame[:, y0:y1, x0:x1] = region * (1 - a) + s[:3] * 255 * a

    @torch.inference_mode()
    def gpu(self, n):
        """Etapa GPU: fondo + fotos + zoom + subtítulos. Devuelve el fotograma como array uint8 (H×W×3)."""
        t = n / M.FPS
        if self.video_bg_frames:
            idx = int(t * self.video_bg_fps) % len(self.video_bg_frames)
            if idx != self.video_bg_index:
                with Image.open(self.video_bg_frames[idx]) as frame:
                    arr = np.asarray(frame.convert("RGB"), dtype=np.uint8).copy()
                self.video_bg_image = torch.tensor(arr, dtype=self.dt, device=self.d).permute(2, 0, 1).contiguous()
                self.video_bg_index = idx
            ph = self.video_bg_image * 0.78
            tint = F.interpolate(ph[None], size=(M.PH, M.PW), mode="bilinear", align_corners=False)[0] * self.band
        else:
            g = self.background(t)
            ph = self.photo_layer(t); lum = ph.mean(0, keepdim=True)
            # M.PESO_FOTO es la constante compartida con make_short.py (ruta CPU). Antes esta
            # linea llevaba un 0.7 duplicado a mano: si se tocaba una ruta y no la otra, el
            # render GPU y el CPU daban videos distintos.
            tint = (0.62 * g * (0.45 + 1.2 * lum / 255) + 0.42 * ph * M.PESO_FOTO) * self.band
        import extras as X
        z = X.zoom_at(t, self.S.get("punches", []))
        if z > 1.001:     # zoom rápido en los giros
            h0, w0 = tint.shape[1:]
            ch, cw = int(h0 / z), int(w0 / z)
            y0, x0 = (h0 - ch) // 2, (w0 - cw) // 2
            tint = tint[:, y0:y0 + ch, x0:x0 + cw]
        frame = F.interpolate(tint.clamp(0, 255)[None], size=(M.H, M.W), mode="bicubic", align_corners=False)[0]
        for i, sub in enumerate(self.S["subs"]):
            a, b = sub[0], sub[1]
            if not (a <= t < b): continue
            al, sc, dy, pin, pout = M.entrada(t, a, b)
            if al <= 0.01: continue
            spr, (x0, y0, x1, y1) = self.sprite(i)
            h, w = int(spr.shape[1] * sc), int(spr.shape[2] * sc)
            sp = F.interpolate(spr[None], size=(h, w), mode="bilinear", align_corners=False)[0]
            self.paste(frame, sp, int((x0 + x1) / 2 - w / 2), int((y0 + y1) / 2 + dy - h / 2), al)
        out = frame.clamp(0, 255).round().to(torch.uint8).permute(1, 2, 0).contiguous()
        return t, out.cpu().numpy()

    def cpu(self, t, arr):
        """Etapa CPU (se ejecuta en hilos, en paralelo con la GPU): karaoke, tarjeta, encuesta, barra."""
        import extras as X
        activos = [i for i, sub in enumerate(self.S["subs"]) if sub[0] <= t < sub[1]]
        img = Image.fromarray(arr).convert("RGBA")
        for i in activos:
            M._karaoke(img, t, i, self.S)
        X.apply(img, t, self.S, self.S.setdefault("xcache", {}))
        aviso = self.S["aviso"]
        if aviso and t < 3.2:   # texto pequeño de 3 s
            from PIL import ImageDraw
            al = min(1, t / 0.3, (3.2 - t) / 0.4)
            with X._LOCK:
                d = ImageDraw.Draw(img); tw = M.FONT_SMALL.getlength(aviso)
                d.text(((M.W - tw) / 2, 1560), aviso, font=M.FONT_SMALL, fill=(255, 255, 255, int(220 * al)),
                       stroke_width=3, stroke_fill=(0, 0, 0, int(200 * al)))
        return img.convert("RGB").tobytes()

    def __call__(self, n):
        return self.cpu(*self.gpu(n))
