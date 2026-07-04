from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message


def build_dummy_response(payload_value: Any) -> dict[str, Any]:
    payload = _payload(payload_value)
    request = _payload(payload.get("request"))
    question = str(request.get("question") or "").strip()
    fixture = _fixture(question)
    rows = fixture["rows"]
    answer = fixture["answer_message"]
    display_message = _display_message(fixture)
    trace = _payload(payload.get("trace"))
    trace.setdefault("warnings", []).append(
        {
            "type": "dummy_data_analysis_flow",
            "message": "이 응답은 라우터와 Web 계약 검증을 위한 더미 분석 결과입니다.",
        }
    )
    trace.setdefault("inspection", {})["dummy_flow"] = {
        "stage": "01_dummy_data_analysis_response_builder",
        "status": "ok",
        "row_count": len(rows),
    }
    trace.setdefault("inspection", {})["intent"] = fixture["intent_trace"]
    trace.setdefault("inspection", {})["data_retrieval"] = fixture["retrieval_trace"]
    trace.setdefault("inspection", {})["pandas_execution"] = fixture["pandas_trace"]
    return {
        "response_type": "data_analysis",
        "status": "ok",
        "message": display_message,
        "answer_message": answer,
        "display_message": display_message,
        "request": request,
        "metadata_refs": fixture["metadata_refs"],
        "intent_plan": fixture["intent_plan"],
        "source_results": fixture["source_results"],
        "analysis": {
            "status": "ok",
            "summary": fixture["summary"],
            "row_count": len(rows),
            "columns": fixture["columns"],
            "analysis_code": fixture["pandas_code"],
            "pandas_code_json": {"code": fixture["pandas_code"]},
            "step_outputs": fixture["step_outputs"],
            "function_case_results": fixture["function_case_results"],
            "used_helpers": fixture["used_helpers"],
        },
        "data": {
            "rows": rows,
            "columns": fixture["columns"],
            "row_count": len(rows),
        },
        "data_refs": [],
        "state": {
            **_payload(payload.get("state")),
            "current_data": {
                "row_count": len(rows),
                "preview_rows": rows[:5],
                "data_ref": "",
            },
        },
        "trace": trace,
    }


def _fixture(question: str) -> dict[str, Any]:
    lowered = question.lower()
    if "rg 32g" in lowered or "bg공정" in lowered or "bg 공정" in lowered:
        return _production_wip_product_fixture(question)
    if "l-218" in lowered or "sbm" in lowered:
        return _single_production_fixture(question)
    return _top_production_fixture(question)


