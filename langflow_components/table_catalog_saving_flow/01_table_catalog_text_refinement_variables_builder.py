from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.message import Message

def build_variables(payload_value: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    return {"raw_text": payload.get("request", {}).get("raw_text", ""), "metadata_type": "table_catalog"}


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class TableCatalogTextRefinementVariablesBuilder(Component):
    display_name = "01 테이블 카탈로그 텍스트 정제 변수 생성기"
    description = "Langflow 프롬프트 템플릿에 연결할 원문 텍스트 변수를 제공합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [Output(name="raw_text", display_name="원문 텍스트", method="build_raw_text", types=["Message"])]

    def build_raw_text(self) -> Message:
        return Message(text=build_variables(getattr(self, "payload", None))["raw_text"])

