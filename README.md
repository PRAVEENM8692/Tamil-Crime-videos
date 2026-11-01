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


## Video format (4-5 min, 1920x1080)
4.5 s animated logo intro -> 6 chapters / 36 scenes (every picture is generated from the exact narration beat it illustrates) -> ~9 s outro with animated LIKE, SUBSCRIBE and bell buttons.
Captions and scene changes are timed from the measured length of every spoken sentence, so they cannot drift.

Optional files in `assets/`: any `.mp3` for background music (ducks under the voice), and `logo.png` (your channel logo, used in the intro; without it the intro shows the channel name as text).
Optional repo variables: `CHANNEL_NAME`, `CHANNEL_TAGLINE`, `TTS_RATE` (default +8%), `TTS_PITCH` (default -2Hz), `BGM_FILE`.
Optional ElevenLabs voice (paid plan needed for daily use): secret `ELEVEN_API_KEY` + variable `ELEVEN_VOICE_ID`.
