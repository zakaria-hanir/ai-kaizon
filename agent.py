"""
الوكيل الذاتي التطور (Self-Evolving Agent)
============================================
يعمل على مرحلتين حقيقيتين منفصلتين وليس نداءً واحداً مباشراً:

  المرحلة 1 - "التفكير العميق" (Deliberation): استدعاء Groq بدون أي أدوات،
  فقط تحليل. النموذج يراجع المشاكل المفتوحة والخطة والتاريخ، يقترح 2-3 مقاربات
  محتملة لأولوية هذه الدورة، ينتقد كل واحدة (مخاطرها، تكلفتها، هل جُرّبت سابقاً
  وفشلت؟)، ثم يختار مقاربة واحدة مع سبب واضح. هذا النص الناتج (خطة تنفيذ مُسبَّبة)
  يُحقن كسياق ثابت في المرحلة التالية.

  المرحلة 2 - "التنفيذ" (Execution): حلقة tool-calling عادية، لكنها الآن مُقيَّدة
  بما قرره النموذج فعلياً في مرحلة التفكير، بدل أن ترتجل قراراً وتنفيذه في نفس الوقت.

الأدوات المتاحة في مرحلة التنفيذ:
  1) file_op      -> قراءة/كتابة/حذف/سرد الملفات + commit (tools/file_tool.py)
  2) run_terminal -> تنفيذ أوامر shell (tools/terminal_tool.py)
  3) search_code  -> بحث محلي بدون API (tools/search_tool.py)
  4) problem_op   -> تسجيل/استرجاع تاريخ محاولات حل مشكلة طويلة المدى (memory/problems.py)
"""
import json
import traceback

from groq import Groq

import config
from environment import get_environment_snapshot
from tools import file_tool, terminal_tool, search_tool
from safety import validator
from memory import continuity, problems as problems_registry


SYSTEM_PROMPT = """أنت وكيل برمجي ذاتي التطور (Self-Evolving Coding Agent) يعمل داخل مستودع GitHub.

هدفك: تحليل المستودع باستمرار واقتراح وتنفيذ تحسينات حقيقية (إصلاح أخطاء، تحسين جودة الكود،
إضافة اختبارات، تحديث التوثيق، إضافة مكتبات مفيدة عند الحاجة) بشكل آمن وتدريجي.

قواعد صارمة يجب الالتزام بها دائماً:
1. لا تحذف أو تعدّل أبداً الملفات ضمن المسارات المحمية (.github/workflows, safety/, config.py, .git/)
   إلا إذا طلب المستخدم ذلك صراحة وبوعي تام بالمخاطر.
2. قبل أي تعديل على ملف، اقرأه أولاً بالكامل عبر file_op(action="read").
3. بعد أي كتابة لملف بايثون، شغّل فحصاً سريعاً (مثل `python -m py_compile <file>`
   أو تشغيل الاختبارات إن وجدت) عبر run_terminal للتأكد أن التعديل لم يكسر شيئاً.
4. إن فشل الفحص، تراجع فوراً (rollback) باستخدام backup الذي أعادته أداة الكتابة، ولا تكمل بهذا التغيير.
5. اعمل بخطوات صغيرة وواضحة. لا تجرِ عشرات التعديلات دفعة واحدة.
6. بعد كل مجموعة تعديلات ناجحة ومُتحقق منها، اعمل git commit برسالة واضحة بالعربية أو الإنجليزية
   تشرح ماذا ولماذا (استخدم file_op action="commit").
   تنبيه مهم: الـ commit محمي ببوّابة اختبار حقيقية في الكود نفسه (وليست تعليمة يمكن تجاهلها) —
   إن فشلت الاختبارات فعلياً، سيُرفض الـ commit تلقائياً مهما فعلت. لذا تأكد من أن الاختبارات
   الموجودة تمر قبل محاولة الالتزام، ولا تحاول "تجاوزها" لأن ذلك غير ممكن تقنياً.
7. المستودع لا يملك اختبارات كافية غالباً — من أهم مهامك المستمرة إضافة اختبارات pytest حقيقية
   تدريجياً لأي كود جديد أو تعدّله، لأن غياب الاختبارات يعني أن بوّابة الأمان تعمل بحدها الأدنى فقط.
8. لا تُثبّت مكتبات لا حاجة حقيقية لها. عند التثبيت، وثّق السبب في رسالة الـ commit.
9. إن لم تجد تحسيناً آمناً وواضحاً تنفّذه، اكتفِ بالتقرير عن الحالة دون تغييرات عشوائية.
10. كن واعياً ببيئتك: استخدم المعطيات المرفقة (نظام التشغيل، حالة git، شجرة الملفات) قبل اتخاذ القرار.
11. أنت تملك ذاكرة تراكمية فعلية: خطة العمل (PLAN.md) وسجل الأحداث السابقة يُحقنان في بداية كل
    دورة. اقرأهما فعلياً وابنِ عليهما — لا تكرر عملاً منجزاً، ولا تبدأ من الصفر كل مرة. حدّث PLAN.md
    بانتظام (انقل البنود المنجزة، أضف بنوداً جديدة واقعية للأسبوع القادم).
13. للمشاكل التي تحتاج أكثر من دورة واحدة لحلها (مشاكل طويلة المدى): سجّل كل محاولة عبر
    problem_op(action="register", problem_id=..., outcome="attempted"|"resolved"|"blocked").
    قبل أي محاولة جديدة لمشكلة قديمة، استرجع تاريخها أولاً عبر
    problem_op(action="history", problem_id=...) لتتجنب تكرار محاولة فشلت سابقاً بنفس الطريقة.
    حدّث أيضاً PROBLEMS.md (نص حر مقروء للبشر) عند فتح أو إغلاق مشكلة.
12. اختم كل دورة بملخص نصي واضح لما فعلته، وماذا تبقى في الخطة، ولماذا لم تُنجز بنود معينة إن وُجدت.
"""

