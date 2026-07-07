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
| 6 | `00 분석 요청 로더.payload_out` | `01E 후속 질문 힌트 생성기.payload` |
| 7 | `01D 메타데이터 후보 생성기.metadata_candidates` | `02 의도 분석 변수 생성기.metadata_candidates_in` |
| 8 | `01E 후속 질문 힌트 생성기.payload_out` | `02 의도 분석 변수 생성기.payload` |
| 9 | `02 의도 분석 변수 생성기.question` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.question` |
| 10 | `02 의도 분석 변수 생성기.state_summary` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.state_summary` |
| 11 | `02 의도 분석 변수 생성기.metadata_candidates` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.metadata_candidates` |
| 12 | optional `Text Input.message` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.specialized_prompt` |
| 13 | `02 의도 분석 변수 생성기.output_schema` | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.output_schema` |
| 14 | `Langflow Prompt Template: 03_intent_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 15 | `01E 후속 질문 힌트 생성기.payload_out` | `04 의도 계획 정규화기.payload` |
| 16 | `Langflow Agent/LLM.output` | `04 의도 계획 정규화기.llm_response` |

`03_intent_prompt_template_ko.md.specialized_prompt`는 공정/현장 특화 지시가 있을 때만 별도 `Text Input.message`에서 직접 연결한다. 없으면 비워 둔다.

`01E 후속 질문 힌트 생성기`는 LLM이 아니며 최종 분류를 확정하지 않는다. 이전 state가 있을 때 현재 질문이 이전 답변/이전 의도에 의존할 가능성, 날짜 변경, 조건 변경, 결과 재가공, 원본 확장, 설명 요청 힌트만 payload에 추가한다. 실제 조건 상속/변경/삭제 판단은 `03 의도 분석 Prompt Template`과 Langflow Agent/LLM이 metadata와 data catalog 기준으로 수행한다.

Langflow Playground에서 멀티턴을 자동으로 테스트하려면 `langflow_components/session_state_flow`의 공통 세션 상태 노드를 함께 둔다.

| From node.output | To node.input |
| --- | --- |
| `Chat Input.message` | `00 MongoDB 세션 상태 로더.question` |
| `00 MongoDB 세션 상태 로더.loaded_state` | `00 분석 요청 로더.previous_state` |

Web/API에서 이미 `previous_state`를 넘기는 경우에는 이 로더를 생략해도 된다.

특화 프롬프트와 특화 함수에 어떤 값을 넣어야 하는지는 `SPECIALIZED_INPUT_GUIDE.md`를 기준으로 확인한다.

- 공정 특화 프롬프트: `Text Input.message`를 `03 의도 분석 Prompt Template.specialized_prompt`에 직접 연결한다.
- 복사용 특화 프롬프트 예시: `specialized_prompt_input_example_ko.md`
- Function Case 선택 정보: `15 pandas 변수 생성기.function_case_selection_json`을 `16 pandas Prompt Template.function_case_selection_json`에 연결한다.
- 특화 함수 코드: 사용자가 pandas 실행 노드에 직접 입력하지 않는다. 실제 함수 정의 코드는 `function_case_helper_code_input_example.py` 내용을 `16 pandas Prompt Template.function_case_helper_code`에 붙여넣어 전달한다.
- `16 pandas Prompt Template.function_case_helper_code` 수동 테스트용 복사 파일: `function_case_helper_code_input_example.py`
- Domain Saving Flow용 function case 등록 지시: repo root의 `domain_knowledge.txt` 맨 아래 `pandas function case 등록 규칙` 블록
- `domain_knowledge.txt`의 등록 지시는 MongoDB에 저장할 helper 선택 metadata만 다룬다. 실제 helper 코드는 `function_case_helper_code_input_example.py`에 있고, 16번 prompt가 생성 pandas 코드에 포함해야 한다.
- 현재 지원 helper는 `match_product_tokens(input_text, frame, token_columns=None, output_order=None)`와 형식 확인용 `sample_passthrough_helper(input_text, frame, note=None)`이다.

## 2. 이전 결과 복원

