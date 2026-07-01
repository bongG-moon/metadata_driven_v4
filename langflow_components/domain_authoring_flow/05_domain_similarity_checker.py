from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data

def check_similarity(payload_value: Any, existing_items_value: Any = None) -> dict[str, Any]:
    payload = _payload(payload_value)
    existing = _items(existing_items_value) or payload.get("existing_items", [])
    matches = []
    warnings = []
    existing_by_key = {_key(item).lower(): item for item in existing if isinstance(item, dict)}
    for item in payload.get("items", []):
        key = _key(item)
        if key.lower() in existing_by_key:
            matches.append({"new_key": key, "existing_key": _key(existing_by_key[key.lower()]), "match_type": "same_key", "recommended_action": "merge", "reason": "같은 저장 기준 key가 이미 존재합니다."})
            warnings.append({"severity": "blocker", "message": "같은 key가 있어 처리 방식 선택이 필요합니다.", "new_item_key": key})
    next_payload = deepcopy(payload)
    next_payload["existing_matches"] = matches
    next_payload["conflict_warnings"] = warnings
    if matches and next_payload.get("duplicate_decision", {}).get("action") == "ask":
        next_payload.setdefault("warnings", []).append({"type": "duplicate_decision_required", "message": "비슷한 기존 정보가 있어 저장 전 선택이 필요합니다."})
    return next_payload


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _items(value: Any) -> list[dict[str, Any]]:
    data = getattr(value, "data", value)
    if isinstance(data, list):
        return [deepcopy(item) for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        raw = data.get("items") or data.get("existing_items") or []
        return [deepcopy(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    return []


def _key(item: dict[str, Any]) -> str:
    section = item.get("section") or item.get("gbn") or ""
    return f"{section}:{item.get('key', '')}" if section else str(item.get("key", ""))


class DomainSimilarityChecker(Component):
    display_name = "05 도메인 유사도 확인기"
    description = "도메인 저장 후보와 기존 항목의 같은 키 충돌을 확인합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True), DataInput(name="existing_items", display_name="기존 항목", required=False)]
    outputs = [Output(name="payload_out", display_name="페이로드 출력", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(data=check_similarity(getattr(self, "payload", None), getattr(self, "existing_items", None)))
