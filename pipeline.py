import os, json, random, re, subprocess, asyncio, time, difflib, datetime, urllib.parse
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out"); os.makedirs(OUT, exist_ok=True)
HIST = os.path.join(ROOT, "history.json")
W, H = 1920, 1080   # long-form landscape 16:9

def env(k, d=""):
    return os.environ.get(k) or d

CRIMES = ["jewellery shop robbery", "missing bank manager", "locked-room death in a lodge", "temple idol theft",
          "forged will and land grab", "hit-and-run on a highway", "kidnapping for ransom", "fake CBI officer fraud",
          "poisoned sweet box", "ATM cash van heist", "college hostel mystery", "village well body discovery",
          "train compartment theft", "insurance fraud with a fake death", "cyber loan-app blackmail", "school lab fire",
          "textile mill owner murder", "bus-stand bag swap", "farmhouse disappearance", "wedding hall gold theft"]
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
CHAPTERS = [("The Shocking Hook", "open with the most shocking moment, then set the scene"),
            ("The Crime", "what exactly happened, who is the victim, how it was discovered"),
            ("The Investigation Begins", "investigator arrives, first observations, early false leads"),
            ("The Suspects", "three suspects with motives and alibis, tension rises"),
            ("The Missing Clue", "the key clue is found and its meaning slowly dawns"),
            ("The Twist", "a shocking twist overturns the theory"),
            ("The Truth Revealed", "culprit exposed, how they were caught, emotional closing and a one-line moral")]

SLOT = int(env("SLOT", "1") or 1)
POOL = {1: ["missing bank manager", "locked-room death in a lodge", "hit-and-run on a highway", "poisoned sweet box",
            "college hostel mystery", "village well body discovery", "school lab fire", "textile mill owner murder",
            "farmhouse disappearance", "forged will and land grab"],
        2: ["jewellery shop robbery", "temple idol theft", "kidnapping for ransom", "fake CBI officer fraud",
            "ATM cash van heist", "train compartment theft", "insurance fraud with a fake death", "cyber loan-app blackmail",
            "bus-stand bag swap", "wedding hall gold theft"]}

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
    used = set(h["fingerprints"])
    recent = h.get("recent_crimes", [])[-6:]
    pool = [x for x in POOL.get(SLOT, CRIMES) if x not in recent] or POOL.get(SLOT, CRIMES)
    for _ in range(300):
        c = (random.choice(pool), random.choice(PLACES), random.choice(TWISTS), random.choice(CLUES), random.choice(DETECTIVES))
        if "|".join(c) not in used: return c
    return c

# ---------- LLM ----------
def llm_json(prompt, retries=6, min_words=0):
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
            if min_words and len(d.get("voiceover", "").split()) < (min_words if a < 4 else int(min_words * .6)):
                extra = f"\nYour previous voiceover had only {len(d.get('voiceover','').split())} words. Write at least {min_words} Tamil words."; continue
            return d
        except Exception as e:
            print("llm attempt failed:", e); time.sleep(3)
    raise SystemExit("LLM failed")

