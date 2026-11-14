"""Channel art for 'சால்வ்டு ஃபைல்ஸ் தமிழ்' (Solved Files Tamil): logo (a case folder stamped SOLVED, with a green tick) and banner.
Colourful but tidy: violet-to-blue background, amber folder, red stamp, green tick, yellow accents. Writes out/*.png."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features

TA = os.environ.get("TA_FONT") or "/usr/share/fonts/truetype/noto/NotoSansTamil-Bold.ttf"
EN = os.environ.get("EN_FONT") or "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W1, W2 = "சால்வ்டு", "ஃபைல்ஸ் தமிழ்"
LINE = "தீர்ப்பு வந்த உண்மை வழக்குகள் · துப்பறிந்த விதம்"
C_A, C_B, C_C = (76, 29, 149), (30, 64, 175), (13, 148, 136)        # violet -> blue -> teal
FOLD, FOLD2, FOLD3 = (255, 196, 46), (245, 158, 11), (217, 119, 6)
RED, GREEN, INK, CREAM, YEL, WHITE = (225, 29, 72), (34, 197, 94), (17, 24, 39), (255, 247, 230), (253, 224, 71), (255, 255, 255)
os.makedirs("out", exist_ok=True)
RAQM = features.check("raqm"); print("raqm (needed for Tamil letters):", RAQM)
def font(p, s): return ImageFont.truetype(p, s, layout_engine=ImageFont.Layout.RAQM if RAQM else ImageFont.Layout.BASIC)
def mix(a, b, f): return tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))

def gradient(w, h, stops, diag=0.35):
    """Left-to-right colour blend with a slight diagonal lean."""
    small = Image.new("RGB", (256, 64)); px = small.load(); n = len(stops) - 1
    for x in range(256):
        for y in range(64):
            f = min(1, max(0, x / 255 + diag * (y / 63 - 0.5))) * n; i = min(n - 1, int(f)); px[x, y] = mix(stops[i], stops[i + 1], f - i)
    return small.resize((w, h), Image.BICUBIC)

def glow(im, cx, cy, r, color, alpha):
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(ov).ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (alpha,))
    return Image.alpha_composite(im, ov.filter(ImageFilter.GaussianBlur(r * 0.45)))

def stamp(text, size, color=RED, bg=WHITE):
    """A rubber stamp: bold text in a double-line box on a white plate, so it reads on any colour."""
    f = font(EN, size); l, t, r, b = f.getbbox(text); tw, th = r - l, b - t; p = int(size * 0.30); lw = max(4, size // 9)
    Wd, Hh = tw + 2 * p + 4 * lw, th + 2 * p + 4 * lw
    im = Image.new("RGBA", (Wd, Hh), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, Wd - 1, Hh - 1], radius=size // 4, fill=bg + (255,))
    d.rounded_rectangle([lw // 2, lw // 2, Wd - lw // 2, Hh - lw // 2], radius=size // 5, outline=color, width=lw)
    d.rounded_rectangle([lw * 2, lw * 2, Wd - lw * 2, Hh - lw * 2], radius=size // 7, outline=color, width=max(2, lw // 3))
    d.text(((Wd - tw) / 2 - l, (Hh - th) / 2 - t), text, font=f, fill=color)
    return im

def tick(S):
    """A green badge with a white tick."""
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=WHITE); d.ellipse([S * 0.07, S * 0.07, S * 0.93, S * 0.93], fill=GREEN)
    d.line([S * 0.28, S * 0.52, S * 0.44, S * 0.68, S * 0.73, S * 0.35], fill=WHITE, width=int(S * 0.12), joint="curve")
    for x, y in ((0.28, 0.52), (0.73, 0.35)): d.ellipse([S * x - S * 0.06, S * y - S * 0.06, S * x + S * 0.06, S * y + S * 0.06], fill=WHITE)
    return im

def folder(S):
    """A case folder with a tab, papers peeking out and a label, on a transparent square of side S."""
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x0, x1, y0, y1 = S * 0.10, S * 0.90, S * 0.24, S * 0.84; r = S * 0.05
    d.rounded_rectangle([x0, y0 - S * 0.09, x0 + S * 0.36, y0 + S * 0.06], radius=r, fill=FOLD3)
    d.rounded_rectangle([x0, y0 - S * 0.02, x1, y1], radius=r, fill=FOLD3)
    d.rounded_rectangle([x0 + S * 0.03, y0 + S * 0.005, x1 - S * 0.03, y1 - S * 0.03], radius=r * 0.5, fill=CREAM)
    d.rounded_rectangle([x0 + S * 0.05, y0 + S * 0.03, x1 - S * 0.06, y1 - S * 0.03], radius=r * 0.5, fill=WHITE)
    front = gradient(int(x1 - x0), int(y1 - y0 - S * 0.05), [FOLD, FOLD2], diag=0.9)
    mk = Image.new("L", front.size, 0); ImageDraw.Draw(mk).rounded_rectangle([0, 0, front.width - 1, front.height - 1], radius=int(r), fill=255)
    im.paste(front, (int(x0), int(y0 + S * 0.05)), mk); d = ImageDraw.Draw(im)
    d.rounded_rectangle([x0 + S * 0.07, y0 + S * 0.115, x0 + S * 0.47, y0 + S * 0.245], radius=r * 0.4, fill=WHITE)
    for k in range(2): d.rounded_rectangle([x0 + S * 0.10, y0 + S * (0.148 + k * 0.045), x0 + S * (0.42 - k * 0.1), y0 + S * (0.166 + k * 0.045)], radius=4, fill=INK)
    return im

def drop(im, layer, pos, blur=16, off=(10, 18), alpha=120):
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); s = Image.new("RGBA", layer.size, (0, 0, 0, 0)); s.paste((0, 0, 0, alpha), (0, 0), layer.split()[3])
    sh.paste(s, (pos[0] + off[0], pos[1] + off[1]), s); im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(blur))); im.paste(layer, pos, layer); return im

def logo(S=1600):
    im = gradient(S, S, [C_A, C_B, C_C], diag=1.0).convert("RGBA")
    im = glow(im, S * 0.5, S * 0.46, S * 0.42, (255, 255, 255), 46)
    f = folder(int(S * 0.72)).rotate(-6, resample=Image.BICUBIC); im = drop(im, f, (int(S * 0.14), int(S * 0.09)), blur=22)
    st = stamp("SOLVED", int(S * 0.12)).rotate(-14, resample=Image.BICUBIC, expand=True)
    im = drop(im, st, (int(S * 0.52 - st.width / 2), int(S * 0.61 - st.height / 2)), blur=12, off=(6, 10), alpha=110)
    tk = tick(int(S * 0.22)); im = drop(im, tk, (int(S * 0.63), int(S * 0.16)), blur=12, off=(6, 10), alpha=110)
    return im.convert("RGB").resize((800, 800), Image.LANCZOS)

L = logo(); L.save("out/logo.png")
m = Image.new("L", (800, 800), 0); ImageDraw.Draw(m).ellipse([0, 0, 799, 799], fill=255)
pv = Image.new("RGB", (800, 800), (255, 255, 255)); pv.paste(L, (0, 0), m); pv.save("out/logo_round_preview.png")
small = Image.new("RGB", (360, 120), (255, 255, 255))
for k, s in enumerate((98, 64, 36)): small.paste(pv.resize((s, s), Image.LANCZOS), (20 + k * 120, (120 - s) // 2))
small.save("out/logo_small_sizes.png")

# ---- banner 2560x1440; everything that matters sits inside the middle 1546x423 (what phones show)
W, H = 2560, 1440; sx0, sy0, sw, sh_ = (W - 1546) // 2, (H - 423) // 2, 1546, 423
b = gradient(W, H, [C_A, C_B, C_C], diag=0.5).convert("RGBA")
b = glow(b, sx0 + 170, H / 2, 330, (255, 255, 255), 40); b = glow(b, W * 0.86, H * 0.2, 420, (253, 224, 71), 26); b = glow(b, W * 0.1, H * 0.85, 420, (225, 29, 72), 30)
ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
for k in range(-6, 60):      # faint diagonal stripes
    x = k * 90; od.line([x, H, x + 520, 0], fill=(255, 255, 255, 10), width=26)
b = Image.alpha_composite(b, ov)
mark = folder(340).rotate(-6, resample=Image.BICUBIC); b = drop(b, mark, (sx0 - 6, sy0 + 34), blur=14)
tk = tick(96); b = drop(b, tk, (sx0 + 228, sy0 + 66), blur=8, off=(4, 6), alpha=100)
d = ImageDraw.Draw(b); tx = sx0 + 350; avail = sw - 350 - 10
size = 128
while True:      # the name on one line: first word in yellow, the rest in white
    fn = font(TA, size); b1, b2 = fn.getbbox(W1), fn.getbbox(W2); sp = int(size * 0.28); total = (b1[2] - b1[0]) + sp + (b2[2] - b2[0])
    if total <= avail or size <= 60: break
    size -= 4
top = min(b1[1], b2[1]); bot = max(b1[3], b2[3]); ny = sy0 + 76
d.text((tx - b1[0] + 4, ny - top + 5), W1, font=fn, fill=(0, 0, 0, 90)); d.text((tx + (b1[2] - b1[0]) + sp - b2[0] + 4, ny - top + 5), W2, font=fn, fill=(0, 0, 0, 90))
d.text((tx - b1[0], ny - top), W1, font=fn, fill=YEL); d.text((tx + (b1[2] - b1[0]) + sp - b2[0], ny - top), W2, font=fn, fill=WHITE)
uy = ny + (bot - top) + 26; d.rounded_rectangle([tx, uy, tx + 170, uy + 12], radius=6, fill=GREEN)
parts = [x.strip() for x in LINE.split("·")]; gap = 46; size2 = 50      # the Tamil font has no middle-dot letter, so the dot is drawn
while True:
    fl = font(TA, size2); ws = [fl.getbbox(x) for x in parts]; tot = sum(w[2] - w[0] for w in ws) + gap * (len(parts) - 1)
    if tot <= avail - 60 or size2 <= 30: break
    size2 -= 2
x = tx; y = uy + 40
for k, (txt, w) in enumerate(zip(parts, ws)):
    d.text((x - w[0], y - min(v[1] for v in ws)), txt, font=fl, fill=CREAM); x += w[2] - w[0]
    if k + 1 < len(parts): cy = y + size2 * 0.5; d.ellipse([x + gap / 2 - 7, cy - 7, x + gap / 2 + 7, cy + 7], fill=YEL); x += gap
st = stamp("CASE SOLVED", 38).rotate(-6, resample=Image.BICUBIC, expand=True); b = drop(b, st, (sx0 + sw - st.width - 12, sy0 + sh_ - st.height - 2), blur=8, off=(4, 6), alpha=100)
b = b.convert("RGB"); b.save("out/banner.png")
b.crop((sx0, sy0, sx0 + sw, sy0 + sh_)).save("out/banner_phone_preview.png")
print("done")
