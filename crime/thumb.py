"""Episode thumbnail 1280x720: python crime/thumb.py PICTURE OUT "EPISODE 2" "LINE1" "LINE2" "SUB"
Left dark panel with text, comic picture on the right (same look as the episode 1 thumbnail)."""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
pic, out, tag, l1, l2, sub = sys.argv[1:7]
TAMIL = "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"; SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
W, H = 1280, 720
src = Image.open(pic).convert("RGB").resize((W, H))
bg = src.filter(ImageFilter.GaussianBlur(30)).point(lambda v: int(v * 0.35))
im = bg.copy(); d = ImageDraw.Draw(im)
for x in range(0, 570):                                    # fade the left panel to near black
    a = int(235 * (1 - x / 760)); d.line([(x, 0), (x, H)], fill=(8, 8, 14))
im = Image.blend(bg, im, 0.78); 
im.paste(src.crop((400, 0, 1110, H)), (570, 0)); d = ImageDraw.Draw(im)
d.rectangle((570, 0, 574, H), fill=(255, 255, 255))
def font(p, s): return ImageFont.truetype(p, s)
def fit(text, p, size, maxw):
    while font(p, size).getlength(text) > maxw: size -= 4
    return font(p, size)
d.rounded_rectangle((50, 50, 330, 120), 14, fill=(255, 214, 51)); d.text((190, 85), tag, font=font(SANS, 36), fill=(20, 20, 20), anchor="mm")
f1 = fit(l1, TAMIL, 120, 500); d.text((50, 130), l1, font=f1, fill="white", stroke_width=7, stroke_fill="black")
f2 = fit(l2, TAMIL, 150, 500); d.text((50, 290), l2, font=f2, fill=(255, 214, 51), stroke_width=7, stroke_fill="black")
d.text((50, 520), sub, font=fit(sub, TAMIL, 44, 520), fill=(150, 225, 240))
d.rounded_rectangle((50, 640, 610, 690), 10, fill=(10, 10, 20)); d.text((330, 665), "SOLVED CRIME FILES - TAMIL", font=font(SANS, 28), fill=(255, 214, 51), anchor="mm")
im.save(out, quality=92)
