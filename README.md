# Mom Taker

Mom Taker membuat notulen rapat berbahasa Indonesia dari transkrip atau rekaman yang Anda unggah. Antarmukanya memakai React dan backend-nya memakai FastAPI.

## Run locally

1. Pasang Python 3.10+ dan Node.js 20+.
2. Buat virtual environment Python, lalu jalankan `pip install -r requirements.txt`.
3. Salin `.env.example` ke `.env`. Isi API key, base URL, model chat, dan model transkripsi dari provider Anda.
4. Di folder `frontend`, jalankan `npm install` lalu `npm run build`.
5. Kembali ke folder proyek. Jalankan `uvicorn app:app --host 127.0.0.1 --port 8000` dan buka http://127.0.0.1:8000.

Untuk mengubah tampilan selama pengembangan, jalankan backend dan `npm run dev` di folder `frontend`. Buka alamat yang ditampilkan Vite. Permintaan `/api` akan diteruskan ke FastAPI.

Notulen dan transkrip disimpan di folder `data/` pada komputer ini. Rekaman asli tidak disimpan. Periksa hasilnya sebelum membagikan file Markdown yang diunduh. Aplikasi ini ditujukan untuk penggunaan lokal; belum ada akun pengguna atau pengaturan akses jaringan.

Provider OpenAI-compatible harus mendukung `/chat/completions`. Untuk unggahan audio, provider juga harus mendukung `/audio/transcriptions`.
