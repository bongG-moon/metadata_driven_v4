from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data

RUNTIME_FUNCTION_HELPERS = [
    {
        "function_name": "match_product_tokens",
        "selection_policy": "product_token_only",
        "selectable_for_intent": True,
        "description": "제품 속성 token 묶음을 실제 조회 DataFrame row와 매칭할 때만 사용한다.",
    },
    {
        "function_name": "sample_passthrough_helper",
        "selection_policy": "demo_only",
        "selectable_for_intent": False,
        "description": "여러 helper 전달 형식 확인용 더미 helper이며 실제 분석에서는 선택하지 않는다.",
    },
]


def build_metadata_candidates(domain_items_value: Any = None, table_catalog_items_value: Any = None, main_flow_filters_value: Any = None) -> dict[str, Any]:
    domain_items, domain_load = _extract(domain_items_value, "domain_items")
    table_catalog_items, table_load = _extract(table_catalog_items_value, "table_catalog_items")
    main_flow_filters, main_load = _extract(main_flow_filters_value, "main_flow_filters")
    domain_items = _annotate_runtime_function_cases(domain_items)
    candidates = {
        "domain_items": domain_items,
        "table_catalog_items": table_catalog_items,
        "main_flow_filters": main_flow_filters,
        "runtime_function_helpers": deepcopy(RUNTIME_FUNCTION_HELPERS),
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
            "counts": {
                "domain_items": len(domain_items),
                "table_catalog_items": len(table_catalog_items),
                "main_flow_filters": len(main_flow_filters),
            },
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


def _annotate_runtime_function_cases(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    helper_by_name = {item["function_name"]: item for item in RUNTIME_FUNCTION_HELPERS}
    annotated = []
    for item in items:
        next_item = deepcopy(item)
        if str(next_item.get("section") or "") == "pandas_function_cases":
            function_name = _function_name(next_item)
            helper = helper_by_name.get(function_name)
            selectable = bool(helper and helper.get("selectable_for_intent"))
            next_item["runtime_helper"] = {
                "function_name": function_name,
                "available": bool(helper),
                "selectable_for_intent": selectable,
                "selection_policy": helper.get("selection_policy", "not_registered_runtime_helper") if helper else "not_registered_runtime_helper",
            }
            if not selectable:
                next_item["selection_note"] = (
                    "이 항목은 intent_plan.pandas_function_case로 선택하지 않는다. "
                    "일반 pandas_execution_plan 또는 analysis guidance로만 참고한다."
                )
        annotated.append(next_item)
    return annotated


def _function_name(item: dict[str, Any]) -> str:
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    explicit = str(item.get("function_name") or payload.get("function_name") or payload.get("helper_name") or "").strip()
    if explicit:
        return explicit
    helper_names = {item["function_name"] for item in RUNTIME_FUNCTION_HELPERS}
    searchable_text = " ".join(
        str(value or "")
        for value in [
            item.get("key"),
            payload.get("description"),
            payload.get("pseudocode"),
            payload.get("usage_rule"),
            payload.get("io_contract"),
        ]
    )
    for helper_name in helper_names:
        if helper_name in searchable_text:
            return helper_name
    return str(item.get("key") or "").strip()


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
