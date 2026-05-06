from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..models import Exercise


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRIVATE_UPLOADS_DIR = PROJECT_ROOT / "private_uploads"
EXERCISE_VIDEOS_DIR = PRIVATE_UPLOADS_DIR / "exercise_videos"
TMP_VIDEOS_DIR = PRIVATE_UPLOADS_DIR / "tmp_videos"

MAX_VIDEO_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB antes de convertir

# Permitimos más formatos de entrada porque FFmpeg los convierte a MP4 móvil.
ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "application/octet-stream",
}

ALLOWED_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mov",
    ".avi",
    ".mkv",
}


def ensure_video_dirs() -> None:
    EXERCISE_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    TMP_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


def has_uploaded_file(upload: UploadFile | None) -> bool:
    return bool(upload and upload.filename and upload.filename.strip())


def _safe_extension(filename: str) -> str:
    ext = Path(filename or "").suffix.lower().strip()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Formato de video no permitido. Usá MP4, MOV, WebM, AVI o MKV.",
        )
    return ext


def _validate_content_type(upload: UploadFile) -> None:
    content_type = (upload.content_type or "").lower().strip()

    if content_type and content_type not in ALLOWED_VIDEO_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Tipo de archivo no permitido. Subí un archivo de video válido.",
        )


def _relative_video_path(filename: str) -> str:
    return f"exercise_videos/{filename}"


def _absolute_video_path(relative_path: str) -> Path:
    clean = (relative_path or "").replace("\\", "/").lstrip("/")
    full_path = (PRIVATE_UPLOADS_DIR / clean).resolve()

    private_root = PRIVATE_UPLOADS_DIR.resolve()
    if private_root not in full_path.parents and full_path != private_root:
        raise HTTPException(status_code=400, detail="Ruta de video inválida.")

    return full_path


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _run_ffmpeg_mobile_conversion(
    *,
    input_path: Path,
    output_path: Path,
) -> None:
    if not _ffmpeg_available():
        raise HTTPException(
            status_code=500,
            detail="FFmpeg no está instalado o no está disponible en PATH.",
        )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        "libx264",
        "-profile:v",
        "baseline",
        "-level",
        "3.0",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=900,  # 15 minutos
        )
    except subprocess.TimeoutExpired:
        output_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail="La conversión del video tardó demasiado y fue cancelada.",
        )

    if result.returncode != 0:
        output_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail="No se pudo convertir el video a MP4 compatible con celular.",
        )

    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise HTTPException(
            status_code=500,
            detail="La conversión del video no generó un archivo válido.",
        )


def delete_private_exercise_video(exercise: Exercise) -> None:
    if not exercise.video_path:
        return

    try:
        path = _absolute_video_path(exercise.video_path)
        if path.exists() and path.is_file():
            path.unlink()
    except Exception:
        # No bloqueamos la operación principal por un error al borrar archivo viejo.
        pass

    exercise.video_path = None
    exercise.video_original_filename = None
    exercise.video_content_type = None
    exercise.video_size_bytes = None


def save_private_exercise_video(
    db: Session,
    *,
    exercise: Exercise,
    upload: UploadFile,
    replace_existing: bool = True,
) -> Exercise:
    if not has_uploaded_file(upload):
        return exercise

    ensure_video_dirs()
    _validate_content_type(upload)

    original_filename = upload.filename or "video"
    _safe_extension(original_filename)

    if replace_existing:
        delete_private_exercise_video(exercise)

    upload_token = uuid.uuid4().hex
    temp_input_name = f"upload_{exercise.id}_{upload_token}{Path(original_filename).suffix.lower()}"
    temp_input_path = TMP_VIDEOS_DIR / temp_input_name

    final_name = f"exercise_{exercise.id}_{upload_token}.mp4"
    final_path = EXERCISE_VIDEOS_DIR / final_name

    total = 0

    try:
        with temp_input_path.open("wb") as out_file:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break

                total += len(chunk)
                if total > MAX_VIDEO_SIZE_BYTES:
                    out_file.close()
                    temp_input_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=400,
                        detail="El video supera el tamaño máximo permitido de 500 MB.",
                    )

                out_file.write(chunk)
    finally:
        try:
            upload.file.close()
        except Exception:
            pass

    try:
        _run_ffmpeg_mobile_conversion(
            input_path=temp_input_path,
            output_path=final_path,
        )
    finally:
        temp_input_path.unlink(missing_ok=True)

    exercise.video_path = _relative_video_path(final_name)
    exercise.video_original_filename = original_filename[:255]
    exercise.video_content_type = "video/mp4"
    exercise.video_size_bytes = final_path.stat().st_size

    db.add(exercise)
    return exercise


def build_private_video_response(exercise: Exercise) -> FileResponse:
    if not exercise.video_path:
        raise HTTPException(status_code=404, detail="El ejercicio no tiene video privado cargado.")

    path = _absolute_video_path(exercise.video_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="No se encontró el archivo de video.")

    filename = exercise.video_original_filename or path.name

    return FileResponse(
        path=str(path),
        media_type="video/mp4",
        filename=filename,
        content_disposition_type="inline",
    )