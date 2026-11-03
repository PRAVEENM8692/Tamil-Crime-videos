"""Tamil kids story videos. Every AI step (script, voices, video clips) is Google Gemini / Veo called directly through the Gemini API (GEMINI_API_KEY)."""
import os, json, base64, random, re, subprocess, time, difflib, datetime, wave, math
from array import array
import concurrent.futures as cf
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT, WORK, HIST = os.path.join(ROOT, "out"), os.path.join(ROOT, "work"), os.path.join(ROOT, "history.json")
os.makedirs(OUT, exist_ok=True); os.makedirs(WORK, exist_ok=True)
W, H, FPS, SR = 1920, 1080, 24, 44100      # normal YouTube video, 16:9 full HD
VENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS), "-video_track_timescale", "15360", "-an"]

def env(k, d=""):
    return os.environ.get(k) or d

CHANNEL = env("CHANNEL_NAME", "Tamil Kids Story")
SLOT = int(env("SLOT", "1") or 1)
LLM_MODEL = env("LLM_MODEL", "gemini-3.8-flash")
VIDEO_MODEL = env("VIDEO_MODEL", "gemini-omni-1.1-flash")      # Veo previews were shut down; Omni picks its own clip length (about 3-10 s)
CLIP_LENGTHS, MAX_SLOW = (4, 6, 8), 1.25                     # a clip may be slowed up to 1.25x, so shorter (cheaper) clips can cover a scene

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


# Gemini voice + acting note per character style. Override with VOICE_MAP (JSON) or NARRATOR_VOICE.
VOICES = {
    "narrator":       ("Charon",        "a warm friendly storyteller telling a bedtime story to a small child, clear and a little slow"),
    "boy":            ("Puck",          "a cheerful excited little boy"),
    "girl":           ("Leda",          "a sweet playful little girl"),
    "old_man":        ("Algieba",       "a kind old grandfather, slow and gentle"),
    "old_woman":      ("Gacrux",        "a loving grandmother, soft and gentle"),
    "big_deep":       ("Algenib",       "a big deep friendly voice, slow and booming but kind"),
    "squeaky":        ("Sadachbia",     "a tiny squeaky high-pitched voice, quick and funny"),
    "cheerful_man":   ("Zubenelgenubi", "a cheerful friendly young man"),
    "cheerful_woman": ("Aoede",         "a cheerful friendly young woman"),
}
def voice_for(style):
    v, note = VOICES.get(style, VOICES["narrator"])
    try: v = json.loads(env("VOICE_MAP", "{}")).get(style, v)
    except Exception: pass
    if style == "narrator" and env("NARRATOR_VOICE"): v = env("NARRATOR_VOICE")
    return v, note

def assign_voices(chars):
    used, styles = set(), {}
    for c in chars:
        st = txt_of(c.get("voice")).lower().replace(" ", "_").replace("-", "_")
        if st not in VOICES or st == "narrator" or st in used:
            st = next((p for p in STYLE_ORDER if p not in used), "boy")
        used.add(st); styles[c["name"]] = st
    styles["Narrator"] = "narrator"
    colors = {n: COLORS[i % len(COLORS)] for i, n in enumerate(c["name"] for c in chars)}; colors["Narrator"] = NARR_COLOR
    return styles, colors


STYLE_ORDER = ["boy", "girl", "old_man", "old_woman", "big_deep", "squeaky", "cheerful_man", "cheerful_woman"]

COLORS = ["00F0FF", "B469FF", "FFE500", "0098FF", "5CFF7C", "FF8AE8"]

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


# ====================== GEMINI API (text / voice / Veo video, direct REST, key = GEMINI_API_KEY) ======================
API = env("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta")
KEY = env("GEMINI_API_KEY")
# Tier 1 allows 10 requests/min and 100/day PER MODEL, so voices rotate over several TTS models (same voices, 3x the quota)
TTS_MODELS = [m.strip() for m in env("TTS_MODEL", "gemini-3.8-flash-tts,gemini-3.8-flash-lite-tts,gemini-3.1-flash-tts-preview").split(",") if m.strip()]
POOL = {"chat": int(env("CHAT_CONCURRENCY", "5")), "tts": int(env("TTS_CONCURRENCY", "2")), "vid": int(env("VID_CONCURRENCY", "3"))}
_stop = {}      # task -> reason; set on errors that retrying cannot fix (bad key, no quota, unknown model)

def _call(method, url, **kw):
    r = requests.request(method, url, headers={"x-goog-api-key": KEY}, timeout=kw.pop("timeout", 120), **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} {r.text[:900]}")
    return r

def _wav_write(path, pcm, rate=24000):
    with wave.open(path, "wb") as w: w.setnframes(0); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)

