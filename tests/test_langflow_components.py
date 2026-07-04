from __future__ import annotations

import ast
import importlib.util
import json
import sys
import types
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT_FILES = sorted(
    path
    for path in (ROOT / "langflow_components").glob("*/*.py")
    if not path.name.endswith("_input_example.py")
)


def install_lfx_test_stubs() -> None:
    if importlib.util.find_spec("lfx") is not None:
        return

    class Component:
        pass

    class Data:
        def __init__(self, data=None):
            self.data = data or {}

    class Message:
        def __init__(self, text=""):
            self.text = text

    class InputBase:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    modules = {
        "lfx": types.ModuleType("lfx"),
        "lfx.custom": types.ModuleType("lfx.custom"),
        "lfx.custom.custom_component": types.ModuleType("lfx.custom.custom_component"),
        "lfx.custom.custom_component.component": types.ModuleType("lfx.custom.custom_component.component"),
        "lfx.io": types.ModuleType("lfx.io"),
        "lfx.schema": types.ModuleType("lfx.schema"),
        "lfx.schema.data": types.ModuleType("lfx.schema.data"),
        "lfx.schema.message": types.ModuleType("lfx.schema.message"),
    }
    modules["lfx.custom.custom_component.component"].Component = Component
    modules["lfx.io"].DataInput = InputBase
    modules["lfx.io"].DropdownInput = InputBase
    modules["lfx.io"].MessageTextInput = InputBase
    modules["lfx.io"].Output = InputBase
    modules["lfx.schema.data"].Data = Data
    modules["lfx.schema.message"].Message = Message
    for name, module in modules.items():
        sys.modules.setdefault(name, module)


install_lfx_test_stubs()


def function_case_source(*function_names: str) -> str:
    source = (
        ROOT
        / "langflow_components"
        / "data_analysis_flow"
        / "function_case_helper_code_input_example.py"
    ).read_text(encoding="utf-8")
    if not function_names:
        return source
    tree = ast.parse(source)
    source_lines = source.splitlines()
    blocks = []
    requested = set(function_names)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in requested:
            blocks.append("\n".join(source_lines[node.lineno - 1 : node.end_lineno]))
    return "\n\n".join(blocks)


def install_fake_pymongo(monkeypatch):
    store = {}

    class FakeCursor:
        def __init__(self, docs):
            self.docs = docs
            self.limit_value = None

        def limit(self, value):
            self.limit_value = int(value)
            return self

        def __iter__(self):
            docs = self.docs[: self.limit_value] if self.limit_value is not None else self.docs
            return iter(deepcopy(docs))

    class FakeCollection:
        def __init__(self, docs):
            self.docs = docs

        def find(self, query=None, projection=None):
            query = query or {}
            rows = [self._project(doc, projection) for doc in self.docs.values() if self._matches(doc, query)]
            return FakeCursor(rows)

        def find_one(self, query=None, projection=None):
            query = query or {}
            for doc in self.docs.values():
                if self._matches(doc, query):
                    return self._project(doc, projection)
            return None

        def replace_one(self, query, doc, upsert=False):
            doc_id = query.get("_id") or doc.get("_id")
            self.docs[doc_id] = deepcopy(doc)

        @staticmethod
        def _matches(doc, query):
            return all(doc.get(key) == value for key, value in query.items())

        @staticmethod
        def _project(doc, projection):
            projected = deepcopy(doc)
            if projection and projection.get("_id") == 0:
                projected.pop("_id", None)
            return projected

    class FakeDatabase:
        def __init__(self, collections):
            self.collections = collections

        def __getitem__(self, collection_name):
            return FakeCollection(self.collections.setdefault(collection_name, {}))

    class FakeMongoClient:
        def __init__(self, uri, serverSelectionTimeoutMS=5000):
            self.uri = uri
            self.server_selection_timeout_ms = serverSelectionTimeoutMS

        def __getitem__(self, database_name):
            return FakeDatabase(store.setdefault(database_name, {}))

        def close(self):
            pass

    module = types.ModuleType("pymongo")
    module.MongoClient = FakeMongoClient
    monkeypatch.setitem(sys.modules, "pymongo", module)
    return store


def set_v4_mongo_env(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "mongodb://fake")
    monkeypatch.setenv("MONGODB_DATABASE", "datagov")
    monkeypatch.setenv("MONGODB_DOMAIN_COLLECTION", "agent_v4_domain_items")
    monkeypatch.setenv("MONGODB_TABLE_CATALOG_COLLECTION", "agent_v4_table_catalog_items")
    monkeypatch.setenv("MONGODB_MAIN_FLOW_FILTER_COLLECTION", "agent_v4_main_flow_filters")
    monkeypatch.setenv("MONGODB_RESULT_COLLECTION", "agent_v4_result_store")


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_langflow_components_do_not_import_project_helpers():
    forbidden = {"reference_runtime", "langflow_components", "utils", "helpers"}
    assert COMPONENT_FILES
    for path in COMPONENT_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0, f"{path.name} uses relative import"
                if node.module:
                    assert node.module.split(".")[0] not in forbidden, path.name
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden, path.name


def test_langflow_components_use_direct_lfx_imports_without_fallback_stubs():
    for path in COMPONENT_FILES:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        assert "from lfx.custom.custom_component.component import Component" in text
        assert "try:\n    from lfx" not in text, f"{path.name} has an lfx import fallback"
        local_classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        assert "Component" not in local_classes, f"{path.name} defines a local Component fallback"
        assert "DataInput" not in local_classes, f"{path.name} defines a local DataInput fallback"
        assert "Output" not in local_classes, f"{path.name} defines a local Output fallback"


def test_langflow_components_load_as_standalone_files():
    for path in COMPONENT_FILES:
        load_module(path)


def test_langflow_components_do_not_overlap_input_and_output_names():
    for path in COMPONENT_FILES:
        module = load_module(path)
        component_classes = [
            value
            for value in vars(module).values()
            if isinstance(value, type) and value.__module__ == module.__name__ and hasattr(value, "inputs") and hasattr(value, "outputs")
        ]
        for component_class in component_classes:
            input_names = {item.kwargs.get("name") for item in getattr(component_class, "inputs", []) if hasattr(item, "kwargs")}
            output_names = {item.kwargs.get("name") for item in getattr(component_class, "outputs", []) if hasattr(item, "kwargs")}
            assert not (input_names & output_names), f"{path.name} has overlapping input/output names: {input_names & output_names}"


def test_langflow_component_visible_labels_are_korean_first():
    def has_korean(text: str) -> bool:
        return any("\uac00" <= char <= "\ud7a3" for char in text)

    for path in COMPONENT_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id in {"display_name", "description"}
                        and isinstance(node.value, ast.Constant)
                        and isinstance(node.value.value, str)
                    ):
                        assert has_korean(node.value.value), f"{path.name}:{node.lineno} visible label is not Korean-first"
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if (
                        keyword.arg == "display_name"
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    ):
                        assert has_korean(keyword.value.value), f"{path.name}:{node.lineno} port label is not Korean-first"


def test_data_retriever_langflow_pipeline_dummy_path():
    validator = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "06_retrieval_job_validator.py")
    router = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "07_retrieval_job_router.py")
    dummy = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "08_dummy_data_retriever.py")
    merger = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "13_source_retrieval_merger.py")
    adapter = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "14_retrieval_payload_adapter.py")
    payload = {
        "intent_plan": {
            "retrieval_jobs": [
                {
                    "dataset_key": "wip_today",
                    "source_alias": "wip_data",
                    "source_type": "oracle",
                    "required_params": {"DATE": "20260701"},
                    "filters": {"OPER_NAME": {"operator": "in", "values": ["D/A1"]}},
                }
            ]
        }
    }

    validated = validator.validate_retrieval_payload(payload)
    dummy_bundle = router.route_retrieval_jobs(validated, "dummy")
    dummy_result = dummy.retrieve_dummy_data(dummy_bundle)
    merged = merger.merge_source_retrieval_payloads(validated, dummy_result)
    adapted = adapter.build_retrieval_payload(merged)
    output_names = {item.kwargs.get("name") for item in adapter.RetrievalPayloadAdapter.outputs}

    assert {"D/A1", "D/A2", "W/B1", "W/B2"}.issubset({row["OPER_NAME"] for row in adapted["runtime_sources"]["wip_data"]})
    assert adapted["source_results"][0]["source_execution"]["used_dummy_data"] is True
    assert adapted["source_results"][0]["source_execution"]["filters_applied_in_retriever"] is False
    assert adapted["source_results"][0]["pandas_filters"] == {"OPER_NAME": {"operator": "in", "values": ["D/A1"]}}
    assert output_names == {"payload_out"}
    assert "final_safe_payload" not in output_names


def test_retrieval_router_sends_jobs_only_to_dummy_when_live_disabled(monkeypatch):
    router = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "07_retrieval_job_router.py")
    monkeypatch.setenv("RUN_LIVE_SOURCE_RETRIEVAL", "true")
    payload = {
        "intent_plan": {
            "retrieval_jobs": [
                {"dataset_key": "wip_today", "source_alias": "wip_data", "source_type": "oracle"},
                {"dataset_key": "target", "source_alias": "target_data", "source_type": "goodocs"},
            ]
        }
    }
    input_names = {item.kwargs.get("name") for item in router.RetrievalJobRouter.inputs}

    dummy = router.route_retrieval_jobs(payload, "dummy", "dummy")
    oracle = router.route_retrieval_jobs(payload, "oracle", "dummy")
    goodocs = router.route_retrieval_jobs(payload, "goodocs", "dummy")

    assert "retrieval_mode" in input_names
    assert len(dummy["retrieval_job_bundle"]["jobs"]) == 2
    assert oracle["retrieval_job_bundle"]["jobs"] == []
    assert goodocs["retrieval_job_bundle"]["jobs"] == []


def test_retrieval_router_live_mode_routes_by_source_type(monkeypatch):
    router = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "07_retrieval_job_router.py")
    monkeypatch.setenv("RUN_LIVE_SOURCE_RETRIEVAL", "false")
    payload = {
        "intent_plan": {
            "retrieval_jobs": [
                {"dataset_key": "wip_today", "source_alias": "wip_data", "source_type": "oracle"},
                {"dataset_key": "target", "source_alias": "target_data", "source_type": "goodocs"},
            ]
        }
    }

    dummy = router.route_retrieval_jobs(payload, "dummy", "live")
    oracle = router.route_retrieval_jobs(payload, "oracle", "live")
    goodocs = router.route_retrieval_jobs(payload, "goodocs", "live")

    assert dummy["retrieval_job_bundle"]["jobs"] == []
    assert [job["dataset_key"] for job in oracle["retrieval_job_bundle"]["jobs"]] == ["wip_today"]
    assert [job["dataset_key"] for job in goodocs["retrieval_job_bundle"]["jobs"]] == ["target"]


def test_h_api_retriever_executes_configured_http_request():
    retriever = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "10_h_api_retriever.py")
    captured = {}

    class FakeResponse:
        def read(self):
            return b'{"data":{"rows":[{"DEVICE":"D1","QTY":12}]}}'

    def fake_open(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["method"] = request.get_method()
        return FakeResponse()

    payload = {
        "retrieval_job_bundle": {
            "jobs": [
                {
                    "dataset_key": "api_dataset",
                    "source_alias": "api_data",
                    "source_type": "h_api",
                    "source_config": {
                        "api_url": "https://example.test/items/{DATE}",
                        "method": "GET",
                        "response_path": "data.rows",
                    },
                    "required_params": {"DATE": "20260701", "PLANT": "PNT"},
                }
            ]
        }
    }

    result = retriever.h_api_retrieve(payload, api_token="token", timeout_seconds="7", opener=fake_open)
    source_result = result["source_results"][0]

    assert result["status"] == "ok"
    assert captured["method"] == "GET"
    assert captured["timeout"] == 7
    assert captured["url"].startswith("https://example.test/items/20260701?")
    assert source_result["rows"] == [{"DEVICE": "D1", "QTY": 12}]
    assert source_result["source_execution"]["used_dummy_data"] is False


def test_datalake_retriever_runs_lakehouse_style_client():
    retriever = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "11_datalake_retriever.py")
    calls = {}

    class FakeLakeHouse:
        def __init__(self, real_user_id=""):
            calls["real_user_id"] = real_user_id

        def ensure_running(self, cluster_type):
            calls["cluster_type"] = cluster_type

        def auto_run_sync_paragraph(self, code):
            calls["code"] = code

        def get_rst(self):
            return [{"DATE": "20260701", "QTY": 21}]

    payload = {
        "retrieval_job_bundle": {
            "jobs": [
                {
                    "dataset_key": "lake_dataset",
                    "source_alias": "lake_data",
                    "source_type": "datalake",
                    "source_config": {"query_template": "select * from t where work_date = {DATE}"},
                    "required_params": {"DATE": "20260701"},
                }
            ]
        }
    }

    result = retriever.datalake_retrieve(payload, user_id="u123", client_cls=FakeLakeHouse)
    source_result = result["source_results"][0]

    assert result["status"] == "ok"
    assert calls["real_user_id"] == "u123"
    assert calls["cluster_type"] == "starrocks"
    assert "work_date = '20260701'" in calls["code"]
    assert source_result["rows"] == [{"DATE": "20260701", "QTY": 21}]
    assert source_result["source_execution"]["adapter"] == "datalake"


def test_goodocs_retriever_uses_v3_goodocs_class_contract():
    retriever = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "12_goodocs_retriever.py")
    captured = {}

    class FakeGoodocs:
        def __init__(self, auth):
            captured["auth"] = auth

        def read_sheet(self, sheet_name):
            captured["sheet_name"] = sheet_name
            return [
                {"DEVICE": "D1", "TARGET": 100, "ROW_ID": "system"},
                {"DEVICE": "D2", "TARGET": 200, "LastUser": "system"},
            ]

    payload = {
        "retrieval_job_bundle": {
            "jobs": [
                {
                    "dataset_key": "target",
                    "source_alias": "target_data",
                    "source_type": "goodocs",
                    "source_config": {
                        "doc_id": "doc-1",
                        "sheet_name": "목표",
                    },
                }
            ]
        }
    }

    previous = retriever.GoodocsRetriever.goodocs_class
    retriever.GoodocsRetriever.goodocs_class = FakeGoodocs
    try:
        result = retriever.goodocs_retrieve(payload, user_id="user-1", token_source="token-source", token_key="token-key")
        source_result = result["source_results"][0]
    finally:
        retriever.GoodocsRetriever.goodocs_class = previous

    assert result["status"] == "ok"
    assert captured["auth"] == {
        "USER_ID": "user-1",
        "DOC_ID": "doc-1",
        "TOKEN_SOURCE": "token-source",
        "TOKEN_KEY": "token-key",
        "SHEET_NAME": "목표",
    }
    assert captured["sheet_name"] == "목표"
    assert source_result["rows"] == [{"DEVICE": "D1", "TARGET": 100}, {"DEVICE": "D2", "TARGET": 200}]
    assert source_result["source_execution"]["doc_id"] == "doc-1"
    assert source_result["source_execution"]["sheet_name"] == "목표"
    assert source_result["source_execution"]["used_dummy_data"] is False


def test_goodocs_retriever_keeps_inline_rows_for_local_fixture():
    retriever = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "12_goodocs_retriever.py")
    payload = {
        "retrieval_job_bundle": {
            "jobs": [
                {
                    "dataset_key": "target",
                    "source_alias": "target_data",
                    "source_type": "goodocs",
                    "source_config": {
                        "doc_id": "doc-1",
                        "sheet_name": "목표",
                        "rows": [{"DEVICE": "D1", "TARGET": 100, "ROW_ID": "system"}],
                    },
                }
            ]
        }
    }

    result = retriever.goodocs_retrieve(payload)
    source_result = result["source_results"][0]

    assert result["status"] == "ok"
    assert source_result["rows"] == [{"DEVICE": "D1", "TARGET": 100}]
    assert source_result["source_execution"]["source_configured"] is True


def test_analysis_request_loader_defaults_reference_date_to_korea_today():
    request_loader = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "00_analysis_request_loader.py")
    expected_today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d")

    payload = request_loader.build_request("오늘 재공 알려줘")
    inherited = request_loader.build_request("오늘 재공 알려줘", {"session_id": "s-from-state"})
    input_names = {item.kwargs.get("name") for item in request_loader.AnalysisRequestLoader.inputs}

    assert payload["request"]["reference_date"] == expected_today
    assert payload["request"]["session_id"] == "demo-session"
    assert inherited["request"]["session_id"] == "s-from-state"
    assert "timezone" not in payload["request"]
    assert "reference_date_source" not in payload["request"]
    assert "reference_date" not in input_names
    assert "timezone" not in input_names
    assert "session_id" not in input_names