def make_script(h):
    combo = pick_combo(h); code = random.randint(1000, 9999)
    avoid = "; ".join(h["titles"][-40:]) or "none"
    ing = f"Crime: {combo[0]} | Place: {combo[1]} | Twist: {combo[2]} | Key clue: {combo[3]} | Investigator: {combo[4]} | Variation code: {code}"
    outline = llm_json(f"""You plan an ORIGINAL, fully fictional SOLVED crime thriller (no real people/cases/brands, no gore, no sexual content) for a 8-10 minute Tamil YouTube video.
Ingredients (all must appear): {ing}
Do NOT repeat these earlier titles/ideas: {avoid}
Return JSON only: title (Tamil, curiosity-driven, max 80 chars), description (Tamil, 3 short lines + hashtags), tags (8 strings),
characters (list of 5 short English descriptions: investigator, victim, 3 suspects - consistent looks, for image prompts),
setting (one English sentence describing the place's look), plot (English, 120-180 words: full story incl. culprit, motive, clue, twist, how caught),
thumbnail_prompt (English, dramatic cinematic 3D cartoon scene, no text).""")
    sim = max([difflib.SequenceMatcher(None, outline["title"], t).ratio() for t in h["titles"]] or [0])
    if sim > 0.7: return make_script(h)
    chars = "; ".join(outline["characters"]) if isinstance(outline["characters"], list) else str(outline["characters"])
    parts = []; recap = ""
    for i, (name, beat) in enumerate(CHAPTERS):
        d = llm_json(f"""Write part {i+1} of {len(CHAPTERS)} ("{name}": {beat}) of a Tamil crime story narration.
Story plot (secret, reveal only at the proper part): {outline['plot']}
Characters (keep consistent): {chars}
Setting: {outline['setting']}
Story so far: {recap or 'nothing yet'}
Rules: natural spoken Tamil in Tamil script, suspenseful male narrator, short punchy sentences, 170-210 words, continue smoothly, no greetings after part 1, do not conclude the story before the last part.
Return JSON only: voiceover (Tamil), scenes (list of exactly 6 English image prompts in order of narration; each is a cinematic 3D animated cartoon scene, dramatic lighting, mention the character looks from the list, no text, no logos, no real people), recap (one English sentence of what happened).""", min_words=140)
        sc = [s for s in d["scenes"] if isinstance(s, str)][:6] or [outline["setting"]]
        parts.append({"name": name, "voiceover": d["voiceover"], "scenes": sc}); recap += " " + str(d.get("recap", ""))
    outline["parts"] = parts; outline["fp"] = "|".join(combo)
    return outline

# ---------- voice ----------
def make_voice(text, path):
    import edge_tts
    voice = env("TTS_VOICE", "ta-IN-ValluvarNeural")   # male Tamil voice
    asyncio.run(edge_tts.Communicate(text, voice, rate="-6%", pitch="-4Hz").save(path))

def duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).decode().strip())

# ---------- images ----------
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
    else: subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x101820:s={size[0]}x{size[1]}", "-frames:v", "1", path], check=True, capture_output=True)

# ---------- captions + chapter titles (ASS) ----------
def ts(t):
    cs = int(round(t * 100)); return f"{cs//360000}:{cs//6000%60:02d}:{cs//100%60:02d}.{cs%100:02d}"

ASS_HDR = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Cap,Noto Sans Tamil,56,&H0000F0FF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,120,120,70,1
Style: Chap,DejaVu Sans,44,&H0000D4FF,&H00FFFFFF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,3,3,0,7,50,50,50,1
Style: Thumb,Noto Sans Tamil,110,&H0000F0FF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,8,3,2,60,60,70,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

def caption_lines(text, t0, total, words_per=7):
    words = text.split(); per = total / max(1, len(words)); out = []
    for i in range(0, len(words), words_per):
        ch = words[i:i + words_per]
        k = "".join("{\\kf%d}%s " % (max(1, int(per * 100)), w) for w in ch)
        out.append(f"Dialogue: 0,{ts(t0 + i*per)},{ts(t0 + (i+len(ch))*per)},Cap,,0,0,0,,{k.strip()}")
    return out

