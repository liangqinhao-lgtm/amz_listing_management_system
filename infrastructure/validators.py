"""输入验证"""
from pathlib import Path
from infrastructure.exceptions import ValidationException

def validate_file_path(file_path: str) -> str:
    path = Path(file_path.strip())
    if not path.exists():
        raise ValidationException(f"文件不存在: {file_path}")
    if not path.is_file():
        raise ValidationException(f"不是文件: {file_path}")
    if path.suffix.lower() not in {".txt", ".csv", ".tsv"}:
        raise ValidationException(f"不支持的格式: {path.suffix}")
    return str(path.absolute())