def test_intent_variables_builder_hides_date_context_and_direct_specialized_prompt_ports():
    intent_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "02_intent_variables_builder.py")

    input_names = {item.kwargs.get("name") for item in intent_variables.IntentVariablesBuilder.inputs}
    output_names = {item.kwargs.get("name") for item in intent_variables.IntentVariablesBuilder.outputs}

    assert output_names == {"question", "state_summary", "metadata_candidates", "output_schema"}
    assert "reference_date" not in output_names
    assert "timezone" not in output_names
    assert "specialized_prompt" not in output_names
    assert "specialized_prompt_text" not in input_names


def test_intent_variables_builder_compacts_metadata_candidate_wrapper():
    intent_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "02_intent_variables_builder.py")
    variables = intent_variables.build_variables(
        {"request": {"question": "오늘 재공 알려줘", "reference_date": "20260701"}},
        {
            "domain_items": [{"key": "duplicated_outer"}],
            "metadata_candidates": {
                "domain_items": [{"section": "process_groups", "key": "DA"}],
                "table_catalog_items": [{"dataset_key": "wip_today"}],
            },
            "metadata_load": {"loads": {"domain_items": {"collection_name": "agent_v4_domain_items"}}},
        },
    )
    candidates = json.loads(variables["metadata_candidates"])
    schema = json.loads(variables["output_schema"])

    assert candidates == {
        "domain_items": [{"section": "process_groups", "key": "DA"}],
        "table_catalog_items": [{"dataset_key": "wip_today"}],
    }
    assert "metadata_candidates" not in candidates
    assert "metadata_load" not in candidates
    assert "pandas_function_case" not in schema["intent_plan"]
    assert schema["intent_plan"]["pandas_function_cases"] == []


def test_langflow_dummy_data_covers_data_catalog_shapes():
    dummy = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "08_dummy_data_retriever.py")
    expected_columns = {
        "production_today": {
            "WORK_DATE", "SHIFT", "FACTORY", "FAB", "FAMILY", "MODE", "DENSITY", "TECH", "ORG", "PKG1",
            "PKG2", "LEAD", "MCP_NO", "TSV_DIE_TYP", "DEVICE", "DEVICE_DESC", "DIE_ATTACH_QTY",
            "NETDIE_300_CNT", "OPER", "OPER_NAME", "OPER_SEQ", "PRODUCTION",
        },
        "production": {
            "WORK_DATE", "SHIFT", "FACTORY", "FAB", "FAMILY", "MODE", "DENSITY", "TECH", "ORG", "PKG1",
            "PKG2", "LEAD", "MCP_NO", "TSV_DIE_TYP", "DEVICE", "DEVICE_DESC", "DIE_ATTACH_QTY",
            "NETDIE_300_CNT", "OPER", "OPER_NAME", "OPER_SEQ", "PRODUCTION",
        },
        "wip_today": {
            "WORK_DATE", "SHIFT", "FACTORY", "FAB", "FAMILY", "MODE", "DENSITY", "TECH", "ORG", "PKG1",
            "PKG2", "LEAD", "MCP_NO", "TSV_DIE_TYP", "DEVICE", "DEVICE_DESC", "DIE_ATTACH_QTY",
            "NETDIE_300_CNT", "OPER", "OPER_NAME", "OPER_SEQ", "WIP",
        },
        "wip": {
            "WORK_DATE", "SHIFT", "FACTORY", "FAB", "FAMILY", "MODE", "DENSITY", "TECH", "ORG", "PKG1",
            "PKG2", "LEAD", "MCP_NO", "TSV_DIE_TYP", "DEVICE", "DEVICE_DESC", "DIE_ATTACH_QTY",
            "NETDIE_300_CNT", "OPER", "OPER_NAME", "OPER_SEQ", "WIP",
        },
        "target": {"DATE", "Mode", "DEN", "TECH", "PKG1", "PKG2", "LEAD", "ORG", "MCP NO", "INPUT 계획", "OUT 계획"},
        "equipment_assign": {
            "BAY_ID", "EQUIP_ID", "EQUIP_MODEL", "PRESS_CNT", "OPER", "OPER_NM", "MODE", "DENSITY",
            "TECH", "PKG1", "PKG2", "LEAD", "ORG", "PKGSIZE", "MCP_NO", "DEVICE", "DEVICE_DESC",
            "LOT_ID", "RECIPE_ID",
        },
        "eqp_uph": {
            "EQUIP_MODEL", "OPER", "OPER_NAME", "PRESS_CNT", "MODE", "TECH", "ORG", "DENSITY",
            "PKG1", "PKG2", "LEAD", "MCP_NO", "RECIPE_ID", "UPH", "LOAD_DT", "BASE_DT",
        },
        "lot_status": {
            "ERM_ID", "OPER", "OPER_NAME", "FAB", "OWNER", "GRADE", "DEVICE", "LOT_ID", "SUB_LOT_ID",
            "PROD_QTY", "WF_QTY", "IN_TAT", "CUM_TAT", "EQP_ID", "FLOW_ID", "OPER_IN_TM",
            "FAC_IN_TIME", "HOLD_STAT", "HOLD_REASON", "FAMILY", "MODE", "DENSITY", "TECH", "ORG",
            "PKG1", "PKG2", "PKG3", "LEAD", "MCP_NO", "THK_CD", "LOT_STAT", "LOT_GRP", "PKG_SIZE",
            "HOT_LOT", "HOT_LEVEL", "PKG_COMPOSIT", "DURABLE_ID", "DURABLE_TYP", "SUB_QTY",
            "TSV_DIE_TYPE", "EVENT_DESC", "MOVE_IN_TM", "PAD_ABNORMAL", "SWR_REQ_NO", "INSP_TARGET",
        },
        "hold_history": {
            "LOT_ID", "PROD_QTY", "OPER", "OPER_NAME", "HOLD_TM", "HOLD_CD", "HOLD_USER", "HOLD_DESC",
            "FAB", "FAMILY", "MODE", "DENSITY", "TECH", "ORG", "PKG1", "PKG2", "LEAD", "MCP_NO",
            "GRADE", "OWNER", "DEVICE", "DEVICE_DESC", "PKG_SIZE", "THK_CD", "flow_id",
        },
    }
    jobs = [
        {
            "dataset_key": dataset_key,
            "source_alias": dataset_key,
            "source_type": "dummy",
            "required_params": _dummy_shape_params(dataset_key),
        }
        for dataset_key in expected_columns
    ]

    payload = dummy.retrieve_dummy_data({"retrieval_job_bundle": {"source_type": "dummy", "jobs": jobs}})
    results = {item["dataset_key"]: item for item in payload["source_results"]}

    assert set(results) == set(expected_columns)
    for dataset_key, columns in expected_columns.items():
        assert results[dataset_key]["row_count"] > 0
        assert columns.issubset(set(results[dataset_key]["columns"]))


def _dummy_shape_params(dataset_key):
    if dataset_key == "hold_history":
        return {"LOT_ID": "T1234567GEN1"}
    if dataset_key in {"production", "wip"}:
        return {"DATE": "20260630"}
    return {"DATE": "20260701"}


def test_langflow_dummy_data_applies_required_params_and_preserves_pandas_filters():
    dummy = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "08_dummy_data_retriever.py")
    payload = dummy.retrieve_dummy_data(
        {
            "retrieval_job_bundle": {
                "source_type": "dummy",
                "jobs": [
                    {
                        "dataset_key": "production_today",
                        "source_alias": "production_data",
                        "source_type": "dummy",
                        "required_params": {"DATE": "20260701"},
                        "filters": {"PKG_TYPE1": {"operator": "eq", "value": "LFBGA"}},
                    },
                    {
                        "dataset_key": "hold_history",
                        "source_alias": "hold_data",
                        "source_type": "dummy",
                        "required_params": {"LOT_ID": "T1234567GEN1"},
                    },
                ],
            }
        }
    )

    production, hold = payload["source_results"]

    assert {row["WORK_DATE"] for row in production["rows"]} == {"20260701"}
    assert {"LFBGA", "HBM", "UFBGA"}.issubset({row["PKG1"] for row in production["rows"]})
    assert production["pandas_filters"] == {"PKG_TYPE1": {"operator": "eq", "value": "LFBGA"}}
    assert production["source_execution"]["filters_applied_in_retriever"] is False
    assert {row["LOT_ID"] for row in hold["rows"]} == {"T1234567GEN1"}


def test_langflow_dummy_data_covers_auto_korea_today_reference_date():
    request_loader = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "00_analysis_request_loader.py")
    validator = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "06_retrieval_job_validator.py")
    router = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "07_retrieval_job_router.py")
    dummy = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "08_dummy_data_retriever.py")

    request_payload = request_loader.build_request("오늘 생산량 알려줘")
    reference_date = request_payload["request"]["reference_date"]
    payload = {
        "intent_plan": {
            "retrieval_jobs": [
                {
                    "dataset_key": "production_today",
                    "source_alias": "production_data",
                    "source_type": "oracle",
                    "required_params": {"DATE": reference_date},
                }
            ]
        },
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }

    validated = validator.validate_retrieval_payload(payload)
    routed = router.route_retrieval_jobs(validated, "dummy", "dummy")
    retrieved = dummy.retrieve_dummy_data(routed)

    assert routed["retrieval_job_bundle"]["live_source_retrieval"] is False
    assert retrieved["status"] == "ok"
    assert retrieved["source_results"][0]["row_count"] > 0
    assert len(retrieved["source_results"][0]["preview_rows"]) <= 5
    assert len(retrieved["source_results"][0]["rows"]) > len(retrieved["source_results"][0]["preview_rows"])
    assert {row["WORK_DATE"] for row in retrieved["source_results"][0]["rows"]} == {reference_date}


def test_representative_questions_have_answerable_dummy_data_coverage():
    validator = load_module(ROOT / "tools" / "validate_representative_questions.py")
    modules = validator.load_flow_modules()
    results = {
        int(case["id"]): validator.run_case(case, modules, "20260701")
        for case in validator.representative_cases()
    }

    da_steps = {row["OPER_NAME"] for row in results[2]["preview_rows"]}
    wb_steps = {row["OPER_NAME"] for row in results[5]["preview_rows"]}
    hbm_wb_devices = {row["DEVICE"] for row in results[4]["preview_rows"]}
    hbm_fcb_devices = {row["DEVICE"] for row in results[6]["preview_rows"]}

    assert results[2]["row_count"] == 6
    assert da_steps == {"D/A1", "D/A2", "D/A3", "D/A4", "D/A5", "D/A6"}
    assert results[5]["row_count"] == 6
    assert wb_steps == {"W/B1", "W/B2", "W/B3", "W/B4", "W/B5", "W/B6"}
    assert results[4]["row_count"] == 1
    assert hbm_wb_devices == {"DEV-HBM"}
    assert results[6]["row_count"] == 1
    assert hbm_fcb_devices == {"DEV-HBM"}
    assert results[1]["preview_rows"][0]["MCP_NO"].startswith("L-267")
    assert results[8]["preview_rows"][0]["DEVICE"] == "DEV-RG-DDR4"
    assert results[9]["preview_rows"][0]["DEVICE"] == "DEV-SP-DDR5"
    assert results[12]["preview_rows"][0]["MCP_NO"] == "L-218K8H"
    assert results[13]["preview_rows"][0]["DEVICE"] == "DEV-DA-GDDR6"


def test_data_analysis_langflow_dummy_path_reaches_api_response():
    request_loader = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "00_analysis_request_loader.py")
    intent_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "02_intent_variables_builder.py")
    intent_normalizer = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "04_intent_plan_normalizer.py")
    validator = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "06_retrieval_job_validator.py")
    router = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "07_retrieval_job_router.py")
    dummy = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "08_dummy_data_retriever.py")
    merger = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "13_source_retrieval_merger.py")
    adapter = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "14_retrieval_payload_adapter.py")
    pandas_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "15_pandas_variables_builder.py")
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    answer_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "18_answer_variables_builder.py")
    answer_builder = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "20_answer_response_builder.py")
    message_adapter = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "21_answer_message_adapter.py")
    api_builder = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "22_api_response_builder.py")

    expected_today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d")
    payload = request_loader.build_request("오늘 D/A1 공정 WIP 합계 알려줘")
    intent_prompt_vars = intent_variables.build_variables(payload, {"datasets": ["wip_today"]})
    assert "wip_today" in intent_prompt_vars["metadata_candidates"]
    state_summary = json.loads(intent_prompt_vars["state_summary"])
    assert state_summary["request_context"]["reference_date"] == expected_today
    assert "timezone" not in state_summary["request_context"]
    assert "reference_date_source" not in state_summary["request_context"]
    assert "reference_date" not in intent_prompt_vars
    assert "timezone" not in intent_prompt_vars
    intent_llm_response = {
        "intent_plan": {
            "analysis_kind": "wip_sum_by_oper",
            "retrieval_jobs": [
                {
                    "dataset_key": "wip_today",
                    "source_alias": "wip_data",
                    "source_type": "oracle",
                    "required_params": {"DATE": "20260701"},
                    "filters": {"OPER_NAME": {"operator": "eq", "value": "D/A1"}},
                }
            ],
            "pandas_execution_plan": [{"step": "sum_wip", "source_alias": "wip_data", "group_by": ["OPER_NAME"]}],
            "output_contract": {"columns": ["OPER_NAME", "wip_sum"]},
        },
        "metadata_refs": [{"type": "table_catalog", "key": "wip_today"}],
        "trace": {"decision_reason": ["사용자가 WIP 합계를 요청했고 wip_today dataset을 사용한다."]},
    }
    payload = intent_normalizer.normalize_intent_plan(payload, intent_llm_response)

    validated = validator.validate_retrieval_payload(payload)
    dummy_bundle = router.route_retrieval_jobs(validated, "dummy")
    dummy_result = dummy.retrieve_dummy_data(dummy_bundle)
    merged = merger.merge_source_retrieval_payloads(validated, dummy_result)
    payload = adapter.build_retrieval_payload(merged)
    assert payload["source_results"][0]["row_count"] > 4
    assert payload["source_results"][0]["pandas_filters"] == {"OPER_NAME": {"operator": "eq", "value": "D/A1"}}

    pandas_prompt_vars = pandas_variables.build_variables(payload)
    assert "wip_data" in pandas_prompt_vars["source_schema_json"]
    pandas_llm_response = {
        "code": (
            "df = sources['wip_data']\n"
            "result = df.groupby('OPER_NAME', as_index=False)['WIP'].sum().rename(columns={'WIP': 'wip_sum'})"
        )
    }
    payload = pandas_executor.execute_pandas_code(payload, pandas_llm_response)

    assert payload["analysis"]["status"] == "ok"
    assert payload["data"]["rows"] == [{"OPER_NAME": "D/A1", "wip_sum": 363}]
    generated_code = payload["trace"]["inspection"]["pandas_execution"]["generated_code"]
    assert "OPER_NAME" in generated_code
    assert "_filter_values_1_1 = ['D/A1']" in generated_code
    assert ".isin(_filter_values_1_1)" in generated_code
    assert "df = sources['wip_data']" in generated_code
    assert payload["trace"]["inspection"]["pandas_execution"]["pandas_filter_plan"][0]["conditions"][0]["field"] == "OPER_NAME"

    answer_prompt_vars = answer_variables.build_variables(payload)
    assert "wip_sum" in answer_prompt_vars["result_summary_json"]
    payload = answer_builder.build_answer_response(payload, "D/A1 공정의 WIP 합계는 120입니다.")
    playground_message = message_adapter.build_message(payload, "", True)
    response = api_builder.build_api_response(payload)

    assert response["status"] == "ok"
    assert response["message"] == "D/A1 공정의 WIP 합계는 120입니다."
    assert response["data"]["row_count"] == 1
    assert response["intent_plan"]["pandas_execution_plan"][0]["step"] == "sum_wip"
    assert response["analysis"]["analysis_code"]
    assert response["trace"]["inspection"]["pandas_execution"]["generated_code"]
    assert "runtime_sources" not in response
    assert "_full_result_rows" not in response
    assert "_runtime_result_rows" not in response
    assert "### 의도 분석" in playground_message
    assert "wip_sum_by_oper" in playground_message
    assert "### 데이터 조회" in playground_message
    assert "wip_data" in playground_message
    assert "pandas 필터" in playground_message
    assert "### pandas 코드/실행" in playground_message
    assert "df = sources['wip_data']" in playground_message
    assert "| 공정 | WIP 합계 |" in playground_message


