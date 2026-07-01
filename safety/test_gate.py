"""
بوّابة الاختبار الحقيقية (Real Test Gate)
==========================================
هذا ليس اقتراحاً في system prompt يمكن للنموذج تجاهله — بل فحص برمجي فعلي
يُستدعى تلقائياً من داخل file_tool.git_commit() قبل أي commit.
إن فشلت الاختبارات، يُرفض الـ commit برمجياً بغض النظر عمّا يريده النموذج.
"""
import os
import subprocess

import config


def _has_pytest_tests(repo_path: str) -> bool:
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv")]
        for f in files:
            if f.startswith("test_") and f.endswith(".py"):
                return True
            if f.endswith("_test.py"):
                return True
    return False


def _has_npm_test(repo_path: str) -> bool:
    pkg = os.path.join(repo_path, "package.json")
    if not os.path.exists(pkg):
        return False
    try:
        import json
        with open(pkg, "r", encoding="utf-8") as f:
            data = json.load(f)
        return "test" in data.get("scripts", {})
    except Exception:
        return False


def _changed_python_files() -> list[str]:
    """يعيد قائمة ملفات .py المعدّلة/الجديدة حسب git diff (staged + unstaged)"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=config.REPO_PATH, capture_output=True, text=True, timeout=15
        )
        result2 = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            cwd=config.REPO_PATH, capture_output=True, text=True, timeout=15
        )
        files = set(result.stdout.splitlines()) | set(result2.stdout.splitlines())
        return [f for f in files if f.endswith(".py")]
    except Exception:
        return []


def detect_and_run_tests() -> dict:
    """
    يكتشف تلقائياً وجود اختبارات (pytest أو npm test) ويشغّلها فعلياً.

    القرار:
      - إن وُجدت اختبارات ونجحت -> ok=True, ran=True
      - إن وُجدت اختبارات وفشلت -> ok=False, ran=True  (يمنع الـ commit)
      - إن لم توجد اختبارات إطلاقاً -> نفحص على الأقل أن كل ملفات .py المعدّلة
        صحيحة الصياغة عبر py_compile (خط دفاع أخير، وليس بديلاً حقيقياً عن الاختبارات)
    """
    repo = config.REPO_PATH

    if _has_pytest_tests(repo):
        try:
            r = subprocess.run(
                ["python", "-m", "pytest", "-q", "--timeout=120"],
                cwd=repo, capture_output=True, text=True, timeout=180
            )
            return {
                "ok": r.returncode == 0,
                "ran": True,
                "runner": "pytest",
                "output": (r.stdout + r.stderr)[-4000:],
            }
        except FileNotFoundError:
            # pytest غير مثبت أصلاً كأداة، نعتبرها اختبارات لم تُشغَّل ونحذّر بوضوح
            return {"ok": False, "ran": False, "runner": "pytest",
                    "output": "توجد ملفات اختبار لكن pytest غير مثبت. ثبّته أولاً (pip install pytest)."}
        except subprocess.TimeoutExpired:
            return {"ok": False, "ran": True, "runner": "pytest", "output": "انتهت المهلة الزمنية للاختبارات."}

    if _has_npm_test(repo):
        try:
            r = subprocess.run(["npm", "test", "--silent"], cwd=repo,
                                capture_output=True, text=True, timeout=180)
            return {"ok": r.returncode == 0, "ran": True, "runner": "npm",
                    "output": (r.stdout + r.stderr)[-4000:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "ran": True, "runner": "npm", "output": "انتهت المهلة الزمنية للاختبارات."}

    # لا توجد أي اختبارات في المستودع أصلاً — خط دفاع أخير: تحقق صياغي فقط
    changed = _changed_python_files()
    if not changed:
        return {"ok": True, "ran": False, "runner": "none",
                "output": "لا توجد اختبارات ولا ملفات بايثون معدّلة."}

    failures = []
    for f in changed:
        full = os.path.join(repo, f)
        if not os.path.exists(full):
            continue
        r = subprocess.run(["python", "-m", "py_compile", full],
                            capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            failures.append(f"{f}: {r.stderr.strip()}")

    return {
        "ok": len(failures) == 0,
        "ran": False,
        "runner": "py_compile_fallback",
        "output": "لا توجد اختبارات في المستودع بعد (يُنصح الوكيل بإضافتها). "
                  f"فحص صياغي فقط على {len(changed)} ملف معدّل.\n" + "\n".join(failures),
    }
