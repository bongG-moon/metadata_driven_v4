from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.message import Message

def build_variables(payload_value: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    schemas = {alias: sorted({column for row in rows[:20] for column in row}) for alias, rows in payload.get("runtime_sources", {}).items() if isinstance(rows, list)}
    previews = {alias: rows[:5] for alias, rows in payload.get("runtime_sources", {}).items() if isinstance(rows, list)}
    return {
        "intent_plan_json": json.dumps(payload.get("intent_plan", {}), ensure_ascii=False, indent=2),
        "source_schema_json": json.dumps(schemas, ensure_ascii=False, indent=2),
        "source_preview_json": json.dumps(previews, ensure_ascii=False, indent=2),
        "output_contract_json": json.dumps(payload.get("intent_plan", {}).get("output_contract", {}), ensure_ascii=False, indent=2),
    }


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class PandasVariablesBuilder(Component):
    display_name = "16 pandas 변수 생성기"
    description = "Langflow 프롬프트 템플릿과 에이전트/LLM에 연결할 pandas 코드 생성 변수를 제공합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [
        Output(name="intent_plan_json", display_name="의도 계획 JSON", method="build_intent_plan_json", types=["Message"], group_outputs=True),
        Output(name="source_schema_json", display_name="소스 스키마 JSON", method="build_source_schema_json", types=["Message"], group_outputs=True),
        Output(name="source_preview_json", display_name="소스 미리보기 JSON", method="build_source_preview_json", types=["Message"], group_outputs=True),
        Output(name="output_contract_json", display_name="출력 계약 JSON", method="build_output_contract_json", types=["Message"], group_outputs=True),
    ]

    def build_intent_plan_json(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["intent_plan_json"])

    def build_source_schema_json(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["source_schema_json"])

    def build_source_preview_json(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["source_preview_json"])

    def build_output_contract_json(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["output_contract_json"])

