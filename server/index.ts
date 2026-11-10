import express from 'express'
import multer from 'multer'
import path from 'node:path'
import os from 'node:os'
import fs from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { fileURLToPath } from 'node:url'

const execFileAsync = promisify(execFile)
const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const port = Number(process.env.PORT || 3000)
const jobs = new Map<string, { dir: string; output: string; report: string; createdAt: number }>()

const app = express()
const upload = multer({
  dest: path.join(os.tmpdir(), 'soalconvert-uploads'),
  limits: { fileSize: 50 * 1024 * 1024, files: 2 },
})

function isDocx(file?: Express.Multer.File): boolean {
  return Boolean(file && (file.originalname.toLowerCase().endsWith('.docx') || file.mimetype.includes('wordprocessingml')))
}

function getFields(files: { [fieldname: string]: Express.Multer.File[] } | undefined) {
  return {
    source: files?.source?.[0],
    template: files?.template?.[0],
  }
}

app.get('/api/health', (_req, res) => {
  res.json({ ok: true, service: 'soalconvert' })
})

app.post('/api/convert', upload.fields([{ name: 'source', maxCount: 1 }, { name: 'template', maxCount: 1 }]), async (req, res) => {
  const { source, template } = getFields(req.files as { [fieldname: string]: Express.Multer.File[] } | undefined)
  if (!source || !template || !isDocx(source) || !isDocx(template)) {
    res.status(400).json({ error: 'Unggah dua file DOCX: dokumen soal sumber dan template tujuan.' })
    return
  }

  const jobDir = await fs.mkdtemp(path.join(os.tmpdir(), 'soalconvert-job-'))
  const outputPath = path.join(jobDir, 'soal-exam-browser.docx')
  const reportPath = path.join(jobDir, 'laporan-validasi.json')
  let registered = false
  try {
    const processorPath = path.join(rootDir, 'processor', 'convert_docx.py')
    await execFileAsync('python3', [processorPath, source.path, template.path, outputPath, reportPath], {
      cwd: rootDir,
      maxBuffer: 2 * 1024 * 1024,
    })
    const report = JSON.parse(await fs.readFile(reportPath, 'utf8'))
    const id = path.basename(jobDir)
    jobs.set(id, { dir: jobDir, output: outputPath, report: reportPath, createdAt: Date.now() })
    registered = true
    res.json({
      ok: true,
      jobId: id,
      report,
      downloads: {
        docx: `/api/download/${id}/docx`,
        report: `/api/download/${id}/report`,
      },
    })
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'Pemrosesan dokumen gagal.'
    res.status(422).json({ error: detail.replace(/^Command failed:.*?\n/i, '').trim() || 'Dokumen tidak dapat diproses.' })
  } finally {
    await Promise.allSettled([fs.rm(source.path, { force: true }), fs.rm(template.path, { force: true })])
    if (!registered) await fs.rm(jobDir, { recursive: true, force: true })
  }
})

app.get('/api/download/:id/:kind', async (req, res) => {
  const job = jobs.get(req.params.id)
  if (!job) {
    res.status(404).json({ error: 'Hasil sudah kedaluwarsa atau tidak ditemukan.' })
    return
  }
  const isReport = req.params.kind === 'report'
  const filePath = isReport ? job.report : job.output
  const filename = isReport ? 'laporan-validasi.json' : 'soal-exam-browser.docx'
  if (!existsSync(filePath)) {
    res.status(404).json({ error: 'File hasil tidak tersedia.' })
    return
  }
  res.download(filePath, filename)
})

const distDir = path.join(rootDir, 'dist')
app.use(express.static(distDir))
app.get(/^(?!\/api(?:\/|$)).*/, (_req, res) => {
  const indexPath = path.join(distDir, 'index.html')
  if (existsSync(indexPath)) res.sendFile(indexPath)
  else res.status(503).send('Aplikasi sedang disiapkan. Jalankan pnpm build terlebih dahulu.')
})

const cleanup = async () => {
  const expiry = Date.now() - 60 * 60 * 1000
  for (const [id, job] of jobs) {
    if (job.createdAt < expiry) {
      jobs.delete(id)
      await fs.rm(job.dir, { recursive: true, force: true })
    }
  }
}
setInterval(cleanup, 15 * 60 * 1000).unref()

app.listen(port, '0.0.0.0', () => {
  console.log(`SoalConvert listening on 0.0.0.0:${port}`)
})
