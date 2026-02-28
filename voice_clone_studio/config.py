import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeSettings:
    device: str
    use_rvc_postprocess: bool


@dataclass(frozen=True)
class XttsSettings:
    model_name: str
    language: str


@dataclass(frozen=True)
class RvcSettings:
    enabled: bool
    inference_script: str
    model_path: str
    index_path: str


@dataclass(frozen=True)
class AppSettings:
    runtime: RuntimeSettings
    xtts: XttsSettings
    rvc: RvcSettings


def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_settings(project_root: Path) -> AppSettings:
    config_dir = project_root / "config"
    settings_path = config_dir / "settings.json"
    fallback_path = config_dir / "settings.example.json"

    config_data = _read_json(settings_path) if settings_path.exists() else _read_json(fallback_path)

    runtime_data = config_data.get("runtime", {})
    xtts_data = config_data.get("xtts", {})
    rvc_data = config_data.get("rvc", {})

    return AppSettings(
        runtime=RuntimeSettings(
            device=runtime_data.get("device", "cuda"),
            use_rvc_postprocess=runtime_data.get("use_rvc_postprocess", True),
        ),
        xtts=XttsSettings(
            model_name=xtts_data.get(
                "model_name",
                "tts_models/multilingual/multi-dataset/xtts_v2",
            ),
            language=xtts_data.get("language", "ko"),
        ),
        rvc=RvcSettings(
            enabled=rvc_data.get("enabled", True),
            inference_script=rvc_data.get("inference_script", ""),
            model_path=rvc_data.get("model_path", ""),
            index_path=rvc_data.get("index_path", ""),
        ),
    )
