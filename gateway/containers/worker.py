#!/usr/bin/env python3
"""Convert text files in the incoming directory into small PDF files."""

from __future__ import annotations

import os
import time
from pathlib import Path


INPUT_DIR = Path(os.environ.get("INPUT_DIR", "/opt/incoming"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/opt/outgoing"))


def escape_pdf(text: str) -> bytes:
    encoded = text.encode("latin-1", errors="replace")
    return encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def create_pdf(source: Path, destination: Path) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()[:55]
    stream = bytearray(b"BT\n/F1 10 Tf\n50 780 Td\n")
    for index, line in enumerate(lines):
        if index:
            stream.extend(b"0 -13 Td\n")
        stream.extend(b"(" + escape_pdf(line[:110]) + b") Tj\n")
    stream.extend(b"ET\n")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + bytes(stream) + b"endstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(pdf)
    temporary.replace(destination)


def process_files() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for source in INPUT_DIR.iterdir():
        if not source.is_file():
            continue
        destination = OUTPUT_DIR / f"{source.name}.pdf"
        if destination.exists() and destination.stat().st_mtime >= source.stat().st_mtime:
            continue
        try:
            create_pdf(source, destination)
        except OSError as error:
            print(f"Could not convert {source}: {error}", flush=True)


if __name__ == "__main__":
    while True:
        process_files()
        time.sleep(2)
