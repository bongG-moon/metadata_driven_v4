from __future__ import annotations

from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message


def build_dummy_response(payload_value: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    question = str(_payload(payload.get("request")).get("question") or "").strip()
    fixture = _fixture(question)
    display_message = _display_message(fixture)
    return {
        "response_type": "metadata_qa",
        "status": "ok",
        "direct_response_ready": True,
        "message": display_message,
        "answer_message": fixture["answer_message"],
        "display_message": display_message,
        "metadata_qa": {
            "summary": fixture["summary"],
            "answer_mode": fixture["answer_mode"],
            "items": fixture["rows"],
            "source_refs": fixture["source_refs"],
            "sql_blocks": fixture.get("sql_blocks", []),
        },
        "metadata_route": {"route": "dummy_metadata_qa", "answer_mode": fixture["answer_mode"], "confidence": "high"},
        "data": {"rows": fixture["rows"], "columns": fixture["columns"], "row_count": len(fixture["rows"])},
        "state": {
            **_payload(payload.get("state")),
            "current_metadata_qa": {
                "question": question,
                "answer_mode": fixture["answer_mode"],
                "source_refs": fixture["source_refs"],
            },
        },
        "trace": {
            "warnings": [{"type": "dummy_metadata_qa_flow", "message": "실제 MongoDB 조회 없이 더미 metadata QA 결과를 반환했습니다."}],
            "errors": [],
            "inspection": {
                "dummy_metadata_qa": {
                    "stage": "01_dummy_metadata_qa_response_builder",
                    "status": "ok",
                    "answer_mode": fixture["answer_mode"],
                    "row_count": len(fixture["rows"]),
                }
            },
        },
    }


def _fixture(question: str) -> dict[str, Any]:
    lowered = question.lower()
    if "쿼리" in lowered or "sql" in lowered or "query" in lowered:
        return _production_sql_fixture()
    if "계산" in lowered or "로직" in lowered or "함수" in lowered:
        return _calculation_fixture()
    if "pop" in lowered:
        return _pop_fixture()
    if "조회" in lowered and ("가능" in lowered or "연결" in lowered or "필수" in lowered):
        return _available_sources_fixture()
    return _production_domain_fixture(question)


def _production_domain_fixture(question: str) -> dict[str, Any]:
    answer = "생산량은 domain metadata의 `quantity_terms.production_quantity`로 등록되어 있으며, 생산 데이터의 `PRODUCTION` 컬럼을 합계 집계하는 지표입니다."
    return {
        "answer_mode": "domain_info",
        "answer_message": answer,
        "summary": answer,
        "columns": ["metadata_type", "section", "key", "display_name", "aliases", "column", "aggregation_method"],
        "rows": [
            {
                "metadata_type": "domain",
                "section": "quantity_terms",
                "key": "production_quantity",
                "display_name": "생산량",
                "aliases": "생산량, 생산실적, 실적, OUTPUT, OUT",
                "column": "PRODUCTION",
                "aggregation_method": "sum",
            }
        ],
        "source_refs": [{"metadata_type": "domain", "section": "quantity_terms", "key": "production_quantity"}],
        "sql_blocks": [],
    }


def _calculation_fixture() -> dict[str, Any]:
    answer = "등록된 계산/분석 로직 예시는 생산 달성율 recipe와 제품 token 매칭 helper입니다. 실제 계산 실행은 data_analysis_flow의 pandas 단계에서 수행됩니다."
    rows = [
        {
            "metadata_type": "domain",
            "section": "analysis_recipes",
            "key": "production_achievement_rate_analysis",
            "display_name": "생산 달성율 분석 recipe",
            "description": "실적 수량과 계획 수량을 집계한 뒤 달성율을 계산합니다.",
        },
        {
            "metadata_type": "domain",
            "section": "pandas_function_cases",
            "key": "product_token_match",
            "display_name": "제품 token 매칭",
            "description": "제품 속성 token 묶음을 DataFrame row와 매칭합니다.",
        },
    ]
    return {
        "answer_mode": "calculation_logic_list",
        "answer_message": answer,
        "summary": answer,
        "columns": ["metadata_type", "section", "key", "display_name", "description"],
        "rows": rows,
        "source_refs": [{"metadata_type": "domain", "section": row["section"], "key": row["key"]} for row in rows],
        "sql_blocks": [],
    }


def _production_sql_fixture() -> dict[str, Any]:
    sql = "-- 더미 query_template\nSELECT WORK_DATE, OPER_NAME, DEVICE, PRODUCTION\nFROM PRODUCTION_TABLE\nWHERE WORK_DATE = {DATE}"
    answer = "생산량 데이터셋은 table catalog의 `production_today` 예시로 등록되어 있으며, 필수 파라미터는 `DATE`입니다."
    rows = [
        {
            "metadata_type": "table_catalog",
            "key": "production_today",
            "display_name": "Production Today",
            "source_type": "oracle",
            "db_key": "PNT_RPT",
            "required_params": "DATE",
        }
    ]
    return {
        "answer_mode": "dataset_sql",
        "answer_message": answer,
        "summary": answer,
        "columns": ["metadata_type", "key", "display_name", "source_type", "db_key", "required_params"],
        "rows": rows,
        "source_refs": [{"metadata_type": "table_catalog", "key": "production_today"}],
        "sql_blocks": [{"label": "production_today", "sql": sql}],
    }


def _available_sources_fixture() -> dict[str, Any]:
    answer = "조회 가능한 데이터셋 예시는 생산 실적, 현재 재공, 아침 재공입니다. 각 데이터셋은 source_type과 required_params 기준으로 Run Flow에서 조회됩니다."
    rows = [
        {"metadata_type": "table_catalog", "key": "production_today", "display_name": "Production Today", "source_type": "oracle", "required_params": "DATE"},
        {"metadata_type": "table_catalog", "key": "wip_today", "display_name": "WIP Today", "source_type": "oracle", "required_params": "DATE"},
        {"metadata_type": "table_catalog", "key": "wip_history", "display_name": "WIP History", "source_type": "oracle", "required_params": "DATE"},
    ]
    return {
        "answer_mode": "available_sources",
        "answer_message": answer,
        "summary": answer,
        "columns": ["metadata_type", "key", "display_name", "source_type", "required_params"],
        "rows": rows,
        "source_refs": [{"metadata_type": "table_catalog", "key": row["key"]} for row in rows],
        "sql_blocks": [],
    }


def _pop_fixture() -> dict[str, Any]:
    answer = "POP 제품 조건은 예시 기준으로 MODE가 LP로 시작하고, PKG_TYPE1이 FBGA 계열이며, MCP_NO가 비어 있지 않은 조건으로 등록되어 있습니다."
    rows = [
        {"metadata_type": "domain", "section": "product_groups", "key": "POP", "display_name": "POP 제품", "description": "MODE starts_with LP, PKG_TYPE1 in FBGA 계열, MCP_NO not empty"},
    ]
    return {
        "answer_mode": "product_domain_info",
        "answer_message": answer,
        "summary": answer,
        "columns": ["metadata_type", "section", "key", "display_name", "description"],
        "rows": rows,
        "source_refs": [{"metadata_type": "domain", "section": "product_groups", "key": "POP"}],
        "sql_blocks": [],
    }


def _display_message(fixture: dict[str, Any]) -> str:
    sections = ["### 답변\n" + fixture["answer_message"]]
    for block in fixture.get("sql_blocks", []):
        sections.append("### 등록된 Query Template\n#### " + block["label"] + "\n```sql\n" + block["sql"] + "\n```")
    if fixture["rows"]:
        sections.append("### 관련 메타데이터\n" + _markdown_table(fixture["rows"], fixture["columns"]))
    return "\n\n".join(sections)


def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(str(row.get(column, "")).replace("|", "\\|") for column in columns) + " |")
    return "\n".join([header, divider] + body)


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class DummyMetadataQaResponseBuilder(Component):
    display_name = "01 더미 메타데이터 QA 응답 생성기"
    description = "메타데이터 QA와 같은 형태의 더미 API 응답과 메시지를 생성합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [
        Output(name="api_response", display_name="API 응답", method="build_api_response", types=["Data"], group_outputs=True),
        Output(name="message", display_name="메시지", method="build_message", types=["Message"], group_outputs=True),
    ]

    def build_api_response(self) -> Data:
        return Data(data=build_dummy_response(getattr(self, "payload", None)))

    def build_message(self) -> Message:
        return Message(text=build_dummy_response(getattr(self, "payload", None))["message"])
