from dataclasses import dataclass
from typing import Protocol

from openai import AsyncOpenAI

from app.core.config import settings


MODEL = "gpt-5.6-luna"

INPUT_PRICE_PER_MILLION = 1.00
OUTPUT_PRICE_PER_MILLION = 6.00

MAX_OUTPUT_TOKENS = 600


@dataclass
class AIContentResult:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class AIContentProvider(Protocol):
    """Generation boundary; adapters own transport and credentials."""

    provider_name: str

    async def generate(self, prompt: str) -> AIContentResult: ...


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
) -> float:

    input_cost = (
        input_tokens
        / 1_000_000
        * INPUT_PRICE_PER_MILLION
    )

    output_cost = (
        output_tokens
        / 1_000_000
        * OUTPUT_PRICE_PER_MILLION
    )

    return round(
        input_cost + output_cost,
        6,
    )


class OpenAIContentProvider:
    provider_name = "openai"

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate(self, prompt: str) -> AIContentResult:
        response = await self._client.responses.create(
            model=MODEL,
            input=prompt,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            store=False,
        )

        content = response.output_text.strip()
        usage = response.usage
        input_tokens = usage.input_tokens if usage else 0
        output_tokens = usage.output_tokens if usage else 0
        return AIContentResult(
            content=content,
            model=MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=calculate_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
        )


class DeterministicFakeContentProvider:
    """Offline provider for orchestration and accounting contracts."""

    provider_name = "deterministic_fake"

    async def generate(self, prompt: str) -> AIContentResult:
        normalized = " ".join(prompt.split())
        return AIContentResult(
            content=f"[deterministic] {normalized[:160]}",
            model="deterministic-fake-v1",
            input_tokens=len(prompt.encode("utf-8")),
            output_tokens=0,
            estimated_cost_usd=0.0,
        )


async def generate_social_content(
    prompt: str,
    *,
    provider: AIContentProvider | None = None,
) -> AIContentResult:
    adapter = provider or OpenAIContentProvider()
    return await adapter.generate(prompt)
