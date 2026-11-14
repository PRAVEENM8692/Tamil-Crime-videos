"""Tamil crime story channel: narrate a whole script with one Gemini voice, no style instruction (the voice's own pace).
Script file: sections start with a '## NN name' line. Writes out/NN_name.mp3, out/full.mp3 and out/durations.json."""
import base64, json, os, re, subprocess, sys, time, wave
import requests

API = "https://generativelanguage.googleapis.com/v1beta"
KEY = os.environ.get("GEMINI_API_KEY", "")
MODELS = [m.strip() for m in (os.environ.get("TTS_MODEL") or "gemini-3.8-flash-tts,gemini-3.8-flash-lite-tts,gemini-3.1-flash-tts-preview").split(",") if m.strip()]
VOICE = os.environ.get("NARRATOR_VOICE") or "Charon"
SCRIPT = os.environ.get("SCRIPT") or "crime/alavandar/script.txt"
MAX_CHARS = 900     # long sections are cut at line ends into pieces of about this size, so no call runs too long

def pieces(text):
    out, cur = [], ""
    for line in text.splitlines():
        if cur and len(cur) + len(line) > MAX_CHARS: out.append(cur); cur = ""
        cur = (cur + " " + line).strip()
    return out + ([cur] if cur else [])

def pcm_of(data):
    """Gemini may answer with a complete WAV file (44-byte RIFF header first) instead of bare samples.
    Played as samples, that header is a loud click at the start of every clip, so cut it off."""
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        i = data.find(b"data", 12)
        if i > 0: return data[i + 8:]
    return data

def clean(pcm):
    """Cut Gemini's loud noise burst at the end of the clip (heard as a squeak) - see tts_clean.py."""
    import numpy as np; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import tts_clean
    x = np.frombuffer(pcm, dtype=np.int16).copy(); ms = tts_clean.strip_tail(x, 24000)
    if ms: print(f'  end burst silenced ({ms} ms)')
    return x.tobytes()

def tts(text):
    last = ""
    for n in range(8):
        model = MODELS[0] if n < 3 else MODELS[n % len(MODELS)]     # stay on one model so the voice sounds the same; others only as a fallback
        r = requests.post(f"{API}/models/{model}:generateContent", headers={"x-goog-api-key": KEY}, timeout=240, json={
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}})
        if r.status_code < 400:
            try: return pcm_of(base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])), model
            except Exception as e: last = f"no audio in answer: {str(e)[:80]}"
        else:
            last = f"HTTP {r.status_code} {r.text[:300]}"
        print(f"{model}: {last}"); time.sleep((30 if "429" in last else 8) * (n + 1))
    raise SystemExit(f"Gemini voice failed: {last}")

if not KEY: raise SystemExit("GEMINI_API_KEY is not set")
secs = [(m.group(1), m.group(2).strip().replace(" ", "_"), m.group(3).strip())
        for m in re.finditer(r"^## (\d+) ([^\n]*)\n(.*?)(?=^## |\Z)", open(SCRIPT, encoding="utf-8").read(), re.S | re.M)]
only = [s.strip() for s in os.environ.get("ONLY", "").split(",") if s.strip()]
os.makedirs("out", exist_ok=True)
durs, files = {}, []
for num, name, text in secs:
    if only and num not in only: continue
    pcm = b""
    for p in pieces(text):
        a, model = tts(p); a = clean(a); pcm += a + b"\0" * int(24000 * 2 * 0.35)      # a short breath between pieces
        time.sleep(7)       # stay under the per-minute limit
    wav = f"out/{num}_{name}.wav"
    with wave.open(wav, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    files.append(wav); durs[f"{num}_{name}"] = round(len(pcm) / 48000, 1)
    print(f"{num} {name}: {durs[f'{num}_{name}']} s ({model})")
open("out/list.txt", "w").write("".join(f"file '{os.path.basename(f)}'\n" for f in files))
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "out/list.txt", "-b:a", "128k", "out/full.mp3"], check=True)
for f in files:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f, "-b:a", "128k", f[:-4] + ".mp3"], check=True); os.remove(f)
os.remove("out/list.txt")
durs["total"] = round(sum(durs.values()), 1)
json.dump(durs, open("out/durations.json", "w"), ensure_ascii=False, indent=1)
print("total:", durs["total"], "s")
