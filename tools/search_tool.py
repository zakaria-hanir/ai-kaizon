"""
أداة البحث (Search Tool) — بدون أي API خارجي
تبحث نصياً/بتعابير منتظمة داخل ملفات المستودع فقط (بحث محلي بحت).
"""
import os
import re

import config
from safety import validator

BINARY_LIKE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".pyc", ".exe", ".bin"}


def search_code(query: str, relative_dir: str = ".", regex: bool = False,
                 max_results: int = 100, case_sensitive: bool = False) -> dict:
    """
    يبحث عن نص أو تعبير منتظم داخل جميع الملفات النصية ضمن relative_dir.
    يعيد قائمة نتائج بصيغة {file, line_number, line_text}.
    """
    try:
        abs_dir = validator._abs_repo_path(relative_dir)
    except validator.SafetyViolation as e:
        return {"ok": False, "error": str(e)}

    if not os.path.isdir(abs_dir):
        return {"ok": False, "error": f"ليس مجلداً: {relative_dir}"}

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query if regex else re.escape(query), flags)
    except re.error as e:
        return {"ok": False, "error": f"تعبير منتظم غير صالح: {e}"}

    results = []
    for root, dirs, files in os.walk(abs_dir):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv")]
        for name in files:
            _, ext = os.path.splitext(name)
            if ext in BINARY_LIKE_EXT:
                continue
            full = os.path.join(root, name)
            rel = os.path.relpath(full, config.REPO_PATH)
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, start=1):
                        if pattern.search(line):
                            results.append({
                                "file": rel,
                                "line_number": i,
                                "line_text": line.strip()[:300],
                            })
                            if len(results) >= max_results:
                                return {"ok": True, "results": results, "truncated": True}
            except (UnicodeDecodeError, PermissionError):
                continue

    return {"ok": True, "results": results, "truncated": False}


def find_files_by_name(pattern: str, relative_dir: str = ".") -> dict:
    """يبحث عن ملفات بأسماء تطابق نمطاً (glob-like بسيط عبر regex)"""
    try:
        abs_dir = validator._abs_repo_path(relative_dir)
    except validator.SafetyViolation as e:
        return {"ok": False, "error": str(e)}

    regex = re.compile(pattern.replace(".", r"\.").replace("*", ".*"), re.IGNORECASE)
    matches = []
    for root, dirs, files in os.walk(abs_dir):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv")]
        for name in files:
            if regex.search(name):
                full = os.path.join(root, name)
                matches.append(os.path.relpath(full, config.REPO_PATH))
    return {"ok": True, "files": matches[:500]}
