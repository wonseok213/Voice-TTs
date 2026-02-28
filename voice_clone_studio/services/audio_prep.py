import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REFERENCE_TARGET_SECONDS = 10.0
REFERENCE_MAX_SECONDS = 12.0
REFERENCE_MIN_ACTIVE_SECONDS = 3.0
REFERENCE_SILENCE_THRESHOLD_RATIO = 0.06
REFERENCE_FADE_SECONDS = 0.01


SUPPORTED_AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".flac",
    ".m4a",
    ".ogg",
}
SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
}
SUPPORTED_MEDIA_EXTENSIONS = SUPPORTED_AUDIO_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS

PENDING_FFMPEG_STATUS = "pending_ffmpeg"
EXTRACT_FAILED_STATUS = "extract_failed"


def build_unique_destination(destination: Path) -> Path:
    if not destination.exists():
        return destination

    counter = 1
    while True:
        candidate = destination.with_name(
            f"{destination.stem}_{counter}{destination.suffix}"
        )
        if not candidate.exists():
            return candidate
        counter += 1


def validate_audio_source(source_path: Path):
    source_path = source_path.expanduser().resolve()

    if not source_path.exists():
        raise FileNotFoundError(f"음성 파일이 없습니다: {source_path}")
    if not source_path.is_file():
        raise ValueError(f"음성 파일 경로가 파일이 아닙니다: {source_path}")
    if source_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(
            f"지원하지 않는 확장자입니다: {source_path.suffix} "
            f"(지원: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))})"
        )

    return source_path


def validate_media_source(source_path: Path):
    source_path = source_path.expanduser().resolve()

    if not source_path.exists():
        raise FileNotFoundError(f"미디어 파일이 없습니다: {source_path}")
    if not source_path.is_file():
        raise ValueError(f"미디어 경로가 파일이 아닙니다: {source_path}")
    if source_path.suffix.lower() not in SUPPORTED_MEDIA_EXTENSIONS:
        raise ValueError(
            f"지원하지 않는 확장자입니다: {source_path.suffix} "
            f"(지원: {', '.join(sorted(SUPPORTED_MEDIA_EXTENSIONS))})"
        )

    return source_path


def find_ffmpeg_binary():
    binary_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    candidates = []

    configured_binary = shutil.which("ffmpeg")
    if configured_binary:
        candidates.append(Path(configured_binary))

    conda_prefix = os.environ.get("CONDA_PREFIX", "").strip()
    if conda_prefix:
        candidates.append(Path(conda_prefix) / "bin" / binary_name)
        candidates.append(Path(conda_prefix) / "Library" / "bin" / binary_name)

    python_bin_dir = Path(sys.executable).expanduser().resolve().parent
    candidates.append(python_bin_dir / binary_name)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate)

    return ""


def _summarize_subprocess_error(error_output: str) -> str:
    cleaned_lines = []

    for line in error_output.splitlines():
        line = line.strip()
        if line:
            cleaned_lines.append(line)

    if not cleaned_lines:
        return "ffmpeg 오류 내용을 확인하지 못했습니다."

    summary = " / ".join(cleaned_lines[-3:])
    if len(summary) > 240:
        summary = f"{summary[:237]}..."
    return summary


def extract_audio_from_video(video_path: Path, destination_path: Path):
    ffmpeg_binary = find_ffmpeg_binary()
    if not ffmpeg_binary:
        return {
            "succeeded": False,
            "status": PENDING_FFMPEG_STATUS,
            "error": "ffmpeg를 찾지 못했습니다.",
        }

    destination_path.parent.mkdir(parents=True, exist_ok=True)

    commands = [
        [
            ffmpeg_binary,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "24000",
            "-acodec",
            "pcm_s16le",
            "-f",
            "wav",
            str(destination_path),
        ],
        [
            ffmpeg_binary,
            "-y",
            "-loglevel",
            "error",
            "-analyzeduration",
            "100M",
            "-probesize",
            "100M",
            "-i",
            str(video_path),
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-ar",
            "24000",
            "-acodec",
            "pcm_s16le",
            "-f",
            "wav",
            str(destination_path),
        ],
    ]

    last_error = "알 수 없는 ffmpeg 오류"

    for command in commands:
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            return {
                "succeeded": True,
                "status": "ready",
                "error": "",
            }
        except subprocess.CalledProcessError as error:
            if destination_path.exists():
                destination_path.unlink()
            last_error = _summarize_subprocess_error(error.stderr or "")

    return {
        "succeeded": False,
        "status": EXTRACT_FAILED_STATUS,
        "error": last_error,
    }