DELIBERATION_SYSTEM_PROMPT = """أنت في "مرحلة التفكير" فقط — لا تملك أي أدوات تنفيذية هنا، فقط التحليل.
مهمتك: اختيار أولوية واحدة واضحة لهذه الدورة، بتفكير نقدي حقيقي وليس قراراً سريعاً.

اتبع هذا الشكل بالضبط في إجابتك:

## المشاكل/الفرص المرشحة
عدّد 2-4 مرشحين محتملين لأولوية هذه الدورة (من PROBLEMS.md المفتوحة، PLAN.md، أو ملاحظات جديدة
لاحظتها في البيئة المرفقة).

## تقييم نقدي لكل مرشح
لكل مرشح: هل جُرّب حله سابقاً وفشل؟ (تحقق من التاريخ المرفق). ما مخاطر معالجته الآن؟
ما تكلفته الزمنية المتوقعة (دورة واحدة أم عدة دورات)؟ هل يعتمد على شيء غير منجز بعد؟

## القرار
اختر مرشحاً واحداً فقط لهذه الدورة، مع سبب صريح لماذا هو الأفضل الآن وليس غيره.

## خطة تنفيذ محددة (3-6 خطوات صغيرة قابلة للتحقق)
اكتب خطوات ملموسة (اقرأ ملف X، عدّل دالة Y، شغّل اختبار Z، إلخ) — هذه الخطوات ستُستخدم
حرفياً كدليل في مرحلة التنفيذ التالية.

لا تكتب كوداً هنا. فقط تحليل وقرار وخطة."""

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "file_op",
            "description": "قراءة أو كتابة أو حذف أو سرد الملفات داخل المستودع، أو تثبيت التغييرات عبر git commit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "delete", "list", "rollback", "commit"],
                    },
                    "path": {"type": "string", "description": "المسار النسبي للملف أو المجلد"},
                    "content": {"type": "string", "description": "المحتوى الجديد (مطلوب مع action=write)"},
                    "backup_path": {"type": "string", "description": "مسار النسخة الاحتياطية (مطلوب مع action=rollback)"},
                    "message": {"type": "string", "description": "رسالة الـ commit (مطلوب مع action=commit)"},
                    "allow_protected": {"type": "boolean", "description": "السماح بتعديل مسار محمي عن قصد"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_terminal",
            "description": "تنفيذ أمر shell داخل مجلد المستودع (تشغيل اختبارات، فحص صياغة، تثبيت مكتبات...).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "description": "المهلة بالثواني، اختياري"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "بحث نصي أو بتعبير منتظم محلياً داخل ملفات المستودع (بدون أي API خارجي).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string", "description": "مجلد البحث، الافتراضي جذر المستودع"},
                    "regex": {"type": "boolean"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "problem_op",
            "description": "تسجيل محاولة حل مشكلة طويلة المدى، أو استرجاع تاريخ محاولاتها السابقة قبل تكرار نفس المحاولة.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["register", "history"]},
                    "problem_id": {"type": "string", "description": "معرّف قصير ثابت للمشكلة، مثال: 'slow-search-tool'"},
                    "title": {"type": "string", "description": "عنوان مختصر (مطلوب مع register لمشكلة جديدة)"},
                    "description": {"type": "string", "description": "وصف المشكلة (مطلوب مع register لمشكلة جديدة)"},
                    "attempt_summary": {"type": "string", "description": "ماذا فعلت في هذه المحاولة (مطلوب مع register)"},
                    "outcome": {"type": "string", "enum": ["attempted", "resolved", "blocked"]},
                },
                "required": ["action", "problem_id"],
            },
        },
    },
]