def _do_chat(j):
    r = _call("POST", f"{API}/models/{j['model']}:generateContent", json={"contents": [{"parts": [{"text": j["prompt"]}]}],
              "generationConfig": {"temperature": 0.9, "responseMimeType": "application/json"}}).json()
    open(j["out"], "w", encoding="utf-8").write("".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"]))

def _do_tts(j):
    r = _call("POST", f"{API}/models/{j["tts_model"]}:generateContent", json={
        "contents": [{"parts": [{"text": f"Say this in everyday colloquial Tamil, in the voice of {j['note']}: {j['text']}"}]}],
        "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": j["voice"]}}}}}).json()
    _wav_write(j["out"], base64.b64decode(r["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]))

def _find_video(o):
    """Depth-first search of an Interactions answer for the video part: returns ('uri', url) or ('data', base64)."""
    if isinstance(o, dict):
        if o.get("type") == "video" or str(o.get("mime_type", "")).startswith("video"):
            for k in ("uri", "url", "data"):
                if isinstance(o.get(k), str) and o[k]: return ("data" if k == "data" else "uri", o[k])
        for v in o.values():
            r = _find_video(v)
            if r: return r
    elif isinstance(o, list):
        for v in o:
            r = _find_video(v)
            if r: return r

def _do_vid(j):
    """Gemini Omni video (Veo previews were shut down): POST /interactions in the background, poll until done, save the mp4."""
    if env("DRY_VIDEO") == "true":      # free layout test: a coloured placeholder clip instead of a paid video clip
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc2=s=1280x720:r=24:d={j['seconds']}", "-pix_fmt", "yuv420p", j["out"]]); return
    o = _call("POST", f"{API}/interactions", json={"model": j["model"], "input": j["prompt"], "background": True,
              "response_format": {"type": "video", "delivery": "uri", "aspect_ratio": "16:9", "resolution": env("VIDEO_RES", "360p")}}).json()
    end = time.time() + 900
    while o.get("status") not in ("completed", None) and time.time() < end:
        if o.get("status") in ("failed", "cancelled"): raise RuntimeError("video failed " + json.dumps(o)[:300])
        time.sleep(float(env("POLL_SEC", "8"))); o = _call("GET", f"{API}/interactions/{o['id']}").json()
    v = _find_video(o)
    if not v: raise RuntimeError("no video in answer: " + json.dumps(o)[:500])
    open(j["out"], "wb").write(base64.b64decode(v[1]) if v[0] == "data" else _call("GET", v[1], timeout=300).content)

_DO = {"chat": _do_chat, "tts": _do_tts, "vid": _do_vid}

def gemini(task, jobs, timeout):
    """Run jobs of one kind in parallel. Returns the set of job ids whose output file was written."""
    if not KEY and env("DRY_VIDEO") != "true": raise SystemExit("GEMINI_API_KEY is not set")
    for j in jobs:
        if os.path.exists(j["out"]): os.remove(j["out"])
    def one(j):
        for n in range(6):
            if task in _stop: return
            if task == "tts": j["tts_model"] = TTS_MODELS[(j["id"] + n) % len(TTS_MODELS)]
            try: _DO[task](j); return
            except Exception as e:
                m = str(e); print(f"FAIL {task} {j['id']} try {n + 1}: {' '.join(m.split())[:150]} ... {' '.join(m.split())[-450:]}")
                if re.search(r"HTTP (400|401|403|404)", m):
                    _stop[task] = m; return
                time.sleep(5 * (n + 1) + ((10 if task == "tts" else 25) * (n + 1) if "HTTP 429" in m else 0))
                if n >= 2 and "HTTP 429" not in m: return
    ex = cf.ThreadPoolExecutor(POOL[task]); futs = [ex.submit(one, j) for j in jobs]
    cf.wait(futs, timeout=timeout); ex.shutdown(wait=False, cancel_futures=True)
    if task == "tts" and len({j["id"] for j in jobs if os.path.exists(j["out"])}) < len(jobs) and "models" not in _stop:
        _stop["models"] = 1
        try: print("Models your key can use:", ", ".join(sorted(m["name"][7:] for m in _call("GET", f"{API}/models?pageSize=200").json().get("models", []) if re.search(r"tts|veo", m["name"]))))
        except Exception as e: print("model list failed:", str(e)[:100])
    if task in _stop and task != "models":
        print(f"{task} stopped: {_stop[task][:300]}")
        try: print("Models your key can use:", ", ".join(sorted(m["name"][7:] for m in _call("GET", f"{API}/models?pageSize=200").json().get("models", []) if re.search(r"flash|tts|veo", m["name"]))))
        except Exception as e: print("model list failed:", str(e)[:100])
    return {j["id"] for j in jobs if os.path.exists(j["out"]) and os.path.getsize(j["out"]) > 500}

_chat_n = 0
def llm_many(specs):
    """specs = [(prompt, check)]. All prompts run in parallel on Gemini; any answer that is not valid JSON or fails its check is asked again."""
    global _chat_n
    res, extra = [None] * len(specs), [""] * len(specs)
    for _ in range(4):
        todo = [i for i, r in enumerate(res) if r is None]
        if not todo: break
        jobs = []
        for i in todo:
            _chat_n += 1; jobs.append({"id": i, "prompt": specs[i][0] + extra[i], "model": LLM_MODEL, "out": os.path.join(WORK, f"chat{_chat_n}.txt")})
        done = gemini("chat", jobs, 600)
        for j in jobs:
            if j["id"] not in done: continue
            raw = open(j["out"], encoding="utf-8").read()
            try:
                d = json.loads(raw[raw.index("{"): raw.rindex("}") + 1]); err = specs[j["id"]][1](d)
            except Exception: err = "Return valid JSON only."
            if err: extra[j["id"]] = "\n" + err; print("retry:", err)
            else: res[j["id"]] = d
    if None in res: raise SystemExit("Gemini script step failed")
    return res


def norm_lines(raw, names):
    """-> list of {speaker, text}; unknown speakers become the Narrator."""
    out = []
    for it in (raw if isinstance(raw, list) else [raw]):
        if isinstance(it, dict):
            sp = txt_of(it.get("speaker") or it.get("name") or it.get("character") or "Narrator")
            tx = txt_of(it.get("text") or it.get("line") or it.get("voiceover") or it.get("dialogue"))
        else:
            s = txt_of(it); m = re.match(r"^\s*([^:：]{1,30})[:：]\s*(.+)$", s)
            sp, tx = (m.group(1), m.group(2)) if m else ("Narrator", s)
        if not tx: continue
        low = sp.strip().lower()
        hit = next((n for n in names if n.lower() == low), None) or next((n for n in names if low and (low in n.lower() or n.lower() in low)), None)
        out.append({"speaker": hit or "Narrator", "text": tx})
    return out

def count_words(d, names):
    return sum(len(l["text"].split()) for b in d.get("beats", []) if isinstance(b, dict) for l in norm_lines(b.get("lines"), names))

ACTS = [
    ("Act 1 - the start", "Meet the characters in the place. Open with an exciting hook (a question or a surprise). Show what they love."),
    ("Act 2 - the problem", "A small problem begins. Ask the kids watching ONE easy question in a Narrator line (for example: 'நீங்களா இருந்தா என்ன பண்ணுவீங்க?')."),
    ("Act 3 - funny tries and the answer", "They try to fix it with one or two funny mistakes, then a kind idea or help solves the problem. Ask the kids to spot or count something in the picture."),
    ("Act 4 - happy ending", "Everyone is happy. Last beats: the Narrator says the moral in one short sentence, then a warm goodbye line. Do not say the like/subscribe words, that is added later."),
]
NACT, NBEAT = len(ACTS), 4          # 4 acts x 4 beats = 16 scenes = 16 Veo clips, a story of about 2 minutes

def make_check(names, lo=55, hi=110):
    def check(d, late=False):
        b = d.get("beats")
        if not isinstance(b, list) or len(b) < 3: return f"Return {NBEAT} beats."
        for x in b:
            if not isinstance(x, dict) or not norm_lines(x.get("lines"), names) or not txt_of(x.get("scene")): return "Every beat needs lines and a scene."
        alltxt = " ".join(l["text"] for x in b for l in norm_lines(x.get("lines"), names))
        letters = [c for c in alltxt if c.isalpha()]
        if letters and sum("\u0b80" <= c <= "\u0bff" for c in letters) / len(letters) < 0.85:
            return "Every spoken line MUST be written in Tamil script (தமிழ்) only - no English or Tanglish words."
        n = count_words(d, names)
        if n < (lo - 25 if late else lo): return f"Your previous answer had only {n} Tamil words in total. Write {lo + 15} to {hi - 30} Tamil words across all lines."
        if n > hi + 30: return f"Too long ({n} words). Keep it to {lo + 15}-{hi - 30} Tamil words in total."
        return None
    return check

STYLE_RULES = """LANGUAGE AND TONE (very important):
- Write the way a loving akka/amma tells a story to a 3-7 year old at home: very simple everyday spoken Tamil (பேச்சு வழக்கு) in Tamil script. NEVER literary/book Tamil, no big or formal words, no long speeches.
- Short sentences, 3 to 8 words. Easy words a 4-year-old knows. Repeat a cute catchphrase or sound now and then (like "டும் டும் டும்!", "ஹை ஹை!").
- The Narrator tells most of the story in a friendly, playful way and sometimes talks to the kids directly ("பாத்தீங்களா?", "சொல்லுங்க பாப்போம்!"). Characters speak only short, lively, funny lines - no stiff or serious conversations, no lecturing.
- Use small reactions (ஹா ஹா!, அச்சச்சோ!, ஐ!) and sound words (டமால்!, சல சல). Nothing scary, no violence, no sad ending."""

def check_outline(d):
    if not (txt_of(d.get("title")) and txt_of(d.get("plot")) and isinstance(d.get("characters"), list) and d["characters"]
            and isinstance(d.get("parts"), list) and len(d["parts"]) >= NACT): return f"Return every field, with 2-4 characters and exactly {NACT} parts."

def make_script(h):
    combo = pick_combo(h); code = random.randint(1000, 9999)
    avoid = "; ".join(h["titles"][-40:]) or "none"
    o = llm_many([(f"""You create ORIGINAL, gentle, funny children's stories in Tamil for kids aged 3-7 (a YouTube video of about 2 minutes). Nothing scary, no real brands or famous cartoon characters.
Ingredients (all must appear): Moral theme: {combo[0]} | Hero: {combo[1]} | Place: {combo[2]} | Situation: {combo[3]} | Variation code: {code}
Do NOT repeat these earlier titles/ideas: {avoid}
Return JSON only:
title (Tamil, cute and curious, max 45 chars), description (Tamil, 2 short lines), tags (8 strings),
moral (Tamil, ONE short sentence in everyday spoken Tamil, like a mum saying it),
setting_look (English, one sentence describing the place's look),
characters: list of 2 to 4 objects, each with name (short Tamil name), look (English: species/age, colours, clothes, adorable 3D cartoon look) and voice (one of: boy, girl, old_man, old_woman, big_deep, squeaky, cheerful_man, cheerful_woman; different voice for each character; big animals big_deep, tiny animals squeaky, kids boy/girl),
plot (English, 70-100 words),
parts (list of exactly 4 English sentences: start, problem, funny tries and the answer, happy ending with the moral).""", check_outline)])[0]
    for k in ("title", "description", "moral", "setting_look", "plot"): o[k] = txt_of(o.get(k))
    if max([difflib.SequenceMatcher(None, o["title"], t).ratio() for t in h["titles"]] or [0]) > 0.7: return make_script(h)
    tg_ = o.get("tags", [])
    o["tags"] = [txt_of(t) for t in tg_] if isinstance(tg_, list) else [t.strip() for t in txt_of(tg_).replace("#", "").split(",") if t.strip()]
    chars = [{"name": txt_of(c["name"]), "look": txt_of(c.get("look")) or "cute cartoon character", "voice": c.get("voice")}
             for c in o["characters"] if isinstance(c, dict) and txt_of(c.get("name"))] or [{"name": "குட்டி", "look": "cute little cartoon animal", "voice": "boy"}]
    styles, colors = assign_voices(chars)
    names = [c["name"] for c in chars]; looks = "; ".join(f"{c['name']} = {c['look']}" for c in chars)
    parts = [txt_of(p) for p in o["parts"][:NACT]]
    def act_prompt(ai):
        return f"""Write one part of a children's story as a short animated script. This is {ACTS[ai][0]} of 4.
Title: {o['title']}
Whole plot: {o['plot']}
All 4 parts in order: {' | '.join(parts)}
THIS part: {parts[ai]}  ({ACTS[ai][1]})
Moral (the Narrator says it in the LAST beat of Act 4): {o['moral']}
Characters (use EXACTLY these names as speakers, plus "Narrator"): {', '.join(names)}
Looks: {looks}
Setting: {o['setting_look']}
{STYLE_RULES}
Return JSON only: beats = list of exactly 4 beats in order. Each beat has:
  lines: list of 1 to 3 objects {{"speaker": name or "Narrator", "text": Tamil line}},
  scene: ONE English prompt for a short animated video clip showing exactly what happens and how the characters MOVE in that beat (cute bright 3D cartoon, the characters' looks from the list, ONE clear continuous action with lively movement, happy colourful, child-friendly, wide shot, no text).
Total across all lines of this part: 65-80 Tamil words (each beat is spoken in about 7 seconds, so about 16-20 words per beat). Do not repeat lines from other parts."""
    acts = llm_many([(act_prompt(i), make_check(names)) for i in range(NACT)])
    beats = []
    for ai, d in enumerate(acts):
        part = [{"lines": norm_lines(b.get("lines"), names), "scene": txt_of(b.get("scene")), "act": ai} for b in d["beats"][:NBEAT]]
        part[0]["act_start"] = True; beats += part
    o.update({"beats": beats, "chars": chars, "styles": styles, "colors": colors, "fp": "|".join(combo), "combo": list(combo)})
    return o


# ====================== VOICE ======================
CTA_TEXT = "கதை பிடிச்சிருந்தா லைக் பண்ணுங்க, சப்ஸ்கிரைப் பண்ணுங்க, பை பை!"

def _to_wav(mp3, wav):
    trim = "silenceremove=start_periods=1:start_duration=0.02:start_threshold=-45dB"
    r = subprocess.run(["ffmpeg", "-y", "-i", mp3, "-af", f"{trim},areverse,{trim},areverse", "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", wav], capture_output=True)
    if r.returncode != 0 or wav_dur(wav) < 0.2:
        run(["ffmpeg", "-y", "-i", mp3, "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", wav])

def wav_dur(p):
    with wave.open(p) as w: return w.getnframes() / w.getframerate()

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

def make_voices(d, beats):
    """One Gemini voice per character. Returns the final 'like and subscribe' line, also spoken."""
    cta = {"speaker": "Narrator", "text": CTA_TEXT}
    lines = [l for b in beats for l in b["lines"]] + [cta]
    jobs = []
    for k, l in enumerate(lines):
        v, note = voice_for(d["styles"].get(l["speaker"], "narrator"))
        l["wav"] = os.path.join(WORK, f"l{k}.wav")
        jobs.append({"id": k, "text": l["text"], "voice": v, "out": os.path.join(WORK, f"l{k}.aud"),
                     "note": note})
    ok = gemini("tts", jobs, 300 + 40 * len(jobs))
    if len(ok) < len(jobs): raise SystemExit(f"Gemini voice failed for {len(jobs) - len(ok)} of {len(jobs)} lines")
    with cf.ThreadPoolExecutor(4) as ex: list(ex.map(lambda a: _to_wav(a[0]["out"], a[1]["wav"]), zip(jobs, lines)))
    for l in lines: l["dur"] = wav_dur(l["wav"])
    return cta



# ====================== VIDEO CLIPS (Veo) ======================
def make_clips(d, beats):
    """One Veo clip per scene (shortest clip length that covers the voice, slowed up to 1.25x). A scene whose clip failed reuses the nearest good one."""
    cast = "; ".join(c["look"] for c in d["chars"]); N = len(beats); jobs = []
    for i, b in enumerate(beats):
        need = (b["f1"] - b["f0"]) / FPS
        sec = next((s for s in CLIP_LENGTHS if s * MAX_SLOW >= need), CLIP_LENGTHS[-1])
        jobs.append({"id": i, "model": VIDEO_MODEL, "seconds": sec, "out": os.path.join(WORK, f"ai{i}.mp4"),
                     "prompt": f"{cast}. {b['scene']}. A short clip of about {sec} seconds. Smooth cute 3D cartoon animation, characters move and react naturally, soft bright colours, no text, no scene cut, steady camera"})
    ok = gemini("vid", jobs, int(env("VIDEO_TIMEOUT_MIN", "150")) * 60)
    print(f"AI video clips: {len(ok)}/{N} made ({VIDEO_MODEL}, {sum(j['seconds'] for j in jobs if j['id'] in ok)} s generated)")
    if not ok: raise SystemExit("No video clips were made (check GEMINI_API_KEY and billing)")
    def fit(i):
        src = jobs[i if i in ok else min(ok, key=lambda g: (abs(g - i), g > i))]["out"]; F = beats[i]["f1"] - beats[i]["f0"]; need = F / FPS
        dc = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip() or need)
        f = min(max(need / dc, 1.0), MAX_SLOW); out = os.path.join(WORK, f"clip{i}.mp4")
        run(["ffmpeg", "-y", "-i", src, "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setpts={f:.4f}*PTS,fps={FPS},tpad=stop_mode=clone:stop_duration={need:.2f}",
             "-frames:v", str(F), "-threads", "2"] + VENC + [out])
        return out
    with cf.ThreadPoolExecutor(3) as ex: return list(ex.map(fit, range(N)))


# ====================== ASS (subtitle shapes) ======================
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
Style: Chip,Noto Sans Tamil,60,&H00FFFFFF,&H00FFFFFF,&H00FF8AE8,&H00000000,1,0,0,0,100,100,0,0,3,3,0,2,60,60,0,1
Style: Title,Noto Sans Tamil,68,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,3,8,70,70,0,1
Style: Shape,DejaVu Sans,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: Txt,DejaVu Sans,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,1,5,0,0,0,1
Style: Tam,Noto Sans Tamil,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,5,1,5,0,0,0,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

def tg(s): return "{" + s + "}"

T0 = 0.0     # seconds added to every subtitle time, so one .ass file can hold the story and the outro
def dlg(layer, st, en, style, text): return f"Dialogue: {layer},{ts(st+T0)},{ts(en+T0)},{style},,0,0,0,,{text}"

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

BIGCIRCLE = circle(110)

THUMB = ("m 0 26 l 12 26 l 12 58 l 0 58 m 16 28 l 25 6 b 27 2 33 2 36 5 b 38 8 38 12 36 16 l 33 22 l 52 22 b 57 22 60 26 59 31 "
         "l 55 50 b 54 55 50 58 45 58 l 16 58 l 16 28")

BELL = ("m 30 2 b 40 2 46 10 46 22 l 46 36 l 54 46 l 54 50 l 6 50 l 6 46 l 14 36 l 14 22 b 14 10 20 2 30 2 "
        "m 23 53 b 24 59 36 59 37 53 l 23 53")

POINTER = "m 0 0 l 0 40 l 10 31 l 17 46 l 24 43 l 17 28 l 30 28 l 0 0"

def outro_clicks(cta):
    s, d = cta["start"], cta["dur"]
    c1 = s + 0.30 * d + 0.15; c2 = max(s + 0.72 * d, c1 + 0.55); c3 = max(s + d + 0.25, c2 + 0.55)
    return c1, c2, c3

def outro_events(cta, L):
    ass = []
    c1, c2, c3 = outro_clicks(cta)
    ass.append(txt(2, 0.05, L, "Tam", 960, 300, "00F0FF", 96, "பிடிச்சிருக்கா?", r"\fad(200,200)\fscx80\fscy80\t(0,300,\fscx100\fscy100)"))
    ass.append(txt(2, 0.05, L, "Txt", 960, 430, "FFFFFF", 72, "LIKE  •  SUBSCRIBE", r"\fad(200,200)"))
    LX, SX, BX, Y = 640, 1055, 1375, 640
    for (a, b, col, label, icon) in [(0.05, c1, "3A3A3A", "LIKE", "FFFFFF"), (c1, L, "FFA63E", "LIKED", "FFFFFF")]:
        ex = r"\fad(200,0)" if a == 0.05 else r"\fscx112\fscy112\t(0,200,\fscx100\fscy100)"
        ass.append(shape(1, a, b, LX, Y, rrect(300, 120, 60), col, ex))
        ass.append(shape(2, a, b, LX - 78, Y - 3, THUMB, icon, ex))
        ass.append(txt(3, a, b, "Txt", LX + 36, Y, "FFFFFF", 44, label, ex))
    for (a, b, col, label, size) in [(0.05, c2, "0000FF", "SUBSCRIBE", 44), (c2, L, "4A4A4A", "SUBSCRIBED ✓", 34)]:
        ex = r"\fad(200,0)" if a == 0.05 else r"\fscx108\fscy108\t(0,200,\fscx100\fscy100)"
        ass.append(shape(1, a, b, SX, Y, rrect(430, 120, 60), col, ex))
        ass.append(txt(3, a, b, "Txt", SX, Y, "FFFFFF", size, label, ex))
    ass.append(shape(1, 0.05, c3, BX, Y, BIGCIRCLE, "4A4A4A", r"\fad(200,0)"))
    ass.append(shape(2, 0.05, c3, BX, Y, BELL, "FFFFFF", r"\fad(200,0)\fscx105\fscy105"))
    shake = r"\t(0,90,\frz18)\t(90,180,\frz-18)\t(180,270,\frz14)\t(270,360,\frz-14)\t(360,450,\frz8)\t(450,540,\frz0)"
    ass.append(shape(1, c3, L, BX, Y, BIGCIRCLE, "00C8FF", r"\fscx108\fscy108\t(0,200,\fscx100\fscy100)"))
    ass.append(shape(2, c3, L, BX, Y, BELL, "000000", r"\fscx105\fscy105" + shake))
    pts = [(1700, 940), (LX + 30, Y + 20), (SX + 60, Y + 20), (BX + 8, Y + 22)]
    clicks = [c1, c2, c3]
    legs = [(0.1, c1 - 0.12), (c1 + 0.2, min(c1 + 0.7, c2 - 0.08)), (c2 + 0.2, min(c2 + 0.7, c3 - 0.08))]
    for i, (s0, e0) in enumerate(legs):
        e0 = max(e0, s0 + 0.2)
        ass.append(dlg(5, s0, e0, "Shape", tg(rf"\an7\move({pts[i][0]},{pts[i][1]},{pts[i+1][0]},{pts[i+1][1]})\c&HFFFFFF&\3c&H000000&\bord2\shad0\p1") + POINTER + tg(r"\p0")))
        ass.append(dlg(5, e0, clicks[i] + 0.5, "Shape", tg(rf"\an7\pos({pts[i+1][0]},{pts[i+1][1]})\c&HFFFFFF&\3c&H000000&\bord2\shad0\p1") + POINTER + tg(r"\p0")))
        ass.append(shape(4, clicks[i], clicks[i] + 0.4, pts[i + 1][0] + 6, pts[i + 1][1] + 6, CIRCLE, "FFFFFF", r"\alpha&H50&\fscx30\fscy30\t(0,380,\fscx230\fscy230\alpha&HFF&)"))
    return ass


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

def find_bgm():
    src = os.path.join(ROOT, "assets", env("BGM_FILE", "bgm.mp3"))
    if not os.path.exists(src): return None
    norm = os.path.join(WORK, "bgm.m4a")
    run(["ffmpeg", "-y", "-i", src, "-vn", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", "-ac", "2", "-c:a", "aac", norm]); return norm

def mix_audio(narr, total_s, workdir):
    """Voices (+sfx) cleaned up first in their own pass, then mixed with the BGM ducked under the voice.
    (Normalising inside the same graph as the sidechain made the mix end ~3 s early and cut the goodbye.)"""
    out = os.path.join(workdir, "mix.m4a"); bgm = find_bgm()
    voice = ("highpass=f=80,equalizer=f=250:t=q:w=1.2:g=1.5,equalizer=f=3000:t=q:w=1:g=4,"
             "acompressor=threshold=0.09:ratio=3:attack=5:release=120:makeup=2,loudnorm=I=-14:TP=-1.5:LRA=9")
    fade = f"afade=t=out:st={total_s-0.8:.2f}:d=0.8"
    vclean = os.path.join(workdir, "voice_clean.wav")
    run(["ffmpeg", "-y", "-i", narr, "-af", voice + f",apad=whole_dur={total_s:.3f}", "-t", f"{total_s:.3f}", "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", vclean])
    if bgm:
        fc = (f"[0:a]asplit=2[v][vs];[1:a]volume=0.34[b];[b][vs]sidechaincompress=threshold=0.02:ratio=9:attack=20:release=500[bd];"
              f"[v][bd]amix=inputs=2:duration=first:normalize=0,apad=whole_dur={total_s:.3f},{fade}[a]")
        run(["ffmpeg", "-y", "-i", vclean, "-stream_loop", "-1", "-i", bgm, "-filter_complex", fc, "-map", "[a]", "-t", f"{total_s:.3f}", "-c:a", "aac", "-b:a", "192k", out])
    else:
        run(["ffmpeg", "-y", "-i", vclean, "-af", fade, "-t", f"{total_s:.3f}", "-c:a", "aac", "-b:a", "192k", out])
    return out

# ====================== CHANNEL INTRO (made once with Gemini, kept in assets/) ======================
def make_intro():
    """assets/intro.mp4 fitted to 16:9 (any other shape sits on a blurred copy of itself), cut to INTRO_SECONDS (default 9) with a fade. INTRO=false skips it."""
    src = os.path.join(ROOT, "assets", "intro.mp4")
    if env("INTRO", "true").lower() == "false" or not os.path.exists(src): return None
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip())
    L = math.floor(min(dur, float(env("INTRO_SECONDS", "9"))) * FPS) / FPS; vid, wav = os.path.join(WORK, "intro_v.mp4"), os.path.join(WORK, "intro_a.wav")
    run(["ffmpeg", "-y", "-i", src, "-t", f"{L:.3f}", "-filter_complex",
         f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:3[bg];[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
         f"[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={FPS},format=yuv420p,fade=t=out:st={L-0.4:.3f}:d=0.4"] + VENC + [vid])
    run(["ffmpeg", "-y", "-i", src, "-t", f"{L:.3f}", "-vn", "-af", f"loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st={L-0.5:.3f}:d=0.5", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", wav])
    return vid, wav, L

# ====================== BUILD ======================
def build_video(d, beats, clips, cta, story_frames):
    global T0
    story_len = story_frames / FPS
    cta["start"] = 0.3; c1, c2, c3 = outro_clicks(dict(cta, dur=cta["dur"]))
    outro_len = math.ceil(max(6.0, c3 + 1.5, cta["start"] + cta["dur"] + 0.8) * FPS) / FPS; total = story_len + outro_len
    print(f"Timeline: story {story_len:.1f}s + outro {outro_len:.1f}s, {len(beats)} scenes, voices: {sorted(set(d['styles'].values()))}")
    # audio: intro sound, then voices + BGM
    pieces = [(l["start"], l["wav"]) for b in beats for l in b["lines"]] + [(story_len + cta["start"], cta["wav"])]
    pop, click = make_sfx(WORK)[1], make_sfx(WORK)[0]
    narr = os.path.join(WORK, "narr.wav")
    build_narration(narr, total, pieces, [(b["start"], pop) for b in beats[1:] if b.get("act_start")] + [(story_len + c, click) for c in (c1, c2, c3)])
    mix = mix_audio(narr, total, WORK)
    intro = make_intro(); il = intro[2] if intro else 0.0
    if intro:
        full = os.path.join(WORK, "full_audio.m4a")
        run(["ffmpeg", "-y", "-i", intro[1], "-i", mix, "-filter_complex", "[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];[1:a]aresample=44100,aformat=channel_layouts=stereo[a1];[a0][a1]concat=n=2:v=0:a=1[a]",
             "-map", "[a]", "-c:a", "aac", "-b:a", "192k", full]); mix = full
    # outro background = blurred last picture of the story
    last = os.path.join(WORK, "last.png"); outro = os.path.join(WORK, "outro.mp4")
    run(["ffmpeg", "-y", "-sseof", "-0.2", "-i", clips[-1], "-frames:v", "1", "-update", "1", last])
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", last, "-vf", "boxblur=22:2,eq=brightness=-0.22:saturation=0.9,fade=t=in:d=0.25",
         "-frames:v", str(round(outro_len * FPS))] + VENC + [outro])
    # one subtitle file: title + name tags over the story, buttons over the outro
    T0 = il; ass = [ass_head()]
    ass.append(dlg(2, 0.0, 4.0, "Title", tg(r"\an8\pos(960,60)\fad(150,450)\fscx88\fscy88\t(0,300,\fscx100\fscy100)") + d["title"]))
    for l in (l for b in beats for l in b["lines"] if l["speaker"] != "Narrator"):
        ass.append(dlg(1, l["start"], l["end"] + 0.1, "Chip", tg(rf"\an2\pos(960,1020)\3c&H{d['colors'][l['speaker']]}&\bord16\1c&H202020&") + " " + l["speaker"] + " "))
    T0 = il + story_len; ass += outro_events(cta, outro_len); T0 = 0.0
    af = os.path.join(WORK, "all.ass"); open(af, "w", encoding="utf-8").write("\n".join(ass) + "\n")
    vl = os.path.join(WORK, "vlist.txt"); open(vl, "w").write("".join(f"file '{p}'\n" for p in ([intro[0]] if intro else []) + clips + [outro]))
    final, logo = os.path.join(OUT, "video.mp4"), os.path.join(ROOT, "assets", "logo.png")
    tail = f"ass={af},fade=t=out:st={il + total - 0.25:.3f}:d=0.25"
    if os.path.exists(logo):     # logo bobs and pulses in the top-left corner from the end of the intro to the last second
        fc = (f"[0:v]{tail}[b];[2:v]format=rgba,scale=w='150*(1+0.06*sin(t*4))':h=-1:eval=frame,fade=in:st={il:.2f}:d=0.5:alpha=1[lg];"
              f"[b][lg]overlay=x='30+(150-overlay_w)/2':y='24+(150-overlay_h)/2+6*sin(t*3)':enable='gte(t,{il:.2f})':shortest=1,format=yuv420p[v]")
        extra = ["-loop", "1", "-i", logo]
    else: fc, extra = f"[0:v]{tail},format=yuv420p[v]", []
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", vl, "-i", mix] + extra + ["-filter_complex", fc, "-map", "[v]", "-map", "1:a",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-r", str(FPS), "-c:a", "copy", "-shortest", "-movflags", "+faststart", final])
    hero = os.path.join(WORK, "hero.png")      # thumbnail picture = a frame of the 2nd scene's clip
    run(["ffmpeg", "-y", "-ss", "1.5", "-i", clips[min(1, len(clips) - 1)], "-frames:v", "1", hero])
    make_thumbnail(d, hero)
    for name, tt in (("story", il + min(story_len - 1, 14.0)), ("outro", il + total - 1.2)):
        subprocess.run(["ffmpeg", "-y", "-ss", f"{tt:.2f}", "-i", final, "-frames:v", "1", os.path.join(OUT, f"frame_{name}.png")], capture_output=True)
    return final

def make_thumbnail(d, img):
    """Kid-friendly 16:9 cover: bright hero picture, big Tamil title on a colour banner, thick border, star burst, channel logo."""
    ass = [ass_head(), shape(1, 0, 5, 960, 870, rrect(1760, 330, 70), "00B4FF", r"\3c&HFFFFFF&\bord10"),
           dlg(2, 0, 5, "Tam", tg(r"\an5\pos(960,870)\fs104\c&HFFFFFF&\3c&H8A2BE2&\bord9\shad0\q0") + d["title"]),
           shape(1, 0, 5, 1650, 250, circle(260), "00E5FF", r"\3c&HFFFFFF&\bord8\frz12"), txt(2, 0, 5, "Tam", 1650, 250, "8A2BE2", 76, "கதை!", r"\bord0\frz12")]
    af = os.path.join(WORK, "thumb.ass"); open(af, "w", encoding="utf-8").write("\n".join(ass) + "\n")
    base = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},eq=saturation=1.35:contrast=1.08,drawbox=x=0:y=0:w={W}:h={H}:color=0xFFD400:t=24,ass={af}"
    logo = os.path.join(ROOT, "assets", "logo.png"); out = os.path.join(OUT, "thumbnail.jpg")
    cmd = (["-i", img, "-i", logo, "-filter_complex", f"[0:v]{base}[bg];[1:v]scale=280:-1[lg];[bg][lg]overlay=50:50"] if os.path.exists(logo) else ["-i", img, "-vf", base])
    r = subprocess.run(["ffmpeg", "-y"] + cmd + ["-frames:v", "1", "-q:v", "3", out], capture_output=True, text=True)
    if r.returncode: print("thumbnail failed:", r.stderr[-300:])


# ====================== YOUTUBE ======================
def set_thumbnail(token, vid, path):
    try:
        r = requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}&uploadType=media",
                          headers={"Authorization": "Bearer " + token, "Content-Type": "image/jpeg"}, data=open(path, "rb").read(), timeout=120)
        print("Thumbnail:", r.status_code, r.text[:150])
    except Exception as e: print("thumbnail upload skipped:", e)

