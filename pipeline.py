import os, json, random, re, subprocess, asyncio, time, difflib, datetime, urllib.parse, wave, math
from array import array
import concurrent.futures as cf
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out"); os.makedirs(OUT, exist_ok=True)
HIST = os.path.join(ROOT, "history.json")
W, H, FPS, SR = 1920, 1080, 30, 44100
INTRO_LEN = 4.5          # logo intro seconds
OV = 0.4                 # cross-dissolve seconds between scenes

def env(k, d=""):
    return os.environ.get(k) or d

CHANNEL = env("CHANNEL_NAME", "CRIME FILES")
TAGLINE = env("CHANNEL_TAGLINE", "தமிழ் க்ரைம் கதைகள்")
SLOT = int(env("SLOT", "1") or 1)

CRIMES = ["jewellery shop robbery", "missing bank manager", "locked-room death in a lodge", "temple idol theft",
          "forged will and land grab", "hit-and-run on a highway", "kidnapping for ransom", "fake CBI officer fraud",
          "poisoned sweet box", "ATM cash van heist", "college hostel mystery", "village well body discovery"]
POOL = {1: ["missing bank manager", "locked-room death in a lodge", "hit-and-run on a highway", "poisoned sweet box",
            "college hostel mystery", "village well body discovery", "school lab fire", "textile mill owner murder",
            "farmhouse disappearance", "forged will and land grab"],
        2: ["jewellery shop robbery", "temple idol theft", "kidnapping for ransom", "fake CBI officer fraud",
            "ATM cash van heist", "train compartment theft", "insurance fraud with a fake death", "cyber loan-app blackmail",
            "bus-stand bag swap", "wedding hall gold theft"]}
PLACES = ["Madurai", "Coimbatore", "Chennai Mylapore", "Tirunelveli", "Ooty hills", "Rameswaram", "Thanjavur",
          "Salem", "Kanchipuram", "Pollachi", "Nagercoil", "Trichy", "Karaikudi", "Kodaikanal", "Vellore", "Erode", "Tiruvallur", "Hosur"]
TWISTS = ["the victim's own relative planned it", "the helpful witness was the culprit", "the crime was staged to look like an accident",
          "a tiny habit exposed the lie", "the stolen item never left the building", "two crimes were actually one",
          "the alibi video had the wrong shadow", "a servant noticed what the police missed", "the culprit returned to the scene",
          "a phone call timing did not match", "the victim was alive all along", "the informer was the mastermind"]
CLUES = ["a muddy footprint", "a torn bus ticket", "a missing bell sound", "a wrong-hand signature", "a broken watch time",
         "a smell of camphor", "a CCTV gap of two minutes", "a half-burnt letter", "a dog that did not bark", "a fresh paint patch",
         "a toll receipt", "a mismatched shoe size"]
DETECTIVES = ["Inspector Arjun", "Inspector Meena", "SI Karthik", "Retired DSP Raghavan", "Sub-Inspector Vimala", "Detective Siva", "ACP Nandhini"]
CHAPTERS = [("The Hook", "start at the most shocking moment, then set the scene"),
            ("The Crime", "what exactly happened, who the victim is, how it was discovered"),
            ("The Investigation", "investigator arrives, first observations, a false lead"),
            ("Suspects and the Clue", "three suspects with motives and alibis, then the key clue appears"),
            ("The Twist", "a shocking twist overturns the theory"),
            ("The Truth", "culprit exposed, how they were caught, a one-line moral")]

def ist_today():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d")

def load_hist():
    try: return json.load(open(HIST))
    except Exception: return {"titles": [], "fingerprints": []}

def save_hist(h):
    h["titles"] = h["titles"][-400:]; h["fingerprints"] = h["fingerprints"][-400:]
    for k in ("done", "tries"):
        if k in h: h[k] = dict(sorted(h[k].items())[-14:])
    h["recent_crimes"] = h.get("recent_crimes", [])[-10:]
    json.dump(h, open(HIST, "w"), ensure_ascii=False, indent=1)

def pick_combo(h):
    used = set(h["fingerprints"]); recent = h.get("recent_crimes", [])[-6:]
    pool = [x for x in POOL.get(SLOT, CRIMES) if x not in recent] or POOL.get(SLOT, CRIMES)
    for _ in range(300):
        c = (random.choice(pool), random.choice(PLACES), random.choice(TWISTS), random.choice(CLUES), random.choice(DETECTIVES))
        if "|".join(c) not in used: return c
    return c

def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print("COMMAND FAILED:", " ".join(str(c) for c in cmd)[:400]); print(r.stderr[-1800:])
        raise SystemExit("ffmpeg step failed")
    return r

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

def txt_of(x):
    """LLM output can be str, dict, list... always return plain text."""
    if x is None: return ""
    if isinstance(x, str): return x.strip()
    if isinstance(x, dict): return " - ".join(t for t in (txt_of(v) for v in x.values()) if t)
    if isinstance(x, (list, tuple)): return "; ".join(t for t in (txt_of(v) for v in x) if t)
    return str(x)

