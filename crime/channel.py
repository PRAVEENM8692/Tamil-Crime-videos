"""Channel settings for the crime story channel, through the YouTube Data API with this repo's YT_* secrets.
DO = check (read only) | kids_off (channel 'made for kids' -> No) | private_old (make every public/unlisted video private)
     | about (set description/keywords from crime/channel_about.json). Nothing is ever deleted."""
import json, os, sys
import requests

DO = (os.environ.get("DO") or "check").strip()
API = "https://www.googleapis.com/youtube/v3"

def token():
    r = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={"client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
                      "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"})
    if r.status_code >= 400: raise SystemExit(f"YouTube key refused: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]

T = token(); H = {"Authorization": f"Bearer {T}"}
info = requests.get("https://oauth2.googleapis.com/tokeninfo", params={"access_token": T}, timeout=60).json()
scopes = [s.rsplit("/", 1)[-1] for s in info.get("scope", "").split()]
print("key permissions:", scopes)

def call(method, path, **kw):
    r = requests.request(method, f"{API}/{path}", headers=H, timeout=90, **kw)
    if r.status_code >= 400: print(f"{method} {path} -> HTTP {r.status_code}: {r.text[:400]}"); return None
    return r.json() if r.text else {}

ch = call("GET", "channels", params={"part": "snippet,status,brandingSettings,contentDetails,statistics", "mine": "true"})
if not ch or not ch.get("items"): raise SystemExit("could not read the channel (the key may only allow uploads)")
c = ch["items"][0]; cid = c["id"]
print("channel:", c["snippet"]["title"], "| id", cid, "| subscribers", c["statistics"].get("subscriberCount"), "| videos", c["statistics"].get("videoCount"))
print("made for kids (channel):", c["status"].get("madeForKids"), "| self declared:", c["status"].get("selfDeclaredMadeForKids"))
print("description now:", (c["snippet"].get("description") or "")[:300].replace("\n", " / "))

vids, page = [], None
while True:
    p = call("GET", "playlistItems", params={"part": "contentDetails", "playlistId": c["contentDetails"]["relatedPlaylists"]["uploads"], "maxResults": 50, **({"pageToken": page} if page else {})})
    if not p: break
    vids += [i["contentDetails"]["videoId"] for i in p.get("items", [])]; page = p.get("nextPageToken")
    if not page: break
det = []
for i in range(0, len(vids), 50):
    v = call("GET", "videos", params={"part": "snippet,status", "id": ",".join(vids[i:i + 50])})
    det += v.get("items", []) if v else []
for v in det: print("  video:", v["status"]["privacyStatus"], "| kids:", v["status"].get("madeForKids"), "|", v["snippet"]["title"][:70])

if DO == "kids_off":
    r = call("PUT", "channels", params={"part": "status"}, json={"id": cid, "status": {"selfDeclaredMadeForKids": False}})
    print("made for kids -> No:", "done, now " + str(r["status"].get("selfDeclaredMadeForKids")) if r else "FAILED")
elif DO == "private_old":
    n = 0
    for v in det:
        if v["status"]["privacyStatus"] != "private":
            st = {"privacyStatus": "private", "selfDeclaredMadeForKids": bool(v["status"].get("selfDeclaredMadeForKids", v["status"].get("madeForKids", False)))}
            if call("PUT", "videos", params={"part": "status"}, json={"id": v["id"], "status": st}) is not None: n += 1
    print("videos made private:", n)
elif DO == "about":
    a = json.load(open("crime/channel_about.json", encoding="utf-8"))
    b = c.get("brandingSettings", {}).get("channel", {})
    body = {"id": cid, "brandingSettings": {"channel": {"description": a["description"], "keywords": a.get("keywords", b.get("keywords", "")),
            "country": b.get("country", "IN"), "defaultLanguage": a.get("language", "ta")}}}
    if a.get("title"): body["brandingSettings"]["channel"]["title"] = a["title"]      # YouTube may ignore a name change made this way
    r = call("PUT", "channels", params={"part": "brandingSettings"}, json=body)
    print("about:", "updated; channel name is now: " + r["brandingSettings"]["channel"].get("title", "?") if r else "FAILED")
