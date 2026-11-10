#!/usr/bin/env python3
"""Convert a marked-up source DOCX into the Exam Browser import template.

The processor intentionally works at the DOCX package/XML level instead of flattening
content to plain text. This lets it carry paragraph formatting, embedded pictures and
source tables into each generated question cell.
"""
from __future__ import annotations

import copy
import json
import posixpath
import re
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
Q = "{" + W + "}"
RQ = "{" + R + "}"

NS = {"w": W, "r": R}
RED_VALUES = {"EE0000", "FF0000", "C00000", "RED"}
OPTION_LEFT = 1275
LABEL_RE = re.compile(r"^\s*[A-Da-d]\s*[\.)\-:]\s*")
CONTEXT_RE = re.compile(
    r"^(?:perhatikan|bacalah|simak|cermati)\b|"
    r"^puisi rakyat\b|^perhatikan teks\b|^perhatikan infografik\b",
    re.IGNORECASE,
)
RANGE_RE = re.compile(r"nomor\s+(\d+)\s*[–-]\s*(\d+)", re.IGNORECASE)

for prefix, uri in {
    "w": W,
    "r": R,
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "v": "urn:schemas-microsoft-com:vml",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "wp14": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
}.items():
    ET.register_namespace(prefix, uri)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def text_of(element: ET.Element) -> str:
    parts: list[str] = []
    for child in element.iter():
        name = local_name(child.tag)
        if name == "t":
            parts.append(child.text or "")
        elif name == "tab":
            parts.append("\t")
        elif name in {"br", "cr"}:
            parts.append("\n")
    return "".join(parts).strip()


def has_visual(element: ET.Element) -> bool:
    return any(local_name(child.tag) in {"drawing", "pict", "object", "imagedata"} for child in element.iter())


def is_red(element: ET.Element) -> bool:
    for color in element.iter(Q + "color"):
        value = color.attrib.get(Q + "val", "").upper()
        if value in RED_VALUES:
            return True
    return False


def paragraph_left(element: ET.Element) -> int | None:
    ppr = element.find("./" + Q + "pPr")
    if ppr is None:
        return None
    ind = ppr.find("./" + Q + "ind")
    if ind is None:
        return None
    raw = ind.attrib.get(Q + "left")
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def is_option(element: ET.Element, text: str) -> bool:
    return local_name(element.tag) == "p" and bool(text) and (paragraph_left(element) or 0) >= 1200


def clone_without_numbering(element: ET.Element) -> ET.Element:
    result = copy.deepcopy(element)
    for ppr in result.iter(Q + "pPr"):
        for child in list(ppr):
            if child.tag == Q + "numPr":
                ppr.remove(child)
    return result


def strip_option_label(element: ET.Element) -> None:
    """Remove an explicit A./B)/C-/D: prefix if the source contains one."""
    for text_node in element.iter(Q + "t"):
        original = text_node.text or ""
        if original.strip():
            text_node.text = LABEL_RE.sub("", original, count=1)
            break


def clear_cell(cell: ET.Element) -> None:
    for child in list(cell):
        if child.tag != Q + "tcPr":
            cell.remove(child)
    cell.append(ET.Element(Q + "p"))


def set_simple_cell(cell: ET.Element, value: str) -> None:
    clear_cell(cell)
    paragraph = cell.find("./" + Q + "p")
    if paragraph is None:
        paragraph = ET.SubElement(cell, Q + "p")
    if value:
        run = ET.SubElement(paragraph, Q + "r")
        text = ET.SubElement(run, Q + "t")
        if value[:1].isspace() or value[-1:].isspace():
            text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        text.text = value


def remove_empty_leading_paragraph(cell: ET.Element) -> None:
    paragraphs = cell.findall("./" + Q + "p")
    if len(paragraphs) > 1 and not text_of(paragraphs[0]) and not has_visual(paragraphs[0]):
        cell.remove(paragraphs[0])


