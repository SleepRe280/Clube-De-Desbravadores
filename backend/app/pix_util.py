"""Geração de payload PIX (BR Code estático) e QR Code."""

from __future__ import annotations

import base64
import io
import re
import unicodedata


def _crc16_ccitt(data: str) -> str:
    crc = 0xFFFF
    for ch in data:
        crc ^= ord(ch) << 8
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def _emv_field(tag: str, value: str) -> str:
    val = value or ""
    return f"{tag}{len(val):02d}{val}"


def _sanitize_ascii(s: str, max_len: int) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9 .\-]", "", s).strip()
    return s[:max_len]


def build_pix_static_payload(
    pix_key: str,
    *,
    merchant_name: str = "Clube Desbravadores",
    merchant_city: str = "BRASIL",
    amount_brl: float | None = None,
    txid: str = "***",
) -> str:
    """Payload copia-e-cola PIX estático (sem valor fixo se amount_brl for None)."""
    key = (pix_key or "").strip()
    if not key:
        return ""
    name = _sanitize_ascii(merchant_name, 25) or "Clube"
    city = _sanitize_ascii(merchant_city, 15) or "BRASIL"
    gui = _emv_field("00", "BR.GOV.BCB.PIX")
    key_field = _emv_field("01", key)
    mai = _emv_field("26", gui + key_field)
    parts = [
        _emv_field("00", "01"),
        mai,
        _emv_field("52", "0000"),
        _emv_field("53", "986"),
    ]
    if amount_brl is not None and amount_brl > 0:
        parts.append(_emv_field("54", f"{amount_brl:.2f}"))
    parts.extend(
        [
            _emv_field("58", "BR"),
            _emv_field("59", name),
            _emv_field("60", city),
            _emv_field("62", _emv_field("05", (txid or "***")[:25])),
        ]
    )
    body = "".join(parts) + "6304"
    return body + _crc16_ccitt(body)


def pix_qr_data_uri(payload: str, size: int = 220) -> str | None:
    if not payload:
        return None
    try:
        import qrcode

        qr = qrcode.QRCode(version=None, box_size=8, border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0d1b3e", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None