def _production_wip_product_fixture(question: str) -> dict[str, Any]:
    rows = [
        {"제품": "RG 32G DDR4 FBGA 96 DDP", "공정": "BG", "생산량": 18400, "재공수량": 9850},
    ]
    pandas_code = """df_prod = sources["production_data"].copy()
df_wip = sources["wip_data"].copy()
prod_matched = match_product_tokens(df_prod, "RG 32G DDR4 FBGA 96 DDP")
wip_matched = match_product_tokens(df_wip, "RG 32G DDR4 FBGA 96 DDP")
prod_bg = prod_matched[prod_matched["OPER_NAME"].astype(str).str.contains("BG", na=False)]
wip_bg = wip_matched[wip_matched["OPER_NAME"].astype(str).str.contains("BG", na=False)]
production_sum = prod_bg["PRODUCTION"].sum()
wip_sum = wip_bg["WIP"].sum()
result = pd.DataFrame([{"제품": "RG 32G DDR4 FBGA 96 DDP", "공정": "BG", "생산량": production_sum, "재공수량": wip_sum}])"""
    return _base_fixture(
        question=question,
        answer_message="RG 32G DDR4 FBGA 96 DDP 제품의 BG공정 기준 생산량은 18.4K, 재공수량은 9,850입니다. 이 결과는 더미 데이터로 만든 라우터 검증용 예시입니다.",
        summary="제품 token 매칭 후 BG 공정의 생산량과 재공수량을 각각 집계했습니다.",
        analysis_kind="production_wip_by_product_process",
        rows=rows,
        columns=["제품", "공정", "생산량", "재공수량"],
        retrieval_jobs=[
            {
                "dataset_key": "production_today",
                "source_alias": "production_data",
                "source_type": "oracle",
                "required_params": {"DATE": "20260701"},
                "filters": {"OPER_NAME": {"operator": "contains", "value": "BG"}},
            },
            {
                "dataset_key": "wip_today",
                "source_alias": "wip_data",
                "source_type": "oracle",
                "required_params": {"DATE": "20260701"},
                "filters": {"OPER_NAME": {"operator": "contains", "value": "BG"}},
            },
        ],
        pandas_plan=[
            {"step": "제품 token 매칭", "operation": "apply_pandas_function_case", "function_name": "match_product_tokens", "input_text": "RG 32G DDR4 FBGA 96 DDP"},
            {"step": "BG 공정 필터 적용", "operation": "filter", "column": "OPER_NAME", "operator": "contains", "value": "BG"},
            {"step": "생산량/재공수량 합계 계산", "operation": "aggregate", "metrics": ["PRODUCTION", "WIP"]},
        ],
        pandas_code=pandas_code,
        metadata_refs=[
            {"section": "pandas_function_cases", "key": "product_token_match"},
            {"section": "quantity_terms", "key": "production_quantity"},
            {"section": "quantity_terms", "key": "wip_quantity"},
            {"section": "table_catalog_items", "key": "production_today"},
            {"section": "table_catalog_items", "key": "wip_today"},
        ],
        function_case_results=[
            {
                "function_name": "match_product_tokens",
                "input_text": "RG 32G DDR4 FBGA 96 DDP",
                "matched_count": 1,
                "columns": ["TECH", "DEN", "MODE", "PKG_TYPE1", "LEAD", "MCP_NO", "DEVICE"],
                "preview_rows": [{"TECH": "RG", "DEN": "32G", "MODE": "DDR4", "PKG_TYPE1": "FBGA", "LEAD": "96", "MCP_NO": "DDP", "DEVICE": "RG32GDDR4FBGA96DDP"}],
            }
        ],
    )


def _single_production_fixture(question: str) -> dict[str, Any]:
    rows = [{"제품": "L-218K8H", "공정": "SBM", "생산 실적": 650}]
    pandas_code = """df = sources["production_data"].copy()
df = df[df["MCP_NO"].astype(str).str.contains("L-218K8H", na=False)]
df = df[df["OPER_NAME"].astype(str).str.contains("SBM", na=False)]
result = pd.DataFrame([{"제품": "L-218K8H", "공정": "SBM", "생산 실적": df["PRODUCTION"].sum()}])"""
    return _base_fixture(
        question=question,
        answer_message="전일 L-218K8H 제품의 SBM공정 생산 실적은 650입니다. 이 결과는 더미 데이터로 만든 라우터 검증용 예시입니다.",
        summary="전일 생산 실적 데이터에서 L-218K8H 제품과 SBM 공정을 필터링한 뒤 생산량을 합산했습니다.",
        analysis_kind="production_by_product_process",
        rows=rows,
        columns=["제품", "공정", "생산 실적"],
        retrieval_jobs=[
            {
                "dataset_key": "production",
                "source_alias": "production_data",
                "source_type": "oracle",
                "required_params": {"DATE": "20260630"},
                "filters": {"OPER_NAME": {"operator": "contains", "value": "SBM"}},
            }
        ],
        pandas_plan=[
            {"step": "제품 MCP_NO 필터 적용", "operation": "filter", "column": "MCP_NO", "operator": "contains", "value": "L-218K8H"},
            {"step": "SBM 공정 필터 적용", "operation": "filter", "column": "OPER_NAME", "operator": "contains", "value": "SBM"},
            {"step": "생산 실적 합계 계산", "operation": "aggregate", "column": "PRODUCTION", "method": "sum"},
        ],
        pandas_code=pandas_code,
        metadata_refs=[
            {"section": "quantity_terms", "key": "production_quantity"},
            {"section": "table_catalog_items", "key": "production"},
            {"section": "main_flow_filters", "key": "DATE"},
        ],
        function_case_results=[],
    )