def set_block_cell(cell: ET.Element, blocks: list[ET.Element], relationship_map: dict[str, str]) -> None:
    clear_cell(cell)
    # clear_cell creates a placeholder; source blocks replace it.
    for child in list(cell):
        if child.tag != Q + "tcPr":
            cell.remove(child)
    for source in blocks:
        cloned = clone_without_numbering(source)
        for element in cloned.iter():
            for attr_name, attr_value in list(element.attrib.items()):
                if attr_value in relationship_map and (
                    attr_name in {RQ + "embed", RQ + "id", RQ + "link"} or attr_name.endswith("}embed") or attr_name.endswith("}id")
                ):
                    element.set(attr_name, relationship_map[attr_value])
        if local_name(cloned.tag) == "p" and not text_of(cloned) and not has_visual(cloned):
            continue
        cell.append(cloned)
    if not list(cell):
        cell.append(ET.Element(Q + "p"))


def read_relationships(xml: bytes) -> dict[str, ET.Element]:
    root = ET.fromstring(xml)
    return {rel.attrib["Id"]: rel for rel in root}


def relationship_target(rel: ET.Element) -> str:
    target = rel.attrib.get("Target", "")
    return posixpath.normpath(posixpath.join("word", target))


def next_relationship_id(root: ET.Element) -> str:
    used = {rel.attrib.get("Id", "") for rel in root}
    i = 1
    while f"rId{i}" in used:
        i += 1
    return f"rId{i}"


def collect_relationship_ids(elements: list[ET.Element]) -> set[str]:
    found: set[str] = set()
    for element in elements:
        for node in element.iter():
            for attr_name, attr_value in node.attrib.items():
                if attr_name in {RQ + "embed", RQ + "id", RQ + "link"} or attr_name.endswith("}embed") or attr_name.endswith("}id"):
                    found.add(attr_value)
    return found


def merge_source_relationships(
    template_rels_xml: bytes,
    source_rels: dict[str, ET.Element],
    source_zip: zipfile.ZipFile,
    used_ids: set[str],
    template_names: set[str],
) -> tuple[bytes, dict[str, str], dict[str, bytes]]:
    root = ET.fromstring(template_rels_xml)
    mapping: dict[str, str] = {}
    additions: dict[str, bytes] = {}
    used_names = set(template_names)

    for source_id in sorted(used_ids):
        rel = source_rels.get(source_id)
        if rel is None:
            continue
        source_type = rel.attrib.get("Type", "")
        target = relationship_target(rel)
        if target not in source_zip.namelist():
            continue
        new_id = next_relationship_id(root)
        attrs = dict(rel.attrib)
        attrs["Id"] = new_id
        if source_type.endswith("/image"):
            base = posixpath.basename(target)
            stem, suffix = posixpath.splitext(base)
            candidate = f"word/media/soalconvert_{stem}{suffix}"
            counter = 2
            while candidate in used_names:
                candidate = f"word/media/soalconvert_{stem}_{counter}{suffix}"
                counter += 1
            used_names.add(candidate)
            attrs["Target"] = posixpath.relpath(candidate, "word")
            additions[candidate] = source_zip.read(target)
        # Hyperlinks and other document-level relationships can be reused with their target.
        ET.SubElement(root, "{" + PKG_REL + "}Relationship", attrs)
        mapping[source_id] = new_id
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), mapping, additions


def is_context_start(text: str) -> bool:
    return bool(CONTEXT_RE.search(text.strip()))


def context_range(text: str) -> tuple[int, int] | None:
    match = RANGE_RE.search(text)
    return (int(match.group(1)), int(match.group(2))) if match else None


def should_append_context(anchor_text: str, marker_text: str, active_range: tuple[int, int] | None, question_number: int) -> bool:
    if active_range is not None and active_range[0] <= question_number <= active_range[1]:
        return True
    # A few source sets omit the range on a shared text's follow-up prompts. Keep
    # ordinary sentence/paragraph prompts attached to a preceding text heading,
    # but treat a new topic (e.g. "perubahan kata dasar") as a new stimulus.
    anchor = anchor_text.lower()
    marker = marker_text.lower()
    return (
        ("perhatikan teks" in anchor or "perhatikan kutipan" in anchor or "perhatikan puisi" in anchor)
        and ("perhatikan kalimat" in marker or "perhatikan paragraf" in marker)
    )


def looks_like_question(text: str) -> bool:
    cleaned = text.strip()
    return bool(cleaned) and ("?" in cleaned or "…" in cleaned or cleaned.endswith("..."))


