# SoalConvert

SoalConvert mengubah dokumen soal DOCX dengan opsi jawaban merah menjadi format DOCX import Exam Browser. Aplikasi menerima dokumen soal sumber dan template `form-soal-ganda`, lalu menghasilkan satu baris `SOAL` dan empat baris `JAWABAN` per nomor.

## Jalankan lokal

```bash
pnpm install
pnpm build
pnpm start
```

Buka `http://localhost:3000`. Untuk pengujian pemroses:

```bash
pnpm test:processor
```

Opsi merah (`EE0000`, `FF0000`, `C00000`, atau `red`) menjadi `1`; opsi lain menjadi `0`. Label A–D eksplisit dihapus, dan stimulus yang ditemukan sebelum kelompok soal disalin ke setiap nomor terkait. File upload dan hasil diproses sementara.
