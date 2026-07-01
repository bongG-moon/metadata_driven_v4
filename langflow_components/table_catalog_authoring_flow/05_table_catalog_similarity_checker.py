from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data

def check_similarity(payload_value: Any, existing_items_value: Any = None) -> dict[str, Any]:
    payload = _payload(payload_value)
    existing = _items(existing_items_value) or payload.get("existing_items", [])
    existing_keys = {str(item.get("dataset_key") or item.get("key") or "").lower() for item in existing if isinstance(item, dict)}
    matches = []
    for item in payload.get("items", []):
        key = str(item.get("dataset_key") or "")
        if key.lower() in existing_keys:
            matches.append({"new_key": key, "existing_key": key, "match_type": "same_key", "recommended_action": "merge", "reason": "같은 dataset_key가 이미 존재합니다."})
    next_payload = deepcopy(payload)
    next_payload["existing_matches"] = matches
    next_payload["conflict_warnings"] = [{"severity": "blocker", "message": "같은 dataset_key가 있어 처리 방식 선택이 필요합니다.", "new_item_key": item["new_key"]} for item in matches]
    return next_payload


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _items(value: Any) -> list[dict[str, Any]]:
    data = getattr(value, "data", value)
    raw = data if isinstance(data, list) else data.get("items", data.get("existing_items", [])) if isinstance(data, dict) else []
    return [deepcopy(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


class TableCatalogSimilarityChecker(Component):
    display_name = "05 테이블 카탈로그 유사도 확인기"
    description = "테이블 카탈로그 저장 후보와 기존 항목의 같은 데이터셋 키 충돌을 확인합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True), DataInput(name="existing_items", display_name="기존 항목", required=False)]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=check_similarity(getattr(self, "payload", None), getattr(self, "existing_items", None)))
