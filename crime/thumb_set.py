"""Replace the thumbnail of an already uploaded video (no re-upload). Env: VIDEO_ID, THUMB, YT_CLIENT_ID/SECRET/REFRESH_TOKEN."""
import os, requests
r = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={"client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
                  "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"})
r.raise_for_status()
H = {"Authorization": "Bearer " + r.json()["access_token"], "Content-Type": "image/jpeg"}
t = requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={os.environ['VIDEO_ID']}", headers=H, data=open(os.environ["THUMB"], "rb").read(), timeout=180)
print("thumbnail:", t.status_code, "" if t.status_code < 400 else t.text[:300]); t.raise_for_status()
