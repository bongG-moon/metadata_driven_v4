from __future__ import annotations

import ast
import importlib.util
import sys
import types
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT_FILES = sorted((ROOT / "langflow_components").glob("*/*.py"))


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
    validator = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "07_retrieval_job_validator.py")
    router = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "08_retrieval_job_router.py")
    dummy = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "09_dummy_data_retriever.py")
    merger = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "14_source_retrieval_merger.py")
    adapter = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "15_retrieval_payload_adapter.py")
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
    final_safe = adapter.strip_runtime_sources(adapted)

    assert adapted["runtime_sources"]["wip_data"][0]["OPER_NAME"] == "D/A1"
    assert adapted["source_results"][0]["source_execution"]["used_dummy_data"] is True
    assert "runtime_sources" not in final_safe


def test_langflow_dummy_data_covers_data_catalog_shapes():
    dummy = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "09_dummy_data_retriever.py")
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


def test_langflow_dummy_data_applies_required_params_and_alias_filters():
    dummy = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "09_dummy_data_retriever.py")
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
    assert {row["PKG1"] for row in production["rows"]} == {"LFBGA"}
    assert {row["LOT_ID"] for row in hold["rows"]} == {"T1234567GEN1"}


def test_data_analysis_langflow_dummy_path_reaches_api_response():
    request_loader = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "00_analysis_request_loader.py")
    intent_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "02_intent_variables_builder.py")
    intent_normalizer = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "03_intent_plan_normalizer.py")
    validator = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "07_retrieval_job_validator.py")
    router = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "08_retrieval_job_router.py")
    dummy = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "09_dummy_data_retriever.py")
    merger = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "14_source_retrieval_merger.py")
    adapter = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "15_retrieval_payload_adapter.py")
    pandas_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "16_pandas_variables_builder.py")
    pandas_executor = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "18_pandas_code_executor.py")
    answer_variables = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "19_answer_variables_builder.py")
    answer_builder = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "21_answer_response_builder.py")
    api_builder = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "23_api_response_builder.py")

    payload = request_loader.build_request("오늘 D/A1 공정 WIP 합계 알려줘", reference_date="20260701")
    intent_prompt_vars = intent_variables.build_variables(payload, {"datasets": ["wip_today"]})
    assert "wip_today" in intent_prompt_vars["metadata_candidates"]
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
    assert payload["data"]["rows"] == [{"OPER_NAME": "D/A1", "wip_sum": 120}]

    answer_prompt_vars = answer_variables.build_variables(payload)
    assert "wip_sum" in answer_prompt_vars["result_summary_json"]
    payload = answer_builder.build_answer_response(payload, "D/A1 공정의 WIP 합계는 120입니다.")
    response = api_builder.build_api_response(payload)

    assert response["status"] == "ok"
    assert response["message"] == "D/A1 공정의 WIP 합계는 120입니다."
    assert response["data"]["row_count"] == 1
    assert "runtime_sources" not in response


def test_data_analysis_mongodb_metadata_loader_uses_v4_env_defaults(monkeypatch):
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
    loader = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "04_mongodb_metadata_loader.py")

    result = loader.load_metadata_candidates(limit="50")

    assert result["metadata_load"]["status"] == "ok"
    assert result["metadata_load"]["database"] == "datagov"
    assert result["metadata_load"]["collections"]["domain_items"] == "agent_v4_domain_items"
    assert result["metadata_load"]["status_filter"] == "active"
    assert result["metadata_load"]["counts"] == {"domain_items": 1, "table_catalog_items": 1, "main_flow_filters": 1}
    assert result["metadata_candidates"]["table_catalog_items"][0]["dataset_key"] == "wip_today"
    assert "_id" not in result["metadata_candidates"]["domain_items"][0]


def test_data_analysis_mongodb_result_store_and_loader_round_trip(monkeypatch):
    install_fake_pymongo(monkeypatch)
    set_v4_mongo_env(monkeypatch)
    result_store = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "24_mongodb_result_store.py")
    result_loader = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "05_mongodb_result_loader.py")
    payload = {
        "request": {"session_id": "s1", "question": "재공 합계"},
        "metadata_refs": [{"type": "table_catalog", "key": "wip_today"}],
        "intent_plan": {"analysis_kind": "wip_sum"},
        "source_results": [{"source_alias": "wip_data", "row_count": 1}],
        "runtime_sources": {"wip_data": [{"OPER_NAME": "D/A1", "WIP": 120}]},
        "analysis": {"status": "ok", "row_count": 1},
        "data": {"rows": [{"OPER_NAME": "D/A1", "wip_sum": 120}], "row_count": 1},
        "trace": {"warnings": [], "errors": [], "inspection": {}},
    }

    stored = result_store.store_result(payload)
    data_ref = stored["data"]["data_ref"]
    restored = result_loader.load_previous_result(
        {
            "request": {"session_id": "s1", "question": "이전 결과 다시 보여줘"},
            "state": {"current_data": {"data_ref": data_ref}},
            "trace": {"warnings": [], "errors": [], "inspection": {}},
        }
    )

    assert data_ref.startswith("result:s1:")
    assert stored["trace"]["inspection"]["result_store"]["collection_name"] == "agent_v4_result_store"
    assert restored["trace"]["inspection"]["result_loader"]["status"] == "ok"
    assert restored["runtime_sources"]["wip_data"][0]["WIP"] == 120
    assert restored["data"]["data_ref"] == data_ref


def test_restored_runtime_sources_survive_empty_retrieval_merge():
    merger = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "14_source_retrieval_merger.py")
    adapter = load_module(ROOT / "langflow_components" / "data_analysis_flow" / "15_retrieval_payload_adapter.py")
    payload = {
        "source_results": [{"source_alias": "wip_data", "row_count": 1}],
        "runtime_sources": {"wip_data": [{"OPER_NAME": "D/A1", "WIP": 120}]},
        "trace": {"warnings": [], "errors": [], "inspection": {"result_loader": {"status": "ok"}}},
    }

    merged = merger.merge_source_retrieval_payloads(payload, {"source_type": "oracle", "status": "skipped", "skipped": True, "skip_reason": "no oracle retrieval jobs"})
    adapted = adapter.build_retrieval_payload(merged)

    assert adapted["runtime_sources"]["wip_data"][0]["WIP"] == 120
    assert adapted["trace"]["inspection"]["data_retrieval"]["preserved_existing_runtime_sources"] is True


def test_langflow_prompt_templates_are_external_files_for_agent_nodes():
    prompt_files = [
        ROOT / "langflow_components" / "data_analysis_flow" / "01_intent_prompt_template_ko.md",
        ROOT / "langflow_components" / "data_analysis_flow" / "17_pandas_prompt_template_ko.md",
        ROOT / "langflow_components" / "data_analysis_flow" / "20_answer_prompt_template_ko.md",
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
        "output_schema",
        "intent_plan_json",
        "source_schema_json",
        "source_preview_json",
        "output_contract_json",
        "result_summary_json",
        "applied_scope_json",
        "warnings_errors_json",
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