이전 turn의 `data_ref`로 전체 rows를 복원해야 할 때만 사용한다. 일반 단일 질문 분석에서는 건너뛰어도 된다. 후속 질문에서 `intent_plan.reuse_strategy`가 `previous_result`, `previous_source`, `trace_only` 중 하나이거나 이전 원본 rows가 필요하면 이 경로를 사용한다. `data_ref`가 없으면 05번은 경고 없이 skip한다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 16A | `04 의도 계획 정규화기.payload_out` | `05 MongoDB 이전 결과 로더.payload` |
| 16B | `05 MongoDB 이전 결과 로더.payload_out` | `06 조회 작업 검증기.payload` |

복원하지 않을 때:

| From node.output | To node.input |
| --- | --- |
| `04 의도 계획 정규화기.payload_out` | `06 조회 작업 검증기.payload` |

## 3. 데이터 조회

기본 검증은 `07 조회 작업 라우터.retrieval_mode=dummy`로 둔다. 실제 Oracle/H-API/Datalake/Goodocs 조회가 필요할 때만 `live`로 바꾼다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 17 | `06 조회 작업 검증기.payload_out` | `07 조회 작업 라우터.payload` |
| 18 | `06 조회 작업 검증기.payload_out` | `13 소스 조회 결과 병합기.main_payload` |
| 19 | `07 조회 작업 라우터.dummy_jobs` | `08 더미 데이터 조회기.payload` |
| 20 | `08 더미 데이터 조회기.retrieval_payload` | `13 소스 조회 결과 병합기.dummy_retrieval` |
| 21 | `13 소스 조회 결과 병합기.payload_out` | `14 조회 페이로드 어댑터.payload` |

Live branch를 사용할 때 추가 연결:

| From node.output | To node.input |
| --- | --- |
| `07 조회 작업 라우터.oracle_jobs` | `09 Oracle 조회기.payload` |
| `09 Oracle 조회기.retrieval_payload` | `13 소스 조회 결과 병합기.oracle_retrieval` |
| `07 조회 작업 라우터.h_api_jobs` | `10 H-API 조회기.payload` |
| `10 H-API 조회기.retrieval_payload` | `13 소스 조회 결과 병합기.h_api_retrieval` |
| `07 조회 작업 라우터.datalake_jobs` | `11 데이터레이크 조회기.payload` |
| `11 데이터레이크 조회기.retrieval_payload` | `13 소스 조회 결과 병합기.datalake_retrieval` |
| `07 조회 작업 라우터.goodocs_jobs` | `12 Goodocs 조회기.payload` |
| `12 Goodocs 조회기.retrieval_payload` | `13 소스 조회 결과 병합기.goodocs_retrieval` |

## 4. pandas 코드 생성과 1차 실행

`retrieval_jobs[].required_params`는 조회 단계에서만 적용되고, `retrieval_jobs[].filters`는 `17 pandas 코드 실행기`가 pandas 전처리 코드로 먼저 적용한다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 22 | `14 조회 페이로드 어댑터.payload_out` | `15 pandas 변수 생성기.payload` |
| 23 | `15 pandas 변수 생성기.intent_plan_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.intent_plan_json` |
| 24 | `15 pandas 변수 생성기.source_schema_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.source_schema_json` |
| 25 | `15 pandas 변수 생성기.source_preview_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.source_preview_json` |
| 26 | `15 pandas 변수 생성기.function_case_selection_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.function_case_selection_json` |
| 27 | `Text Input.message`에 `function_case_helper_code_input_example.py` 내용 붙여넣기 | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.function_case_helper_code` |
| 28 | `15 pandas 변수 생성기.output_contract_json` | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.output_contract_json` |
| 29 | `Langflow Prompt Template: 16_pandas_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 30 | `14 조회 페이로드 어댑터.payload_out` | `17 pandas 코드 실행기.payload` |
| 31 | `Langflow Agent/LLM.output` | `17 pandas 코드 실행기.llm_response` |

재생성 경로를 쓰지 않으면 `17 pandas 코드 실행기.payload_out`을 바로 `23 MongoDB 결과 저장기.payload` 또는 `18 답변 변수 생성기.payload`로 연결한다.

`15 pandas 변수 생성기.function_case_selection_json` 출력은 실제 함수 코드가 아니라 의도 분석 결과에 들어 있는 function case 선택 정보다. 이 출력은 16번 Prompt Template의 `function_case_selection_json` 입력에 연결한다. 특화 함수 코드는 별도로 16번 Prompt Template의 `function_case_helper_code` 입력값에 `function_case_helper_code_input_example.py` 내용으로 넣는다.

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
| 39 | `17A pandas 재생성 변수 생성기.function_case_selection_json` | `Langflow Prompt Template: 17b_pandas_repair_prompt_template_ko.md.function_case_selection_json` |
| 40 | `Text Input.message`에 `function_case_helper_code_input_example.py` 내용 붙여넣기 | `Langflow Prompt Template: 17b_pandas_repair_prompt_template_ko.md.function_case_helper_code` |
| 41 | `17A pandas 재생성 변수 생성기.output_schema` | `Langflow Prompt Template: 17b_pandas_repair_prompt_template_ko.md.output_schema` |
| 42 | `Langflow Prompt Template: 17b_pandas_repair_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 43 | `17 pandas 코드 실행기.payload_out` | `17R pandas 코드 재실행기.payload` |
| 44 | `Langflow Agent/LLM.output` | `17R pandas 코드 재실행기.llm_response` |
| 45 | `17 pandas 코드 실행기.payload_out` | `17C pandas 재생성 결과 선택기.original_payload` |
| 46 | `17R pandas 코드 재실행기.payload_out` | `17C pandas 재생성 결과 선택기.retry_payload` |
| 47 | `17C pandas 재생성 결과 선택기.payload_out` | `23 MongoDB 결과 저장기.payload` |