def test_answer_message_adapter_result_table_uses_ten_row_preview():
    message_adapter = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "21_answer_message_adapter.py")
    payload = {
        "answer_message": "완료했습니다.",
        "data": {
            "columns": ["idx"],
            "rows": [{"idx": index} for index in range(12)],
            "row_count": 12,
        },
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }

    message = message_adapter.build_message(payload)

    assert "| 9 |" in message
    assert "| 10 |" not in message
    assert "총 12건 중 10건을 표시했습니다." in message


def test_answer_message_adapter_formats_numbers_and_shows_recorded_outputs():
    message_adapter = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "21_answer_message_adapter.py")
    payload = {
        "answer_message": "현재 재공 기준 분석 결과입니다.",
        "analysis": {
            "status": "ok",
            "step_outputs": [
                {
                    "key": "top_wip_product",
                    "description": "현재 재공이 가장 많은 제품",
                    "row_count": 1,
                    "columns": ["DEVICE", "WIP"],
                    "preview_rows": [{"DEVICE": "DEV-A", "WIP": 12000}],
                }
            ],
            "function_case_results": [
                {
                    "function_name": "sample_helper",
                    "input_text": "DEV-A",
                    "description": "특화 함수 결과",
                    "matched_count": 1,
                    "columns": ["DEVICE", "WIP"],
                    "preview_rows": [{"DEVICE": "DEV-A", "WIP": 12000}],
                }
            ],
        },
        "data": {
            "columns": ["DEVICE", "WIP", "ASSIGN_COUNT"],
            "rows": [{"DEVICE": "DEV-A", "WIP": 12000, "ASSIGN_COUNT": 9850}],
            "row_count": 1,
        },
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }

    message = message_adapter.build_message(payload)

    assert "### 분석 과정 요약" in message
    assert "### 분석 근거" in message
    assert "12K" in message
    assert "9,850" in message


def test_intent_normalizer_parses_langflow_message_text_with_nested_json():
    intent_normalizer = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "04_intent_plan_normalizer.py")
    payload = {"request": {"question": "오늘 da공정 생산량 상위 3개 제품 알려줘"}, "trace": {"warnings": [], "errors": [], "inspection": {}}}
    llm_response = types.SimpleNamespace(
        text="""```json
{
  "intent_plan": {
    "analysis_kind": "top_product_production",
    "retrieval_jobs": [
      {
        "dataset_key": "production_today",
        "source_alias": "production_data",
        "source_type": "oracle",
        "source_config": {"source_type": "oracle", "db_key": "PNT_RPT", "query_template": "SELECT * FROM PROD_TABLE WHERE WORK_DATE = {DATE}"},
        "required_params": {"DATE": "20260701"},
        "filters": {"OPER_NAME": {"operator": "contains", "value": "D/A"}}
      }
    ],
    "pandas_execution_plan": [{"step": "top_n", "source_alias": "production_data"}],
    "output_contract": {"top_n": 3}
  },
  "metadata_refs": [{"type": "table_catalog", "key": "production_today"}],
  "trace": {"decision_reason": ["production_today를 선택"]}
}
```"""
    )

    normalized = intent_normalizer.normalize_intent_plan(payload, llm_response)

    assert normalized["intent_plan"]["retrieval_jobs"][0]["dataset_key"] == "production_today"
    assert normalized["intent_plan"]["retrieval_jobs"][0]["required_params"] == {"DATE": "20260701"}
    assert normalized["metadata_refs"] == [{"type": "table_catalog", "key": "production_today"}]
    assert normalized["trace"]["inspection"]["intent"]["retrieval_job_count"] == 1
    assert not any(warning.get("type") == "missing_retrieval_jobs" for warning in normalized["trace"]["warnings"])


def test_intent_normalizer_accepts_llm_json_with_literal_sql_newlines():
    intent_normalizer = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "04_intent_plan_normalizer.py")
    payload = {"request": {"question": "어제 DA공정 차수별 생산량 알려줘"}, "trace": {"warnings": [], "errors": [], "inspection": {}}}
    llm_response = types.SimpleNamespace(
        text="""{
  "intent_plan": {
    "analysis_kind": "data_retrieval_and_analysis",
    "retrieval_jobs": [
      {
        "dataset_key": "production",
        "source_alias": "production_data",
        "source_type": "oracle",
        "source_config": {
          "source_type": "oracle",
          "db_key": "PNT_RPT",
          "query_template": "SELECT *
FROM PROD_TABLE
WHERE WORK_DATE = {DATE}"
        },
        "required_params": {"DATE": "20260630"},
        "filters": {"OPER_NAME": {"operator": "in", "value": ["D/A1", "D/A2"]}}
      }
    ],
    "pandas_execution_plan": [{"operation": "group_by", "source_alias": "production_data"}],
    "output_contract": {}
  }
}"""
    )

    normalized = intent_normalizer.normalize_intent_plan(payload, llm_response)

    assert normalized["intent_plan"]["analysis_kind"] == "data_retrieval_and_analysis"
    assert normalized["intent_plan"]["retrieval_jobs"][0]["source_config"]["query_template"].startswith("SELECT *")
    assert normalized["trace"]["inspection"]["intent"]["retrieval_job_count"] == 1


def test_intent_normalizer_recovers_intent_plan_when_metadata_refs_are_malformed():
    intent_normalizer = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "04_intent_plan_normalizer.py")
    payload = {"request": {"question": "어제 DA공정 차수별 생산량 알려줘"}, "trace": {"warnings": [], "errors": [], "inspection": {}}}
    llm_response = types.SimpleNamespace(
        text="""{
  "intent_plan": {
    "analysis_kind": "data_retrieval_and_analysis",
    "retrieval_jobs": [
      {
        "dataset_key": "production",
        "source_alias": "production_data",
        "source_type": "oracle",
        "required_params": {"DATE": "20260630"},
        "filters": {"OPER_NAME": {"operator": "in", "value": ["D/A1", "D/A2"]}}
      }
    ],
    "pandas_execution_plan": [{"operation": "group_by", "source_alias": "production_data"}],
    "output_contract": {}
  },
  "metadata_refs": [
    {"section": "process_groups", "key": "DA"}],
    {"section": "analysis_recipes", "key": "group_by_oper_name_for_process_sequence"}
  ],
  "trace": {"decision_reason": ["metadata_refs 문법이 깨져도 intent_plan은 복구한다."]}
}"""
    )

    normalized = intent_normalizer.normalize_intent_plan(payload, llm_response)

    assert normalized["intent_plan"]["analysis_kind"] == "data_retrieval_and_analysis"
    assert normalized["intent_plan"]["retrieval_jobs"][0]["dataset_key"] == "production"
    assert normalized["trace"]["inspection"]["intent"]["retrieval_job_count"] == 1
    assert normalized["metadata_refs"] == []


def test_pandas_executor_parses_langflow_message_text_json():
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    payload = {"runtime_sources": {"production_data": [{"MODE": "LPDDR5", "PRODUCTION": 1000}]}, "trace": {"warnings": [], "errors": [], "inspection": {}}}
    llm_response = types.SimpleNamespace(text='```json\n{"code": "df = sources[\'production_data\']\\nresult = df"}\n```')

    result = pandas_executor.execute_pandas_code(payload, llm_response)

    assert result["analysis"]["status"] == "ok"
    assert result["data"]["rows"] == [{"MODE": "LPDDR5", "PRODUCTION": 1000}]


def test_pandas_executor_accepts_llm_json_with_literal_code_newlines():
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    payload = {"runtime_sources": {"production_data": [{"MODE": "LPDDR5", "PRODUCTION": 1000}]}, "trace": {"warnings": [], "errors": [], "inspection": {}}}
    llm_response = types.SimpleNamespace(
        text="""{
  "code": "df = sources['production_data']
result = df"
}"""
    )

    result = pandas_executor.execute_pandas_code(payload, llm_response)

    assert result["analysis"]["status"] == "ok"
    assert result["data"]["rows"] == [{"MODE": "LPDDR5", "PRODUCTION": 1000}]


def test_pandas_executor_prepends_non_required_filters_before_aggregation():
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    payload = {
        "intent_plan": {
            "retrieval_jobs": [
                {
                    "dataset_key": "production_today",
                    "source_alias": "production_data",
                    "source_type": "oracle",
                    "required_params": {"DATE": "20260701"},
                    "filters": {"OPER_NAME": {"operator": "in", "value": ["D/A1", "D/A2", "D/A3", "D/A4", "D/A5", "D/A6"]}},
                }
            ],
            "pandas_execution_plan": [{"step": "top_3_products"}],
        },
        "runtime_sources": {
            "production_data": [
                {"WORK_DATE": "20260701", "OPER_NAME": "D/A1", "TECH": "1Z", "DEN": "16G", "MODE": "LPDDR5", "PKG_TYPE1": "LFBGA", "PKG_TYPE2": "POP", "LEAD": "200", "MCP_NO": "MCP001", "DEVICE": "DEV001", "PRODUCTION": 1000},
                {"WORK_DATE": "20260701", "OPER_NAME": "D/A2", "TECH": "1A", "DEN": "24G", "MODE": "HBM3E", "PKG_TYPE1": "HBM", "PKG_TYPE2": "TSV", "LEAD": "300", "MCP_NO": "MCPHBM", "DEVICE": "DEV-HBM", "PRODUCTION": 700},
                {"WORK_DATE": "20260701", "OPER_NAME": "W/B1", "TECH": "1B", "DEN": "32G", "MODE": "LPDDR5X", "PKG_TYPE1": "UFBGA", "PKG_TYPE2": "MOBILE", "LEAD": "180", "MCP_NO": "MCP002", "DEVICE": "DEV002", "PRODUCTION": 650},
            ]
        },
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }
    llm_response = {
        "code": (
            "grouped_data = sources[\"production_data\"].groupby([\"TECH\", \"DEN\", \"MODE\", \"PKG_TYPE1\", \"PKG_TYPE2\", \"LEAD\", \"MCP_NO\", \"DEVICE\"])[\"PRODUCTION\"].sum().reset_index()\n"
            "grouped_data = grouped_data.rename(columns={\"PRODUCTION\": \"TOTAL_PRODUCTION\"})\n"
            "sorted_data = grouped_data.sort_values(by=\"TOTAL_PRODUCTION\", ascending=False)\n"
            "result = sorted_data.head(3)"
        )
    }

    result = pandas_executor.execute_pandas_code(payload, llm_response)
    generated_code = result["trace"]["inspection"]["pandas_execution"]["generated_code"]

    assert result["analysis"]["status"] == "ok"
    assert [row["DEVICE"] for row in result["data"]["rows"]] == ["DEV001", "DEV-HBM"]
    assert "W/B1" not in json.dumps(result["data"]["rows"], ensure_ascii=False)
    assert "OPER_NAME" in generated_code
    assert "_filter_values_1_1 = ['D/A1', 'D/A2', 'D/A3', 'D/A4', 'D/A5', 'D/A6']" in generated_code
    assert ".isin(_filter_values_1_1)" in generated_code
    assert "grouped_data = sources[\"production_data\"].groupby" in generated_code


def test_pandas_executor_supports_prefix_filter_and_product_token_helper():
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    payload = {
        "intent_plan": {
            "retrieval_jobs": [
                {
                    "dataset_key": "production_today",
                    "source_alias": "production_data",
                    "required_params": {"DATE": "20260701"},
                    "filters": {"MCP_NO": {"operator": "starts_with", "value": "L-267"}},
                }
            ],
            "pandas_execution_plan": [],
        },
        "runtime_sources": {
            "production_data": [
                {"TECH": "1C", "DENSITY": "16G", "MODE": "LPDDR5", "LEAD": "267", "MCP_NO": "L-267A1", "DEVICE": "DEV-L267", "PRODUCTION": 10},
                {"TECH": "1Y", "DENSITY": "8G", "MODE": "LPDDR4", "LEAD": "218", "MCP_NO": "L-218K8H", "DEVICE": "DEV-L218K8H", "PRODUCTION": 20},
            ]
        },
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }
    result = pandas_executor.execute_pandas_code(payload, {"code": "result = sources['production_data'][['DEVICE', 'MCP_NO']]"})

    assert result["analysis"]["status"] == "ok"
    assert result["data"]["rows"] == [{"DEVICE": "DEV-L267", "MCP_NO": "L-267A1"}]
    assert ".str.startswith(str(_filter_values_1_1[0]), na=False)" in result["trace"]["inspection"]["pandas_execution"]["generated_code"]

    helper_payload = {
        "runtime_sources": {
            "wip_data": [
                {"TECH": "DA", "DENSITY": "16G", "MODE": "GDDR6", "LEAD": 180, "DEVICE": "DEV-DA-GDDR6", "WIP": 33},
                {"TECH": "DA", "DENSITY": "16G", "MODE": "GDDR6", "LEAD": 180.0, "DEVICE": "DEV-DA-GDDR6-FLOAT", "WIP": 44},
                {"TECH": "ZZ", "DENSITY": "16G", "MODE": "GDDR6", "LEAD": 180.0, "DEVICE": "DEV-ZZ-GDDR6", "WIP": 99},
            ]
        },
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }
    helper_result = pandas_executor.execute_pandas_code(
        helper_payload,
        {"code": function_case_source("match_product_tokens") + "\n\ndf = match_product_tokens('DA 16G GDDR6 180', sources['wip_data'])\nresult = df[['TECH', 'DEVICE', 'WIP']]"},
    )

    assert helper_result["analysis"]["status"] == "ok"
    assert helper_result["data"]["rows"] == [
        {"TECH": "DA", "DEVICE": "DEV-DA-GDDR6", "WIP": 33},
        {"TECH": "DA", "DEVICE": "DEV-DA-GDDR6-FLOAT", "WIP": 44},
    ]
    helper_trace = helper_result["trace"]["inspection"]["pandas_execution"]
    effective_code = helper_trace["effective_code_with_helpers"]
    assert helper_trace["used_helpers"] == ["match_product_tokens"]
    assert helper_result["analysis"]["used_helpers"] == ["match_product_tokens"]
    assert helper_result["analysis"]["effective_code_with_helpers"] == effective_code
    assert "def match_product_tokens" in effective_code
    assert "df = match_product_tokens('DA 16G GDDR6 180', sources['wip_data'])" in effective_code

    message_adapter = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "21_answer_message_adapter.py")
    helper_message = message_adapter.build_message(helper_result)
    assert "### 제품/조건 매핑 결과" in helper_message
    assert "DA 16G GDDR6 180" in helper_message
    assert "def match_product_tokens" not in helper_message
    helper_diagnostic_message = message_adapter.build_message(helper_result, "", True)
    assert "사용 helper" in helper_diagnostic_message
    assert "실제 실행 pandas 코드" in helper_diagnostic_message
    assert "def match_product_tokens" in helper_diagnostic_message