def beat_words(d):
    return sum(len(txt_of(b.get("voiceover", "")).split()) for b in d.get("beats", []) if isinstance(b, dict))

def check_part(d, late):
    b = d.get("beats")
    if not isinstance(b, list) or len(b) < 4: return "Return 5 or 6 beats."
    for x in b:
        if not isinstance(x, dict) or not txt_of(x.get("voiceover")) or not txt_of(x.get("scene")): return "Every beat needs both voiceover and scene."
    n = beat_words(d)
    if n < (60 if late else 90): return f"Your previous answer had only {n} Tamil words in total. Write 100 to 125 Tamil words across the beats."
    if n > 160: return f"Too long ({n} words). Keep it to 100-125 Tamil words in total."
    return None

def make_script(h):
    combo = pick_combo(h); code = random.randint(1000, 9999)
    avoid = "; ".join(h["titles"][-40:]) or "none"
    ing = f"Crime: {combo[0]} | Place: {combo[1]} | Twist: {combo[2]} | Key clue: {combo[3]} | Investigator: {combo[4]} | Variation code: {code}"
    outline = llm_json(f"""You plan an ORIGINAL, fully fictional SOLVED crime thriller (no real people/cases/brands, no gore, no sexual content) for a gripping 4-5 minute Tamil YouTube video.
Ingredients (all must appear): {ing}
Do NOT repeat these earlier titles/ideas: {avoid}
Return JSON only: title (Tamil, curiosity-driven, max 80 chars), description (Tamil, 3 short lines + hashtags), tags (8 strings),
characters (list of 5 short English descriptions: investigator, victim, 3 suspects - consistent looks, for image prompts),
setting (one English sentence describing the place's look), plot (English, 120-180 words: full story incl. culprit, motive, clue, twist, how caught),
thumbnail_prompt (English, dramatic cinematic 3D cartoon scene, no text).""")
    for k in ("title", "description", "setting", "plot", "thumbnail_prompt"):
        outline[k] = txt_of(outline.get(k))
    if not outline["title"] or not outline["plot"]: raise SystemExit("Outline missing title/plot")
    outline["thumbnail_prompt"] = outline["thumbnail_prompt"] or ("dramatic cinematic crime scene, " + outline["setting"])
    tg_ = outline.get("tags", [])
    outline["tags"] = [txt_of(t) for t in tg_] if isinstance(tg_, list) else [t.strip() for t in txt_of(tg_).replace("#", "").split(",") if t.strip()]
    if max([difflib.SequenceMatcher(None, outline["title"], t).ratio() for t in h["titles"]] or [0]) > 0.7:
        return make_script(h)
    chars = "; ".join(t for t in (txt_of(c) for c in (outline.get("characters") if isinstance(outline.get("characters"), list) else [outline.get("characters")])) if t)
    parts = []; recap = ""
    for i, (name, beat) in enumerate(CHAPTERS):
        d = llm_json(f"""Write part {i+1} of {len(CHAPTERS)} ("{name}": {beat}) of a Tamil crime-story narration, as a series of BEATS.
Story plot (secret - reveal only at the proper part): {outline['plot']}
Characters (keep consistent): {chars}
Setting: {outline['setting']}
Story so far: {recap or 'nothing yet'}
Style: gripping storyteller, simple conversational spoken Tamil (Tamil script, avoid heavy literary words), very short punchy sentences (max 12 words), vivid details, an occasional question to the listener, a cliffhanger at the end of the part. No greetings after part 1. Do not conclude the story before the last part.
Return JSON only: beats = list of 5 or 6 objects, in order. Each beat has:
  voiceover: 2 short Tamil sentences (about 18-22 words) narrating one moment,
  scene: ONE English image prompt that shows EXACTLY what that voiceover describes (cinematic 3D animated cartoon, dramatic lighting, mention the character looks from the list, no text, no logos, no real people).
Total across all beats: 100-125 Tamil words. Also return recap (one English sentence of what happened in this part).""", check=check_part)
        beats = [{"voiceover": txt_of(b["voiceover"]), "scene": txt_of(b["scene"])} for b in d["beats"][:6]]
        parts.append({"name": name, "beats": beats}); recap += " " + txt_of(d.get("recap"))
    outline["parts"] = parts; outline["fp"] = "|".join(combo)
    return outline

# ====================== VOICE ======================
CTA = ["கதை பிடிச்சிருந்தா, ஒரு லைக் போடுங்க!", "நம்ம சேனலை சப்ஸ்கிரைப் பண்ணுங்க!", "பெல் ஐகானை அழுத்த மறக்காதீங்க!"]

def chunk_long(words, mx=18):
    parts = []
    while len(words) > mx:
        idx = next((i for i in range(mx, 5, -1) if words[i - 1].endswith(",")), mx - 2)
        parts.append(words[:idx]); words = words[idx:]
    parts.append(words); return parts

