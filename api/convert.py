from __future__ import annotations

import base64
import cgi
import io
import json
import sys
import tempfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "processor"))
from convert_docx import convert  # type: ignore  # noqa: E402

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


class handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, status: int, value: object) -> None:
        payload = json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", "0"))
        if "multipart/form-data" not in content_type or content_length <= 0:
            self.send_json(400, {"error": "Unggah dua file DOCX: dokumen soal sumber dan template tujuan."})
            return
        try:
            body = self.rfile.read(content_length)
            form = cgi.FieldStorage(
                fp=io.BytesIO(body),
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type,
                    "CONTENT_LENGTH": str(content_length),
                },
                keep_blank_values=True,
            )
            source = form["source"] if "source" in form else None
            template = form["template"] if "template" in form else None
            if source is None or template is None or not getattr(source, "file", None) or not getattr(template, "file", None):
                self.send_json(400, {"error": "Dua file DOCX wajib diunggah."})
                return
            source_data = source.file.read()
            template_data = template.file.read()
            with tempfile.TemporaryDirectory(prefix="soalconvert-vercel-") as temp_dir:
                temp = Path(temp_dir)
                source_path = temp / "source.docx"
                template_path = temp / "template.docx"
                output_path = temp / "output.docx"
                report_path = temp / "report.json"
                source_path.write_bytes(source_data)
                template_path.write_bytes(template_data)
                report = convert(source_path, template_path, output_path, report_path)
                output = output_path.read_bytes()

            encoded_report = base64.urlsafe_b64encode(json_bytes(report)).decode("ascii")
            self.send_response(200)
            self.send_header("Content-Type", DOCX_MIME)
            self.send_header("Content-Disposition", 'attachment; filename="soal-exam-browser.docx"')
            self.send_header("Content-Length", str(len(output)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-SoalConvert-Report", encoded_report)
            self.send_header("Access-Control-Expose-Headers", "X-SoalConvert-Report, Content-Disposition")
            self.end_headers()
            self.wfile.write(output)
        except Exception as exc:
            self.send_json(422, {"error": str(exc) or "Dokumen tidak dapat diproses."})

    def do_GET(self) -> None:
        self.send_json(405, {"error": "Gunakan POST untuk mengunggah dua file DOCX."})