def test_match_product_tokens_handles_org_x_lead_mcp_and_multiple_products():
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    payload = {
        "runtime_sources": {
            "product_data": [
                {"TECH": "RG", "DENSITY": "8G", "MODE": "DDR4", "ORG": "16", "LEAD": "96", "PKG1": "FCBGA", "PKG2": "SDP", "MCP_NO": "L-218K8H", "DEVICE": "RG-X16", "WIP": 10},
                {"TECH": "CP", "DENSITY": "16G", "MODE": "DDR", "ORG": "8", "LEAD": "78", "PKG1": "FCBGA", "PKG2": "SDP", "MCP_NO": "L-216A1", "DEVICE": "CP-X8", "WIP": 20},
                {"TECH": "CP", "DENSITY": "16G", "MODE": "DDR", "ORG": "16", "LEAD": "78", "PKG1": "VFBGA", "PKG2": "SDP", "MCP_NO": "A-663Z9", "DEVICE": "CP-F78-V", "WIP": 30},
                {"TECH": "RG", "DENSITY": "8G", "MODE": "DDR4", "ORG": "16", "LEAD": "96", "PKG1": "VFBGA", "PKG2": "SDP", "MCP_NO": "A-777Z9", "DEVICE": "RG-F96-V", "WIP": 35},
                {"TECH": "RG", "DENSITY": "8G", "MODE": "DDR4", "ORG": "8", "LEAD": "96", "PKG1": "FCBGA", "PKG2": "SDP", "MCP_NO": "L-999", "DEVICE": "RG-WRONG-ORG", "WIP": 40},
                {"TECH": "CP", "DENSITY": "16G", "MODE": "DDR", "ORG": "8", "LEAD": "96", "PKG1": "FCBGA", "PKG2": "SDP", "MCP_NO": "L-000", "DEVICE": "CP-WRONG-LEAD", "WIP": 50},
            ]
        },
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }

    multi = pandas_executor.execute_pandas_code(
        payload,
        {
            "code": (
                function_case_source("match_product_tokens")
                + "\n\n"
                "df = match_product_tokens('RG 8G DDR4 x16 96 FCBGA SDP, CP 16G DDR x8 78 FCBGA SDP', sources['product_data'])\n"
                "result = df[['DEVICE', 'ORG', 'LEAD']]"
            )
        },
    )
    fc78 = pandas_executor.execute_pandas_code(
        payload,
        {"code": function_case_source("match_product_tokens") + "\n\ndf = match_product_tokens('FC78', sources['product_data'])\nresult = df[['DEVICE', 'PKG1', 'LEAD']]"},
    )
    f78 = pandas_executor.execute_pandas_code(
        payload,
        {"code": function_case_source("match_product_tokens") + "\n\ndf = match_product_tokens('F78', sources['product_data'])\nresult = df[['DEVICE', 'PKG1', 'LEAD']]"},
    )
    fc96 = pandas_executor.execute_pandas_code(
        payload,
        {"code": function_case_source("match_product_tokens") + "\n\ndf = match_product_tokens('FC96', sources['product_data'])\nresult = df[['DEVICE', 'PKG1', 'LEAD']]"},
    )
    f96 = pandas_executor.execute_pandas_code(
        payload,
        {"code": function_case_source("match_product_tokens") + "\n\ndf = match_product_tokens('F96', sources['product_data'])\nresult = df[['DEVICE', 'PKG1', 'LEAD']]"},
    )
    mcp = pandas_executor.execute_pandas_code(
        payload,
        {"code": function_case_source("match_product_tokens") + "\n\ndf = match_product_tokens('L-218, L-216, A-663 제품 PKG 투입수량 알려줘', sources['product_data'])\nresult = df[['DEVICE', 'MCP_NO']]"},
    )

    assert multi["analysis"]["status"] == "ok"
    assert [row["DEVICE"] for row in multi["data"]["rows"]] == ["RG-X16", "CP-X8"]
    assert [row["DEVICE"] for row in fc78["data"]["rows"]] == ["CP-X8"]
    assert [row["DEVICE"] for row in f78["data"]["rows"]] == ["CP-X8", "CP-F78-V"]
    assert [row["DEVICE"] for row in fc96["data"]["rows"]] == ["RG-X16", "RG-WRONG-ORG", "CP-WRONG-LEAD"]
    assert [row["DEVICE"] for row in f96["data"]["rows"]] == ["RG-X16", "RG-F96-V", "RG-WRONG-ORG", "CP-WRONG-LEAD"]
    assert [row["MCP_NO"] for row in mcp["data"]["rows"]] == ["L-218K8H", "L-216A1", "A-663Z9"]


def test_answer_message_adapter_skips_duplicate_result_table_when_answer_has_table():
    message_adapter = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "21_answer_message_adapter.py")
    payload = {
        "answer_message": "요청 결과입니다.\n\n| OPER_NAME | wip_sum |\n| --- | ---: |\n| D/A1 | 363 |",
        "data": {
            "columns": ["OPER_NAME", "wip_sum"],
            "rows": [{"OPER_NAME": "D/A1", "wip_sum": 363}],
            "row_count": 1,
        },
        "intent_plan": {"analysis_kind": "wip_sum_by_oper"},
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }

    message = message_adapter.build_message(payload, "", True)

    assert message.count("| OPER_NAME | wip_sum |") == 1
    assert "wip_sum_by_oper" in message


def test_answer_message_adapter_adds_data_ref_download_links():
    message_adapter = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "21_answer_message_adapter.py")
    payload = {
        "answer_message": "완료했습니다.",
        "data": {
            "columns": ["DEVICE", "QTY"],
            "rows": [{"DEVICE": "A", "QTY": 1}],
            "row_count": 1,
        },
        "data_refs": [
            {
                "store": "mongodb",
                "ref_id": "result:s1:abc",
                "database": "datagov",
                "collection_name": "agent_v4_result_store",
                "path": "payload.result_rows",
                "role": "analysis_result",
                "label": "분석 결과 데이터",
            },
            {
                "store": "mongodb",
                "ref_id": "result:s1:abc",
                "database": "datagov",
                "collection_name": "agent_v4_result_store",
                "path": "payload.runtime_sources.production_data",
                "role": "source_rows",
                "source_alias": "production_data",
                "label": "사용 원본 데이터: production_data",
            },
        ],
    }

    message = message_adapter.build_message(payload, "http://localhost:8501")
    input_names = {item.kwargs.get("name") for item in message_adapter.AnswerMessageAdapter.inputs}

    assert "### 데이터 다운로드" in message
    assert "분석 결과 데이터 CSV 다운로드" in message
    assert "사용 원본 데이터: production_data CSV 다운로드" in message
    assert "http://localhost:8501/?download_ref=" in message
    assert "download_base_url" in input_names


def test_answer_message_adapter_default_download_link_uses_standalone_server():
    message_adapter = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "21_answer_message_adapter.py")
    payload = {
        "answer_message": "완료했습니다.",
        "data_refs": [
            {
                "store": "mongodb",
                "ref_id": "result:s1:abc",
                "collection_name": "agent_v4_result_store",
                "path": "payload.result_rows",
                "role": "analysis_result",
            }
        ],
    }

    message = message_adapter.build_message(payload)

    assert "http://localhost:8765/?download_ref=" in message


def test_api_response_builder_uses_chat_display_message_when_connected():
    api_builder = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "22_api_response_builder.py")
    payload = {
        "answer_message": "단순 답변입니다.",
        "analysis": {"status": "ok"},
        "data": {"columns": ["지표", "값"], "rows": [{"지표": "생산 실적", "값": 650}], "row_count": 1},
    }

    response = api_builder.build_api_response(payload, "### 답변\n상세 답변입니다.\n\n### 결과 테이블\n| 지표 | 값 |\n| --- | ---: |\n| 생산 실적 | 650 |")

    assert response["status"] == "ok"
    assert response["answer_message"] == "단순 답변입니다."
    assert response["display_message"].startswith("### 답변")
    assert response["message"] == response["display_message"]


def test_pandas_executor_outputs_json_ready_numeric_rows():
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    payload = {"runtime_sources": {}, "trace": {"warnings": [], "errors": [], "inspection": {}}}

    result = pandas_executor.execute_pandas_code(
        payload,
        {
            "code": (
                "result = pd.DataFrame({"
                "'DEVICE': ['DEV-A'], "
                "'QTY': pd.Series([7], dtype='int64'), "
                "'RATIO': pd.Series([1.5], dtype='float64'), "
                "'EMPTY': [float('nan')]"
                "})"
            )
        },
    )

    json.dumps(result["data"], ensure_ascii=False)
    assert result["data"]["rows"] == [{"DEVICE": "DEV-A", "EMPTY": None, "QTY": 7, "RATIO": 1.5}]
    assert result["_full_result_rows"] == [{"DEVICE": "DEV-A", "EMPTY": None, "QTY": 7, "RATIO": 1.5}]
    assert "_runtime_result_rows" not in result


def test_pandas_executor_wraps_scalar_result_with_meaningful_columns():
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    payload = {
        "request": {"question": "전일 L-218K8H 제품의 SBM공정에서 생산 실적 알려줘"},
        "runtime_sources": {},
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }

    result = pandas_executor.execute_pandas_code(payload, {"code": "result = 650"})

    assert result["data"]["columns"] == ["지표", "값"]
    assert result["data"]["rows"] == [{"지표": "생산 실적", "값": 650}]
    assert result["analysis"]["columns"] == ["지표", "값"]


def test_pandas_executor_trace_preview_is_compact_but_full_rows_are_kept():
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    payload = {"runtime_sources": {}, "trace": {"warnings": [], "errors": [], "inspection": {}}}

    result = pandas_executor.execute_pandas_code(
        payload,
        {"code": "result = pd.DataFrame({'idx': list(range(12))})"},
    )
    trace_rows = result["trace"]["inspection"]["pandas_execution"]["execution_result"]["preview_rows"]

    assert result["analysis"]["row_count"] == 12
    assert len(result["_full_result_rows"]) == 12
    assert len(result["data"]["rows"]) == 12
    assert len(trace_rows) == 5


def test_pandas_executor_records_step_and_function_case_outputs():
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    payload = {
        "runtime_sources": {
            "production_data": [
                {"DEVICE": "DEV-A", "WIP": 12000, "PRODUCTION": 7},
                {"DEVICE": "DEV-B", "WIP": 3000, "PRODUCTION": 3},
            ]
        },
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }

    result = pandas_executor.execute_pandas_code(
        payload,
        {
            "code": (
                "df = sources['production_data'].copy()\n"
                "top = df.sort_values('WIP', ascending=False).head(1)\n"
                "record_step('top_wip_product', top, description='현재 재공이 가장 많은 제품', role='basis')\n"
                "record_function_case_result('sample_helper', 'DEV-A', top, description='helper 결과')\n"
                "result = top[['DEVICE', 'WIP']]"
            )
        },
    )

    step_outputs = result["analysis"]["step_outputs"]
    function_case_results = result["analysis"]["function_case_results"]

    assert result["analysis"]["status"] == "ok"
    assert step_outputs[0]["key"] == "top_wip_product"
    assert step_outputs[0]["preview_rows"][0]["DEVICE"] == "DEV-A"
    assert function_case_results[0]["function_name"] == "sample_helper"
    assert function_case_results[0]["matched_count"] == 1
    assert result["trace"]["inspection"]["pandas_execution"]["step_outputs"] == step_outputs


def test_answer_variables_accept_numpy_scalars_after_result_store(monkeypatch):
    import numpy as np

    mongo_store = install_fake_pymongo(monkeypatch)
    set_v4_mongo_env(monkeypatch)
    result_store = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "23_mongodb_result_store.py")
    answer_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "18_answer_variables_builder.py")
    payload = {
        "request": {"session_id": "s1", "question": "수량 알려줘"},
        "runtime_sources": {"production": [{"DEVICE": "DEV-A", "QTY": np.int64(7)}]},
        "_full_result_rows": [{"DEVICE": "DEV-A", "QTY": np.int64(7), "RATIO": np.float64(1.5), "EMPTY": np.nan}],
        "source_results": [{"source_alias": "production", "row_count": np.int64(1), "preview_rows": [{"DEVICE": "DEV-A"}]}],
        "analysis": {"status": "ok", "row_count": np.int64(1), "rows": [{"SHOULD_NOT_STORE": True}]},
        "data": {
            "columns": ["DEVICE", "QTY", "RATIO", "EMPTY"],
            "rows": [{"DEVICE": "DEV-A", "QTY": np.int64(7), "RATIO": np.float64(1.5), "EMPTY": np.nan}],
            "row_count": np.int64(1),
        },
        "trace": {
            "warnings": [],
            "errors": [],
            "inspection": {
                "pandas_execution": {
                    "generated_code": "result = sources['production']",
                    "effective_code_with_helpers": "def helper(): pass\nresult = sources['production']",
                    "helper_sources": {"helper": "def helper(): pass"},
                    "used_helpers": ["match_product_tokens"],
                    "execution_result": {"row_count": np.int64(1), "columns": ["DEVICE"], "preview_rows": [{"DEVICE": "DEV-A"}]},
                }
            },
        },
    }

    stored = result_store.store_result(payload)
    variables = answer_variables.build_variables(stored)
    result_summary = json.loads(variables["result_summary_json"])
    applied_scope = json.loads(variables["applied_scope_json"])
    answer_context = json.loads(variables["answer_context_json"])
    ref_id = stored["data"]["data_ref"]["ref_id"]

    assert variables["question"] == "수량 알려줘"
    assert result_summary["rows"][0] == {"DEVICE": "DEV-A", "EMPTY": None, "QTY": 7, "RATIO": 1.5}
    assert applied_scope["pandas_execution"]["row_count"] == 1
    assert applied_scope["pandas_execution"]["used_helpers"] == ["match_product_tokens"]
    assert answer_context["number_display_policy"]["gte_10000"] == "k_unit"
    assert answer_context["result_shape"]["row_count"] == 1
    assert "generated_code" not in variables["applied_scope_json"]
    assert "effective_code_with_helpers" not in variables["applied_scope_json"]
    assert "helper_sources" not in variables["applied_scope_json"]
    assert "preview_rows" not in variables["applied_scope_json"]
    stored_payload = mongo_store["datagov"]["agent_v4_result_store"][ref_id]["payload"]
    assert stored_payload["result_rows"][0]["QTY"] == 7
    assert "rows" not in stored_payload["data"]
    assert "rows" not in stored_payload["analysis"]


def test_result_store_accepts_legacy_runtime_result_rows(monkeypatch):
    import numpy as np

    mongo_store = install_fake_pymongo(monkeypatch)
    set_v4_mongo_env(monkeypatch)
    result_store = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "23_mongodb_result_store.py")
    payload = {
        "request": {"session_id": "s1", "question": "수량 알려줘"},
        "_runtime_result_rows": [{"DEVICE": "LEGACY", "QTY": np.int64(3)}],
        "data": {"columns": ["DEVICE", "QTY"], "rows": [{"DEVICE": "PREVIEW", "QTY": 1}], "row_count": 1},
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }

    stored = result_store.store_result(payload)
    ref_id = stored["data"]["data_ref"]["ref_id"]

    assert mongo_store["datagov"]["agent_v4_result_store"][ref_id]["payload"]["result_rows"] == [{"DEVICE": "LEGACY", "QTY": 3}]


def test_pandas_executor_uses_shared_namespace_for_comprehensions():
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    payload = {
        "runtime_sources": {
            "production_data": [
                {"OPER_NAME": "D/A1", "PRODUCTION": 10},
                {"OPER_NAME": "D/A2", "PRODUCTION": 20},
            ]
        },
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }
    llm_response = {
        "code": (
            "df_production_data = sources['production_data']\n"
            "group_by_cols = ['OPER_NAME']\n"
            "if all(col in df_production_data.columns for col in group_by_cols):\n"
            "    result = df_production_data.groupby(group_by_cols)['PRODUCTION'].sum().reset_index()\n"
            "else:\n"
            "    result = pd.DataFrame(columns=group_by_cols + ['PRODUCTION'])"
        )
    }

    result = pandas_executor.execute_pandas_code(payload, llm_response)

    assert result["analysis"]["status"] == "ok"
    assert result["data"]["row_count"] == 2


def test_intent_and_pandas_variables_expose_selected_function_case_context():
    intent_normalizer = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "04_intent_plan_normalizer.py")
    pandas_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "15_pandas_variables_builder.py")
    payload = {"request": {"question": "RG 32G DDR4 FBGA 96 DDP 제품 BG공정 생산량 알려줘"}, "trace": {"warnings": [], "errors": [], "inspection": {}}}
    normalized = intent_normalizer.normalize_intent_plan(
        payload,
        {
            "intent_plan": {
                "analysis_kind": "product_token_analysis",
                "pandas_function_case": {
                    "key": "product_token_match",
                    "function_name": "match_product_tokens",
                    "input_text": "RG 32G DDR4 FBGA 96 DDP",
                },
                "retrieval_jobs": [{"dataset_key": "production_today", "source_alias": "production_data"}],
                "pandas_execution_plan": [{"step": "sum_production", "source_alias": "production_data"}],
            }
        },
    )

    assert normalized["intent_plan"]["pandas_execution_plan"][0]["operation"] == "apply_pandas_function_case"
    assert "pandas_function_case" not in normalized["intent_plan"]
    assert "selected_function_cases" not in normalized["intent_plan"]
    assert normalized["intent_plan"]["pandas_function_cases"] == [
        {
            "key": "product_token_match",
            "function_name": "match_product_tokens",
            "input_text": "RG 32G DDR4 FBGA 96 DDP",
            "source_alias": "production_data",
        }
    ]
    variables = pandas_variables.build_variables(normalized)
    context = json.loads(variables["function_case_selection_json"])

    assert context["available_helpers"][0]["function_name"] == "match_product_tokens"
    assert "selected_case" not in context
    assert context["selected_steps"][0]["input_text"] == "RG 32G DDR4 FBGA 96 DDP"


