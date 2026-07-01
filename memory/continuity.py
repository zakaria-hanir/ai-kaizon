"""
الذاكرة التراكمية (Continuity Memory)
======================================
هذا ما يجعل الوكيل "حقيقياً" لا مجرد سكربت يعيد نفسه كل يوم:
كل دورة تبدأ بقراءة فعلية لِما حدث سابقاً (history.json) ولخطة العمل (PLAN.md)،
وتُحقن في الرسالة الأولى للنموذج، فيبني على ما فعله لا أن يبدأ من صفر.
"""
import json
import os

import config

PLAN_PATH = os.path.join(config.REPO_PATH, "PLAN.md")

DEFAULT_PLAN = """# خطة تطور المستودع

## الهدف العام (يُحدَّث يدوياً من قِبل المطوّر إن رغب)
تحسين جودة الكود، رفع تغطية الاختبارات، وتحسين التوثيق تدريجياً.

## هذا الأسبوع
- (لم يُحدَّد بعد — سيقوم الوكيل بتحديثه في أول دورة)

## منجز
- (لا شيء بعد)

## ملاحظات وقرارات سابقة مهمة
- (لا شيء بعد)
"""


def load_plan() -> str:
    if not os.path.exists(PLAN_PATH):
        with open(PLAN_PATH, "w", encoding="utf-8") as f:
            f.write(DEFAULT_PLAN)
        return DEFAULT_PLAN
    with open(PLAN_PATH, "r", encoding="utf-8") as f:
        return f.read()


def load_recent_history(n: int = 15) -> list[dict]:
    if not os.path.exists(config.MEMORY_FILE):
        return []
    try:
        with open(config.MEMORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []
    return history[-n:]


def summarize_recent_history(n: int = 15) -> str:
    """يبني ملخصاً نصياً مختصراً لآخر n حدث، ليُحقن في الـ prompt بدون إغراق السياق"""
    events = load_recent_history(n)
    if not events:
        return "(لا يوجد تاريخ سابق — هذه أول دورة للوكيل)"

    lines = []
    for e in events:
        action = e.get("action", "?")
        if action == "git_commit":
            lines.append(f"✅ commit: {e.get('message', '')}")
        elif action == "git_commit_blocked":
            lines.append(f"⛔ رُفض commit '{e.get('message', '')}' بسبب فشل الاختبارات")
        elif action == "write_file":
            lines.append(f"✏️ تعديل ملف: {e.get('path', '')}")
        elif action == "delete_file":
            lines.append(f"🗑️ حذف ملف: {e.get('path', '')}")
        elif action == "agent_cycle_complete":
            summary = (e.get("summary") or "")[:150]
            lines.append(f"🔁 نهاية دورة سابقة: {summary}")
        elif action == "tool_exception":
            lines.append(f"⚠️ خطأ غير متوقع في أداة {e.get('tool', '')}: {e.get('error', '')[:100]}")
    return "\n".join(lines) if lines else "(لا يوجد تاريخ سابق ذو دلالة)"


def build_continuity_context() -> str:
    plan = load_plan()
    history_summary = summarize_recent_history()
    return f"""=== خطة العمل الحالية (PLAN.md) ===
{plan}

=== ملخص آخر الأحداث الفعلية من الدورات السابقة ===
{history_summary}

تعليمات: راجع الخطة والتاريخ أعلاه أولاً. لا تكرر عملاً أُنجز فعلاً. إن كانت الخطة فارغة أو منتهية،
حدّثها الآن عبر file_op(action="write", path="PLAN.md", content=...) بخطوات أسبوعية واقعية قبل أن تنفذ أي شيء آخر.
بعد إنجاز أي بند من الخطة، عدّل PLAN.md لتحريكه إلى قسم "منجز"."""
