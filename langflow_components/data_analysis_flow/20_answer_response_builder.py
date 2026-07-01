from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data

def build_answer_response(payload_value: Any, answer_text: Any = "") -> dict[str, Any]:
    payload = _payload(payload_value)
    message = _answer_text(answer_text).strip()
    if not message:
        row_count = payload.get("data", {}).get("row_count", 0)
        message = f"분석 결과 {row_count}건을 확인했습니다." if payload.get("analysis", {}).get("status") == "ok" else "분석을 완료하지 못했습니다. trace의 오류를 확인해 주세요."
    next_payload = deepcopy(payload)
    next_payload["answer_message"] = message
    next_payload["state"] = {**next_payload.get("state", {}), "current_data": {"row_count": next_payload.get("data", {}).get("row_count", 0), "preview_rows": next_payload.get("data", {}).get("rows", [])[:5], "data_ref": next_payload.get("data", {}).get("data_ref", "")}}
    return next_payload


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _answer_text(value: Any) -> str:
    if isinstance(value, dict):
        text = _answer_text_from_dict(value)
        return text if text else json.dumps(value, ensure_ascii=False, default=str)

    text = _message_text(value).strip()
    parsed = _json_text(text)
    if parsed:
        parsed_text = _answer_text_from_dict(parsed)
        if parsed_text:
            return parsed_text
    return text


def _answer_text_from_dict(value: dict[str, Any]) -> str:
    for key in ("answer_message", "answer", "text", "message", "output"):
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            return item.strip()
    data = value.get("data")
    if isinstance(data, dict):
        return _answer_text_from_dict(data)
    return ""


def _message_text(value: Any) -> str:
    for attr in ("text", "content", "message"):
        text = getattr(value, attr, None)
        if isinstance(text, str):
            return text
    data = getattr(value, "data", None)
    if isinstance(data, dict):
        extracted = _answer_text_from_dict(data)
        if extracted:
            return extracted
    return str(value or "")


def _json_text(text: str) -> dict[str, Any]:
    if not text:
        return {}
    candidate = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL)
    if match:
        candidate = match.group(1).strip()
    elif "{" in candidate and "}" in candidate:
        candidate = candidate[candidate.find("{") : candidate.rfind("}") + 1]
    try:
        parsed = json.loads(candidate)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


class AnswerResponseBuilder(Component):
    display_name = "20 답변 응답 생성기"
    description = "Langflow 에이전트/LLM 답변 문장과 결정된 데이터를 합쳐 페이로드를 완성합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True), MessageTextInput(name="answer_text", display_name="답변 문장", required=False)]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=build_answer_response(getattr(self, "payload", None), getattr(self, "answer_text", "")))
