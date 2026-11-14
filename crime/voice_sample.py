"""Tamil crime story channel: a short Gemini voice sample (hook of the Alavandar case) in a few voices, to pick the narrator.
Needs GEMINI_API_KEY. Writes out/sample_<voice>.mp3."""
import base64, os, subprocess, sys, time, wave
import requests

API = "https://generativelanguage.googleapis.com/v1beta"
KEY = os.environ.get("GEMINI_API_KEY", "")
MODELS = [m.strip() for m in (os.environ.get("TTS_MODEL") or "gemini-3.8-flash-tts,gemini-3.8-flash-lite-tts,gemini-3.1-flash-tts-preview").split(",") if m.strip()]
VOICES = [v.strip() for v in (os.environ.get("SAMPLE_VOICES") or "Charon,Algenib").split(",") if v.strip()]
STYLE = ("Read this in Tamil as a true-crime story narrator talking to a friend: low, tense, natural spoken Tamil, "
         "a brisk conversational pace, a short breath between sentences, a slightly longer pause at each '…'. Do not sound like a news reader: ")
TEXT = ("1952-ஆம் வருஷம், ஆகஸ்ட் 29. மதியம் பன்னிரண்டு மணி. "
        "மானாமதுரை ரயில் நிலையம். மெட்ராஸ்ல இருந்து வந்த போட் மெயில் ரயில் நிக்குது. "
        "மூணாம் வகுப்புப் பெட்டியில ஒரு இருக்கைக்கு அடியில, ஒரு பெரிய பச்சை நிற இரும்புப் பெட்டி. அதுல இருந்து தாங்க முடியாத நாத்தம். "
        "போலீஸ் வந்து பெட்டியைத் திறக்கறாங்க. "
        "உள்ளே ஒரு மனுஷ உடல். ஆனா அந்த உடலுக்கு… தலை இல்லை. "
        "இவர் யாரு? தலை எங்கே? இந்தப் பெட்டியை ரயில்ல வெச்சது யாரு? "
        "DNA டெஸ்ட் இல்லாத, CCTV இல்லாத காலத்துல, மெட்ராஸ் போலீஸ் இந்த வழக்கை எப்படி உடைச்சாங்க? கடைசி வரை பாருங்க.")

def tts(voice):
    last = ""
    for n in range(6):
        model = MODELS[n % len(MODELS)]
        r = requests.post(f"{API}/models/{model}:generateContent", headers={"x-goog-api-key": KEY}, timeout=180, json={
            "contents": [{"parts": [{"text": STYLE + TEXT}]}],
            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}})
        if r.status_code < 400:
            try: return base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]), model
            except Exception as e: last = f"no audio in answer: {str(e)[:80]}"
        else:
            last = f"HTTP {r.status_code} {r.text[:300]}"
        print(f"{voice} / {model}: {last}"); time.sleep(8 * (n + 1))
    raise SystemExit(f"Gemini voice failed for {voice}: {last}")

if not KEY: raise SystemExit("GEMINI_API_KEY is not set")
os.makedirs("out", exist_ok=True)
for v in VOICES:
    pcm, model = tts(v)
    wav = f"out/sample_{v}.wav"
    with wave.open(wav, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-b:a", "128k", wav[:-4] + ".mp3"], check=True); os.remove(wav)
    print(f"{v}: {len(pcm) / 48000:.1f} s ({model})")
