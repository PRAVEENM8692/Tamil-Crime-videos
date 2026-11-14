"""Episode thumbnail 1280x720: python crime/thumb.py PICTURE OUT "EPISODE 2" "LINE1" "LINE2" "SUB" [LAYOUT A|B|C|D]
Four different looks so each episode's thumbnail is new: A dark left panel, B full picture + bottom band,
C red frame + top headline, D yellow right panel. Default layout = episode number cycle (1->A, 2->B, 3->C, 4->D, 5->A ...)."""
import sys, re
from PIL import Image, ImageDraw, ImageFont, ImageFilter
pic, out, tag, l1, l2, sub = sys.argv[1:7]
TAMIL = "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H = 1280, 720
num = int((re.findall(r"\d+", tag) or ["1"])[0])
layout = (sys.argv[7] if len(sys.argv) > 7 else "ABCD"[(num - 1) % 4]).upper()
src = Image.open(pic).convert("RGB")
if src.width < src.height * 1.5: src = src.resize((W, W)).crop((0, (W - H) // 2, W, (W - H) // 2 + H))   # old square picture
else: src = src.crop((14, 14, src.width - 14, src.height - 14)).resize((W, H))
def font(p, s): return ImageFont.truetype(p, s)
def fit(text, p, size, maxw):
    while font(p, size).getlength(text) > maxw: size -= 4
    return font(p, size)
YEL = (255, 214, 51)
def badge(d, x, y, fill=(10, 10, 20), fg=YEL):
    d.rounded_rectangle((x, y, x + 560, y + 50), 10, fill=fill); d.text((x + 280, y + 25), "SOLVED CRIME FILES - TAMIL", font=font(SANS, 28), fill=fg, anchor="mm")
def tagbox(d, x, y, fill=YEL, fg=(20, 20, 20)):
    d.rounded_rectangle((x, y, x + 280, y + 70), 14, fill=fill); d.text((x + 140, y + 35), tag, font=font(SANS, 36), fill=fg, anchor="mm")
if layout == "A":
    bg = src.filter(ImageFilter.GaussianBlur(30)).point(lambda v: int(v * 0.35)); im = bg.copy(); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 569, H), fill=(8, 8, 14)); im = Image.blend(bg, im, 0.78)
    im.paste(src.crop((400, 0, 1110, H)), (570, 0)); d = ImageDraw.Draw(im); d.rectangle((570, 0, 574, H), fill="white")
    tagbox(d, 50, 50)
    d.text((50, 130), l1, font=fit(l1, TAMIL, 120, 500), fill="white", stroke_width=7, stroke_fill="black")
    d.text((50, 290), l2, font=fit(l2, TAMIL, 150, 500), fill=YEL, stroke_width=7, stroke_fill="black")
    d.text((50, 520), sub, font=fit(sub, TAMIL, 44, 520), fill=(150, 225, 240)); badge(d, 50, 640)
elif layout == "B":
    im = src.copy(); sh = Image.new("L", (1, H))
    for y in range(H): sh.putpixel((0, y), 0 if y < 330 else int(235 * ((y - 330) / (H - 330)) ** 1.3))
    im.paste(Image.new("RGB", (W, H), (6, 6, 12)), (0, 0), sh.resize((W, H))); d = ImageDraw.Draw(im)
    tagbox(d, 40, 40, fill=(215, 25, 32), fg="white")
    d.text((50, 410), l1 + " " + l2, font=fit(l1 + " " + l2, TAMIL, 150, 1180), fill="white", stroke_width=8, stroke_fill="black")
    d.text((50, 600), sub, font=fit(sub, TAMIL, 50, 700), fill=YEL, stroke_width=3, stroke_fill="black"); badge(d, 690, 640)
elif layout == "C":
    im = Image.new("RGB", (W, H), (150, 18, 24)); d = ImageDraw.Draw(im)
    box = src.crop((120, 0, 1280, H)).resize((870, 540)); im.paste(box, (370, 150)); d.rectangle((370, 150, 1239, 689), outline="white", width=6)
    d.text((40, 20), l1 + " " + l2, font=fit(l1 + " " + l2, TAMIL, 125, 1200), fill="white", stroke_width=6, stroke_fill=(40, 0, 0))
    tagbox(d, 40, 170); d.text((40, 270), sub, font=fit(sub, TAMIL, 50, 300), fill=YEL)
    d.rounded_rectangle((40, 560, 340, 690), 12, fill=(10, 10, 20)); d.text((190, 598), "SOLVED", font=font(SANS, 36), fill=YEL, anchor="mm"); d.text((190, 645), "CRIME FILES", font=font(SANS, 30), fill="white", anchor="mm")
else:
    im = Image.new("RGB", (W, H), YEL); d = ImageDraw.Draw(im)
    im.paste(src.crop((0, 0, 780, H)), (0, 0)); d = ImageDraw.Draw(im); d.polygon([(780, 0), (860, 0), (780, H), (700, H)], fill=(10, 10, 14))
    d.rounded_rectangle((820, 40, 1240, 110), 14, fill=(10, 10, 14)); d.text((1030, 75), tag, font=font(SANS, 38), fill=YEL, anchor="mm")
    d.text((830, 160), l1, font=fit(l1, TAMIL, 110, 430), fill=(10, 10, 14))
    d.text((830, 300), l2, font=fit(l2, TAMIL, 130, 430), fill=(180, 20, 28), stroke_width=2, stroke_fill=(10, 10, 14))
    d.text((830, 480), sub, font=fit(sub, TAMIL, 44, 420), fill=(10, 10, 14))
    d.rounded_rectangle((820, 620, 1250, 690), 10, fill=(10, 10, 14)); d.text((1035, 655), "SOLVED CRIME FILES", font=font(SANS, 28), fill=YEL, anchor="mm")
im.save(out, quality=92)
