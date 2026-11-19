import html
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse


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


def page(body: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Mom Taker</title>
<style>body{{font:16px system-ui;max-width:850px;margin:40px auto;padding:0 20px;color:#222}}h1{{margin-bottom:4px}}.muted{{color:#666}}form,.card{{border:1px solid #ddd;border-radius:12px;padding:20px;margin:20px 0}}input,button{{font:inherit;margin:8px 0}}button{{padding:9px 16px;cursor:pointer}}pre{{white-space:pre-wrap;font:inherit;line-height:1.55}}a{{color:#175c9e}}</style>
<body><h1>Mom Taker</h1><p class="muted">Unggah transkrip atau rekaman untuk membuat notulen rapat.</p>{body}</body></html>""")


@app.get("/", response_class=HTMLResponse)
async def home():
    meetings = []
    for path in sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            meetings.append(f'<li><a href="/meetings/{item["id"]}">{html.escape(item["title"])}</a> <span class="muted">{html.escape(item["created_at"])}</span></li>')
        except (OSError, ValueError, KeyError):
            continue
    body = f"""<form action="/meetings" method="post" enctype="multipart/form-data"><label>Nama rapat (opsional)<br><input name="title" maxlength="120" placeholder="Contoh: Weekly Product Sync"></label><br><label>File transkrip (.txt/.md) atau audio (.mp3, .m4a, .wav, .webm, .mp4)<br><input type="file" name="file" required accept=".txt,.md,.mp3,.m4a,.wav,.webm,.mp4,.mpeg,.mpga"></label><br><button type="submit">Buat notulen</button></form><h2>Notulen tersimpan</h2><ul>{''.join(meetings) or '<li class="muted">Belum ada notulen.</li>'}</ul>"""
    return page(body)


@app.post("/meetings", response_class=HTMLResponse)
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
    return HTMLResponse(status_code=303, headers={"Location": f"/meetings/{meeting_id}"})


@app.get("/meetings/{meeting_id}", response_class=HTMLResponse)
async def get_meeting(meeting_id: str):
    if not meeting_id.isalnum() or len(meeting_id) != 32:
        raise HTTPException(404, "Notulen tidak ditemukan.")
    path = DATA_DIR / f"{meeting_id}.json"
    try:
        meeting = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(404, "Notulen tidak ditemukan.") from exc
    title = html.escape(meeting["title"])
    notes = html.escape(meeting["notes"])
    transcript = html.escape(meeting["transcript"])
    body = f"""<p><a href="/">← Semua notulen</a></p><h2>{title}</h2><p class="muted">{html.escape(meeting["created_at"])}</p><section class="card"><h3>Notulen</h3><pre>{notes}</pre></section><details class="card"><summary>Transkrip sumber</summary><pre>{transcript}</pre></details>"""
    return page(body)
