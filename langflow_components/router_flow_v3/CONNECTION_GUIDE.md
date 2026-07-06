# Router Flow v3 연결 가이드 - Smart Router + Langflow API 메시지 호출

`router_flow_v3`는 Smart Router가 선택한 route branch에서 하위 Langflow flow를 Run API로 호출하는 방식입니다.
Run Flow 노드는 호출 시간과 입력 전달 확인이 어려울 수 있으므로, v3는 API 호출 전용 구조로 정리합니다.

핵심 원칙은 단순합니다.

- API 호출 route의 Smart Router `Route Message`는 비웁니다.
- Smart Router route output이 사용자 원문을 그대로 내보내게 합니다.
- 선택된 branch의 메시지를 `01 선택 Flow API 메시지 호출기.flow_input`에 연결합니다.
- `01`은 하위 flow API를 호출할 때 `input_value`와 `session_id`를 함께 보내고, 하위 flow가 반환한 Message만 `Chat Output`으로 보냅니다.

## 1. 기본 구조

route마다 아래 노드 하나만 둡니다.

```text
Chat Input.message
  -> Smart Router.input

Smart Router.<route output>
  -> 01 선택 Flow API 메시지 호출기.flow_input

01 선택 Flow API 메시지 호출기.message
  -> Chat Output.input
```

예를 들어 `data_analysis`, `metadata_qa`, `domain_saving` route를 사용한다면 각 route output 뒤에 `01 선택 Flow API 메시지 호출기`를 하나씩 복사해 둡니다.
각 `01` 노드의 `하위 Flow API URL`만 해당 flow URL로 다르게 입력합니다.

## 2. Smart Router 설정

Smart Router route table은 route 분류만 담당합니다.

| Route Name | Route Description | Route Message |
| --- | --- | --- |
| `data_analysis` | 생산량, 재공, 투입, 장비 ASSIGN 등 실제 제조 데이터 조회/분석 질문 | 비움 |
| `metadata_qa` | 등록된 데이터셋, 필수 파라미터, 쿼리, 도메인 용어, 계산 로직 확인 질문 | 비움 |
| `domain_saving` | 도메인 용어, 공정 그룹, 제품 그룹, 분석 규칙, 특화 함수 설명 저장 요청 | 비움 |
| `table_catalog_saving` | 데이터셋, source type, query template, required params, 컬럼 정보 저장 요청 | 비움 |
| `main_flow_filter_saving` | DATE, OPER_NAME, ORG 같은 공통 필터 정의 저장 요청 | 비움 |
| `dummy_data_analysis` | 개발 검증용 dummy data analysis flow 호출 | 비움 |
| `dummy_metadata_qa` | 개발 검증용 dummy metadata QA flow 호출 | 비움 |
| `dummy_domain_saving` | 개발 검증용 dummy domain saving flow 호출 | 비움 |
| `dummy_table_catalog_saving` | 개발 검증용 dummy table catalog saving flow 호출 | 비움 |
| `dummy_main_flow_filter_saving` | 개발 검증용 dummy main filter saving flow 호출 | 비움 |
| `direct_answer` | 인사, 기능 안내처럼 하위 flow API가 필요 없는 요청 | 사용자에게 보여줄 안내 메시지 |
| `clarification` | 요청이 모호해서 추가 설명이 필요한 경우 | 사용자에게 보여줄 확인 질문 |

중요: API 호출 route에 `{"route":"data_analysis"}` 같은 Route Message를 넣지 않습니다.
Smart Router는 Route Message가 있으면 원문 대신 그 메시지를 output으로 내보낼 수 있습니다.
그러면 하위 flow에는 사용자 질문이 아니라 route JSON이 들어가서 엉뚱한 답변이 나올 수 있습니다.

## 3. 01 노드 입력

`01 선택 Flow API 메시지 호출기`는 아래 입력만 사용합니다.

| 입력 | 연결/입력 방식 |
| --- | --- |
| `Flow 입력` | Smart Router의 해당 route output을 연결합니다. Route Message가 비어 있으면 사용자 원문이 들어옵니다. |
| `하위 Flow API URL` | 해당 하위 flow의 Langflow Run API URL을 입력합니다. 예: `http://127.0.0.1:7860/api/v1/run/<flow_id>` |
| `Langflow API 키` | 필요한 환경에서만 입력합니다. |
| `세션 ID` | advanced 입력입니다. 비워두면 `01`이 실행마다 격리용 session_id를 자동 생성합니다. 웹처럼 같은 대화 세션을 유지해야 하면 외부 session_id를 넣습니다. |
| `제한 시간(초)` | advanced 입력입니다. 기본값은 180초입니다. |

## 4. 하위 Flow API 호출 형식

`01`은 Langflow Run API에 아래 payload만 보냅니다.

```json
{
  "input_value": "사용자 원문",
  "input_type": "chat",
  "output_type": "chat",
  "session_id": "router_v3_..."
}
```

하위 flow가 API용 구조화 응답을 만들어야 한다면 router가 아니라 하위 flow 내부에서 Message를 그렇게 만들도록 수정합니다.
router v3는 응답을 감싸거나 재구성하지 않습니다.

웹 구현과의 가장 큰 차이는 `session_id`입니다.
웹은 Langflow API를 호출할 때 항상 현재 대화의 `session_id`를 전달합니다.
router v3에서 `session_id`를 보내지 않으면 Langflow가 하위 flow ID 기반 기본 세션을 사용할 수 있고, 이 경우 이전 실행 맥락이 섞여 사용자 질문과 다른 답변처럼 보일 수 있습니다.

## 5. Route별 URL 설정

route별 URL 예시는 [ROUTE_API_NODE_SETTINGS_EXAMPLE.md](C:/Users/qkekt/Desktop/meta_driven_v4/langflow_components/router_flow_v3/ROUTE_API_NODE_SETTINGS_EXAMPLE.md:1)를 참고합니다.

## 6. 오류 점검

`01`은 `Flow 입력`이 아래처럼 route JSON만 들어온 경우 API 호출을 막고 안내 메시지를 반환합니다.

```json
{"route":"data_analysis"}
```

이 메시지가 보이면 Smart Router의 API 호출 route에서 Route Message를 비우면 됩니다.

## 7. 검증 기준

- API 호출 route의 Route Message가 비어 있다.
- Smart Router route output이 사용자 질문 원문이다.
- `01`의 실제 API payload에서 `input_value`가 사용자 질문과 동일하고 `session_id`가 함께 전달된다.
- `01.message`를 Chat Output에 연결하면 하위 flow가 반환한 실제 Message가 그대로 보인다.
- router v3에는 route-flow 매핑 상수나 별도 API 응답 envelope가 없다.
