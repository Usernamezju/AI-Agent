import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env", override=False)


class Settings:
    DEFAULT_PROVIDER       = os.getenv("DEFAULT_LLM_PROVIDER", "deepseek")

    DEEPSEEK_API_KEY       = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL      = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL         = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    QWEN_API_KEY           = os.getenv("QWEN_API_KEY", "")
    QWEN_BASE_URL          = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QWEN_MODEL             = os.getenv("QWEN_MODEL", "qwen-plus")
    QWEN_VISION_MODEL      = os.getenv("QWEN_VISION_MODEL", "qwen-vl-plus")

    MAX_ITERATIONS         = int(os.getenv("MAX_ITERATIONS", "15"))
    TEMPERATURE            = float(os.getenv("TEMPERATURE", "0.7"))
    MAX_TOKENS             = int(os.getenv("MAX_TOKENS", "4096"))

    SLIDING_WINDOW_SIZE    = int(os.getenv("SLIDING_WINDOW_SIZE", "10"))
    MAX_CONTEXT_TOKENS     = int(os.getenv("MAX_CONTEXT_TOKENS", "8000"))

    SANDBOX_ROOT           = os.getenv("SANDBOX_ROOT", str(ROOT_DIR / "sandbox"))
    WIKIPEDIA_LANGUAGE     = os.getenv("WIKIPEDIA_LANGUAGE", "zh")
    MULTI_AGENT_MAX_WORKERS = int(os.getenv("MULTI_AGENT_MAX_WORKERS", "3"))

    @classmethod
    def get_llm_config(cls, provider: str | None = None) -> dict:
        provider = provider or cls.DEFAULT_PROVIDER
        if provider == "deepseek":
            return {"api_key": cls.DEEPSEEK_API_KEY, "base_url": cls.DEEPSEEK_BASE_URL, "model": cls.DEEPSEEK_MODEL}
        if provider == "qwen":
            return {"api_key": cls.QWEN_API_KEY, "base_url": cls.QWEN_BASE_URL, "model": cls.QWEN_MODEL}
        raise ValueError(f"Unknown provider: {provider}")


settings = Settings()
