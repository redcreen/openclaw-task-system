#!/usr/bin/env python3
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Iterable


DEFAULT_LONG_TASK_KEYWORDS = (
    "继续",
    "开始",
    "需要",
    "处理",
    "排查",
    "修复",
    "整理",
    "重构",
    "实现",
    "检查",
    "分析",
    "调查",
    "同步",
    "测试",
    "验证",
    "规划",
)


@dataclass(frozen=True)
class TaskClassification:
    is_long_task: bool
    confidence: str
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContinuationPlan:
    kind: str
    due_at: str
    wait_seconds: int
    reply_text: str
    lead_request: str | None = None


PRIMARY_DELAYED_REPLY_PATTERN = re.compile(
    r"^\s*(?P<delay>\d+)\s*(?P<unit>分钟|分|秒)(?:钟)?\s*(?:后)?\s*"
    r"(?P<verb>回复(?:我)?|回(?:我)?|提醒(?:我)?|告诉(?:我)?)"
    r"(?P<message>.+?)\s*$"
)
FALLBACK_DELAYED_REPLY_PATTERN = re.compile(
    r"(?P<delay>\d+)\s*(?P<unit>分钟|分|秒)(?:钟)?\s*(?:后)?\s*"
    r"(?P<verb>回复(?:我)?|回(?:我)?|提醒(?:我)?|告诉(?:我)?)"
    r"(?P<message>.+?)\s*$"
)
TRAILING_SEQUENCE_PATTERN = re.compile(r"(?:[\s,，;；。.!！?？]+|然后|之后|再|并且|并在|接着|随后)+$")
GENERIC_FOLLOWUP_TARGETS = frozenset(
    {
        "我",
        "我一下",
        "我一声",
        "我信息",
        "信息",
        "消息",
        "一下",
        "一声",
    }
)


def _contains_any(text: str, keywords: Iterable[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


def _normalize_request_text(user_request: str) -> str:
    return " ".join(user_request.replace("\u3000", " ").split()).strip()


def _is_tolerable_delay_leadin(prefix: str) -> bool:
    cleaned = re.sub(r"[\s\-—–_·•、，,。.:：;；()（）\[\]【】'\"“”‘’]+", "", prefix)
    return len(cleaned) <= 2


def _parse_wait_seconds(delay: int, unit: str) -> int:
    if unit.startswith("分"):
        return delay * 60
    return delay


def _strip_trailing_sequence(prefix: str) -> str:
    return TRAILING_SEQUENCE_PATTERN.sub("", prefix).strip()


def _build_post_run_followup_text(lead_request: str, raw_message: str) -> str:
    normalized_target = _normalize_request_text(raw_message)
    normalized_target = normalized_target.strip("，,。.!！?？;；:：\"'“”‘’()（）[]【】 ")
    if normalized_target and normalized_target not in GENERIC_FOLLOWUP_TARGETS:
        return normalized_target
    compact_lead = _normalize_request_text(lead_request)
    if len(compact_lead) > 36:
        compact_lead = f"{compact_lead[:33]}..."
    return f"按约定提醒：关于「{compact_lead}」，我现在回来继续跟进。"


def parse_delayed_reply_request(
    user_request: str,
    *,
    now_dt: datetime | None = None,
) -> ContinuationPlan | None:
    normalized = _normalize_request_text(user_request)
    if not normalized:
        return None

    matched = PRIMARY_DELAYED_REPLY_PATTERN.fullmatch(normalized)
    if matched is None:
        fallback = FALLBACK_DELAYED_REPLY_PATTERN.search(normalized)
        if fallback is not None and _is_tolerable_delay_leadin(normalized[: fallback.start()]):
            matched = fallback
    if matched is None:
        return None

    message = matched.group("message").strip()
    if not message:
        return None
    delay = int(matched.group("delay"))
    unit = matched.group("unit")
    wait_seconds = _parse_wait_seconds(delay, unit)
    base = now_dt or datetime.now(timezone.utc).astimezone()
    due_at = (base + timedelta(seconds=wait_seconds)).isoformat()
    return ContinuationPlan(
        kind="delayed-reply",
        due_at=due_at,
        wait_seconds=wait_seconds,
        reply_text=message,
    )


def parse_post_run_delayed_followup_request(
    user_request: str,
    *,
    now_dt: datetime | None = None,
) -> ContinuationPlan | None:
    normalized = _normalize_request_text(user_request)
    if not normalized:
        return None

    matched = FALLBACK_DELAYED_REPLY_PATTERN.search(normalized)
    if matched is None:
        return None

    prefix = _strip_trailing_sequence(normalized[: matched.start()])
    if not prefix or _is_tolerable_delay_leadin(prefix):
        return None

    message = str(matched.group("message") or "").strip()
    delay = int(matched.group("delay"))
    unit = str(matched.group("unit") or "")
    wait_seconds = _parse_wait_seconds(delay, unit)
    base = now_dt or datetime.now(timezone.utc).astimezone()
    due_at = (base + timedelta(seconds=wait_seconds)).isoformat()
    return ContinuationPlan(
        kind="delayed-reply",
        due_at=due_at,
        wait_seconds=wait_seconds,
        reply_text=_build_post_run_followup_text(prefix, message),
        lead_request=prefix,
    )


def classify_main_task(
    user_request: str,
    *,
    estimated_steps: int | None = None,
    touches_multiple_files: bool = False,
    involves_delegation: bool = False,
    requires_external_wait: bool = False,
    needs_verification: bool = False,
    min_request_length: int = 24,
    min_reason_count: int = 2,
    estimated_steps_threshold: int = 3,
    keywords: Iterable[str] = DEFAULT_LONG_TASK_KEYWORDS,
) -> TaskClassification:
    normalized = user_request.strip()
    reasons: list[str] = []

    if len(normalized) >= min_request_length:
        reasons.append("request-length")

    matched_keywords = _contains_any(normalized, keywords)
    if matched_keywords:
        reasons.append(f"keywords:{','.join(matched_keywords[:4])}")

    if estimated_steps is not None and estimated_steps >= estimated_steps_threshold:
        reasons.append("multi-step")

    if touches_multiple_files:
        reasons.append("multi-file")

    if involves_delegation:
        reasons.append("delegation")

    if requires_external_wait:
        reasons.append("external-wait")

    if needs_verification:
        reasons.append("needs-verification")

    is_long_task = len(reasons) >= min_reason_count or "multi-step" in reasons or "external-wait" in reasons
    confidence = "high" if len(reasons) >= 3 else "medium" if is_long_task else "low"
    return TaskClassification(is_long_task=is_long_task, confidence=confidence, reasons=reasons)
