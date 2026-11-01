import os, json, random, re, subprocess, asyncio, time, difflib, datetime, urllib.parse, wave, math
from array import array
import concurrent.futures as cf
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out"); os.makedirs(OUT, exist_ok=True)
HIST = os.path.join(ROOT, "history.json")
W, H, FPS, SR = 1080, 1920, 30, 44100      # YouTube Shorts: vertical 9:16
OV = 0.3                                    # cross-dissolve seconds

def env(k, d=""):
    return os.environ.get(k) or d

CHANNEL = env("CHANNEL_NAME", "Kutty Kadhaigal")
SLOT = int(env("SLOT", "1") or 1)

# ---------------- variety pools (every story = new combination) ----------------
THEMES = ["honesty", "sharing with others", "kindness to animals", "teamwork", "helping elders", "bravery", "patience",
          "hard work", "keeping clean", "respecting teachers", "never telling lies", "saying thank you", "listening to parents",
          "saving water", "planting trees", "avoiding greed", "being curious", "forgiving a friend", "road safety",
          "eating healthy food", "being humble", "not giving up", "caring for nature", "including everyone in play"]
HEROES = {1: ["a little elephant", "a clever crow", "a brave mouse", "a slow tortoise and a fast rabbit", "a naughty monkey", "a talkative parrot",
              "a shy peacock", "a tiny squirrel", "a lion cub", "a golden fish", "a gentle cow", "a puppy", "a curious kitten", "a busy bee", "a little ant"],
          2: ["two village kids Anbu and Meena", "a girl named Kavya and her grandmother", "a boy named Arun and his school friends", "twin sisters Tara and Mala",
              "a boy named Ravi who loves cricket", "a girl named Nila who loves painting", "a village potter's son", "a boy and his bullock cart"],
          3: ["a talking little bus", "the friendly moon and a star", "a magic mango tree", "a cloud who wanted to rain", "a toy robot and a child", "a kite that loved flying",
              "a flower fairy", "a small boat on the river", "a rainbow and a raindrop", "a talking school bag"]}
SETTINGS = ["a Tamil village", "under a big banyan tree", "a mango grove", "a river bank", "a temple festival fair", "a school ground",
            "a green forest", "a paddy field", "a sunny beach", "a hill village", "a pond with lotus flowers", "a village market"]
CHALLENGES = ["something precious gets lost", "a friendly contest", "preparing for a festival", "a sudden rain", "a helper in disguise",
              "a wrong shortcut", "a broken promise", "a new friend feels left out", "a hungry traveller arrives", "a secret is discovered"]

# voice styles -> (edge voice, rate, pitch). Child-like / big / squeaky voices come from pitch + speed shifts.
STYLES = {
    "narrator":       ("ta-IN-PallaviNeural", "+0%",  "+0Hz"),
    "boy":            ("ta-IN-ValluvarNeural", "+0%", "+16Hz"),
    "girl":           ("ta-IN-PallaviNeural", "+0%",  "+12Hz"),
    "old_man":        ("ta-LK-KumarNeural",   "-6%",  "-6Hz"),
    "old_woman":      ("ta-SG-VenbaNeural",   "-4%",  "-2Hz"),
    "big_deep":       ("ta-MY-SuryaNeural",   "-4%",  "-14Hz"),
    "squeaky":        ("ta-LK-SaranyaNeural", "+4%", "+24Hz"),
    "cheerful_man":   ("ta-SG-AnbuNeural",    "+2%",  "+6Hz"),
    "cheerful_woman": ("ta-MY-KaniNeural",    "+2%",  "+8Hz"),
}
STYLE_ORDER = ["boy", "girl", "old_man", "old_woman", "big_deep", "squeaky", "cheerful_man", "cheerful_woman"]
COLORS = ["00F0FF", "B469FF", "FFE500", "0098FF", "5CFF7C", "FF8AE8"]     # ASS BGR: yellow, pink, cyan, orange, green, lilac
NARR_COLOR = "FFFFFF"

def ist_today():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d")

def load_hist():
    try: return json.load(open(HIST))
    except Exception: return {"titles": [], "fingerprints": []}

def save_hist(h):
    h["titles"] = h["titles"][-400:]; h["fingerprints"] = h["fingerprints"][-400:]
    for k in ("done", "tries"):
        if k in h: h[k] = dict(sorted(h[k].items())[-14:])
    for k in ("recent_themes", "recent_heroes"): h[k] = h.get(k, [])[-12:]
    json.dump(h, open(HIST, "w"), ensure_ascii=False, indent=1)

def pick_combo(h):
    used = set(h["fingerprints"])
    rt = h.get("recent_themes", [])[-8:]; rh = h.get("recent_heroes", [])[-8:]
    themes = [x for x in THEMES if x not in rt] or THEMES
    heroes_all = HEROES.get(SLOT, HEROES[1]); heroes = [x for x in heroes_all if x not in rh] or heroes_all
    for _ in range(300):
        c = (random.choice(themes), random.choice(heroes), random.choice(SETTINGS), random.choice(CHALLENGES))
        if "|".join(c) not in used: return c
    return c

def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print("COMMAND FAILED:", " ".join(str(c) for c in cmd)[:400]); print(r.stderr[-1800:])
        raise SystemExit("ffmpeg step failed")
    return r

def txt_of(x):
    """LLM output can be str, dict, list... always return plain text."""
    if x is None: return ""
    if isinstance(x, str): return x.strip()
    if isinstance(x, dict): return " - ".join(t for t in (txt_of(v) for v in x.values()) if t)
    if isinstance(x, (list, tuple)): return "; ".join(t for t in (txt_of(v) for v in x) if t)
    return str(x)

