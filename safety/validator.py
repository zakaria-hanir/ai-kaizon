"""
طبقة الأمان (Safety Layer)
مسؤولة عن:
  - منع الوكيل من الخروج عن حدود المستودع (path traversal)
  - منع تعديل المسارات المحمية دون علامة "يحتاج مراجعة بشرية"
  - التحقق من صحة صيغة ملفات بايثون قبل حفظها (ast.parse)
  - أخذ نسخة احتياطية قبل أي تعديل/حذف، مع إمكانية التراجع (rollback)
  - فحص أوامر الطرفية ضد قائمة حظر صريحة قبل التنفيذ
"""
import os
import re
import ast
import json
import shutil
import time
from datetime import datetime

import config


class SafetyViolation(Exception):
    """يُرفع عند اكتشاف عملية غير آمنة"""
    pass


def _abs_repo_path(relative_path: str) -> str:
    """يحوّل مساراً نسبياً إلى مطلق ويتأكد أنه داخل حدود المستودع فقط"""
    repo_root = os.path.abspath(config.REPO_PATH)
    target = os.path.abspath(os.path.join(repo_root, relative_path))
    if not target.startswith(repo_root + os.sep) and target != repo_root:
        raise SafetyViolation(
            f"محاولة وصول خارج حدود المستودع مرفوضة: {relative_path}"
        )
    return target


def is_protected(relative_path: str) -> bool:
    norm = relative_path.replace("\\", "/").lstrip("/")
    for p in config.PROTECTED_PATHS:
        if norm.startswith(p.rstrip("/")):
            return True
    return False


def check_extension_allowed(relative_path: str) -> bool:
    _, ext = os.path.splitext(relative_path)
    if ext == "":
        return True  # ملفات بدون امتداد (مثل LICENSE) مسموحة
    return ext in config.ALLOWED_EXTENSIONS


def validate_python_syntax(content: str, filename: str = "<agent_write>") -> None:
    """يتحقق من صحة صيغة بايثون قبل الحفظ. يرفع SafetyViolation عند خطأ."""
    try:
        ast.parse(content, filename=filename)
    except SyntaxError as e:
        raise SafetyViolation(f"خطأ صياغي (SyntaxError) في {filename}: {e}")


def validate_write(relative_path: str, content: str, allow_protected: bool = False) -> str:
    """
    يجري كل فحوصات الأمان قبل كتابة ملف.
    يعيد المسار المطلق إذا نجح الفحص، وإلا يرفع SafetyViolation.
    """
    if not allow_protected and is_protected(relative_path):
        raise SafetyViolation(
            f"المسار '{relative_path}' محمي ويتطلب مراجعة بشرية صريحة "
            f"(مرر allow_protected=True عن قصد إن كنت متأكداً)."
        )

    if not check_extension_allowed(relative_path):
        raise SafetyViolation(f"امتداد الملف غير مسموح به: {relative_path}")

    abs_path = _abs_repo_path(relative_path)

    if relative_path.endswith(".py"):
        validate_python_syntax(content, filename=relative_path)

    if relative_path.endswith((".json",)):
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            raise SafetyViolation(f"JSON غير صالح في {relative_path}: {e}")

    return abs_path


def validate_command(command: str) -> None:
    """يفحص أمر الطرفية ضد قائمة الحظر قبل التنفيذ"""
    for pattern in config.FORBIDDEN_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            raise SafetyViolation(f"أمر محظور تم رفضه لأسباب أمنية: {command}")


def backup_file(relative_path: str) -> str | None:
    """يأخذ نسخة احتياطية من الملف قبل تعديله/حذفه. يعيد مسار النسخة أو None إن لم يكن الملف موجوداً."""
    abs_path = _abs_repo_path(relative_path)
    if not os.path.exists(abs_path):
        return None

    os.makedirs(config.BACKUP_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
    safe_name = relative_path.replace("/", "__").replace("\\", "__")
    backup_path = os.path.join(config.BACKUP_DIR, f"{safe_name}.{timestamp}.bak")
    shutil.copy2(abs_path, backup_path)
    return backup_path


def rollback(relative_path: str, backup_path: str) -> None:
    """يستعيد ملفاً من نسخته الاحتياطية"""
    abs_path = _abs_repo_path(relative_path)
    if not os.path.exists(backup_path):
        raise SafetyViolation(f"نسخة احتياطية غير موجودة: {backup_path}")
    shutil.copy2(backup_path, abs_path)


def log_action(action: dict) -> None:
    """يسجل كل عملية في ذاكرة الوكيل ليتعلم منها لاحقاً"""
    os.makedirs(os.path.dirname(config.MEMORY_FILE), exist_ok=True)
    history = []
    if os.path.exists(config.MEMORY_FILE):
        try:
            with open(config.MEMORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            history = []

    action["timestamp"] = time.time()
    history.append(action)
    history = history[-500:]  # نحتفظ بآخر 500 حدث فقط

    with open(config.MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
