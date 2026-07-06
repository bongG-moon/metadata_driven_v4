# Router Flow v3 연결 가이드 - Smart Router + Langflow API

`router_flow_v3`는 Smart Router로 route를 고른 뒤, 선택된 하위 flow를 Langflow HTTP API로 호출하는 구조다.
v1처럼 route별 `Run Flow` 노드를 만들지 않고, v2처럼 Agent tool call도 사용하지 않는다.

## 1. 최종 구조

```text
Chat Input
-> Smart Router
-> 01 Route API 요청 생성기
-> 02 선택 Flow API 호출기
-> 03 Router API 응답 정리기
-> Chat Output / Data Output
```

중요한 점은 `Chat Input.message`를 두 갈래로 연결한다는 것이다.

- 한 갈래는 Smart Router로 보내 route를 고른다.
- 다른 한 갈래는 `01 Route API 요청 생성기.original_input`으로 보내 하위 flow 입력값으로 그대로 사용한다.

따라서 Smart Router의 Route Message가 질문을 바꾸거나 비워도 하위 flow에는 원문이 전달된다.

## 2. 노드 목록

| 순서 | 노드 | 역할 |
| --- | --- | --- |
| 1 | `Chat Input` | 사용자 질문 또는 저장 원문 수신 |
| 2 | `Smart Router` | route 선택 |
| 3 | `01 Route API 요청 생성기` | route와 원문을 합쳐 API 호출 요청 생성 |
| 4 | `02 선택 Flow API 호출기` | 선택된 하위 flow 하나만 `/api/v1/run/{flow_id}`로 호출 |
| 5 | `03 Router API 응답 정리기` | Web/API와 Chat Output용 응답 정리 |
| 6 | `Chat Output` | Playground 표시 |
| 7 | `Data Output` | Web/API 구조화 응답 노출이 필요한 경우 사용 |

## 3. Smart Router 설정

Smart Router route table에는 아래 route를 둔다.

| Route Name | Route Description | Route Message |
| --- | --- | --- |
| `data_analysis` | 생산량, 재공, 투입, 장비 ASSIGN, 제품/공정별 집계처럼 실제 제조 데이터를 조회하고 pandas 분석이 필요한 질문 | `{"route":"data_analysis"}` |
| `metadata_qa` | 등록된 데이터셋, 필수 파라미터, 쿼리, 도메인 용어, 계산 로직을 확인하는 질문 | `{"route":"metadata_qa"}` |
| `domain_saving` | 도메인 용어, 공정 그룹, 제품 그룹, 분석 규칙, 특화 함수 설명을 등록/수정하는 요청 | `{"route":"domain_saving"}` |
| `table_catalog_saving` | 데이터셋, source type, query template, required params, 컬럼 정보를 등록/수정하는 요청 | `{"route":"table_catalog_saving"}` |
| `main_flow_filter_saving` | DATE, OPER_NAME, ORG 같은 공통 필터 정의를 등록/수정하는 요청 | `{"route":"main_flow_filter_saving"}` |
| `dummy_data_analysis` | 명시적으로 dummy data analysis 테스트를 요청한 경우 | `{"route":"dummy_data_analysis"}` |
| `dummy_metadata_qa` | 명시적으로 dummy metadata QA 테스트를 요청한 경우 | `{"route":"dummy_metadata_qa"}` |
| `dummy_domain_saving` | 명시적으로 dummy domain saving 테스트를 요청한 경우 | `{"route":"dummy_domain_saving"}` |
| `dummy_table_catalog_saving` | 명시적으로 dummy table catalog saving 테스트를 요청한 경우 | `{"route":"dummy_table_catalog_saving"}` |
| `dummy_main_flow_filter_saving` | 명시적으로 dummy main filter saving 테스트를 요청한 경우 | `{"route":"dummy_main_flow_filter_saving"}` |
| `direct_answer` | 인사, 기능 범위 안내처럼 하위 flow 실행이 필요 없는 요청 | `{"route":"direct_answer"}` |
| `clarification` | 사용자가 무엇을 원하는지 불명확한 요청 | `{"route":"clarification"}` |

실행 route의 Route Message에는 원문 질문을 넣지 않는다.
원문은 `Chat Input.message -> 01 Route API 요청 생성기.original_input`으로 따로 들어간다.

## 4. 정확한 연결

