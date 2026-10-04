import io
from pathlib import Path

import pytest
from fastapi import UploadFile
from PIL import Image

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.storage import delete_private_file, detect_type, save_private_file


def image_bytes(fmt: str, with_gps: bool = False) -> bytes:
    image = Image.new("RGB", (40, 20), "teal")
    out = io.BytesIO()
    if with_gps:
        exif = Image.Exif()
        exif[0x8825] = {1: "N", 2: (7.0, 22.0, 30.0)}
        exif[0x010F] = "Camara"
        image.save(out, format=fmt, exif=exif)
    else:
        image.save(out, format=fmt)
    return out.getvalue()


def upload(data: bytes, name: str = "archivo") -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=name)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (image_bytes("JPEG"), ("image/jpeg", "jpg")),
        (image_bytes("PNG"), ("image/png", "png")),
        (image_bytes("WEBP"), ("image/webp", "webp")),
        (b"%PDF-1.7\n", ("application/pdf", "pdf")),
        (b"GIF89a....", None),
        (b"<html></html>", None),
    ],
)
def test_detects_type_by_content(data: bytes, expected: tuple[str, str] | None) -> None:
    assert detect_type(data[:16]) == expected


async def test_images_lose_exif_and_get_random_names() -> None:
    stored = await save_private_file(
        upload(image_bytes("JPEG", with_gps=True), "mi_foto.jpg"), "identity", 5
    )
    path = Path(get_settings().storage_dir) / stored.path
    assert "mi_foto" not in stored.path
    assert stored.path.startswith("identity/") and stored.path.endswith(".jpg")
    with Image.open(path) as image:
        assert dict(image.getexif()) == {}
        assert image.size == (40, 20)
    assert oct(path.stat().st_mode)[-3:] in {"600", "666"}  # 666 en sistemas sin permisos POSIX


async def test_rejects_disguised_and_empty_files() -> None:
    with pytest.raises(AppError) as disguised:
        await save_private_file(upload(b"#!/bin/sh\nrm -rf /", "carnet.jpg"), "identity", 5)
    assert disguised.value.code == "FILE_TYPE_NOT_ALLOWED"
    with pytest.raises(AppError) as empty:
        await save_private_file(upload(b""), "identity", 5)
    assert empty.value.code == "FILE_EMPTY"


async def test_rejects_corrupt_images() -> None:
    with pytest.raises(AppError) as corrupt:
        await save_private_file(upload(b"\xff\xd8\xff\xe0 no es una imagen"), "identity", 5)
    assert corrupt.value.code == "FILE_INVALID"


async def test_delete_never_leaves_the_storage_root(tmp_path: Path) -> None:
    outside = tmp_path / "fuera.txt"
    outside.write_text("no borrar")
    delete_private_file("../fuera.txt")
    assert outside.exists()