# ---------- video ----------
def make_video(d, workdir):
    part_audio = []; durs = []
    for i, p in enumerate(d["parts"]):
        raw = os.path.join(workdir, f"v{i}.mp3"); make_voice(p["voiceover"], raw)
        a = os.path.join(workdir, f"v{i}.m4a")   # pad 0.6s silence so audio length == chapter video length
        subprocess.run(["ffmpeg", "-y", "-i", raw, "-af", "apad=pad_dur=0.6", "-ar", "44100", "-ac", "1", "-c:a", "aac", a], check=True, capture_output=True)
        part_audio.append(a); durs.append(duration(raw) + 0.6)
    lst = os.path.join(workdir, "alist.txt"); open(lst, "w").write("".join(f"file '{a}'\n" for a in part_audio))
    voice = os.path.join(workdir, "voice.m4a")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:a", "copy", voice], check=True, capture_output=True)
    clips = []; ass = [ASS_HDR]; t = 0.0; prev = None; chapter_marks = []
    for i, p in enumerate(d["parts"]):
        chapter_marks.append((t, p["name"]))
        ass.append(f"Dialogue: 1,{ts(t)},{ts(t+5)},Chap,,0,0,0,,{i+1}/{len(d['parts'])}  {p['name']}")
        ass += caption_lines(p["voiceover"], t, durs[i] - 0.6)
        n = len(p["scenes"]); seg = durs[i] / n
        for j, s in enumerate(p["scenes"]):
            img = os.path.join(workdir, f"img{i}_{j}.jpg"); get_image(s, img, prev); prev = img
            c = os.path.join(workdir, f"c{i}_{j}.mp4"); frames = int(seg * 25) + 1
            zoom = "z='min(zoom+0.0006,1.18)'" if (i + j) % 2 == 0 else "z='if(eq(on,0),1.18,max(zoom-0.0006,1.0))'"
            subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", img, "-vf",
                f"scale=2880:1620,zoompan={zoom}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps=25,format=yuv420p",
                "-frames:v", str(frames), "-preset", "veryfast", c], check=True, capture_output=True)
            clips.append(c)
        t += durs[i]
    cl = os.path.join(workdir, "clist.txt"); open(cl, "w").write("".join(f"file '{c}'\n" for c in clips))
    base = os.path.join(workdir, "base.mp4")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl, "-c", "copy", base], check=True, capture_output=True)
    assf = os.path.join(workdir, "cap.ass"); open(assf, "w", encoding="utf-8").write("\n".join(ass) + "\n")
    today = datetime.datetime.strptime(ist_today(), '%Y-%m-%d').strftime("%d %b %Y")
    vf = (f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='CRIME FILES  |  SOLVED CASE  |  {today}':"
          f"fontcolor=white@0.85:fontsize=28:x=w-text_w-40:y=h-50:box=1:boxcolor=black@0.5:boxborderw=8,ass={assf}")
    final = os.path.join(OUT, "video.mp4")
    bgm = os.path.join(ROOT, "assets", "bgm.mp3")
    if os.path.exists(bgm):
        cmd = ["ffmpeg", "-y", "-i", base, "-i", voice, "-stream_loop", "-1", "-i", bgm, "-filter_complex",
               "[1:a]volume=1.6[v];[2:a]volume=0.10[b];[v][b]amix=inputs=2:duration=first:dropout_transition=0[a]",
               "-vf", vf, "-map", "0:v", "-map", "[a]", "-t", f"{t:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "160k", final]
    else:
        cmd = ["ffmpeg", "-y", "-i", base, "-i", voice, "-vf", vf, "-map", "0:v", "-map", "1:a", "-t", f"{t:.2f}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "160k", final]
    subprocess.run(cmd, check=True)
    subprocess.run(["ffmpeg", "-y", "-ss", "8", "-i", final, "-frames:v", "1", os.path.join(OUT, "frame_check.png")], capture_output=True)
    return final, chapter_marks

def make_thumbnail(d, workdir):
    img = os.path.join(workdir, "thumb_src.jpg"); get_image(d["thumbnail_prompt"], img, None)
    a = os.path.join(workdir, "thumb.ass")
    open(a, "w", encoding="utf-8").write(ASS_HDR.replace("PlayResX: 1920", "PlayResX: 1280").replace("PlayResY: 1080", "PlayResY: 720")
        + f"Dialogue: 0,0:00:00.00,0:00:05.00,Thumb,,0,0,0,,{d['title'][:38]}\n")
    out = os.path.join(OUT, "thumbnail.jpg")
    r = subprocess.run(["ffmpeg", "-y", "-i", img, "-vf", f"scale=1280:720,drawbox=x=0:y=ih*0.55:w=iw:h=ih*0.45:color=black@0.45:t=fill,ass={a}", "-frames:v", "1", "-q:v", "3", out], capture_output=True)
    return out if r.returncode == 0 else None

# ---------- YouTube upload ----------
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
        print("Thumbnail:", tr.status_code, tr.text[:150])   # needs a verified channel; failure is non-fatal

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
