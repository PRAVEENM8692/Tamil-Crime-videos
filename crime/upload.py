"""Upload one crime-channel video to YouTube as PRIVATE, with thumbnail and the question comment.
Reads crime/<case>/youtube.json (title, description, tags, pinned_comment). Env: CASE (folder name, default alavandar), VIDEO (mp4 path), THUMB (jpg path).
Never makes the video public (the owner does that himself), never sets the 'altered / AI-generated content' flag, skips if a video with the same title exists."""
import json, os, requests

CASE = os.environ.get("CASE") or "alavandar"
VIDEO = os.environ.get("VIDEO") or f"out/{CASE}.mp4"
THUMB = os.environ.get("THUMB") or f"assets/crime_{CASE}_thumb.jpg"
meta = json.load(open(f"crime/{CASE}/youtube.json", encoding="utf-8"))
API = "https://www.googleapis.com/youtube/v3"

r = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={"client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
                  "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"})
if r.status_code >= 400: raise SystemExit(f"YouTube key refused: {r.status_code} {r.text[:200]}")
H = {"Authorization": "Bearer " + r.json()["access_token"]}

up = requests.get(f"{API}/channels", headers=H, params={"part": "contentDetails", "mine": "true"}, timeout=60).json()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
page = None
while True:
    d = requests.get(f"{API}/playlistItems", headers=H, params={"part": "snippet", "playlistId": up, "maxResults": 50, **({"pageToken": page} if page else {})}, timeout=60).json()
    for it in d.get("items", []):
        if it["snippet"]["title"] == meta["title"]: raise SystemExit(f"already uploaded: https://youtu.be/{it['snippet']['resourceId']['videoId']} - nothing done")
    page = d.get("nextPageToken")
    if not page: break

body = {"snippet": {"title": meta["title"], "description": meta["description"], "tags": meta["tags"], "categoryId": "22", "defaultLanguage": "ta", "defaultAudioLanguage": "ta"},
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "embeddable": True}}
size = os.path.getsize(VIDEO)
init = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status", timeout=120,
                     headers={**H, "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"}, json=body)
if init.status_code >= 400: raise SystemExit(f"upload start refused: {init.status_code} {init.text[:400]}")
done = requests.put(init.headers["Location"], data=open(VIDEO, "rb"), headers={"Content-Type": "video/mp4"}, timeout=1800)
if done.status_code >= 400: raise SystemExit(f"upload failed: {done.status_code} {done.text[:400]}")
vid = done.json()["id"]; print(f"uploaded (private): https://youtu.be/{vid}  size {size / 1e6:.1f} MB")

t = requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}", headers={**H, "Content-Type": "image/jpeg"}, data=open(THUMB, "rb").read(), timeout=180)
print("thumbnail:", t.status_code, "" if t.status_code < 400 else t.text[:300])

c = requests.post(f"{API}/commentThreads?part=snippet", headers=H, timeout=60, json={"snippet": {"videoId": vid, "topLevelComment": {"snippet": {"textOriginal": meta["pinned_comment"]}}}})
print("comment:", c.status_code, "" if c.status_code < 400 else c.text[:300])
print("privacy now:", requests.get(f"{API}/videos", headers=H, params={"part": "status", "id": vid}, timeout=60).json()["items"][0]["status"])
