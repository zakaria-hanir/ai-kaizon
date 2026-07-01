#!/usr/bin/env python3
"""
نقطة تشغيل الوكيل.
الاستخدام:
    python main.py                      # هدف افتراضي: ابحث عن تحسين وطبّقه
    python main.py "أضف اختبارات لـ tools/search_tool.py"
"""
import sys
from agent import run_agent

if __name__ == "__main__":
    goal = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    print("🤖 بدء دورة الوكيل الذاتي التطور...\n")
    summary = run_agent(goal)
    print("\n" + "=" * 50)
    print("ملخص الدورة:")
    print(summary)