# ====================== SCRIPT (LLM) ======================
def llm_json(prompt, check=None, retries=7):
    key = env("LLM_API_KEY"); base = env("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    model = env("LLM_MODEL")
    if not model:
        model = "llama-3.3-70b-versatile"
        try:
            ids = [x["id"] for x in requests.get(base + "/models", headers={"Authorization": "Bearer " + key}, timeout=30).json()["data"]]
            for pref in ["gpt-oss-120b", "llama-3.3-70b", "llama-4", "llama-3.1-70b"]:
                m = [i for i in ids if pref in i]
                if m: model = m[0]; break
        except Exception as e: print("model list failed", e)
    extra = ""
    for a in range(retries):
        body = {"model": model, "messages": [{"role": "user", "content": prompt + extra}], "temperature": 0.9, "max_tokens": 6000}
        if a % 2 == 0: body["response_format"] = {"type": "json_object"}
        if "gpt-oss" in model: body["reasoning_effort"] = "low"
        try:
            r = requests.post(base + "/chat/completions", headers={"Authorization": "Bearer " + key}, json=body, timeout=180)
            if r.status_code == 429: time.sleep(30); continue
            if r.status_code != 200: print("LLM", r.status_code, r.text[:200]); time.sleep(5); continue
            txt = re.sub(r"^```(?:json)?|```$", "", (r.json()["choices"][0]["message"]["content"] or "").strip(), flags=re.M).strip()
            d = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
            err = check(d, a >= 5) if check else None
            if err: extra = "\n" + err; print("retry:", err); continue
            return d
        except Exception as e:
            print("llm attempt failed:", e); time.sleep(3)
    raise SystemExit("LLM failed")

def norm_lines(raw, names):
    """-> list of {speaker, text}; unknown speakers become the Narrator."""
    out = []
    for it in (raw if isinstance(raw, list) else [raw]):
        if isinstance(it, dict):
            sp = txt_of(it.get("speaker") or it.get("name") or it.get("character") or "Narrator")
            tx = txt_of(it.get("text") or it.get("line") or it.get("voiceover") or it.get("dialogue"))
        else:
            s = txt_of(it); m = re.match(r"^\s*([^:锛歖{1,30})[:锛歖\s*(.+)$", s)
            sp, tx = (m.group(1), m.group(2)) if m else ("Narrator", s)
        if not tx: continue
        low = sp.strip().lower()
        hit = next((n for n in names if n.lower() == low), None) or next((n for n in names if low and (low in n.lower() or n.lower() in low)), None)
        out.append({"speaker": hit or "Narrator", "text": tx})
    return out

def count_words(d, names):
    return sum(len(l["text"].split()) for b in d.get("beats", []) if isinstance(b, dict) for l in norm_lines(b.get("lines"), names))

def make_check(names):
    def check(d, late):
        b = d.get("beats")
        if not isinstance(b, list) or len(b) < 6: return "Return 8 beats."
        for x in b:
            if not isinstance(x, dict) or not norm_lines(x.get("lines"), names) or not txt_of(x.get("scene")): return "Every beat needs lines and a scene."
        n = count_words(d, names)
        if n < (60 if late else 85): return f"Your previous answer had only {n} Tamil words in total. Write 105 to 130 Tamil words across all lines."
        if n > 175: return f"Too long ({n} words). Keep it to 105-130 Tamil words in total."
        return None
    return check

def assign_voices(chars):
    used = set(); styles = {}
    for c in chars:
        st = txt_of(c.get("voice")).lower().replace(" ", "_").replace("-", "_")
        if st not in STYLES or st == "narrator" or st in used:
            st = next((p for p in STYLE_ORDER if p not in used), "boy")
        used.add(st); styles[c["name"]] = st
    styles["Narrator"] = "narrator"
    colors = {n: COLORS[i % len(COLORS)] for i, n in enumerate(c["name"] for c in chars)}
    colors["Narrator"] = NARR_COLOR
    return styles, colors

def make_script(h):
    combo = pick_combo(h); code = random.randint(1000, 9999)
    avoid = "; ".join(h["titles"][-40:]) or "none"
    outline = llm_json(f"""You create ORIGINAL, gentle, funny children's stories in Tamil for kids aged 3-8 (YouTube Short, about 50 seconds). No violence, nothing scary, no real brands or famous cartoon characters.
Ingredients (all must appear): Moral theme: {combo[0]} | Hero: {combo[1]} | Place: {combo[2]} | Situation: {combo[3]} | Variation code: {code}
Do NOT repeat these earlier titles/ideas: {avoid}
Return JSON only:
title (Tamil, cute and curious, max 45 chars),
description (Tamil, 2 short lines),
tags (8 strings),
moral (Tamil, ONE short sentence),
setting_look (English, one sentence describing the place's look),
characters: list of 2 to 4 objects, each with name (short Tamil name), look (English: species/age, colours, clothes, adorable 3D cartoon look) and voice (choose one of: boy, girl, old_man, old_woman, big_deep, squeaky, cheerful_man, cheerful_woman; use different voices for different characters; big animals use big_deep, tiny animals squeaky, kids boy/girl),
plot (English, 60-90 words: beginning, small problem, how it is solved, moral).""")
    for k in ("title", "description", "moral", "setting_look", "plot"): outline[k] = txt_of(outline.get(k))
    if not outline["title"] or not outline["plot"]: raise SystemExit("Outline missing title/plot")
    tg_ = outline.get("tags", [])
    outline["tags"] = [txt_of(t) for t in tg_] if isinstance(tg_, list) else [t.strip() for t in txt_of(tg_).replace("#", "").split(",") if t.strip()]
    if max([difflib.SequenceMatcher(None, outline["title"], t).ratio() for t in h["titles"]] or [0]) > 0.7:
        return make_script(h)
    chars = []
    for c in (outline.get("characters") if isinstance(outline.get("characters"), list) else []):
        if isinstance(c, dict) and txt_of(c.get("name")): chars.append({"name": txt_of(c["name"]), "look": txt_of(c.get("look")) or "cute cartoon character", "voice": c.get("voice")})
    if len(chars) < 1: chars = [{"name": "喈曕瘉喈熰瘝喈熰", "look": "cute little cartoon animal", "voice": "boy"}]
    styles, colors = assign_voices(chars)
    names = [c["name"] for c in chars]
    looks = "; ".join(f"{c['name']} = {c['look']}" for c in chars)
    d = llm_json(f"""Write the script of this children's story as a short animated dialogue.
Title: {outline['title']}
Plot: {outline['plot']}
Moral (the Narrator says it in the LAST beat): {outline['moral']}
Characters (use EXACTLY these names as speakers, plus "Narrator"): {', '.join(names)}
Looks: {looks}
Setting: {outline['setting_look']}
Style: cheerful, simple spoken Tamil (Tamil script) a small child understands, very short lines (max 10 words), lively dialogue between the characters, a little humour, sound words like "喈熰喈距喁�!" are welcome. The FIRST beat must be an exciting hook (a question or a surprise).
Return JSON only: beats = list of exactly 8 beats in order. Each beat has:
  lines: list of 1 or 2 objects {{"speaker": name or "Narrator", "text": Tamil line}},
  scene: ONE English image prompt showing exactly what happens in that beat (cute bright 3D cartoon, the characters' looks from the list, happy colourful, child-friendly, no text).
Total across all lines: 105-130 Tamil words.""", check=make_check(names))
    beats = []
    for b in d["beats"][:9]:
        beats.append({"lines": norm_lines(b.get("lines"), names), "scene": txt_of(b.get("scene"))})
    outline.update({"beats": beats, "chars": chars, "styles": styles, "colors": colors, "fp": "|".join(combo), "combo": list(combo)})
    return outline

# ====================== VOICE ======================
CTA_TEXT = "喈曕喁� 喈喈熰喈氞瘝喈氞喈班瘉喈ㄠ瘝喈む 喈侧瘓喈曕瘝 喈喁嵿喁佮畽喁嵿畷, 喈氞喁嵿喁嵿畷喈苦喁堗喁� 喈喁嵿喁佮畽喁嵿畷!"

def chunk_long(words, mx=12):
    parts = []
    while len(words) > mx:
        idx = next((i for i in range(mx, 4, -1) if words[i - 1].endswith((",", "!", "?"))), mx - 1)
        parts.append(words[:idx]); words = words[idx:]
    parts.append(words); return parts

async def _edge_one(text, path, voice, rate, pitch, sem):
    import edge_tts
    fallback = "ta-IN-ValluvarNeural" if any(k in voice for k in ("Valluvar", "Kumar", "Surya", "Anbu")) else "ta-IN-PallaviNeural"
    async with sem:
        for a in range(6):
            v = voice if a < 3 else fallback          # unknown/blocked voice -> fall back to the core Tamil voice, same pitch
            try:
                await edge_tts.Communicate(text, v, rate=rate, pitch=pitch).save(path)
                if os.path.getsize(path) > 800: return
            except Exception as e:
                print("tts retry", a, v, str(e)[:80]); await asyncio.sleep(2 * (a + 1))
        raise SystemExit("TTS failed for: " + text[:40])

def _to_wav(mp3, wav):
    trim = "silenceremove=start_periods=1:start_duration=0.02:start_threshold=-45dB"
    r = subprocess.run(["ffmpeg", "-y", "-i", mp3, "-af", f"{trim},areverse,{trim},areverse", "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", wav], capture_output=True)
    if r.returncode != 0 or wav_dur(wav) < 0.2:
        run(["ffmpeg", "-y", "-i", mp3, "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", wav])

def wav_dur(p):
    with wave.open(p) as w: return w.getnframes() / w.getframerate()

def tts_batch(jobs):
    """jobs: list of dicts text, wav, voice, rate, pitch"""
    async def go():
        sem = asyncio.Semaphore(4)
        await asyncio.gather(*[_edge_one(j["text"], j["wav"] + ".mp3", j["voice"], j["rate"], j["pitch"], sem) for j in jobs])
    asyncio.run(go())
    with cf.ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda j: _to_wav(j["wav"] + ".mp3", j["wav"]), jobs))

