# Data Analysis Flow Connection Guide

이 flow는 `의도 분석 -> 데이터 조회 -> pandas 코드 생성/실행 -> 답변/API response` 순서로 연결한다. Prompt 작성과 LLM 호출은 custom component 안에 넣지 않고, Langflow 기본 `Prompt Template`과 `Agent/LLM` 노드를 사용한다.

## 1. 의도 분석

메타데이터 로딩은 의도 분석 LLM보다 먼저 실행한다. LLM은 domain/table catalog/main variable metadata를 보고 dataset, 필수 조회 파라미터, pandas 필터, 분석 계획을 선택해야 한다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 1 | `Chat Input.message` 또는 `Text Input.message` | `00 분석 요청 로더.question` |
| 2 | optional previous state Data | `00 분석 요청 로더.previous_state` |
| 3 | `01A MongoDB 도메인 메타데이터 로더.domain_items` | `01D 메타데이터 후보 생성기.domain_items` |
| 4 | `01B MongoDB 테이블 카탈로그 로더.table_catalog_items` | `01D 메타데이터 후보 생성기.table_catalog_items` |
| 5 | `01C MongoDB 메인 변수 로더.main_flow_filters` | `01D 메타데이터 후보 생성기.main_flow_filters` |
| 6 | `01D 메타데이터 후보 생성기.metadata_candidates` | `02 의도 분석 변수 생성기.metadata_candidates_in` |
| 7 | `00 분석 요청 로더.payload_out` | `02 의도 분석 변수 생성기.payload` |
| 8 | optional `Text Input.message` | `02 의도 분석 변수 생성기.specialized_prompt_text` |
| 9 | `02 의도 분석 변수 생성기.question` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.question` |
| 10 | `02 의도 분석 변수 생성기.state_summary` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.state_summary` |
| 11 | `02 의도 분석 변수 생성기.metadata_candidates` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.metadata_candidates` |
| 12 | `02 의도 분석 변수 생성기.specialized_prompt` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.specialized_prompt` |
| 13 | `02 의도 분석 변수 생성기.output_schema` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.output_schema` |
| 14 | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 15 | `00 분석 요청 로더.payload_out` | `04 의도 계획 정규화기.payload` |
| 16 | `Langflow Agent/LLM.output` | `04 의도 계획 정규화기.llm_response` |

`specialized_prompt_text`는 공정/현장 특화 지시가 있을 때만 연결한다. 없으면 비워 둔다.

특화 프롬프트와 특화 함수에 어떤 값을 넣어야 하는지는 `SPECIALIZED_INPUT_GUIDE.md`를 기준으로 확인한다.

- 공정 특화 프롬프트: `02 의도 분석 변수 생성기.specialized_prompt_text`에 자연어 지시를 입력한다.
- 복사용 특화 프롬프트 예시: `specialized_prompt_input_example_ko.md`
- 특화 함수: 사용자가 pandas 노드에 직접 입력하지 않는다. 의도 분석 LLM이 `intent_plan.pandas_function_case`와 `pandas_execution_plan[].operation=apply_pandas_function_case`를 출력하면, `15 pandas 변수 생성기.function_case_context_json`을 통해 pandas Prompt Template으로 전달된다.
- Domain Authoring Flow용 function case raw text 예시: `../domain_authoring_flow/pandas_function_cases_raw_text_input_example.md`
- 현재 지원 helper는 `match_product_tokens(input_text, frame, token_columns=None, output_order=None)`와 형식 확인용 `sample_passthrough_helper(input_text, frame, note=None)`이다.

## 2. 이전 결과 복원

이전 turn의 `data_ref`로 전체 rows를 복원해야 할 때만 사용한다. 일반 단일 질문 분석에서는 건너뛰어도 된다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 17A | `04 의도 계획 정규화기.payload_out` | `05 MongoDB 이전 결과 로더.payload` |
| 17B | `05 MongoDB 이전 결과 로더.payload_out` | `06 조회 작업 검증기.payload` |

복원하지 않을 때:

| From node.output | To node.input |
| --- | --- |
| `04 의도 계획 정규화기.payload_out` | `06 조회 작업 검증기.payload` |

## 3. 데이터 조회

기본 검증은 `07 조회 작업 라우터.retrieval_mode=dummy`로 둔다. 실제 Oracle/H-API/Datalake/Goodocs 조회가 필요할 때만 `live`로 바꾼다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 18 | `06 조회 작업 검증기.payload_out` | `07 조회 작업 라우터.payload` |
| 19 | `06 조회 작업 검증기.payload_out` | `13 소스 조회 결과 병합기.main_payload` |
| 20 | `07 조회 작업 라우터.dummy_jobs` | `08 더미 데이터 조회기.payload` |
| 21 | `08 더미 데이터 조회기.retrieval_payload` | `13 소스 조회 결과 병합기.dummy_retrieval` |
| 22 | `13 소스 조회 결과 병합기.payload_out` | `14 조회 페이로드 어댑터.payload` |

Live branch를 사용할 때 추가 연결:

| From node.output | To node.input |
| --- | --- |
| `07 조회 작업 라우터.oracle_jobs` | `09 Oracle 조회기.payload` |
| `09 Oracle 조회기.retrieval_payload` | `13 소스 조회 결과 병합기.oracle_retrieval` |
| `07 조회 작업 라우터.h_api_jobs` | `10 H-API 조회기.payload` |
| `10 H-API 조회기.retrieval_payload` | `13 소스 조회 결과 병합기.h_api_retrieval` |
| `07 조회 작업 라우터.datalake_jobs` | `11 Datalake 조회기.payload` |
| `11 Datalake 조회기.retrieval_payload` | `13 소스 조회 결과 병합기.datalake_retrieval` |
| `07 조회 작업 라우터.goodocs_jobs` | `12 Goodocs 조회기.payload` |
| `12 Goodocs 조회기.retrieval_payload` | `13 소스 조회 결과 병합기.goodocs_retrieval` |

## 4. pandas 코드 생성과 1차 실행

`retrieval_jobs[].required_params`는 조회 단계에서만 적용되고, `retrieval_jobs[].filters`는 `17 pandas 코드 실행기`가 pandas 전처리 코드로 먼저 적용한다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 23 | `14 조회 페이로드 어댑터.payload_out` | `15 pandas 변수 생성기.payload` |
| 24 | `15 pandas 변수 생성기.intent_plan_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.intent_plan_json` |
| 25 | `15 pandas 변수 생성기.source_schema_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.source_schema_json` |
| 26 | `15 pandas 변수 생성기.source_preview_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.source_preview_json` |
| 27 | `15 pandas 변수 생성기.function_case_context_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.function_case_context_json` |
| 28 | `15 pandas 변수 생성기.output_contract_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.output_contract_json` |
| 29 | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 30 | `14 조회 페이로드 어댑터.payload_out` | `17 pandas 코드 실행기.payload` |
| 31 | `Langflow Agent/LLM.output` | `17 pandas 코드 실행기.llm_response` |

재생성 경로를 쓰지 않으면 `17 pandas 코드 실행기.payload_out`을 바로 `23 MongoDB 결과 저장기.payload` 또는 `18 답변 변수 생성기.payload`로 연결한다.

## 5. pandas 코드 재생성 선택 경로

pandas 실행 실패 시 오류 정보와 실패한 코드를 LLM에 넘겨 한 번 더 코드를 생성할 수 있다. Langflow 화면에서는 `17 pandas 코드 실행기`를 하나 더 복제해서 `17R pandas 코드 재실행기`처럼 이름을 바꿔 사용하면 된다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 32 | `17 pandas 코드 실행기.payload_out` | `17A pandas 재생성 변수 생성기.payload` |
| 33 | `17A pandas 재생성 변수 생성기.repair_required` | `Langflow Prompt Template: 17b_pandas_repair_prompt_template_ko.md.repair_required` |
| 34 | `17A pandas 재생성 변수 생성기.intent_plan_json` | `Langflow Prompt Template: 17b_pandas_repair_prompt_template_ko.md.intent_plan_json` |
| 35 | `17A pandas 재생성 변수 생성기.source_schema_json` | `Langflow Prompt Template: 17b_pandas_repair_prompt_template_ko.md.source_schema_json` |
| 36 | `17A pandas 재생성 변수 생성기.source_preview_json` | `Langflow Prompt Template: 17b_pandas_repair_prompt_template_ko.md.source_preview_json` |
| 37 | `17A pandas 재생성 변수 생성기.failed_code` | `Langflow Prompt Template: 17b_pandas_repair_prompt_template_ko.md.failed_code` |
| 38 | `17A pandas 재생성 변수 생성기.error_context_json` | `Langflow Prompt Template: 17b_pandas_repair_prompt_template_ko.md.error_context_json` |
| 39 | `17A pandas 재생성 변수 생성기.function_case_context_json` | `Langflow Prompt Template: 17b_pandas_repair_prompt_template_ko.md.function_case_context_json` |
| 40 | `17A pandas 재생성 변수 생성기.output_schema` | `Langflow Prompt Template: 17b_pandas_repair_prompt_template_ko.md.output_schema` |
| 41 | `Langflow Prompt Template: 17b_pandas_repair_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 42 | `17 pandas 코드 실행기.payload_out` | `17R pandas 코드 재실행기.payload` |
| 43 | `Langflow Agent/LLM.output` | `17R pandas 코드 재실행기.llm_response` |
| 44 | `17 pandas 코드 실행기.payload_out` | `17C pandas 재생성 결과 선택기.original_payload` |
| 45 | `17R pandas 코드 재실행기.payload_out` | `17C pandas 재생성 결과 선택기.retry_payload` |
| 46 | `17C pandas 재생성 결과 선택기.payload_out` | `23 MongoDB 결과 저장기.payload` |