def split_sentences(text):
    text = re.sub(r"\s+", " ", text.strip()); out = []
    for s in re.split(r"(?<=[.!?।…])\s+", text):
        s = s.strip()
        if not s: continue
        for w in chunk_long(s.split()):
            t = " ".join(w)
            if out and len(w) < 3: out[-1] += " " + t
            else: out.append(t)
    return out or [text]

async def _edge_one(text, path, sem):
    import edge_tts
    voice = env("TTS_VOICE", "ta-IN-ValluvarNeural")
    async with sem:
        for a in range(5):
            try:
                await edge_tts.Communicate(text, voice, rate=env("TTS_RATE", "+8%"), pitch=env("TTS_PITCH", "-2Hz")).save(path)
                if os.path.getsize(path) > 800: return
            except Exception as e:
                print("tts retry", a, str(e)[:80]); await asyncio.sleep(2 * (a + 1))
        raise SystemExit("TTS failed for: " + text[:40])

def _eleven_one(text, path):
    vid = env("ELEVEN_VOICE_ID")
    r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=mp3_44100_128",
                      headers={"xi-api-key": env("ELEVEN_API_KEY"), "Content-Type": "application/json"},
                      json={"text": text, "model_id": "eleven_multilingual_v2",
                            "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35, "use_speaker_boost": True}}, timeout=120)
    if r.status_code != 200: raise SystemExit(f"ElevenLabs error {r.status_code}: {r.text[:200]}")
    open(path, "wb").write(r.content)

def _to_wav(mp3, wav):
    trim = "silenceremove=start_periods=1:start_duration=0.02:start_threshold=-45dB"
    r = subprocess.run(["ffmpeg", "-y", "-i", mp3, "-af", f"{trim},areverse,{trim},areverse", "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", wav], capture_output=True)
    if r.returncode != 0 or wav_dur(wav) < 0.25:
        run(["ffmpeg", "-y", "-i", mp3, "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", wav])

def wav_dur(p):
    with wave.open(p) as w: return w.getnframes() / w.getframerate()

def tts_batch(jobs):
    mp3s = [(t, w + ".mp3") for t, w in jobs]
    if env("ELEVEN_API_KEY") and env("ELEVEN_VOICE_ID"):
        for t, m in mp3s: _eleven_one(t, m)
    else:
        async def go():
            sem = asyncio.Semaphore(4)
            await asyncio.gather(*[_edge_one(t, m, sem) for t, m in mp3s])
        asyncio.run(go())
    with cf.ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda x: _to_wav(x[1], x[0][1]), zip(jobs, mp3s)))

# ====================== TIMELINE ======================
def plan_timeline(d):
    """Place every sentence on a timeline from measured audio durations; every beat (=one image) spans exactly its own sentences."""
    t = 0.3; beats = []; bi = 0
    for pi, p in enumerate(d["parts"]):
        for k, b in enumerate(p["beats"]):
            b["start"] = t
            for s in b["sents"]:
                s["start"] = t; t += s["dur"]; s["end"] = t; t += 0.18
            if k == len(p["beats"]) - 1: t += 0.4
            b["end"] = t; b["part"] = pi; b["first_in_part"] = (k == 0); beats.append(b)
    story_frames = math.ceil((t + 0.5) * FPS)
    for i, b in enumerate(beats):
        b["f0"] = 0 if i == 0 else round(b["start"] * FPS)
        b["f1"] = story_frames if i == len(beats) - 1 else round(beats[i + 1]["start"] * FPS)
    return beats, story_frames

# ====================== ASS (captions / intro / outro) ======================
def ts(t):
    cs = int(round(max(t, 0) * 100)); return f"{cs//360000}:{cs//6000%60:02d}:{cs//100%60:02d}.{cs%100:02d}"

def ass_head(w, h):
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Cap,Noto Sans Tamil,58,&H0000F0FF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,140,140,64,1
Style: Chap,DejaVu Sans,40,&H0000D4FF,&H00FFFFFF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,3,3,0,7,50,50,50,1
Style: Thumb,Noto Sans Tamil,110,&H0000F0FF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,8,3,2,60,60,70,1
Style: Shape,DejaVu Sans,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: Txt,DejaVu Sans,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,3,1,5,0,0,0,1
Style: Tam,Noto Sans Tamil,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,3,1,5,0,0,0,1

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
CIRCLE = circle(60)
BIGCIRCLE = circle(140)
THUMB = ("m 0 26 l 12 26 l 12 58 l 0 58 m 16 28 l 25 6 b 27 2 33 2 36 5 b 38 8 38 12 36 16 l 33 22 l 52 22 b 57 22 60 26 59 31 "
         "l 55 50 b 54 55 50 58 45 58 l 16 58 l 16 28")
BELL = ("m 30 2 b 40 2 46 10 46 22 l 46 36 l 54 46 l 54 50 l 6 50 l 6 46 l 14 36 l 14 22 b 14 10 20 2 30 2 "
        "m 23 53 b 24 59 36 59 37 53 l 23 53")