# ====================== TIMELINE ======================
def plan_timeline(beats):
    t = 0.2
    for b in beats:
        b["start"] = t
        for s in b["lines"]:
            s["start"] = t; t += s["dur"]; s["end"] = t; t += 0.12
        t += 0.06; b["end"] = t
    story_frames = math.ceil((t + 0.2) * FPS)
    for i, b in enumerate(beats):
        b["f0"] = 0 if i == 0 else round(b["start"] * FPS)
        b["f1"] = story_frames if i == len(beats) - 1 else round(beats[i + 1]["start"] * FPS)
    return story_frames

# ====================== ASS ======================
def ts(t):
    cs = int(round(max(t, 0) * 100)); return f"{cs//360000}:{cs//6000%60:02d}:{cs//100%60:02d}.{cs%100:02d}"

def ass_head():
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Cap,Noto Sans Tamil,78,&H0000F0FF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,7,3,2,70,70,0,1
Style: Chip,Noto Sans Tamil,60,&H00FFFFFF,&H00FFFFFF,&H00FF8AE8,&H00000000,1,0,0,0,100,100,0,0,3,3,0,2,60,60,0,1
Style: Title,Noto Sans Tamil,68,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,3,8,70,70,0,1
Style: Brand,DejaVu Sans,34,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,1,0,0,0,100,100,2,0,3,3,0,7,40,40,0,1
Style: Shape,DejaVu Sans,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: Txt,DejaVu Sans,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,1,5,0,0,0,1
Style: Tam,Noto Sans Tamil,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,5,1,5,0,0,0,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

def tg(s): return "{" + s + "}"
def dlg(layer, st, en, style, text): return f"Dialogue: {layer},{ts(st)},{ts(en)},{style},,0,0,0,,{text}"
def shape(layer, st, en, cx, cy, path, col, extra=""):
    return dlg(layer, st, en, "Shape", tg(rf"\an5\pos({cx:.0f},{cy:.0f})\c&H{col}&\bord0\shad0{extra}\p1") + path + tg(r"\p0"))
def txt(layer, st, en, style, cx, cy, col, size, text, extra=""):
    return dlg(layer, st, en, style, tg(rf"\an5\pos({cx:.0f},{cy:.0f})\c&H{col}&\fs{size}{extra}") + text)

def rrect(w, h, r):
    k = 0.5523 * r
    return (f"m {r} 0 l {w-r} 0 b {w-r+k:.1f} 0 {w} {r-k:.1f} {w} {r} l {w} {h-r} b {w} {h-r+k:.1f} {w-r+k:.1f} {h} {w-r} {h} "
            f"l {r} {h} b {r-k:.1f} {h} 0 {h-r+k:.1f} 0 {h-r} l 0 {r} b 0 {r-k:.1f} {r-k:.1f} 0 {r} 0")
