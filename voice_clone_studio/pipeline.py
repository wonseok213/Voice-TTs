import json
from pathlib import Path
from shutil import copy2

from voice_clone_studio.config import load_settings
from voice_clone_studio.paths import ProjectPaths
from voice_clone_studio.services.audio_prep import (
    SUPPORTED_AUDIO_EXTENSIONS,
    import_training_media,
    normalize_audio_for_xtts,
    retry_pending_video_extractions,
    store_reference_audio,
)
from voice_clone_studio.services.rvc_service import RvcRequest, RvcService
from voice_clone_studio.services.xtts_service import XttsRequest, XttsService


class VoiceClonePipeline:
    def __init__(self, project_root: Path):
        self.paths = ProjectPaths.from_root(project_root)
        self.paths.ensure_directories()
        self.settings = load_settings(self.paths.root)
        self.xtts_service = XttsService()
        self.rvc_service = RvcService()

    def add_reference(self, profile_name: str, source_path: Path) -> Path:
        destination_dir = self.paths.raw_profile_dir(profile_name)
        return store_reference_audio(source_path=source_path, destination_dir=destination_dir)

    def has_coqui_tos_agreement(self) -> bool:
        return self.paths.coqui_tos_marker_path.exists()

    def accept_coqui_tos(self) -> Path:
        marker_path = self.paths.coqui_tos_marker_path
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(
            "The local user confirmed they purchased a commercial Coqui license "
            "or agreed to the non-commercial CPML terms.\n",
            encoding="utf-8",
        )
        return marker_path

    def list_profiles(self):
        names = set()

        for base_dir in (self.paths.data_raw_dir, self.paths.data_processed_dir):
            for entry in sorted(base_dir.iterdir(), key=lambda path: path.name.lower()):
                if entry.is_dir():
                    names.add(entry.name)

        return sorted(names, key=str.lower)

    def list_profile_summaries(self):
        summaries = []

        for profile_name in self.list_profiles():
            training_dir = self.paths.training_dataset_dir(profile_name)
            manifest_path = self.paths.training_manifest_path(profile_name)
            training_audio_count = 0
            pending_video_count = 0
            pending_video_errors = []

            if training_dir.exists():
                training_audio_count = sum(
                    1 for candidate in training_dir.iterdir() if candidate.is_file()
                )

            if manifest_path.exists():
                with manifest_path.open("r", encoding="utf-8") as handle:
                    manifest_data = json.load(handle)
                for item in manifest_data.get("items", []):
                    if item.get("kind") != "video":
                        continue
                    if item.get("status") == "ready":
                        continue

                    pending_video_count += 1
                    error_text = item.get("error", "").strip()
                    stored_name = item.get("stored_name", "").strip() or item.get(
                        "source_name", ""
                    ).strip()
                    if error_text and stored_name:
                        pending_video_errors.append(f"{stored_name}: {error_text}")
                    elif error_text:
                        pending_video_errors.append(error_text)

            summaries.append(
                {
                    "name": profile_name,
                    "has_reference": self._has_reference_audio(profile_name),
                    "training_audio_count": training_audio_count,
                    "pending_video_count": pending_video_count,
                    "pending_video_errors": pending_video_errors[:3],
                }
            )

        return summaries

    def import_training_media(self, profile_name: str, source_paths):
        result = import_training_media(
            source_paths=source_paths,
            raw_media_dir=self.paths.raw_media_dir(profile_name),
            processed_training_dir=self.paths.training_dataset_dir(profile_name),
            manifest_path=self.paths.training_manifest_path(profile_name),
        )

        auto_reference_path = None
        if result["first_audio_path"] and not self._has_reference_audio(profile_name):
            auto_reference_path = store_reference_audio(
                source_path=result["first_audio_path"],
                destination_dir=self.paths.raw_profile_dir(profile_name),
            )

        result["auto_reference_path"] = auto_reference_path
        return result

    def retry_pending_video_extractions(self, profile_name: str, retry_failed: bool = False):
        result = retry_pending_video_extractions(
            raw_media_dir=self.paths.raw_media_dir(profile_name),
            processed_training_dir=self.paths.training_dataset_dir(profile_name),
            manifest_path=self.paths.training_manifest_path(profile_name),
            retry_failed=retry_failed,
        )

        auto_reference_path = None
        if result["first_audio_path"] and not self._has_reference_audio(profile_name):
            auto_reference_path = store_reference_audio(
                source_path=result["first_audio_path"],
                destination_dir=self.paths.raw_profile_dir(profile_name),
            )

        result["auto_reference_path"] = auto_reference_path
        return result

    def _collect_training_reference_audios(self, profile_name: str, limit: int = 2):
        training_dir = self.paths.training_dataset_dir(profile_name)
        if not training_dir.exists():
            return []

        cache_dir = self.paths.raw_profile_dir(profile_name) / "training_refs"
        collected_paths = []

        for candidate in sorted(training_dir.iterdir(), key=lambda path: path.name.lower()):
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
                continue

            normalized_path = cache_dir / f"{candidate.stem}.wav"
            if (
                not normalized_path.exists()
                or normalized_path.stat().st_mtime < candidate.stat().st_mtime
            ):
                conversion_result = normalize_audio_for_xtts(
                    source_path=candidate,
                    destination_path=normalized_path,
                )
                if not conversion_result["succeeded"]:
                    continue

            if normalized_path.exists() and normalized_path.is_file():
                collected_paths.append(normalized_path)

            if len(collected_paths) >= limit:
                break

        return collected_paths

    def _get_reference_audios(self, profile_name: str):
        raw_profile_dir = self.paths.raw_profile_dir(profile_name)
        preferred_reference = raw_profile_dir / "reference.wav"
        prepared_reference = raw_profile_dir / "reference_xtts.wav"

        primary_reference = None

        if preferred_reference.exists() and preferred_reference.is_file():
            primary_reference = preferred_reference
        else:
            for candidate in sorted(raw_profile_dir.glob("reference.*")):
                if candidate.is_file():
                    normalized_reference = candidate.with_name("reference.wav")
                    if candidate.suffix.lower() == ".wav":
                        primary_reference = candidate
                    else:
                        conversion_result = normalize_audio_for_xtts(
                            source_path=candidate,
                            destination_path=normalized_reference,
                        )
                        if conversion_result["succeeded"]:
                            primary_reference = normalized_reference
                    break

        if primary_reference is None and prepared_reference.exists() and prepared_reference.is_file():
            primary_reference = prepared_reference

        if primary_reference is None:
            raise FileNotFoundError(
                f"프로필 `{profile_name}`의 참조 음성이 없습니다. "
                "먼저 `add-reference`를 실행하세요."
            )

        reference_audios = [primary_reference]
        for candidate in self._collect_training_reference_audios(profile_name):
            if candidate not in reference_audios:
                reference_audios.append(candidate)

        return reference_audios

    def _get_reference_audio(self, profile_name: str) -> Path:
        for candidate in self._get_reference_audios(profile_name):
            if candidate.is_file():
                return candidate

        raise FileNotFoundError(
            f"프로필 `{profile_name}`의 참조 음성이 없습니다. "
            "먼저 `add-reference`를 실행하세요."
        )

    def _has_reference_audio(self, profile_name: str) -> bool:
        raw_profile_dir = self.paths.raw_profile_dir(profile_name)
        return any(candidate.is_file() for candidate in raw_profile_dir.glob("reference.*"))

    def synthesize(self, profile_name: str, text: str, output_path: Path) -> Path:
        if not self.has_coqui_tos_agreement():
            raise RuntimeError(
                "Coqui XTTS 약관 동의가 필요합니다. "
                "웹 화면에서 먼저 약관 동의를 저장하세요."
            )

        reference_audio = self._get_reference_audios(profile_name)
        resolved_output = self._resolve_output_path(output_path)

        request = XttsRequest(
            text=text,
            language=self.settings.xtts.language,
            model_name=self.settings.xtts.model_name,
            device=self.settings.runtime.device,
            speaker_wav=reference_audio,
            output_wav=resolved_output,
            coqui_tos_agreed=True,
        )
        return self.xtts_service.synthesize(request)

    def convert_with_rvc(self, source_path: Path, output_path: Path) -> Path:
        resolved_source = source_path.expanduser().resolve()
        resolved_output = self._resolve_output_path(output_path)

        request = RvcRequest(
            source_wav=resolved_source,
            output_wav=resolved_output,
            inference_script=self._resolve_optional_config_path(self.settings.rvc.inference_script),
            model_path=self._resolve_optional_config_path(self.settings.rvc.model_path),
            index_path=self._resolve_optional_config_path(self.settings.rvc.index_path),
        )
        return self.rvc_service.convert(request)

    def clone(self, profile_name: str, text: str, output_path: Path) -> Path:
        resolved_output = self._resolve_output_path(output_path)
        temp_output = self.paths.temp_dir / f"{resolved_output.stem}_xtts.wav"

        synthesized_path = self.synthesize(
            profile_name=profile_name,
            text=text,
            output_path=temp_output,
        )

        if not self.settings.runtime.use_rvc_postprocess or not self.settings.rvc.enabled:
            if synthesized_path != resolved_output:
                resolved_output.parent.mkdir(parents=True, exist_ok=True)
                copy2(synthesized_path, resolved_output)
            return resolved_output

        return self.convert_with_rvc(source_path=synthesized_path, output_path=resolved_output)

    def _resolve_output_path(self, output_path: Path) -> Path:
        output_path = output_path.expanduser()
        if not output_path.is_absolute():
            output_path = self.paths.root / output_path
        return output_path.resolve()

    def _resolve_optional_config_path(self, configured_path: str) -> str:
        if not configured_path:
            return ""

        path = Path(configured_path).expanduser()
        if not path.is_absolute():
            path = self.paths.root / path
        return str(path.resolve())