def _dispatch_tool(name: str, args: dict) -> dict:
    """يوجّه استدعاء الأداة من النموذج إلى الدالة الفعلية، مع التقاط أي استثناء غير متوقع."""
    try:
        if name == "file_op":
            action = args.get("action")
            if action == "read":
                return file_tool.read_file(args["path"])
            if action == "write":
                return file_tool.write_file(args["path"], args.get("content", ""),
                                             args.get("allow_protected", False))
            if action == "delete":
                return file_tool.delete_file(args["path"], args.get("allow_protected", False))
            if action == "list":
                return file_tool.list_files(args.get("path", "."))
            if action == "rollback":
                return file_tool.rollback_file(args["path"], args["backup_path"])
            if action == "commit":
                return file_tool.git_commit(args.get("message", "agent: update"))
            return {"ok": False, "error": f"action غير معروف: {action}"}

        if name == "run_terminal":
            return terminal_tool.run_command(args["command"], args.get("timeout"))

        if name == "search_code":
            return search_tool.search_code(
                args["query"], args.get("path", "."), args.get("regex", False)
            )

        if name == "problem_op":
            action = args.get("action")
            if action == "history":
                return problems_registry.get_problem_history(args["problem_id"])
            if action == "register":
                return problems_registry.register_attempt(
                    problem_id=args["problem_id"],
                    title=args.get("title", args["problem_id"]),
                    description=args.get("description", ""),
                    attempt_summary=args.get("attempt_summary", ""),
                    outcome=args.get("outcome", "attempted"),
                )
            return {"ok": False, "error": f"action غير معروف: {action}"}

        return {"ok": False, "error": f"أداة غير معروفة: {name}"}
    except Exception as e:
        # طبقة أمان أخيرة: أي خطأ غير متوقع من الأداة لا يجب أن يوقف العملية بشكل عنيف
        validator.log_action({"action": "tool_exception", "tool": name, "error": str(e),
                               "trace": traceback.format_exc()})
        return {"ok": False, "error": f"استثناء غير متوقع أثناء تنفيذ {name}: {e}"}


def _deliberate(client: Groq, env_snapshot: str, continuity_context: str,
                 problems_summary: str, user_goal: str) -> str:
    """
    المرحلة 1: استدعاء منفصل بدون أدوات إطلاقاً، غرضه التحليل والقرار فقط.
    هذا ما يمنع الوكيل من "التصرف أثناء التفكير" — يفصل القرار عن التنفيذ فعلياً
    عبر استدعاء API منفصل، وليس مجرد فقرة في نفس البرومبت.
    """
    messages = [
        {"role": "system", "content": DELIBERATION_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"{env_snapshot}\n\n{continuity_context}\n\n"
            f"=== المشاكل طويلة المدى المفتوحة حالياً ===\n{problems_summary}\n\n"
            f"=== توجيه إضافي من المشغّل (قد يكون فارغاً) ===\n{user_goal}"
        )},
    ]
    response = client.chat.completions.create(
        model=config.MODEL_NAME,
        messages=messages,
        max_tokens=config.MAX_TOKENS,
        temperature=0.4,  # تفكير أوسع قليلاً من مرحلة التنفيذ
    )
    return response.choices[0].message.content or ""