def _top_production_fixture(question: str) -> dict[str, Any]:
    rows = [
        {"제품": "DUMMY-A", "공정": "D/A", "생산량": 1200},
        {"제품": "DUMMY-B", "공정": "D/A", "생산량": 930},
        {"제품": "DUMMY-C", "공정": "D/A", "생산량": 770},
    ]
    pandas_code = """df = sources["production_data"].copy()
df = df[df["OPER_NAME"].isin(["D/A1", "D/A2", "D/A3", "D/A4", "D/A5", "D/A6"])]
grouped = df.groupby(["DEVICE"], dropna=False)["PRODUCTION"].sum().reset_index()
grouped = grouped.rename(columns={"DEVICE": "제품", "PRODUCTION": "생산량"})
result = grouped.sort_values("생산량", ascending=False).head(3)"""
    return _base_fixture(
        question=question,
        answer_message="더미 분석 기준으로 D/A 공정 생산량 상위 제품은 DUMMY-A, DUMMY-B, DUMMY-C 순입니다. 이 결과는 더미 데이터로 만든 라우터 검증용 예시입니다.",
        summary="D/A 공정 생산 데이터를 제품별로 집계하고 생산량 기준 내림차순으로 상위 3개를 선택했습니다.",
        analysis_kind="top_production_by_process",
        rows=rows,
        columns=["제품", "공정", "생산량"],
        retrieval_jobs=[
            {
                "dataset_key": "production_today",
                "source_alias": "production_data",
                "source_type": "oracle",
                "required_params": {"DATE": "20260701"},
                "filters": {"OPER_NAME": {"operator": "in", "value": ["D/A1", "D/A2", "D/A3", "D/A4", "D/A5", "D/A6"]}},
            }
        ],
        pandas_plan=[
            {"step": "D/A 공정 필터 적용", "operation": "filter", "column": "OPER_NAME"},
            {"step": "제품별 생산량 합계", "operation": "groupby_sum", "groupby_columns": ["DEVICE"], "aggregate_column": "PRODUCTION"},
            {"step": "생산량 상위 3개 선택", "operation": "sort_head", "n": 3},
        ],
        pandas_code=pandas_code,
        metadata_refs=[
            {"section": "process_groups", "key": "DA"},
            {"section": "quantity_terms", "key": "production_quantity"},
            {"section": "table_catalog_items", "key": "production_today"},
        ],
        function_case_results=[],
    )


