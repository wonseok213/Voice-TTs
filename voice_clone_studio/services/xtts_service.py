import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Union


XTTS_TEMPERATURE = 0.32
XTTS_REPETITION_PENALTY = 5.0
XTTS_SPEED = 0.94


@dataclass(frozen=True)
class XttsRequest:
    text: str
    language: str
    model_name: str
    device: str
    speaker_wav: Union[Path, list[Path]]
    output_wav: Path
    coqui_tos_agreed: bool


def _normalize_tts_text(text: str) -> str:
    collapsed = " ".join(text.replace("\r", "\n").replace("\t", " ").split())
    collapsed = re.sub(r"\s*([,;:.!?])\s*", r"\1 ", collapsed)
    collapsed = re.sub(r"\s*([，、。！？])\s*", r"\1 ", collapsed)
    return collapsed.strip()


def _patch_torch_load_for_trusted_xtts_checkpoints():
    import torch

    if getattr(torch, "_voice_clone_studio_torch_load_patched", False):
        return

    original_torch_load = torch.load

    def compatible_torch_load(*args, **kwargs):
        # Coqui XTTS checkpoints still expect the old torch.load behavior.
        kwargs.setdefault("weights_only", False)
        return original_torch_load(*args, **kwargs)

    torch.load = compatible_torch_load
    torch._voice_clone_studio_torch_load_patched = True


def _patch_torchaudio_load_without_torchcodec():
    import torch
    import torchaudio
    import soundfile as sf

    if getattr(torchaudio, "_voice_clone_studio_load_patched", False):
        return

    def compatible_torchaudio_load(
        uri,
        frame_offset=0,
        num_frames=-1,
        normalize=True,
        channels_first=True,
        format=None,
        buffer_size=4096,
        backend=None,
    ):
        del normalize, format, buffer_size, backend

        start_frame = max(frame_offset, 0)
        frames = num_frames if num_frames is not None else -1
        if frames == 0:
            frames = -1

        audio_data, sample_rate = sf.read(
            uri,
            start=start_frame,
            frames=frames,
            dtype="float32",
            always_2d=True,
        )
        audio_tensor = torch.from_numpy(audio_data)

        if channels_first:
            audio_tensor = audio_tensor.transpose(0, 1)

        return audio_tensor.contiguous(), sample_rate

    torchaudio.load = compatible_torchaudio_load
    torchaudio._voice_clone_studio_load_patched = True


class XttsService:
    def synthesize(self, request: XttsRequest) -> Path:
        _patch_torch_load_for_trusted_xtts_checkpoints()
        _patch_torchaudio_load_without_torchcodec()

        try:
            from TTS.api import TTS
        except ImportError as error:
            raise RuntimeError(
                "XTTS 실행에 필요한 `TTS` 패키지가 없습니다. "
                "먼저 requirements 설치 후 다시 시도하세요."
            ) from error

        speaker_paths = request.speaker_wav if isinstance(request.speaker_wav, list) else [request.speaker_wav]
        missing_paths = [path for path in speaker_paths if not path.exists()]
        if missing_paths:
            raise FileNotFoundError(f"참조 음성이 없습니다: {missing_paths[0]}")

        if request.coqui_tos_agreed:
            os.environ["COQUI_TOS_AGREED"] = "1"

        request.output_wav.parent.mkdir(parents=True, exist_ok=True)

        tts = TTS(request.model_name).to(request.device)
        normalized_text = _normalize_tts_text(request.text)
        if not normalized_text:
            raise ValueError("읽을 텍스트가 비어 있습니다.")
        speaker_wav = [str(path) for path in speaker_paths]
        if len(speaker_wav) == 1:
            speaker_wav = speaker_wav[0]

        wav = tts.tts(
            text=normalized_text,
            speaker_wav=speaker_wav,
            language=request.language,
            split_sentences=False,
            enable_text_splitting=True,
            temperature=XTTS_TEMPERATURE,
            repetition_penalty=XTTS_REPETITION_PENALTY,
            speed=XTTS_SPEED,
        )
        tts.synthesizer.save_wav(wav=wav, path=str(request.output_wav))
        return request.output_wav
