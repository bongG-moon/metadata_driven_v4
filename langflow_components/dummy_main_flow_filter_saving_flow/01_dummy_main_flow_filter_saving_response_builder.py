from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

METADATA_TYPE = "main_flow_filter"
METADATA_LABEL = "메인 플로우 필터"


def build_response(payload_value: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    item = {
        "filter_key": "DUMMY_DATE",
        "payload": {
            "display_name": "더미 기준일 필터",
            "aliases": ["기준일", "날짜"],
            "operator": "eq",
            "value_type": "date",
            "value_shape": "scalar",
        },
    }
    items = [item]
    columns = ["필터 키", "표시명", "연산자", "값 타입", "값 형태", "상태"]
    rows = [_item_row(item)]
    answer_message = f"{METADATA_LABEL} 메타데이터 1건을 저장 전 검토했습니다. 현재 더미 flow라 MongoDB에는 반영하지 않았습니다."
    answer_sections = _answer_sections(answer_message, columns, rows)
    message = _display_message(answer_sections)
    return {
        "response_type": "metadata_authoring",
        "metadata_type": METADATA_TYPE,
        "metadata_label": METADATA_LABEL,
        "status": "dry_run",
        "success": False,
        "direct_response_ready": True,
        "message": message,
        "answer_message": answer_message,
        "display_message": message,
        "answer_sections": answer_sections,
        "items": items,
        "data": {"columns": columns, "rows": rows, "row_count": len(rows)},
        "metadata_authoring": {
            "metadata_type": METADATA_TYPE,
            "metadata_label": METADATA_LABEL,
            "status": "dry_run",
            "generated_count": len(items),
            "saved_count": 0,
            "would_save_count": len(items),
            "dry_run": True,
            "keys": ["DUMMY_DATE"],
        },
        "review": {"status": "ok", "warnings": ["더미 flow이므로 MongoDB에 저장하지 않았습니다."]},
        "write_result": {"success": False, "dry_run": True, "message": "더미 flow는 저장하지 않습니다.", "saved_count": 0, "would_save_count": len(items)},
        "trace": {
            "raw_text_preview": _payload(payload.get("trace")).get("raw_text_preview", ""),
            "generated_items_preview": items,
            "existing_matches": [],
            "conflict_warnings": [],
        },
        "warnings": [{"type": "dummy_saving_flow", "message": "실제 LLM/MongoDB 저장 없이 더미 등록 응답을 반환했습니다."}],
        "errors": _list(payload.get("errors")),
    }


def _item_row(item: dict[str, Any]) -> dict[str, Any]:
    payload = _payload(item.get("payload"))
    return {
        "필터 키": str(item.get("filter_key") or ""),
        "표시명": str(payload.get("display_name") or item.get("filter_key") or ""),
        "연산자": str(payload.get("operator") or ""),
        "값 타입": str(payload.get("value_type") or ""),
        "값 형태": str(payload.get("value_shape") or ""),
        "상태": "저장 예정",
    }


def _answer_sections(answer_message: str, columns: list[str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "summary": {"headline": answer_message, "description": answer_message},
        "key_points": [
            f"생성된 {METADATA_LABEL} 등록 후보는 {len(rows)}건입니다.",
            "더미 flow라 실제 LLM 호출과 MongoDB 저장은 수행하지 않았습니다.",
            "필터 키, 연산자, 값 타입이 화면/API에서 확인 가능한 형태로 정리되었습니다.",
        ],
        "target_table": {"title": "등록 대상 메인 플로우 필터", "columns": columns, "rows": rows, "row_count": len(rows)},
        "notices": [{"type": "dummy", "title": "더미 응답", "message": "실제 저장 flow의 응답 형식만 빠르게 확인하기 위한 결과입니다."}],
        "next_steps": ["실제 저장 flow에서 같은 원문으로 실행해 검수 결과를 확인하세요.", "저장 후 분석 flow에서 해당 필터가 의도 분석에 반영되는지 테스트하세요."],
    }


def _display_message(answer_sections: dict[str, Any]) -> str:
    sections = []
    headline = str(_payload(answer_sections.get("summary")).get("headline") or "").strip()
    if headline:
        sections.append("### 등록 결과\n" + headline)
    key_points = _list(answer_sections.get("key_points"))
    if key_points:
        sections.append("### 한눈에 보기\n" + "\n".join(f"- {point}" for point in key_points))
    target_table = _payload(answer_sections.get("target_table"))
    rows = _list(target_table.get("rows"))
    columns = [str(item) for item in _list(target_table.get("columns"))]
    if rows and columns:
        sections.append("### " + str(target_table.get("title") or "등록 대상") + "\n" + _markdown_table(rows, columns) + f"\n\n총 {len(rows)}건입니다.")
    notices = [item for item in _list(answer_sections.get("notices")) if isinstance(item, dict)]
    if notices:
        lines = ["### 확인할 점"]
        for item in notices:
            lines.append(f"- {item.get('title') or item.get('type')}: {item.get('message')}")
        sections.append("\n".join(lines))
    next_steps = _list(answer_sections.get("next_steps"))
    if next_steps:
        sections.append("### 다음 단계\n" + "\n".join(f"- {step}" for step in next_steps))
    return "\n\n".join(sections)


def _markdown_table(rows: list[Any], columns: list[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        row_dict = _payload(row)
        body.append("| " + " | ".join(str(row_dict.get(column, "")).replace("|", "\\|") for column in columns) + " |")
    return "\n".join([header, divider] + body)


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _list(value: Any) -> list[Any]:
    return deepcopy(value) if isinstance(value, list) else []


class DummyMainFlowFilterSavingResponseBuilder(Component):
    display_name = "01 더미 메인 필터 등록 응답 생성기"
    description = "메인 플로우 필터 등록 flow와 같은 형태의 더미 API 응답과 메시지를 생성합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [
        Output(name="api_response", display_name="API 응답", method="build_api_response", types=["Data"], group_outputs=True),
        Output(name="message", display_name="메시지", method="build_message", types=["Message"], group_outputs=True),
    ]

    def build_api_response(self) -> Data:
        return Data(data=build_response(getattr(self, "payload", None)))

    def build_message(self) -> Message:
        return Message(text=build_response(getattr(self, "payload", None))["message"])
