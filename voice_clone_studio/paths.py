from dataclasses import dataclass
from pathlib import Path


def sanitize_name(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value.strip())
    cleaned = cleaned.strip("_")
    return cleaned or "default"


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    config_dir: Path
    data_raw_dir: Path
    data_processed_dir: Path
    models_dir: Path
    outputs_dir: Path
    temp_dir: Path

    @classmethod
    def from_root(cls, root: Path):
        root = root.expanduser().resolve()
        return cls(
            root=root,
            config_dir=root / "config",
            data_raw_dir=root / "data" / "raw",
            data_processed_dir=root / "data" / "processed",
            models_dir=root / "models",
            outputs_dir=root / "outputs",
            temp_dir=root / "outputs" / "temp",
        )

    def ensure_directories(self):
        for path in (
            self.config_dir,
            self.data_raw_dir,
            self.data_processed_dir,
            self.models_dir,
            self.outputs_dir,
            self.temp_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def raw_profile_dir(self, profile_name: str) -> Path:
        return self.data_raw_dir / sanitize_name(profile_name)

    def processed_profile_dir(self, profile_name: str) -> Path:
        return self.data_processed_dir / sanitize_name(profile_name)

    def raw_media_dir(self, profile_name: str) -> Path:
        return self.raw_profile_dir(profile_name) / "media"

    def training_dataset_dir(self, profile_name: str) -> Path:
        return self.processed_profile_dir(profile_name) / "training"

    def training_manifest_path(self, profile_name: str) -> Path:
        return self.processed_profile_dir(profile_name) / "dataset_manifest.json"

    @property
    def coqui_tos_marker_path(self) -> Path:
        return self.config_dir / "coqui_tos_agreed.txt"
