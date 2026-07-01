from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data

def normalize_intent_plan(payload_value: Any, llm_response: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    parsed = _json(llm_response)
    plan = parsed.get("intent_plan") if isinstance(parsed.get("intent_plan"), dict) else parsed
    retrieval_jobs = plan.get("retrieval_jobs") if isinstance(plan.get("retrieval_jobs"), list) else []
    pandas_plan = plan.get("pandas_execution_plan") if isinstance(plan.get("pandas_execution_plan"), list) else []
    next_payload = deepcopy(payload)
    next_payload["intent_plan"] = {**plan, "retrieval_jobs": retrieval_jobs, "pandas_execution_plan": pandas_plan}
    next_payload["metadata_refs"] = parsed.get("metadata_refs", plan.get("metadata_refs", [])) if isinstance(parsed.get("metadata_refs", plan.get("metadata_refs", [])), list) else []
    next_payload.setdefault("trace", {}).setdefault("inspection", {})["intent"] = {
        "stage": "04_intent_plan_normalizer",
        "status": "ok" if retrieval_jobs else "warning",
        "analysis_kind": next_payload["intent_plan"].get("analysis_kind", ""),
        "retrieval_job_count": len(retrieval_jobs),
        "pandas_step_count": len(pandas_plan),
        "decision_reason": parsed.get("trace", {}).get("decision_reason", []) if isinstance(parsed.get("trace"), dict) else [],
    }
    if not retrieval_jobs:
        next_payload.setdefault("trace", {}).setdefault("warnings", []).append({"type": "missing_retrieval_jobs", "message": "intent_plan.retrieval_jobs가 비어 있습니다."})
    return next_payload


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    text = _text_value(value)
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    elif "{" in text and "}" in text:
        text = text[text.find("{") : text.rfind("}") + 1]
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _text_value(value: Any) -> str:
    for attr in ("text", "content", "message"):
        text = getattr(value, attr, None)
        if isinstance(text, str):
            return text
    data = getattr(value, "data", None)
    if isinstance(data, dict):
        for key in ("text", "content", "message", "output"):
            if isinstance(data.get(key), str):
                return data[key]
    return str(value or "")


class IntentPlanNormalizer(Component):
    display_name = "04 의도 계획 정규화기"
    description = "Langflow 에이전트/LLM의 의도 JSON을 표준 의도 계획으로 정규화합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True), MessageTextInput(name="llm_response", display_name="의도 LLM 응답", required=True)]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=normalize_intent_plan(getattr(self, "payload", None), getattr(self, "llm_response", "")))
