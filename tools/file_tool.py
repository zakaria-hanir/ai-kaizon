"""
أداة الملفات (File Tool)
تسمح للوكيل بقراءة/كتابة/حذف/سرد الملفات داخل المستودع فقط،
مع تطبيق فحوصات الأمان (validator.py) قبل أي عملية كتابة أو حذف.
"""
import os
import subprocess

import config
from safety import validator, test_gate


def list_files(relative_dir: str = ".") -> dict:
    """يسرد الملفات والمجلدات داخل مسار معيّن من المستودع"""
    try:
        abs_dir = validator._abs_repo_path(relative_dir)
        if not os.path.isdir(abs_dir):
            return {"ok": False, "error": f"ليس مجلداً: {relative_dir}"}

        entries = []
        for root, dirs, files in os.walk(abs_dir):
            # تجاهل مجلدات النظام الثقيلة
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv")]
            for name in files:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, config.REPO_PATH)
                entries.append(rel)
        return {"ok": True, "files": sorted(entries)[:2000]}
    except validator.SafetyViolation as e:
        return {"ok": False, "error": str(e)}


def read_file(relative_path: str) -> dict:
    try:
        abs_path = validator._abs_repo_path(relative_path)
        if not os.path.isfile(abs_path):
            return {"ok": False, "error": f"الملف غير موجود: {relative_path}"}
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {"ok": True, "content": content}
    except validator.SafetyViolation as e:
        return {"ok": False, "error": str(e)}


def write_file(relative_path: str, content: str, allow_protected: bool = False) -> dict:
    """
    يكتب/يعدّل ملفاً بعد التحقق الأمني الكامل:
      1) الملف ضمن حدود المستودع
      2) المسار غير محمي (إلا بإذن صريح)
      3) الامتداد مسموح
      4) صيغة بايثون/JSON صحيحة إن انطبق
      5) نسخة احتياطية تُؤخذ أولاً
    """
    try:
        abs_path = validator.validate_write(relative_path, content, allow_protected)
        backup_path = validator.backup_file(relative_path)

        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

        validator.log_action({
            "action": "write_file",
            "path": relative_path,
            "backup": backup_path,
        })
        return {"ok": True, "path": relative_path, "backup": backup_path}
    except validator.SafetyViolation as e:
        return {"ok": False, "error": str(e)}


def delete_file(relative_path: str, allow_protected: bool = False) -> dict:
    try:
        if not allow_protected and validator.is_protected(relative_path):
            return {"ok": False, "error": f"المسار محمي: {relative_path}"}

        abs_path = validator._abs_repo_path(relative_path)
        if not os.path.isfile(abs_path):
            return {"ok": False, "error": f"الملف غير موجود: {relative_path}"}

        backup_path = validator.backup_file(relative_path)
        os.remove(abs_path)

        validator.log_action({
            "action": "delete_file",
            "path": relative_path,
            "backup": backup_path,
        })
        return {"ok": True, "path": relative_path, "backup": backup_path}
    except validator.SafetyViolation as e:
        return {"ok": False, "error": str(e)}


def rollback_file(relative_path: str, backup_path: str) -> dict:
    try:
        validator.rollback(relative_path, backup_path)
        return {"ok": True, "path": relative_path}
    except validator.SafetyViolation as e:
        return {"ok": False, "error": str(e)}


def git_commit(message: str, skip_tests: bool = False) -> dict:
    """
    يلتزم (commit) بكل التغييرات مباشرة في المستودع الحالي (بدون فرع/PR).

    بوّابة حقيقية: قبل أي commit، تُشغَّل الاختبارات فعلياً عبر safety.test_gate.
    إن فشلت، يُرفض الـ commit برمجياً بغض النظر عمّا "يريده" النموذج —
    هذا ليس تعليمة في system prompt يمكن تجاهلها، بل فحص كود فعلي.
    skip_tests=True مخصص فقط لحالات استثنائية (مثل commit توثيقي بحت) ويُسجَّل صراحة في السجل.
    """
    try:
        subprocess.run(["git", "add", "-A"], cwd=config.REPO_PATH, check=True,
                        capture_output=True, text=True)

        test_result = {"ok": True, "ran": False, "runner": "skipped"}
        if not skip_tests:
            test_result = test_gate.detect_and_run_tests()

        if not test_result["ok"]:
            # نتراجع عن git add حتى لا تبقى التغييرات في منطقة staging بلا التزام
            subprocess.run(["git", "reset"], cwd=config.REPO_PATH, capture_output=True, text=True)
            validator.log_action({
                "action": "git_commit_blocked",
                "message": message,
                "reason": "فشلت الاختبارات",
                "test_output": test_result.get("output", "")[:2000],
            })
            return {
                "ok": False,
                "error": "تم رفض الـ commit: فشلت الاختبارات فعلياً. لن تُطبَّق أي تغييرات.",
                "test_runner": test_result.get("runner"),
                "test_output": test_result.get("output", "")[:2000],
            }

        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=config.REPO_PATH, capture_output=True, text=True
        )
        validator.log_action({
            "action": "git_commit", "message": message,
            "stdout": result.stdout, "stderr": result.stderr,
            "test_runner": test_result.get("runner"), "tests_ran": test_result.get("ran"),
        })
        return {"ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr,
                "tests": test_result}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": str(e), "stderr": e.stderr}
