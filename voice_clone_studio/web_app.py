from pathlib import Path

from flask import Flask, abort, redirect, render_template_string, request, send_from_directory, url_for

from voice_clone_studio.pipeline import VoiceClonePipeline


PAGE_TEMPLATE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>Voice Clone Studio</title>
  <style>
    :root {
      --bg: #f3efe6;
      --panel: #fffdf8;
      --border: #d7cbb7;
      --text: #1f1a14;
      --accent: #9f5f2e;
    }
    body {
      margin: 0;
      font-family: "Segoe UI", "Noto Sans KR", sans-serif;
      background: radial-gradient(circle at top right, #fff7df, var(--bg));
      color: var(--text);
    }
    main {
      max-width: 920px;
      margin: 40px auto;
      padding: 0 16px 40px;
    }
    h1 {
      margin-bottom: 8px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 20px;
      margin-bottom: 18px;
      box-shadow: 0 8px 24px rgba(80, 55, 20, 0.08);
    }
    label, input, textarea, button, select {
      display: block;
      width: 100%;
      box-sizing: border-box;
      font: inherit;
    }
    input, textarea, select {
      margin-top: 6px;
      margin-bottom: 12px;
      padding: 10px 12px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: #fff;
    }
    textarea {
      min-height: 100px;
      resize: vertical;
    }
    button {
      border: 0;
      border-radius: 10px;
      padding: 12px 14px;
      background: var(--accent);
      color: #fff;
      cursor: pointer;
      font-weight: 700;
    }
    .hint {
      color: #5f5243;
      font-size: 14px;
    }
    .message {
      margin-bottom: 16px;
      padding: 12px 14px;
      border-radius: 12px;
      background: #efe4d3;
      border: 1px solid var(--border);
    }
    ul {
      margin: 8px 0 0;
      padding-left: 20px;
    }
    .checkbox {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 10px 0 14px;
    }
    .checkbox input {
      width: auto;
      margin: 0;
    }
    .inline-form {
      display: inline-block;
      margin-left: 8px;
    }
    .inline-form button {
      width: auto;
      padding: 6px 10px;
      border-radius: 8px;
      font-size: 13px;
    }
    .output-item {
      margin-bottom: 18px;
      padding-bottom: 14px;
      border-bottom: 1px solid #eadfce;
    }
    .output-item.is-latest {
      padding: 14px;
      border: 1px solid #d9b88f;
      border-radius: 14px;
      background: linear-gradient(135deg, #fff6df, #fffdf8);
      box-shadow: 0 10px 24px rgba(159, 95, 46, 0.08);
    }
    .output-item:last-child {
      margin-bottom: 0;
      padding-bottom: 0;
      border-bottom: 0;
    }
    .output-meta {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
      font-size: 14px;
    }
    .output-title {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .output-actions {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .output-meta a {
      color: var(--accent);
      font-weight: 700;
      text-decoration: none;
    }
    .output-meta a:hover {
      text-decoration: underline;
    }
    .badge {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      background: #9f5f2e;
      color: #fff;
      font-size: 12px;
      font-weight: 700;
      line-height: 1;
    }
    audio {
      width: 100%;
    }
  </style>
</head>
<body>
  <main>
    <h1>Voice Clone Studio</h1>
    <p class="hint">XTTS로 음성을 만들고, 설정에 따라 RVC 후처리를 연결할 수 있습니다.</p>
    {% if message %}
      <div class="message">{{ message }}</div>
    {% endif %}

    <section class="card">
      <h2>Coqui XTTS 약관</h2>
      {% if coqui_tos_agreed %}
        <p class="hint">약관 동의가 저장되어 있습니다. 이제 XTTS 생성이 가능합니다.</p>
      {% else %}
        <p class="hint">XTTS 모델은 처음 사용 전에 Coqui 라이선스 확인이 필요합니다. 상업 라이선스를 구매했거나, 비상업 CPML 약관에 동의하는 경우에만 저장하세요.</p>
        <form method="post" action="{{ url_for('agree_coqui_tos') }}">
          <button type="submit">약관 동의 저장</button>
        </form>
      {% endif %}
    </section>

    <section class="card">
      <h2>등록된 프로필</h2>
      {% if profiles %}
        <ul>
          {% for profile in profiles %}
            <li>
              <strong>{{ profile.name }}</strong>
              /
              참조 {% if profile.has_reference %}있음{% else %}없음{% endif %}
              /
              학습 오디오 {{ profile.training_audio_count }}개
              /
              영상 추출 대기 {{ profile.pending_video_count }}개
              {% if profile.pending_video_count %}
              <form class="inline-form" method="post" action="{{ url_for('retry_profile_extraction') }}">
                <input type="hidden" name="profile_name" value="{{ profile.name }}">
                <button type="submit">다시 추출</button>
              </form>
              {% if profile.pending_video_errors %}
                <div class="hint">
                  최근 오류:
                  {{ profile.pending_video_errors | join(" / ") }}
                </div>
              {% endif %}
              {% endif %}
            </li>
          {% endfor %}
        </ul>
      {% else %}
        <p class="hint">아직 등록된 프로필이 없습니다.</p>
      {% endif %}
    </section>

    <section class="card">
      <h2>최근 생성 파일</h2>
      {% if outputs %}
        {% for output in outputs %}
          <div class="output-item{% if output.is_latest %} is-latest{% endif %}">
            <div class="output-meta">
              <div class="output-title">
                <strong>{{ output.name }}</strong>
                {% if output.is_latest %}
                  <span class="badge">방금 생성</span>
                {% endif %}
              </div>
              <div class="output-actions">
                <a href="{{ url_for('serve_output_file', filename=output.name) }}" target="_blank" rel="noopener">파일 열기</a>
                <a href="{{ url_for('serve_output_file', filename=output.name, download=1) }}">다운로드</a>
              </div>
            </div>
            <audio controls preload="none" src="{{ url_for('serve_output_file', filename=output.name) }}"></audio>
            <p class="hint">형식: {{ output.format }} / 저장 위치: {{ output.path }}</p>
          </div>
        {% endfor %}
      {% else %}
        <p class="hint">아직 생성된 출력 파일이 없습니다. `.wav`와 `.mp3`가 여기에 표시됩니다.</p>
      {% endif %}
    </section>

    <section class="card">
      <h2>학습용 데이터셋 등록</h2>
      <p class="hint">여러 개의 녹음 파일을 한 번에 고를 수 있습니다. 첫 번째 준비된 오디오가 자동으로 참조 음성이 될 수 있습니다. `ffmpeg`가 잡히면 영상 파일에서도 자동으로 음성을 추출합니다.</p>
      <form method="post" action="{{ url_for('add_training_data') }}" enctype="multipart/form-data">
        <label>
          기존 프로필 선택
          <select name="profile_select">
            <option value="">새 프로필 직접 입력</option>
            {% for profile in profiles %}
              <option value="{{ profile.name }}">{{ profile.name }}</option>
            {% endfor %}
          </select>
        </label>
        <label>
          새 프로필 이름(직접 입력할 때만)
          <input name="profile_new" placeholder="예: streamer_ko">
        </label>
        <label>
          녹음/영상 파일들
          <input type="file" name="media_files" accept=".wav,.mp3,.flac,.m4a,.ogg,.mp4,.mov,.mkv,.avi,.webm,.m4v" multiple required>
        </label>
        <button type="submit">학습 데이터 등록</button>
      </form>
    </section>

    <section class="card">
      <h2>참조 음성 직접 지정</h2>
      <p class="hint">배경음 없는 또박또박한 6~12초 정도의 짧은 음성이 가장 안정적으로 나옵니다. 업로드하면 XTTS용 참조 구간을 자동으로 정리합니다.</p>
      <form method="post" action="{{ url_for('add_reference') }}" enctype="multipart/form-data">
        <label>
          기존 프로필 선택
          <select name="profile_select">
            <option value="">새 프로필 직접 입력</option>
            {% for profile in profiles %}
              <option value="{{ profile.name }}">{{ profile.name }}</option>
            {% endfor %}
          </select>
        </label>
        <label>
          새 프로필 이름(직접 입력할 때만)
          <input name="profile_new" placeholder="예: streamer_ko">
        </label>
        <label>
          참조 음성 파일
          <input type="file" name="audio_file" accept=".wav,.mp3,.flac,.m4a,.ogg" required>
        </label>
        <button type="submit">참조 음성 등록</button>
      </form>
    </section>

    <section class="card">
      <h2>음성 생성</h2>
      <p class="hint">긴 문장은 XTTS 내부 분할을 사용해 자연스럽게 끊어 읽도록 처리합니다.</p>
      <form method="post" action="{{ url_for('generate_audio') }}">
        <label>
          기존 프로필 선택
          <select name="profile_select" required>
            <option value="">프로필 선택</option>
            {% for profile in profiles %}
              <option value="{{ profile.name }}">{{ profile.name }}</option>
            {% endfor %}
          </select>
        </label>
        <label>
          읽을 텍스트
          <textarea name="text" required></textarea>
        </label>
        <label>
          출력 파일명
          <input name="output_name" value="sample.wav" required>
        </label>
        <label class="checkbox">
          <input type="checkbox" name="use_rvc" value="1" checked>
          RVC 후처리 사용
        </label>
        <button type="submit">생성 실행</button>
      </form>
    </section>
  </main>
</body>
</html>
"""


def build_unique_upload_path(temp_dir: Path, original_name: str) -> Path:
    safe_name = Path(original_name).name or "upload.bin"
    destination = temp_dir / safe_name

    if not destination.exists():
        return destination

    stem = destination.stem
    suffix = destination.suffix
    counter = 1

    while True:
        candidate = temp_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def store_uploaded_file(upload, temp_dir: Path) -> Path:
    temp_dir.mkdir(parents=True, exist_ok=True)
    destination = build_unique_upload_path(temp_dir, upload.filename)
    upload.save(destination)
    return destination


def resolve_profile_name(form_data):
    selected_profile = form_data.get("profile_select", "").strip()
    new_profile = form_data.get("profile_new", "").strip()

    if selected_profile:
        return selected_profile
    return new_profile


def list_recent_outputs(outputs_dir: Path, limit: int = 5, latest_name: str = ""):
    allowed_suffixes = {".wav", ".mp3"}
    normalized_latest = Path(latest_name).name if latest_name else ""
    entries = []

    for file_path in outputs_dir.iterdir():
        if not file_path.is_file():
            continue

        suffix = file_path.suffix.lower()
        if suffix not in allowed_suffixes:
            continue

        entries.append(
            {
                "file_path": file_path,
                "mtime": file_path.stat().st_mtime,
                "is_latest": file_path.name == normalized_latest,
            }
        )

    entries.sort(
        key=lambda entry: (
            0 if entry["is_latest"] else 1,
            -entry["mtime"],
        )
    )

    return [
        {
            "name": entry["file_path"].name,
            "path": str(entry["file_path"]),
            "format": entry["file_path"].suffix.lower().lstrip(".").upper(),
            "is_latest": entry["is_latest"],
        }
        for entry in entries[:limit]
    ]


def create_app(project_root: Path):
    app = Flask(__name__)
    pipeline = VoiceClonePipeline(project_root=project_root)

    @app.get("/")
    def index():
        message = request.args.get("message", "")
        latest_output = Path(request.args.get("latest_output", "")).name
        return render_template_string(
            PAGE_TEMPLATE,
            message=message,
            profiles=pipeline.list_profile_summaries(),
            coqui_tos_agreed=pipeline.has_coqui_tos_agreement(),
            outputs=list_recent_outputs(
                pipeline.paths.outputs_dir,
                latest_name=latest_output,
            ),
        )

    @app.get("/outputs/<path:filename>")
    def serve_output_file(filename: str):
        safe_name = Path(filename).name
        if safe_name != filename:
            abort(404)
        return send_from_directory(
            str(pipeline.paths.outputs_dir),
            safe_name,
            as_attachment=request.args.get("download") == "1",
        )

    @app.post("/agree-coqui-tos")
    def agree_coqui_tos():
        marker_path = pipeline.accept_coqui_tos()
        return redirect(
            url_for(
                "index",
                message=f"Coqui XTTS 약관 동의 저장 완료: {marker_path.name}",
            )
        )

    @app.post("/add-training-data")
    def add_training_data():
        profile = resolve_profile_name(request.form)
        uploads = [
            upload
            for upload in request.files.getlist("media_files")
            if upload is not None and upload.filename
        ]

        if not profile or not uploads:
            return redirect(url_for("index", message="프로필 이름과 업로드 파일이 필요합니다."))

        temp_paths = []
        try:
            for upload in uploads:
                temp_paths.append(store_uploaded_file(upload, pipeline.paths.temp_dir))

            result = pipeline.import_training_media(
                profile_name=profile,
                source_paths=temp_paths,
            )
            retry_result = pipeline.retry_pending_video_extractions(
                profile,
                retry_failed=False,
            )
        except Exception as error:
            return redirect(url_for("index", message=f"데이터 등록 실패: {error}"))
        finally:
            for temp_path in temp_paths:
                if temp_path.exists():
                    temp_path.unlink()

        message_parts = [f"오디오 {result['audio_files']}개 등록"]
        if result["extracted_video_files"]:
            message_parts.append(
                f"영상 {result['extracted_video_files']}개에서 오디오 추출 완료"
            )
        if result["pending_ffmpeg_files"]:
            message_parts.append(
                f"영상 {result['pending_ffmpeg_files']}개는 ffmpeg를 찾지 못해 추출 대기"
            )
        if result["failed_video_files"]:
            message_parts.append(
                f"영상 {result['failed_video_files']}개는 추출 실패"
            )
        if retry_result["extracted_video_files"]:
            message_parts.append(
                f"기존 대기 영상 {retry_result['extracted_video_files']}개 재추출 완료"
            )
        if result["auto_reference_path"] is not None:
            message_parts.append("첫 오디오를 참조 음성으로 자동 지정")
        elif retry_result["auto_reference_path"] is not None:
            message_parts.append("재추출된 첫 오디오를 참조 음성으로 자동 지정")
        if result["pending_video_errors"]:
            message_parts.append(
                f"최근 오류: {' / '.join(result['pending_video_errors'][:2])}"
            )
        elif retry_result["remaining_video_errors"]:
            message_parts.append(
                f"재추출 후 남은 오류: {' / '.join(retry_result['remaining_video_errors'][:2])}"
            )

        return redirect(url_for("index", message=" / ".join(message_parts)))

    @app.post("/retry-extraction")
    def retry_profile_extraction():
        profile = request.form.get("profile_name", "").strip()

        if not profile:
            return redirect(url_for("index", message="프로필 이름이 필요합니다."))

        try:
            result = pipeline.retry_pending_video_extractions(
                profile,
                retry_failed=True,
            )
        except Exception as error:
            return redirect(url_for("index", message=f"재추출 실패: {error}"))

        if result["extracted_video_files"] == 0:
            if result["remaining_video_errors"]:
                message = (
                    "재추출 실패: "
                    + " / ".join(result["remaining_video_errors"][:2])
                )
            else:
                message = "다시 추출할 대기 영상이 없습니다."
            return redirect(url_for("index", message=message))

        message = f"대기 영상 {result['extracted_video_files']}개 재추출 완료"
        if result["auto_reference_path"] is not None:
            message += " / 재추출된 첫 오디오를 참조 음성으로 자동 지정"
        if result["remaining_video_errors"]:
            message += (
                " / 아직 남은 오류: "
                + " / ".join(result["remaining_video_errors"][:2])
            )

        return redirect(url_for("index", message=message))

    @app.post("/add-reference")
    def add_reference():
        profile = resolve_profile_name(request.form)
        upload = request.files.get("audio_file")

        if not profile or upload is None or not upload.filename:
            return redirect(url_for("index", message="프로필 이름과 음성 파일이 필요합니다."))

        temp_path = store_uploaded_file(upload, pipeline.paths.temp_dir)

        try:
            stored_path = pipeline.add_reference(profile_name=profile, source_path=temp_path)
        except Exception as error:
            return redirect(url_for("index", message=f"참조 음성 등록 실패: {error}"))
        finally:
            if temp_path.exists():
                temp_path.unlink()

        return redirect(url_for("index", message=f"참조 음성 등록 완료: {stored_path.name}"))

    @app.post("/generate")
    def generate_audio():
        profile = resolve_profile_name(request.form)
        text = request.form.get("text", "").strip()
        output_name = request.form.get("output_name", "sample.wav").strip() or "sample.wav"
        use_rvc = request.form.get("use_rvc") == "1"

        if not profile or not text:
            return redirect(url_for("index", message="프로필과 텍스트를 입력하세요."))

        output_path = pipeline.paths.outputs_dir / output_name

        try:
            if use_rvc and pipeline.settings.rvc.enabled:
                result_path = pipeline.clone(profile_name=profile, text=text, output_path=output_path)
            else:
                result_path = pipeline.synthesize(profile_name=profile, text=text, output_path=output_path)
        except Exception as error:
            return redirect(url_for("index", message=f"실행 실패: {error}"))

        return redirect(
            url_for(
                "index",
                message=f"생성 완료: {result_path.name}",
                latest_output=result_path.name,
            )
        )

    return app