재생성 LLM이 `{"code": ""}`를 반환하면 재실행 결과는 실패로 남고, `17C`는 원래 payload를 선택한다.

## 6. 답변 생성

결과 저장을 사용할 때는 `23 MongoDB 결과 저장기.payload_out`을 기준으로 답변을 만든다. 재생성 경로를 쓰지 않고 저장도 하지 않을 때는 `17 pandas 코드 실행기.payload_out`을 `18`, `20`에 직접 연결한다.

| # | From node.output | To node.input |
| --- | --- | --- |
| 48 | `23 MongoDB 결과 저장기.payload_out` | `18 답변 변수 생성기.payload` |
| 49 | `18 답변 변수 생성기.question` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.question` |
| 50 | `18 답변 변수 생성기.result_summary_json` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.result_summary_json` |
| 51 | `18 답변 변수 생성기.applied_scope_json` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.applied_scope_json` |
| 52 | `18 답변 변수 생성기.answer_context_json` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.answer_context_json` |
| 53 | `Text Input: 답변 특화 지침.text` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.domain_answer_guidance` |
| 54 | `18 답변 변수 생성기.warnings_errors_json` | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.warnings_errors_json` |
| 55 | `Langflow Prompt Template: 19_answer_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 56 | `23 MongoDB 결과 저장기.payload_out` | `20 답변 응답 생성기.payload` |
| 57 | `Langflow Agent/LLM.output` | `20 답변 응답 생성기.answer_text` |
| 58 | `20 답변 응답 생성기.payload_out` | `21 답변 메시지 어댑터.payload` |
| 59 | `21 답변 메시지 어댑터.message` | `Chat Output.message` |

`21 답변 메시지 어댑터.download_base_url`에는 다운로드 링크를 만들 때 사용할 Base URL만 입력한다. 기본값은 `http://localhost:8765`이다.
`21 답변 메시지 어댑터.include_diagnostics`는 기본값 OFF를 권장한다. Langflow Playground에서 의도 분석, 데이터 조회, pandas 코드까지 한 번에 검증해야 할 때만 토글을 켠다.
`21 답변 메시지 어댑터`는 메시지 길이를 줄이기 위해 섹션별 ON/OFF 토글을 제공한다. `show_result_table`, `show_analysis_evidence`(화면 표시명: 중간 산출물/helper 결과 표시), `show_download_links`, `show_notices`, `show_applied_criteria`, `show_next_questions`는 기본값 ON이고, `show_intent_analysis`, `show_data_retrieval`, `show_pandas_code`는 기본값 OFF이다.
`answer_message` 안에 `### 결과 테이블`, `### 중간 분석 산출물`, `### helper 실행 결과`, `### 분석 근거`, `### 데이터 다운로드`, `### 적용 기준`, `### 다음에 볼 만한 질문`, `### 의도 분석`, `### 데이터 조회`, `### pandas 코드/실행` 같은 섹션이 이미 들어와도 21번 토글이 OFF인 섹션은 최종 메시지에서 제거된다.
Playground에서 답변만 간단히 보고 싶으면 다운로드 링크, 중간 산출물/helper 결과, pandas 코드 토글을 끄면 된다. Web/API 구조화 표시는 `22 API 응답 생성기.data`와 `data_refs`를 기준으로 동작하므로, 21번 메시지 섹션을 꺼도 웹의 전체 표와 CSV 다운로드 계약은 유지된다.
`Text Input: 답변 특화 지침`에는 `answer_domain_guidance_input_example_ko.md`의 내용을 복사해 넣을 수 있다. 공통 답변 Prompt Template에는 특정 제품 token/helper 규칙을 직접 넣지 않는다.
`19 답변 Prompt Template`은 LLM이 `answer_message`를 포함한 JSON 객체를 반환하도록 요청한다. 특화 지침에서 컬럼 표시명/순서를 지정해야 할 때만 `answer_sections.result_table.column_labels`, `answer_sections.result_table.display_columns`를 함께 반환하게 한다.

