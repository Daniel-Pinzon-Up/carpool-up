"""Archivos privados (carnets, constancias, licencias).

Se guardan fuera de la raiz publica con nombre aleatorio y solo se sirven por endpoints
autenticados. El tipo se detecta por los primeros bytes, no por la extension ni por el
Content-Type que envia el navegador. Las imagenes se vuelven a codificar para quitar EXIF.
"""

import io
import secrets
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.core.errors import AppError

CHUNK = 64 * 1024
MAX_IMAGE_PIXELS = 40_000_000

# Firma inicial de cada formato permitido -> (tipo MIME, extension)
SIGNATURES: list[tuple[bytes, str, str]] = [
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"%PDF-", "application/pdf", "pdf"),
]

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


@dataclass(frozen=True)
class StoredFile:
    path: str  # relativo a STORAGE_DIR
    content_type: str
    size: int


def detect_type(head: bytes) -> tuple[str, str] | None:
    for signature, mime, ext in SIGNATURES:
        if head.startswith(signature):
            return mime, ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


async def read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Lee el archivo por partes y corta apenas supera el limite."""
    data = bytearray()
    while chunk := await upload.read(CHUNK):
        data.extend(chunk)
        if len(data) > max_bytes:
            raise AppError(
                "FILE_TOO_LARGE",
                "File exceeds the size limit",
                413,
                {"max_mb": max_bytes // (1024 * 1024)},
            )
    if not data:
        raise AppError("FILE_EMPTY", "File is empty", 422)
    return bytes(data)


def strip_image_metadata(data: bytes, ext: str) -> bytes:
    """Vuelve a codificar la imagen sin EXIF (ubicacion GPS, modelo de camara...).

    Aplica la orientacion del EXIF antes de descartarlo para que la foto no quede girada.
    """
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            cleaned = ImageOps.exif_transpose(image)
            output = io.BytesIO()
            if ext == "jpg":
                cleaned.convert("RGB").save(output, format="JPEG", quality=90, optimize=True)
            elif ext == "png":
                cleaned.save(output, format="PNG", optimize=True)
            else:
                cleaned.save(output, format="WEBP", quality=90)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise AppError("FILE_INVALID", "The image could not be read", 422) from exc


def storage_root() -> Path:
    return Path(get_settings().storage_dir)


async def save_private_file(upload: UploadFile, folder: str, max_mb: int) -> StoredFile:
    data = await read_limited(upload, max_mb * 1024 * 1024)
    detected = detect_type(data[:16])
    if detected is None:
        raise AppError(
            "FILE_TYPE_NOT_ALLOWED",
            "Only JPG, PNG, WebP or PDF files are allowed",
            415,
            {"allowed": ["jpg", "png", "webp", "pdf"]},
        )
    mime, ext = detected
    if mime.startswith("image/"):
        data = strip_image_metadata(data, ext)
    relative = Path(folder) / f"{secrets.token_hex(16)}.{ext}"
    target = storage_root() / relative
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.write_bytes(data)
    target.chmod(0o600)
    return StoredFile(path=relative.as_posix(), content_type=mime, size=len(data))


def delete_private_file(relative_path: str) -> None:
    target = (storage_root() / relative_path).resolve()
    root = storage_root().resolve()
    if root in target.parents and target.is_file():
        target.unlink()
