# Router Flow v3 API 호출 방식 설계

이 문서는 `router_flow_v3`를 Smart Router + Langflow API 호출 방식으로 구현하기 위한 설계안이다.
기존 `router_flow` v1은 Smart Router 뒤에 route별 `Run Flow` 노드를 직접 연결했고, `router_flow_v2`는 Agent tool call 방식으로 하위 flow를 호출했다.
v3는 Smart Router는 분류만 담당하고, 선택된 하위 flow 실행은 커스텀 컴포넌트가 Langflow HTTP API(`/api/v1/run/{flow_id}`)로 호출하는 구조를 사용한다.

참고한 이전 구현:

- `C:/Users/qkekt/Desktop/metadata_driven_v3/langflow_components/router_flow/06_selected_flow_api_runner.py`
- `C:/Users/qkekt/Desktop/metadata_driven_v3/langflow_components/router_flow2/01_smart_router_route_response_builder.py`
- `C:/Users/qkekt/Desktop/metadata_driven_v3/docs/LANGFLOW_NODE_CONNECTION_GUIDE.md`

## 1. 목표

v3의 목표는 아래 세 가지다.

1. Smart Router의 route 판단 결과와 실제 사용자 입력을 분리한다.
2. Run Flow/Tool Mode refresh나 agent-controlled input 문제 없이 원문 질문을 하위 flow에 그대로 보낸다.
3. Web/API에서는 router flow 하나만 호출해도 선택된 하위 flow 결과까지 포함된 구조화 응답을 받게 한다.

특히 최근 확인한 문제처럼 `Smart Router`, `Run Flow`, `Tool Mode`를 거치면서 사용자 질문이 비거나 변형되는 경우를 줄이는 것이 핵심이다.

## 2. 권장 전체 구조

```text
Chat Input
-> Smart Router
-> 01 Route API Request Builder
-> 02 Selected Flow API Caller
-> 03 Router API Response Adapter
-> Chat Output / Data Output
```

역할 분리는 아래처럼 둔다.

| 노드 | 역할 |
| --- | --- |
| `Chat Input` | 사용자가 입력한 질문 또는 저장용 원문을 그대로 받는다. |
| `Smart Router` | `data_analysis`, `metadata_qa`, `domain_saving` 같은 route만 결정한다. |
| `01 Route API Request Builder` | Smart Router 결과와 원문 입력을 합쳐 하위 flow API 호출 요청을 만든다. |
| `02 Selected Flow API Caller` | `subflow_call.api_url` 또는 `base_url + flow_id`로 Langflow API를 호출한다. |
| `03 Router API Response Adapter` | 하위 flow 응답에서 `message`, `api_response`, `route_decision`, `trace`를 정규화한다. |

v1과 달리 route별 `Run Flow` 노드를 만들지 않는다.
v2와 달리 Agent가 tool을 고르는 구조도 사용하지 않는다.

## 3. 핵심 원칙

### 3.1 Smart Router output을 사용자 질문으로 쓰지 않는다

Smart Router의 `Route Message`는 route 선택용 신호로만 사용한다.
하위 flow에 보낼 입력값은 반드시 `Chat Input.message` 원문에서 가져온다.

이렇게 해야 아래 문제가 줄어든다.

- Smart Router가 route message를 응답 문장처럼 바꿔서 하위 flow에 넘기는 문제
- Tool Mode에서 agent가 tool input을 빈 문자열로 넘기는 문제
- metadata saving raw text의 줄바꿈, `WITH`, `--` 주석이 손상되는 문제

### 3.2 router는 해석하지 않는다

router v3는 아래 작업을 하지 않는다.

- 제품 token 매칭
- pandas function case 선택
- 공정/제품/상태 조건 분해
- table catalog `required_params` 해석
- metadata raw text 요약 또는 변형

이 작업들은 기존처럼 각 하위 flow가 담당한다.

### 3.3 하위 flow 실행 계약은 하나로 통일한다

Langflow API 호출 payload는 기본적으로 아래 형태를 사용한다.

```json
{
  "input_value": "사용자 원문",
  "input_type": "chat",
  "output_type": "chat",
  "session_id": "선택값"
}
```

Langflow 버전에 따라 `session_id` 처리 방식이 다를 수 있으므로, v3 컴포넌트에서는 `session_id`를 request payload에 포함하되 없어도 실행되도록 한다.
하위 flow의 첫 입력이 `Chat Input`이든 `Text Input`이든, Langflow API 호출에서는 `input_value`가 원문 역할을 하도록 맞춘다.

## 4. Route Registry

v3에서는 route와 target flow 매핑을 코드에만 숨기지 않고, 컴포넌트 입력값 또는 문서화된 JSON으로 관리한다.
새 flow를 추가할 때는 registry row만 추가하면 되게 만든다.

