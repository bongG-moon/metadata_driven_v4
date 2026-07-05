from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.message import Message

def build_variables(payload_value: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    review_input = {"metadata_type": "domain", "items": payload.get("items", []), "conflict_warnings": payload.get("conflict_warnings", [])}
    return {"review_input_json": json.dumps(review_input, ensure_ascii=False, indent=2)}


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class DomainReviewVariablesBuilder(Component):
    display_name = "06 도메인 검수 변수 생성기"
    description = "Langflow 프롬프트 템플릿에 연결할 검수 입력 JSON 변수를 제공합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [Output(name="review_input_json", display_name="검수 입력 JSON", method="build_review_input_json", types=["Message"])]

    def build_review_input_json(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["review_input_json"])

