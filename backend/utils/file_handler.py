"""
backend/utils/file_handler.py
==============================
Utility functions for saving and managing uploaded files on disk.
Used internally by RAG upload flow when a temp file is needed.
"""

from pathlib import Path


def save_file(content: bytes, path: str | Path) -> Path:
    """Write raw bytes to *path* and return the Path object."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def save_upload_file(uploaded_file, path: str | Path) -> Path:
    """
    Save a FastAPI / Starlette UploadFile-like object whose .file
    attribute supports .read().

    Returns the saved Path.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as f:
        f.write(uploaded_file.file.read())
    return target