def circle(d):
    r = d / 2.0; k = 0.5523 * r
    return (f"m 0 {r:.1f} b 0 {r-k:.1f} {r-k:.1f} 0 {r:.1f} 0 b {r+k:.1f} 0 {d} {r-k:.1f} {d} {r:.1f} "
            f"b {d} {r+k:.1f} {r+k:.1f} {d} {r:.1f} {d} b {r-k:.1f} {d} 0 {r+k:.1f} 0 {r:.1f}")
CIRCLE = circle(60); BIGCIRCLE = circle(110)
THUMB = ("m 0 26 l 12 26 l 12 58 l 0 58 m 16 28 l 25 6 b 27 2 33 2 36 5 b 38 8 38 12 36 16 l 33 22 l 52 22 b 57 22 60 26 59 31 "
         "l 55 50 b 54 55 50 58 45 58 l 16 58 l 16 28")
BELL = ("m 30 2 b 40 2 46 10 46 22 l 46 36 l 54 46 l 54 50 l 6 50 l 6 46 l 14 36 l 14 22 b 14 10 20 2 30 2 "
        "m 23 53 b 24 59 36 59 37 53 l 23 53")
POINTER = "m 0 0 l 0 40 l 10 31 l 17 46 l 24 43 l 17 28 l 30 28 l 0 0"

def caption_events(lines, colors_by_speaker):
    ev = []
    for s in lines:
        col = colors_by_speaker.get(s["speaker"], NARR_COLOR)
        words = s["text"].split(); wts = [max(1, len(x)) for x in words]; tot = float(sum(wts)); dur = s["dur"]
        chunks = []; cur = []; cl = 0
        for i, x in enumerate(words):
            if cur and (cl + len(x) + 1 > 22 or len(cur) >= 4): chunks.append(cur); cur = []; cl = 0
            cur.append(i); cl += len(x) + 1
        if cur: chunks.append(cur)
        acc = 0; starts = []
        for wt in wts: starts.append(acc / tot * dur); acc += wt
        ends = starts[1:] + [dur]
        base = tg(rf"\an2\pos(540,1520)\1c&H{col}&\2c&HFFFFFF&")
        for ci, ch in enumerate(chunks):
            st = s["start"] + starts[ch[0]]
            en = (s["end"] + 0.1) if ci == len(chunks) - 1 else (s["start"] + ends[ch[-1]])
            k = "".join(r"{\kf%d}%s " % (max(1, round((ends[i] - starts[i]) * 100)), words[i]) for i in ch)
            ev.append(dlg(0, st, en, "Cap", base + k.strip()))
    return ev


def logo_events(L):
    """Animated channel badge, top-left, whole video. Own logo: put assets/logo.png (overlaid later)."""
    if os.path.exists(os.path.join(ROOT, "assets", "logo.png")): return []
    ini = (CHANNEL.strip()[:1] or "K").upper(); ev = []
    ev.append(dlg(8, 0, L, "Shape", tg(r"\an5\pos(120,170)\c&H3A9BFF&\3c&HFFFFFF&\bord6\shad0\fad(300,0)\p1") + circle(130) + tg(r"\p0")))
    t = 0.0; wob = ""
    while t < L:
        wob += rf"\t({int(t*1000)},{int(t*1000+400)},\frz8\fscx108\fscy108)\t({int(t*1000+400)},{int(t*1000+800)},\frz-8\fscx100\fscy100)"; t += 0.8
    ev.append(dlg(9, 0, L, "Shape", tg(r"\an5\pos(120,170)\c&HFFFFFF&\bord0\shad0\fs72\b1\fad(300,0)" + wob) + ini))
    ev.append(dlg(9, 0, L, "Brand", tg(r"\an4\pos(200,170)\fad(400,0)\fs38") + CHANNEL))
    return ev

# ====================== IMAGES ======================
STYLE = ", cute 3D animated cartoon style like a children's movie, bright vibrant colours, soft warm lighting, big friendly expressive eyes, happy mood, child-friendly, vertical composition, no text"
def get_image(prompt, path, prev, size=(720, 1280), style=True):
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt + (STYLE if style else ", cute 3D animated cartoon style, bright colours, big friendly eyes")) + f"?width={size[0]}&height={size[1]}&nologo=true&seed={random.randint(1,999999)}"
    for i in range(5):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 5000 and r.headers.get("content-type", "").startswith("image"):
                open(path, "wb").write(r.content); return
        except Exception as e: print("img retry", e)
        time.sleep(4 * (i + 1))
    if prev and os.path.exists(prev): open(path, "wb").write(open(prev, "rb").read())
    else: run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x2a6fdb:s={size[0]}x{size[1]}", "-frames:v", "1", path])


# ====================== PUPPET ANIMATION ======================
CHAR_H = 660          # character height in the 1080x1920 frame
CHAR_BASE = 1600      # feet line

def make_cutout(img_path, out_png):
    """Remove the plain white background (flood fill from the 4 corners) -> RGBA png cropped to the character."""
    from PIL import Image, ImageDraw, ImageChops, ImageFilter
    im = Image.open(img_path).convert("RGB"); w, h = im.size
    work = im.copy(); mark = (255, 0, 254)
    for pt in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1)):
        try:
            if work.getpixel(pt) != mark: ImageDraw.floodfill(work, pt, mark, thresh=48)
        except Exception: pass
    r, g, b = work.split()
    bg = ImageChops.multiply(ImageChops.multiply(r.point(lambda v: 255 if v == 255 else 0), g.point(lambda v: 255 if v == 0 else 0)), b.point(lambda v: 255 if v == 254 else 0))
    alpha = ImageChops.invert(bg).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    rgba = im.convert("RGBA"); rgba.putalpha(alpha)
    box = alpha.point(lambda v: 255 if v > 40 else 0).getbbox()
    if not box or (box[2] - box[0]) < w * 0.12 or (box[3] - box[1]) < h * 0.25: return False   # nothing usable cut out
    rgba = rgba.crop(box); sc = CHAR_H / rgba.size[1]
    nw, nh = int(rgba.size[0] * sc), CHAR_H
    if nw > 480: nh = int(nh * 480 / nw); nw = 480
    rgba = rgba.resize((nw, nh), Image.LANCZOS)
    rgba.save(out_png); return True