POINTER = "m 0 0 l 0 40 l 10 31 l 17 46 l 24 43 l 17 28 l 30 28 l 0 0"

def caption_events(sents, off=0.0):
    ev = []
    for s in sents:
        words = s["text"].split(); wts = [max(1, len(x)) for x in words]; tot = float(sum(wts)); dur = s["dur"]
        chunks = []; cur = []; cl = 0
        for i, x in enumerate(words):
            if cur and (cl + len(x) + 1 > 34 or len(cur) >= 6): chunks.append(cur); cur = []; cl = 0
            cur.append(i); cl += len(x) + 1
        if cur: chunks.append(cur)
        acc = 0; starts = []
        for wt in wts: starts.append(acc / tot * dur); acc += wt
        ends = starts[1:] + [dur]
        for ci, ch in enumerate(chunks):
            st = s["start"] + starts[ch[0]] + off
            en = (s["end"] + 0.12 + off) if ci == len(chunks) - 1 else (s["start"] + ends[ch[-1]] + off)
            k = "".join(r"{\kf%d}%s " % (max(1, round((ends[i] - starts[i]) * 100)), words[i]) for i in ch)
            ev.append(dlg(0, st, en, "Cap", k.strip()))
    return ev

# ====================== IMAGES ======================
STYLE = ", 3D animated cartoon movie style, cinematic dramatic lighting, dark suspenseful mood, wide 16:9 composition, highly detailed, no text"
def get_image(prompt, path, prev, size=(1280, 720)):
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt + STYLE) + f"?width={size[0]}&height={size[1]}&nologo=true&seed={random.randint(1,999999)}"
    for i in range(5):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 5000 and r.headers.get("content-type", "").startswith("image"):
                open(path, "wb").write(r.content); return
        except Exception as e: print("img retry", e)
        time.sleep(4 * (i + 1))
    if prev and os.path.exists(prev): open(path, "wb").write(open(prev, "rb").read())
    else: run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x101820:s={size[0]}x{size[1]}", "-frames:v", "1", path])

# ====================== VIDEO PARTS ======================
VENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-r", str(FPS), "-video_track_timescale", "15360", "-an"]

def motion(kind, F):
    c = {"x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"}
    if kind == 0: z = f"1+0.20*on/{F}"
    elif kind == 1: z = f"1.20-0.20*on/{F}"
    elif kind == 2: z = "1.16"; c["x"] = f"(iw-iw/zoom)*on/{F}"
    elif kind == 3: z = "1.16"; c["x"] = f"(iw-iw/zoom)*(1-on/{F})"
    elif kind == 4: z = f"1+0.25*on/{F}"; c["x"] = "iw*0.3-(iw/zoom)*0.3"; c["y"] = "ih*0.35-(ih/zoom)*0.35"
    else: z = "1.16"; c["y"] = f"(ih-ih/zoom)*on/{F}"
    return f"zoompan=z='{z}':x='{c['x']}':y='{c['y']}':d={F}:s={W}x{H}:fps={FPS}"

def render_clip(a):
    img, out, F, kind = a
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", img, "-vf",
         f"crop=iw:ih*0.93:0:0,scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160,{motion(kind, F)},format=yuv420p",
         "-frames:v", str(F), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "17", "-threads", "2", out])
    return out

def make_story(d, beats, story_frames, workdir):
    imgs = []; prev = None
    for i, b in enumerate(beats):
        p = os.path.join(workdir, f"img{i}.jpg"); get_image(b["scene"], p, prev); imgs.append(p); prev = p
    hf = int(OV * FPS / 2); N = len(beats)
    jobs = []
    for i, b in enumerate(beats):
        n = b["f1"] - b["f0"]
        F = n + (hf if i in (0, N - 1) else 2 * hf)       # overlap frames so cross-dissolves stay inside the clips
        if N == 1: F = n
        jobs.append((imgs[i], os.path.join(workdir, f"clip{i}.mp4"), F, (i * 5 + 2) % 6))
    with cf.ThreadPoolExecutor(3) as ex: clips = list(ex.map(render_clip, jobs))
    # captions + chapter labels
    ass = [ass_head(W, H)]
    for b in beats:
        if b["first_in_part"]:
            lab = f"{b['part']+1}/{len(d['parts'])}  {d['parts'][b['part']]['name']}"
            ass.append(dlg(1, b["start"], b["start"] + 4, "Chap", tg(r"\fad(250,350)") + lab))
        ass += caption_events(b["sents"])
    assf = os.path.join(workdir, "story.ass"); open(assf, "w", encoding="utf-8").write("\n".join(ass) + "\n")
    # cross-dissolve chain (transition centred on every beat start so the new picture arrives with the new narration)
    fc = []; last = "0:v"
    for i in range(1, N):
        off = (beats[i]["f0"] - hf) / FPS
        tr = "fadeblack" if beats[i]["first_in_part"] else "fade"
        fc.append(f"[{last}][{i}:v]xfade=transition={tr}:duration={OV}:offset={off:.4f}[x{i}]"); last = f"x{i}"
    today = datetime.datetime.strptime(ist_today(), "%Y-%m-%d").strftime("%d %b %Y")
    tail = (f"[{last}]tpad=stop_mode=clone:stop_duration=2,eq=contrast=1.06:saturation=1.12:gamma=0.95,vignette=PI/4.5,noise=alls=4:allf=t,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='{CHANNEL}  |  SOLVED CASE  |  {today}':"
            f"fontcolor=white@0.8:fontsize=26:x=w-text_w-40:y=36:box=1:boxcolor=black@0.45:boxborderw=8,"
            f"ass={assf},fade=t=out:st={story_frames/FPS-0.3:.3f}:d=0.3[vout]")
    fc.append(tail) if N > 1 else fc.append(tail.replace(f"[{last}]", "[0:v]", 1))
    out = os.path.join(workdir, "story.mp4")
    cmd = ["ffmpeg", "-y"]
    for c in clips: cmd += ["-i", c]
    run(cmd + ["-filter_complex", ";".join(fc), "-map", "[vout]", "-frames:v", str(story_frames)] + VENC + [out])
    return out, imgs[-1]

