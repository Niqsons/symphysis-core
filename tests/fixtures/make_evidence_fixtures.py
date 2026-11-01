# -*- coding: utf-8 -*-
"""Порождает бинарные файлы улик для tests/test_journal_check.py (F-42): запуск
`python -X utf8 tests/fixtures/make_evidence_fixtures.py` перезаписывает четыре файла рядом."""
import struct
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = 8192   # порог journal_apply.BINARY_PROBE


def png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))
    raw = b"\x00\xff\x00\x00"   # фильтр 0 + один красный пиксель RGB
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def padded(nul_at: int) -> bytes:
    """ASCII-текст длиной PROBE + 16 с единственным NUL на позиции nul_at (с нуля)."""
    data = bytearray(b"x" * (PROBE + 16))
    data[nul_at] = 0
    data[-1:] = b"\n"
    return bytes(data)


(HERE / "evidence-nul-at-8191.bin").write_bytes(padded(PROBE - 1))
(HERE / "evidence-nul-at-8192.txt").write_bytes(padded(PROBE))
(HERE / "evidence-utf16le-bom.txt").write_bytes(b"\xff\xfe" + "needle in utf16\n".encode("utf-16-le"))
(HERE / "evidence-pixel.png").write_bytes(png())