def _normalize_audio_with_python_audio_stack(source_path: Path, destination_path: Path):
    try:
        import soundfile as sf
    except ImportError:
        return {
            "succeeded": False,
            "error": "Python `soundfile` 패키지가 없어 참조 음성을 변환할 수 없습니다.",
        }

    try:
        audio_data, sample_rate = sf.read(str(source_path), always_2d=True)
    except Exception as error:
        return {
            "succeeded": False,
            "error": str(error),
        }

    mono_audio = audio_data.mean(axis=1)
    target_sample_rate = 24000

    if sample_rate != target_sample_rate:
        try:
            from math import gcd

            from scipy.signal import resample_poly

            shared_divisor = gcd(int(sample_rate), target_sample_rate)
            upsample_factor = target_sample_rate // shared_divisor
            downsample_factor = sample_rate // shared_divisor
            mono_audio = resample_poly(
                mono_audio,
                upsample_factor,
                downsample_factor,
            )
            sample_rate = target_sample_rate
        except Exception:
            pass

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        sf.write(str(destination_path), mono_audio, sample_rate, subtype="PCM_16")
    except Exception as error:
        if destination_path.exists():
            destination_path.unlink()
        return {
            "succeeded": False,
            "error": str(error),
        }

    return {
        "succeeded": True,
        "error": "",
    }