def make_intro(workdir, logo):
    ay = 700 if logo else 470
    ass = [ass_head(W, H)]
    ass.append(dlg(0, 0.3, 1.9, "Shape", tg(r"\an7\move(-300,0,2300,0,300,1500)\c&HFFFFFF&\alpha&HC8&\blur25\bord0\p1") + "m 100 0 l 240 0 l 140 1080 l 0 1080" + tg(r"\p0")))
    ass.append(dlg(1, 0, INTRO_LEN, "Txt", tg(r"\an5\pos(960,%d)\fs38\c&HCCCCCC&\alpha&HFF&\t(200,700,\alpha&H00&)\fad(0,300)" % (ay - 150))
                   + tg(r"\c&H2020E0&") + "●" + tg(r"\c&HCCCCCC&") + f" CASE FILE No. {random.randint(1000, 9999)}   |   SOLVED"))
    ass.append(dlg(1, 0, INTRO_LEN, "Txt", tg(r"\an5\pos(960,%d)\fs150\fsp10\c&HFFFFFF&\fad(450,300)\fscx125\fscy125\blur12\t(0,800,\fscx100\fscy100\blur0)" % ay) + CHANNEL))
    ass.append(shape(1, 0.5, INTRO_LEN, 960, ay + 95, "m 0 0 l 1000 0 l 1000 6 l 0 6", "00C8FF", r"\fscx0\fad(0,300)\t(0,800,\fscx100)"))
    ass.append(dlg(1, 0.5, INTRO_LEN, "Tam", tg(rf"\an5\pos(960,{ay+170})\fs62\c&H00C8FF&\alpha&HFF&\t(1100,1700,\alpha&H00&)\fad(0,300)") + TAGLINE))
    af = os.path.join(workdir, "intro.ass"); open(af, "w", encoding="utf-8").write("\n".join(ass) + "\n")
    out = os.path.join(workdir, "intro.mp4"); n = int(INTRO_LEN * FPS)
    bg = f"format=yuv420p,geq=lum='10+34*exp(-(pow(X-960,2)+pow(Y-540,2))/500000)':cb=140:cr=120,noise=alls=9:allf=t,vignette=PI/3"
    fade = f"ass={af},fade=t=out:st={INTRO_LEN-0.3}:d=0.3"
    if logo:
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x06080c:s={W}x{H}:r={FPS}:d={INTRO_LEN}", "-loop", "1", "-i", logo, "-filter_complex",
             f"[0:v]{bg}[b];[1:v]scale=-1:360,format=rgba,fade=t=in:st=0.3:d=0.9:alpha=1[lg];[b][lg]overlay=(W-w)/2:110:shortest=1,{fade}[v]",
             "-map", "[v]", "-frames:v", str(n)] + VENC + [out])
    else:
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x06080c:s={W}x{H}:r={FPS}:d={INTRO_LEN}", "-vf", f"{bg},{fade}", "-frames:v", str(n)] + VENC + [out])
    return out

