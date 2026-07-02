from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.message import Message

def build_variables(payload_value: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    existing = payload.get("existing_items", [])
    existing_summary = [{"filter_key": item.get("filter_key"), "payload_keys": sorted((item.get("payload") or {}).keys())} for item in existing if isinstance(item, dict)]
    return {"existing_metadata_summary": json.dumps(existing_summary[:50], ensure_ascii=False, indent=2), "refined_text": payload.get("refinement", {}).get("refined_text", ""), "metadata_type": "main_flow_filter"}


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class MainFlowFilterAuthoringVariablesBuilder(Component):
    display_name = "03 메인 플로우 필터 등록 변수 생성기"
    description = "Langflow 프롬프트 템플릿에 연결할 정제 텍스트와 기존 필터 요약 변수를 제공합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [
        Output(name="existing_metadata_summary", display_name="기존 메타데이터 요약", method="build_existing_summary", types=["Message"], group_outputs=True),
        Output(name="refined_text", display_name="정제 텍스트", method="build_refined_text", types=["Message"], group_outputs=True),
    ]

    def build_refined_text(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["refined_text"])

    def build_existing_summary(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["existing_metadata_summary"])

