#!/usr/bin/env python3
"""
يبني تقريراً أسبوعياً من memory/history.json الفعلي (وليس نصاً وهمياً من النموذج).
يُشغَّل عبر GitHub Actions أسبوعياً، ويحفظ النتيجة في reports/weekly-<date>.md
"""
import json
import os
from datetime import datetime, timedelta

import config

REPORTS_DIR = os.path.join(config.REPO_PATH, "reports")


def load_history() -> list[dict]:
    if not os.path.exists(config.MEMORY_FILE):
        return []
    with open(config.MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_report(days: int = 7) -> str:
    history = load_history()
    cutoff = datetime.utcnow().timestamp() - days * 86400
    recent = [e for e in history if e.get("timestamp", 0) >= cutoff]

    commits = [e for e in recent if e.get("action") == "git_commit"]
    blocked = [e for e in recent if e.get("action") == "git_commit_blocked"]
    writes = [e for e in recent if e.get("action") == "write_file"]
    deletes = [e for e in recent if e.get("action") == "delete_file"]
    errors = [e for e in recent if e.get("action") == "tool_exception"]
    cycles = [e for e in recent if e.get("action") == "agent_cycle_complete"]

    lines = [
        f"# تقرير أسبوعي — {datetime.utcnow().strftime('%Y-%m-%d')}",
        "",
        f"عدد دورات الوكيل: {len(cycles)}",
        f"عدد الـ commits الناجحة: {len(commits)}",
        f"عدد الـ commits المرفوضة (فشل اختبار حقيقي): {len(blocked)}",
        f"عدد الملفات المعدّلة: {len(writes)}",
        f"عدد الملفات المحذوفة: {len(deletes)}",
        f"عدد الأخطاء غير المتوقعة في الأدوات: {len(errors)}",
        "",
        "## الالتزامات (commits)",
    ]
    for c in commits:
        lines.append(f"- {c.get('message', '(بدون رسالة)')}")
    if not commits:
        lines.append("- لا يوجد")

    if blocked:
        lines.append("\n## commits مرفوضة (فشلت الاختبارات فعلياً)")
        for b in blocked:
            lines.append(f"- {b.get('message', '')} — السبب: {b.get('reason', '')}")

    if errors:
        lines.append("\n## أخطاء غير متوقعة يجب مراجعتها يدوياً")
        for e in errors:
            lines.append(f"- أداة {e.get('tool', '')}: {e.get('error', '')[:200]}")

    return "\n".join(lines)


if __name__ == "__main__":
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report = build_report()
    filename = f"weekly-{datetime.utcnow().strftime('%Y-%m-%d')}.md"
    path = os.path.join(REPORTS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"تم إنشاء التقرير: {path}")
    print(report)