| From output | To input |
| --- | --- |
| `Chat Input.message` | `Smart Router.input` |
| `Chat Input.message` | `01 Route API 요청 생성기.original_input` |
| `Smart Router.selected output` 또는 route output message | `01 Route API 요청 생성기.smart_router_output` |
| `01 Route API 요청 생성기.route_request` | `02 선택 Flow API 호출기.route_request` |
| `02 선택 Flow API 호출기.api_call_result` | `03 Router API 응답 정리기.api_call_result` |
| `03 Router API 응답 정리기.display_message` | `Chat Output.input` |
| `03 Router API 응답 정리기.api_response` | `Data Output.input` 또는 Web/API에서 읽을 최종 output |

Smart Router 버전에 따라 `selected output` 이름이 다르게 보일 수 있다.
핵심은 Route Message로 나온 `{"route":"..."}` 값을 `01 Route API 요청 생성기.smart_router_output`에 연결하는 것이다.

## 5. 01 Route API 요청 생성기 설정

| 입력 | 값 |
| --- | --- |
| `Route Registry JSON` | `ROUTE_REGISTRY_EXAMPLE.json` 내용을 붙여넣거나 기본값 사용 |
| `Langflow Base URL` | 예: `http://127.0.0.1:7860` |
| `Session ID` | 필요 시 입력. 비워도 됨 |
| `Input Type` | 기본 `chat` |
| `Output Type` | 기본 `chat` |

`Route Registry JSON`에서 각 route의 `flow_id`를 직접 넣거나, Langflow 실행 환경에 `flow_id_env` 값을 설정한다.
예를 들어 `metadata_qa`는 `LANGFLOW_METADATA_QA_FLOW_ID` 또는 `LANGFLOW_METADATA_QA_API_URL`을 사용할 수 있다.

## 6. 02 선택 Flow API 호출기 설정

| 입력 | 값 |
| --- | --- |
| `Langflow API Key` | 필요한 환경이면 입력. 없으면 비움 |
| `Timeout Seconds` | 기본 `180` |

이 노드는 선택된 하위 flow 하나만 호출한다.
`direct_answer`, `clarification` route는 HTTP 호출 없이 바로 응답을 반환한다.

## 7. 03 Router API 응답 정리기 출력

| Output | 사용처 |
| --- | --- |
| `display_message` | Playground/Chat Output 표시 |
| `api_response` | Web/API 구조화 응답 |
| `api_message` | Message output만 안정적인 환경에서 예비 JSON 메시지로 사용 |

`api_response`는 항상 `response_type=routed_flow_execution` 형태를 가진다.
내부에는 `route`, `selected_flow`, `route_decision`, `selected_flow_response`, `message`, `trace`가 포함된다.

## 8. Web/API 사용 방식

Web에서는 router v3 flow 하나만 호출한다.

```text
Web
-> /api/v1/run/<router_flow_v3_id>
-> router_flow_v3 내부에서 selected subflow API 호출
-> router_flow_v3 api_response 반환
```

Web은 하위 flow URL을 직접 호출하지 않는다.
하위 flow의 구조화 응답은 `selected_flow_response`와 `raw_response.api_response`에 들어간다.

## 9. 새 flow 추가 방법

1. 하위 flow가 `message` 또는 `api_response` 계약을 지키는지 확인한다.
2. Smart Router route table에 route row를 추가한다.
3. Route Message에는 `{"route":"new_route"}` 형식만 넣는다.
4. `ROUTE_REGISTRY_EXAMPLE.json` 또는 `01 Route API 요청 생성기.Route Registry JSON`에 route 정보를 추가한다.
5. 새 route의 `selected_flow`, `flow_id` 또는 `flow_id_env`, `api_url_env`, `input_kind`, `response_type`을 입력한다.
6. 대표 질문으로 route와 원문 입력이 보존되는지 확인한다.

## 10. 지시사항 체크

- router v3는 제품 token 매칭, pandas function case 선택, 공정/제품 조건 해석을 하지 않는다.
- saving raw text는 요약하거나 변형하지 않고 그대로 하위 saving flow로 전달한다.
- dummy route는 사용자가 명시적으로 dummy/더미/route_hint를 요청한 경우에만 선택한다.
- 하위 flow API URL이 없거나 입력이 비어 있으면 HTTP 호출하지 않고 오류 응답을 반환한다.
- Web/API에서는 `api_response`를 우선 사용한다.
