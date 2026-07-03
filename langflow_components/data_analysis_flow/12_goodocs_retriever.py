from __future__ import annotations

import os
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, MessageTextInput, Output
from lfx.schema.data import Data


PREVIEW_LIMIT = 20


def goodocs_retrieve(
    payload_value: Any,
    user_id: Any = "",
    token: Any = "",
    token_source: Any = "",
    token_key: Any = "",
    fetch_limit: Any = "",
    client: Any = None,
) -> dict[str, Any]:
    payload = _payload(payload_value)
    jobs = _jobs_for_source(payload)
    if not jobs:
        return _skipped("goodocs", "no goodocs retrieval jobs")

    limit = _fetch_limit(fetch_limit or os.getenv("SOURCE_FETCH_LIMIT", "5000"))
    godocs_client = client or GodocsClient(
        user_id=str(user_id or os.getenv("GOODOCS_USER_ID", "")).strip(),
        token=str(token or os.getenv("GOODOCS_TOKEN", "")).strip(),
        token_source=str(token_source or os.getenv("GOODOCS_TOKEN_SOURCE", "")).strip(),
        token_key=str(token_key or os.getenv("GOODOCS_TOKEN_KEY", "")).strip(),
    )
    results = [_run_goodocs_job(job, godocs_client, limit) for job in jobs]
    errors = [error for result in results for error in result.get("errors", []) if isinstance(error, dict)]
    warnings = [warning for result in results for warning in result.get("warnings", []) if isinstance(warning, dict)]
    return {
        "source_type": "goodocs",
        "status": "error" if errors else "ok",
        "skipped": False,
        "executed_jobs": [str(job.get("job_id") or job.get("dataset_key") or index) for index, job in enumerate(jobs, 1)],
        "source_results": results,
        "errors": errors,
        "warnings": warnings,
    }


def _run_goodocs_job(job: dict[str, Any], client: "GodocsClient", fetch_limit: int) -> dict[str, Any]:
    source_config = _source_config(job)
    params = _job_params(job)
    missing = _missing_required_params(params, _required_param_names(job, source_config))
    if missing:
        return _error_result(job, "missing_required_params", f"필수 파라미터가 없습니다: {', '.join(missing)}", params=params)

    if not _has_goodocs_source(source_config):
        return _error_result(job, "missing_goodocs_source", "Goodocs source_config에 doc_id 또는 테스트용 rows/data가 없습니다.", params=params)

    try:
        rows = client.fetch_rows(source_config=source_config, params=params, fetch_limit=fetch_limit)
        rows = [_row_dict(row) for row in _rows_from_value(rows)[:fetch_limit]]
        rows = _json_ready(rows)
        return _standard_result(job, rows, params, source_config)
    except Exception as exc:
        return _error_result(job, "goodocs_retrieval_failed", f"Goodocs 조회 실패: {exc}", params=params)


class GodocsClient:
    def __init__(self, user_id: str = "", token: str = "", token_source: str = "", token_key: str = ""):
        self.user_id = user_id
        self.token = token
        self.token_source = token_source
        self.token_key = token_key

    def fetch_rows(self, source_config: dict[str, Any], params: dict[str, Any], fetch_limit: int) -> list[dict[str, Any]]:
        for key in ("rows", "data", "items"):
            if isinstance(source_config.get(key), list):
                return deepcopy(source_config[key])[:fetch_limit]
        raise NotImplementedError("GodocsClient.fetch_rows를 실제 환경용 Goodocs 조회 class로 교체해야 합니다.")


GoodocsClient = GodocsClient


def _jobs_for_source(payload: dict[str, Any]) -> list[dict[str, Any]]:
    bundle = payload.get("retrieval_job_bundle") if isinstance(payload.get("retrieval_job_bundle"), dict) else {}
    bundle_jobs = bundle.get("jobs") if isinstance(bundle.get("jobs"), list) else []
    if bundle_jobs:
        return [deepcopy(job) for job in bundle_jobs if isinstance(job, dict)]
    plan = payload.get("intent_plan") if isinstance(payload.get("intent_plan"), dict) else {}
    jobs = plan.get("retrieval_jobs") if isinstance(plan.get("retrieval_jobs"), list) else []
    return [deepcopy(job) for job in jobs if isinstance(job, dict) and _source_type(job.get("source_type")) in {"goodocs", "godocs"}]


def _source_config(job: dict[str, Any]) -> dict[str, Any]:
    config = deepcopy(job.get("source_config")) if isinstance(job.get("source_config"), dict) else {}
    for key in ("doc_id", "document_id", "sheet_name", "sheet", "range", "table_name", "columns", "required_columns", "rows", "data", "items"):
        if job.get(key) not in (None, "", [], {}):
            config.setdefault(key, deepcopy(job[key]))
    return config


def _job_params(job: dict[str, Any]) -> dict[str, Any]:
    if isinstance(job.get("params"), dict):
        return deepcopy(job["params"])
    if isinstance(job.get("required_params"), dict):
        return deepcopy(job["required_params"])
    return {}


def _required_param_names(job: dict[str, Any], source_config: dict[str, Any]) -> list[Any]:
    if isinstance(source_config.get("required_params"), (list, tuple, set)):
        return _as_list(source_config.get("required_params"))
    if isinstance(job.get("required_param_names"), (list, tuple, set)):
        return _as_list(job.get("required_param_names"))
    if not isinstance(job.get("required_params"), dict):
        return _as_list(job.get("required_params"))
    return []


