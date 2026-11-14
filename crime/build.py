"""Tamil crime story channel: put a story video together from the pictures, the narration and the background music.
Inputs (folders): PICS (NN.jpg), VOICE (NN_name.mp3 per script section), script + plan in crime/<NAME>/. Output: out/<NAME>.mp4 (1280x720).
On-screen tags (names, dates, places, clue list, verdict) are drawn with libass, timed from where their cue words fall in the script."""
import json, os, re, subprocess, sys
from PIL import Image, ImageFilter

NAME = os.environ.get("NAME") or "alavandar"
D = f"crime/{NAME}"
PICS, VOICE = os.environ.get("PICS") or "pics", os.environ.get("VOICE") or "voice"
BGM = os.environ.get("BGM") or "assets/crime_bgm.mp3"
FONT = os.environ.get("FONT") or "Noto Sans Tamil"
W, H, FPS, GAP = 1280, 720, 30, 0.45      # GAP = silence between script sections
WORK = "work"; os.makedirs(WORK, exist_ok=True); os.makedirs("out", exist_ok=True)

def run(*a): subprocess.run(list(a), check=True)
def dur(f): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout)

secs = [(m.group(1), m.group(2).strip().replace(" ", "_"), m.group(3).strip())
        for m in re.finditer(r"^## (\d+) ([^\n]*)\n(.*?)(?=^## |\Z)", open(f"{D}/script.txt", encoding="utf-8").read(), re.S | re.M)]
plan = json.load(open(f"{D}/plan.json", encoding="utf-8"))

# ---- timing: where each section starts, and where a cue phrase falls inside it (by its position in the text)
start, t = {}, 0.0
for num, name, text in secs:
    f = f"{VOICE}/{num}_{name}.mp3"; d = dur(f); start[num] = (t, d, text, f); t += d + GAP
TOTAL = t - GAP
def when(num, cue):
    s, d, text, _ = start[num]
    if not cue: return s
    i = text.find(cue)
    if i < 0: raise SystemExit(f"cue not found in section {num}: {cue}")
    return s + d * i / max(1, len(text))

# ---- pictures: each one starts at its cue and stays until the next one
shots = sorted(((when(p["sec"], p.get("cue")), p["n"]) for p in plan["pictures"]))
def frame(n):
    """The whole square picture in the middle of a 16:9 frame, over a blurred, darkened copy of itself."""
    out = f"{WORK}/f{n:02d}.jpg"
    im = Image.open(f"{PICS}/{n:02d}.jpg").convert("RGB")
    bg = im.resize((W, W)).crop((0, (W - H) // 2, W, (W - H) // 2 + H)).filter(ImageFilter.GaussianBlur(28)).point(lambda v: int(v * 0.45))
    fg = im.resize((H, H)); bg.paste(fg, ((W - H) // 2, 0)); bg.save(out, quality=92); return out
with open(f"{WORK}/pics.txt", "w") as f:
    for k, (ts, n) in enumerate(shots):
        end = shots[k + 1][0] if k + 1 < len(shots) else TOTAL + 1.5
        f.write(f"file '{os.path.abspath(frame(n))}'\nduration {end - ts:.3f}\n")
    f.write(f"file '{os.path.abspath(frame(shots[-1][1]))}'\n")

# ---- on-screen tags (ASS subtitles)
def ts(x): h = int(x // 3600); m = int(x % 3600 // 60); return f"{h}:{m:02d}:{x % 60:05.2f}"
ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: tag,{FONT},40,&H0000E6FF,&H0,&H28101010,&H0,1,0,0,0,100,100,0,0,3,10,0,1,40,40,46,1
Style: big,{FONT},52,&H00FFFFFF,&H0,&H20101010,&H0,1,0,0,0,100,100,0,0,3,14,0,2,80,80,70,1
Style: card,{FONT},48,&H00FFFFFF,&H0,&H18101010,&H0,1,0,0,0,100,100,0,0,3,22,0,5,120,120,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
for g in plan["tags"]:
    a = when(g["sec"], g.get("cue")) + g.get("delay", 0.3); b = min(a + g.get("for", 5.0), TOTAL)
    ass += f"Dialogue: 0,{ts(a)},{ts(b)},{g.get('style', 'tag')},,0,0,0,,{{\\fad(350,350)}}{g['text']}\n"
open(f"{WORK}/tags.ass", "w", encoding="utf-8").write(ass)

# ---- sound: narration (sections with a short gap), music looped quietly underneath
ins, parts = [], []
for k, (num, name, text) in enumerate(secs):
    ins += ["-i", start[num][3]]; parts.append(f"[{k}]aresample=44100,apad=pad_dur={GAP}[a{k}]")
n = len(secs)
fc = ";".join(parts) + ";" + "".join(f"[a{k}]" for k in range(n)) + f"concat=n={n}:v=0:a=1,highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=9[v];" \
     f"[{n}]aloop=loop=-1:size=2e9,aresample=44100,volume={plan.get('bgm_volume', 0.07)},afade=t=in:d=2,afade=t=out:st={TOTAL - 2.5:.2f}:d=4[m];[v][m]amix=inputs=2:duration=first:normalize=0[out]"
run("ffmpeg", "-v", "error", "-y", *ins, "-i", BGM, "-filter_complex", fc, "-map", "[out]", "-t", f"{TOTAL + 1.5:.2f}", "-ar", "44100", f"{WORK}/sound.wav")

# ---- the video
run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{WORK}/pics.txt", "-i", f"{WORK}/sound.wav",
    "-vf", f"fps={FPS},ass={WORK}/tags.ass,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-tune", "stillimage",
    "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", f"out/{NAME}.mp4")
print(f"video: out/{NAME}.mp4  {dur(f'out/{NAME}.mp4'):.1f} s, {len(shots)} pictures, {len(plan['tags'])} tags")