def upload(path, d, thumb=None):
    tok = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": env("YT_CLIENT_ID"), "client_secret": env("YT_CLIENT_SECRET"),
        "refresh_token": env("YT_REFRESH_TOKEN"), "grant_type": "refresh_token"}, timeout=60).json()
    if "access_token" not in tok: raise SystemExit("YouTube auth failed: " + json.dumps(tok))
    desc = d["description"] + f"\n\nMoral / நீதி: {d['moral']}\n\nஇது ஒரு கற்பனைக் குழந்தைக் கதை. AI animated story for kids.\n#TamilKidsStories #KidsStories #TamilStories #TamilCartoon"
    kids = env("MADE_FOR_KIDS", "true").lower() != "false"
    meta = {"snippet": {"title": d["title"][:95], "description": desc, "tags": d.get("tags", [])[:12] + ["Tamil kids stories", "Tamil story", "kids cartoon"],
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
    t0, key = time.time(), ist_today()
    try:
        h = load_hist(); d = make_script(h); beats = d["beats"]
        print(f"TITLE: {d['title']} | SLOT: {SLOT} | script {time.time()-t0:.0f}s")
        cta = make_voices(d, beats); story_frames = plan_timeline(beats); print(f"voices done {time.time()-t0:.0f}s")
        clips = make_clips(d, beats); print(f"clips done {time.time()-t0:.0f}s")
        json.dump(d, open(os.path.join(OUT, "script.json"), "w"), ensure_ascii=False, indent=1)
        final = build_video(d, beats, clips, cta, story_frames); print(f"video done {time.time()-t0:.0f}s")
        if env("UPLOAD") == "true":
            upload(final, d, os.path.join(OUT, "thumbnail.jpg")); h = load_hist()
            h["titles"].append(d["title"]); h["fingerprints"].append(d["fp"])
            h.setdefault("recent_themes", []).append(d["combo"][0]); h.setdefault("recent_heroes", []).append(d["combo"][1])
            h.setdefault("done", {}).setdefault(key, []).append(SLOT); save_hist(h)
        else: print("Upload skipped (test run).")
    except BaseException:
        if env("UPLOAD") == "true":
            h = load_hist(); t = h.setdefault("tries", {}).setdefault(key, {}); t[str(SLOT)] = int(t.get(str(SLOT), 0)) + 1; save_hist(h)
        raise

if __name__ == "__main__":
    main()
