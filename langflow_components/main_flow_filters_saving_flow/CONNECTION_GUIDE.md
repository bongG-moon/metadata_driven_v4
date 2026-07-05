# Main Flow Filters Saving Flow Connection Guide

이 flow는 DATE, OPER_NAME, MODE, LOT_ID, EQP_MODEL 같은 표준 filter metadata를 자연어로 등록하기 위한 Langflow flow다. 기본 동작은 dry-run이다. 실제 MongoDB 저장은 `dry_run=false`이고 `MONGODB_URI`가 있으면 실행된다. 데이터베이스와 컬렉션은 입력값이 없을 때 `MONGODB_DATABASE=datagov`, `MONGODB_MAIN_FLOW_FILTER_COLLECTION=agent_v4_main_flow_filters`를 기본값으로 사용한다.

## Required Connections

| # | From node.output | To node.input |
| --- | --- | --- |
| 1 | `Text Input.message` 또는 `Chat Input.message` | `00 Main Flow Filter Saving Request Loader.raw_text` |
| 2 | `00 Main Flow Filter Existing Items Loader.existing_items` | `00 Main Flow Filter Saving Request Loader.existing_items` |
| 3 | `00 Main Flow Filter Saving Request Loader.payload_out` | `01 Main Flow Filter Text Refinement Variables Builder.payload` |
| 4 | `01 Main Flow Filter Text Refinement Variables Builder.raw_text` | `Langflow Prompt Template: 01_text_refinement_prompt_template_ko.md.raw_text` |
| 5 | `Langflow Prompt Template: 01_text_refinement_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 6 | `00 Main Flow Filter Saving Request Loader.payload_out` | `02 Main Flow Filter Text Refinement Normalizer.payload` |
| 7 | `Langflow Agent/LLM.output` | `02 Main Flow Filter Text Refinement Normalizer.llm_response` |
| 8 | `02 Main Flow Filter Text Refinement Normalizer.payload_out` | `03 Main Flow Filter Saving Variables Builder.payload` |
| 9 | `03 Main Flow Filter Saving Variables Builder.existing_metadata_summary` | `Langflow Prompt Template: 03_saving_prompt_template_ko.md.existing_metadata_summary` |
| 10 | `03 Main Flow Filter Saving Variables Builder.refined_text` | `Langflow Prompt Template: 03_saving_prompt_template_ko.md.refined_text` |
| 11 | `Langflow Prompt Template: 03_saving_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 12 | `02 Main Flow Filter Text Refinement Normalizer.payload_out` | `04 Main Flow Filter Saving Result Normalizer.payload` |
| 13 | `Langflow Agent/LLM.output` | `04 Main Flow Filter Saving Result Normalizer.llm_response` |
| 14 | `04 Main Flow Filter Saving Result Normalizer.payload_out` | `05 Main Flow Filter Similarity Checker.payload` |
| 15 | `05 Main Flow Filter Similarity Checker.payload_out` | `06 Main Flow Filter Review Variables Builder.payload` |
| 16 | `06 Main Flow Filter Review Variables Builder.review_input_json` | `Langflow Prompt Template: 06_review_prompt_template_ko.md.review_input_json` |
| 17 | `Langflow Prompt Template: 06_review_prompt_template_ko.md.output` | `Langflow Agent/LLM.input` |
| 18 | `05 Main Flow Filter Similarity Checker.payload_out` | `07 Main Flow Filter Review Writer.payload` |
| 19 | `Langflow Agent/LLM.output` | `07 Main Flow Filter Review Writer.review_response` |
| 20 | `07 메인 플로우 필터 검수/저장 처리기.payload_out` | `08 메인 플로우 필터 등록 응답 정규화기.payload` |
| 21 | `08 메인 플로우 필터 등록 응답 정규화기.payload_out` | `09 메인 플로우 필터 등록 메시지 어댑터.payload` |
| 22 | `08 메인 플로우 필터 등록 응답 정규화기.payload_out` | `10 메인 플로우 필터 등록 API 응답 생성기.payload` |
| 23 | `09 메인 플로우 필터 등록 메시지 어댑터.message` | `10 메인 플로우 필터 등록 API 응답 생성기.display_message` |
| 24 | `09 메인 플로우 필터 등록 메시지 어댑터.message` | `Chat Output.message` |

## Optional Connections

| From node.output | To node.input | When to use |
| --- | --- | --- |
| `00 Main Flow Filter Existing Items Loader.existing_items` | `05 Main Flow Filter Similarity Checker.existing_items` | 중복 검사를 명시적으로 연결하고 싶을 때 사용한다. 2번 연결을 했다면 payload에 기존 항목이 포함되므로 필수는 아니다. |
| `10 메인 플로우 필터 등록 API 응답 생성기.api_response` | downstream Data Output | Web/API에서 구조화 응답을 직접 읽을 때 사용한다. |
| `10 메인 플로우 필터 등록 API 응답 생성기.api_message` | downstream Message Output | Run Flow가 Message output을 안정적으로 읽어야 할 때 사용한다. |

## Final Output Usage

- Playground에서는 `09 메인 플로우 필터 등록 메시지 어댑터.message -> Chat Output.message`를 사용한다.
- Web/API에서는 `10 메인 플로우 필터 등록 API 응답 생성기.api_response`를 우선 사용한다.
- JSON 문자열 형태가 더 안정적인 환경에서는 `10 메인 플로우 필터 등록 API 응답 생성기.api_message`를 함께 노출한다.

## Fixed/Manual Inputs

- `00 Main Flow Filter Saving Request Loader.duplicate_action`: 기본은 `ask`. 중복 처리 재실행 때 `merge`, `replace`, `skip`, `create_new` 중 하나로 바꾼다.
- `00 Main Flow Filter Saving Request Loader.dry_run`: 실제 저장 전에는 `true`, 검수 후 저장할 때만 `false`.
- `00 Main Flow Filter Existing Items Loader.mongo_uri`, `mongo_database`, `collection_name`: 비워두면 `.env`의 `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_MAIN_FLOW_FILTER_COLLECTION`을 사용한다.
- `07 Main Flow Filter Review Writer.mongo_uri`, `mongo_database`, `collection_name`: 비워두면 같은 env 기본값을 사용한다.

## Rules

- main flow filter는 표준 filter 의미만 저장한다.
- dataset별 physical column mapping은 table catalog에 둔다.
- `operator`, `value_type`, `value_shape`가 없는 실행 filter는 저장하지 않는다.
- 원문 근거 없는 known value나 alias를 만들지 않는다.
- 프롬프트 본문은 custom component 안에 넣지 않고 Langflow Prompt Template 노드에 둔다.
- LLM 실행은 custom component가 아니라 Langflow 기본 Agent/LLM 노드가 담당한다.
- 실제 저장 시 `registration_trace.raw_text`로 원문을 보존한다.
