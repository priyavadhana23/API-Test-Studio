"""
utilities/file_utils.py
=======================
Reusable file-system helpers for API Test Studio.

Provides:
    - Safe file reading / writing
    - JSON / YAML / CSV read helpers
    - Path construction and validation utilities
    - Directory management helpers

All public functions are pure (no global state) and raise descriptive
exceptions so callers can handle errors clearly.
"""

import csv
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from utilities.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------

def resolve_path(*parts: Union[str, Path]) -> Path:
    """
    Join path components and return an absolute, resolved ``Path``.

    Args:
        *parts: Path components, e.g. ``("base_dir", "sub", "file.json")``.

    Returns:
        Resolved absolute ``Path``.
    """
    return Path(*parts).resolve()


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Create a directory (and all parents) if it does not already exist.

    Args:
        path: Directory path to create.

    Returns:
        The resolved ``Path`` of the directory.
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    logger.debug("Directory ensured: %s", dir_path)
    return dir_path


def path_exists(path: Union[str, Path]) -> bool:
    """Return ``True`` if *path* exists on the filesystem."""
    return Path(path).exists()


def is_file(path: Union[str, Path]) -> bool:
    """Return ``True`` if *path* points to a regular file."""
    return Path(path).is_file()


def is_directory(path: Union[str, Path]) -> bool:
    """Return ``True`` if *path* points to a directory."""
    return Path(path).is_dir()


def get_file_extension(path: Union[str, Path]) -> str:
    """
    Return the lowercase file extension including the leading dot.

    Example::

        get_file_extension("spec.yaml")  # → ".yaml"

    Args:
        path: File path.

    Returns:
        Lowercase extension string (e.g. ``".json"``), or ``""`` if none.
    """
    return Path(path).suffix.lower()


def get_filename(path: Union[str, Path], with_extension: bool = True) -> str:
    """
    Return the final component of *path*.

    Args:
        path:           File path.
        with_extension: When ``False``, the extension is stripped.

    Returns:
        Filename string.
    """
    p = Path(path)
    return p.name if with_extension else p.stem


def list_files(
    directory: Union[str, Path],
    extension: Optional[str] = None,
    recursive: bool = False,
) -> List[Path]:
    """
    List files inside *directory*, optionally filtered by extension.

    Args:
        directory:  Directory to scan.
        extension:  If provided (e.g. ``".yaml"``), only matching files
                    are returned.  Case-insensitive.
        recursive:  When ``True``, subdirectories are scanned recursively.

    Returns:
        Sorted list of ``Path`` objects for matching files.

    Raises:
        NotADirectoryError: If *directory* is not an existing directory.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {dir_path}")

    pattern = "**/*" if recursive else "*"
    files = [p for p in dir_path.glob(pattern) if p.is_file()]

    if extension:
        ext = extension.lower() if not extension.startswith(".") else extension.lower()
        ext = ext if ext.startswith(".") else f".{ext}"
        files = [f for f in files if f.suffix.lower() == ext]

    return sorted(files)


# ---------------------------------------------------------------------------
# Generic text / binary file I/O
# ---------------------------------------------------------------------------

def read_text_file(path: Union[str, Path], encoding: str = "utf-8") -> str:
    """
    Read and return the contents of a text file.

    Args:
        path:     Path to the file.
        encoding: File encoding (default ``utf-8``).

    Returns:
        File contents as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
        IOError:           On read failure.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    logger.debug("Reading text file: %s", file_path)
    return file_path.read_text(encoding=encoding)


def write_text_file(
    path: Union[str, Path],
    content: str,
    encoding: str = "utf-8",
    overwrite: bool = True,
) -> Path:
    """
    Write *content* to a text file, creating parent directories as needed.

    Args:
        path:      Destination file path.
        content:   Text to write.
        encoding:  File encoding (default ``utf-8``).
        overwrite: If ``False`` and the file exists, raises ``FileExistsError``.

    Returns:
        Resolved path of the written file.

    Raises:
        FileExistsError: If *overwrite* is ``False`` and the file already exists.
    """
    file_path = Path(path)
    if not overwrite and file_path.exists():
        raise FileExistsError(f"File already exists and overwrite=False: {file_path}")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding=encoding)
    logger.debug("Text file written: %s", file_path)
    return file_path.resolve()