def _base_fixture(
    question: str,
    answer_message: str,
    summary: str,
    analysis_kind: str,
    rows: list[dict[str, Any]],
    columns: list[str],
    retrieval_jobs: list[dict[str, Any]],
    pandas_plan: list[dict[str, Any]],
    pandas_code: str,
    metadata_refs: list[dict[str, Any]],
    function_case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    source_results = [
        {
            "dataset_key": job["dataset_key"],
            "source_alias": job["source_alias"],
            "source_type": job["source_type"],
            "status": "ok",
            "row_count": max(len(rows), 1),
            "columns": columns,
            "applied_params": job.get("required_params", {}),
            "pandas_filters": job.get("filters", {}),
            "source_execution": {"used_dummy_data": True, "adapter": "dummy", "filters_applied_in_retriever": False},
        }
        for job in retrieval_jobs
    ]
    return {
        "question": question,
        "answer_message": answer_message,
        "summary": summary,
        "rows": rows,
        "columns": columns,
        "intent_plan": {"analysis_kind": analysis_kind, "retrieval_jobs": retrieval_jobs, "pandas_execution_plan": pandas_plan},
        "metadata_refs": metadata_refs,
        "source_results": source_results,
        "pandas_code": pandas_code,
        "step_outputs": [
            {"key": "filtered_source", "description": "조회 결과에 분석 조건을 적용한 중간 데이터", "row_count": max(len(rows), 1), "columns": columns, "preview_rows": rows[:3]},
            {"key": "result", "description": "최종 집계 결과", "row_count": len(rows), "columns": columns, "preview_rows": rows[:3]},
        ],
        "function_case_results": function_case_results,
        "used_helpers": ["match_product_tokens"] if function_case_results else [],
        "intent_trace": {
            "stage": "04_intent_plan_normalizer",
            "status": "ok",
            "analysis_kind": analysis_kind,
            "retrieval_job_count": len(retrieval_jobs),
            "pandas_step_count": len(pandas_plan),
            "decision_reason": _decision_reason(question, analysis_kind),
        },
        "retrieval_trace": {
            "stage": "13_source_retrieval_merger",
            "status": "ok",
            "executed_source_count": len(retrieval_jobs),
            "sources": source_results,
        },
        "pandas_trace": {
            "stage": "17_pandas_code_executor",
            "status": "ok",
            "generated_code": pandas_code,
            "llm_generated_code": pandas_code,
            "effective_code_with_helpers": pandas_code,
            "used_helpers": ["match_product_tokens"] if function_case_results else [],
            "pandas_filter_plan": [job.get("filters", {}) for job in retrieval_jobs if job.get("filters")],
            "execution_result": {"row_count": len(rows), "columns": columns},
            "step_outputs": [
                {"key": "result", "description": "더미 pandas 실행 결과", "row_count": len(rows), "columns": columns, "preview_rows": rows[:3]}
            ],
            "function_case_results": function_case_results,
        },
    }


def _decision_reason(question: str, analysis_kind: str) -> list[str]:
    reasons = [f"사용자 질문 '{question}'을 더미 분석 시나리오 `{analysis_kind}`로 분류했습니다."]
    if "product" in analysis_kind or "제품" in question:
        reasons.append("제품 조건이 포함되어 제품/공정 기준의 pandas 전처리와 집계를 계획했습니다.")
    reasons.append("실제 DB 조회 없이 dummy source를 사용하되, 실제 data_analysis_flow의 응답 구조와 동일한 진단 정보를 구성했습니다.")
    return reasons


def _display_message(fixture: dict[str, Any]) -> str:
    sections = [
        "### 답변\n" + fixture["answer_message"],
        "### 결과 테이블\n" + _markdown_table(fixture["rows"], fixture["columns"]) + f"\n\n총 {len(fixture['rows'])}건입니다.",
        _intent_section(fixture),
        _retrieval_section(fixture),
        _pandas_section(fixture),
    ]
    if fixture["function_case_results"]:
        sections.insert(2, _function_case_section(fixture["function_case_results"]))
    return "\n\n".join(section for section in sections if section)


def _intent_section(fixture: dict[str, Any]) -> str:
    plan = fixture["intent_plan"]
    lines = [
        "### 의도 분석",
        f"- 분석 유형: `{plan['analysis_kind']}`",
        f"- 조회 작업 수: `{len(plan['retrieval_jobs'])}`",
        f"- pandas 단계 수: `{len(plan['pandas_execution_plan'])}`",
        "- 참조 메타데이터: `" + _json(fixture["metadata_refs"]) + "`",
        "- 의도 판단 근거:",
    ]
    for index, reason in enumerate(fixture["intent_trace"]["decision_reason"], start=1):
        lines.append(f"  {index}. {reason}")
    lines.append("- 조회 계획:")
    for job in plan["retrieval_jobs"]:
        lines.append("  - " + _retrieval_job_label(job))
    lines.append("- pandas 실행 계획:")
    for index, step in enumerate(plan["pandas_execution_plan"], start=1):
        lines.append(f"  {index}. `{_json(step)}`")
    return "\n".join(lines)


def _retrieval_section(fixture: dict[str, Any]) -> str:
    lines = [
        "### 데이터 조회",
        "- 상태: `ok`",
        f"- 실행 소스 수: `{len(fixture['source_results'])}`",
        "- 조회 결과:",
    ]
    for source in fixture["source_results"]:
        lines.append("  - " + _source_result_label(source))
    return "\n".join(lines)


def _pandas_section(fixture: dict[str, Any]) -> str:
    return "\n".join(
        [
            "### pandas 코드/실행",
            "- 상태: `ok`",
            f"- 결과 행 수: `{len(fixture['rows'])}`",
            "- 결과 컬럼: `" + _json(fixture["columns"]) + "`",
            "- 실제 실행 pandas 코드:",
            "```python\n" + fixture["pandas_code"] + "\n```",
        ]
    )


def _function_case_section(results: list[dict[str, Any]]) -> str:
    lines = ["### 제품/조건 매핑 결과"]
    for item in results:
        lines.append(f"- 제품 표현 `{item.get('input_text', '')}` 기준으로 `{item.get('matched_count', 0)}`개 제품이 매칭되었습니다.")
        preview = item.get("preview_rows") if isinstance(item.get("preview_rows"), list) else []
        columns = item.get("columns") if isinstance(item.get("columns"), list) else []
        if preview and columns:
            lines.append(_markdown_table(preview[:3], columns))
    return "\n".join(lines)


def _retrieval_job_label(job: dict[str, Any]) -> str:
    parts = []
    for label, key in (("데이터셋", "dataset_key"), ("소스 별칭", "source_alias"), ("소스 유형", "source_type"), ("조회 파라미터", "required_params"), ("pandas 필터", "filters")):
        value = job.get(key)
        if value not in (None, "", [], {}):
            parts.append(f"{label}={_json(value)}")
    return ", ".join(parts)


def _source_result_label(source: dict[str, Any]) -> str:
    execution = source.get("source_execution") if isinstance(source.get("source_execution"), dict) else {}
    parts = []
    for label, key in (("데이터셋", "dataset_key"), ("소스 별칭", "source_alias"), ("소스 유형", "source_type"), ("상태", "status"), ("행 수", "row_count"), ("적용 파라미터", "applied_params"), ("pandas 필터", "pandas_filters")):
        value = source.get(key)
        if value not in (None, "", [], {}):
            parts.append(f"{label}={_json(value)}")
    parts.append(f"더미 사용={'예' if execution.get('used_dummy_data') else '아니오'}")
    return ", ".join(parts)


def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    header = "| " + " | ".join(str(column) for column in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(_table_cell(row.get(column, "")) for column in columns) + " |")
    return "\n".join([header, divider] + body)


def _table_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        text = _json(value)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        text = f"{value / 1000:,.1f}K" if abs(value) >= 10000 else f"{value:,}"
    else:
        text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def _json(value: Any) -> str:
    return deepcopy(value) if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


class DummyDataAnalysisResponseBuilder(Component):
    display_name = "01 더미 분석 응답 생성기"
    description = "실제 데이터 분석 flow와 같은 형태의 더미 API 응답과 메시지를 생성합니다."
    inputs = [DataInput(name="payload", display_name="페이로드", required=True)]
    outputs = [
        Output(name="api_response", display_name="API 응답", method="build_api_response", types=["Data"], group_outputs=True),
        Output(name="message", display_name="메시지", method="build_message", types=["Message"], group_outputs=True),
    ]

    def build_api_response(self) -> Data:
        return Data(data=build_dummy_response(getattr(self, "payload", None)))

    def build_message(self) -> Message:
        return Message(text=build_dummy_response(getattr(self, "payload", None))["message"])