def make_characters(d, workdir):
    ok = {}
    for i, c in enumerate(d["chars"][:4]):
        raw = os.path.join(workdir, f"char{i}.jpg"); png = os.path.join(workdir, f"char{i}.png")
        for attempt in range(2):
            get_image(f"{c['look']}, full body, standing, front view, facing the camera, smiling, centered, solid pure white background #FFFFFF, no shadow, no ground, no text",
                      raw, None, size=(768, 768), style=False)
            try:
                if make_cutout(raw, png): ok[c["name"]] = png; break
            except Exception as e: print("cutout failed:", e)
    return ok

def beat_cast(beat, chars_ok, order):
    names = []
    for l in beat["lines"]:
        if l["speaker"] in chars_ok and l["speaker"] not in names: names.append(l["speaker"])
    if not names: names = [order[0]] if order else []
    return names[:3]

def overlay_chars(clip_in, clip_out, beat, clip_start, F, cast, chars_ok):
    """Puppets: idle sway always, lively bounce while that character speaks."""
    from PIL import Image
    if not cast: os.replace(clip_in, clip_out); return
    n = len(cast); inputs = ["-i", clip_in]; chain = []; last = "0:v"
    for k, nm in enumerate(cast):
        inputs += ["-i", chars_ok[nm]]
        wpx, hpx = Image.open(chars_ok[nm]).size
        cx = int(W * (k + 1) / (n + 1)); x0 = cx - wpx // 2; y0 = CHAR_BASE - hpx
        spk = [(max(0.0, l["start"] - clip_start), l["end"] - clip_start) for l in beat["lines"] if l["speaker"] == nm]
        bounce = "+".join(f"between(t,{a:.3f},{b:.3f})*(26*abs(sin(t*13)))" for a, b in spk) or "0"
        dip = "+".join(f"between(t,{a:.3f},{b:.3f})*0" for a, b in spk) or "0"
        pop = f"if(lt(t,0.35),(0.35-t)*260,0)"          # characters hop in at the start of every scene
        chain.append(f"[{last}][{k+1}:v]overlay=x='{x0}+5*sin(t*2+{k})':y='{y0}+4*sin(t*3+{k})-({bounce})+{pop}':format=auto[o{k}]")
        last = f"o{k}"
    run(["ffmpeg", "-y"] + inputs + ["-filter_complex", ";".join(chain), "-map", f"[{last}]", "-frames:v", str(F)] + VENC[:-1] + [clip_out])

# ====================== VIDEO ======================
VENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-r", str(FPS), "-video_track_timescale", "15360", "-an"]

def motion(kind, F):
    x = "iw/2-(iw/zoom/2)"; y = "ih/2-(ih/zoom/2)"
    if kind == 0: z = f"1+0.16*on/{F}+0.012*sin(on/5)"
    elif kind == 1: z = f"1.18-0.16*on/{F}+0.012*sin(on/5)"
    elif kind == 2: z = "1.15"; x = f"(iw-iw/zoom)*on/{F}"
    elif kind == 3: z = "1.15"; x = f"(iw-iw/zoom)*(1-on/{F})"
    elif kind == 4: z = f"1+0.2*on/{F}+0.01*sin(on/4)"; x = "iw*0.5-(iw/zoom)*0.5"; y = "ih*0.4-(ih/zoom)*0.4"
    else: z = "1.14"; y = f"(ih-ih/zoom)*on/{F}"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={F}:s={W}x{H}:fps={FPS}"

def render_clip(a):
    img, out, F, kind = a
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", img, "-vf",
         f"crop=iw:ih*0.93:0:0,scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},{motion(kind, F)},format=yuv420p",
         "-frames:v", str(F), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "17", "-threads", "2", out])
    return out

def make_story(d, beats, story_frames, workdir):
    chars_ok = make_characters(d, workdir) if env("PUPPETS", "true") != "false" else {}
    puppet = bool(chars_ok); order = [c["name"] for c in d["chars"] if c["name"] in chars_ok]
    print("Puppet mode:", puppet, "| cutouts:", list(chars_ok))
    imgs = []; prev = None
    for i, b in enumerate(beats):
        p = os.path.join(workdir, f"img{i}.jpg")
        sc = (f"{d['setting_look']}, {b['scene']}, EMPTY background scenery only, no people, no animals, no characters, wide open ground in the lower middle" if puppet else b["scene"])
        get_image(sc, p, prev); imgs.append(p); prev = p
    hf = int(OV * FPS / 2); N = len(beats); jobs = []
    for i, b in enumerate(beats):
        n = b["f1"] - b["f0"]
        F = n if N == 1 else n + (hf if i in (0, N - 1) else 2 * hf)
        jobs.append((imgs[i], os.path.join(workdir, f"clip{i}.mp4"), F, (i * 5 + 1) % 6))
    with cf.ThreadPoolExecutor(3) as ex: clips = list(ex.map(render_clip, jobs))
    if puppet:
        for i, b in enumerate(beats):
            cs = 0.0 if i == 0 else (b["f0"] - hf) / FPS
            outp = os.path.join(workdir, f"clipc{i}.mp4")
            overlay_chars(clips[i], outp, b, cs, jobs[i][2], beat_cast(b, chars_ok, order), chars_ok)
            clips[i] = outp
    allines = [l for b in beats for l in b["lines"]]; story_len = story_frames / FPS
    ass = [ass_head()]
    ass += logo_events(story_len)
    ass.append(dlg(2, 0.0, 3.4, "Title", tg(r"\an8\pos(540,300)\fad(150,450)\fscx88\fscy88\t(0,300,\fscx100\fscy100)") + d["title"]))
    for s in allines:
        if s["speaker"] != "Narrator":
            ass.append(dlg(1, s["start"], s["end"] + 0.1, "Chip", tg(rf"\an2\pos(540,1700)\3c&H{d["colors"][s["speaker"]]}&\bord18\1c&H202020&") + " " + s["speaker"] + " "))
    assf = os.path.join(workdir, "story.ass"); open(assf, "w", encoding="utf-8").write("\n".join(ass) + "\n")
    fc = []; last = "0:v"
    for i in range(1, N):
        off = (beats[i]["f0"] - hf) / FPS
        fc.append(f"[{last}][{i}:v]xfade=transition=fade:duration={OV}:offset={off:.4f}[x{i}]"); last = f"x{i}"
    tail = (f"[{last}]tpad=stop_mode=clone:stop_duration=2,eq=contrast=1.05:saturation=1.22,"
            f"ass={assf},fade=t=out:st={story_len-0.2:.3f}:d=0.2[vout]")
    fc.append(tail if N > 1 else tail.replace(f"[{last}]", "[0:v]", 1))
    out = os.path.join(workdir, "story.mp4"); cmd = ["ffmpeg", "-y"]
    for c in clips: cmd += ["-i", c]
    run(cmd + ["-filter_complex", ";".join(fc), "-map", "[vout]", "-frames:v", str(story_frames)] + VENC + [out])
    return out, imgs[-1]