재생성 LLM이 `{"code": ""}`를 반환하면 재실행 결과는 실패로 남고, `17C`는 원래 payload를 선택한다.

## 6. 답변 생성

결과 저장을 사용할 때는 `23 MongoDB 결과 저장기.payload_out`을 기준으로 답변을 만든다. 재생성 경로를 쓰지 않고 저장도 하지 않을 때는 `17 pandas 코드 실행기.payload_out`을 `18`, `20`에 직접 연결한다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 47 | `23 MongoDB 결과 저장기.payload_out` | `18 답변 변수 생성기.payload` |
| 48 | `18 답변 변수 생성기.question` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.question` |
| 49 | `18 답변 변수 생성기.result_summary_json` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.result_summary_json` |
| 50 | `18 답변 변수 생성기.applied_scope_json` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.applied_scope_json` |
| 51 | `18 답변 변수 생성기.warnings_errors_json` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.warnings_errors_json` |
| 52 | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 53 | `23 MongoDB 결과 저장기.payload_out` | `20 답변 응답 생성기.payload` |
| 54 | `Langflow Agent/LLM.output` | `20 답변 응답 생성기.answer_text` |
| 55 | `20 답변 응답 생성기.payload_out` | `21 답변 메시지 어댑터.payload` |
| 56 | `21 답변 메시지 어댑터.message` | `Chat Output.message` |

