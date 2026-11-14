"""Channel art for 'க்ளோஸ்டு ஃபைல்ஸ் தமிழ்' (Closed Files Tamil): logo (a case folder stamped CLOSED) and banner. Writes out/*.png."""
import math, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features

TA = os.environ.get("TA_FONT") or "/usr/share/fonts/truetype/noto/NotoSansTamil-Bold.ttf"
EN = os.environ.get("EN_FONT") or "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
NAME, LINE = "க்ளோஸ்டு ஃபைல்ஸ் தமிழ்", "தீர்ப்பு வந்த உண்மை வழக்குகள் · துப்பறிந்த விதம்"
BG, BG2, FOLD, FOLD2, RED, INK, CREAM, YEL = (13, 17, 24), (28, 36, 50), (232, 180, 76), (196, 142, 48), (214, 40, 40), (22, 26, 34), (240, 232, 214), (255, 200, 40)
os.makedirs("out", exist_ok=True)
print("raqm (needed for Tamil letters):", features.check("raqm"))
def font(p, s): return ImageFont.truetype(p, s, layout_engine=ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC)

def backdrop(w, h):
    im = Image.new("RGB", (w, h), BG); d = ImageDraw.Draw(im)
    for i in range(60, 0, -1):      # soft glow in the middle
        f = i / 60; c = tuple(int(BG[k] + (BG2[k] - BG[k]) * (1 - f) ** 2) for k in range(3))
        d.ellipse([w / 2 - w * 0.75 * f, h / 2 - h * 0.9 * f, w / 2 + w * 0.75 * f, h / 2 + h * 0.9 * f], fill=c)
    return im