예시:

```json
{
  "routes": {
    "data_analysis": {
      "selected_flow": "data_analysis_flow",
      "flow_id_env": "LANGFLOW_DATA_ANALYSIS_FLOW_ID",
      "api_url_env": "LANGFLOW_DATA_ANALYSIS_API_URL",
      "input_kind": "question",
      "response_type": "data_analysis"
    },
    "metadata_qa": {
      "selected_flow": "metadata_qa_flow",
      "flow_id_env": "LANGFLOW_METADATA_QA_FLOW_ID",
      "api_url_env": "LANGFLOW_METADATA_QA_API_URL",
      "input_kind": "question",
      "response_type": "metadata_qa"
    },
    "domain_saving": {
      "selected_flow": "domain_saving_flow",
      "flow_id_env": "LANGFLOW_DOMAIN_SAVING_FLOW_ID",
      "api_url_env": "LANGFLOW_DOMAIN_SAVING_API_URL",
      "input_kind": "raw_text",
      "response_type": "metadata_authoring"
    },
    "table_catalog_saving": {
      "selected_flow": "table_catalog_saving_flow",
      "flow_id_env": "LANGFLOW_TABLE_CATALOG_SAVING_FLOW_ID",
      "api_url_env": "LANGFLOW_TABLE_CATALOG_SAVING_API_URL",
      "input_kind": "raw_text",
      "response_type": "metadata_authoring"
    },
    "main_flow_filter_saving": {
      "selected_flow": "main_flow_filters_saving_flow",
      "flow_id_env": "LANGFLOW_MAIN_FLOW_FILTER_SAVING_FLOW_ID",
      "api_url_env": "LANGFLOW_MAIN_FLOW_FILTER_SAVING_API_URL",
      "input_kind": "raw_text",
      "response_type": "metadata_authoring"
    }
  }
}
```

dummy flow도 같은 형식으로 추가한다.
dummy route는 사용자가 `dummy`, `더미`, `route_hint=dummy_*`를 명시한 경우에만 선택되도록 Smart Router 설명에 제한한다.

## 5. 컴포넌트 설계

### 5.1 `01 Route API Request Builder`

표시 이름:

```text
01 Route API 요청 생성기
```

입력:

| Input | Type | 설명 |
| --- | --- | --- |
| `original_input` | Message | Chat Input에서 받은 사용자 원문. |
| `smart_router_output` | Message/Data | Smart Router가 선택한 route 결과. |
| `route_registry_json` | MessageTextInput | route와 flow ID/API URL 매핑. |
| `base_url` | MessageTextInput | Langflow base URL. 예: `http://127.0.0.1:7860` |
| `session_id` | MessageTextInput | 선택 입력. 없으면 빈 값으로 둔다. |

출력:

| Output | Type | 설명 |
| --- | --- | --- |
| `route_request` | Data | `selected_flow`, `route`, `subflow_call`, `original_input`을 포함한 실행 요청. |

생성하는 Data 예시:

```json
{
  "status": "ready",
  "response_type": "route_api_request",
  "route": "metadata_qa",
  "selected_flow": "metadata_qa_flow",
  "request": {
    "original_input": "현재 조회 가능한 dataset list와 필수 para정보를 알려줘",
    "session_id": "demo-session"
  },
  "subflow_call": {
    "api_url": "http://127.0.0.1:7860/api/v1/run/<metadata_qa_flow_id>",
    "flow_id": "<metadata_qa_flow_id>",
    "input_value": "현재 조회 가능한 dataset list와 필수 para정보를 알려줘",
    "input_type": "chat",
    "output_type": "chat"
  },
  "route_decision": {
    "route": "metadata_qa",
    "route_source": "smart_router",
    "raw_smart_router_output": "metadata_qa"
  }
}
```

주의:

- `original_input`을 trim만 하고 문장 수정은 하지 않는다.
- saving route는 `input_kind=raw_text`로 표시만 남기고, 원문 값은 그대로 `input_value`에 넣는다.
- route가 direct/clarification이면 API 호출 요청을 만들지 않고 `status=direct_response`로 둔다.

### 5.2 `02 Selected Flow API Caller`

표시 이름:

```text
02 선택 Flow API 호출기
```

입력:

| Input | Type | 설명 |
| --- | --- | --- |
| `route_request` | Data | 01에서 만든 실행 요청. |
| `api_key` | MessageTextInput | 선택 입력. 값이 있으면 `x-api-key` header로 보낸다. |
| `timeout_seconds` | MessageTextInput | 기본 180초. |

출력:

| Output | Type | 설명 |
| --- | --- | --- |
| `api_call_result` | Data | HTTP 호출 결과, raw response, 추출 메시지, 오류 정보. |
| `message` | Message | Playground에서 바로 볼 수 있는 표시 메시지. |