def test_multiple_function_cases_expose_multiple_helpers_and_dummy_runtime():
    intent_normalizer = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "04_intent_plan_normalizer.py")
    pandas_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "15_pandas_variables_builder.py")
    repair_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17a_pandas_repair_variables_builder.py")
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    payload = {
        "request": {"question": "RG 32G DDR4 FBGA 96 DDP 제품 BG공정 생산량 알려줘"},
        "runtime_sources": {
            "production_data": [
                {"TECH": "RG", "DEN": "32G", "MODE": "DDR4", "PKG_TYPE1": "FBGA", "PKG_TYPE2": "DDP", "LEAD": "96", "DEVICE": "DEV-RG", "PRODUCTION": 10},
                {"TECH": "XX", "DEN": "16G", "MODE": "DDR5", "PKG_TYPE1": "BGA", "PKG_TYPE2": "SDP", "LEAD": "78", "DEVICE": "DEV-XX", "PRODUCTION": 99},
            ]
        },
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }
    normalized = intent_normalizer.normalize_intent_plan(
        payload,
        {
            "intent_plan": {
                "analysis_kind": "multi_function_case_demo",
                "pandas_function_cases": [
                    {
                        "key": "product_token_match",
                        "function_name": "match_product_tokens",
                        "input_text": "RG 32G DDR4 FBGA 96 DDP",
                        "source_alias": "production_data",
                    },
                    {
                        "key": "sample_passthrough_demo",
                        "function_name": "sample_passthrough_helper",
                        "input_text": "format demo",
                        "source_alias": "production_data",
                    },
                ],
                "retrieval_jobs": [{"dataset_key": "production_today", "source_alias": "production_data"}],
                "pandas_execution_plan": [{"step": "sum_production", "source_alias": "production_data"}],
            }
        },
    )
    variables = pandas_variables.build_variables(normalized)
    context = json.loads(variables["function_case_selection_json"])
    helper_names = [item["function_name"] for item in context["available_helpers"]]

    assert [step["function_name"] for step in normalized["intent_plan"]["pandas_execution_plan"][:2]] == ["match_product_tokens", "sample_passthrough_helper"]
    assert helper_names == ["match_product_tokens", "sample_passthrough_helper"]
    assert json.loads(repair_variables.build_variables(normalized)["function_case_selection_json"])["available_helpers"][1]["function_name"] == "sample_passthrough_helper"

    result = pandas_executor.execute_pandas_code(
        normalized,
        {
            "code": (
                function_case_source("match_product_tokens", "sample_passthrough_helper")
                + "\n\n"
                "df = match_product_tokens('RG 32G DDR4 FBGA 96 DDP', sources['production_data'])\n"
                "df = sample_passthrough_helper('format demo', df)\n"
                "result = df[['DEVICE', 'PRODUCTION']]"
            )
        },
    )

    trace = result["trace"]["inspection"]["pandas_execution"]
    assert result["data"]["rows"] == [{"DEVICE": "DEV-RG", "PRODUCTION": 10}]
    assert trace["used_helpers"] == ["match_product_tokens", "sample_passthrough_helper"]
    assert "def sample_passthrough_helper" in trace["effective_code_with_helpers"]


def test_intent_normalizer_dedupes_single_and_multiple_function_cases():
    intent_normalizer = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "04_intent_plan_normalizer.py")
    payload = {"request": {"question": "제품 token 분석"}, "trace": {"warnings": [], "errors": [], "inspection": {}}}
    normalized = intent_normalizer.normalize_intent_plan(
        payload,
        {
            "intent_plan": {
                "analysis_kind": "product_token_analysis",
                "pandas_function_case": {
                    "key": "product_token_match",
                    "function_name": "match_product_tokens",
                    "input_text": "RG 32G DDR4 FBGA 96 DDP",
                    "source_alias": "production_data",
                },
                "pandas_function_cases": [
                    {
                        "key": "product_token_match",
                        "function_name": "match_product_tokens",
                        "input_text": "RG 32G DDR4 FBGA 96 DDP",
                        "source_alias": "production_data",
                    }
                ],
                "selected_function_cases": [{"key": "legacy"}],
                "retrieval_jobs": [{"dataset_key": "production_today", "source_alias": "production_data"}],
                "pandas_execution_plan": [{"step": "sum_production", "source_alias": "production_data"}],
            }
        },
    )

    assert "pandas_function_case" not in normalized["intent_plan"]
    assert "selected_function_cases" not in normalized["intent_plan"]
    assert normalized["intent_plan"]["pandas_function_cases"] == [
        {
            "key": "product_token_match",
            "function_name": "match_product_tokens",
            "input_text": "RG 32G DDR4 FBGA 96 DDP",
            "source_alias": "production_data",
        }
    ]
    assert [step["operation"] for step in normalized["intent_plan"]["pandas_execution_plan"][:1]] == ["apply_pandas_function_case"]


def test_specialized_function_examples_match_runtime_and_domain_authoring_contracts():
    removed_domain_md = (
        ROOT
        / "langflow_components"
        / "domain_authoring_flow"
        / "pandas_function_cases_raw_text_input_example.md"
    )
    removed_context_json = (
        ROOT
        / "langflow_components"
        / "data_analysis_flow"
        / "function_case_context_json_input_example.json"
    )
    domain_text = (ROOT / "domain_knowledge.txt").read_text(encoding="utf-8")
    helper_code = function_case_source()

    assert not removed_domain_md.exists()
    assert not removed_context_json.exists()
    assert "pandas function case 등록 규칙" in domain_text
    assert "section은 pandas_function_cases이고 key는 product_token_match" in domain_text
    assert "function_name은 match_product_tokens" in domain_text
    assert "section은 pandas_function_cases이고 key는 sample_passthrough_demo" in domain_text

    assert "def match_product_tokens" in helper_code
    assert "def sample_passthrough_helper" in helper_code
    assert "source_code_lines" not in helper_code


def test_pandas_repair_variables_and_retry_selector_use_failed_execution_context():
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    repair_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17a_pandas_repair_variables_builder.py")
    selector = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17c_pandas_retry_result_selector.py")
    payload = {
        "intent_plan": {"retrieval_jobs": [], "pandas_execution_plan": []},
        "runtime_sources": {"production_data": [{"DEVICE": "DEV001", "PRODUCTION": 10}]},
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }

    failed = pandas_executor.execute_pandas_code(payload, {"code": "result = sources['missing_data']"})
    variables = repair_variables.build_variables(failed, "1")

    assert failed["analysis"]["status"] == "error"
    assert variables["repair_required"] == "true"
    assert "missing_data" in variables["failed_code"]
    assert "KeyError" in variables["error_context_json"]

    retry = pandas_executor.execute_pandas_code(failed, {"code": "result = sources['production_data']"})
    selected = selector.select_pandas_result(failed, retry)

    assert selected["analysis"]["status"] == "ok"
    assert selected["trace"]["inspection"]["pandas_retry_selection"]["selected"] == "retry"


def test_pandas_filter_preamble_handles_compound_null_empty_filters_and_repair_scope():
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_code_executor.py")
    repair_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "17a_pandas_repair_variables_builder.py")
    payload = {
        "intent_plan": {
            "retrieval_jobs": [
                {
                    "dataset_key": "production",
                    "source_alias": "production",
                    "filters": {
                        "MODE": {"operator": "starts_with_any", "value": ["LP"]},
                        "PKG_TYPE1": {"operator": "in", "value": ["LFBGA", "TFBGA", "UFBGA", "VFBGA", "WFBGA"]},
                        "MCP_NO": {"operator": "or", "value": [{"operator": "isNull"}, {"operator": "isEmpty"}]},
                    },
                }
            ],
            "pandas_execution_plan": [],
        },
        "runtime_sources": {
            "production": [
                {"MODE": "LPDDR5", "PKG1": "LFBGA", "MCP_NO": "", "DEVICE": "MOBILE-1", "PRODUCTION": 10},
                {"MODE": "LPDDR5", "PKG1": "LFBGA", "MCP_NO": "MCP001", "DEVICE": "POP-1", "PRODUCTION": 99},
                {"MODE": "DDR4", "PKG1": "FBGA", "MCP_NO": "", "DEVICE": "OTHER-1", "PRODUCTION": 88},
            ]
        },
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }
    bad_llm_code = "if True:\nresult = sources['production']"

    failed = pandas_executor.execute_pandas_code(payload, {"code": bad_llm_code})
    variables = repair_variables.build_variables(failed, "1")
    error_context = json.loads(variables["error_context_json"])
    generated_code = failed["trace"]["inspection"]["pandas_execution"]["generated_code"]

    assert failed["analysis"]["status"] == "error"
    assert "expected an indented block" in failed["analysis"]["error"]["message"]
    assert variables["failed_code"] == bad_llm_code
    assert "_filtered_source_1_production" in error_context["executed_code_with_preamble"]
    assert error_context["repair_code_scope"].startswith("failed_code")
    assert "if _filter_col_1_1:\n    _filter_col_1_2" not in generated_code
    assert ".str.startswith" in generated_code
    assert ".isna()" in generated_code
    assert ".str.strip().eq('')" in generated_code

    retry = pandas_executor.execute_pandas_code(failed, {"code": "result = sources['production'][['DEVICE', 'PRODUCTION']]"})

    assert retry["analysis"]["status"] == "ok"
    assert retry["data"]["rows"] == [{"DEVICE": "MOBILE-1", "PRODUCTION": 10}]


def test_langflow_dummy_data_covers_representative_manufacturing_cases():
    dummy = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "08_dummy_data_retriever.py")
    payload = dummy.retrieve_dummy_data(
        {
            "retrieval_job_bundle": {
                "source_type": "dummy",
                "jobs": [
                    {"dataset_key": "production_today", "source_alias": "production_today", "required_params": {"DATE": "20260701"}},
                    {"dataset_key": "production", "source_alias": "production", "required_params": {"DATE": "20260630"}},
                    {"dataset_key": "wip", "source_alias": "wip", "required_params": {"DATE": "20260630"}},
                    {"dataset_key": "wip", "source_alias": "wip_boh_0627", "required_params": {"DATE": "20260626"}},
                ],
            }
        }
    )
    results = {item["source_alias"]: item["rows"] for item in payload["source_results"]}

    assert any(row["OPER_NAME"] == "INPUT" and str(row["MCP_NO"]).startswith("L-267") for row in results["production_today"])
    assert any(row["OPER_NAME"] == "FCB/H" and row["DEVICE"] == "DEV-SP-DDR5" for row in results["production"])
    assert any(row["OPER_NAME"] == "SBM" and row["MCP_NO"] == "L-218K8H" for row in results["production"])
    assert any(row["OPER_NAME"].startswith("W/B") and row["FAMILY"] == "HBM" for row in results["wip"])
    assert any(row["OPER_NAME"] == "D/A1" and row["DEVICE"] == "DEV-DA-GDDR6" for row in results["wip"])
    assert any(row["OPER_NAME"].startswith("W/B") for row in results["wip_boh_0627"])


def test_data_analysis_split_mongodb_metadata_loaders_use_v4_env_defaults(monkeypatch):
    store = install_fake_pymongo(monkeypatch)
    set_v4_mongo_env(monkeypatch)
    store["datagov"] = {
        "agent_v4_domain_items": {
            "domain:process_groups:DA": {"_id": "domain:process_groups:DA", "section": "process_groups", "key": "DA", "status": "active", "payload": {"processes": ["D/A1"]}},
        },
        "agent_v4_table_catalog_items": {
            "table_catalog:wip_today": {"_id": "table_catalog:wip_today", "dataset_key": "wip_today", "status": "active", "payload": {"source_type": "oracle"}},
        },
        "agent_v4_main_flow_filters": {
            "main_flow_filter:DATE": {"_id": "main_flow_filter:DATE", "filter_key": "DATE", "status": "active", "payload": {"operator": "eq"}},
        },
    }
    domain_loader = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "01a_mongodb_domain_metadata_loader.py")
    table_loader = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "01b_mongodb_table_catalog_loader.py")
    main_variable_loader = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "01c_mongodb_main_variable_loader.py")
    candidates_builder = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "01d_metadata_candidates_builder.py")

    domain_result = domain_loader.load_domain_metadata(limit="50")
    table_result = table_loader.load_table_catalog_metadata(limit="50")
    main_variable_result = main_variable_loader.load_main_variable_metadata(limit="50")
    result = candidates_builder.build_metadata_candidates(domain_result, table_result, main_variable_result)

    assert result["metadata_load"]["status"] == "ok"
    assert result["metadata_load"]["counts"] == {"domain_items": 1, "table_catalog_items": 1, "main_flow_filters": 1}
    assert result["metadata_load"]["loads"]["domain_items"]["database"] == "datagov"
    assert result["metadata_load"]["loads"]["domain_items"]["collection_name"] == "agent_v4_domain_items"
    assert result["metadata_load"]["loads"]["table_catalog_items"]["collection_name"] == "agent_v4_table_catalog_items"
    assert result["metadata_load"]["loads"]["main_flow_filters"]["collection_name"] == "agent_v4_main_flow_filters"
    assert result["metadata_load"]["loads"]["domain_items"]["status_filter"] == "active"
    assert result["metadata_candidates"]["table_catalog_items"][0]["dataset_key"] == "wip_today"
    assert "_id" not in result["metadata_candidates"]["domain_items"][0]


def test_metadata_candidates_remove_authoring_trace_but_keep_runtime_catalog_fields():
    candidates_builder = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "01d_metadata_candidates_builder.py")
    result = candidates_builder.build_metadata_candidates(
        {
            "domain_items": [
                {
                    "_id": "domain:process_groups:DA",
                    "section": "process_groups",
                    "key": "DA",
                    "text": "authoring-only text",
                    "registration_trace": {"raw_text": "원문 전체"},
                    "raw_trace": {"llm": "debug"},
                    "payload": {
                        "display_name": "D/A",
                        "aliases": ["DA"],
                        "raw_text": "payload raw text",
                        "description": "공정 그룹 설명",
                    },
                    "review": {"ready_to_save": True},
                    "updated_at": "2026-07-03T00:00:00Z",
                }
            ],
            "metadata_load": {"status": "ok"},
        },
        {
            "table_catalog_items": [
                {
                    "_id": "table_catalog:production_today",
                    "dataset_key": "production_today",
                    "registration_trace": {"raw_text": "catalog 원문"},
                    "payload": {
                        "source_type": "oracle",
                        "source_config": {
                            "db_key": "PNT_RPT",
                            "query_template": "SELECT * FROM PROD WHERE WORK_DATE = {DATE}",
                        },
                        "required_params": ["DATE"],
                    },
                }
            ],
            "metadata_load": {"status": "ok"},
        },
        {"main_flow_filters": [], "metadata_load": {"status": "ok"}},
    )

    domain_item = result["metadata_candidates"]["domain_items"][0]
    catalog_item = result["metadata_candidates"]["table_catalog_items"][0]

    assert "_id" not in domain_item
    assert "text" not in domain_item
    assert "registration_trace" not in domain_item
    assert "raw_trace" not in domain_item
    assert "review" not in domain_item
    assert "updated_at" not in domain_item
    assert "raw_text" not in domain_item["payload"]
    assert domain_item["payload"]["description"] == "공정 그룹 설명"
    assert "registration_trace" not in catalog_item
    assert catalog_item["payload"]["source_config"]["query_template"].startswith("SELECT *")
    assert result["domain_items"] == result["metadata_candidates"]["domain_items"]


