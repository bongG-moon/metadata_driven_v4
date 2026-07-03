from __future__ import annotations

import base64
import json
import re
from copy import deepcopy
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.message import Message

TABLE_PREVIEW_LIMIT = 10
CELL_TEXT_LIMIT = 120
VALUE_TEXT_LIMIT = 900
DEFAULT_DOWNLOAD_BASE_URL = "http://localhost:8765"


def build_message(payload_value: Any, download_base_url: Any = "") -> str:
    payload = _payload(payload_value)
    if not payload:
        return ""

    sections: list[str] = []
    answer = str(payload.get("answer_message") or "").strip()
    if answer:
        sections.append("### 답변\n" + _escape_markdown_tilde(answer))

    result_table_section = "" if _contains_markdown_table(answer) else _result_table_section(payload)
    for section in (
        result_table_section,
        _intent_section(payload),
        _retrieval_section(payload),
        _pandas_section(payload),
        _download_links_section(payload, download_base_url),
        _notice_section(payload),
    ):
        if section:
            sections.append(section)

    if sections:
        return "\n\n".join(sections)
    return json.dumps(payload, ensure_ascii=False, default=str)


def _payload(value: Any) -> dict[str, Any]:
    data = getattr(value, "data", value)
    return deepcopy(data) if isinstance(data, dict) else {}


def _contains_markdown_table(text: str) -> bool:
    lines = [line.strip() for line in str(text or "").splitlines()]
    for index in range(len(lines) - 1):
        if "|" not in lines[index] or "|" not in lines[index + 1]:
            continue
        divider = lines[index + 1].replace("|", "").replace(":", "").replace("-", "").strip()
        if not divider:
            return True
    return False


def _result_table_section(payload: dict[str, Any]) -> str:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    columns = data.get("columns") if isinstance(data.get("columns"), list) else []
    row_count = int(data.get("row_count") or len(rows) or 0)

    if not rows and not columns and not data:
        return ""
    if not columns:
        columns = _columns_from_rows(rows)
    if not rows:
        column_text = ", ".join(str(column) for column in columns) if columns else "없음"
        return "### 결과 테이블\n표시할 결과 행이 없습니다.\n\n- 컬럼: `" + column_text + "`"

    preview_rows = rows[:TABLE_PREVIEW_LIMIT]
    note = f"\n\n총 {row_count}건 중 {len(preview_rows)}건을 표시했습니다."
    if row_count <= len(preview_rows):
        note = f"\n\n총 {row_count}건입니다."
    return "### 결과 테이블\n" + _markdown_table(preview_rows, columns) + note


def _intent_section(payload: dict[str, Any]) -> str:
    plan = payload.get("intent_plan") if isinstance(payload.get("intent_plan"), dict) else {}
    metadata_refs = payload.get("metadata_refs") if isinstance(payload.get("metadata_refs"), list) else []
    inspection = _inspection(payload).get("intent")
    intent_trace = inspection if isinstance(inspection, dict) else {}
    if not plan and not metadata_refs and not intent_trace:
        return ""

    retrieval_jobs = plan.get("retrieval_jobs") if isinstance(plan.get("retrieval_jobs"), list) else []
    pandas_plan = plan.get("pandas_execution_plan") if isinstance(plan.get("pandas_execution_plan"), list) else []
    lines = ["### 의도 분석"]
    for label, value in (
        ("분석 유형", plan.get("analysis_kind") or intent_trace.get("analysis_kind")),
        ("조회 작업 수", intent_trace.get("retrieval_job_count") if "retrieval_job_count" in intent_trace else len(retrieval_jobs)),
        ("pandas 단계 수", intent_trace.get("pandas_step_count") if "pandas_step_count" in intent_trace else len(pandas_plan)),
        ("참조 메타데이터", metadata_refs),
    ):
        if value not in (None, "", [], {}):
            lines.append(f"- {label}: `{_display_value(value)}`")

    reasons = _list_value(intent_trace.get("decision_reason")) or _list_value(plan.get("decision_reason"))
    if reasons:
        lines.append("- 의도 판단 근거:")
        for index, reason in enumerate(reasons[:8], start=1):
            lines.append(f"  {index}. {_display_text(reason)}")

    if retrieval_jobs:
        lines.append("- 조회 계획:")
        for job in retrieval_jobs[:8]:
            lines.append("  - " + _retrieval_job_label(job))

    if pandas_plan:
        lines.append("- pandas 실행 계획:")
        for index, step in enumerate(pandas_plan[:8], start=1):
            lines.append(f"  {index}. {_display_value(step)}")

    return "\n".join(lines)


