#!/usr/bin/env python3

import argparse
from pathlib import Path

from voice_clone_studio.pipeline import VoiceClonePipeline


def build_parser():
    parser = argparse.ArgumentParser(
        description="XTTS + RVC 기반 로컬 음성 클론 프로젝트 뼈대"
    )
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parent,
        type=Path,
        help="프로젝트 루트 경로",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    add_reference = subparsers.add_parser(
        "add-reference",
        help="참조 음성 파일을 프로필 폴더로 복사",
    )
    add_reference.add_argument("--profile", required=True, help="프로필 이름")
    add_reference.add_argument("--source", required=True, type=Path, help="원본 음성 파일")

    synthesize = subparsers.add_parser(
        "synthesize",
        help="XTTS로 음성을 생성",
    )
    synthesize.add_argument("--profile", required=True, help="프로필 이름")
    synthesize.add_argument("--text", required=True, help="읽을 텍스트")
    synthesize.add_argument("--output", required=True, type=Path, help="출력 파일")

    convert = subparsers.add_parser(
        "convert",
        help="기존 음성을 RVC로 후처리",
    )
    convert.add_argument("--source", required=True, type=Path, help="입력 음성 파일")
    convert.add_argument("--output", required=True, type=Path, help="출력 파일")

    clone = subparsers.add_parser(
        "clone",
        help="XTTS 생성 뒤 필요하면 RVC까지 적용",
    )
    clone.add_argument("--profile", required=True, help="프로필 이름")
    clone.add_argument("--text", required=True, help="읽을 텍스트")
    clone.add_argument("--output", required=True, type=Path, help="최종 출력 파일")

    accept_coqui_tos = subparsers.add_parser(
        "accept-coqui-tos",
        help="Coqui XTTS 약관 동의를 프로젝트 설정에 저장",
    )
    accept_coqui_tos.add_argument(
        "--i-understand",
        action="store_true",
        help="상업 라이선스 구매 또는 비상업 CPML 동의를 직접 확인했음을 표시",
    )

    serve_web = subparsers.add_parser(
        "serve-web",
        help="간단한 로컬 웹 UI 실행",
    )
    serve_web.add_argument("--host", default="127.0.0.1", help="바인드 호스트")
    serve_web.add_argument("--port", default=5000, type=int, help="바인드 포트")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    pipeline = VoiceClonePipeline(project_root=args.root)

    if args.command == "add-reference":
        stored_path = pipeline.add_reference(profile_name=args.profile, source_path=args.source)
        print(f"참조 음성 등록: {stored_path}")
        return

    if args.command == "synthesize":
        output_path = pipeline.synthesize(
            profile_name=args.profile,
            text=args.text,
            output_path=args.output,
        )
        print(f"XTTS 출력: {output_path}")
        return

    if args.command == "convert":
        output_path = pipeline.convert_with_rvc(
            source_path=args.source,
            output_path=args.output,
        )
        print(f"RVC 출력: {output_path}")
        return

    if args.command == "clone":
        output_path = pipeline.clone(
            profile_name=args.profile,
            text=args.text,
            output_path=args.output,
        )
        print(f"최종 출력: {output_path}")
        return

    if args.command == "accept-coqui-tos":
        if not args.i_understand:
            parser.error(
                "`accept-coqui-tos`는 `--i-understand` 플래그와 함께 실행해야 합니다."
            )
        marker_path = pipeline.accept_coqui_tos()
        print(f"Coqui XTTS 약관 동의 저장: {marker_path}")
        return

    if args.command == "serve-web":
        from voice_clone_studio.web_app import create_app

        app = create_app(project_root=args.root)
        app.run(host=args.host, port=args.port, debug=False)
        return

    parser.error("지원하지 않는 명령입니다.")


if __name__ == "__main__":
    main()