def test_metadata_candidates_mark_non_runtime_pandas_function_cases():
    candidates_builder = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "01d_metadata_candidates_builder.py")
    result = candidates_builder.build_metadata_candidates(
        {
            "domain_items": [
                {
                    "section": "pandas_function_cases",
                    "key": "calculate_production_by_oper_name",
                    "payload": {"function_name": "calculate_production_by_oper_name"},
                },
                {
                    "section": "pandas_function_cases",
                    "key": "product_token_match",
                    "payload": {"function_name": "match_product_tokens"},
                },
                {
                    "section": "pandas_function_cases",
                    "key": "component_token_product_lookup",
                    "payload": {"pseudocode": "filtered_df = match_product_tokens(product_dataframe, product_tokens)"},
                },
            ],
            "metadata_load": {"status": "ok"},
        },
        {"table_catalog_items": [], "metadata_load": {"status": "ok"}},
        {"main_flow_filters": [], "metadata_load": {"status": "ok"}},
    )

    items = {item["key"]: item for item in result["metadata_candidates"]["domain_items"]}
    assert items["calculate_production_by_oper_name"]["runtime_helper"] == {
        "function_name": "calculate_production_by_oper_name",
        "available": False,
        "selectable_for_intent": False,
        "selection_policy": "not_registered_runtime_helper",
    }
    assert "intent_plan.pandas_function_cases로 선택하지 않는다" in items["calculate_production_by_oper_name"]["selection_note"]
    assert items["product_token_match"]["runtime_helper"]["function_name"] == "match_product_tokens"
    assert items["product_token_match"]["runtime_helper"]["available"] is True
    assert items["product_token_match"]["runtime_helper"]["selectable_for_intent"] is True
    assert items["component_token_product_lookup"]["runtime_helper"]["function_name"] == "match_product_tokens"
    assert items["component_token_product_lookup"]["runtime_helper"]["selectable_for_intent"] is True
    assert result["metadata_candidates"]["runtime_function_helpers"][0]["function_name"] == "match_product_tokens"
    assert result["metadata_load"]["counts"] == {"domain_items": 3, "table_catalog_items": 0, "main_flow_filters": 0}


def test_data_analysis_mongodb_result_store_and_loader_round_trip(monkeypatch):
    mongo_store = install_fake_pymongo(monkeypatch)
    set_v4_mongo_env(monkeypatch)
    result_store = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "23_mongodb_result_store.py")
    result_loader = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "05_mongodb_result_loader.py")
    payload = {
        "request": {"session_id": "s1", "question": "재공 합계"},
        "metadata_refs": [{"type": "table_catalog", "key": "wip_today"}],
        "intent_plan": {"analysis_kind": "wip_sum"},
        "source_results": [{"source_alias": "wip_data", "row_count": 1}],
        "runtime_sources": {"wip_data": [{"OPER_NAME": "D/A1", "WIP": 120}]},
        "analysis": {"status": "ok", "row_count": 1, "columns": ["OPER_NAME", "wip_sum"], "rows": [{"OPER_NAME": "D/A1", "wip_sum": 120}]},
        "data": {"columns": ["OPER_NAME", "wip_sum"], "rows": [{"OPER_NAME": "D/A1", "wip_sum": 120}], "row_count": 1},
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }

    stored = result_store.store_result(payload, ttl_hours="3")
    data_ref = stored["data"]["data_ref"]
    ref_id = data_ref["ref_id"]
    restored = result_loader.load_previous_result(
        {
            "request": {"session_id": "s1", "question": "이전 결과 다시 보여줘"},
            "state": {"current_data": {"data_ref": data_ref}},
            "trace": {"warnings": [], "errors": [], "inspection": {}},
        }
    )

    assert ref_id.startswith("result:s1:")
    assert data_ref["role"] == "analysis_result"
    assert data_ref["path"] == "payload.result_rows"
    assert stored["data_refs"][0] == data_ref
    assert stored["data_refs"][1]["role"] == "source_rows"
    assert stored["data_refs"][1]["source_alias"] == "wip_data"
    assert stored["trace"]["inspection"]["result_store"]["collection_name"] == "agent_v4_result_store"
    assert stored["trace"]["inspection"]["result_store"]["ttl_hours"] == 3
    assert "expires_at" in stored["trace"]["inspection"]["result_store"]
    result_doc = mongo_store["datagov"]["agent_v4_result_store"][ref_id]
    assert result_doc["ttl_hours"] == 3
    assert isinstance(result_doc["expires_at"], datetime)
    assert result_doc["expires_at"] > datetime.now(timezone.utc)
    assert result_doc["payload"]["result_rows"] == [{"OPER_NAME": "D/A1", "wip_sum": 120}]
    assert "rows" not in result_doc["payload"]["data"]
    assert "rows" not in result_doc["payload"]["analysis"]
    assert restored["trace"]["inspection"]["result_loader"]["status"] == "ok"
    assert restored["runtime_sources"]["wip_data"][0]["WIP"] == 120
    assert restored["data"]["rows"] == [{"OPER_NAME": "D/A1", "wip_sum": 120}]
    assert restored["data"]["data_ref"] == data_ref

    data_ref_store = load_module(ROOT / "web_app" / "data_ref_store.py")
    result_rows = data_ref_store.load_data_ref_rows(data_ref, "mongodb://fake")
    source_rows = data_ref_store.load_data_ref_rows(stored["data_refs"][1], "mongodb://fake")
    assert result_rows["rows"] == [{"OPER_NAME": "D/A1", "wip_sum": 120}]
    assert source_rows["rows"] == [{"OPER_NAME": "D/A1", "WIP": 120}]


def test_mongodb_result_loader_accepts_legacy_data_rows(monkeypatch):
    mongo_store = install_fake_pymongo(monkeypatch)
    set_v4_mongo_env(monkeypatch)
    result_loader = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "05_mongodb_result_loader.py")
    mongo_store.setdefault("datagov", {}).setdefault("agent_v4_result_store", {})["legacy-ref"] = {
        "_id": "legacy-ref",
        "payload": {
            "source_results": [],
            "runtime_sources": {},
            "analysis": {"status": "ok", "row_count": 1},
            "data": {"columns": ["DEVICE"], "rows": [{"DEVICE": "LEGACY"}], "row_count": 1},
        },
    }

    restored = result_loader.load_previous_result(
        {
            "data": {"data_ref": "legacy-ref"},
            "trace": {"warnings": [], "errors": [], "inspection": {}},
        }
    )

    assert restored["trace"]["inspection"]["result_loader"]["status"] == "ok"
    assert restored["data"]["rows"] == [{"DEVICE": "LEGACY"}]
    assert restored["data"]["data_ref"]["path"] == "payload.result_rows"


def test_data_analysis_mongodb_result_store_has_ttl_input():
    result_store = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "23_mongodb_result_store.py")

    input_names = {item.kwargs.get("name") for item in result_store.MongoDBResultStore.inputs}

    assert "ttl_hours" in input_names


def test_data_ref_store_rejects_expired_document():
    data_ref_store = load_module(ROOT / "web_app" / "data_ref_store.py")

    loaded = data_ref_store.rows_from_data_ref_document(
        {
            "expires_at": datetime.now(timezone.utc) - timedelta(hours=1),
            "payload": {"result_rows": [{"DEVICE": "DEV-A"}]},
        },
        path="payload.result_rows",
    )

    assert loaded["ok"] is False
    assert loaded["expired"] is True
    assert loaded["rows"] == []


def test_mongodb_previous_result_loader_uses_payload_data_ref_only():
    result_loader = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "05_mongodb_result_loader.py")

    input_names = {item.kwargs.get("name") for item in result_loader.MongoDBResultLoader.inputs}
    payload = {"trace": {"warnings": [], "errors": [], "inspection": {}}}
    skipped = result_loader.load_previous_result(payload)

    assert "payload" in input_names
    assert "data_ref" not in input_names
    assert skipped["trace"]["warnings"] == []
    assert skipped["trace"]["inspection"]["result_loader"]["status"] == "skipped"
    assert skipped["trace"]["inspection"]["result_loader"]["errors"][0]["type"] == "missing_data_ref"


def test_restored_runtime_sources_survive_empty_retrieval_merge():
    merger = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "13_source_retrieval_merger.py")
    adapter = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "14_retrieval_payload_adapter.py")
    payload = {
        "source_results": [{"source_alias": "wip_data", "row_count": 1}],
        "runtime_sources": {"wip_data": [{"OPER_NAME": "D/A1", "WIP": 120}]},
        "trace": {"warnings": [], "errors": [], "inspection": {"result_loader": {"status": "ok"}}},
    }

    merged = merger.merge_source_retrieval_payloads(payload, {"source_type": "oracle", "status": "skipped", "skipped": True, "skip_reason": "no oracle retrieval jobs"})
    adapted = adapter.build_retrieval_payload(merged)

    assert adapted["runtime_sources"]["wip_data"][0]["WIP"] == 120
    assert adapted["trace"]["inspection"]["data_retrieval"]["preserved_existing_runtime_sources"] is True


def test_oracle_retriever_executes_sql_with_configured_tns():
    oracle = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "09_oracle_query_retriever.py")

    class FakeCursor:
        description = [("WORK_DATE",), ("PRODUCTION",)]

        def __init__(self):
            self.executed_sql = ""

        def execute(self, sql):
            self.executed_sql = sql

        def fetchmany(self, limit):
            assert limit == 100
            return [("20260701", 1234)]

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self):
            return self.cursor_obj

        def close(self):
            pass

    class FakeOracleModule:
        def __init__(self):
            self.connection = FakeConnection()
            self.connect_kwargs = {}

        def connect(self, **kwargs):
            self.connect_kwargs = kwargs
            return self.connection

    fake_oracle = FakeOracleModule()
    oracle.OracleQueryRetriever.oracledb = fake_oracle
    payload = {
        "retrieval_job_bundle": {
            "source_type": "oracle",
            "jobs": [
                {
                    "job_id": "job_1",
                    "dataset_key": "production_today",
                    "source_alias": "prod_data",
                    "source_type": "oracle",
                    "source_config": {
                        "source_type": "oracle",
                        "db_key": "PNT_RPT",
                        "query_template": "SELECT WORK_DATE, PRODUCTION FROM PROD_TABLE WHERE WORK_DATE = {DATE}",
                    },
                    "required_params": {"DATE": "20260701"},
                    "filters": {"OPER_NAME": {"operator": "eq", "value": "D/A1"}},
                }
            ],
        }
    }

    result = oracle.retrieve_oracle_data(payload, json.dumps({"PNT_RPT": {"user": "u", "password": "p", "tns": "tns-value"}}), "100")
    source_result = result["source_results"][0]

    assert result["status"] == "ok"
    assert fake_oracle.connect_kwargs == {"user": "u", "password": "p", "dsn": "tns-value"}
    assert source_result["rows"] == [{"WORK_DATE": "20260701", "PRODUCTION": 1234}]
    assert source_result["source_execution"]["executed_query"] == "SELECT WORK_DATE, PRODUCTION FROM PROD_TABLE WHERE WORK_DATE = '20260701'"
    assert source_result["source_execution"]["filters_applied_in_retriever"] is False
    assert source_result["pandas_filters"] == {"OPER_NAME": {"operator": "eq", "value": "D/A1"}}
    assert "applied_filters" not in source_result


def test_oracle_retriever_parses_named_tns_block():
    oracle = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "09_oracle_query_retriever.py")

    config, errors = oracle._oracle_config_from_value("PNT_RPT:\n(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP))(CONNECT_DATA=(SERVICE_NAME=PNT)))")

    assert errors == []
    assert config == {"PNT_RPT": {"tns": "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP))(CONNECT_DATA=(SERVICE_NAME=PNT)))"}}


def test_langflow_prompt_templates_are_external_files_for_agent_nodes():
    prompt_files = [
        ROOT / "langflow_components" / "data_analysis_flow" / "03_intent_prompt_template_ko.md",
        ROOT / "langflow_components" / "data_analysis_flow" / "16_pandas_prompt_template_ko.md",
        ROOT / "langflow_components" / "data_analysis_flow" / "19_answer_prompt_template_ko.md",
        ROOT / "langflow_components" / "domain_authoring_flow" / "01_text_refinement_prompt_template_ko.md",
        ROOT / "langflow_components" / "domain_authoring_flow" / "03_authoring_prompt_template_ko.md",
        ROOT / "langflow_components" / "domain_authoring_flow" / "06_review_prompt_template_ko.md",
        ROOT / "langflow_components" / "table_catalog_authoring_flow" / "01_text_refinement_prompt_template_ko.md",
        ROOT / "langflow_components" / "table_catalog_authoring_flow" / "03_authoring_prompt_template_ko.md",
        ROOT / "langflow_components" / "table_catalog_authoring_flow" / "06_review_prompt_template_ko.md",
        ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "01_text_refinement_prompt_template_ko.md",
        ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "03_authoring_prompt_template_ko.md",
        ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "06_review_prompt_template_ko.md",
    ]
    for path in prompt_files:
        text = path.read_text(encoding="utf-8")
        assert "너는" in text

    for guide_name in [
        "data_analysis_flow",
        "domain_authoring_flow",
        "table_catalog_authoring_flow",
        "main_flow_filters_authoring_flow",
    ]:
        guide = (ROOT / "langflow_components" / guide_name / "CONNECTION_GUIDE.md").read_text(encoding="utf-8")
        assert "Langflow Prompt Template" in guide
        assert "Langflow Agent/LLM" in guide


def test_metadata_authoring_guide_uses_current_writer_ports():
    guide = (ROOT / "docs" / "METADATA_AUTHORING_FLOW_GUIDE.md").read_text(encoding="utf-8")

    assert "MongoDB Writer.authoring_payload" not in guide
    assert "MongoDB Writer.review_payload" not in guide
    assert "Review Writer.review_response" in guide
    assert "API Adapter.api_response" in guide


def test_data_analysis_connection_guide_intent_numbers_are_contiguous():
    import re

    guide = (ROOT / "langflow_components" / "data_analysis_flow" / "CONNECTION_GUIDE.md").read_text(encoding="utf-8")
    intent_section = guide.split("## 2. 이전 결과 복원", 1)[0]
    numbers = [int(match.group(1)) for match in re.finditer(r"^\| (\d+) \|", intent_section, flags=re.MULTILINE)]

    assert numbers == list(range(1, 16))


def test_langflow_prompt_templates_only_expose_valid_variables():
    import re

    allowed = {
        "raw_text",
        "existing_metadata_summary",
        "refined_text",
        "review_input_json",
        "question",
        "state_summary",
        "metadata_candidates",
        "specialized_prompt",
        "output_schema",
        "intent_plan_json",
        "source_schema_json",
        "source_preview_json",
        "function_case_helper_code",
        "function_case_selection_json",
        "repair_required",
        "failed_code",
        "error_context_json",
            "output_contract_json",
            "result_summary_json",
            "applied_scope_json",
            "answer_context_json",
            "metadata_context_json",
                "domain_answer_guidance",
                "warnings_errors_json",
                "user_input",
            "route_candidates_json",
            "routing_rules",
            "output_schema_json",
        }
    prompt_files = sorted((ROOT / "langflow_components").glob("*/*prompt_template_ko.md"))
    for path in prompt_files:
        text = path.read_text(encoding="utf-8")
        variables = {
            match.group(1)
            for match in re.finditer(r"(?<!\{)\{([^{}\r\n]+)\}(?!\})", text)
        }
        assert variables <= allowed, f"{path.name} exposes invalid Langflow variables: {variables - allowed}"
        assert "" not in variables


def test_langflow_prompt_templates_keep_domain_specific_examples_out_of_generic_prompts():
    prompt_text_by_path = {
        path: path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "langflow_components").glob("*/*prompt_template_ko.md"))
    }
    specialized_prompt = (
        ROOT
        / "langflow_components"
        / "data_analysis_flow"
        / "specialized_prompt_input_example_ko.md"
    ).read_text(encoding="utf-8")
    moved_to_specialized_prompt_terms = [
        "match_product_tokens",
        "sample_passthrough_helper",
        "RG 32G DDR4 FBGA 96 DDP",
        "DA 16G GDDR6 180",
        "PKG OUT",
        "BOH",
        "현시간 기준 재공",
        "x16",
        "X8",
        "L-218",
        "A-663",
    ]
    generic_prompt_blocklist = moved_to_specialized_prompt_terms + [
        "POP",
        "MOBILE",
        "HBM",
        "D/A",
        "wip_today",
        "PNT_RPT",
        "OPER_NAME",
        "WORK_DATE",
    ]

    for term in generic_prompt_blocklist:
        for path, text in prompt_text_by_path.items():
            assert term not in text, f"{path.name} contains domain-specific example: {term}"

    for term in moved_to_specialized_prompt_terms:
        assert term in specialized_prompt


