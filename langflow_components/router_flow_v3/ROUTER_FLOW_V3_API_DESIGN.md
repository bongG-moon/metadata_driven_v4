# Router Flow v3 API 호출 방식 설계

이 문서는 `router_flow_v3`의 현재 권장 구조를 설명한다.
초기 설계는 Smart Router 결과를 하나의 공통 `01 Route API 요청 생성기`로 모으는 방식이었지만, 실제 Langflow Smart Router는 route별 output port를 따로 제공한다.
따라서 v3는 route branch마다 API 요청/호출/응답 정리 세트를 배치하는 방식으로 정리한다.

## 1. 목표

1. Smart Router의 개별 route output 구조와 자연스럽게 맞춘다.
2. route마다 호출할 Langflow Run API URL을 화면에서 직접 입력한다.
3. 사용자 원문은 Smart Router Route Message가 아니라 `Chat Input.message`에서 그대로 하위 flow에 전달한다.
4. router는 제품 token, pandas function case, 공정/제품 조건을 해석하지 않고 하위 flow에 위임한다.

## 2. 최종 구조

route마다 아래 세트를 하나씩 둔다.

```text
Smart Router.<route output>
-> 01 Route API 요청 생성기
-> 02 선택 Flow API 호출기
-> 03 Router API 응답 정리기
-> Chat Output / Data Output
```

예를 들어 `data_analysis`, `metadata_qa`, `domain_saving`을 사용한다면 `01 -> 02 -> 03` 세트가 3개 생긴다.
각 route별 `01`에는 해당 flow의 API URL을 직접 입력한다.

## 3. 01 Route API 요청 생성기

`01`은 이제 공통 registry를 읽는 노드가 아니다.
각 route branch에 붙는 route 전용 요청 생성기다.

주요 입력:

| 입력 | 의미 |
| --- | --- |
| `원문 입력` | `Chat Input.message`를 연결한다. 질문/저장 원문을 그대로 보존한다. |
| `선택 Route 신호` | Smart Router의 해당 route output을 연결한다. |
| `Route 이름` | 예: `data_analysis`, `metadata_qa`, `table_catalog_saving` |
| `선택 Flow 이름` | 예: `data_analysis_flow` |
| `하위 Flow API URL` | 예: `http://127.0.0.1:7860/api/v1/run/<flow_id>` |
| `입력 종류` | 분석/QA는 `question`, 저장 flow는 `raw_text` |

`선택 Route 신호`가 비어 있으면 선택되지 않은 branch라고 보고 API 호출을 막는다.

## 4. 02 선택 Flow API 호출기

`02`는 같은 branch의 `01.route_request`만 받는다.
요청이 정상이고 API URL이 있으면 Langflow API를 호출한다.

기본 호출 payload:

```json
{
  "input_value": "사용자 원문",
  "input_type": "chat",
  "output_type": "chat",
  "session_id": "선택값"
}
```

`01`에서 오류가 있으면 `02`는 HTTP 호출을 하지 않고 오류 응답을 반환한다.

## 5. 03 Router API 응답 정리기

`03`은 하위 flow 응답을 Web/API와 Chat Output에서 읽을 수 있게 `routed_flow_execution` 형태로 감싼다.

```json
{
  "response_type": "routed_flow_execution",
  "status": "ok",
  "route": "metadata_qa",
  "selected_flow": "metadata_qa_flow",
  "message": "...",
  "selected_flow_response": {},
  "route_decision": {},
  "trace": {}
}
```

## 6. Direct / Clarification

`direct_answer`, `clarification`은 하위 flow API를 호출하지 않는다.
Smart Router Route Message를 바로 Chat Output으로 보낸다.

## 7. 새 route 추가 방법

1. Smart Router route table에 route row를 추가한다.
2. route branch에 `01 -> 02 -> 03` 세트를 추가한다.
3. `01`에 `Route 이름`, `선택 Flow 이름`, `하위 Flow API URL`, `입력 종류`를 입력한다.
4. `Chat Input.message`를 `01.original_input`에 연결한다.
5. Smart Router의 해당 route output을 `01.route_signal`에 연결한다.
6. 대표 질문으로 route, API URL, 원문 보존, 응답 구조를 확인한다.

## 8. 검증 기준

- `data_analysis` 질문은 data analysis flow API로 전달된다.
- `metadata_qa` 질문은 metadata QA flow API로 전달된다.
- saving route의 raw text는 앞 공백, 줄바꿈, `WITH`, `--` 주석을 보존한다.
- 선택되지 않은 branch는 `route_signal`이 없어 API를 호출하지 않는다.
- 하위 flow 응답은 `response_type=routed_flow_execution` envelope로 정리된다.
