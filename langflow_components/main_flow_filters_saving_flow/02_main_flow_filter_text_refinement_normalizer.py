from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data

def normalize_refinement(payload_value: Any, llm_response: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    parsed = _json(llm_response)
    raw_text = payload.get("request", {}).get("raw_text", "")
    next_payload = deepcopy(payload)
    next_payload["refinement"] = {"refined_text": str(parsed.get("refined_text") or raw_text), "needs_more_input": bool(parsed.get("needs_more_input", False)), "missing_information": _list(parsed.get("missing_information")), "assumptions": _list(parsed.get("assumptions")), "remaining_questions": _list(parsed.get("remaining_questions"))}
    return next_payload


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    text = str(value or "")
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class MainFlowFilterTextRefinementNormalizer(Component):
    display_name = "02 메인 플로우 필터 텍스트 정제 정규화기"
    description = "한국어 텍스트 정제 LLM 응답을 페이로드의 정제 결과로 정규화합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True), MessageTextInput(name="llm_response", display_name="LLM 응답", required=False)]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=normalize_refinement(getattr(self, "payload", None), getattr(self, "llm_response", "")))
