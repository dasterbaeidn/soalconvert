# TODO SoalConvert

- [x] **Alur upload dua dokumen Word**
  - Pengguna dapat mengunggah satu dokumen soal sumber dan satu template Word tujuan.
  - Sistem memvalidasi bahwa kedua file berformat DOCX dan menampilkan nama file yang dipilih.

- [x] **Konversi struktur pilihan ganda**
  - Sistem mendeteksi soal pilihan ganda dengan tepat empat opsi.
  - Sistem menghapus label A/B/C/D sehingga kolom jawaban hanya berisi teks opsi.
  - Sistem mengosongkan contoh input pada template sebelum memasukkan hasil.

- [x] **Jawaban benar dan stimulus**
  - Opsi berwarna merah, termasuk kode EE0000, diberi nilai 1; opsi lain diberi nilai 0.
  - Cerita, gambar, tabel, infografik, puisi, dan stimulus sejenis yang merujuk pada rentang nomor disertakan pada setiap soal terkait agar tetap membuntuti soal ketika diacak.
  - Dokumen hasil mengikuti satu baris SOAL dan empat baris JAWABAN untuk setiap soal.

- [x] **Validasi dan unduhan**
  - Antarmuka menampilkan status pemrosesan, jumlah soal, jumlah jawaban benar terbaca, stimulus yang terdeteksi, dan peringatan.
  - Sistem menyediakan file DOCX hasil serta laporan validasi untuk bagian ambigu/tidak lengkap.
  - File diproses sementara tanpa penyimpanan permanen.

- [ ] **Preview dan kesiapan deployment**
  - Route `/` memiliki UI yang usable pada desktop dan layar sempit.
  - `GET /manus-routes.json` mengembalikan manifest route yang valid.
  - Build, typecheck, dan uji pemroses berhasil sebelum checkpoint.
