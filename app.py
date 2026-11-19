import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles


APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env")
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
TEXT_TYPES = {".txt", ".md"}
AUDIO_TYPES = {".mp3", ".m4a", ".wav", ".webm", ".mp4", ".mpeg", ".mpga"}

app = FastAPI(title="Mom Taker", docs_url=None, redoc_url=None)


def config(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def api_url(path: str) -> str:
    base = config("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    return f"{base}/{path}"


def api_headers() -> dict[str, str]:
    key = config("OPENAI_API_KEY")
    if not key:
        raise HTTPException(503, "OPENAI_API_KEY belum diatur. Salin .env.example menjadi .env lalu isi konfigurasi.")
    return {"Authorization": f"Bearer {key}"}


async def transcribe(filename: str, content: bytes) -> str:
    model = config("OPENAI_TRANSCRIPTION_MODEL")
    if not model:
        raise HTTPException(503, "OPENAI_TRANSCRIPTION_MODEL belum diatur.")
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                api_url("audio/transcriptions"),
                headers=api_headers(),
                data={"model": model},
                files={"file": (filename, content, "application/octet-stream")},
            )
        response.raise_for_status()
        transcript = response.json().get("text", "").strip()
        if not transcript:
            raise HTTPException(502, "Layanan transkripsi mengembalikan teks kosong.")
        return transcript
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, f"Transkripsi gagal: {exc.response.text[:500]}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Tidak dapat menghubungi layanan transkripsi: {exc}") from exc


async def summarize(transcript: str) -> str:
    model = config("OPENAI_MODEL")
    if not model:
        raise HTTPException(503, "OPENAI_MODEL belum diatur.")
    system_prompt = """Anda adalah Mom Taker, pencatat rapat yang teliti. Buat notulen dalam Bahasa Indonesia berdasarkan transkrip saja. Jangan mengarang nama, keputusan, tenggat, atau penanggung jawab. Tandai informasi yang tidak jelas sebagai 'Belum disebutkan'. Bedakan keputusan final dari usulan. Keluarkan Markdown ringkas dengan bagian: Ringkasan, Poin penting, Keputusan, dan Tindak lanjut (tugas | penanggung jawab | tenggat). Jika tidak ada isi untuk suatu bagian, tulis 'Tidak ada yang tercatat'."""
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                api_url("chat/completions"),
                headers={**api_headers(), "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Buat notulen dari transkrip berikut:\n\n{transcript}"},
                    ],
                    "temperature": 0.2,
                },
            )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, f"Pembuatan notulen gagal: {exc.response.text[:500]}") from exc
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(502, f"Respons layanan AI tidak dapat dibaca: {exc}") from exc


@app.get("/api/meetings")
async def list_meetings():
    meetings = []
    for path in sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            meetings.append({key: item[key] for key in ("id", "title", "created_at")})
        except (OSError, ValueError, KeyError):
            continue
    return meetings


@app.post("/api/meetings", status_code=201)
async def create_meeting(file: UploadFile = File(...), title: str = Form("")):
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in TEXT_TYPES | AUDIO_TYPES:
        raise HTTPException(400, "Format file tidak didukung.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "File kosong atau lebih besar dari batas 50 MB.")
    if suffix in TEXT_TYPES:
        try:
            transcript = content.decode("utf-8-sig").strip()
        except UnicodeDecodeError as exc:
            raise HTTPException(400, "Transkrip harus berupa teks UTF-8.") from exc
    else:
        transcript = await transcribe(filename, content)
    if not transcript:
        raise HTTPException(400, "Transkrip kosong.")
    notes = await summarize(transcript)
    meeting_id = uuid.uuid4().hex
    meeting = {
        "id": meeting_id,
        "title": title.strip()[:120] or Path(filename).stem or "Rapat",
        "created_at": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M"),
        "transcript": transcript,
        "notes": notes,
    }
    (DATA_DIR / f"{meeting_id}.json").write_text(json.dumps(meeting, ensure_ascii=False, indent=2), encoding="utf-8")
    return meeting


@app.get("/api/meetings/{meeting_id}")
async def get_meeting(meeting_id: str):
    if not meeting_id.isalnum() or len(meeting_id) != 32:
        raise HTTPException(404, "Notulen tidak ditemukan.")
    path = DATA_DIR / f"{meeting_id}.json"
    try:
        meeting = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(404, "Notulen tidak ditemukan.") from exc
    return meeting


DIST_DIR = APP_DIR / "frontend" / "dist"
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="frontend")
