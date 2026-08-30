from dataclasses import dataclass
from typing import Protocol


class AnswerQualityEvaluationError(RuntimeError):
    """Generated output could not be evaluated safely."""


@dataclass(frozen=True)
class AnswerQualityPolicy:
    minimum_passing_score: int = 55
    maximum_answer_bytes: int = 32_768

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_passing_score <= 100:
            raise ValueError("quality threshold is invalid")
        if not 1_024 <= self.maximum_answer_bytes <= 65_536:
            raise ValueError("answer byte limit is invalid")


@dataclass(frozen=True)
class AnswerQualityContext:
    context_item_count: int
    local_item_count: int
    collective_item_count: int
    context_bytes: int


@dataclass(frozen=True)
class AnswerQualityEvaluation:
    overall_score: int
    relevance_score: int
    grounding_score: int
    clarity_score: int
    actionability_score: int
    safety_score: int
    passed: bool
    disclosure: str | None
    evaluator: str = "deterministic-quality-v1"


class AnswerQualityEvaluator(Protocol):
    async def evaluate(
        self,
        answer: str,
        context: AnswerQualityContext,
        policy: AnswerQualityPolicy,
    ) -> AnswerQualityEvaluation: ...


class DeterministicFakeAnswerQualityEvaluator:
    """Offline evaluator; no provider transport or customer telemetry."""

    async def evaluate(
        self,
        answer: str,
        context: AnswerQualityContext,
        policy: AnswerQualityPolicy,
    ) -> AnswerQualityEvaluation:
        normalized = " ".join(answer.split())
        if not normalized or len(answer.encode("utf-8")) > policy.maximum_answer_bytes:
            raise AnswerQualityEvaluationError("generated answer is not evaluable")
        relevance = min(100, 55 + min(len(normalized) // 8, 35))
        grounding = min(100, 45 + min(context.context_item_count * 10, 45))
        clarity = 90 if len(normalized) <= 1_500 else 70
        actionability = 80 if any(mark in normalized for mark in ("。", ".", "：", ":")) else 65
        safety = 100
        overall = round(
            relevance * .25 + grounding * .30 + clarity * .20
            + actionability * .15 + safety * .10
        )
        disclosure = None
        if context.context_item_count == 0:
            disclosure = "insufficient_context"
        elif grounding < 60:
            disclosure = "low_context_confidence"
        return AnswerQualityEvaluation(
            overall_score=overall,
            relevance_score=relevance,
            grounding_score=grounding,
            clarity_score=clarity,
            actionability_score=actionability,
            safety_score=safety,
            passed=overall >= policy.minimum_passing_score,
            disclosure=disclosure,
        )


async def evaluate_ai_answer(
    answer: str,
    context: AnswerQualityContext,
    *,
    evaluator: AnswerQualityEvaluator | None = None,
    policy: AnswerQualityPolicy | None = None,
) -> AnswerQualityEvaluation:
    adapter = evaluator or DeterministicFakeAnswerQualityEvaluator()
    effective_policy = policy or AnswerQualityPolicy()
    try:
        return await adapter.evaluate(answer, context, effective_policy)
    except AnswerQualityEvaluationError:
        raise
    except Exception as exc:
        raise AnswerQualityEvaluationError("quality evaluation failed") from exc
