"""Channel intro for the crime channel: the 10 s title clip (assets/crime_intro_clip.mp4, made in Gemini, no text in it), then the channel
name written over the closed case folder and a 3 s 'EPISODE n' card, spliced into a built story video right after the hook.
Used by build.py:  splice(main_video, split_second, out_video, episode_dict). The episode dict: {"num": 1, "title": "THE ALAVANDAR CASE", "sub": "MADRAS | 1952"}"""
import os, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1280, 720, 30
CLIP = os.environ.get("INTRO_CLIP") or "assets/crime_intro_clip.mp4"
LAND, CARD = 6.4, 3.0        # second at which the folder has landed and the name fades in; length of the episode card

def _font(size):
    for p in ("/usr/share/fonts/truetype/noto/NotoSans-Black.ttf", "/usr/share/fonts/truetype/noto/NotoSans-ExtraBold.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(p): return ImageFont.truetype(p, size)
    raise SystemExit("no bold font found for the intro")

def _text(img, xy, text, size, fill):
    f = _font(size); lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).text(xy, text, font=f, fill=(0, 0, 0, 230), anchor="mm", stroke_width=10, stroke_fill=(0, 0, 0, 230))
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(6)))
    ImageDraw.Draw(img).text(xy, text, font=f, fill=fill, anchor="mm", stroke_width=3, stroke_fill=(20, 10, 5, 255))

def make_art(ep, work):
    t = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _text(t, (W // 2, 300), "SOLVED", 110, (255, 214, 64, 255)); _text(t, (W // 2, 410), "CRIME FILES", 110, (255, 255, 255, 255))
    _text(t, (W // 2, 500), "- TAMIL -", 52, (120, 220, 230, 255)); t.save(f"{work}/intro_title.png")
    c = Image.new("RGBA", (W, H), (10, 8, 18, 255))
    _text(c, (W // 2, 300), f"EPISODE {ep['num']}", 120, (255, 214, 64, 255))
    ImageDraw.Draw(c).rectangle((W // 2 - 260, 372, W // 2 + 260, 376), fill=(120, 220, 230, 255))
    _text(c, (W // 2, 450), ep["title"], 58, (255, 255, 255, 255)); _text(c, (W // 2, 525), ep.get("sub", ""), 40, (190, 190, 200, 255))
    c.convert("RGB").save(f"{work}/intro_card.png")

def splice(main, split, out, ep, work="work"):
    make_art(ep, work)
    intro = f"{work}/intro.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", CLIP, "-loop", "1", "-t", str(CARD), "-i", f"{work}/intro_card.png", "-loop", "1", "-t", "4", "-i", f"{work}/intro_title.png",
        "-filter_complex",
        f"[0:v]delogo=x=1132:y=572:w=62:h=62,fps={FPS},format=yuv420p[a];[2:v]format=rgba,fade=t=in:st=0:d=0.7:alpha=1,setpts=PTS+{LAND}/TB[t];"
        f"[a][t]overlay=0:0:eof_action=pass,format=yuv420p[v1];[1:v]fps={FPS},format=yuv420p,fade=t=in:st=0:d=0.4,fade=t=out:st={CARD - 0.5}:d=0.5[c];[v1][c]concat=n=2:v=1:a=0[v];"
        f"[0:a]aresample=44100,loudnorm=I=-18:TP=-1.5:LRA=9,afade=t=out:st=9:d=1,apad=pad_dur={CARD},aformat=channel_layouts=stereo[au]",
        "-map", "[v]", "-map", "[au]", "-t", f"{10 + CARD}", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-ar", "44100", "-pix_fmt", "yuv420p", intro], check=True)
    enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-r", str(FPS), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2"]
    parts = []
    fades = [f"afade=t=out:st={max(0, split - 0.35):.3f}:d=0.35", "afade=t=in:st=0:d=0.15", "afade=t=in:st=0:d=0.5"]      # the music must not be cut off or start abruptly at the seams
    for k, (src, a) in enumerate([(main, ["-t", f"{split:.3f}"]), (intro, []), (main, ["-ss", f"{split:.3f}"])]):
        f = f"{work}/seg{k}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *(["-ss", a[1]] if a[:1] == ["-ss"] else []), "-i", src, *(a if a[:1] == ["-t"] else []), "-af", fades[k], *enc, f], check=True); parts.append(f)
    open(f"{work}/segs.txt", "w").write("".join(f"file '{os.path.abspath(f)}'\n" for f in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{work}/segs.txt", "-c", "copy", "-movflags", "+faststart", out], check=True)

if __name__ == "__main__":
    import sys
    splice(sys.argv[1], float(sys.argv[2]), sys.argv[3], {"num": 1, "title": "THE ALAVANDAR CASE", "sub": "MADRAS | 1952"}, work=sys.argv[4] if len(sys.argv) > 4 else "work")