def normalize_audio_for_xtts(source_path: Path, destination_path: Path):
    source_path = source_path.expanduser().resolve()
    destination_path = destination_path.expanduser().resolve()

    ffmpeg_binary = find_ffmpeg_binary()
    if ffmpeg_binary:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        commands = [
            [
                ffmpeg_binary,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(source_path),
                "-ac",
                "1",
                "-ar",
                "24000",
                "-acodec",
                "pcm_s16le",
                "-f",
                "wav",
                str(destination_path),
            ],
            [
                ffmpeg_binary,
                "-y",
                "-loglevel",
                "error",
                "-analyzeduration",
                "100M",
                "-probesize",
                "100M",
                "-i",
                str(source_path),
                "-ac",
                "1",
                "-ar",
                "24000",
                "-acodec",
                "pcm_s16le",
                "-f",
                "wav",
                str(destination_path),
            ],
        ]

        last_error = "알 수 없는 ffmpeg 오류"

        for command in commands:
            try:
                subprocess.run(
                    command,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                return {
                    "succeeded": True,
                    "error": "",
                }
            except subprocess.CalledProcessError as error:
                if destination_path.exists():
                    destination_path.unlink()
                last_error = _summarize_subprocess_error(error.stderr or "")

        return {
            "succeeded": False,
            "error": last_error,
        }

    python_stack_result = _normalize_audio_with_python_audio_stack(
        source_path=source_path,
        destination_path=destination_path,
    )
    if python_stack_result["succeeded"]:
        return python_stack_result

    if source_path.suffix.lower() == ".wav":
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path != destination_path:
            shutil.copy2(source_path, destination_path)
        return {
            "succeeded": True,
            "error": "",
        }

    return {
        "succeeded": False,
        "error": (
            "ffmpeg를 찾지 못했고, 현재 Python 오디오 스택으로도 읽지 못했습니다. "
            f"{python_stack_result['error']}"
        ),
    }


def _trim_waveform_edges(audio_data, sample_rate: int):
    import numpy as np

    waveform = np.asarray(audio_data, dtype="float32").reshape(-1)
    if waveform.size == 0:
        return waveform

    peak_amplitude = float(np.max(np.abs(waveform)))
    if peak_amplitude <= 1e-6:
        return waveform

    threshold = max(peak_amplitude * REFERENCE_SILENCE_THRESHOLD_RATIO, 0.0025)
    active_indices = np.flatnonzero(np.abs(waveform) >= threshold)
    if active_indices.size == 0:
        return waveform

    padding_frames = int(sample_rate * 0.12)
    start_index = max(int(active_indices[0]) - padding_frames, 0)
    end_index = min(int(active_indices[-1]) + padding_frames + 1, waveform.size)
    trimmed = waveform[start_index:end_index]

    minimum_frames = int(sample_rate * REFERENCE_MIN_ACTIVE_SECONDS)
    if trimmed.size < minimum_frames:
        return waveform

    return trimmed


def _pick_reference_window(audio_data, sample_rate: int):
    import numpy as np

    waveform = np.asarray(audio_data, dtype="float32").reshape(-1)
    max_frames = int(sample_rate * REFERENCE_MAX_SECONDS)
    target_frames = int(sample_rate * REFERENCE_TARGET_SECONDS)

    if waveform.size <= max_frames:
        return waveform

    # For zero-shot XTTS, a stable early speaking segment tends to sound less
    # distorted than the loudest/highest-energy segment, which can over-select
    # shouts or emotionally exaggerated parts.
    window_frames = min(target_frames, waveform.size)
    return waveform[:window_frames]


def _apply_reference_fade(audio_data, sample_rate: int):
    import numpy as np

    waveform = np.asarray(audio_data, dtype="float32").reshape(-1)
    fade_frames = min(int(sample_rate * REFERENCE_FADE_SECONDS), waveform.size // 2)
    if fade_frames <= 0:
        return waveform

    fade_curve = np.linspace(0.0, 1.0, fade_frames, dtype="float32")
    waveform[:fade_frames] *= fade_curve
    waveform[-fade_frames:] *= fade_curve[::-1]
    return waveform


def _normalize_reference_level(audio_data):
    import numpy as np

    waveform = np.asarray(audio_data, dtype="float32").reshape(-1)
    if waveform.size == 0:
        return waveform

    waveform = waveform - float(np.mean(waveform))
    peak_amplitude = float(np.max(np.abs(waveform)))
    if peak_amplitude <= 1e-6:
        return waveform

    return waveform / peak_amplitude * 0.92


def prepare_reference_audio_for_xtts(source_wav_path: Path, destination_path: Path) -> Path:
    import numpy as np

    try:
        import soundfile as sf
    except ImportError as error:
        raise RuntimeError(
            "참조 음성 전처리에 필요한 `soundfile` 패키지가 없습니다."
        ) from error

    source_wav_path = source_wav_path.expanduser().resolve()
    destination_path = destination_path.expanduser().resolve()

    if not source_wav_path.exists():
        raise FileNotFoundError(f"참조 음성이 없습니다: {source_wav_path}")

    audio_data, sample_rate = sf.read(
        str(source_wav_path),
        dtype="float32",
        always_2d=True,
    )
    mono_audio = np.asarray(audio_data.mean(axis=1), dtype="float32")
    prepared_audio = _trim_waveform_edges(mono_audio, sample_rate)
    prepared_audio = _pick_reference_window(prepared_audio, sample_rate)
    prepared_audio = _normalize_reference_level(prepared_audio)
    prepared_audio = _apply_reference_fade(prepared_audio, sample_rate)

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(
        str(destination_path),
        prepared_audio,
        sample_rate,
        subtype="PCM_16",
    )
    return destination_path


def _load_manifest(manifest_path: Path):
    if not manifest_path.exists():
        return {"items": []}

    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_manifest(manifest_path: Path, manifest_data):
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest_data, handle, ensure_ascii=True, indent=2)


def store_reference_audio(source_path: Path, destination_dir: Path) -> Path:
    source_path = validate_audio_source(source_path)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_path = destination_dir / "reference.wav"
    prepared_reference_path = destination_dir / "reference_xtts.wav"

    for existing_reference in destination_dir.glob("reference.*"):
        if existing_reference.is_file() and existing_reference != destination_path:
            existing_reference.unlink()
    if prepared_reference_path.exists() and prepared_reference_path.is_file():
        prepared_reference_path.unlink()

    conversion_result = normalize_audio_for_xtts(
        source_path=source_path,
        destination_path=destination_path,
    )
    if not conversion_result["succeeded"]:
        raise RuntimeError(
            "참조 음성을 XTTS용 WAV로 변환하지 못했습니다. "
            f"{conversion_result['error']}"
        )

    prepare_reference_audio_for_xtts(
        source_wav_path=destination_path,
        destination_path=prepared_reference_path,
    )

    return destination_path


def ensure_reference_audio_for_xtts(reference_path: Path) -> Path:
    reference_path = validate_audio_source(reference_path)
    normalized_reference_path = reference_path.with_name("reference.wav")
    prepared_reference_path = reference_path.with_name("reference_xtts.wav")

    if (
        prepared_reference_path.exists()
        and prepared_reference_path.is_file()
        and normalized_reference_path.exists()
        and prepared_reference_path.stat().st_mtime >= normalized_reference_path.stat().st_mtime
    ):
        return prepared_reference_path

    if reference_path.suffix.lower() != ".wav" or not normalized_reference_path.exists():
        if reference_path.suffix.lower() == ".wav":
            normalized_reference_path = reference_path
        else:
            conversion_result = normalize_audio_for_xtts(
                source_path=reference_path,
                destination_path=normalized_reference_path,
            )
            if not conversion_result["succeeded"]:
                raise RuntimeError(
                    "참조 음성을 XTTS용 WAV로 변환하지 못했습니다. "
                    f"{conversion_result['error']}"
                )

    return prepare_reference_audio_for_xtts(
        source_wav_path=normalized_reference_path,
        destination_path=prepared_reference_path,
    )


def import_training_media(
    source_paths,
    raw_media_dir: Path,
    processed_training_dir: Path,
    manifest_path: Path,
):
    raw_media_dir.mkdir(parents=True, exist_ok=True)
    processed_training_dir.mkdir(parents=True, exist_ok=True)

    manifest_data = _load_manifest(manifest_path)
    first_audio_path = None
    audio_files = 0
    video_files = 0
    extracted_video_files = 0
    pending_video_files = 0
    pending_ffmpeg_files = 0
    failed_video_files = 0
    pending_video_errors = []

    for source_path in source_paths:
        source_path = validate_media_source(source_path)
        raw_destination = build_unique_destination(raw_media_dir / source_path.name)
        shutil.copy2(source_path, raw_destination)

        suffix = source_path.suffix.lower()
        if suffix in SUPPORTED_AUDIO_EXTENSIONS:
            prepared_destination = build_unique_destination(
                processed_training_dir / raw_destination.name
            )
            shutil.copy2(source_path, prepared_destination)

            if first_audio_path is None:
                first_audio_path = raw_destination

            audio_files += 1
            manifest_data["items"].append(
                {
                    "source_name": source_path.name,
                    "stored_name": raw_destination.name,
                    "kind": "audio",
                    "status": "ready",
                    "prepared_name": prepared_destination.name,
                    "error": "",
                }
            )
            continue

        video_files += 1
        prepared_destination = build_unique_destination(
            processed_training_dir / f"{raw_destination.stem}.wav"
        )
        extraction_result = extract_audio_from_video(
            video_path=raw_destination,
            destination_path=prepared_destination,
        )

        if extraction_result["succeeded"]:
            extracted_video_files += 1
            if first_audio_path is None:
                first_audio_path = prepared_destination

            manifest_data["items"].append(
                {
                    "source_name": source_path.name,
                    "stored_name": raw_destination.name,
                    "kind": "video",
                    "status": "ready",
                    "prepared_name": prepared_destination.name,
                    "error": "",
                }
            )
            continue

        pending_video_files += 1
        if extraction_result["status"] == PENDING_FFMPEG_STATUS:
            pending_ffmpeg_files += 1
        else:
            failed_video_files += 1
        pending_video_errors.append(
            f"{raw_destination.name}: {extraction_result['error']}"
        )
        manifest_data["items"].append(
            {
                "source_name": source_path.name,
                "stored_name": raw_destination.name,
                "kind": "video",
                "status": extraction_result["status"],
                "prepared_name": "",
                "error": extraction_result["error"],
            }
        )

    _save_manifest(manifest_path, manifest_data)

    return {
        "audio_files": audio_files,
        "video_files": video_files,
        "extracted_video_files": extracted_video_files,
        "pending_video_files": pending_video_files,
        "pending_ffmpeg_files": pending_ffmpeg_files,
        "failed_video_files": failed_video_files,
        "pending_video_errors": pending_video_errors,
        "first_audio_path": first_audio_path,
        "manifest_path": manifest_path,
    }


def retry_pending_video_extractions(
    raw_media_dir: Path,
    processed_training_dir: Path,
    manifest_path: Path,
    retry_failed: bool = False,
):
    manifest_data = _load_manifest(manifest_path)
    processed_training_dir.mkdir(parents=True, exist_ok=True)

    extracted_video_files = 0
    remaining_video_files = 0
    remaining_video_errors = []
    first_audio_path = None

    for item in manifest_data.get("items", []):
        if item.get("kind") != "video":
            continue
        allowed_statuses = {PENDING_FFMPEG_STATUS}
        if retry_failed:
            allowed_statuses.add(EXTRACT_FAILED_STATUS)
        if item.get("status") not in allowed_statuses:
            continue

        stored_name = item.get("stored_name", "").strip()
        if not stored_name:
            continue

        raw_video_path = raw_media_dir / stored_name
        if not raw_video_path.exists():
            continue

        prepared_name = item.get("prepared_name", "").strip()
        if prepared_name:
            prepared_destination = processed_training_dir / Path(prepared_name).name
        else:
            prepared_destination = build_unique_destination(
                processed_training_dir / f"{raw_video_path.stem}.wav"
            )

        extraction_result = extract_audio_from_video(
            video_path=raw_video_path,
            destination_path=prepared_destination,
        )
        if not extraction_result["succeeded"]:
            item["status"] = extraction_result["status"]
            item["error"] = extraction_result["error"]
            item["prepared_name"] = ""
            remaining_video_files += 1
            remaining_video_errors.append(
                f"{stored_name}: {extraction_result['error']}"
            )
            continue

        item["status"] = "ready"
        item["prepared_name"] = prepared_destination.name
        item["error"] = ""
        extracted_video_files += 1

        if first_audio_path is None:
            first_audio_path = prepared_destination

    _save_manifest(manifest_path, manifest_data)

    return {
        "extracted_video_files": extracted_video_files,
        "remaining_video_files": remaining_video_files,
        "remaining_video_errors": remaining_video_errors,
        "first_audio_path": first_audio_path,
    }