처리:

1. `route_request.status`가 `direct_response` 또는 `clarification`이면 HTTP 호출 없이 메시지를 반환한다.
2. `subflow_call.api_url`이 없으면 `status=error`로 반환한다.
3. `input_value`가 비어 있으면 하위 flow를 호출하지 않고 오류를 반환한다.
4. API 응답에서 `api_response`, `display_message`, `message`, Langflow nested output 순서로 값을 찾는다.
5. `raw_response`는 디버깅용으로 보관하되, 최종 Web 응답에는 필요한 요약만 노출한다.

### 5.3 `03 Router API Response Adapter`

표시 이름:

```text
03 Router API 응답 정리기
```

입력:

| Input | Type | 설명 |
| --- | --- | --- |
| `api_call_result` | Data | 02 호출 결과. |

출력:

| Output | Type | 설명 |
| --- | --- | --- |
| `api_response` | Data | Web/API에서 읽을 구조화 응답. |
| `api_message` | Message | JSON 문자열 형태의 예비 응답. |
| `display_message` | Message | Playground Chat Output용 메시지. |

정규화 결과 예시:

```json
{
  "response_type": "routed_flow_execution",
  "status": "ok",
  "route": "metadata_qa",
  "selected_flow": "metadata_qa_flow",
  "message": "현재 조회 가능한 데이터셋은 ...",
  "display_message": "현재 조회 가능한 데이터셋은 ...",
  "selected_flow_response": {
    "response_type": "metadata_qa",
    "answer_sections": {}
  },
  "route_decision": {
    "route": "metadata_qa",
    "route_source": "smart_router"
  },
  "trace": {
    "api_url": "http://127.0.0.1:7860/api/v1/run/<flow_id>",
    "input_length": 39,
    "http_status": 200
  }
}
```

## 6. Smart Router 설정

Smart Router routes table에는 아래 route를 둔다.

| Route Name | Route Description | Route Message |
| --- | --- | --- |
| `data_analysis` | 생산량, 재공, 투입, 장비 ASSIGN, 제품/공정별 집계처럼 실제 제조 데이터를 조회하고 pandas 분석이 필요한 질문 | `data_analysis` |
| `metadata_qa` | 등록된 데이터셋, 필수 파라미터, 쿼리, 도메인 용어, 계산 로직을 확인하는 질문 | `metadata_qa` |
| `domain_saving` | 도메인 용어, 공정 그룹, 제품 그룹, 분석 규칙, 특화 함수 설명을 등록/수정하는 요청 | `domain_saving` |
| `table_catalog_saving` | 데이터셋, source type, query template, required params, 컬럼 정보를 등록/수정하는 요청 | `table_catalog_saving` |
| `main_flow_filter_saving` | DATE, OPER_NAME, ORG 같은 공통 필터 정의를 등록/수정하는 요청 | `main_flow_filter_saving` |
| `dummy_data_analysis` | 명시적으로 dummy data analysis 테스트를 요청한 경우 | `dummy_data_analysis` |
| `dummy_metadata_qa` | 명시적으로 dummy metadata QA 테스트를 요청한 경우 | `dummy_metadata_qa` |
| `dummy_domain_saving` | 명시적으로 dummy domain saving 테스트를 요청한 경우 | `dummy_domain_saving` |
| `dummy_table_catalog_saving` | 명시적으로 dummy table catalog saving 테스트를 요청한 경우 | `dummy_table_catalog_saving` |
| `dummy_main_flow_filter_saving` | 명시적으로 dummy main filter saving 테스트를 요청한 경우 | `dummy_main_flow_filter_saving` |
| `direct_answer` | 인사, 기능 범위 안내처럼 하위 flow 실행이 필요 없는 요청 | 안내 문구 |
| `clarification` | 사용자가 무엇을 원하는지 불명확한 요청 | 확인 질문 문구 |

v1에서는 실행 route의 Route Message를 비워 원문을 Run Flow로 보내는 방식을 썼다.
v3에서는 원문은 별도 `Chat Input -> 01 Route API 요청 생성기.original_input`으로 연결하므로, 실행 route의 Route Message에는 짧은 route token을 넣어도 된다.
이 token은 하위 flow input으로 쓰지 않는다.

## 7. Connection Guide

### 7.1 기본 연결

```text
Chat Input.message
  -> Smart Router.input

Chat Input.message
  -> 01 Route API 요청 생성기.original_input

Smart Router output
  -> 01 Route API 요청 생성기.smart_router_output

01 Route API 요청 생성기.route_request
  -> 02 선택 Flow API 호출기.route_request

02 선택 Flow API 호출기.api_call_result
  -> 03 Router API 응답 정리기.api_call_result

03 Router API 응답 정리기.display_message
  -> Chat Output.input

03 Router API 응답 정리기.api_response
  -> Data Output 또는 Web/API용 output
```