def stamp(text, size, color=RED, pad=0.32):
    """A rubber stamp: bold text in a double-line box, slightly worn."""
    f = font(EN, size); l, t, r, b = f.getbbox(text); tw, th = r - l, b - t; p = int(size * pad); lw = max(4, size // 9)
    W, Hh = tw + 2 * p + 4 * lw, th + 2 * p + 4 * lw
    im = Image.new("RGBA", (W, Hh), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([lw // 2, lw // 2, W - lw // 2, Hh - lw // 2], radius=size // 5, outline=color, width=lw)
    d.rounded_rectangle([lw * 2, lw * 2, W - lw * 2, Hh - lw * 2], radius=size // 7, outline=color, width=max(2, lw // 3))
    d.text(((W - tw) / 2 - l, (Hh - th) / 2 - t), text, font=f, fill=color)
    return im

def folder(S):
    """A closed case folder with a tab, a red tape band and a label, drawn on a transparent square of side S."""
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x0, x1, y0, y1 = S * 0.10, S * 0.90, S * 0.24, S * 0.84; r = S * 0.045
    d.rounded_rectangle([x0, y0 - S * 0.09, x0 + S * 0.36, y0 + S * 0.06], radius=r, fill=FOLD2)            # tab (back sheet)
    d.rounded_rectangle([x0, y0 - S * 0.02, x1, y1], radius=r, fill=FOLD2)                                    # back sheet
    d.rounded_rectangle([x0 + S * 0.03, y0 + S * 0.005, x1 - S * 0.03, y1 - S * 0.03], radius=r * 0.5, fill=CREAM)   # papers peeking out
    d.rounded_rectangle([x0, y0 + S * 0.05, x1, y1], radius=r, fill=FOLD)                                     # front cover
    d.rectangle([x0, y0 + S * 0.30, x1, y0 + S * 0.335], fill=FOLD2)                                          # darker band across the cover
    d.rounded_rectangle([x0 + S * 0.07, y0 + S * 0.115, x0 + S * 0.47, y0 + S * 0.245], radius=r * 0.4, fill=CREAM)   # label
    for k in range(2): d.rounded_rectangle([x0 + S * 0.10, y0 + S * (0.148 + k * 0.045), x0 + S * (0.42 - k * 0.1), y0 + S * (0.166 + k * 0.045)], radius=4, fill=INK)
    return im

def logo(S=1600):
    im = backdrop(S, S).convert("RGBA")
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0)); f = folder(int(S * 0.74)).rotate(-6, resample=Image.BICUBIC, expand=False)
    pos = (int(S * 0.13), int(S * 0.10))
    shadow = Image.new("RGBA", f.size, (0, 0, 0, 0)); shadow.paste((0, 0, 0, 150), (0, 0), f.split()[3]); sh.paste(shadow, (pos[0] + 14, pos[1] + 22), shadow)
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(18))); im.paste(f, pos, f)
    st = stamp("CLOSED", int(S * 0.125)).rotate(-16, resample=Image.BICUBIC, expand=True)
    im.paste(st, (int(S * 0.5 - st.width / 2 + S * 0.03), int(S * 0.60 - st.height / 2)), st)
    return im.convert("RGB").resize((800, 800), Image.LANCZOS)

L = logo(); L.save("out/logo.png")
m = Image.new("L", (800, 800), 0); ImageDraw.Draw(m).ellipse([0, 0, 799, 799], fill=255)
pv = Image.new("RGB", (800, 800), (255, 255, 255)); pv.paste(L, (0, 0), m); pv.save("out/logo_round_preview.png")
small = Image.new("RGB", (360, 120), (255, 255, 255))
for k, s in enumerate((98, 64, 36)):      # how it reads at the sizes YouTube shows it
    t = pv.resize((s, s), Image.LANCZOS); small.paste(t, (20 + k * 120, (120 - s) // 2))
small.save("out/logo_small_sizes.png")

# ---- banner 2560x1440; everything that matters sits inside the middle 1546x423 (what phones show)
W, H = 2560, 1440; sx0, sy0, sw, sh_ = (W - 1546) // 2, (H - 423) // 2, 1546, 423
b = backdrop(W, H).convert("RGBA")
ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
for k in range(-4, 44):      # faint diagonal case-file stripes across the whole banner (TV crop)
    x = k * 70; od.line([x, H, x + 520, 0], fill=(255, 255, 255, 9), width=22)
b = Image.alpha_composite(b, ov); d = ImageDraw.Draw(b)
mark = folder(330).rotate(-6, resample=Image.BICUBIC); b.paste(mark, (sx0 + 6, sy0 + 44), mark)
fn = font(TA, 132); l, t, r, bb = fn.getbbox(NAME)
if r - l > sw - 380: fn = font(TA, int(132 * (sw - 380) / (r - l))); l, t, r, bb = fn.getbbox(NAME)
tx = sx0 + 350; d.text((tx - l, sy0 + 88 - t), NAME, font=fn, fill=CREAM)
d.rectangle([tx, sy0 + 88 + (bb - t) + 28, tx + 150, sy0 + 88 + (bb - t) + 38], fill=YEL)
parts = [x.strip() for x in LINE.split("·")]; gap = 46      # the Tamil font has no middle-dot letter, so the dot is drawn
size = 52
while True:
    fl = font(TA, size); ws = [fl.getbbox(x) for x in parts]; total = sum(w[2] - w[0] for w in ws) + gap * (len(parts) - 1)
    if total <= sw - 380 - 60 or size <= 30: break
    size -= 2
x = tx; y = sy0 + 88 + (bb - t) + 62
for k, (txt, w) in enumerate(zip(parts, ws)):
    d.text((x - w[0], y - min(v[1] for v in ws)), txt, font=fl, fill=YEL); x += w[2] - w[0]
    if k + 1 < len(parts): cy = y + size * 0.5; d.ellipse([x + gap / 2 - 6, cy - 6, x + gap / 2 + 6, cy + 6], fill=YEL); x += gap
st = stamp("CASE CLOSED", 40).rotate(-7, resample=Image.BICUBIC, expand=True); b.paste(st, (sx0 + sw - st.width - 10, sy0 + sh_ - st.height + 4), st)
b = b.convert("RGB"); b.save("out/banner.png")
b.crop((sx0, sy0, sx0 + sw, sy0 + sh_)).save("out/banner_phone_preview.png")
print("done")
