"""
وعي الوكيل ببيئته (Environment Awareness)
يبني ملخصاً عن حالة المستودع والنظام قبل كل دورة تفكير،
كي يتخذ الوكيل قرارات مبنية على واقع البيئة لا افتراضات.
"""
import os
import sys
import platform
import subprocess

import config


def _run(cmd: str) -> str:
    try:
        r = subprocess.run(cmd, shell=True, cwd=config.REPO_PATH,
                            capture_output=True, text=True, timeout=15)
        return (r.stdout or r.stderr).strip()
    except Exception as e:
        return f"<error: {e}>"


def get_environment_snapshot() -> str:
    py_version = sys.version.split()[0]
    os_info = f"{platform.system()} {platform.release()}"
    git_status = _run("git status --short") or "(لا توجد تغييرات غير مثبتة)"
    git_log = _run("git log --oneline -5") or "(لا يوجد تاريخ commits)"
    branch = _run("git rev-parse --abbrev-ref HEAD") or "unknown"

    top_files = []
    for root, dirs, files in os.walk(config.REPO_PATH):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv")]
        depth = root[len(config.REPO_PATH):].count(os.sep)
        if depth >= 2:
            dirs[:] = []
            continue
        for f in files:
            top_files.append(os.path.relpath(os.path.join(root, f), config.REPO_PATH))

    installed_pkgs = _run("pip list --format=freeze 2>/dev/null | head -30")

    snapshot = f"""
=== بيئة الوكيل الحالية ===
نظام التشغيل: {os_info}
إصدار بايثون: {py_version}
الفرع الحالي (git branch): {branch}
مسار المستودع: {config.REPO_PATH}

--- حالة git ---
{git_status}

--- آخر 5 commits ---
{git_log}

--- شجرة الملفات (أول مستويين) ---
{chr(10).join(top_files[:100])}

--- الحزم المثبتة (عيّنة) ---
{installed_pkgs}
""".strip()
    return snapshot