def outro_clicks(cta):
    s, d = cta["start"], cta["dur"]
    c1 = s + 0.30 * d + 0.15; c2 = max(s + 0.72 * d, c1 + 0.55); c3 = max(s + d + 0.25, c2 + 0.55)
    return c1, c2, c3

def make_outro(workdir, last_img, cta, outro_frames):
    L = outro_frames / FPS; ass = [ass_head()]
    c1, c2, c3 = outro_clicks(cta)
    ass += logo_events(L)
    ass.append(txt(2, 0.05, L, "Tam", 540, 560, "00F0FF", 84, "喈喈熰喈氞瘝喈氞喈班瘉喈曕瘝喈曕?", r"\fad(200,200)\fscx80\fscy80\t(0,300,\fscx100\fscy100)"))
    ass.append(txt(2, 0.05, L, "Txt", 540, 700, "FFFFFF", 70, "LIKE  鈥�  SUBSCRIBE", r"\fad(200,200)"))
    LX, SX, BX, Y = 255, 640, 905, 900
    for (a, b, col, label, icon) in [(0.05, c1, "3A3A3A", "LIKE", "FFFFFF"), (c1, L, "FFA63E", "LIKED", "FFFFFF")]:
        ex = r"\fad(200,0)" if a == 0.05 else r"\fscx112\fscy112\t(0,200,\fscx100\fscy100)"
        ass.append(shape(1, a, b, LX, Y, rrect(300, 120, 60), col, ex))
        ass.append(shape(2, a, b, LX - 78, Y - 3, THUMB, icon, ex))
        ass.append(txt(3, a, b, "Txt", LX + 36, Y, "FFFFFF", 44, label, ex))
    for (a, b, col, label, size) in [(0.05, c2, "0000FF", "SUBSCRIBE", 44), (c2, L, "4A4A4A", "SUBSCRIBED 鉁�", 34)]:
        ex = r"\fad(200,0)" if a == 0.05 else r"\fscx108\fscy108\t(0,200,\fscx100\fscy100)"
        ass.append(shape(1, a, b, SX, Y, rrect(430, 120, 60), col, ex))
        ass.append(txt(3, a, b, "Txt", SX, Y, "FFFFFF", size, label, ex))
    ass.append(shape(1, 0.05, c3, BX, Y, BIGCIRCLE, "4A4A4A", r"\fad(200,0)"))
    ass.append(shape(2, 0.05, c3, BX, Y, BELL, "FFFFFF", r"\fad(200,0)\fscx105\fscy105"))
    shake = r"\t(0,90,\frz18)\t(90,180,\frz-18)\t(180,270,\frz14)\t(270,360,\frz-14)\t(360,450,\frz8)\t(450,540,\frz0)"
    ass.append(shape(1, c3, L, BX, Y, BIGCIRCLE, "00C8FF", r"\fscx108\fscy108\t(0,200,\fscx100\fscy100)"))
    ass.append(shape(2, c3, L, BX, Y, BELL, "000000", r"\fscx105\fscy105" + shake))
    pts = [(1000, 1300), (LX + 30, Y + 20), (SX + 60, Y + 20), (BX + 8, Y + 22)]
    clicks = [c1, c2, c3]
    legs = [(0.1, c1 - 0.12), (c1 + 0.2, min(c1 + 0.7, c2 - 0.08)), (c2 + 0.2, min(c2 + 0.7, c3 - 0.08))]
    for i, (s0, e0) in enumerate(legs):
        e0 = max(e0, s0 + 0.2)
        ass.append(dlg(5, s0, e0, "Shape", tg(rf"\an7\move({pts[i][0]},{pts[i][1]},{pts[i+1][0]},{pts[i+1][1]})\c&HFFFFFF&\3c&H000000&\bord2\shad0\p1") + POINTER + tg(r"\p0")))
        ass.append(dlg(5, e0, clicks[i] + 0.5, "Shape", tg(rf"\an7\pos({pts[i+1][0]},{pts[i+1][1]})\c&HFFFFFF&\3c&H000000&\bord2\shad0\p1") + POINTER + tg(r"\p0")))
        ass.append(shape(4, clicks[i], clicks[i] + 0.4, pts[i + 1][0] + 6, pts[i + 1][1] + 6, CIRCLE, "FFFFFF", r"\alpha&H50&\fscx30\fscy30\t(0,380,\fscx230\fscy230\alpha&HFF&)"))
    af = os.path.join(workdir, "outro.ass"); open(af, "w", encoding="utf-8").write("\n".join(ass) + "\n")
    out = os.path.join(workdir, "outro.mp4")
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", last_img, "-vf",
         f"crop=iw:ih*0.93:0:0,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=22:2,eq=brightness=-0.22:saturation=0.9,fade=t=in:d=0.25,ass={af},fade=t=out:st={L-0.25:.2f}:d=0.25",
         "-frames:v", str(outro_frames)] + VENC + [out])
    return out, clicks

