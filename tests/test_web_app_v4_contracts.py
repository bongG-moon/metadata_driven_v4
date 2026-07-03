from __future__ import annotations

from web_app.data_ref_store import DEFAULT_RESULT_COLLECTION
from web_app.langflow_client import (
    LangflowSettings,
    build_authoring_node_input_settings,
    build_data_analysis_node_input_settings,
    normalize_authoring_response,
    normalize_query_response,
)
from web_app.metadata_store import DEFAULT_COLLECTIONS
from web_app.session_state_store import DEFAULT_SESSION_COLLECTION


def test_web_defaults_use_v4_collections() -> None:
    assert DEFAULT_COLLECTIONS["domain"] == "agent_v4_domain_items"
    assert DEFAULT_COLLECTIONS["table_catalog"] == "agent_v4_table_catalog_items"
    assert DEFAULT_COLLECTIONS["main_flow_filter"] == "agent_v4_main_flow_filters"
    assert DEFAULT_RESULT_COLLECTION == "agent_v4_result_store"
    assert DEFAULT_SESSION_COLLECTION == "agent_v4_session_states"


def test_langflow_settings_chat_ready_with_data_analysis_only() -> None:
    settings = LangflowSettings(data_analysis_api_url="http://127.0.0.1:7860/api/v1/run/analysis")

    configured = settings.configured_summary()

    assert configured["query"] is True
    assert configured["router"] is False
    assert configured["data_analysis"] is True


def test_data_analysis_direct_call_uses_previous_state_input() -> None:
    tweaks = build_data_analysis_node_input_settings({"current_data": {"row_count": 1}}, "web-session")

    assert tweaks == {
        "00 분석 요청 로더": {"previous_state": {"current_data": {"row_count": 1}}},
    }


def test_authoring_api_tweaks_use_v4_korean_node_names(monkeypatch) -> None:
    monkeypatch.setenv("MONGODB_DOMAIN_COLLECTION", "agent_v4_domain_items")

    tweaks = build_authoring_node_input_settings("domain")

    assert tweaks == {
        "00 도메인 등록 요청 로더": {"collection_name": "agent_v4_domain_items"},
        "07 도메인 검수/저장 처리기": {"collection_name": "agent_v4_domain_items"},
    }


def test_normalize_query_response_accepts_v4_data_analysis_payload() -> None:
    result = normalize_query_response(
        {
            "api_response": {
                "response_type": "data_analysis",
                "status": "ok",
                "message": "상위 제품은 DEV-A입니다.",
                "data": {
                    "columns": ["DEVICE", "TOTAL_PRODUCTION"],
                    "rows": [{"DEVICE": "DEV-A", "TOTAL_PRODUCTION": 120}],
                    "row_count": 1,
                },
                "state": {"current_data": {"row_count": 1}},
                "trace": {"warnings": []},
            }
        }
    )

    assert result["message_only"] is False
    assert result["answer_message"] == "상위 제품은 DEV-A입니다."
    assert result["data"]["row_count"] == 1
    assert result["data"]["rows"][0]["DEVICE"] == "DEV-A"
    assert result["response_type"] == "data_analysis"


def test_normalize_query_response_derives_pandas_developer_info_from_trace() -> None:
    result = normalize_query_response(
        {
            "api_response": {
                "response_type": "data_analysis",
                "status": "ok",
                "message": "분석 완료",
                "intent_plan": {
                    "pandas_execution_plan": [
                        {"step": "제품별 생산량 집계", "source_alias": "production_data"},
                    ]
                },
                "analysis": {
                    "status": "ok",
                    "row_count": 1,
                    "columns": ["DEVICE", "TOTAL_PRODUCTION"],
                },
                "data": {
                    "columns": ["DEVICE", "TOTAL_PRODUCTION"],
                    "rows": [{"DEVICE": "DEV-A", "TOTAL_PRODUCTION": 120}],
                    "row_count": 1,
                },
                "trace": {
                    "inspection": {
                        "intent": {"decision_reason": ["생산량 요청으로 판단했습니다."]},
                        "pandas_execution": {
                            "status": "ok",
                            "generated_code": "result = sources['production_data']",
                            "llm_generated_code": "result = sources['production_data']",
                            "pandas_filter_preamble": "production_data = production_data.copy()",
                            "pandas_filter_plan": [{"source_alias": "production_data", "conditions": []}],
                            "execution_result": {"row_count": 1, "columns": ["DEVICE", "TOTAL_PRODUCTION"]},
                        },
                    }
                },
            }
        }
    )

    developer = result["developer"]
    assert developer["analysis_plan"][0]["step"] == "제품별 생산량 집계"
    assert developer["analysis_code"] == "result = sources['production_data']"
    assert developer["data_preparation_code"] == "production_data = production_data.copy()"
    assert developer["filter_notes"][0]["source_alias"] == "production_data"
    assert developer["pandas_execution_status"]["execution_result"]["row_count"] == 1


def test_web_intent_summary_uses_plural_pandas_function_cases() -> None:
    from web_app.app import intent_plan_summary_lines

    lines = intent_plan_summary_lines(
        {
            "analysis_kind": "product_token_analysis",
            "pandas_function_cases": [
                {
                    "key": "product_token_match",
                    "function_name": "match_product_tokens",
                    "input_text": "RG 32G DDR4 FBGA 96 DDP",
                    "source_alias": "production_data",
                }
            ],
        }
    )

    text = "\n".join(lines)

    assert "pandas 함수 케이스 `product_token_match`" in text
    assert "match_product_tokens" in text
    assert "RG 32G DDR4 FBGA 96 DDP" in text


def test_normalize_authoring_response_accepts_v4_trace_preview_items() -> None:
    result = normalize_authoring_response(
        {
            "api_response": {
                "response_type": "metadata_authoring",
                "metadata_type": "domain",
                "success": True,
                "message": "저장되었습니다.",
                "write_result": {"success": True, "saved_count": 1},
                "trace": {
                    "generated_items_preview": [{"section": "process_groups", "key": "WB"}],
                    "existing_matches": [{"section": "process_groups", "key": "W/B"}],
                    "conflict_warnings": [{"message": "유사 항목 확인 필요"}],
                },
            }
        }
    )

    assert result["items"] == [{"section": "process_groups", "key": "WB"}]
    assert result["existing_matches"][0]["key"] == "W/B"
    assert result["conflict_warnings"][0]["message"] == "유사 항목 확인 필요"