def _retrieval_section(payload: dict[str, Any]) -> str:
    source_results = payload.get("source_results") if isinstance(payload.get("source_results"), list) else []
    retrieval_trace = _inspection(payload).get("data_retrieval")
    retrieval_trace = retrieval_trace if isinstance(retrieval_trace, dict) else {}
    if not source_results and not retrieval_trace:
        return ""

    lines = ["### 데이터 조회"]
    for label, value in (
        ("상태", retrieval_trace.get("status")),
        ("실행 소스 수", retrieval_trace.get("executed_source_count")),
        ("스킵 소스", retrieval_trace.get("skipped_sources")),
    ):
        if value not in (None, "", [], {}):
            lines.append(f"- {label}: `{_display_value(value)}`")

    sources = source_results or retrieval_trace.get("sources")
    if isinstance(sources, list) and sources:
        lines.append("- 조회 결과:")
        for source in sources[:8]:
            lines.append("  - " + _source_result_label(source))
    return "\n".join(lines)


def _pandas_section(payload: dict[str, Any]) -> str:
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    pandas_trace = _inspection(payload).get("pandas_execution")
    pandas_trace = pandas_trace if isinstance(pandas_trace, dict) else {}
    if not analysis and not pandas_trace:
        return ""

    execution_result = pandas_trace.get("execution_result") if isinstance(pandas_trace.get("execution_result"), dict) else {}
    lines = ["### pandas 코드/실행"]
    for label, value in (
        ("상태", pandas_trace.get("status") or analysis.get("status")),
        ("결과 행 수", execution_result.get("row_count") if "row_count" in execution_result else analysis.get("row_count")),
        ("결과 컬럼", execution_result.get("columns") or analysis.get("columns")),
        ("pandas 필터 전처리", pandas_trace.get("pandas_filter_plan")),
    ):
        if value not in (None, "", [], {}):
            lines.append(f"- {label}: `{_display_value(value)}`")

    error = pandas_trace.get("error") or analysis.get("error")
    if error not in (None, "", [], {}):
        lines.append(f"- 실행 오류: `{_display_value(error)}`")

    used_helpers = pandas_trace.get("used_helpers") or analysis.get("used_helpers")
    if used_helpers not in (None, "", [], {}):
        lines.append(f"- 사용 helper: `{_display_value(used_helpers)}`")

    effective_code = str(pandas_trace.get("effective_code_with_helpers") or analysis.get("effective_code_with_helpers") or "").strip()
    code = effective_code or str(pandas_trace.get("generated_code") or analysis.get("analysis_code") or "").strip()
    pandas_code_json = analysis.get("pandas_code_json") if isinstance(analysis.get("pandas_code_json"), dict) else {}
    if not code:
        code = str(pandas_code_json.get("code") or "").strip()
    if code:
        label = "실제 실행 pandas 코드" if effective_code else "생성된 pandas 코드"
        lines.append(f"- {label}:")
        lines.append("```python\n" + code + "\n```")

    return "\n".join(lines)


def _notice_section(payload: dict[str, Any]) -> str:
    trace = payload.get("trace") if isinstance(payload.get("trace"), dict) else {}
    warnings = _list_value(trace.get("warnings")) + _list_value(payload.get("warnings"))
    errors = _list_value(trace.get("errors")) + _list_value(payload.get("errors"))
    if not warnings and not errors:
        return ""

    lines = ["### 경고/오류"]
    if warnings:
        lines.append("- 경고:")
        for item in warnings[:12]:
            lines.append(f"  - {_display_value(item)}")
    if errors:
        lines.append("- 오류:")
        for item in errors[:12]:
            lines.append(f"  - {_display_value(item)}")
    return "\n".join(lines)


def _download_links_section(payload: dict[str, Any], download_base_url: Any = "") -> str:
    refs = _downloadable_data_refs(payload)
    if not refs:
        return ""
    lines = ["### 데이터 다운로드"]
    for ref in refs[:12]:
        label = _download_label(ref)
        url = _download_url(ref, download_base_url)
        lines.append(f"- [{_escape_markdown_tilde(label)}]({url})")
    lines.append("- 링크는 MongoDB result store의 `data_ref`를 웹 다운로드 화면으로 여는 용도입니다.")
    return "\n".join(lines)


def _downloadable_data_refs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for ref in _list_value(payload.get("data_refs")):
        if isinstance(ref, dict):
            _append_ref(refs, ref)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    data_ref = data.get("data_ref")
    if isinstance(data_ref, dict):
        _append_ref(refs, data_ref)
    return refs


def _append_ref(refs: list[dict[str, Any]], ref: dict[str, Any]) -> None:
    ref_id = str(ref.get("ref_id") or "").strip()
    if not ref_id:
        return
    signature = "|".join(str(ref.get(key) or "") for key in ("ref_id", "path", "role", "source_alias"))
    if any("|".join(str(existing.get(key) or "") for key in ("ref_id", "path", "role", "source_alias")) == signature for existing in refs):
        return
    refs.append(ref)


def _download_label(ref: dict[str, Any]) -> str:
    label = str(ref.get("label") or "").strip()
    if label:
        return label + " CSV 다운로드"
    role = str(ref.get("role") or "").strip()
    alias = str(ref.get("source_alias") or ref.get("dataset_key") or "").strip()
    if role == "source_rows" and alias:
        return f"사용 원본 데이터 {alias} CSV 다운로드"
    if role == "analysis_result":
        return "분석 결과 데이터 CSV 다운로드"
    return "저장 데이터 CSV 다운로드"