# ====================== AUDIO ======================
def make_sfx(workdir):
    click = os.path.join(workdir, "click.wav"); pop = os.path.join(workdir, "pop.wav")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=f=1000:d=0.07:r=44100", "-af", "afade=t=out:st=0.01:d=0.06,volume=0.5,aformat=sample_fmts=s16:channel_layouts=mono", "-c:a", "pcm_s16le", click])
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=f=620:d=0.10:r=44100", "-af", "afade=t=in:d=0.01,afade=t=out:st=0.02:d=0.08,volume=0.35,aformat=sample_fmts=s16:channel_layouts=mono", "-c:a", "pcm_s16le", pop])
    return click, pop

def build_narration(path, total_s, pieces, sfx):
    buf = array("h", bytes(2 * int(round(total_s * SR))))
    for start_s, wav in pieces:
        with wave.open(wav) as w:
            a = array("h"); a.frombytes(w.readframes(w.getnframes()))
        s = int(round(start_s * SR)); e = min(len(buf), s + len(a)); buf[s:e] = a[: e - s]
    cache = {}
    for t, wav in sfx:
        if wav not in cache:
            with wave.open(wav) as w:
                a = array("h"); a.frombytes(w.readframes(w.getnframes())); cache[wav] = a
        s = int(round(t * SR))
        for i, v in enumerate(cache[wav]):
            if s + i < len(buf): buf[s + i] = max(-32768, min(32767, buf[s + i] + v))
    with wave.open(path, "wb") as o:
        o.setnchannels(1); o.setsampwidth(2); o.setframerate(SR); o.writeframes(buf.tobytes())

def find_bgm(workdir):
    folder = os.path.join(ROOT, "assets"); pref = env("BGM_FILE")
    files = sorted(f for f in (os.listdir(folder) if os.path.isdir(folder) else []) if f.lower().endswith((".mp3", ".m4a", ".wav", ".ogg", ".aac")))
    if pref and pref in files: pick = pref
    elif "bgm.mp3" in files: pick = "bgm.mp3"
    elif files: pick = random.choice(files)
    else: print("No BGM found in assets/ - voice-only audio"); return None
    src = os.path.join(folder, pick); norm = os.path.join(workdir, "bgm_norm.m4a")
    r = subprocess.run(["ffmpeg", "-y", "-i", src, "-vn", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", "-ac", "2", "-c:a", "aac", norm], capture_output=True)
    if r.returncode != 0: print("BGM normalise failed, using original"); norm = src
    print("BGM:", pick); return norm

def mix_audio(narr, total_s, workdir):
    out = os.path.join(workdir, "mix.m4a"); bgm = find_bgm(workdir)
    voice = ("highpass=f=80,equalizer=f=250:t=q:w=1.2:g=1.5,equalizer=f=3000:t=q:w=1:g=4,"
             "acompressor=threshold=0.09:ratio=3:attack=5:release=120:makeup=2,loudnorm=I=-14:TP=-1.5:LRA=9")
    fade = f"afade=t=out:st={total_s-0.8:.2f}:d=0.8"
    if bgm:
        fc = (f"[0:a]{voice},asplit=2[v][vs];[1:a]volume=0.34[b];[b][vs]sidechaincompress=threshold=0.02:ratio=9:attack=20:release=500[bd];"
              f"[v][bd]amix=inputs=2:duration=first:normalize=0,{fade}[a]")
        run(["ffmpeg", "-y", "-i", narr, "-stream_loop", "-1", "-i", bgm, "-filter_complex", fc, "-map", "[a]", "-t", f"{total_s:.3f}", "-c:a", "aac", "-b:a", "192k", out])
    else:
        run(["ffmpeg", "-y", "-i", narr, "-af", f"{voice},{fade}", "-t", f"{total_s:.3f}", "-c:a", "aac", "-b:a", "192k", out])
    return out

# ====================== BUILD ======================
def make_video(d, workdir):
    workdir = os.path.abspath(workdir); os.makedirs(workdir, exist_ok=True)
    beats = d["beats"]; jobs = []
    for bi, b in enumerate(beats):
        lines = []
        for li, l in enumerate(b["lines"]):
            for ci, ch in enumerate(chunk_long(l["text"].split())):
                lines.append({"speaker": l["speaker"], "text": " ".join(ch)})
        b["lines"] = lines
        for li, l in enumerate(lines):
            v, r, p = STYLES[d["styles"].get(l["speaker"], "narrator")]
            l["wav"] = os.path.join(workdir, f"l_{bi}_{li}.wav")
            jobs.append({"text": l["text"], "wav": l["wav"], "voice": v, "rate": r, "pitch": p})
    nv, nr, np_ = STYLES["narrator"]
    cta = {"speaker": "Narrator", "text": CTA_TEXT, "wav": os.path.join(workdir, "cta.wav")}
    jobs.append({"text": CTA_TEXT, "wav": cta["wav"], "voice": nv, "rate": "+0%", "pitch": np_})
    tts_batch(jobs)
    for b in beats:
        for l in b["lines"]: l["dur"] = wav_dur(l["wav"])
    cta["dur"] = wav_dur(cta["wav"])
    story_frames = plan_timeline(beats); story_len = story_frames / FPS
    cta["start"] = 0.3; cta["end"] = 0.3 + cta["dur"]; c3 = outro_clicks(cta)[2]
    outro_frames = math.ceil(max(3.4, c3 + 1.1, cta["start"] + cta["dur"] + 0.8) * FPS); outro_len = outro_frames / FPS
    total = story_len + outro_len
    print(f"Timeline: story {story_len:.1f}s + outro {outro_len:.1f}s = {total:.1f}s, {len(beats)} scenes, voices: {sorted(set(d['styles'].values()))}")
    story, last_img = make_story(d, beats, story_frames, workdir)
    outro, clicks = make_outro(workdir, last_img, cta, outro_frames)
    click_wav, pop_wav = make_sfx(workdir)
    pieces = [(l["start"], l["wav"]) for b in beats for l in b["lines"]] + [(story_len + cta["start"], cta["wav"])]
    sfx = [(b["start"], pop_wav) for b in beats[1:]] + [(story_len + c, click_wav) for c in clicks]
    narr = os.path.join(workdir, "narr.wav"); build_narration(narr, total, pieces, sfx)
    mix = mix_audio(narr, total, workdir)
    vl = os.path.join(workdir, "vlist.txt"); open(vl, "w").write("".join(f"file '{p}'\n" for p in (story, outro)))
    final = os.path.join(OUT, "video.mp4")
    logo = os.path.join(ROOT, "assets", "logo.png")
    if os.path.exists(logo):   # own logo: gently bobbing + pulsing in the top-left corner for the whole video
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", vl, "-i", mix, "-loop", "1", "-i", logo, "-filter_complex",
             "[2:v]scale=170:-1,format=rgba,fade=in:st=0:d=0.5:alpha=1[lg];[0:v][lg]overlay=x=40:y='90+8*sin(t*3)':shortest=1,format=yuv420p[v]",
             "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-r", str(FPS), "-c:a", "copy", "-shortest", "-movflags", "+faststart", final])
    else:
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", vl, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", final])
    hero = os.path.join(workdir, "img1.jpg") if len(beats) > 1 else last_img
    make_thumbnail(d, hero, workdir)
    for name, tt in (("hook", 0.8), ("story", min(story_len - 1, 14.0)), ("outro", total - 1.2)):
        subprocess.run(["ffmpeg", "-y", "-ss", f"{tt:.2f}", "-i", final, "-frames:v", "1", os.path.join(OUT, f"frame_{name}.png")], capture_output=True)
    return final