### 7.2 설정값

`01 Route API 요청 생성기`에는 아래 값을 넣는다.

| 입력 | 예시 |
| --- | --- |
| `base_url` | `http://127.0.0.1:7860` |
| `route_registry_json` | 위 Route Registry JSON |
| `session_id` | 비워둬도 됨. Web에서 필요하면 tweak으로 주입 가능 |

`02 선택 Flow API 호출기`에는 아래 값을 넣는다.

| 입력 | 예시 |
| --- | --- |
| `api_key` | Langflow API key. 없으면 빈 값 |
| `timeout_seconds` | `180` |

## 8. Web/API 관점

Web은 지금처럼 router flow API 하나만 호출한다.

```text
Web
-> /api/v1/run/<router_flow_v3_id>
-> router_flow_v3 내부에서 selected subflow API 호출
-> router_flow_v3의 api_response 반환
```

장점:

- Web이 하위 flow URL을 모두 알 필요가 없다.
- router가 어떤 subflow를 호출했는지 `route_decision`으로 확인 가능하다.
- data analysis, metadata QA, saving flow의 기존 `api_response` 계약을 최대한 보존한다.

## 9. 오류 처리

| 상황 | 처리 |
| --- | --- |
| route를 못 고름 | `clarification` 메시지 반환 |
| API URL 없음 | `status=error`, `flow_id_env`, `api_url_env` 안내 |
| input_value 비어 있음 | HTTP 호출하지 않고 `empty_input` 오류 반환 |
| HTTP timeout | `status=error`, `timeout_seconds`, target flow 표시 |
| 하위 flow 응답 파싱 실패 | raw response 일부와 함께 `message` fallback 반환 |
| 하위 flow가 error 응답 반환 | router가 재해석하지 않고 error status를 보존 |

## 10. 검증 계획

단위 검증:

1. Smart Router output이 `metadata_qa`일 때 원문 질문이 그대로 `subflow_call.input_value`에 들어가는지 확인한다.
2. `L-114제품 생산량 알려줘` 같은 질문이 router에서 변형되지 않고 data analysis API로 전달되는지 확인한다.
3. saving raw text에 `WITH`, `--`, 줄바꿈이 있어도 `input_value`가 손상되지 않는지 확인한다.
4. API caller가 nested Langflow response에서 `api_response.message`, `display_message`, `message`, nested `outputs.results.message.data.text`를 순서대로 추출하는지 확인한다.
5. dummy route가 명시적 dummy 요청에서만 선택되는지 확인한다.

통합 검증 질문:

| 질문 | 기대 route |
| --- | --- |
| `오늘 DA공정 생산량 알려줘` | `data_analysis` |
| `L-114제품 생산량 알려줘` | `data_analysis` |
| `현재 조회 가능한 dataset list와 필수 para정보를 알려줘` | `metadata_qa` |
| `DA 공정 그룹을 D/A1~D/A6로 등록해줘` | `domain_saving` |
| `production_today 데이터셋 등록해줘 ...` | `table_catalog_saving` |
| `route_hint=dummy_metadata_qa 현재 조회 가능한 데이터 알려줘` | `dummy_metadata_qa` |
| `안녕` | `direct_answer` |
| `이거 확인해줘` | `clarification` |

## 11. 구현 순서

1. `router_flow_v3` 폴더 생성
2. `01_route_api_request_builder.py` 구현
3. `02_selected_flow_api_caller.py` 구현
4. `03_router_api_response_adapter.py` 구현
5. `ROUTE_REGISTRY_EXAMPLE.json` 작성
6. `CONNECTION_GUIDE.md` 작성
7. mock API 기반 단위 테스트 추가
8. 대표 질문으로 route/input 보존 검증

## 12. 최종 판단

이번 v3 구조는 v1/v2에서 나온 입력 전달 문제를 가장 직접적으로 줄일 수 있다.
Smart Router는 route token만 만들고, 원문은 별도 선으로 API caller에 직접 들어가기 때문에 하위 flow가 단독 실행될 때와 router를 통해 실행될 때의 입력 차이가 줄어든다.

다만 Langflow 서버가 자기 자신 또는 다른 Langflow 서버의 `/api/v1/run`을 호출해야 하므로, 실제 환경에서는 아래 값을 반드시 먼저 확정해야 한다.

- router v3가 호출할 Langflow base URL
- 각 하위 flow의 flow id 또는 full API URL
- API key 사용 여부
- timeout 기준
- router flow가 자기 자신을 호출하지 않도록 하는 route registry 관리
