import { useRef, useState, type DragEvent, type ChangeEvent, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import JSZip from 'jszip'
import './styles.css'

type Report = {
  questionCount: number
  correctAnswerCount: number
  stimulusQuestionCount: number
  stimulusTypes: string[]
  warnings: string[]
  questions: Array<{ number: number; correctOption: number | null; stimulus: boolean; stimulusBlocks: number }>
}

type Result = {
  report: Report
  downloads: { docx: string; report: string }
}

function decodeReportHeader(value: string | null): Report {
  if (!value) throw new Error('Laporan hasil tidak ditemukan pada respons server.')
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4)
  const binary = atob(normalized)
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0))
  return JSON.parse(new TextDecoder().decode(bytes)) as Report
}

const MAX_SERVERLESS_UPLOAD = 4_000_000

async function compressDocxImages(file: File): Promise<File> {
  if (file.size <= MAX_SERVERLESS_UPLOAD) return file
  const zip = await JSZip.loadAsync(await file.arrayBuffer())
  const imageEntries = Object.keys(zip.files).filter((name) => name.startsWith('word/media/') && name.toLowerCase().endsWith('.png'))
  for (const name of imageEntries) {
    const original = await zip.files[name].async('blob')
    const url = URL.createObjectURL(original)
    try {
      const image = await new Promise<HTMLImageElement>((resolve, reject) => {
        const element = new Image()
        element.onload = () => resolve(element)
        element.onerror = () => reject(new Error(`Gambar ${name} tidak dapat dibaca.`))
        element.src = url
      })
      const scale = Math.min(1, 1800 / Math.max(image.naturalWidth, image.naturalHeight))
      const canvas = document.createElement('canvas')
      canvas.width = Math.max(1, Math.round(image.naturalWidth * scale))
      canvas.height = Math.max(1, Math.round(image.naturalHeight * scale))
      const context = canvas.getContext('2d')
      if (context) context.fillStyle = '#ffffff'
      context?.fillRect(0, 0, canvas.width, canvas.height)
      context?.drawImage(image, 0, 0, canvas.width, canvas.height)
      const compressed = await new Promise<Blob>((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error(`Gambar ${name} gagal dikompres.`)), 'image/jpeg', 0.82))
      const jpgName = name.replace(/\.png$/i, '.jpg')
      const relativeJpgName = jpgName.replace(/^word\//, '')
      zip.file(jpgName, compressed)
      zip.remove(name)
      for (const textName of ['[Content_Types].xml', 'word/_rels/document.xml.rels']) {
        const entry = zip.files[textName]
        if (entry) {
          const text = await entry.async('string')
          zip.file(textName, text.replaceAll(name, jpgName).replaceAll(name.replace(/^word\//, ''), relativeJpgName).replaceAll('image/png', 'image/jpeg').replace('Extension="png"', 'Extension="jpg"'))
        }
      }
    } finally {
      URL.revokeObjectURL(url)
    }
  }
  const bytes = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 } })
  if (bytes.size > MAX_SERVERLESS_UPLOAD) throw new Error('Dokumen sumber masih terlalu besar setelah kompresi gambar. Coba kurangi ukuran gambar di Word lalu unggah kembali.')
  return new File([bytes], file.name, { type: file.type || 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
}

function FileGlyph() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3.75h6.1L18.5 9v10.75A1.25 1.25 0 0 1 17.25 21h-10A1.25 1.25 0 0 1 6 19.75V5a1.25 1.25 0 0 1 1.25-1.25Z"/><path d="M13 3.75V9h5.5M9 13h6M9 16.5h6"/></svg>
}

function UploadGlyph() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M5 14.5v3.25A1.75 1.75 0 0 0 6.75 19.5h10.5A1.75 1.75 0 0 0 19 17.75V14.5"/></svg>
}

function CheckGlyph() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.3 4.3L19 7.2"/></svg>
}

function ArrowGlyph() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h13m-5-5 5 5-5 5"/></svg>
}

