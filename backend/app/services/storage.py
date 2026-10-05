"""
Storage abstraction.

Only `LocalStorage` exists today. Everything callers need is this interface
(save_original, save_thumbnail, read, delete, path_for) so swapping in an
S3StorageBackend later (Phase 10+) means adding one class, not touching
every route that reads/writes files.

Security notes:
- We NEVER use the user-supplied filename as a path component. Every stored
  file gets a fresh UUID-based name. The original filename is kept only as
  a display string in the database.
- Every path is built by joining a fixed root with a UUID + a whitelisted
  extension, so there is no path-traversal surface even if some caller
  forgets to sanitize input.
"""
import uuid
from pathlib import Path

from app.core.config import settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff"}


class LocalStorage:
    def __init__(self) -> None:
        self.originals_root = Path(settings.LOCAL_STORAGE_ROOT)
        self.thumbnails_root = Path(settings.THUMBNAIL_STORAGE_ROOT)
        self.originals_root.mkdir(parents=True, exist_ok=True)
        self.thumbnails_root.mkdir(parents=True, exist_ok=True)

    def _user_dir(self, root: Path, user_id: uuid.UUID) -> Path:
        d = root / str(user_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_original(self, user_id: uuid.UUID, extension: str, content: bytes) -> str:
        extension = extension.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported extension: {extension}")
        filename = f"{uuid.uuid4().hex}{extension}"
        dest = self._user_dir(self.originals_root, user_id) / filename
        dest.write_bytes(content)
        # Path relative to originals_root — what we store in Photo.file_path
        return str(dest.relative_to(self.originals_root))

    def save_thumbnail(self, user_id: uuid.UUID, photo_id: uuid.UUID, content: bytes) -> str:
        filename = f"{photo_id.hex}.jpg"
        dest = self._user_dir(self.thumbnails_root, user_id) / filename
        dest.write_bytes(content)
        return str(dest.relative_to(self.thumbnails_root))

    def original_path(self, relative_path: str) -> Path:
        return self._safe_join(self.originals_root, relative_path)

    def thumbnail_path(self, relative_path: str) -> Path:
        return self._safe_join(self.thumbnails_root, relative_path)

    def delete_original(self, relative_path: str) -> None:
        p = self.original_path(relative_path)
        p.unlink(missing_ok=True)

    def delete_thumbnail(self, relative_path: str) -> None:
        p = self.thumbnail_path(relative_path)
        p.unlink(missing_ok=True)

    @staticmethod
    def _safe_join(root: Path, relative_path: str) -> Path:
        """Resolves relative_path under root and rejects any escape attempt."""
        candidate = (root / relative_path).resolve()
        root_resolved = root.resolve()
        if root_resolved not in candidate.parents and candidate != root_resolved:
            raise ValueError("Path traversal attempt detected")
        return candidate


storage = LocalStorage()
