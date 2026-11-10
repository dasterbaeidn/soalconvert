# Rencana SoalConvert

## Tujuan
SoalConvert adalah web app berbahasa Indonesia untuk guru yang mengonversi dokumen soal DOCX menjadi format DOCX import Exam Browser. Sistem membaca opsi benar dari warna merah, menyalin stimulus ke setiap soal yang menggunakannya, menghapus label A/B/C/D, mengosongkan contoh template, dan memberi laporan validasi.

## Pendekatan implementasi
- Frontend React/TypeScript dengan alur unggah dua DOCX, ringkasan hasil, peringatan, dan unduhan.
- Backend Express/TypeScript yang menerima multipart upload secara sementara dan menjalankan pemroses dokumen Python.
- Pemroses Python memanipulasi paket DOCX/XML agar warna opsi, gambar, tabel, dan struktur template dapat dipertahankan semaksimal mungkin. Stimulus ditentukan dari blok sebelum pertanyaan dan digandakan ke isi setiap soal terkait.
- Output mengikuti template: baris header, lalu satu baris SOAL dan empat baris JAWABAN per soal; nilai 1 hanya pada opsi merah.
- File sementara dihapus setelah respons selesai; tidak ada penyimpanan permanen.

## Desain
### Opsi gaya
- Editorial alat kerja sekolah — probabilitas 0,06.
- Minimal utilitas laboratorium — probabilitas 0,04.
- Kartu proses ramah guru — probabilitas 0,08.

Dipilih: **Editorial alat kerja sekolah**.

- **Design Movement:** editorial modern yang tenang, terinspirasi lembar kerja sekolah dan panel instruksi yang rapi.
- **Core Principles:** jelas sebelum dekoratif; status selalu terlihat; satu alur utama; peringatan mudah ditindaklanjuti.
- **Color Philosophy:** tinta navy untuk kepercayaan, kertas hangat untuk konteks dokumen, dan hijau-teal sebagai penanda progres; merah hanya untuk peringatan/kunci yang perlu diperhatikan.
- **Layout Paradigm:** kolom kerja asimetris dengan panel konteks di samping, bukan dashboard grid generik.
- **Signature Elements:** garis margin seperti kertas, badge status berbentuk label, dan garis aksen teal pada area dropzone.
- **Interaction Philosophy:** setiap langkah memberi umpan balik langsung; drag/drop tetap memiliki tombol pilih file; state error menjelaskan tindakan perbaikan.
- **Animation:** transisi 160–220 ms, progress bar bergerak halus saat pemrosesan, tanpa animasi dekoratif berulang.
- **Typography System:** IBM Plex Sans untuk UI dan IBM Plex Mono untuk angka/status teknis; hirarki tegas dengan judul besar dan caption ringkas.
- **Brand Essence:** konverter Word yang membantu guru menyiapkan ujian tanpa memindahkan soal satu per satu; teliti, praktis, dapat dipercaya.
- **Brand Voice:** instruktif, hangat, langsung. Contoh: “Unggah dua dokumen, kami rapikan sisanya.” dan “Periksa 3 bagian ini sebelum diimpor.”
- **Wordmark & Logo:** tanda kurung siku yang membentuk lembar dan centang, dipasangkan dengan wordmark SoalConvert.
- **Signature Brand Color:** teal tinta `#0F766E`.

## Struktur proyek
- `server/index.ts`: server HTTP, upload, endpoint konversi, dan response file.
- `processor/convert_docx.py`: pembacaan blok DOCX, deteksi merah, stimulus, dan pembuatan output.
- `src/`: frontend React dan styling.
- `public/manus-routes.json`: manifest route Preview.
- `tests/`: uji pemroses dengan dokumen contoh.
