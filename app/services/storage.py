import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from app.config import get_settings

settings = get_settings()


class StorageService(ABC):
    """Abstract interface for file storage operations.

    Enables seamless swapping between local disk storage and cloud storage (e.g. AWS S3).
    """

    @abstractmethod
    def save_file(self, content: bytes, filename: str, subfolder: str = "") -> str:
        """Save file content and return the stored file path identifier."""
        pass

    @abstractmethod
    def get_absolute_path(self, relative_path: str) -> str:
        """Resolve a stored relative file path to its absolute filesystem path."""
        pass

    @abstractmethod
    def read_file(self, relative_path: str) -> bytes:
        """Read and return the raw byte contents of a stored file."""
        pass

    @abstractmethod
    def file_exists(self, relative_path: str) -> bool:
        """Check if a file exists at the given path."""
        pass


class LocalStorageService(StorageService):
    """Local filesystem implementation of StorageService."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or settings.storage_dir).resolve()
        # Ensure base directories exist
        (self.base_dir / "photos").mkdir(parents=True, exist_ok=True)
        (self.base_dir / "reports").mkdir(parents=True, exist_ok=True)

    def save_file(self, content: bytes, filename: str, subfolder: str = "") -> str:
        """Save byte content to the designated subfolder and return the relative path."""
        target_dir = self.base_dir / subfolder if subfolder else self.base_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / filename
        with open(target_file, "wb") as f:
            f.write(content)

        # Return a normalized POSIX-style relative path from current working directory or base_dir
        try:
            rel_path = target_file.relative_to(Path.cwd())
            return str(rel_path).replace("\\", "/")
        except ValueError:
            return str(target_file).replace("\\", "/")

    def get_absolute_path(self, relative_path: str) -> str:
        """Convert stored path to absolute system path."""
        p = Path(relative_path)
        if p.is_absolute():
            return str(p)
        # Check relative to cwd or base_dir
        if (Path.cwd() / p).exists():
            return str(Path.cwd() / p)
        return str(self.base_dir / p)

    def read_file(self, relative_path: str) -> bytes:
        """Read raw bytes from local disk."""
        abs_path = self.get_absolute_path(relative_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"File not found: {abs_path}")
        with open(abs_path, "rb") as f:
            return f.read()

    def file_exists(self, relative_path: str) -> bool:
        """Check if local file exists."""
        abs_path = self.get_absolute_path(relative_path)
        return os.path.exists(abs_path)


# Default singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Dependency injector / factory for StorageService."""
    global _storage_service
    if _storage_service is None:
        _storage_service = LocalStorageService()
    return _storage_service
