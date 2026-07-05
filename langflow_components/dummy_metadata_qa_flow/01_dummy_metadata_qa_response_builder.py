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
    answer_sections = _answer_sections(fixture)
    display_message = _display_message(fixture, answer_sections)
    return {
        "response_type": "metadata_qa",
        "status": "ok",
        "direct_response_ready": True,
        "message": display_message,
        "answer_message": fixture["answer_message"],
        "display_message": display_message,
        "answer_sections": answer_sections,
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
    if _is_available_sources_question(lowered):
        return _available_sources_fixture()
    return _production_domain_fixture(question)


def _is_available_sources_question(text: str) -> bool:
    if "조회" in text and ("가능" in text or "연결" in text or "필수" in text):
        return True
    dataset_terms = ("데이터셋", "dataset", "데이터")
    list_terms = ("목록", "리스트", "등록", "전체", "가능", "연결", "필수")
    return any(term in text for term in dataset_terms) and any(term in text for term in list_terms)


def _production_domain_fixture(question: str) -> dict[str, Any]:
    answer = "생산량은 생산 데이터의 `PRODUCTION` 컬럼을 합계로 집계하는 도메인 지표입니다. 질문에서 생산량, 생산실적, OUT 같은 표현이 나오면 이 용어 정의를 기준으로 분석 flow가 생산 실적 집계를 계획합니다."
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
    answer = "등록된 계산/분석 로직은 질문을 실제 pandas 분석으로 바꿀 때 참고하는 규칙입니다. 예시로 생산 달성율 recipe와 제품 token 매칭 helper가 있으며, 실제 계산 실행은 data_analysis_flow의 pandas 단계에서 수행됩니다."
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
    answer = "생산량 데이터셋은 table catalog의 `production_today` 예시로 등록되어 있습니다. Oracle 조회 방식이며, 실행 시 `DATE`가 필수 파라미터로 들어가야 합니다."
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
    answer = "현재 더미 QA 기준으로 조회 가능한 데이터셋은 생산 실적, 현재 재공, 아침 재공 3종입니다. 각 데이터셋은 연결 방식과 필수 조건을 기준으로 data analysis flow의 조회 계획에 사용됩니다."
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
    answer = "POP 제품 조건은 제품군을 해석하기 위한 도메인 조건 예시입니다. 더미 기준으로는 MODE가 LP로 시작하고, PKG_TYPE1이 FBGA 계열이며, MCP_NO가 비어 있지 않은 조건으로 설명됩니다."
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


def _answer_sections(fixture: dict[str, Any]) -> dict[str, Any]:
    answer_mode = str(fixture.get("answer_mode") or "").strip()
    rows = deepcopy(fixture["rows"])
    columns = list(fixture["columns"])
    return {
        "summary": {"headline": fixture["answer_message"], "description": fixture["summary"]},
        "key_points": _key_points(answer_mode, rows),
        "detail_table": {
            "title": _table_title(answer_mode),
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "display_limit": 12,
        },
        "sql_blocks": deepcopy(fixture.get("sql_blocks", [])),
        "usage_examples": _usage_examples(answer_mode),
        "related_items": [] if answer_mode == "available_sources" else deepcopy(fixture["source_refs"][:10]),
        "show_related_items": answer_mode != "available_sources",
        "warnings": [{"type": "dummy_metadata_qa_flow", "message": "실제 MongoDB 조회 없이 더미 metadata QA 결과를 반환했습니다."}],
    }


def _key_points(answer_mode: str, rows: list[dict[str, Any]]) -> list[str]:
    if answer_mode == "available_sources":
        source_counts: dict[str, int] = {}
        required_count = 0
        for row in rows:
            source_type = str(row.get("source_type") or "").strip() or "미등록"
            source_counts[source_type] = source_counts.get(source_type, 0) + 1
            if str(row.get("required_params") or "").strip():
                required_count += 1
        source_text = ", ".join(f"{key} {value}개" for key, value in source_counts.items())
        return [
            f"총 {len(rows)}개 데이터셋 예시가 있습니다.",
            f"연결 방식은 {source_text}로 구성되어 있습니다.",
            f"필수 조건이 있는 데이터셋은 {required_count}개입니다.",
        ]
    if answer_mode == "calculation_logic_list":
        return [f"계산/분석 로직 예시 {len(rows)}건을 보여줍니다.", "실제 수량 계산은 data_analysis flow의 pandas 단계에서 수행됩니다."]
    if answer_mode == "dataset_sql":
        return ["query_template은 사용자가 쿼리문을 명시적으로 물은 경우에만 표시합니다.", "실제 접속 정보와 쿼리 전문은 운영 table catalog 기준으로 확인해야 합니다."]
    if answer_mode == "product_domain_info":
        return ["제품군 조건은 분석 질문에서 제품 범위를 좁힐 때 사용됩니다.", "운영 환경에서는 저장된 도메인 metadata가 우선 기준입니다."]
    return ["도메인 용어 정의는 질문 표현을 데이터 컬럼과 집계 방식으로 연결합니다."]


def _table_title(answer_mode: str) -> str:
    return {
        "available_sources": "조회 가능한 데이터",
        "calculation_logic_list": "계산/분석 로직",
        "dataset_sql": "데이터셋 등록 정보",
        "product_domain_info": "제품 조건",
        "domain_info": "등록된 용어 정의",
    }.get(answer_mode, "관련 메타데이터")


def _usage_examples(answer_mode: str) -> list[str]:
    examples = {
        "available_sources": ["production_today 데이터셋의 쿼리문을 보여줘", "wip_today 데이터셋 필수 조건을 알려줘"],
        "calculation_logic_list": ["등록된 계산 로직 중 생산 달성율 기준 알려줘", "제품 token 매칭 규칙은 어떻게 동작해?"],
        "dataset_sql": ["이 데이터셋으로 답할 수 있는 대표 질문을 알려줘"],
        "product_domain_info": ["POP 제품 생산량을 제품별로 알려줘"],
        "domain_info": ["생산량 기준으로 제품별 상위 5개 알려줘"],
    }
    return examples.get(answer_mode, [])


def _display_message(fixture: dict[str, Any], answer_sections: dict[str, Any]) -> str:
    sections = ["### 답변\n" + fixture["answer_message"]]
    key_points = answer_sections.get("key_points") if isinstance(answer_sections.get("key_points"), list) else []
    if key_points:
        sections.append("### 한눈에 보기\n" + "\n".join(f"- {point}" for point in key_points))
    detail_table = answer_sections.get("detail_table") if isinstance(answer_sections.get("detail_table"), dict) else {}
    table_section = _detail_table_section(detail_table)
    if table_section:
        sections.append(table_section)
    for block in answer_sections.get("sql_blocks", []):
        if isinstance(block, dict) and str(block.get("sql") or "").strip():
            sections.append("### 등록된 Query Template\n#### " + str(block.get("label") or "query_template") + "\n```sql\n" + str(block["sql"]) + "\n```")
    examples = answer_sections.get("usage_examples") if isinstance(answer_sections.get("usage_examples"), list) else []
    if examples:
        sections.append("### 다음에 물어볼 수 있는 질문\n" + "\n".join(f"- {example}" for example in examples))
    if answer_sections.get("show_related_items"):
        refs = answer_sections.get("related_items") if isinstance(answer_sections.get("related_items"), list) else []
        if refs:
            sections.append("### 사용한 메타데이터\n" + "\n".join(f"- `{_ref_label(ref)}`" for ref in refs if isinstance(ref, dict)))
    warnings = answer_sections.get("warnings") if isinstance(answer_sections.get("warnings"), list) else []
    if warnings:
        sections.append("### 참고\n" + "\n".join(f"- {str(item.get('message') or item) if isinstance(item, dict) else str(item)}" for item in warnings[:5]))
    return "\n\n".join(sections)


def _detail_table_section(detail_table: dict[str, Any]) -> str:
    rows = detail_table.get("rows") if isinstance(detail_table.get("rows"), list) else []
    columns = detail_table.get("columns") if isinstance(detail_table.get("columns"), list) else []
    if not rows:
        return ""
    title = str(detail_table.get("title") or "관련 메타데이터").strip()
    limit = int(detail_table.get("display_limit") or 12)
    preview_rows = rows[:limit]
    row_count = int(detail_table.get("row_count") or len(rows))
    note = f"\n\n총 {row_count}건 중 {len(preview_rows)}건을 표시했습니다." if row_count > len(preview_rows) else f"\n\n총 {row_count}건입니다."
    return f"### {title}\n" + _markdown_table(preview_rows, columns) + note


def _ref_label(ref: dict[str, Any]) -> str:
    return ":".join(str(ref.get(key) or "").strip() for key in ("metadata_type", "section", "key") if str(ref.get(key) or "").strip())


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
