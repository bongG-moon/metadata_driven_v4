from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data


def build_metadata_candidates(domain_items_value: Any = None, table_catalog_items_value: Any = None, main_flow_filters_value: Any = None) -> dict[str, Any]:
    domain_items, domain_load = _extract(domain_items_value, "domain_items")
    table_catalog_items, table_load = _extract(table_catalog_items_value, "table_catalog_items")
    main_flow_filters, main_load = _extract(main_flow_filters_value, "main_flow_filters")
    candidates = {
        "domain_items": domain_items,
        "table_catalog_items": table_catalog_items,
        "main_flow_filters": main_flow_filters,
    }
    loads = {
        "domain_items": domain_load,
        "table_catalog_items": table_load,
        "main_flow_filters": main_load,
    }
    errors = []
    for load in loads.values():
        if isinstance(load, dict):
            errors.extend(load.get("errors", []))
    return {
        **candidates,
        "metadata_candidates": deepcopy(candidates),
        "metadata_load": {
            "status": _combined_status(loads),
            "counts": {key: len(value) for key, value in candidates.items()},
            "loads": loads,
            "errors": errors,
        },
    }


def _extract(value: Any, key: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data = getattr(value, "data", value)
    if isinstance(data, dict):
        items = data.get(key)
        if not isinstance(items, list) and isinstance(data.get("metadata_candidates"), dict):
            items = data["metadata_candidates"].get(key)
        load = data.get("metadata_load") if isinstance(data.get("metadata_load"), dict) else {}
        return ([deepcopy(item) for item in items if isinstance(item, dict)] if isinstance(items, list) else []), deepcopy(load)
    if isinstance(data, list):
        return [deepcopy(item) for item in data if isinstance(item, dict)], {}
    return [], {}


def _combined_status(loads: dict[str, dict[str, Any]]) -> str:
    statuses = [str(load.get("status", "")) for load in loads.values() if isinstance(load, dict) and load]
    if not statuses:
        return "empty"
    if any(status == "error" for status in statuses):
        return "partial_error"
    if all(status == "ok" for status in statuses):
        return "ok"
    if any(status == "ok" for status in statuses):
        return "partial"
    return statuses[0]


class MetadataCandidatesBuilder(Component):
    display_name = "01D 메타데이터 후보 결합기"
    description = "도메인, 테이블 카탈로그, 메인 변수 메타데이터를 의도 분석용 후보 JSON으로 결합합니다."
    inputs = [
        DataInput(name="domain_items", display_name="도메인 메타데이터", required=False),
        DataInput(name="table_catalog_items", display_name="테이블 카탈로그 메타데이터", required=False),
        DataInput(name="main_flow_filters", display_name="메인 변수 메타데이터", required=False),
    ]
    outputs = [Output(name="metadata_candidates", display_name="메타데이터 후보", method="build_payload", types=["Data"])]

    def build_payload(self) -> Data:
        return Data(
            data=build_metadata_candidates(
                getattr(self, "domain_items", None),
                getattr(self, "table_catalog_items", None),
                getattr(self, "main_flow_filters", None),
            )
        )
