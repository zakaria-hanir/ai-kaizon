#!/usr/bin/env python3
"""
مراجعة معمارية أسبوعية (Architect Review)
============================================
تختلف عن دورة الوكيل اليومية في شيء جوهري: السياق هنا أوسع بكثير.
الدورة اليومية تقرأ آخر 15 حدث فقط. هذه المراجعة تقرأ آخر 100 حدث كامل،
كل المشاكل المفتوحة والمغلقة، وكل التقارير الأسبوعية السابقة — وتُنتج
إعادة صياغة نقدية لـ PLAN.md، بدل أن يترك التخطيط يتراكم عشوائياً يوماً بيوم.

الفرق عن الدورة اليومية:
  - لا تنفّذ أي كود أو تعديل مباشر — فقط تعيد كتابة PLAN.md و PROBLEMS.md بعد نقد شامل.
  - تُشغَّل أسبوعياً فقط (سياق أوسع = تكلفة أعلى بالـ tokens، لا معنى لتشغيلها يومياً).
"""
import json
import os

from groq import Groq

import config
from memory import continuity, problems as problems_registry
from safety import validator


ARCHITECT_SYSTEM_PROMPT = """أنت "المهندس المعماري" لهذا المستودع — مراجعة أسبوعية نقدية، لست منفذاً.
مهمتك مختلفة عن الوكيل اليومي: هو ينفّذ خطوة بخطوة، أنت تراجع الصورة الكاملة وتنقدها.

اقرأ كل ما يُرفق (تاريخ موسّع، كل المشاكل المفتوحة والمغلقة) واسأل نفسك بصدق:
- هل الوكيل اليومي يدور حول نفسه (نفس نوع التعديلات تتكرر بلا تقدم حقيقي)؟
- هل هناك مشكلة مفتوحة منذ أكثر من أسبوعين بلا تقدم فعلي؟ لماذا؟ هل المقاربة نفسها خاطئة؟
- هل PLAN.md الحالي واقعي، أم فيه بنود مؤجلة باستمرار يجب حذفها أو إعادة صياغتها بشكل أصغر؟
- هل هناك قرار معماري أكبر (إعادة هيكلة، تغيير مكتبة، حذف كود ميت) لم يقترحه أحد لأن الدورات
  اليومية مصممة لخطوات صغيرة فقط؟

أخرج بصيغة Markdown نظيفة تصلح لتكون محتوى PLAN.md جديداً بالكامل، بالأقسام:
## الهدف العام
## أولويات هذا الأسبوع (3-5 بنود واقعية فقط، لا أكثر)
## قرارات معمارية يجب مراجعتها بشرياً (إن وُجدت)
## ملاحظات نقدية على أداء الأسابيع الماضية
"""


def _load_recent_history(n: int = 100) -> str:
    if not os.path.exists(config.MEMORY_FILE):
        return "(لا يوجد سجل بعد)"
    with open(config.MEMORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    recent = history[-n:]
    lines = []
    for e in recent:
        a = e.get("action", "?")
        if a == "git_commit":
            lines.append(f"commit: {e.get('message', '')}")
        elif a == "git_commit_blocked":
            lines.append(f"commit مرفوض: {e.get('message', '')} — {e.get('reason', '')}")
        elif a == "agent_cycle_complete":
            lines.append(f"ملخص دورة: {(e.get('summary') or '')[:200]}")
    return "\n".join(lines) if lines else "(لا يوجد أحداث ذات دلالة)"


def run_architect_review() -> str:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY غير مضبوط.")

    client = Groq(api_key=config.GROQ_API_KEY)

    history_wide = _load_recent_history(100)
    current_plan = continuity.load_plan()
    problems_md = problems_registry.load_problems_markdown()
    open_problems_summary = problems_registry.summarize_open_problems()

    prompt = f"""=== الخطة الحالية (PLAN.md) ===
{current_plan}

=== سجل المشاكل (PROBLEMS.md) ===
{problems_md}

=== ملخص المشاكل المفتوحة مع عدد المحاولات ===
{open_problems_summary}

=== آخر 100 حدث فعلي من كل الدورات اليومية الماضية ===
{history_wide}
"""

    messages = [
        {"role": "system", "content": ARCHITECT_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    response = client.chat.completions.create(
        model=config.MODEL_NAME,
        messages=messages,
        max_tokens=config.MAX_TOKENS,
        temperature=0.3,
    )
    new_plan = response.choices[0].message.content or ""

    # كتابة مباشرة (بلا أدوات وسيطة) لأن هذا سكربت مراجعة منفصل، ليس جزءاً من حلقة tool-calling
    with open(continuity.PLAN_PATH, "w", encoding="utf-8") as f:
        f.write(new_plan)

    validator.log_action({"action": "architect_review", "new_plan_excerpt": new_plan[:1000]})
    return new_plan


if __name__ == "__main__":
    result = run_architect_review()
    print("✅ تم تحديث PLAN.md بناءً على مراجعة معمارية أسبوعية:\n")
    print(result)
                                       
