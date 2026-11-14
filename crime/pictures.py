"""Tamil crime story channel: draw the story pictures with the free Cloudflare Workers AI FLUX schnell model.
Env: CF_ACCOUNT_ID, CF_API_TOKEN. ONLY = scene numbers to draw (comma separated, empty = all still missing). Writes out/NN.jpg."""
import base64, io, json, os, sys, time, urllib.error, urllib.request

CF_ID, CF_TOKEN = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_API_TOKEN")
SCENES = os.environ.get("SCENES") or "crime/alavandar/scenes.json"
STYLE = ("Indian crime comic book illustration, bold clean black ink outlines, flat colours with soft cel shading, "
         "muted vintage palette of sepia, teal and amber, dramatic film-noir lighting, richly detailed background, expressive faces, cinematic. ")
END = " Clean floor, calm tidy scene. Nothing cut off at the frame edges. No text, no letters, no numbers, no captions, no watermark, no border."

def draw(prompt, dst):
    from PIL import Image
    klein = (os.environ.get("MODEL") or "").startswith("klein")      # MODEL=klein: FLUX.2 klein 4B, drawn 16:9 (1280x720); default: FLUX.1 schnell, square
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ID}/ai/run/@cf/black-forest-labs/" + ("flux-2-klein-4b" if klein else "flux-1-schnell")
    last = None
    for n in range(4):
        try:
            if klein:
                b = "----crimeboundary7f3a"
                parts = {"prompt": prompt[:2000], "width": "1280", "height": "720"}
                body = "".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in parts.items()).encode() + f"--{b}--\r\n".encode()
                req = urllib.request.Request(url, body, {"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": f"multipart/form-data; boundary={b}"})
            else:
                body = json.dumps({"prompt": prompt[:2000], "steps": 4}).encode()
                req = urllib.request.Request(url, body, {"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"})
            raw = base64.b64decode(json.load(urllib.request.urlopen(req, timeout=180))["result"]["image"])
            Image.open(io.BytesIO(raw)).convert("RGB").save(dst, quality=90)
            return True
        except urllib.error.HTTPError as e: last = f"HTTP {e.code}: {e.read()[:300]!r}"
        except Exception as e: last = str(e)
        time.sleep(4 * (n + 1))
    print("picture failed:", last); return False

if not (CF_ID and CF_TOKEN):
    raise SystemExit("CF_ACCOUNT_ID / CF_API_TOKEN secrets are not set on this repo (Settings > Secrets and variables > Actions)")
redo = {int(x) for x in (os.environ.get("REDO") or "").replace(" ", "").split(",") if x}
only = {int(x) for x in (os.environ.get("ONLY") or "").replace(" ", "").split(",") if x}
os.makedirs("out", exist_ok=True)
done, fails = [], 0
for s in json.load(open(SCENES, encoding="utf-8"))["shots"]:
    f = f"out/{s['n']:02d}.jpg"
    if s["n"] in redo and os.path.exists(f): os.remove(f)
    if (only and s["n"] not in only) or (not only and os.path.exists(f)): continue
    style = STYLE.replace("expressive faces, ", "") + "Objects only, absolutely no people, no faces, no portraits. " if s["scene"].startswith(("Still life", "A clean anatomy", "Empty")) else STYLE
    if draw(style + s["scene"] + END, f): done.append(s["n"]); fails = 0; print(f"picture {s['n']:02d} drawn")
    else:
        fails += 1
        if fails >= 3: print("3 failures in a row (daily free limit?), stopping"); break
print("drawn:", done)
if not done: raise SystemExit("no pictures were drawn")