def make_outro(workdir, last_img, cta, outro_frames):
    """cta: list of 3 dicts with start/dur (seconds, relative to outro start). Returns video path and click times."""
    L = outro_frames / FPS; ass = [ass_head(W, H)]
    # headline
    ass.append(txt(2, 0.1, L, "Txt", 960, 240, "FFFFFF", 92, "LIKE  •  SHARE  •  SUBSCRIBE", r"\fad(300,300)\fscx80\fscy80\t(0,400,\fscx100\fscy100)"))
    ass.append(dlg(2, 1.0, L, "Tam", tg(r"\an5\pos(960,830)\fs58\c&H00C8FF&\fad(400,300)") + "தினமும் புதிய க்ரைம் கதைகள்!"))
    # button geometry
    LX, SX, BX, Y = 540, 1050, 1480, 520
    clicks = []
    for k, c in enumerate(cta): clicks.append(c["start"] + min(0.9, c["dur"] * 0.45) + 0.2)
    c1, c2, c3 = clicks
    # LIKE
    for (a, b, col, label, icon_col) in [(0.1, c1, "3A3A3A", "LIKE", "FFFFFF"), (c1, L, "FFA63E", "LIKED", "FFFFFF")]:
        ex = r"\fad(250,0)" if a == 0.1 else r"\fscx112\fscy112\t(0,200,\fscx100\fscy100)"
        ass.append(shape(1, a, b, LX, Y, rrect(380, 140, 70), col, ex))
        ass.append(shape(2, a, b, LX - 110, Y - 4, THUMB, icon_col, ex))
        ass.append(txt(3, a, b, "Txt", LX + 50, Y, "FFFFFF", 56, label, ex))
    # SUBSCRIBE
    for (a, b, col, label, size) in [(0.1, c2, "0000FF", "SUBSCRIBE", 56), (c2, L, "4A4A4A", "SUBSCRIBED ✓", 46)]:
        ex = r"\fad(250,0)" if a == 0.1 else r"\fscx108\fscy108\t(0,200,\fscx100\fscy100)"
        ass.append(shape(1, a, b, SX, Y, rrect(560, 140, 70), col, ex))
        ass.append(txt(3, a, b, "Txt", SX, Y, "FFFFFF", size, label, ex))
    # BELL
    ass.append(shape(1, 0.1, c3, BX, Y, BIGCIRCLE, "4A4A4A", r"\fad(250,0)"))
    ass.append(shape(2, 0.1, c3, BX, Y, BELL, "FFFFFF", r"\fad(250,0)\fscx135\fscy135"))
    shake = r"\t(0,90,\frz18)\t(90,180,\frz-18)\t(180,270,\frz14)\t(270,360,\frz-14)\t(360,450,\frz8)\t(450,540,\frz0)"
    ass.append(shape(1, c3, L, BX, Y, BIGCIRCLE, "00C8FF", r"\fscx108\fscy108\t(0,200,\fscx100\fscy100)"))
    ass.append(shape(2, c3, L, BX, Y, BELL, "000000", r"\fscx135\fscy135" + shake))
    # pointer + click ripples
    pts = [(1850, 960), (LX + 40, Y + 20), (SX + 80, Y + 20), (BX + 10, Y + 25)]
    legs = [(0.2, c1 - 0.15), (c1 + 0.3, min(c1 + 1.0, c2 - 0.1)), (c2 + 0.3, min(c2 + 1.0, c3 - 0.1))]
    for i, (s0, e0) in enumerate(legs):
        e0 = max(e0, s0 + 0.3)
        ass.append(dlg(5, s0, e0, "Shape", tg(rf"\an7\move({pts[i][0]},{pts[i][1]},{pts[i+1][0]},{pts[i+1][1]})\c&HFFFFFF&\3c&H000000&\bord2\shad0\p1") + POINTER + tg(r"\p0")))
        ass.append(dlg(5, e0, (clicks[i]), "Shape", tg(rf"\an7\pos({pts[i+1][0]},{pts[i+1][1]})\c&HFFFFFF&\3c&H000000&\bord2\shad0\p1") + POINTER + tg(r"\p0")))
        ass.append(shape(4, clicks[i], clicks[i] + 0.4, pts[i + 1][0] + 6, pts[i + 1][1] + 6, CIRCLE, "FFFFFF", r"\alpha&H50&\fscx30\fscy30\t(0,380,\fscx230\fscy230\alpha&HFF&)"))
        ass.append(dlg(5, clicks[i], clicks[i] + 0.6, "Shape", tg(rf"\an7\pos({pts[i+1][0]},{pts[i+1][1]})\c&HFFFFFF&\3c&H000000&\bord2\shad0\p1") + POINTER + tg(r"\p0")))
    for c in cta: ass += caption_events([{"text": c["text"], "start": c["start"], "end": c["start"] + c["dur"], "dur": c["dur"]}])
    af = os.path.join(workdir, "outro.ass"); open(af, "w", encoding="utf-8").write("\n".join(ass) + "\n")
    out = os.path.join(workdir, "outro.mp4")
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", last_img, "-vf",
         f"crop=iw:ih*0.93:0:0,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=22:2,eq=brightness=-0.30:saturation=0.8,fade=t=in:d=0.4,ass={af},fade=t=out:st={L-0.4:.2f}:d=0.4",
         "-frames:v", str(outro_frames)] + VENC + [out])
    return out, clicks