def execute_plan(client: Groq, env_snapshot: str, continuity_context: str,
                  deliberation: str, user_goal: str, system_prompt: str = SYSTEM_PROMPT,
                  max_iterations: int | None = None) -> str:
    """
    مرحلة التنفيذ العامة: تُستخدم من الدورة اليومية (run_agent) ومن المراجعة
    المعمارية الأسبوعية (scripts/architect_review.py) على حد سواء — بنفس
    الأدوات ونفس بوابة الأمان (فحص صياغة + بوابة اختبار حقيقية عند الـ commit).
    القرار (deliberation) قد يأتي من تفكير يومي ضيق أو من مراجعة معمارية واسعة السياق؛
    التنفيذ نفسه لا يفرّق، وينفّذ ما تقرر دون انتظار موافقة بشرية إضافية.
    """
    max_iterations = max_iterations or config.MAX_ITERATIONS
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"{env_snapshot}\n\n{continuity_context}\n\n"
            f"=== قرار وخطة مرحلة التفكير (نتائج تحليل سابق لهذه الدورة بالذات) ===\n"
            f"{deliberation}\n\n"
            f"=== تعليمات التنفيذ ===\n"
            f"نفّذ خطة التفكير أعلاه بالضبط بأدواتك، بما في ذلك أي قرار كبير ورد فيها "
            f"(إعادة هيكلة، حذف كود ميت، تغيير تصميم). أنت مخوَّل باتخاذ القرار وتنفيذه بنفسك "
            f"دون انتظار موافقة بشرية إضافية. لا تغيّر الأولوية التي اختارها التحليل إلا إذا "
            f"اكتشفت أثناء التنفيذ معلومة تجعلها مستحيلة أو خطيرة فعلياً — وإن حصل ذلك، اشرح لماذا "
            f"في ملخصك النهائي. بوابة الاختبار الحقيقية ستمنع أي commit يكسر الاختبارات تلقائياً، "
            f"لذا لا داعي للتردد خوفاً من كسر شيء — الأمان مضمون على مستوى الكود لا القرار."
        )},
    ]

    final_summary = ""

    for iteration in range(max_iterations):
        response = client.chat.completions.create(
            model=config.MODEL_NAME,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
            max_tokens=config.MAX_TOKENS,
            temperature=config.TEMPERATURE,
        )
        choice = response.choices[0]
        msg = choice.message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            final_summary = msg.content or ""
            break

        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                fn_args = {}

            result = _dispatch_tool(fn_name, fn_args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False)[:6000],
            })
    else:
        final_summary = "(تم الوصول للحد الأقصى من الدورات قبل أن يعلن الوكيل الانتهاء)"

    return final_summary


def run_agent(goal: str | None = None) -> str:
    """
    يشغّل دورة كاملة على مرحلتين حقيقيتين:
      1) التفكير العميق (_deliberate) بدون أدوات — ينتج خطة تنفيذ مُسبَّبة.
      2) التنفيذ (execute_plan) مقيّد بما قررته المرحلة الأولى فعلياً.
    """
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY غير مضبوط في متغيرات البيئة.")

    client = Groq(api_key=config.GROQ_API_KEY)
    env_snapshot = get_environment_snapshot()
    continuity_context = continuity.build_continuity_context()
    problems_summary = problems_registry.summarize_open_problems()

    user_goal = goal or "لا يوجد توجيه خاص لهذه الدورة — قرر أفضل أولوية بنفسك."

    # ---- المرحلة 1: التفكير العميق (بدون أدوات) ----
    deliberation = _deliberate(client, env_snapshot, continuity_context, problems_summary, user_goal)
    validator.log_action({"action": "deliberation", "content": deliberation[:3000]})

    # ---- المرحلة 2: التنفيذ (مقيّد بقرار المرحلة الأولى، بلا مراجعة بشرية) ----
    final_summary = execute_plan(client, env_snapshot, continuity_context, deliberation, user_goal)

    validator.log_action({"action": "agent_cycle_complete", "goal": user_goal,
                           "deliberation_excerpt": deliberation[:500],
                           "summary": final_summary[:2000]})
    return final_summary


if __name__ == "__main__":
    import sys
    goal_arg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    print(run_agent(goal_arg))
