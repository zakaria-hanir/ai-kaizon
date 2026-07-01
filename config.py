"""
إعدادات الوكيل - كل القيم قابلة للتعديل عبر متغيرات البيئة (Environment Variables)
"""
import os

# ==== Groq ====
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL_NAME = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
MAX_TOKENS = int(os.environ.get("GROQ_MAX_TOKENS", "4096"))
TEMPERATURE = float(os.environ.get("GROQ_TEMPERATURE", "0.3"))

# ==== المستودع ====
REPO_PATH = os.environ.get("REPO_PATH", os.getcwd())

# استخدام مسار كامل للملف لضمان عدم حدوث خطأ عند التعامل مع المجلدات
# إذا كنت تريد تخزينه في المجلد الرئيسي، نجعله يعتمد على REPO_PATH
MEMORY_FILE = os.environ.get("MEMORY_FILE", os.path.join(REPO_PATH, "memory.json"))

# ==== حلقة الوكيل ====
MAX_ITERATIONS = int(os.environ.get("AGENT_MAX_ITERATIONS", "15"))

# ==== ملفات/مسارات محمية لا يمكن للوكيل تعديلها تلقائياً بدون علامة مراجعة ====
PROTECTED_PATHS = [
    ".github/workflows",
    "safety/",
    "config.py",
    ".git/",
    ".env",
]

# ==== امتدادات مسموح فحصها/تعديلها ====
ALLOWED_EXTENSIONS = {
    ".py", ".md", ".txt", ".json", ".yml", ".yaml",
    ".toml", ".cfg", ".ini", ".js", ".ts", ".html", ".css"
}

# ==== أوامر طرفية محظورة (أنماط) ====
FORBIDDEN_COMMAND_PATTERNS = [
    r"rm\s+-rf\s+/(?!\S)",   # rm -rf /
]