# ====================== AUDIO ======================
def make_sfx(workdir):
    intro = os.path.join(workdir, "intro_sfx.wav"); click = os.path.join(workdir, "click.wav")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=d=1.4:c=pink:r=44100:a=0.6", "-f", "lavfi", "-i", "sine=f=48:d=3.5:r=44100", "-f", "lavfi", "-i", "sine=f=96:d=3.5:r=44100",
         "-filter_complex", "[0]highpass=f=500,afade=t=in:st=0:d=1.2,afade=t=out:st=1.2:d=0.2,volume=0.7[n];[1]afade=t=out:st=0.2:d=3.2,adelay=1300|1300[b1];[2]volume=0.4,afade=t=out:st=0.2:d=2.4,adelay=1300|1300[b2];"
         f"[n][b1][b2]amix=inputs=3:normalize=0,apad=whole_dur={INTRO_LEN},atrim=0:{INTRO_LEN},aformat=sample_fmts=s16:channel_layouts=mono:sample_rates=44100", "-c:a", "pcm_s16le", intro])
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=f=1000:d=0.07:r=44100", "-af", "afade=t=out:st=0.01:d=0.06,volume=0.5,aformat=sample_fmts=s16:channel_layouts=mono", "-c:a", "pcm_s16le", click])
    return intro, click

def build_narration(path, total_s, pieces, clicks, click_wav):
    buf = array("h", bytes(2 * int(round(total_s * SR))))
    for start_s, wav in pieces:
        with wave.open(wav) as w:
            a = array("h"); a.frombytes(w.readframes(w.getnframes()))
        s = int(round(start_s * SR)); e = min(len(buf), s + len(a)); buf[s:e] = a[: e - s]
    with wave.open(click_wav) as w:
        ck = array("h"); ck.frombytes(w.readframes(w.getnframes()))
    for t in clicks:
        s = int(round(t * SR))
        for i, v in enumerate(ck):
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
    voice = ("highpass=f=70,equalizer=f=200:t=q:w=1.2:g=2,equalizer=f=3200:t=q:w=1:g=3,"
             "acompressor=threshold=0.09:ratio=3:attack=5:release=120:makeup=2,loudnorm=I=-15:TP=-1.5:LRA=9")
    fade = f"afade=t=out:st={total_s-1.5:.2f}:d=1.5"
    if bgm:
        fc = (f"[0:a]{voice},asplit=2[v][vs];[1:a]volume=0.32[b];[b][vs]sidechaincompress=threshold=0.02:ratio=9:attack=20:release=600[bd];"
              f"[v][bd]amix=inputs=2:duration=first:normalize=0,{fade}[a]")
        run(["ffmpeg", "-y", "-i", narr, "-stream_loop", "-1", "-i", bgm, "-filter_complex", fc, "-map", "[a]", "-t", f"{total_s:.3f}", "-c:a", "aac", "-b:a", "192k", out])
    else:
        run(["ffmpeg", "-y", "-i", narr, "-af", f"{voice},{fade}", "-t", f"{total_s:.3f}", "-c:a", "aac", "-b:a", "192k", out])
    return out

# ====================== BUILD ======================
def find_logo():
    folder = os.path.join(ROOT, "assets")
    if not os.path.isdir(folder): return None
    for f in sorted(os.listdir(folder)):
        if f.lower().startswith("logo") and f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")): return os.path.join(folder, f)
    return None

