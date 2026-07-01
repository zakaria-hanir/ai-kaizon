"""
أداة الطرفية (Terminal Tool)
تنفّذ أوامر shell داخل مجلد المستودع فقط، بعد فحصها ضد قائمة حظر صريحة
(انظر config.FORBIDDEN_COMMAND_PATTERNS)، ومع مهلة زمنية لمنع التعليق اللانهائي.
"""
import subprocess

import config
from safety import validator


def run_command(command: str, timeout: int | None = None) -> dict:
    timeout = timeout or config.TERMINAL_TIMEOUT_SECONDS
    try:
        validator.validate_command(command)
    except validator.SafetyViolation as e:
        return {"ok": False, "error": str(e)}

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=config.REPO_PATH,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-8000:],
            "stderr": result.stderr[-4000:],
        }
        validator.log_action({
            "action": "run_command",
            "command": command,
            "returncode": result.returncode,
        })
        return output
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"انتهت المهلة الزمنية ({timeout}s) للأمر: {command}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def install_package(package_name: str, manager: str = "pip") -> dict:
    """يضيف مكتبة جديدة (pip أو npm) — يمر عبر نفس فحوصات run_command"""
    if manager == "pip":
        cmd = f"pip install --quiet {package_name}"
    elif manager == "npm":
        cmd = f"npm install --silent {package_name}"
    else:
        return {"ok": False, "error": f"مدير حزم غير مدعوم: {manager}"}
    result = run_command(cmd, timeout=180)

    # إن نجح تثبيت باكج بايثون، نحدّث requirements.txt تلقائياً
    if result.get("ok") and manager == "pip":
        run_command(f"pip freeze | grep -i '^{package_name.split('==')[0]}' >> requirements.txt", timeout=30)
    return result
