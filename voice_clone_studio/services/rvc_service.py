import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RvcRequest:
    source_wav: Path
    output_wav: Path
    inference_script: str
    model_path: str
    index_path: str


class RvcService:
    def convert(self, request: RvcRequest) -> Path:
        if not request.source_wav.exists():
            raise FileNotFoundError(f"RVC 입력 파일이 없습니다: {request.source_wav}")

        request.output_wav.parent.mkdir(parents=True, exist_ok=True)

        if not request.inference_script:
            shutil.copy2(request.source_wav, request.output_wav)
            return request.output_wav

        script_path = Path(request.inference_script).expanduser().resolve()
        if not script_path.exists():
            raise FileNotFoundError(f"RVC 스크립트가 없습니다: {script_path}")

        command = [
            sys.executable,
            str(script_path),
            "--input",
            str(request.source_wav),
            "--output",
            str(request.output_wav),
            "--model",
            request.model_path,
        ]

        if request.index_path:
            command.extend(["--index", request.index_path])

        subprocess.run(command, check=True)
        return request.output_wav
