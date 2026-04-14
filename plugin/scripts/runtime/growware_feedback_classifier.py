#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable

from growware_project import load_feedback_intake_policy


EXECUTION_SOURCE_DAEMON = "daemon-owned"
CLASSIFICATION_STEERING = "steering"
CLASSIFICATION_QUEUEING = "queueing"
POLICY_RULE_ID = "growware.feedback-intake.same-session.v1"


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _contains_any(text: str, signals: Iterable[str]) -> bool:
    return any(signal and signal in text for signal in (_normalize_text(item) for item in signals))


def classify(payload: dict[str, Any], *, project_root: Path | None = None) -> dict[str, Any]:
    policy = load_feedback_intake_policy(project_root)
    classifier = (policy.get("sameSessionClassifier") or {}) if isinstance(policy.get("sameSessionClassifier"), dict) else {}
    min_confidence = float(classifier.get("minConfidence") or 0.78)

    new_message = _normalize_text(payload.get("new_message"))
    active_task_summary = _normalize_text(payload.get("active_task_summary"))
    recent_messages = [
        _normalize_text(item)
        for item in (payload.get("recent_user_messages") or [])
        if _normalize_text(item)
    ]
    context_text = "\n".join([active_task_summary, *recent_messages, new_message]).strip()

    steering_signals = classifier.get("steeringSignals") or []
    queueing_signals = classifier.get("queueingSignals") or []
    bug_signals = classifier.get("bugSignals") or []
    idea_signals = classifier.get("ideaSignals") or []

    if _contains_any(new_message, steering_signals):
        return {
            "classification": CLASSIFICATION_STEERING,
            "confidence": max(0.9, min_confidence),
            "needs_confirmation": False,
            "reason_code": "growware-feedback-wording-refinement",
            "reason_text": "The latest feedback is phrased like a refinement of the current result, so runtime should keep it on the active Growware task.",
            "execution_source": str(policy.get("defaultExecutionSource") or EXECUTION_SOURCE_DAEMON),
            "policy_rule_id": POLICY_RULE_ID,
        }

    if _contains_any(new_message, queueing_signals):
        return {
            "classification": CLASSIFICATION_QUEUEING,
            "confidence": max(0.88, min_confidence),
            "needs_confirmation": False,
            "reason_code": "growware-feedback-independent-request",
            "reason_text": "The latest feedback introduces a separate goal, so runtime should queue it as a new Growware task.",
            "execution_source": str(policy.get("defaultExecutionSource") or EXECUTION_SOURCE_DAEMON),
            "policy_rule_id": POLICY_RULE_ID,
        }

    if _contains_any(new_message, bug_signals) and active_task_summary:
        return {
            "classification": CLASSIFICATION_STEERING,
            "confidence": min_confidence,
            "needs_confirmation": False,
            "reason_code": "growware-feedback-bug-followup",
            "reason_text": "The latest feedback reports a problem against the current active result, so runtime should treat it as a same-task correction.",
            "execution_source": str(policy.get("defaultExecutionSource") or EXECUTION_SOURCE_DAEMON),
            "policy_rule_id": POLICY_RULE_ID,
        }

    if _contains_any(new_message, idea_signals) and not active_task_summary:
        return {
            "classification": CLASSIFICATION_QUEUEING,
            "confidence": min_confidence,
            "needs_confirmation": False,
            "reason_code": "growware-feedback-new-idea",
            "reason_text": "The feedback reads like a new idea without an active task anchor, so runtime should keep it as a new task.",
            "execution_source": str(policy.get("defaultExecutionSource") or EXECUTION_SOURCE_DAEMON),
            "policy_rule_id": POLICY_RULE_ID,
        }

    if active_task_summary and any(token in new_message for token in ("这个", "它", "这条", "刚才", "上一个", "这次", "that", "this")):
        return {
            "classification": CLASSIFICATION_STEERING,
            "confidence": min_confidence,
            "needs_confirmation": False,
            "reason_code": "growware-feedback-pronoun-followup",
            "reason_text": "The feedback points back to the active result with anaphora, so runtime should keep it on the current task.",
            "execution_source": str(policy.get("defaultExecutionSource") or EXECUTION_SOURCE_DAEMON),
            "policy_rule_id": POLICY_RULE_ID,
        }

    return {
        "classification": CLASSIFICATION_QUEUEING,
        "confidence": min_confidence,
        "needs_confirmation": False,
        "reason_code": "growware-feedback-default-new-task",
        "reason_text": "No stronger same-task refinement signal matched, so runtime keeps this as a separate Growware task.",
        "execution_source": str(policy.get("defaultExecutionSource") or EXECUTION_SOURCE_DAEMON),
        "policy_rule_id": POLICY_RULE_ID,
        "context_excerpt": context_text[:160] or None,
    }


def main() -> None:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise SystemExit("classifier input must be a JSON object")
    print(json.dumps(classify(payload), ensure_ascii=False))


if __name__ == "__main__":
    main()
