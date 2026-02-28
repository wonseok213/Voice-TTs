#!/usr/bin/env python3

import argparse
import shutil
from pathlib import Path


def build_parser():
    parser = argparse.ArgumentParser(
        description="RVC 자리 표시자 CLI. 입력 파일을 그대로 복사합니다."
    )
    parser.add_argument("--input", required=True, type=Path, help="입력 음성 파일")
    parser.add_argument("--output", required=True, type=Path, help="출력 음성 파일")
    parser.add_argument("--model", default="", help="호환용 인자")
    parser.add_argument("--index", default="", help="호환용 인자")
    return parser


def main():
    args = build_parser().parse_args()
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()

    if not source.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)
    print(f"RVC passthrough: {source} -> {output}")


if __name__ == "__main__":
    main()
