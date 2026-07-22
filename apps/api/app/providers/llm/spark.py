from app.providers.llm.iflytek_spark import IflytekSparkProvider

# Backward-compatible import name for existing integrations.
SparkLLMProvider = IflytekSparkProvider

__all__ = ["SparkLLMProvider"]
