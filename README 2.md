> NOTE: This file is kept for legacy/client notes.
>
> The main, updated instructions (cell-wise / Colab-style) are in `README.md`.

# Automated World News → Indian Voice Video → YouTube

Pipeline scaffold for a **15-minute style** news video: collect headlines, generate a simple script, Indian-accent TTS, combine with client anchor image + stock visuals, optional background music, upload metadata to YouTube.

## What “free” usually means in practice

- **No paid SaaS** is possible if you use **RSS**, **Edge TTS** (Microsoft’s free edge voices), **FFmpeg/MoviePy**, and **YouTube Data API** (free quota with OAuth).
- **LLM scripting** still needs *some* model access: OpenAI pay-as-you-go, or **Google AI Studio (Gemini) free tier**, or a **local model** on a GPU machine — pick one and wire it in `script_generator.py`.
- **“110% copyright-free”** is a marketing phrase. Safer approach: **Pexels / Pixabay / Wikimedia** with API + license metadata, or **AI-generated B-roll** (check your jurisdiction and platform policies).
- **Talking anchor like TV**: true lip-sync from a **static photo** needs **Wav2Lip / SadTalker** (GPU, setup heavy) or **paid APIs**. This repo uses a **professional layout**: anchor image + lower-third style + voiceover, which matches many successful faceless/anchor-style channels.

## Quick start

1. Python 3.10+ and **FFmpeg** installed (`ffmpeg -version`).
2. `cp .env.example .env` and fill keys as needed.
3. Put client **Indian women anchor** image(s) in `assets/anchor/` (PNG/JPG) — at least one real file (not only `.gitkeep`).
4. Each day, add **today’s news visuals** to `assets/news_today/` (sorted filenames: `01.jpg`, `02.mp4`, …). They become full-screen B-roll with the anchor in the **corner** (friend-style). If the folder is empty, the video uses **full-screen anchor** only.
5. `pip install -r requirements.txt`
6. Run: `python -m src.main --dry-run` (no YouTube upload)
7. YouTube: create OAuth **Desktop app** credentials, download JSON to `secrets/client_secret.json`, first run will open browser to authorize.

See `assets/README_ASSETS.txt` for the daily folder workflow (Hindi notes for the client).

## What you should do next (progress checklist)

1. Copy `.env.example` → `.env` and add **`OPENAI_API_KEY`** (script) and optionally **`PEXELS_API_KEY`** (auto stock images when `news_today/` is empty).
2. Install **FFmpeg**, then `pip install -r requirements.txt`.
3. Run **`python -m src.main --skip-upload`** until the MP4 + `thumbnail.jpg` in `temp/<timestamp>/` look good.
4. Add **`secrets/client_secret.json`** (YouTube OAuth), then upload without `--skip-upload`.
5. **Automate**: cron (Mac/Linux), Task Scheduler (Windows), or **Google Colab + Drive** for daily runs.

## Project layout

- `src/news_fetcher.py` — RSS-based world news collection.
- `src/script_generator.py` — LLM → ~15 min spoken script (target length configurable).
- `src/tts_edge.py` — Indian English / Hindi voices via `edge-tts`.
- `src/media_sources.py` — Lists daily images/videos from `assets/news_today/`.
- `src/pexels_fetch.py` — Optional Pexels downloads when the daily folder is empty.
- `src/thumbnail_gen.py` — 1280×720 JPEG thumbnail (headline + anchor inset).
- `src/video_compose.py` — Intro + B-roll slideshow + anchor corner (or full-screen anchor if no B-roll).
- `src/youtube_upload.py` — Title, description, tags, thumbnail path.
- `src/main.py` — Orchestration.

## Client requirements mapping

| Client ask | This scaffold |
|------------|----------------|
| World news | RSS feeds list (edit in `news_fetcher.py`) |
| Indian voice | `en-IN-*` or `hi-IN-*` voices in `tts_edge.py` |
| Anchor images | `assets/anchor/` + corner or full-screen in `video_compose.py` |
| Daily news images/video | `assets/news_today/` (or `NEWS_MEDIA_DIR` in `.env`) |
| Metadata | `youtube_upload.py` + generated title/description/tags |

## Legal / product note

You (or the client) should confirm **YouTube Partner Program**, **content policies**, and **news aggregation** terms for chosen sources. This code is a technical starting point, not legal advice.
