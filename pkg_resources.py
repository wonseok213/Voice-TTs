from importlib import import_module
from pathlib import Path


def resource_filename(package_or_requirement, resource_name):
    module = import_module(package_or_requirement)

    if hasattr(module, "__path__"):
        base_path = Path(next(iter(module.__path__)))
    elif hasattr(module, "__file__") and module.__file__:
        base_path = Path(module.__file__).resolve().parent
    else:
        raise ValueError(f"리소스 기준 경로를 찾을 수 없습니다: {package_or_requirement}")

    return str((base_path / resource_name).resolve())