`20 답변 응답 생성기`는 기존 `answer_message`와 함께 현업 화면/API에서 재사용할 `answer_sections`를 payload에 추가한다. `answer_sections`에는 요약, 결과 테이블, 적용 기준, 중간 산출물/helper 결과, 다운로드 참조, 참고/다음 질문이 들어간다. `21 답변 메시지 어댑터`와 `22 API 응답 생성기`는 이 구조를 우선 사용하되, 기존 payload만 들어와도 fallback으로 동작한다.

세션 상태를 MongoDB에 저장하려면 `20 답변 응답 생성기.payload_out`과 `21/22` 사이에 `01 MongoDB 세션 상태 저장기`를 끼운다.

| From node.output | To node.input |
| --- | --- |
| `20 답변 응답 생성기.payload_out` | `01 MongoDB 세션 상태 저장기.response_payload` |
| `01 MongoDB 세션 상태 저장기.payload_out` | `21 답변 메시지 어댑터.payload` |
| `01 MongoDB 세션 상태 저장기.payload_out` | `22 API 응답 생성기.payload` |

저장기는 원본 전체 rows를 session state에 저장하지 않고, `current_data`, `last_intent_plan`, `last_applied_criteria`, `followup_source_results`, `runtime_source_refs` 같은 compact state와 `data_ref`만 저장한다.

컬럼 표시명이나 화면 표시 순서가 필요하면 공통 컴포넌트에 하드코딩하지 않고 `payload.data.column_labels`, `payload.data.display_columns` 또는 `answer_sections.result_table.column_labels`, `answer_sections.result_table.display_columns`로 명시적으로 전달한다. 전달값이 없으면 `21 답변 메시지 어댑터`는 원본 컬럼명과 원본 순서를 그대로 사용한다.

API 응답이 필요하면 다음을 추가한다.

| From node.output | To node.input |
| --- | --- |
| `20 답변 응답 생성기.payload_out` | `22 API 응답 생성기.payload` |
| `21 답변 메시지 어댑터.message` | `22 API 응답 생성기.display_message` |
| `22 API 응답 생성기.api_response` | downstream API/Data output |

## 7. Langflow Chat 데이터 다운로드 링크

`23 MongoDB 결과 저장기`를 사용하면 `payload.data_refs`에 분석 결과와 사용 원본 source별 MongoDB 참조가 남는다. `21 답변 메시지 어댑터`는 이 참조를 읽어 Langflow Chat Markdown에 다운로드 화면 링크를 추가한다.