API 응답이 필요하면 다음을 추가한다.

| From node.output | To node.input |
| --- | --- |
| `20 답변 응답 생성기.payload_out` | `22 API 응답 생성기.payload` |
| `22 API 응답 생성기.api_response` | downstream API/Data output |

## 7. 수동 입력과 환경값

- `00 분석 요청 로더`는 `reference_date`, `timezone`, `session_id` 입력 포트를 만들지 않는다. 기준일은 실행 시점 한국 기준 `YYYYMMDD`로 `request.reference_date`에 자동 저장한다.
- `02 의도 분석 변수 생성기`는 `reference_date`, `timezone`을 별도 출력하지 않는다. Prompt에는 `state_summary.request_context.reference_date`만 전달한다.
- `05 MongoDB 이전 결과 로더`는 `data_ref` 입력 포트를 만들지 않는다. `payload.data.data_ref`, `payload.state.current_data.data_ref`, `payload.state.data_ref` 순서로 자동 탐색한다.
- `07 조회 작업 라우터.retrieval_mode` 기본값은 `dummy`다. 실제 DB/API 조회만 `live`로 바꾼다.
- `09 Oracle 조회기.oracle_config`가 비어 있으면 `.env`의 `ORACLE_CONFIG_JSON`을 사용한다. 값은 `{"PNT_RPT": {"user": "...", "password": "...", "dsn": "(DESCRIPTION=...)"}}` 형태 또는 TNS block 형태를 지원한다.
- MongoDB 기본값은 `.env`의 `MONGODB_DATABASE=datagov`, `MONGODB_DOMAIN_COLLECTION=agent_v4_domain_items`, `MONGODB_TABLE_CATALOG_COLLECTION=agent_v4_table_catalog_items`, `MONGODB_MAIN_FLOW_FILTER_COLLECTION=agent_v4_main_flow_filters`, `MONGODB_RESULT_COLLECTION=agent_v4_result_store`를 사용한다.
- `01A~01C status_filter` 기본값은 `active`다. 전체 문서를 읽어야 할 때만 `all`로 바꾼다.

## 8. 구현 규칙

- Prompt와 LLM 호출은 Langflow 기본 `Prompt Template`, `Agent/LLM` 노드에 둔다.
- custom component는 프롬프트 본문을 내장하지 않고 변수 생성, 정규화, 조회, 실행, 저장만 담당한다.
- `required_params`만 조회 단계에 적용한다. 공정/제품/상태/장비/LOT 같은 분석 조건은 `filters`로 보존했다가 pandas 전처리에서 적용한다.
- 제품 token 매칭이 필요한 복잡한 케이스는 `pandas_function_case.function_name=match_product_tokens`로 표현하고, pandas code는 `match_product_tokens(...)` helper를 사용한다. 세부 입력 예시는 `SPECIALIZED_INPUT_GUIDE.md`를 따른다.
- pandas code는 `result` 또는 `result_df`를 반드시 설정해야 한다.
- pandas code는 import/open/eval/exec/file/network 접근을 사용하면 안 된다.
- `runtime_sources`는 최종 API response에서 제거한다.