def copy_file(source: Union[str, Path], destination: Union[str, Path]) -> Path:
    """
    Copy a file from *source* to *destination*.

    Args:
        source:      Path to the source file.
        destination: Destination path (file or directory).

    Returns:
        Path of the copied file.

    Raises:
        FileNotFoundError: If *source* does not exist.
    """
    src = Path(source)
    dst = Path(destination)
    if not src.is_file():
        raise FileNotFoundError(f"Source file not found: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    result = shutil.copy2(str(src), str(dst))
    logger.debug("File copied: %s → %s", src, result)
    return Path(result)


def delete_file(path: Union[str, Path], missing_ok: bool = True) -> None:
    """
    Delete a file.

    Args:
        path:       Path to the file.
        missing_ok: When ``True``, silently ignores a missing file.

    Raises:
        FileNotFoundError: If the file is missing and *missing_ok* is ``False``.
    """
    file_path = Path(path)
    if not file_path.exists():
        if missing_ok:
            return
        raise FileNotFoundError(f"File not found: {file_path}")

    file_path.unlink()
    logger.debug("File deleted: %s", file_path)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def read_json(path: Union[str, Path]) -> Any:
    """
    Parse and return the contents of a JSON file.

    Args:
        path: Path to the ``.json`` file.

    Returns:
        Parsed Python object (dict, list, etc.).

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"JSON file not found: {file_path}")

    logger.debug("Reading JSON: %s", file_path)
    with open(file_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(
    path: Union[str, Path],
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False,
    overwrite: bool = True,
) -> Path:
    """
    Serialize *data* to a JSON file.

    Args:
        path:         Destination file path.
        data:         Python object to serialize.
        indent:       JSON indentation level.
        ensure_ascii: Passed directly to ``json.dump``.
        overwrite:    If ``False`` and the file exists, raises ``FileExistsError``.

    Returns:
        Resolved path of the written file.
    """
    file_path = Path(path)
    if not overwrite and file_path.exists():
        raise FileExistsError(f"File already exists and overwrite=False: {file_path}")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=indent, ensure_ascii=ensure_ascii)

    logger.debug("JSON written: %s", file_path)
    return file_path.resolve()


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

def read_yaml(path: Union[str, Path]) -> Any:
    """
    Parse and return the contents of a YAML file.

    Args:
        path: Path to the ``.yaml`` / ``.yml`` file.

    Returns:
        Parsed Python object.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError:    If the file is not valid YAML.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"YAML file not found: {file_path}")

    logger.debug("Reading YAML: %s", file_path)
    with open(file_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def write_yaml(
    path: Union[str, Path],
    data: Any,
    overwrite: bool = True,
) -> Path:
    """
    Serialize *data* to a YAML file.

    Args:
        path:      Destination file path.
        data:      Python object to serialize.
        overwrite: If ``False`` and the file exists, raises ``FileExistsError``.

    Returns:
        Resolved path of the written file.
    """
    file_path = Path(path)
    if not overwrite and file_path.exists():
        raise FileExistsError(f"File already exists and overwrite=False: {file_path}")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True)

    logger.debug("YAML written: %s", file_path)
    return file_path.resolve()


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def read_csv(
    path: Union[str, Path],
    has_header: bool = True,
    delimiter: str = ",",
) -> List[Dict[str, str]]:
    """
    Read a CSV file and return rows as a list of dictionaries.

    When *has_header* is ``True`` the first row is used as the key names.
    When ``False``, keys are zero-based integer strings (``"0"``, ``"1"`` …).

    Args:
        path:       Path to the ``.csv`` file.
        has_header: Whether the first row is a header row.
        delimiter:  Column delimiter character.

    Returns:
        List of row dictionaries.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    logger.debug("Reading CSV: %s", file_path)
    rows: List[Dict[str, str]] = []

    with open(file_path, "r", encoding="utf-8", newline="") as fh:
        if has_header:
            reader = csv.DictReader(fh, delimiter=delimiter)
            for row in reader:
                rows.append(dict(row))
        else:
            reader_plain = csv.reader(fh, delimiter=delimiter)
            for row in reader_plain:
                rows.append({str(i): val for i, val in enumerate(row)})

    return rows


def write_csv(
    path: Union[str, Path],
    rows: List[Dict[str, Any]],
    fieldnames: Optional[List[str]] = None,
    delimiter: str = ",",
    overwrite: bool = True,
) -> Path:
    """
    Write a list of dictionaries to a CSV file.

    Args:
        path:       Destination file path.
        rows:       List of row dictionaries.
        fieldnames: Column names for the header row.  Inferred from the first
                    row when ``None``.
        delimiter:  Column delimiter character.
        overwrite:  If ``False`` and the file exists, raises ``FileExistsError``.

    Returns:
        Resolved path of the written file.

    Raises:
        ValueError: If *rows* is empty and *fieldnames* is not provided.
    """
    if not rows and fieldnames is None:
        raise ValueError("Cannot write CSV: rows is empty and fieldnames is not provided.")

    file_path = Path(path)
    if not overwrite and file_path.exists():
        raise FileExistsError(f"File already exists and overwrite=False: {file_path}")

    file_path.parent.mkdir(parents=True, exist_ok=True)
    headers = fieldnames or list(rows[0].keys())

    with open(file_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)

    logger.debug("CSV written: %s", file_path)
    return file_path.resolve()