def make_thumbnail(d, img, workdir):
    """Kid-friendly cover: bright hero image, big Tamil title on a colour banner, thick border, star burst."""
    ass = [ass_head()]
    ass.append(shape(1, 0, 5, 540, 1560, rrect(960, 300, 70), "00B4FF", r"\3c&HFFFFFF&\bord10"))
    ass.append(dlg(2, 0, 5, "Tam", tg(r"\an5\pos(540,1560)\fs100\c&HFFFFFF&\3c&H8A2BE2&\bord9\shad0\q0\fscx100") + d["title"]))
    ass.append(shape(1, 0, 5, 880, 330, circle(300), "00E5FF", r"\3c&HFFFFFF&\bord8\frz12"))
    ass.append(txt(2, 0, 5, "Tam", 880, 330, "8A2BE2", 78, "喈曕喁�!", r"\bord0\frz12"))
    af = os.path.join(workdir, "thumb.ass"); open(af, "w", encoding="utf-8").write("\n".join(ass) + "\n")
    out = os.path.join(OUT, "thumbnail.jpg")
    r = subprocess.run(["ffmpeg", "-y", "-i", img, "-vf",
        f"crop=iw:ih*0.93:0:0,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},eq=saturation=1.35:contrast=1.08,"
        f"drawbox=x=0:y=0:w={W}:h={H}:color=0xFFD400:t=28,ass={af}", "-frames:v", "1", "-q:v", "3", out], capture_output=True, text=True)
    if r.returncode != 0: print("thumbnail failed:", r.stderr[-400:]); return None
    return out

def set_thumbnail(token, vid, path):
    try:
        r = requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}&uploadType=media",
                          headers={"Authorization": "Bearer " + token, "Content-Type": "image/jpeg"}, data=open(path, "rb").read(), timeout=120)
        print("Thumbnail:", r.status_code, r.text[:150])
    except Exception as e: print("thumbnail upload skipped:", e)

# ====================== YOUTUBE ======================
def upload(path, d, thumb=None):
    tok = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": env("YT_CLIENT_ID"), "client_secret": env("YT_CLIENT_SECRET"),
        "refresh_token": env("YT_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=60).json()
    if "access_token" not in tok: raise SystemExit("YouTube auth failed: " + json.dumps(tok))
    desc = d["description"] + f"\n\nMoral / 喈ㄠ瘈喈む: {d['moral']}\n\n喈囙喁� 喈掄喁� 喈曕喁嵿喈┼瘓喈曕瘝 喈曕瘉喈脆喁嵿喁堗畷喁� 喈曕喁�. AI animated story for kids.\n#Shorts #TamilKidsStories #KidsStories #TamilStories"
    kids = env("MADE_FOR_KIDS", "true").lower() != "false"
    meta = {"snippet": {"title": (d["title"][:88] + " #Shorts"), "description": desc, "tags": d.get("tags", [])[:12] + ["Shorts", "Tamil kids stories"],
                        "categoryId": "1", "defaultLanguage": "ta", "defaultAudioLanguage": "ta"},
            "status": {"privacyStatus": env("YT_PRIVACY", "private"), "selfDeclaredMadeForKids": kids, "containsSyntheticMedia": True}}
    hdr = {"Authorization": "Bearer " + tok["access_token"], "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "video/mp4"}
    r = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status", headers=hdr, data=json.dumps(meta), timeout=60)
    if r.status_code != 200: raise SystemExit(f"Upload init failed {r.status_code}: {r.text[:400]}")
    with open(path, "rb") as f:
        up = requests.put(r.headers["Location"], data=f, headers={"Content-Type": "video/mp4"}, timeout=1800)
    print("Upload:", up.status_code, up.text[:200])
    if up.status_code not in (200, 201): raise SystemExit("Upload failed")
    if thumb and os.path.exists(thumb): set_thumbnail(tok["access_token"], up.json().get("id"), thumb)

def main():
    key = ist_today()
    try:
        h = load_hist(); d = make_script(h)
        print("TITLE:", d["title"], "| SLOT:", SLOT)
        json.dump(d, open(os.path.join(OUT, "script.json"), "w"), ensure_ascii=False, indent=1)
        work = os.path.join(ROOT, "work"); os.makedirs(work, exist_ok=True)
        final = make_video(d, work)
        if env("UPLOAD") == "true":
            upload(final, d, os.path.join(OUT, "thumbnail.jpg"))
            h = load_hist()
            h["titles"].append(d["title"]); h["fingerprints"].append(d["fp"])
            h.setdefault("recent_themes", []).append(d["combo"][0]); h.setdefault("recent_heroes", []).append(d["combo"][1])
            h.setdefault("done", {}).setdefault(key, []).append(SLOT)
            save_hist(h)
        else:
            print("Upload skipped (test run).")
    except BaseException:
        if env("UPLOAD") == "true":
            h = load_hist(); t = h.setdefault("tries", {}).setdefault(key, {})
            t[str(SLOT)] = int(t.get(str(SLOT), 0)) + 1; save_hist(h)
        raise

if __name__ == "__main__":
    main()