def _has_goodocs_source(source_config: dict[str, Any]) -> bool:
    if source_config.get("doc_id") or source_config.get("document_id"):
        return True
    return any(isinstance(source_config.get(key), list) for key in ("rows", "data", "items"))


def _standard_result(job: dict[str, Any], rows: list[dict[str, Any]], params: dict[str, Any], source_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_alias": job.get("source_alias") or job.get("dataset_key"),
        "dataset_key": job.get("dataset_key"),
        "source_type": "goodocs",
        "status": "ok",
        "row_count": len(rows),
        "columns": _rows_columns(rows),
        "preview_rows": rows[:PREVIEW_LIMIT],
        "rows": rows,
        "applied_params": deepcopy(params),
        "pandas_filters": deepcopy(job.get("filters", {})),
        "data_ref": "",
        "source_execution": {
            "used_dummy_data": False,
            "adapter": "goodocs",
            "doc_id": source_config.get("doc_id") or source_config.get("document_id") or "",
            "sheet_name": source_config.get("sheet_name") or source_config.get("sheet") or "",
            "range": source_config.get("range") or "",
            "source_configured": True,
            "filters_applied_in_retriever": False,
        },
        "warnings": [],
        "errors": [],
    }


def _error_result(job: dict[str, Any], error_type: str, message: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    error = {"type": error_type, "message": message, "dataset_key": job.get("dataset_key", "")}
    return {
        "source_alias": job.get("source_alias") or job.get("dataset_key"),
        "dataset_key": job.get("dataset_key"),
        "source_type": "goodocs",
        "status": "error",
        "row_count": 0,
        "columns": [],
        "preview_rows": [],
        "rows": [],
        "applied_params": deepcopy(params if params is not None else _job_params(job)),
        "pandas_filters": deepcopy(job.get("filters", {})),
        "data_ref": "",
        "source_execution": {"used_dummy_data": False, "adapter": "goodocs", "source_configured": False},
        "warnings": [],
        "errors": [error],
    }


def _missing_required_params(params: dict[str, Any], required_params: Any) -> list[str]:
    missing = []
    for item in _as_list(required_params):
        key = str(item or "").strip()
        if key and _dict_get_ci(params, key) in (None, "", []):
            missing.append(key)
    return missing


def _rows_from_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("rows", "data", "items", "result", "results", "records"):
            if isinstance(value.get(key), list):
                return value[key]
            if isinstance(value.get(key), dict):
                nested = _rows_from_value(value[key])
                if nested:
                    return nested
        return [value]
    if value in (None, ""):
        return []
    if hasattr(value, "to_dict"):
        try:
            return value.to_dict(orient="records")
        except TypeError:
            return value.to_dict()
    return [{"value": value}]


def _row_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return {"value": _json_ready(value)}


def _rows_columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            text = str(key)
            if text not in columns:
                columns.append(text)
    return columns


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    try:
        if value != value:
            return None
    except Exception:
        pass
    return str(value)


def _fetch_limit(value: Any) -> int:
    try:
        return max(1, int(value or 5000))
    except Exception:
        return 5000


def _source_type(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", "").replace("-", "").replace(" ", "")


def _dict_get_ci(mapping: dict[str, Any], key: Any, default: Any = None) -> Any:
    if not isinstance(mapping, dict):
        return default
    text = str(key or "").strip()
    if text in mapping:
        return mapping[text]
    normalized = _normalize_key(text)
    for item_key, value in mapping.items():
        if _normalize_key(item_key) == normalized:
            return value
    return default


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return [value]


def _payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    data = getattr(value, "data", None)
    return deepcopy(data) if isinstance(data, dict) else {}


def _skipped(source_type: str, reason: str) -> dict[str, Any]:
    return {"source_type": source_type, "status": "skipped", "skipped": True, "skip_reason": reason, "source_results": [], "errors": [], "warnings": []}


class GoodocsRetriever(Component):
    display_name = "12 Goodocs 조회기"
    description = "table catalog의 Goodocs source_config를 사용해 문서/시트 데이터를 조회합니다."
    inputs = [
        DataInput(name="payload", display_name="페이로드", required=True),
        MessageTextInput(name="user_id", display_name="Goodocs 사용자 ID", required=False, value="", advanced=True),
        MessageTextInput(name="token", display_name="Goodocs 토큰", required=False, value="", advanced=True),
        MessageTextInput(name="token_source", display_name="Goodocs 토큰 소스", required=False, value="", advanced=True),
        MessageTextInput(name="token_key", display_name="Goodocs 토큰 키", required=False, value="", advanced=True),
        MessageTextInput(name="fetch_limit", display_name="조회 제한 건수", required=False, value="5000", advanced=True),
    ]
    outputs = [Output(name="retrieval_payload", display_name="조회 페이로드", method="build_payload")]

    def build_payload(self) -> Data:
        return Data(
            data=goodocs_retrieve(
                getattr(self, "payload", None),
                getattr(self, "user_id", ""),
                getattr(self, "token", ""),
                getattr(self, "token_source", ""),
                getattr(self, "token_key", ""),
                getattr(self, "fetch_limit", ""),
            )
        )
