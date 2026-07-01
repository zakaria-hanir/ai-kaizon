"""
سجل المشاكل طويلة المدى (Problem Registry)
=============================================
الفرق بين هذا و PLAN.md:
  - PLAN.md = مهام قصيرة قابلة للإنجاز في دورة أو أسبوع
  - PROBLEMS.md = مشاكل قد تحتاج أسابيع، تُتابع بمحاولات متعددة، ولها تاريخ فشل/نجاح يجب تذكّره

بدون هذا الملف، أي مشكلة صعبة تُنسى بمجرد خروجها من نافذة "آخر 15 حدث" في الذاكرة القصيرة.
"""
import json
import os
from datetime import datetime

import config

PROBLEMS_PATH = os.path.join(config.REPO_PATH, "PROBLEMS.md")
PROBLEMS_JSON = os.path.join(config.REPO_PATH, "memory", "problems.json")

DEFAULT_PROBLEMS_MD = """# سجل المشاكل طويلة المدى

هذا الملف يُدار آلياً جزئياً من الوكيل. كل مشكلة تبقى مفتوحة هنا حتى تُحل فعلياً
(تُختبر وتُغلق)، بغض النظر عن عدد الدورات التي تمر.

## مشاكل مفتوحة
(لا يوجد بعد)

## مشاكل مغلقة (تم حلها والتحقق منها)
(لا يوجد بعد)
"""


def _load_json() -> list[dict]:
    if not os.path.exists(PROBLEMS_JSON):
        return []
    try:
        with open(PROBLEMS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save_json(problems: list[dict]) -> None:
    os.makedirs(os.path.dirname(PROBLEMS_JSON), exist_ok=True)
    with open(PROBLEMS_JSON, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)


def load_problems_markdown() -> str:
    if not os.path.exists(PROBLEMS_PATH):
        with open(PROBLEMS_PATH, "w", encoding="utf-8") as f:
            f.write(DEFAULT_PROBLEMS_MD)
        return DEFAULT_PROBLEMS_MD
    with open(PROBLEMS_PATH, "r", encoding="utf-8") as f:
        return f.read()


def register_attempt(problem_id: str, title: str, description: str,
                      attempt_summary: str, outcome: str) -> dict:
    """
    يسجل محاولة حل لمشكلة (سواء نجحت أو فشلت) في سجل منظم (JSON) يبقى دقيقاً،
    بينما PROBLEMS.md (نص حر) يبقى بيد الوكيل ليكتب فيه ملخصاً مقروءاً للبشر.
    outcome: 'attempted' | 'resolved' | 'blocked'
    """
    problems = _load_json()
    existing = next((p for p in problems if p["id"] == problem_id), None)
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "summary": attempt_summary,
        "outcome": outcome,
    }
    if existing:
        existing["attempts"].append(entry)
        existing["status"] = "resolved" if outcome == "resolved" else existing["status"]
    else:
        problems.append({
            "id": problem_id,
            "title": title,
            "description": description,
            "status": "resolved" if outcome == "resolved" else "open",
            "attempts": [entry],
        })
    _save_json(problems)
    return {"ok": True, "problem_id": problem_id, "total_attempts":
            len(next(p for p in problems if p["id"] == problem_id)["attempts"])}


def get_problem_history(problem_id: str) -> dict:
    """يعيد كل محاولات حل مشكلة معينة سابقاً — كي لا يكرر الوكيل نفس المحاولة الفاشلة"""
    problems = _load_json()
    match = next((p for p in problems if p["id"] == problem_id), None)
    if not match:
        return {"ok": True, "found": False}
    return {"ok": True, "found": True, "problem": match}


def summarize_open_problems() -> str:
    problems = _load_json()
    open_problems = [p for p in problems if p.get("status") == "open"]
    if not open_problems:
        return "(لا توجد مشاكل مفتوحة مسجّلة في memory/problems.json حالياً)"

    lines = []
    for p in open_problems:
        attempts = p.get("attempts", [])
        lines.append(f"- [{p['id']}] {p['title']} — {len(attempts)} محاولة سابقة")
        for a in attempts[-3:]:
            lines.append(f"    · ({a['outcome']}) {a['summary'][:150]}")
    return "\n".join(lines)
