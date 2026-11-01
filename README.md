# Tamil Crime Files – Daily Solved-Crime Videos (long-form 16:9)

Fully automated daily long-form (8-10 min, 1920x1080) YouTube video in 7 chapters: an original, solved, thrilling crime story told in Tamil by a male voice (`ta-IN-ValluvarNeural`) over AI-animated (3D cartoon style) images with running captions.

## No repeated stories
Every day the pipeline picks a fresh combination of crime + place + twist + clue + investigator, avoids combos already in `history.json`, tells the LLM the last 40 titles to avoid, and rejects titles >70% similar. `history.json` is committed back after each upload.

## Setup (all free)
Repo > Settings > Secrets and variables > Actions:
- Secrets: `LLM_API_KEY` (Groq), `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`
- Variables (optional): `LLM_BASE_URL`, `LLM_MODEL`, `TTS_VOICE`, `YT_PRIVACY`
- Settings > Actions > General > Workflow permissions = **Read and write**

## Schedule: 2 videos a day
Slot 1 = 12:00 IST (murder/mystery stories), slot 2 = 18:00 IST (heists/frauds/thefts). The workflow wakes every 30 min; `plan.py` starts whichever slot is due and not done today (max 3 tries), so late or skipped GitHub crons don't lose a video. Each slot has its own crime pool, and the last 6 crime types are never reused.

## First test
Actions > Daily Crime Video > Run workflow, `upload=false`. Download the `video` artifact, check `frame_check.png` and `video.mp4`, `thumbnail.jpg`. Then run once with `upload=true`. After that it runs daily at 18:00 IST.

Optional: add royalty-free `assets/bgm.mp3` for background music.

All stories are fictional.
