from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.contracts import ImageInput, ModelResponse  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.providers.llm import (  # noqa: E402
    BaseModelProvider,
    DashScopeQwenProvider,
    IflytekSparkProvider,
)
from app.services.model_registry import ModelRegistry  # noqa: E402


@dataclass(slots=True)
class ResultRow:
    provider: str
    model: str
    configured: bool
    available: bool
    elapsed: str = "-"
    prompt_tokens: str = "-"
    completion_tokens: str = "-"
    result: str = "-"
    error: str = "-"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="国产模型安全连通性测试")
    group = value.add_mutually_exclusive_group(required=True)
    group.add_argument("--config-only", action="store_true")
    group.add_argument("--provider", choices=("iflytek", "dashscope"))
    group.add_argument("--all", action="store_true")
    group.add_argument("--vision", type=Path, metavar="IMAGE")
    return value


def response_row(response: ModelResponse) -> ResultRow:
    usage = response.usage
    return ResultRow(
        provider=response.provider,
        model=response.model,
        configured=True,
        available=True,
        elapsed=f"{response.elapsed_ms}ms",
        prompt_tokens=str(usage.prompt_tokens if usage else "-"),
        completion_tokens=str(usage.completion_tokens if usage else "-"),
        result=response.content.replace("\n", " ")[:48],
    )


async def run(args: argparse.Namespace) -> int:
    settings = Settings()
    registry = ModelRegistry(settings)
    spark = IflytekSparkProvider(settings)
    qwen = DashScopeQwenProvider(settings)
    targets = (
        [spark]
        if args.provider == "iflytek"
        else [qwen]
        if args.provider == "dashscope" or args.vision
        else [spark, qwen]
    )
    rows: list[ResultRow] = []
    try:
        if registry.errors:
            for error in registry.errors:
                rows.append(ResultRow("registry", "-", False, False, error=error[:80]))
            print_table(rows)
            return 1
        url_errors = validate_provider_urls(spark, qwen)
        if url_errors:
            print_table(url_errors)
            return 1
        if args.config_only:
            targets = [spark, qwen]
            for provider in targets:
                rows.append(
                    ResultRow(
                        provider.provider_name,
                        provider.default_model,
                        provider.configured,
                        provider.configured,
                        result="配置有效"
                        if provider.configured
                        else "请在.env中填写对应API Key",
                    )
                )
            print_table(rows)
            return 0 if all(item.configured for item in rows) else 2
        if any(not provider.configured for provider in targets):
            for provider in targets:
                rows.append(
                    ResultRow(
                        provider.provider_name,
                        provider.default_model,
                        provider.configured,
                        False,
                        error=(
                            "-" if provider.configured else "请在.env中填写对应API Key"
                        ),
                    )
                )
            print_table(rows)
            return 2
        if spark in targets:
            rows.append(
                await text_call(
                    spark,
                    settings.iflytek_spark_model,
                    "SPARK_OK",
                    {"thinking": "disabled"},
                )
            )
        if qwen in targets and not args.vision:
            for model in (
                settings.qwen_text_fast_model,
                settings.qwen_vision_fast_model,
                settings.qwen_vision_primary_model,
                settings.qwen_brief_model,
            ):
                rows.append(
                    await text_call(qwen, model, "QWEN_OK", {"enable_thinking": False})
                )
        if args.vision:
            image = ImageInput(source_type="path", value=str(args.vision))
            for model in (
                settings.qwen_vision_fast_model,
                settings.qwen_vision_primary_model,
                settings.qwen_brief_model,
            ):
                try:
                    response = await qwen.generate_multimodal(
                        prompt="只输出一句简短图片描述。",
                        images=[image],
                        model=model,
                        high_resolution=False,
                    )
                    rows.append(response_row(response))
                except Exception as exc:
                    rows.append(
                        ResultRow(
                            qwen.provider_name,
                            model,
                            True,
                            False,
                            error=f"{type(exc).__name__}: {exc}"[:80],
                        )
                    )
        print_table(rows)
        return 0 if rows and all(item.available for item in rows) else 1
    finally:
        await asyncio.gather(spark.aclose(), qwen.aclose())


async def text_call(
    provider: BaseModelProvider,
    model: str,
    expected: str,
    options: dict[str, object],
) -> ResultRow:
    try:
        response = await provider.generate_text(
            messages=[{"role": "user", "content": f"只回答：{expected}"}],
            model=model,
            temperature=0,
            max_tokens=16,
            extra_options=options,
        )
        row = response_row(response)
        if expected not in response.content:
            row.available = False
            row.error = f"响应未包含 {expected}"
        return row
    except Exception as exc:
        return ResultRow(
            provider.provider_name,
            model,
            True,
            False,
            error=f"{type(exc).__name__}: {exc}"[:80],
        )


def validate_provider_urls(
    spark: IflytekSparkProvider, qwen: DashScopeQwenProvider
) -> list[ResultRow]:
    rows: list[ResultRow] = []
    for provider in (spark, qwen):
        try:
            parsed = urlparse(provider.base_url)
            valid = (
                parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username
            )
        except ValueError as exc:
            valid = False
            error = str(exc)
        else:
            error = "Base URL必须是无凭据的HTTPS地址"
        if not valid:
            rows.append(
                ResultRow(
                    provider.provider_name,
                    provider.default_model,
                    bool(provider.api_key),
                    False,
                    error=error,
                )
            )
    return rows


def print_table(rows: list[ResultRow]) -> None:
    headers = (
        "Provider",
        "Model",
        "Configured",
        "Available",
        "Elapsed",
        "Prompt Tokens",
        "Completion Tokens",
        "Result",
        "Error",
    )
    values = [
        (
            row.provider,
            row.model,
            str(row.configured),
            str(row.available),
            row.elapsed,
            row.prompt_tokens,
            row.completion_tokens,
            row.result,
            row.error,
        )
        for row in rows
    ]
    widths = [
        max(len(header), *(len(row[i]) for row in values))
        for i, header in enumerate(headers)
    ]
    print(" | ".join(header.ljust(widths[i]) for i, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in values:
        print(" | ".join(value.ljust(widths[i]) for i, value in enumerate(row)))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parser().parse_args())))