function UploadCard({ label, hint, file, onFile }: { label: string; hint: string; file: File | null; onFile: (file: File | null) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const accept = '.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  const choose = (event: ChangeEvent<HTMLInputElement>) => onFile(event.target.files?.[0] ?? null)
  const drop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    onFile(event.dataTransfer.files?.[0] ?? null)
  }
  return <div className={`upload-card ${dragging ? 'is-dragging' : ''} ${file ? 'has-file' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={drop}>
    <input ref={inputRef} type="file" accept={accept} onChange={choose} hidden />
    <div className="upload-card-top"><span className="step-number">{label === 'Dokumen soal sumber' ? '01' : '02'}</span><span className="file-type">DOCX</span></div>
    <div className="upload-card-body">
      <div className="upload-icon"><FileGlyph /></div>
      <div className="upload-copy">
        <strong>{label}</strong>
        {file ? <span className="selected-file"><CheckGlyph /> {file.name}</span> : <span>{hint}</span>}
      </div>
      <button type="button" className="button button-quiet" onClick={() => inputRef.current?.click()}>{file ? 'Ganti' : 'Pilih file'}</button>
    </div>
  </div>
}

function Stat({ value, label, accent = false }: { value: string | number; label: string; accent?: boolean }) {
  return <div className={`stat ${accent ? 'accent' : ''}`}><strong>{value}</strong><span>{label}</span></div>
}

function App() {
  const [source, setSource] = useState<File | null>(null)
  const [template, setTemplate] = useState<File | null>(null)
  const [status, setStatus] = useState<'idle' | 'processing' | 'done' | 'error'>('idle')
  const [error, setError] = useState('')
  const [result, setResult] = useState<Result | null>(null)

  const ready = Boolean(source && template)
  const processFiles = async () => {
    if (!source || !template) return
    setStatus('processing')
    setError('')
    setResult(null)
    try {
      const compactSource = await compressDocxImages(source)
      const form = new FormData()
      form.append('source', compactSource)
      form.append('template', template)
      const response = await fetch('/api/convert', { method: 'POST', body: form })
      const contentType = response.headers.get('content-type') || ''
      if (!response.ok) {
        const payload = await response.json() as { error?: string }
        throw new Error(payload.error || 'Konversi tidak berhasil.')
      }
      if (contentType.includes('application/vnd.openxmlformats-officedocument.wordprocessingml.document')) {
        const docx = await response.blob()
        const report = decodeReportHeader(response.headers.get('x-soalconvert-report'))
        const reportBlob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
        setResult({ report, downloads: { docx: URL.createObjectURL(docx), report: URL.createObjectURL(reportBlob) } })
      } else {
        const payload = await response.json() as Result
        setResult(payload)
      }
      setStatus('done')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Konversi tidak berhasil.')
      setStatus('error')
    }
  }

  return <div className="app-shell">
    <header className="topbar">
      <a className="brand" href="/" aria-label="SoalConvert beranda"><span className="brand-mark">[✓]</span><span>Soal<span>Convert</span></span></a>
      <div className="topbar-note"><span className="status-dot" /> Pemrosesan sementara · file tidak disimpan permanen</div>
    </header>

    <main>
      <section className="hero page-width">
        <div className="hero-copy">
          <p className="eyebrow">WORD → EXAM BROWSER</p>
          <h1>Siapkan soal tanpa<br /><em>salin satu per satu.</em></h1>
          <p className="hero-lede">Unggah dokumen soal dan template tujuan. SoalConvert membaca jawaban merah, membawa stimulus ke setiap soal terkait, lalu menyiapkan file import untuk Anda.</p>
        </div>
        <div className="hero-aside"><span className="aside-label">ATURAN INTI</span><p>Opsi merah menjadi <b>1</b>. Opsi lain menjadi <b>0</b>. Label A–D dilepas agar Exam Browser bebas mengacak jawaban.</p></div>
      </section>

      <section className="workspace page-width">
        <div className="workspace-main">
          <div className="section-heading"><div><p className="eyebrow">LANGKAH 01 / SUMBER</p><h2>Masukkan dua dokumen kerja.</h2></div><span className={`ready-pill ${ready ? 'ready' : ''}`}>{ready ? 'Siap diproses' : 'Menunggu file'}</span></div>
          <div className="upload-stack">
            <UploadCard label="Dokumen soal sumber" hint="Soal Pemkab dengan jawaban benar berwarna merah" file={source} onFile={setSource} />
            <UploadCard label="Template Word tujuan" hint="Format form-soal-ganda yang akan diimpor" file={template} onFile={setTemplate} />
          </div>
          {status === 'error' && <div className="alert error"><strong>Belum bisa diproses.</strong><span>{error}</span></div>}
          <button className="process-button" type="button" disabled={!ready || status === 'processing'} onClick={processFiles}>{status === 'processing' ? <><span className="spinner" /> Membaca struktur dokumen…</> : <>Proses dan buat Word hasil <ArrowGlyph /></>}</button>
          <p className="privacy-note"><span className="lock-mark">◇</span> File sumber dan hasil diproses sementara di server, lalu dibersihkan otomatis.</p>
        </div>
        <aside className="workspace-aside">
          <p className="eyebrow">YANG AKAN DILAKUKAN</p>
          <ol className="rule-list">
            <li><span>01</span><div><strong>Deteksi soal</strong><p>Empat opsi dibaca dari struktur Word, bukan dari posisi visual semata.</p></div></li>
            <li><span>02</span><div><strong>Bawa stimulus</strong><p>Cerita, puisi, tabel, gambar, atau infografik ditempel ulang pada soal terkait.</p></div></li>
            <li><span>03</span><div><strong>Isi template</strong><p>Contoh input dikosongkan. Jawaban tanpa A–D, nilai benar/salah otomatis.</p></div></li>
          </ol>
          <div className="note-card"><span className="note-card-label">CATATAN</span><p>Versi awal memproses soal pilihan ganda dengan empat opsi. Soal uraian tidak dimasukkan ke template ini.</p></div>
        </aside>
      </section>

      {status === 'processing' && <section className="progress-section page-width"><div className="progress-label"><span>Memeriksa warna, struktur, dan media dokumen…</span><span>sedang berjalan</span></div><div className="progress-track"><div className="progress-bar" /></div></section>}

      {result && status === 'done' && <section className="result-section page-width">
        <div className="result-heading"><div><p className="eyebrow">LANGKAH 02 / HASIL</p><h2>Dokumen siap diperiksa.</h2><p>Ringkasan ini berasal dari struktur Word yang terbaca. Unduh hasil dan laporan sebelum mengimpor.</p></div><div className="result-stamp"><CheckGlyph /> SELESAI</div></div>
        <div className="stats-row"><Stat value={result.report.questionCount} label="soal terdeteksi" accent /><Stat value={`${result.report.correctAnswerCount}/${result.report.questionCount}`} label="kunci terbaca" /><Stat value={result.report.stimulusQuestionCount} label="soal dengan stimulus" /><Stat value={result.report.warnings.length} label="peringatan" /></div>
        <div className="download-row"><a className="download-card primary" href={result.downloads.docx}><span className="download-icon"><FileGlyph /></span><span><strong>Unduh Word hasil</strong><small>soal-exam-browser.docx</small></span><ArrowGlyph /></a><a className="download-card" href={result.downloads.report}><span className="download-icon report-icon">{`{ }`}</span><span><strong>Unduh laporan validasi</strong><small>laporan-validasi.json</small></span><ArrowGlyph /></a></div>
        {result.report.warnings.length > 0 ? <div className="alert warning"><strong>Perlu pemeriksaan manual ({result.report.warnings.length})</strong><ul>{result.report.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></div> : <div className="alert success"><CheckGlyph /><span><strong>Semua {result.report.questionCount} soal memiliki satu jawaban merah.</strong> Tidak ada peringatan struktur pada pemrosesan ini.</span></div>}
      </section>}
    </main>
    <footer className="footer page-width"><span>SoalConvert / alat kerja guru</span><span>dibuat untuk alur import Exam Browser</span></footer>
  </div>
}

createRoot(document.getElementById('root')!).render(<App />)