- 기본 링크 base URL은 `http://localhost:8765`이다.
- 운영/테스트 다운로드 화면 주소는 `21 답변 메시지 어댑터.download_base_url` 입력값으로 설정한다. 이 값은 링크 생성용 주소일 뿐, 데이터 저장/만료 정책을 바꾸지 않는다.
- `23 MongoDB 결과 저장소.ttl_hours`에는 result store 데이터 보관 시간을 시간 단위로 입력한다. 이 값은 MongoDB에 저장되는 `expires_at`을 결정하므로, 데이터를 쓰는 23번 노드에서 설정한다. 기본값은 `24`이고, 참고 HTML 리포트 서버와 동일하게 최대 `168`시간으로 보정된다.
- `23 MongoDB 결과 저장소`는 저장 문서에 `expires_at`을 남기고 `expires_at` 기준 MongoDB TTL 인덱스를 생성한다. MongoDB TTL monitor가 실제 만료 문서를 자동 삭제한다.
- 로컬 다운로드 서버는 `python tools/data_ref_download_server.py`로 실행한다.
- 링크는 CSV 파일을 직접 노출하지 않고 `download_ref` 토큰만 전달한다.
- 데이터는 다운로드 서버에 저장되지 않는다. 실제 저장은 `23 MongoDB 결과 저장소`가 MongoDB result store에 수행하고, 로컬 다운로드 서버는 자신의 `.env`의 `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_RESULT_COLLECTION`로 MongoDB를 읽어 CSV를 만들어 준다.
- TTL monitor가 아직 삭제하지 않은 문서라도 `expires_at`이 지난 경우 로컬 다운로드 서버는 해당 `data_ref`를 다운로드 대상으로 제공하지 않는다.
- 결과 CSV와 원본 CSV를 모두 제공하려면 `17/17C -> 23 -> 18/20 -> 21` 순서로 연결해야 한다.

## 8. 수동 입력과 환경값

- `00 분석 요청 로더`는 `reference_date`, `timezone`, `session_id` 입력 포트를 만들지 않는다. 기준일은 실행 시점 한국 기준 `YYYYMMDD`로 `request.reference_date`에 자동 저장한다.
- `02 의도 분석 변수 생성기`는 `reference_date`, `timezone`, `specialized_prompt`를 별도 출력하지 않는다. 기준일은 `state_summary.request_context.reference_date`로 전달하고, 특화 프롬프트는 별도 Text Input에서 03 Prompt Template으로 직접 연결한다.
- `05 MongoDB 이전 결과 로더`는 `data_ref` 입력 포트를 만들지 않는다. `payload.data.data_ref`, `payload.state.current_data.data_ref`, `payload.state.data_ref` 순서로 자동 탐색한다.
- `07 조회 작업 라우터.retrieval_mode` 기본값은 `dummy`다. 실제 DB/API 조회만 `live`로 바꾼다.
- 더미 데이터는 실행일 기준 한국 날짜의 오늘/어제/그제 rows와 기존 고정 검증일 rows를 함께 제공한다. 따라서 `00 분석 요청 로더`가 자동 생성한 오늘 날짜도 더미 조회에서 0건으로 떨어지지 않아야 한다.
- `09 Oracle 조회기.oracle_config`가 비어 있으면 `.env`의 `ORACLE_CONFIG_JSON`을 사용한다. 값은 `{"PNT_RPT": {"user": "...", "password": "...", "dsn": "(DESCRIPTION=...)"}}` 형태 또는 TNS block 형태를 지원한다.
- MongoDB 기본값은 `.env`의 `MONGODB_DATABASE=datagov`, `MONGODB_DOMAIN_COLLECTION=agent_v4_domain_items`, `MONGODB_TABLE_CATALOG_COLLECTION=agent_v4_table_catalog_items`, `MONGODB_MAIN_FLOW_FILTER_COLLECTION=agent_v4_main_flow_filters`, `MONGODB_RESULT_COLLECTION=agent_v4_result_store`를 사용한다.
- `01A~01C status_filter` 기본값은 `active`다. 전체 문서를 읽어야 할 때만 `all`로 바꾼다.

## 9. 구현 규칙

- Prompt와 LLM 호출은 Langflow 기본 `Prompt Template`, `Agent/LLM` 노드에 둔다.
- custom component는 프롬프트 본문을 내장하지 않고 변수 생성, 정규화, 조회, 실행, 저장만 담당한다.
- `required_params`만 조회 단계에 적용한다. 공정/제품/상태/장비/LOT 같은 분석 조건은 `filters`로 보존했다가 pandas 전처리에서 적용한다.
- 제품 token 매칭이 필요한 복잡한 케이스는 `pandas_function_cases[].function_name=match_product_tokens`로 표현하고, pandas code는 `match_product_tokens(...)` helper를 사용한다. 세부 입력 예시는 `SPECIALIZED_INPUT_GUIDE.md`와 `function_case_helper_code_input_example.py`를 따른다.
- pandas code는 `result` 또는 `result_df`를 반드시 설정해야 한다.
- pandas code는 import/open/eval/exec/file/network 접근을 사용하면 안 된다.
- `runtime_sources`는 최종 API response에서 제거한다.