def make_video(d, workdir):
    workdir = os.path.abspath(workdir); os.makedirs(workdir, exist_ok=True)
    jobs = []
    for pi, p in enumerate(d["parts"]):
        for bi, b in enumerate(p["beats"]):
            b["sents"] = [{"text": t, "wav": os.path.join(workdir, f"s_{pi}_{bi}_{si}.wav")} for si, t in enumerate(split_sentences(b["voiceover"]))]
            jobs += [(s["text"], s["wav"]) for s in b["sents"]]
    cta = [{"text": t, "wav": os.path.join(workdir, f"cta{i}.wav")} for i, t in enumerate(CTA)]
    jobs += [(c["text"], c["wav"]) for c in cta]
    tts_batch(jobs)
    for p in d["parts"]:
        for b in p["beats"]:
            for s in b["sents"]: s["dur"] = wav_dur(s["wav"])
    for c in cta: c["dur"] = wav_dur(c["wav"])
    beats, story_frames = plan_timeline(d); story_len = story_frames / FPS
    # outro timeline
    t = 0.6
    for c in cta: c["start"] = t; t += c["dur"] + 0.3
    est_clicks = [c["start"] + min(0.9, c["dur"] * 0.45) + 0.2 for c in cta]
    outro_len = max(9.0, t + 1.3, est_clicks[-1] + 2.0); outro_frames = math.ceil(outro_len * FPS); outro_len = outro_frames / FPS
    total = INTRO_LEN + story_len + outro_len
    print(f"Timeline: intro {INTRO_LEN:.1f}s + story {story_len:.1f}s + outro {outro_len:.1f}s = {total:.1f}s ({total/60:.2f} min), {len(beats)} scenes")
    # visuals
    story, last_img = make_story(d, beats, story_frames, workdir)
    intro = make_intro(workdir, find_logo())
    outro, clicks = make_outro(workdir, last_img, cta, outro_frames)
    # audio
    intro_sfx, click_wav = make_sfx(workdir)
    base = INTRO_LEN
    pieces = [(0.0, intro_sfx)] + [(base + s["start"], s["wav"]) for b in beats for s in b["sents"]]
    ob = INTRO_LEN + story_len
    pieces += [(ob + c["start"], c["wav"]) for c in cta]
    narr = os.path.join(workdir, "narr.wav")
    build_narration(narr, total, pieces, [ob + c for c in clicks], click_wav)
    mix = mix_audio(narr, total, workdir)
    vl = os.path.join(workdir, "vlist.txt"); open(vl, "w").write("".join(f"file '{p}'\n" for p in (intro, story, outro)))
    final = os.path.join(OUT, "video.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", vl, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", final])
    for name, tt in (("intro", 2.6), ("story", INTRO_LEN + 14.0), ("outro", total - outro_len + 5.5)):
        subprocess.run(["ffmpeg", "-y", "-ss", f"{tt:.2f}", "-i", final, "-frames:v", "1", os.path.join(OUT, f"frame_{name}.png")], capture_output=True)
    marks = [(0.0 if i == 0 else INTRO_LEN + next(b["start"] for b in beats if b["part"] == i and b["first_in_part"]), p["name"]) for i, p in enumerate(d["parts"])]
    return final, marks

def make_thumbnail(d, workdir):
    img = os.path.join(workdir, "thumb_src.jpg"); get_image(d["thumbnail_prompt"], img, None)
    a = os.path.join(workdir, "thumb.ass")
    open(a, "w", encoding="utf-8").write(ass_head(1280, 720) + dlg(0, 0, 5, "Thumb", d["title"][:38]) + "\n")
    out = os.path.join(OUT, "thumbnail.jpg")
    r = subprocess.run(["ffmpeg", "-y", "-i", img, "-vf", f"crop=iw:ih*0.93:0:0,scale=1280:720,drawbox=x=0:y=ih*0.55:w=iw:h=ih*0.45:color=black@0.45:t=fill,ass={a}", "-frames:v", "1", "-q:v", "3", out], capture_output=True)
    return out if r.returncode == 0 else None

# ====================== YOUTUBE ======================
def upload(path, d, thumb, marks):
    tok = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": env("YT_CLIENT_ID"), "client_secret": env("YT_CLIENT_SECRET"),
        "refresh_token": env("YT_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=60).json()
    if "access_token" not in tok: raise SystemExit("YouTube auth failed: " + json.dumps(tok))
    chap = "\n".join(f"{int(t//60):02d}:{int(t%60):02d} {n}" for t, n in marks)
    desc = d["description"] + "\n\nChapters:\n" + chap + "\n\nஇது ஒரு கற்பனைக் கதை. All characters and events are fictional.\n#CrimeStory #Tamil #TamilCrime"
    meta = {"snippet": {"title": d["title"][:95], "description": desc, "tags": d.get("tags", [])[:12], "categoryId": "24", "defaultLanguage": "ta", "defaultAudioLanguage": "ta"},
            "status": {"privacyStatus": env("YT_PRIVACY", "private"), "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}
    hdr = {"Authorization": "Bearer " + tok["access_token"], "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "video/mp4"}
    r = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status", headers=hdr, data=json.dumps(meta), timeout=60)
    if r.status_code != 200: raise SystemExit(f"Upload init failed {r.status_code}: {r.text[:400]}")
    with open(path, "rb") as f:
        up = requests.put(r.headers["Location"], data=f, headers={"Content-Type": "video/mp4"}, timeout=3000)
    print("Upload:", up.status_code, up.text[:200])
    if up.status_code not in (200, 201): raise SystemExit("Upload failed")
    if thumb and os.path.exists(thumb):
        vid = up.json().get("id")
        tr = requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}", headers={"Authorization": "Bearer " + tok["access_token"], "Content-Type": "image/jpeg"}, data=open(thumb, "rb"), timeout=120)
        print("Thumbnail:", tr.status_code, tr.text[:150])

def main():
    key = ist_today()
    try:
        h = load_hist(); d = make_script(h)
        print("TITLE:", d["title"], "| SLOT:", SLOT)
        json.dump(d, open(os.path.join(OUT, "script.json"), "w"), ensure_ascii=False, indent=1)
        work = os.path.join(ROOT, "work"); os.makedirs(work, exist_ok=True)
        final, marks = make_video(d, work)
        thumb = make_thumbnail(d, work)
        if env("UPLOAD") == "true":
            upload(final, d, thumb, marks)
            h = load_hist()
            h["titles"].append(d["title"]); h["fingerprints"].append(d["fp"])
            h.setdefault("recent_crimes", []).append(d["fp"].split("|")[0])
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
