import { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import ReactMarkdown from 'react-markdown'
import { ArrowLeft, ArrowRight, Check, Clipboard, FileAudio, FileText, LockKeyhole, Plus, Sparkles, UploadCloud, X } from 'lucide-react'
import './style.css'

async function api(path, options) {
  const response = await fetch(`/api${path}`, options)
  if (!response.ok) {
    let detail = 'Permintaan gagal. Coba lagi.'
    try { detail = (await response.json()).detail || detail } catch { /* Keep the fallback. */ }
    throw new Error(detail)
  }
  return response.json()
}

function App() {
  const [meetings, setMeetings] = useState([])
  const [selected, setSelected] = useState(null)
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [showTranscript, setShowTranscript] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    api('/meetings').then(setMeetings).catch((err) => setError(err.message))
  }, [])

  async function openMeeting(id) {
    setError('')
    try {
      setSelected(await api(`/meetings/${id}`))
      setShowTranscript(false)
    } catch (err) { setError(err.message) }
  }

  async function submit(event) {
    event.preventDefault()
    if (!file || busy) return
    setBusy(true)
    setError('')
    const form = new FormData()
    form.append('file', file)
    form.append('title', title)
    try {
      const meeting = await api('/meetings', { method: 'POST', body: form })
      setMeetings((current) => [{ id: meeting.id, title: meeting.title, created_at: meeting.created_at }, ...current])
      setSelected(meeting)
      setFile(null)
      setTitle('')
      if (inputRef.current) inputRef.current.value = ''
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  async function copyNotes() {
    if (!selected) return
    try {
      await navigator.clipboard.writeText(selected.notes)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { setError('Gagal menyalin notulen. Pilih teksnya secara manual.') }
  }

  function downloadNotes() {
    if (!selected) return
    const blob = new Blob([`# ${selected.title}\n\n${selected.notes}\n`], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `notulen-${selected.id.slice(0, 8)}.md`
    link.click()
    URL.revokeObjectURL(url)
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><FileText size={20}/></div><span>mom<span className="brand-light">taker</span></span></div>
      <button className="new-button" onClick={() => { setSelected(null); setError('') }}><Plus size={18}/> Rapat baru</button>
      <div className="sidebar-label">RAPAT TERSIMPAN <span>{meetings.length}</span></div>
      <nav className="meeting-list" aria-label="Rapat tersimpan">
        {meetings.length ? meetings.map((meeting) => <button key={meeting.id} className={`meeting-link ${selected?.id === meeting.id ? 'active' : ''}`} onClick={() => openMeeting(meeting.id)}><FileText size={17}/><span><strong>{meeting.title}</strong><small>{meeting.created_at}</small></span></button>) : <p className="sidebar-empty">Belum ada rapat. Unggah berkas pertama Anda.</p>}
      </nav>
      <div className="privacy-note"><LockKeyhole size={17}/><span>Notulen hanya tersimpan di perangkat ini.</span></div>
    </aside>

    <main className="main">
      <header className="topbar"><span>Ruang kerja / {selected ? 'Notulen rapat' : 'Rapat baru'}</span><div className="topbar-status"><span className="status-dot"/> Penyimpanan lokal</div></header>
      {error && <div className="error" role="alert"><span>{error}</span><button onClick={() => setError('')} aria-label="Tutup pesan"><X size={16}/></button></div>}
      {selected ? <div className="content detail">
        <button className="back" onClick={() => setSelected(null)}><ArrowLeft size={17}/> Kembali</button>
        <div className="detail-heading"><div><div className="eyebrow">NOTULEN RAPAT</div><h1>{selected.title}</h1><p>{selected.created_at} · Tersimpan di komputer ini</p></div><div className="actions"><button className="secondary" onClick={copyNotes}>{copied ? <Check size={16}/> : <Clipboard size={16}/>} {copied ? 'Tersalin' : 'Salin'}</button><button className="primary" onClick={downloadNotes}>Unduh .md <ArrowRight size={16}/></button></div></div>
        <article className="notes-card"><ReactMarkdown>{selected.notes}</ReactMarkdown></article>
        <section className="transcript-section"><button onClick={() => setShowTranscript(!showTranscript)}><FileAudio size={18}/> Transkrip sumber <span>{showTranscript ? 'Sembunyikan' : 'Lihat'}</span></button>{showTranscript && <div className="transcript-text">{selected.transcript}</div>}</section>
      </div> : <div className="content home">
        <div className="eyebrow"><Sparkles size={14}/> CATATAN RAPAT</div>
        <h1>Rapat selesai.<br/><span>Saatnya susun catatan.</span></h1>
        <p className="intro">Unggah rekaman atau transkrip. Mom Taker akan menyusun ringkasan, keputusan, dan tindak lanjut dalam Bahasa Indonesia.</p>
        <form onSubmit={submit} className="upload-card">
          <div className="card-head"><span className="step">01</span><div><h2>Buat notulen baru</h2><p>Pilih berkas rapat yang ingin dirangkum.</p></div></div>
          <label className="field-label" htmlFor="title">Nama rapat <span>opsional</span></label>
          <input id="title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} placeholder="Contoh: Rapat produk mingguan"/>
          <label className={`dropzone ${file ? 'has-file' : ''}`} htmlFor="file"><input ref={inputRef} id="file" type="file" required accept=".txt,.md,.mp3,.m4a,.wav,.webm,.mp4,.mpeg,.mpga" onChange={(e) => setFile(e.target.files?.[0] || null)}/><div className="upload-icon">{file ? <FileText size={23}/> : <UploadCloud size={25}/>}</div><strong>{file ? file.name : 'Pilih rekaman atau transkrip'}</strong><span>{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : 'Klik untuk memilih berkas dari perangkat Anda'}</span></label>
          <div className="form-footer"><small>TXT, MD, MP3, M4A, WAV, WEBM, MP4 · Maks. 50 MB</small><button className="primary" type="submit" disabled={!file || busy}>{busy ? 'Sedang membuat notulen…' : 'Buat notulen'} {!busy && <ArrowRight size={17}/>}</button></div>
        </form>
        <div className="below"><div><span className="mini-icon"><LockKeyhole size={17}/></span><strong>Tersimpan secara lokal</strong><p>Notulen disimpan di komputer ini. Anda dapat mengunduhnya untuk dibagikan.</p></div><div><span className="mini-icon"><FileText size={17}/></span><strong>Periksa sebelum dibagikan</strong><p>Baca kembali notulen dan transkrip sumbernya sebelum mengirim hasil rapat.</p></div></div>
      </div>}
    </main>
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
