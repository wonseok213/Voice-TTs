# Voice Clone Studio

`XTTS v2`를 메인으로 쓰고, 필요하면 `RVC`를 후처리로 붙이는 로컬 음성 클론 프로젝트 뼈대입니다.

이 프로젝트는 네 PC 사양 기준으로 아래 방향을 전제로 잡았습니다.

- GPU: `RTX 4060 Ti 8GB`
- RAM: `16GB`
- 목표: 로컬 `추론` 중심
- 추천 흐름: `XTTS TTS -> 선택적 RVC 보정`

## Why This Stack

- `XTTS v2`는 텍스트를 원하는 목소리로 읽게 만드는 TTS에 적합합니다.
- `RVC`는 만들어진 음성을 목표 음색에 더 가깝게 다듬는 후처리 단계로 붙이기 좋습니다.
- 네 PC에서는 초대형 학습보다, 좋은 사전학습 모델을 가져와 `추론 + 가벼운 적응` 쪽이 현실적입니다.

## Current Scope

이 저장소는 다음을 위한 시작점입니다.

- 폴더 구조 정리
- 설정 파일 구조
- CLI 실행 흐름
- 음성 프로필(참조 음성) 관리
- XTTS / RVC 연동 지점 분리
- 웹에서 학습용 데이터셋 업로드

실제 모델 다운로드와 패키지 설치는 아직 자동으로 하지 않습니다.

## Layout

```text
voice_clone_studio/
  config/
    settings.example.json
  data/
    raw/
    processed/
  models/
  outputs/
  tools/
    rvc_passthrough.py
  voice_clone_studio/
    services/
      audio_prep.py
      rvc_service.py
      xtts_service.py
    config.py
    paths.py
    pipeline.py
    web_app.py
  main.py
  pkg_resources.py
  requirements.txt
  CODEX_MEMORY.md
  TODO.md
```

## Basic Flow

1. 참조 음성 파일을 `data/raw/<profile>/reference.*` 쪽으로 넣습니다.
2. 웹 또는 CLI로 여러 개의 녹음 파일을 `학습용 데이터셋`으로 넣습니다.
3. 영상 파일은 `ffmpeg`가 있으면 자동으로 `wav`로 추출되어 학습 데이터셋에 들어갑니다.
4. `ffmpeg`가 없거나 추출에 실패하면 영상 원본만 저장되고 대기 상태로 남습니다.
5. 필요하면 전처리로 샘플레이트, 포맷, 볼륨을 정리합니다.
6. `XTTS`로 텍스트를 합성합니다.
7. 필요하면 합성 결과를 `RVC`로 한 번 더 변환합니다.
8. 결과 파일은 `outputs/`에 저장합니다.

## Commands

설정 파일 복사:

```bash
cp config/settings.example.json config/settings.json
```

참조 음성 등록:

```bash
python3 main.py add-reference --profile my_voice --source /path/to/reference.wav
```

XTTS만 사용:

```bash
python3 main.py synthesize --profile my_voice --text "안녕하세요" --output outputs/hello.wav
```

Coqui XTTS 약관 동의 저장:

```bash
python3 main.py accept-coqui-tos --i-understand
```

XTTS + RVC 전체 파이프라인:

```bash
python3 main.py clone --profile my_voice --text "안녕하세요" --output outputs/hello_rvc.wav
```

웹 UI 실행:

```bash
python3 main.py serve-web --host 127.0.0.1 --port 5000
```

웹 UI에서는 다음이 가능합니다.

- 프로필별 참조 음성 여부 확인
- 여러 오디오 파일 한 번에 선택해서 학습용 데이터셋 등록
- 영상 파일 업로드 후 `ffmpeg`로 자동 음성 추출
- 필요하면 참조 음성 직접 덮어쓰기
- 텍스트 입력 후 합성 실행
- 웹에서 Coqui XTTS 약관 동의를 한 번 저장한 뒤 합성 실행

## Notes

- 실제 `XTTS` / `RVC` 패키지가 없으면, 실행 시 친절한 에러 메시지를 내도록 해두었습니다.
- 이 프로젝트는 `numpy==1.22.0`, `TTS==0.22.0`, `transformers==4.41.2` 조합으로 고정합니다. 다른 최신 버전으로 올라가면 XTTS가 쉽게 깨집니다.
- `torch 2.6+`에서는 `weights_only=True` 기본값 때문에 Coqui XTTS 체크포인트 로딩이 깨질 수 있어서, 이 프로젝트는 XTTS 실행 시 `torch.load` 기본값을 호환 모드로 패치합니다.
- `torchaudio 2.9+`는 기본 `load()`가 `torchcodec`을 요구할 수 있어서, 이 프로젝트는 XTTS 실행 시 `torchaudio.load`를 `soundfile` 기반으로 우회합니다.
- 현재 기본 `RVC` 설정은 `tools/rvc_passthrough.py`로 연결되어 있어서 전체 파이프라인 점검용으로는 바로 동작합니다.
- 실제 RVC를 붙일 때는 `config/settings.json`의 `rvc.inference_script`를 실제 스크립트 경로로 바꾸면 됩니다.
- `pkg_resources.py`는 최신 `setuptools` 환경에서 `TTS` import 호환성을 맞추기 위한 작은 shim입니다.
- 실제 첫 `XTTS` 합성 때는 모델 파일을 처음 다운로드할 수 있으니, 네 터미널에서 한 번 직접 실행하는 편이 안전합니다.
- Coqui XTTS는 처음 사용 전에 라이선스 확인이 필요합니다. 웹의 `약관 동의 저장` 버튼이나 `accept-coqui-tos --i-understand`로 네가 직접 동의해야 실행됩니다.
- 현재 `ffmpeg`가 있으면 영상 파일 업로드 시 자동으로 `wav`를 추출합니다.
- 추출이 실패하면 영상 원본은 그대로 보관되고, 최근 ffmpeg 오류가 웹에 표시됩니다.
- 타인 음성은 명시적 허락 없이 사용하지 않는 것이 맞습니다.
