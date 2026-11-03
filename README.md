# Tamil Kids Story (Gemini only)

Script, voices and animated clips all come straight from the Google Gemini API. No Puter, no Node.

## Secrets (Settings > Secrets and variables > Actions)
- `GEMINI_API_KEY` : key from https://aistudio.google.com/apikey (billing must be enabled, Veo is paid)
- `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` : YouTube upload

## Optional variables
`LLM_MODEL` (gemini-3.8-flash), `TTS_MODEL` (gemini-2.5-flash-preview-tts), `VIDEO_MODEL` (veo-3.1-lite-generate-preview),
`VIDEO_RES` (720p), `VID_CONCURRENCY` (3), `NARRATOR_VOICE`, `VOICE_MAP`, `INTRO`, `INTRO_SECONDS`, `CHANNEL_NAME`, `YT_PRIVACY`.

## Test in this order
1. Actions > Run workflow: `upload=false`, `dry_video=true`. Costs almost nothing (text + voice only, placeholder clips). Check layout, voices, intro, logo, outro.
2. Same with `dry_video=false`: real Veo clips, no upload. This is the paid test, one video.
3. Happy with it? Schedule runs by itself (3 slots a day).

## Cost
Each video asks Veo for 16 clips of 4-8 s (a story of about 2 minutes). At Veo 3.1 Lite prices that is roughly 90-130 s of generated video per story, so check the current price on the Gemini API pricing page and set a billing budget alert in Google AI Studio.
