"""Rule-based query intent classification."""
from dataclasses import dataclass
from typing import Dict, List

INTENTS = ("vqa", "captioning", "grounding", "change_detection", "fusion", "unknown")

CHANGE_KEYWORDS = [
    "changed", "difference", "before", "after", "between", "since", "grew", "shrank", "new",
]
GROUNDING_KEYWORDS = [
    "where", "locate", "show me", "point to", "highlight", "find the",
]
CAPTIONING_KEYWORDS = [
    "describe", "summarise", "summarize", "what is this", "caption", "overview",
]
FUSION_KEYWORDS = [
    "combine", "both sensors", "radar and optical", "sar and", "all-weather",
]

KEYWORD_SETS = {
    "change_detection": CHANGE_KEYWORDS,
    "grounding": GROUNDING_KEYWORDS,
    "captioning": CAPTIONING_KEYWORDS,
    "fusion": FUSION_KEYWORDS,
}

TWO_IMAGE_BONUS = {"change_detection": 1.5, "fusion": 1.0}
ONE_IMAGE_PENALTY_FACTOR = {"change_detection": 0.3, "fusion": 0.3}

CONFIDENCE_ESCALATION_THRESHOLD = 0.5


@dataclass
class IntentResult:
    intent: str
    confidence: float
    matched_signals: List[str]
    method: str


def classify_intent(query: str, image_count: int) -> IntentResult:
    q = (query or "").strip().lower()

    if not q:
        return IntentResult(
            intent="unknown",
            confidence=0.0,
            matched_signals=[],
            method="rule_based_empty_query",
        )

    matched_signals: Dict[str, List[str]] = {intent: [] for intent in KEYWORD_SETS}
    for intent, keywords in KEYWORD_SETS.items():
        for kw in keywords:
            if kw in q:
                matched_signals[intent].append(kw)

    scores: Dict[str, float] = {intent: float(len(sigs)) for intent, sigs in matched_signals.items()}

    if image_count >= 2:
        for intent, bonus in TWO_IMAGE_BONUS.items():
            scores[intent] += bonus
            matched_signals[intent].append(f"image_count={image_count}")
    elif image_count == 1:
        for intent, factor in ONE_IMAGE_PENALTY_FACTOR.items():
            scores[intent] *= factor

    best_intent = max(scores, key=lambda k: scores[k])
    best_score = scores[best_intent]

    if best_score <= 0:
        return IntentResult(
            intent="vqa",
            confidence=0.30,
            matched_signals=["no rule-based keyword matched; defaulted to vqa"],
            method="rule_based_fallback",
        )

    signals = matched_signals[best_intent]
    keyword_hits = len([s for s in signals if not s.startswith("image_count=")])
    image_bonus_applied = any(s.startswith("image_count=") for s in signals)

    confidence = 0.45 + 0.15 * keyword_hits + (0.15 if image_bonus_applied else 0.0)
    confidence = min(confidence, 0.95)

    method = "rule_based_keyword"
    if confidence < CONFIDENCE_ESCALATION_THRESHOLD:
        method = "rule_based_keyword_low_confidence"

    # TODO(intent-llm): once an LLM-based classifier exists in this codebase, route
    # low-confidence results (confidence < CONFIDENCE_ESCALATION_THRESHOLD) to it for
    # disambiguation instead of trusting this rule-based guess. Not implemented yet.

    return IntentResult(
        intent=best_intent,
        confidence=round(confidence, 3),
        matched_signals=signals,
        method=method,
    )
