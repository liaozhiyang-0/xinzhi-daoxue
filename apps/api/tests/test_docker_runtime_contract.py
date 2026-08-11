from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_runtime_image_keeps_dependency_metadata_as_the_single_source() -> None:
    dockerfile = (ROOT / "apps" / "api" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "tomllib" in dockerfile
    assert "--requirement /tmp/runtime-requirements.txt" in dockerfile
    assert "--no-deps ." in dockerfile
    assert "--mount=type=cache,target=/root/.cache/pip" in dockerfile


def test_compose_exposes_cpu_torch_default_for_api_and_worker() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert (
        compose.count(
            "TORCH_INDEX_URL: ${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cpu}"
        )
        == 2
    )
    assert compose.count("TORCH_REQUIREMENT: ${TORCH_REQUIREMENT:-torch>=2.7,<3}") == 2


def test_env_example_documents_the_torch_build_overrides() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu" in env_example
    assert "TORCH_REQUIREMENT=torch>=2.7,<3" in env_example
