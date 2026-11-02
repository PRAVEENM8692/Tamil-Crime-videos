# Tamil Kids Story – animated YouTube videos (auto)

3 videos/day (9:00, 14:00, 19:00 IST), each about 3.5-4.5 minutes, 16:9 full HD, auto-uploaded.
Each video = your channel intro animation -> a simple, casual Tamil cartoon story (a friendly narrator + 2-4 characters
with different Gemini voices, no subtitles, only a small name tag) -> like / subscribe / bell ending.
Every scene is a real AI video clip made with Puter (image-to-video: a cartoon picture of the scene is the first frame).
The channel logo bobs and pulses in the top-left corner from the end of the intro to the last second.

## Secrets (Settings > Secrets and variables > Actions > Secrets)
- LLM_API_KEY (Groq key; optional LLM_BASE_URL, LLM_MODEL)
- PUTER_AUTH_TOKEN (Gemini voices + backup pictures through Puter)
- YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Also: Settings > Actions > General > Workflow permissions = Read and write.

## Variables (all optional)
- YT_PRIVACY: private (default) / unlisted / public
- TTS_ENGINE: puter (default when the token is set) or edge
- NARRATOR_VOICE: a Gemini voice name, default Charon (Kore or Sulafat for a woman)
- PUTER_VOICE_MAP: JSON, e.g. {"boy":"Puck","girl":"Leda"}
- IMG_ENGINES: default "pollinations,puter" (order tried)
- INTRO: false to skip the intro; INTRO_SECONDS: default 9
- USE_PUTER_VIDEO: false = no AI clips (scene pictures only)
- VIDEO_TEST: true = Puter returns its sample clip and spends NO credits (use for the first test of the whole chain)
- VIDEO_MODEL: default wan-ai/wan2.7-i2v (try bytedance/seedance-2.0 or kling-3.0-turbo); VIDEO_MODE: i2v (default) or t2v
- VIDEO_SIZE (default 720P), VIDEO_MIN_SECONDS (4), VIDEO_MAX_SECONDS (8), MAX_AI_CLIPS (45), VID_CONCURRENCY (3)
- FALLBACK_MOTION: true = a scene whose AI clip failed gets a slow zoom; default is a still picture
- CHANNEL_NAME, MADE_FOR_KIDS, BGM_FILE

## Files in assets/
- intro.mp4  your intro animation (16:9 is shown full screen; other shapes are fitted over a blurred copy)
- logo.png   round-cornered channel logo (corner animation + thumbnail)
- bgm.mp3    background music

## Cost warning
AI video clips are NOT free: Puter bills them per second to the account that owns PUTER_AUTH_TOKEN. One video needs about
3-4 minutes of clips, so 3 videos a day is roughly 10-12 minutes of generated video per day. Check the price of your model
in your Puter account before running it daily. If the balance runs out, Puter shortens or refuses clips and those scenes
fall back to still pictures, so the video still gets made.

## First test
1) Set variable VIDEO_TEST = true, run the workflow with upload = false (spends no Puter credits; checks the whole chain).
2) Remove VIDEO_TEST, run again with upload = false for one real video (AI clips take about 40-90 minutes).
Download the "kids-video" artifact: video.mp4, thumbnail.jpg, script.json, frame_*.png.
Listen to the voices and check the story, then set YT_PRIVACY and run with upload = true.