def make_report(groups: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    return {
        "questionCount": len(groups),
        "correctAnswerCount": sum(1 for group in groups if sum(1 for option in group["options"] if option["red"]) == 1),
        "stimulusQuestionCount": sum(1 for group in groups if group["context"]),
        "stimulusTypes": sorted({"media" if any(has_visual(block) for block in group["context"]) else "text" for group in groups if group["context"]}),
        "questions": [
            {
                "number": i + 1,
                "correctOption": next((j + 1 for j, option in enumerate(group["options"]) if option["red"]), None),
                "stimulus": bool(group["context"]),
                "stimulusBlocks": len(group["context"]),
            }
            for i, group in enumerate(groups)
        ],
        "warnings": warnings,
    }


def convert(source_path: Path, template_path: Path, output_path: Path, report_path: Path) -> dict[str, Any]:
    warnings: list[str] = []
    with zipfile.ZipFile(source_path, "r") as source_zip, zipfile.ZipFile(template_path, "r") as template_zip:
        source_root = ET.fromstring(source_zip.read("word/document.xml"))
        template_root = ET.fromstring(template_zip.read("word/document.xml"))
        source_body = source_root.find("./" + Q + "body")
        template_body = template_root.find("./" + Q + "body")
        if source_body is None or template_body is None:
            raise ValueError("Dokumen DOCX tidak memiliki body yang valid.")

        source_blocks: list[ET.Element] = []
        block_text: list[str] = []
        for child in list(source_body):
            if child.tag == Q + "sectPr":
                continue
            text = text_of(child)
            if text or has_visual(child):
                source_blocks.append(child)
                block_text.append(text)

        # Locate four-answer windows around every red paragraph. Some source documents use the
        # same indent for list items and question stems, so scanning only contiguous indented
        # runs would incorrectly swallow stimulus tables/lists. The red marker gives us a stable
        # anchor; the score prefers a window whose preceding block is the question stem.
        groups: list[dict[str, Any]] = []
        red_indices = [index for index, element in enumerate(source_blocks) if is_red(element) and block_text[index]]
        selected_starts: set[int] = set()
        for red_index in red_indices:
            windows: list[tuple[int, int]] = []
            for start in range(max(0, red_index - 3), red_index + 1):
                window = source_blocks[start : start + 4]
                if len(window) != 4 or any(not is_option(element, block_text[start + offset]) for offset, element in enumerate(window)):
                    continue
                if sum(1 for option in window if is_red(option)) != 1:
                    continue
                question_index = start - 1
                if question_index < 0 or not block_text[question_index]:
                    continue
                score = 0
                if looks_like_question(block_text[question_index]):
                    score += 6
                if looks_like_question(block_text[start]):
                    score -= 8
                if not is_option(source_blocks[question_index], block_text[question_index]):
                    score += 2
                windows.append((score, start))
            if not windows:
                warnings.append(f"Opsi merah pada posisi sumber {red_index + 1} tidak memiliki empat opsi yang dapat dipisahkan.")
                continue
            _, start = max(windows, key=lambda item: (item[0], -item[1]))
            if start in selected_starts:
                continue
            selected_starts.add(start)
            run = source_blocks[start : start + 4]
            question_index = start - 1
            groups.append({
                "question": source_blocks[question_index],
                "questionIndex": question_index,
                "optionStart": start,
                "optionEnd": start + 4,
                "options": [{"element": option, "red": is_red(option)} for option in run],
                "context": [],
            })

        groups.sort(key=lambda group: group["optionStart"])

        if not groups:
            raise ValueError("Tidak ditemukan kelompok soal dengan empat opsi berindentasi.")

        # Carry the nearest stimulus forward. A new marker starts a new context; the context is
        # copied to each later question until another marker appears.
        marker_indices = [index for index, text in enumerate(block_text) if is_context_start(text)]
        current_context_indices: list[int] = []
        current_anchor_text = ""
        current_range: tuple[int, int] | None = None
        previous_option_end = 0
        for question_number, group in enumerate(groups, start=1):
            candidates: list[int] = [m for m in marker_indices if previous_option_end <= m < group["questionIndex"]]
            if candidates:
                for marker in candidates:
                    marker_text = block_text[marker]
                    marker_range = context_range(marker_text)
                    if marker_range is not None or not current_context_indices:
                        current_context_indices = list(range(marker, group["questionIndex"]))
                        current_anchor_text = marker_text
                        current_range = marker_range
                    elif should_append_context(current_anchor_text, marker_text, current_range, question_number):
                        for context_index in range(marker, group["questionIndex"]):
                            if context_index not in current_context_indices:
                                current_context_indices.append(context_index)
                    else:
                        current_context_indices = list(range(marker, group["questionIndex"]))
                        current_anchor_text = marker_text
                        current_range = marker_range
            group["context"] = [source_blocks[index] for index in current_context_indices]
            previous_option_end = group["optionEnd"]

        # We only need source relationships referenced by copied question, option, or stimulus XML.
        copied_elements: list[ET.Element] = []
        for group in groups:
            copied_elements.extend(group["context"])
            copied_elements.append(group["question"])
            copied_elements.extend(option["element"] for option in group["options"])
        source_rels = read_relationships(source_zip.read("word/_rels/document.xml.rels")) if "word/_rels/document.xml.rels" in source_zip.namelist() else {}
        used_ids = collect_relationship_ids(copied_elements)
        template_rels_xml = template_zip.read("word/_rels/document.xml.rels") if "word/_rels/document.xml.rels" in template_zip.namelist() else b'<?xml version="1.0"?><Relationships xmlns="%s" />' % PKG_REL
        template_names = set(template_zip.namelist())
        merged_rels, relationship_map, added_media = merge_source_relationships(template_rels_xml, source_rels, source_zip, used_ids, template_names)

        tables = template_body.findall("./" + Q + "tbl")
        if not tables:
            raise ValueError("Template tidak memiliki tabel input.")
        target_table = tables[0]
        rows = target_table.findall("./" + Q + "tr")
        required_rows = 1 + (len(groups) * 5)
        if len(rows) < required_rows:
            raise ValueError(f"Template hanya menyediakan {len(rows) - 1} slot soal, tetapi ditemukan {len(groups)} soal.")

        # Clear every example/data row, including unused slots.
        for row in rows[1:]:
            for cell in row.findall("./" + Q + "tc"):
                clear_cell(cell)

        # Fill the first 5 rows per question. We retain the template's convention: the number
        # is in the second answer row, while the question row and other answer rows stay blank.
        for q_index, group in enumerate(groups, start=1):
            row_base = 1 + (q_index - 1) * 5
            row_nodes = rows[row_base : row_base + 5]
            cells = [row.findall("./" + Q + "tc") for row in row_nodes]
            if any(len(row_cells) < 4 for row_cells in cells):
                warnings.append(f"Struktur baris template untuk soal {q_index} tidak memiliki empat kolom.")
                continue
            set_simple_cell(cells[0][0], "\u00a0")
            set_simple_cell(cells[0][1], "SOAL")
            set_block_cell(cells[0][2], group["context"] + [group["question"]], relationship_map)
            set_simple_cell(cells[0][3], "\u00a0")
            for option_index, option in enumerate(group["options"]):
                row_cells = cells[option_index + 1]
                set_simple_cell(row_cells[0], str(q_index) if option_index == 1 else "\u00a0")
                set_simple_cell(row_cells[1], "JAWABAN")
                option_element = clone_without_numbering(option["element"])
                strip_option_label(option_element)
                set_block_cell(row_cells[2], [option_element], relationship_map)
                set_simple_cell(row_cells[3], "1" if option["red"] else "0")

        # Keep the template's surrounding document but replace the package parts that changed.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as out_zip:
            for name in template_zip.namelist():
                if name in {"word/document.xml", "word/_rels/document.xml.rels"}:
                    continue
                out_zip.writestr(name, template_zip.read(name))
            out_zip.writestr("word/document.xml", ET.tostring(template_root, encoding="utf-8", xml_declaration=True))
            out_zip.writestr("word/_rels/document.xml.rels", merged_rels)
            for name, content in added_media.items():
                out_zip.writestr(name, content)

    report = make_report(groups, warnings)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    if len(sys.argv) != 5:
        print("usage: convert_docx.py SOURCE.docx TEMPLATE.docx OUTPUT.docx REPORT.json", file=sys.stderr)
        return 2
    try:
        report = convert(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