def test_prompt_variable_builder_output_order_matches_prompt_input_order():
    import re

    prompt_to_builder = [
        ("data_analysis_flow/03_intent_prompt_template_ko.md", "data_analysis_flow/02_intent_variables_builder.py"),
        ("data_analysis_flow/16_pandas_prompt_template_ko.md", "data_analysis_flow/15_pandas_variables_builder.py"),
        ("data_analysis_flow/17b_pandas_repair_prompt_template_ko.md", "data_analysis_flow/17a_pandas_repair_variables_builder.py"),
        ("data_analysis_flow/19_answer_prompt_template_ko.md", "data_analysis_flow/18_answer_variables_builder.py"),
        ("domain_authoring_flow/01_text_refinement_prompt_template_ko.md", "domain_authoring_flow/01_domain_text_refinement_variables_builder.py"),
        ("domain_authoring_flow/03_authoring_prompt_template_ko.md", "domain_authoring_flow/03_domain_authoring_variables_builder.py"),
        ("domain_authoring_flow/06_review_prompt_template_ko.md", "domain_authoring_flow/06_domain_review_variables_builder.py"),
        ("table_catalog_authoring_flow/01_text_refinement_prompt_template_ko.md", "table_catalog_authoring_flow/01_table_catalog_text_refinement_variables_builder.py"),
        ("table_catalog_authoring_flow/03_authoring_prompt_template_ko.md", "table_catalog_authoring_flow/03_table_catalog_authoring_variables_builder.py"),
        ("table_catalog_authoring_flow/06_review_prompt_template_ko.md", "table_catalog_authoring_flow/06_table_catalog_review_variables_builder.py"),
        ("main_flow_filters_authoring_flow/01_text_refinement_prompt_template_ko.md", "main_flow_filters_authoring_flow/01_main_flow_filter_text_refinement_variables_builder.py"),
        ("main_flow_filters_authoring_flow/03_authoring_prompt_template_ko.md", "main_flow_filters_authoring_flow/03_main_flow_filter_authoring_variables_builder.py"),
        ("main_flow_filters_authoring_flow/06_review_prompt_template_ko.md", "main_flow_filters_authoring_flow/06_main_flow_filter_review_variables_builder.py"),
    ]
    manual_prompt_variables = {
        "data_analysis_flow/03_intent_prompt_template_ko.md": {"specialized_prompt"},
            "data_analysis_flow/16_pandas_prompt_template_ko.md": {"function_case_helper_code"},
            "data_analysis_flow/17b_pandas_repair_prompt_template_ko.md": {"function_case_helper_code"},
            "data_analysis_flow/19_answer_prompt_template_ko.md": {"domain_answer_guidance"},
        }

    for prompt_relpath, builder_relpath in prompt_to_builder:
        prompt_path = ROOT / "langflow_components" / prompt_relpath
        builder_path = ROOT / "langflow_components" / builder_relpath
        prompt_variables = []
        for match in re.finditer(r"(?<!\{)\{([^{}\r\n]+)\}(?!\})", prompt_path.read_text(encoding="utf-8")):
            variable_name = match.group(1)
            if variable_name not in prompt_variables:
                prompt_variables.append(variable_name)

        module = load_module(builder_path)
        component_classes = [
            value
            for value in vars(module).values()
            if isinstance(value, type) and value.__module__ == module.__name__ and hasattr(value, "outputs")
        ]
        assert len(component_classes) == 1, builder_path.name
        output_names = [item.kwargs.get("name") for item in component_classes[0].outputs]

        expected_output_names = [
            name
            for name in prompt_variables
            if name not in manual_prompt_variables.get(prompt_relpath, set())
        ]

        assert output_names == expected_output_names, f"{builder_path.name} output order must match {prompt_path.name} input order"


def test_variable_builders_do_not_expose_redundant_variables_output():
    variable_builder_files = sorted((ROOT / "langflow_components").glob("*/*variables_builder.py"))
    assert variable_builder_files
    for path in variable_builder_files:
        text = path.read_text(encoding="utf-8")
        assert 'name="variables"' not in text, f"{path.name} exposes redundant variables output"
        assert 'display_name="변수"' not in text, f"{path.name} exposes redundant variables display label"
        assert "def build_payload" not in text, f"{path.name} keeps redundant variables payload builder"


def test_multi_output_components_expose_all_ports_simultaneously():
    for path in COMPONENT_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == "outputs" for target in node.targets):
                continue
            if not isinstance(node.value, ast.List):
                continue
            output_calls = [item for item in node.value.elts if isinstance(item, ast.Call)]
            if len(output_calls) <= 1:
                continue
            for call in output_calls:
                kwargs = {keyword.arg: keyword.value for keyword in call.keywords}
                group_outputs = kwargs.get("group_outputs")
                assert isinstance(group_outputs, ast.Constant) and group_outputs.value is True, f"{path.name}:{call.lineno} multi-output port is missing group_outputs=True"


def test_message_output_ports_declare_message_type():
    for path in COMPONENT_FILES:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        message_methods = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and isinstance(node.returns, ast.Name)
            and node.returns.id == "Message"
        }
        if not message_methods:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "Output":
                continue
            kwargs = {keyword.arg: keyword.value for keyword in node.keywords}
            method_value = kwargs.get("method")
            if not isinstance(method_value, ast.Constant) or method_value.value not in message_methods:
                continue
            types_value = kwargs.get("types")
            assert isinstance(types_value, ast.List), f"{path.name}:{node.lineno} Message output is missing types=['Message']"
            type_names = [item.value for item in types_value.elts if isinstance(item, ast.Constant)]
            assert "Message" in type_names, f"{path.name}:{node.lineno} Message output has wrong types={type_names}"


def test_domain_langflow_authoring_blocks_source_config_in_dry_run():
    request_loader = load_module(ROOT / "langflow_components" / "domain_authoring_flow" / "00_domain_authoring_request_loader.py")
    normalizer = load_module(ROOT / "langflow_components" / "domain_authoring_flow" / "04_domain_authoring_result_normalizer.py")
    writer = load_module(ROOT / "langflow_components" / "domain_authoring_flow" / "07_domain_review_writer.py")
    payload = request_loader.build_request("BAD domain", "ask", "true")
    payload = normalizer.normalize_authoring(
        payload,
        {
            "items": [
                {
                    "section": "process_groups",
                    "key": "BAD",
                    "payload": {"source_config": {"query_template": "SELECT * FROM X"}},
                }
            ]
        },
    )

    result = writer.review_and_write(payload)

    assert result["write_result"]["success"] is False
    assert result["write_result"]["errors"][0]["type"] == "domain_source_config_forbidden"


def test_domain_writer_keeps_deterministic_blockers_even_when_review_is_ready():
    request_loader = load_module(ROOT / "langflow_components" / "domain_authoring_flow" / "00_domain_authoring_request_loader.py")
    normalizer = load_module(ROOT / "langflow_components" / "domain_authoring_flow" / "04_domain_authoring_result_normalizer.py")
    writer = load_module(ROOT / "langflow_components" / "domain_authoring_flow" / "07_domain_review_writer.py")
    payload = request_loader.build_request("BAD domain", "ask", "true")
    payload = normalizer.normalize_authoring(
        payload,
        {"items": [{"section": "process_groups", "key": "BAD", "payload": {"source_config": {"query_template": "SELECT * FROM X"}}}]},
    )

    result = writer.review_and_write(payload, {"ready_to_save": True, "errors": [], "supplement_requests": []})

    assert result["write_result"]["success"] is False
    assert result["write_result"]["errors"][0]["type"] == "domain_source_config_forbidden"


def test_table_catalog_langflow_writer_blocks_truncated_query():
    request_loader = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "00_table_catalog_authoring_request_loader.py")
    normalizer = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "04_table_catalog_authoring_result_normalizer.py")
    writer = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "07_table_catalog_review_writer.py")
    payload = request_loader.build_request("bad query", "ask", "true")
    payload = normalizer.normalize_authoring(
        payload,
        {
            "items": [
                {
                    "dataset_key": "bad",
                    "payload": {
                        "source_type": "oracle",
                        "source_config": {"source_type": "oracle", "db_key": "PNT_RPT", "query_template": "SELECT ..."},
                    },
                }
            ]
        },
    )

    result = writer.review_and_write(payload)

    assert result["write_result"]["success"] is False
    assert any(error["type"] == "truncated_query" for error in result["write_result"]["errors"])


def test_table_catalog_writer_allows_sql_line_comments_and_preserves_query():
    request_loader = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "00_table_catalog_authoring_request_loader.py")
    normalizer = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "04_table_catalog_authoring_result_normalizer.py")
    writer = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "07_table_catalog_review_writer.py")
    sql = "--쿼리 작성\nSELECT WORK_DATE, OPER_NAME, WIP\nFROM WIP_TABLE\nWHERE WORK_DATE = {DATE}"
    payload = request_loader.build_request("commented query", "ask", "true")
    payload = normalizer.normalize_authoring(
        payload,
        {
            "items": [
                {
                    "dataset_key": "wip_today",
                    "payload": {
                        "source_type": "oracle",
                        "source_config": {"source_type": "oracle", "db_key": "PNT_RPT", "query_template": sql},
                    },
                }
            ]
        },
    )

    result = writer.review_and_write(payload)

    assert result["write_result"]["success"] is True
    assert result["items"][0]["payload"]["source_config"]["query_template"] == sql


def test_table_catalog_writer_allows_with_cte_query():
    request_loader = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "00_table_catalog_authoring_request_loader.py")
    normalizer = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "04_table_catalog_authoring_result_normalizer.py")
    writer = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "07_table_catalog_review_writer.py")
    sql = "WITH base AS (\n  SELECT WORK_DATE, OPER_NAME, WIP FROM WIP_TABLE\n)\nSELECT * FROM base WHERE WORK_DATE = {DATE}"
    payload = request_loader.build_request("with query", "ask", "true")
    payload = normalizer.normalize_authoring(
        payload,
        {
            "items": [
                {
                    "dataset_key": "wip_today_cte",
                    "payload": {
                        "source_type": "oracle",
                        "source_config": {"source_type": "oracle", "db_key": "PNT_RPT", "query_template": sql},
                    },
                }
            ]
        },
    )

    result = writer.review_and_write(payload)

    assert result["write_result"]["success"] is True
    assert result["items"][0]["payload"]["source_config"]["query_template"].startswith("WITH base AS")


def test_table_and_filter_writers_respect_negative_review_response():
    table_request_loader = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "00_table_catalog_authoring_request_loader.py")
    table_normalizer = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "04_table_catalog_authoring_result_normalizer.py")
    table_writer = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "07_table_catalog_review_writer.py")
    filter_request_loader = load_module(ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "00_main_flow_filter_authoring_request_loader.py")
    filter_normalizer = load_module(ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "04_main_flow_filter_authoring_result_normalizer.py")
    filter_writer = load_module(ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "07_main_flow_filter_review_writer.py")
    table_payload = table_request_loader.build_request("wip_today", "ask", "true")
    table_payload = table_normalizer.normalize_authoring(
        table_payload,
        {
            "items": [
                {
                    "dataset_key": "wip_today",
                    "payload": {
                        "source_type": "oracle",
                        "source_config": {"source_type": "oracle", "db_key": "PNT_RPT", "query_template": "SELECT WORK_DATE, WIP FROM WIP_TABLE WHERE WORK_DATE = {DATE}"},
                    },
                }
            ]
        },
    )
    filter_payload = filter_request_loader.build_request("DATE는 기준일입니다.", "ask", "true")
    filter_payload = filter_normalizer.normalize_authoring(
        filter_payload,
        {"items": [{"filter_key": "DATE", "payload": {"display_name": "기준일", "aliases": ["오늘"], "operator": "eq", "value_type": "date", "value_shape": "scalar"}}]},
    )
    negative_review = {"ready_to_save": False, "errors": [{"type": "review_rejected", "message": "검수 보류"}], "supplement_requests": []}

    table_result = table_writer.review_and_write(table_payload, negative_review)
    filter_result = filter_writer.review_and_write(filter_payload, negative_review)

    assert table_result["write_result"]["success"] is False
    assert table_result["write_result"]["errors"][0]["type"] == "review_rejected"
    assert filter_result["write_result"]["success"] is False
    assert filter_result["write_result"]["errors"][0]["type"] == "review_rejected"


def test_authoring_writers_use_v4_mongo_env_defaults(monkeypatch):
    store = install_fake_pymongo(monkeypatch)
    set_v4_mongo_env(monkeypatch)
    domain_request_loader = load_module(ROOT / "langflow_components" / "domain_authoring_flow" / "00_domain_authoring_request_loader.py")
    domain_normalizer = load_module(ROOT / "langflow_components" / "domain_authoring_flow" / "04_domain_authoring_result_normalizer.py")
    domain_writer = load_module(ROOT / "langflow_components" / "domain_authoring_flow" / "07_domain_review_writer.py")
    table_request_loader = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "00_table_catalog_authoring_request_loader.py")
    table_normalizer = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "04_table_catalog_authoring_result_normalizer.py")
    table_writer = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "07_table_catalog_review_writer.py")
    filter_request_loader = load_module(ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "00_main_flow_filter_authoring_request_loader.py")
    filter_normalizer = load_module(ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "04_main_flow_filter_authoring_result_normalizer.py")
    filter_writer = load_module(ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "07_main_flow_filter_review_writer.py")

    domain_payload = domain_request_loader.build_request("DA는 D/A1 공정입니다.", "ask", "false")
    domain_payload = domain_normalizer.normalize_authoring(domain_payload, {"items": [{"section": "process_groups", "key": "DA", "payload": {"processes": ["D/A1"]}}]})
    table_payload = table_request_loader.build_request("wip_today", "ask", "false")
    table_payload = table_normalizer.normalize_authoring(
        table_payload,
        {
            "items": [
                {
                    "dataset_key": "wip_today",
                    "payload": {
                        "source_type": "oracle",
                        "source_config": {"source_type": "oracle", "db_key": "PNT_RPT", "query_template": "SELECT WORK_DATE, WIP FROM WIP_TABLE WHERE WORK_DATE = {DATE}"},
                    },
                }
            ]
        },
    )
    filter_payload = filter_request_loader.build_request("DATE는 기준일입니다.", "ask", "false")
    filter_payload = filter_normalizer.normalize_authoring(
        filter_payload,
        {"items": [{"filter_key": "DATE", "payload": {"display_name": "기준일", "aliases": ["오늘"], "operator": "eq", "value_type": "date", "value_shape": "scalar"}}]},
    )

    domain_result = domain_writer.review_and_write(domain_payload)
    table_result = table_writer.review_and_write(table_payload)
    filter_result = filter_writer.review_and_write(filter_payload)

    assert domain_result["write_result"]["collection_name"] == "agent_v4_domain_items"
    assert table_result["write_result"]["collection_name"] == "agent_v4_table_catalog_items"
    assert filter_result["write_result"]["collection_name"] == "agent_v4_main_flow_filters"
    assert "domain:process_groups:DA" in store["datagov"]["agent_v4_domain_items"]
    assert "table_catalog:wip_today" in store["datagov"]["agent_v4_table_catalog_items"]
    assert "main_flow_filter:DATE" in store["datagov"]["agent_v4_main_flow_filters"]


def test_authoring_existing_item_loaders_use_v4_mongo_env_defaults(monkeypatch):
    store = install_fake_pymongo(monkeypatch)
    set_v4_mongo_env(monkeypatch)
    store["datagov"] = {
        "agent_v4_domain_items": {"domain:process_groups:DA": {"_id": "domain:process_groups:DA", "section": "process_groups", "key": "DA", "payload": {}}},
        "agent_v4_table_catalog_items": {"table_catalog:wip_today": {"_id": "table_catalog:wip_today", "dataset_key": "wip_today", "payload": {}}},
        "agent_v4_main_flow_filters": {"main_flow_filter:DATE": {"_id": "main_flow_filter:DATE", "filter_key": "DATE", "payload": {}}},
    }
    domain_loader = load_module(ROOT / "langflow_components" / "domain_authoring_flow" / "00_domain_existing_items_loader.py")
    table_loader = load_module(ROOT / "langflow_components" / "table_catalog_authoring_flow" / "00_table_catalog_existing_items_loader.py")
    filter_loader = load_module(ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "00_main_flow_filter_existing_items_loader.py")

    domain_result = domain_loader.load_existing_items()
    table_result = table_loader.load_existing_items()
    filter_result = filter_loader.load_existing_items()

    assert domain_result["metadata_load"]["collection_name"] == "agent_v4_domain_items"
    assert table_result["metadata_load"]["collection_name"] == "agent_v4_table_catalog_items"
    assert filter_result["metadata_load"]["collection_name"] == "agent_v4_main_flow_filters"
    assert domain_result["existing_items"][0]["key"] == "DA"
    assert table_result["existing_items"][0]["dataset_key"] == "wip_today"
    assert filter_result["existing_items"][0]["filter_key"] == "DATE"


