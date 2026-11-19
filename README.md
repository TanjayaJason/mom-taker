# Mom Taker

Local-first meeting note taker MVP. Upload a UTF-8 transcript (`.txt` or `.md`) or an audio file (`.mp3`, `.m4a`, `.wav`, `.webm`, `.mp4`); Mom Taker creates Indonesian notes with a configurable OpenAI-compatible API.

## Run locally

1. Install Python 3.10 or newer.
2. Create and activate a virtual environment, then run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_TRANSCRIPTION_MODEL` for your provider.
4. Run `uvicorn app:app --host 127.0.0.1 --port 8000`.
5. Open http://127.0.0.1:8000.

The app listens on localhost by default. Notes and transcripts are stored as JSON under `data/`; source audio is not retained. Keep this folder private. The owner reviews notes and can share them manually outside the app. The app does not yet include user accounts, a share workflow, or meeting-bot integrations.

An OpenAI-compatible provider must implement `/chat/completions` and, when uploading audio, `/audio/transcriptions`.
