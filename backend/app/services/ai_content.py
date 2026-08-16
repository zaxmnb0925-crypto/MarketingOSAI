from dataclasses import dataclass

from openai import AsyncOpenAI

from app.core.config import settings


MODEL = "gpt-5.6-luna"

INPUT_PRICE_PER_MILLION = 1.00
OUTPUT_PRICE_PER_MILLION = 6.00

MAX_OUTPUT_TOKENS = 600


client = AsyncOpenAI(
    api_key=settings.openai_api_key,
)


@dataclass
class AIContentResult:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


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


async def generate_social_content(
    prompt: str,
) -> AIContentResult:

    response = await client.responses.create(
        model=MODEL,
        input=prompt,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        store=False,
    )

    content = response.output_text.strip()

    usage = response.usage

    input_tokens = (
        usage.input_tokens
        if usage
        else 0
    )

    output_tokens = (
        usage.output_tokens
        if usage
        else 0
    )

    estimated_cost = calculate_cost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    return AIContentResult(
        content=content,
        model=MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost,
    )