def test_mongodb_metadata_export_upload_round_trip(monkeypatch, tmp_path):
    store = install_fake_pymongo(monkeypatch)
    set_v4_mongo_env(monkeypatch)
    store["datagov"] = {
        "agent_v4_domain_items": {
            "domain:process_groups:DA": {"_id": "domain:process_groups:DA", "section": "process_groups", "key": "DA", "status": "active", "payload": {"processes": ["D/A1"]}},
        },
        "agent_v4_table_catalog_items": {
            "table_catalog:wip_today": {"_id": "table_catalog:wip_today", "dataset_key": "wip_today", "status": "active", "payload": {"source_type": "oracle"}},
        },
        "agent_v4_main_flow_filters": {
            "main_flow_filter:DATE": {"_id": "main_flow_filter:DATE", "filter_key": "DATE", "status": "active", "payload": {"aliases": ["오늘"]}},
        },
    }
    export_tool = load_module(ROOT / "tools" / "export_mongodb_metadata_to_json.py")
    upload_tool = load_module(ROOT / "tools" / "upload_json_to_mongodb.py")
    output_path = tmp_path / "metadata_bundle.json"

    export_summary = export_tool.export_metadata_bundle(
        export_tool.MongoExportConfig(
            mongo_uri="mongodb://fake",
            database="datagov",
            collections={
                "domain": "agent_v4_domain_items",
                "table-catalog": "agent_v4_table_catalog_items",
                "main-flow-filter": "agent_v4_main_flow_filters",
            },
        ),
        ["domain", "table-catalog", "main-flow-filter"],
        output_path,
    )
    upload_summary = upload_tool.upload_bundle(
        output_path,
        upload_tool.MongoUploadConfig(
            mongo_uri="mongodb://fake",
            database="portable_datagov",
            collections={
                "domain": "agent_v4_domain_items",
                "table-catalog": "agent_v4_table_catalog_items",
                "main-flow-filter": "agent_v4_main_flow_filters",
            },
        ),
        [],
        mode="upsert",
    )

    assert export_summary["collections"]["domain"]["document_count"] == 1
    assert upload_summary["collections"]["main-flow-filter"]["written_count"] == 1
    assert store["portable_datagov"]["agent_v4_domain_items"]["domain:process_groups:DA"]["payload"]["processes"] == ["D/A1"]
    assert store["portable_datagov"]["agent_v4_table_catalog_items"]["table_catalog:wip_today"]["payload"]["source_type"] == "oracle"
    assert store["portable_datagov"]["agent_v4_main_flow_filters"]["main_flow_filter:DATE"]["payload"]["aliases"] == ["오늘"]


def test_langflow_writer_non_dry_run_requires_explicit_mongo_config(monkeypatch):
    for env_name in (
        "MONGODB_URI",
        "MONGODB_DATABASE",
        "MONGODB_DOMAIN_COLLECTION",
        "MONGODB_TABLE_CATALOG_COLLECTION",
        "MONGODB_MAIN_FLOW_FILTER_COLLECTION",
        "MONGODB_RESULT_COLLECTION",
    ):
        monkeypatch.delenv(env_name, raising=False)
    request_loader = load_module(ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "00_main_flow_filter_authoring_request_loader.py")
    normalizer = load_module(ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "04_main_flow_filter_authoring_result_normalizer.py")
    writer = load_module(ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "07_main_flow_filter_review_writer.py")
    payload = request_loader.build_request("DATE는 기준일 필터야.", "ask", "false")
    payload = normalizer.normalize_authoring(
        payload,
        {
            "items": [
                {
                    "filter_key": "DATE",
                    "payload": {
                        "display_name": "기준일",
                        "aliases": ["날짜", "오늘"],
                        "operator": "eq",
                        "value_type": "date",
                        "value_shape": "scalar",
                    },
                }
            ]
        },
    )

    result = writer.review_and_write(payload)

    assert result["write_result"]["success"] is False
    assert result["write_result"]["errors"][0]["type"] == "missing_mongo_config"


def test_metadata_authoring_api_adapters_emit_structured_api_message():
    adapter_specs = [
        (
            ROOT / "langflow_components" / "domain_authoring_flow" / "09_domain_authoring_api_adapter.py",
            "domain",
        ),
        (
            ROOT / "langflow_components" / "table_catalog_authoring_flow" / "09_table_catalog_authoring_api_adapter.py",
            "table_catalog",
        ),
        (
            ROOT / "langflow_components" / "main_flow_filters_authoring_flow" / "09_main_flow_filter_authoring_api_adapter.py",
            "main_flow_filter",
        ),
    ]
    for path, metadata_type in adapter_specs:
        module = load_module(path)
        wrapped = module.build_api_payload({"message": "저장했습니다.", "success": True})

        assert wrapped["api_response"]["response_type"] == "metadata_authoring"
        assert wrapped["api_response"]["metadata_type"] == metadata_type
        assert wrapped["api_response"]["message"] == "저장했습니다."

        component_classes = [
            value
            for value in vars(module).values()
            if isinstance(value, type) and value.__module__ == module.__name__ and hasattr(value, "outputs")
        ]
        assert len(component_classes) == 1
        output_names = [item.kwargs.get("name") for item in component_classes[0].outputs]
        assert output_names == ["api_payload", "api_message"]


def test_dummy_data_analysis_flow_emits_data_analysis_contract():
    request_loader = load_module(ROOT / "langflow_components" / "dummy_data_analysis_flow" / "00_dummy_request_loader.py")
    response_builder = load_module(ROOT / "langflow_components" / "dummy_data_analysis_flow" / "01_dummy_data_analysis_response_builder.py")

    payload = request_loader.build_dummy_request("router smoke test")
    response = response_builder.build_dummy_response(payload)

    assert response["response_type"] == "data_analysis"
    assert response["status"] == "ok"
    assert response["message"] == response["display_message"]
    assert response["message"].startswith("### 답변")
    assert "### 결과 테이블" in response["message"]
    assert "### 의도 분석" in response["message"]
    assert "### 데이터 조회" in response["message"]
    assert "### pandas 코드/실행" in response["message"]
    assert "```python" in response["message"]
    assert response["answer_message"]
    assert response["intent_plan"]["retrieval_jobs"]
    assert response["intent_plan"]["pandas_execution_plan"]
    assert response["data"]["row_count"] == len(response["data"]["rows"])
    assert response["analysis"]["analysis_code"]
    assert response["trace"]["inspection"]["intent"]["status"] == "ok"
    assert response["trace"]["inspection"]["data_retrieval"]["status"] == "ok"
    assert response["trace"]["inspection"]["pandas_execution"]["generated_code"]
    assert response["trace"]["inspection"]["dummy_flow"]["status"] == "ok"


def test_dummy_metadata_qa_flow_emits_metadata_qa_contract():
    request_loader = load_module(ROOT / "langflow_components" / "dummy_metadata_qa_flow" / "00_dummy_metadata_qa_request_loader.py")
    response_builder = load_module(ROOT / "langflow_components" / "dummy_metadata_qa_flow" / "01_dummy_metadata_qa_response_builder.py")

    payload = request_loader.build_dummy_request("등록된 데이터셋 알려줘", {"session_id": "s1"})
    response = response_builder.build_dummy_response(payload)

    assert response["response_type"] == "metadata_qa"
    assert response["status"] == "ok"
    assert response["direct_response_ready"] is True
    assert response["message"] == response["display_message"]
    assert response["message"].startswith("### 답변")
    assert response["answer_message"]
    assert response["data"]["row_count"] == len(response["data"]["rows"])
    assert response["metadata_qa"]["source_refs"]
    assert response["metadata_route"]["route"] == "dummy_metadata_qa"
    assert response["state"]["session_id"] == "s1"


def test_metadata_qa_flow_reads_v4_metadata_and_emits_api_contract(monkeypatch):
    store = install_fake_pymongo(monkeypatch)
    set_v4_mongo_env(monkeypatch)
    store["datagov"] = {
        "agent_v4_domain_items": {
            "domain:quantity_terms:production_quantity": {
                "_id": "domain:quantity_terms:production_quantity",
                "section": "quantity_terms",
                "key": "production_quantity",
                "status": "active",
                "raw_trace": {"hidden": True},
                "payload": {
                    "display_name": "생산량",
                    "aliases": ["생산량", "생산실적"],
                    "column": "PRODUCTION",
                    "aggregation_method": "sum",
                },
            }
        },
        "agent_v4_table_catalog_items": {
            "table_catalog:production_today": {
                "_id": "table_catalog:production_today",
                "dataset_key": "production_today",
                "status": "active",
                "payload": {
                    "display_name": "Production Today",
                    "dataset_family": "production",
                    "source_type": "oracle",
                    "required_params": ["DATE"],
                    "source_config": {
                        "source_type": "oracle",
                        "db_key": "PNT_RPT",
                        "query_template": "SELECT WORK_DATE, DEVICE, PRODUCTION FROM PROD WHERE WORK_DATE = {DATE}",
                    },
                },
            }
        },
        "agent_v4_main_flow_filters": {
            "main_flow_filter:DATE": {
                "_id": "main_flow_filter:DATE",
                "filter_key": "DATE",
                "status": "active",
                "payload": {"display_name": "기준일", "aliases": ["오늘", "어제"], "operator": "eq"},
            }
        },
    }
    request_loader = load_module(ROOT / "langflow_components" / "metadata_qa_flow" / "00_metadata_qa_request_loader.py")
    domain_loader = load_module(ROOT / "langflow_components" / "metadata_qa_flow" / "01a_mongodb_domain_metadata_loader.py")
    table_loader = load_module(ROOT / "langflow_components" / "metadata_qa_flow" / "01b_mongodb_table_catalog_loader.py")
    filter_loader = load_module(ROOT / "langflow_components" / "metadata_qa_flow" / "01c_mongodb_main_filter_loader.py")
    context_builder = load_module(ROOT / "langflow_components" / "metadata_qa_flow" / "02_metadata_qa_context_builder.py")
    variables_builder = load_module(ROOT / "langflow_components" / "metadata_qa_flow" / "03_metadata_qa_variables_builder.py")
    normalizer = load_module(ROOT / "langflow_components" / "metadata_qa_flow" / "04_metadata_qa_response_normalizer.py")
    message_adapter = load_module(ROOT / "langflow_components" / "metadata_qa_flow" / "05_metadata_qa_message_adapter.py")
    api_builder = load_module(ROOT / "langflow_components" / "metadata_qa_flow" / "06_metadata_qa_api_response_builder.py")

    payload = request_loader.build_request("생산량 데이터 관련 쿼리문은 어떤건지 알려줘")
    domain = domain_loader.load_domain_metadata()
    table = table_loader.load_table_catalog_metadata()
    main_filter = filter_loader.load_main_filter_metadata()
    context_payload = context_builder.build_metadata_qa_context(payload, domain, table, main_filter)
    variables = variables_builder.build_variables(context_payload)
    qa_payload = normalizer.normalize_metadata_qa_response(context_payload, "")
    message = message_adapter.build_message(qa_payload)
    api_response = api_builder.build_api_response(qa_payload, message)

    assert context_payload["metadata_route"]["answer_mode"] == "dataset_sql"
    assert "raw_trace" not in variables["metadata_context_json"]
    assert "production_today" in variables["metadata_context_json"]
    assert qa_payload["response_type"] == "metadata_qa"
    assert qa_payload["direct_response_ready"] is True
    assert qa_payload["metadata_qa"]["sql_blocks"][0]["sql"].startswith("SELECT WORK_DATE")
    assert "```sql" in message
    assert api_response["response_type"] == "metadata_qa"
    assert "metadata_qa_context" not in api_response
    assert "agent_v4_result_store" not in store["datagov"]


def test_metadata_qa_variables_keep_static_policy_inside_prompt_template():
    variables_builder = load_module(ROOT / "langflow_components" / "metadata_qa_flow" / "03_metadata_qa_variables_builder.py")
    prompt_text = (ROOT / "langflow_components" / "metadata_qa_flow" / "03_metadata_qa_prompt_template_ko.md").read_text(encoding="utf-8")

    output_names = [item.kwargs.get("name") for item in variables_builder.MetadataQaVariablesBuilder.outputs]
    variables = variables_builder.build_variables({"request": {"question": "생산량 도메인 알려줘"}, "metadata_qa_context": {}})

    assert output_names == ["question", "metadata_context_json", "output_schema_json"]
    assert "response_policy" not in variables
    assert "{response_policy}" not in prompt_text
    assert "응답 정책:" in prompt_text


def test_dummy_metadata_authoring_flows_preserve_raw_text_and_do_not_save():
    specs = [
        (
            "dummy_domain_authoring_flow",
            "00_dummy_domain_authoring_request_loader.py",
            "01_dummy_domain_authoring_response_builder.py",
            "domain",
        ),
        (
            "dummy_table_catalog_authoring_flow",
            "00_dummy_table_catalog_authoring_request_loader.py",
            "01_dummy_table_catalog_authoring_response_builder.py",
            "table_catalog",
        ),
        (
            "dummy_main_flow_filter_authoring_flow",
            "00_dummy_main_flow_filter_authoring_request_loader.py",
            "01_dummy_main_flow_filter_authoring_response_builder.py",
            "main_flow_filter",
        ),
    ]
    raw_text = "  -- 주석 포함 원문\nWITH sample AS (SELECT 1 AS value)\nSELECT * FROM sample\n"

    for folder, request_file, response_file, metadata_type in specs:
        request_loader = load_module(ROOT / "langflow_components" / folder / request_file)
        response_builder = load_module(ROOT / "langflow_components" / folder / response_file)

        payload = request_loader.build_request(raw_text, duplicate_action="replace", dry_run="false")
        response = response_builder.build_response(payload)

        assert payload["request"]["raw_text"] == raw_text
        assert payload["request"]["duplicate_action"] == "replace"
        assert payload["request"]["dry_run"] is False
        assert response["response_type"] == "metadata_authoring"
        assert response["metadata_type"] == metadata_type
        assert response["write_result"]["saved_count"] == 0
        assert response["write_result"]["success"] is False
        assert response["trace"]["raw_text_preview"].startswith("  -- 주석 포함 원문")


def test_router_flow_final_structure_uses_smart_router_docs_only():
    router_dir = ROOT / "langflow_components" / "router_flow"
    py_files = sorted(router_dir.glob("*.py"))
    connection_guide = (router_dir / "CONNECTION_GUIDE.md").read_text(encoding="utf-8")

    assert py_files == []
    assert not (router_dir / "ROUTE_FLOW_MAP.md").exists()
    assert "Chat Input\n-> Smart Router\n-> route별 Run Flow" in connection_guide
    assert "Smart Router routes table" in connection_guide
    assert "direct_answer" in connection_guide
    assert "clarification" in connection_guide
    assert "Chat Output 하나만 써야 하는 경우" in connection_guide
    assert "selected_flow`는 Run Flow에 변수로 연결하는 값이 아니라" in connection_guide
    assert "`data_analysis` | `data_analysis_flow`" in connection_guide
    assert "`dummy_main_flow_filter_authoring` | `dummy_main_flow_filter_authoring_flow`" in connection_guide
    assert "`flow_error` |" not in connection_guide
    assert "`flow_error`는 Smart Router routes table에 넣는 route가 아니다" in connection_guide


def test_router_connection_guide_lists_only_final_runtime_nodes():
    guide = (ROOT / "langflow_components" / "router_flow" / "CONNECTION_GUIDE.md").read_text(encoding="utf-8")

    assert "router request loader" in guide
    assert "더 이상 사용하지 않는 것" in guide
    assert "Notify(router_response" in guide
    assert "`Route Message`를 비워 원래 입력을 Run Flow로 보내고" in guide
    assert "실제 실행 노드로 연결하지 않는다" not in guide
    assert "Run Flow 대상 flow는 변수 입력이 아니라 각 Run Flow 노드 설정에서 미리 선택한다" in guide
