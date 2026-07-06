# Router Flow v3 연결 가이드 - Route별 API 호출 방식

`router_flow_v3`는 Smart Router가 route별 output port를 따로 제공하는 Langflow 환경에 맞춘 구조다.
이 구조에서는 공통 API 호출기 하나로 모든 route를 모으지 않는다.
각 Smart Router branch마다 아래 세트를 하나씩 배치한다.

```text
Smart Router.<route output>
-> 01 Route API 요청 생성기
-> 02 선택 Flow API 호출기
-> 03 Router API 응답 정리기
-> Chat Output 또는 Data Output
```

즉 `data_analysis`, `metadata_qa`, `domain_saving` route를 사용한다면 `01 -> 02 -> 03` 세트도 각각 하나씩 둔다.

## 1. 전체 구조

```text
Chat Input
  -> Smart Router.input

Chat Input
  -> route별 01 Route API 요청 생성기.original_input

Smart Router.data_analysis
  -> 01 Data Analysis Route API 요청 생성기.route_signal
  -> 02 Data Analysis 선택 Flow API 호출기
  -> 03 Data Analysis Router API 응답 정리기
  -> Chat Output

Smart Router.metadata_qa
  -> 01 Metadata QA Route API 요청 생성기.route_signal
  -> 02 Metadata QA 선택 Flow API 호출기
  -> 03 Metadata QA Router API 응답 정리기
  -> Chat Output
```

route별 `01`에는 해당 하위 flow의 Langflow Run API URL을 직접 넣는다.
예: `http://127.0.0.1:7860/api/v1/run/<metadata_qa_flow_id>`

## 2. Smart Router 설정

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
| `direct_answer` | 인사, 기능 범위 안내처럼 하위 flow 실행이 필요 없는 요청 | 안내 문구 |
| `clarification` | 사용자가 무엇을 원하는지 불명확한 요청 | 확인 질문 문구 |

실제 flow 실행 route의 Route Message는 원문 질문이 아니라 짧은 route JSON만 둔다.
원문은 `Chat Input.message -> 01 Route API 요청 생성기.original_input`으로 별도 연결한다.

## 3. Route별 01 노드 설정

각 route branch마다 `01 Route API 요청 생성기`를 복사해서 아래처럼 설정한다.

| 01 입력 | data_analysis 예시 | metadata_qa 예시 | table_catalog_saving 예시 |
| --- | --- | --- | --- |
| `Route 이름` | `data_analysis` | `metadata_qa` | `table_catalog_saving` |
| `선택 Flow 이름` | `data_analysis_flow` | `metadata_qa_flow` | `table_catalog_saving_flow` |
| `하위 Flow API URL` | `http://127.0.0.1:7860/api/v1/run/<data_analysis_flow_id>` | `http://127.0.0.1:7860/api/v1/run/<metadata_qa_flow_id>` | `http://127.0.0.1:7860/api/v1/run/<table_catalog_saving_flow_id>` |
| `입력 종류` | `question` | `question` | `raw_text` |

전체 route 설정 예시는 [ROUTE_API_NODE_SETTINGS_EXAMPLE.md](C:/Users/qkekt/Desktop/meta_driven_v4/langflow_components/router_flow_v3/ROUTE_API_NODE_SETTINGS_EXAMPLE.md:1)를 참고한다.

## 4. 정확한 연결

각 route마다 아래 연결을 반복한다.

| From output | To input |
| --- | --- |
| `Chat Input.message` | `01 Route API 요청 생성기.original_input` |
| `Smart Router.<route output>` | `01 Route API 요청 생성기.route_signal` |
| `01 Route API 요청 생성기.route_request` | `02 선택 Flow API 호출기.route_request` |
| `02 선택 Flow API 호출기.api_call_result` | `03 Router API 응답 정리기.api_call_result` |
| `03 Router API 응답 정리기.display_message` | route별 `Chat Output.input` |
| `03 Router API 응답 정리기.api_response` | route별 `Data Output.input` 또는 Web/API용 output |

`route_signal`은 선택된 branch만 실행되도록 하는 신호다.
이 값이 비어 있으면 `01`은 `missing_route_signal` 오류를 만들고 `02`는 API를 호출하지 않는다.

## 5. Direct / Clarification

`direct_answer`, `clarification`은 하위 flow API를 호출하지 않는다.
Smart Router의 Route Message를 바로 Chat Output으로 연결한다.

```text
Smart Router.direct_answer
  -> Chat Output

Smart Router.clarification 또는 Else
  -> Chat Output
```

## 6. Web/API 사용 방식

Langflow에서 route별 Chat Output을 여러 개 사용할 수 있으면 각 branch의 `display_message`를 Chat Output으로 연결한다.
구조화 응답이 필요하면 route별 `03 Router API 응답 정리기.api_response`도 Data Output으로 노출한다.

하나의 Chat Output만 허용되는 환경에서는 기존 guide의 Notify/Listen 같은 rendezvous 구성을 사용해 선택 branch의 결과만 모은다.
여러 branch output을 단순 merge 노드 하나에 모두 연결하면 선택되지 않은 branch까지 기다릴 수 있으므로 피한다.

## 7. 지시사항 체크

- router v3는 제품 token 매칭, pandas function case 선택, 공정/제품 조건 해석을 하지 않는다.
- saving raw text는 요약하거나 변형하지 않고 그대로 하위 saving flow로 전달한다.
- route별 API URL은 각 `01 Route API 요청 생성기` 안에 직접 넣는다.
- dummy route는 사용자가 명시적으로 dummy/더미/route_hint를 요청한 경우에만 선택한다.
- `route_signal`이 없거나 API URL이 없으면 HTTP 호출하지 않고 오류 응답을 반환한다.
- Web/API에서는 각 branch의 `api_response`를 우선 사용한다.
