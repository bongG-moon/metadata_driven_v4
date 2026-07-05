from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, DropdownInput, MessageTextInput, Output
from lfx.schema.data import Data

METADATA_TYPE = "table_catalog"


def build_request(raw_text: Any, duplicate_action: str = "ask", dry_run: str = "true", existing_items_value: Any = None) -> dict[str, Any]:
    original_text = "" if raw_text is None else str(raw_text)
    return {
        "metadata_type": METADATA_TYPE,
        "request": {
            "raw_text": original_text,
            "duplicate_action": duplicate_action if duplicate_action in {"ask", "merge", "replace", "skip", "create_new"} else "ask",
            "dry_run": str(dry_run).lower() != "false",
        },
        "existing_items": _items(existing_items_value),
        "trace": {"raw_text_preview": original_text[:500], "generated_items_preview": []},
        "errors": [] if original_text.strip() else [{"type": "empty_raw_text", "message": "등록할 자연어 원문이 비어 있습니다."}],
        "warnings": [],
    }


def _items(value: Any) -> list[dict[str, Any]]:
    data = getattr(value, "data", value)
    if isinstance(data, dict):
        raw = data.get("items") or data.get("existing_items") or []
        return [deepcopy(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    if isinstance(value, list):
        return [deepcopy(item) for item in value if isinstance(item, dict)]
    return []


class DummyTableCatalogSavingRequestLoader(Component):
    display_name = "00 더미 테이블 카탈로그 등록 요청 로더"
    description = "더미 테이블 카탈로그 등록 요청을 시작합니다. 실제 저장은 하지 않습니다."
    inputs = [
        MessageTextInput(name="raw_text", display_name="원문 텍스트", required=True),
        DropdownInput(name="duplicate_action", display_name="중복 처리 방식", options=["ask", "merge", "replace", "skip", "create_new"], value="ask"),
        DropdownInput(name="dry_run", display_name="드라이런", options=["true", "false"], value="true"),
        DataInput(name="existing_items", display_name="기존 항목", required=False),
    ]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=build_request(getattr(self, "raw_text", ""), getattr(self, "duplicate_action", "ask"), getattr(self, "dry_run", "true"), getattr(self, "existing_items", None)))
