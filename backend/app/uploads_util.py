import os
import uuid
from pathlib import Path

from werkzeug.utils import secure_filename

ALLOWED_EXT = frozenset({"png", "jpg", "jpeg", "webp"})
ALLOWED_DOC_EXT = frozenset({"pdf", "doc", "docx", "xls", "xlsx", "png", "jpg", "jpeg"})


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def save_upload(file_storage, upload_folder: str, subfolder: str) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    fn = secure_filename(file_storage.filename)
    if not fn or not allowed_file(fn):
        return None
    ext = fn.rsplit(".", 1)[1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    dest_dir = Path(upload_folder) / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / name
    file_storage.save(str(path))
    return f"{subfolder}/{name}"


def allowed_document(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_DOC_EXT


def save_document_upload(file_storage, upload_folder: str, subfolder: str = "docs") -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    fn = secure_filename(file_storage.filename)
    if not fn or not allowed_document(fn):
        return None
    ext = fn.rsplit(".", 1)[1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    dest_dir = Path(upload_folder) / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / name
    file_storage.save(str(path))
    return f"{subfolder}/{name}"


def attachment_display_name(rel_path: str | None) -> str:
    if not rel_path:
        return ""
    base = Path(rel_path).name
    if len(base) > 40:
        return base[:37] + "…"
    return base


def attachment_ext(rel_path: str | None) -> str:
    if not rel_path or "." not in rel_path:
        return "file"
    return rel_path.rsplit(".", 1)[1].lower()


def safe_remove_upload(upload_folder: str, rel_path: str | None) -> None:
    if not rel_path:
        return
    p = Path(upload_folder) / rel_path
    if p.is_file():
        p.unlink()


def _optimize_image_file(path: Path, *, max_dim: int = 1920, quality: int = 85) -> tuple[int | None, int | None]:
    """Redimensiona e comprime JPEG/WebP quando Pillow está disponível."""
    try:
        from PIL import Image
    except ImportError:
        return None, None
    try:
        with Image.open(path) as img:
            img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
            w, h = img.size
            if max(w, h) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            w, h = img.size
            img.save(path, format="JPEG", quality=quality, optimize=True)
            return w, h
    except Exception:
        return None, None


def _make_thumbnail(src: Path, dest: Path, size: int = 480) -> None:
    try:
        from PIL import Image
    except ImportError:
        return
    try:
        with Image.open(src) as img:
            img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, format="JPEG", quality=78, optimize=True)
    except Exception:
        pass


def save_gallery_upload(file_storage, upload_folder: str) -> dict | None:
    """Salva foto da galeria com otimização e miniatura."""
    if not file_storage or not file_storage.filename:
        return None
    fn = secure_filename(file_storage.filename)
    if not fn or not allowed_file(fn):
        return None
    name = f"{uuid.uuid4().hex}.jpg"
    thumb_name = f"{uuid.uuid4().hex}_t.jpg"
    dest_dir = Path(upload_folder) / "gallery"
    thumb_dir = dest_dir / "thumbs"
    dest_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / name
    file_storage.save(str(path))
    w, h = _optimize_image_file(path)
    thumb_path = thumb_dir / thumb_name
    _make_thumbnail(path, thumb_path)
    return {
        "filename": f"gallery/{name}",
        "thumb_filename": f"gallery/thumbs/{thumb_name}",
        "width": w,
        "height": h,
    }