def _download_url(ref: dict[str, Any], download_base_url: Any = "") -> str:
    base_url = str(download_base_url or "").strip() or DEFAULT_DOWNLOAD_BASE_URL
    token = base64.urlsafe_b64encode(json.dumps(ref, ensure_ascii=False, default=str).encode("utf-8")).decode("ascii").rstrip("=")
    return f"{base_url.rstrip('/')}/?download_ref={token}"


def _inspection(payload: dict[str, Any]) -> dict[str, Any]:
    trace = payload.get("trace") if isinstance(payload.get("trace"), dict) else {}
    inspection = trace.get("inspection")
    return inspection if isinstance(inspection, dict) else {}


def _retrieval_job_label(job: Any) -> str:
    if not isinstance(job, dict):
        return _display_value(job)
    parts = []
    for label, key in (
        ("데이터셋", "dataset_key"),
        ("소스 별칭", "source_alias"),
        ("소스 유형", "source_type"),
        ("조회 파라미터", "required_params"),
        ("조회 필터", "filters"),
    ):
        value = job.get(key)
        if value not in (None, "", [], {}):
            parts.append(f"{label}={_display_value(value)}")
    return ", ".join(parts) if parts else _display_value(job)


def _source_result_label(source: Any) -> str:
    if not isinstance(source, dict):
        return _display_value(source)
    execution = source.get("source_execution") if isinstance(source.get("source_execution"), dict) else {}
    parts = []
    for label, key in (
        ("데이터셋", "dataset_key"),
        ("소스 별칭", "source_alias"),
        ("소스 유형", "source_type"),
        ("상태", "status"),
        ("행 수", "row_count"),
        ("data_ref", "data_ref"),
        ("적용 파라미터", "applied_params"),
        ("pandas 필터", "pandas_filters"),
    ):
        value = source.get(key)
        if value not in (None, "", [], {}):
            parts.append(f"{label}={_display_value(value)}")
    legacy_filters = source.get("applied_filters")
    if legacy_filters not in (None, "", [], {}):
        parts.append(f"pandas 필터={_display_value(legacy_filters)}")
    if execution.get("used_dummy_data") not in (None, "", [], {}):
        parts.append(f"더미 사용={_display_value(execution.get('used_dummy_data'))}")
    if source.get("errors") not in (None, "", [], {}):
        parts.append(f"오류={_display_value(source.get('errors'))}")
    return ", ".join(parts) if parts else _display_value(source)


def _markdown_table(rows: list[Any], columns: list[Any]) -> str:
    cleaned_columns = [str(column) for column in columns if str(column or "").strip()]
    if not cleaned_columns:
        cleaned_columns = _columns_from_rows(rows)
    header = "| " + " | ".join(_escape_table_cell(column) for column in cleaned_columns) + " |"
    divider = "| " + " | ".join("---" for _ in cleaned_columns) + " |"
    body = []
    for row in rows:
        row_dict = row if isinstance(row, dict) else {}
        body.append("| " + " | ".join(_escape_table_cell(row_dict.get(column, "")) for column in cleaned_columns) + " |")
    return "\n".join([header, divider] + body)


def _columns_from_rows(rows: list[Any]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in row:
            text = str(key)
            if text not in columns:
                columns.append(text)
    return columns


def _escape_table_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = "" if value is None else str(value)
    text = _truncate(text.replace("\n", "<br>"), CELL_TEXT_LIMIT)
    return _escape_markdown_tilde(text.replace("|", "\\|"))


def _escape_markdown_tilde(text: str) -> str:
    return re.sub(r"(?<!\\)~", r"\\~", text)


def _display_value(value: Any) -> str:
    if isinstance(value, bool):
        return "예" if value else "아니오"
    if isinstance(value, str):
        return _truncate(value.strip(), VALUE_TEXT_LIMIT)
    if isinstance(value, (list, dict)):
        return _truncate(json.dumps(value, ensure_ascii=False, default=str), VALUE_TEXT_LIMIT)
    return str(value)


def _display_text(value: Any) -> str:
    if isinstance(value, str):
        return _escape_markdown_tilde(value.strip())
    return "`" + _display_value(value) + "`"


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)] + "..."


class AnswerMessageAdapter(Component):
    display_name = "21 답변 메시지 어댑터"
    description = "최종 답변, 결과 테이블, 의도 분석, 데이터 조회, pandas 코드를 채팅 출력용 메시지로 변환합니다."
    inputs = [
        DataInput(name="payload", display_name="페이로드", required=True),
        MessageTextInput(
            name="download_base_url",
            display_name="다운로드 링크 Base URL",
            value=DEFAULT_DOWNLOAD_BASE_URL,
            required=False,
            advanced=True,
        ),
    ]
    outputs = [Output(name="message", display_name="메시지", method="build_output_message", types=["Message"])]

    def build_output_message(self) -> Message:
        return Message(text=build_message(getattr(self, "payload", None), getattr(self, "download_base_url", "")))
