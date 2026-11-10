import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

SOURCE = Path('/home/ubuntu/upload/Soal_PSAS_BahasaIndonesia_7_2026_2027F4.docx')
TEMPLATE = Path('/home/ubuntu/upload/form-soal-ganda(1).docx')
ROOT = Path(__file__).resolve().parents[1]
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}


def main() -> None:
    assert SOURCE.exists(), SOURCE
    assert TEMPLATE.exists(), TEMPLATE
    with tempfile.TemporaryDirectory(prefix='soalconvert-test-') as tmp:
        output = Path(tmp) / 'output.docx'
        report_path = Path(tmp) / 'report.json'
        completed = subprocess.run(
            ['python3', str(ROOT / 'processor' / 'convert_docx.py'), str(SOURCE), str(TEMPLATE), str(output), str(report_path)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        report = json.loads(report_path.read_text(encoding='utf-8'))
        assert report['questionCount'] == 40, report
        assert report['correctAnswerCount'] == 40, report
        assert not report['warnings'], report['warnings']
        with zipfile.ZipFile(output) as archive:
            document = archive.read('word/document.xml')
            assert document.startswith(b'<?xml')
            assert b'Ini adalah contoh soal' not in document
            assert b'Jawaban Salah statusnya 0' not in document
            assert len([name for name in archive.namelist() if name.startswith('word/media/')]) >= 3
            root = ET.fromstring(document)
            table = root.findall('.//w:body/w:tbl', NS)[0]
            rows = table.findall('./w:tr', NS)
            for question_index in range(40):
                chunk = rows[1 + question_index * 5: 1 + (question_index + 1) * 5]
                values = [
                    ''.join(node.text or '' for node in row.findall('./w:tc', NS)[3].findall('.//w:t', NS)).strip()
                    for row in chunk[1:]
                ]
                assert values.count('1') == 1 and values.count('0') == 3, (question_index + 1, values)
            q3_text = ''.join(node.text or '' for node in rows[11].findall('.//w:t', NS))
            q8_text = ''.join(node.text or '' for node in rows[36].findall('.//w:t', NS))
            assert 'Pesona Pantai Menganti' in q3_text
            assert 'Waduk Sempor' in q8_text
    print('processor test passed: 40 soal, 40 kunci, no warnings')


if __name__ == '__main__':
    main()
