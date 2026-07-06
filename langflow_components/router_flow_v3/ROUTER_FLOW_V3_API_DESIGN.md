# Router Flow v3 API 호출 방식 설계

`router_flow_v3`는 Smart Router가 선택한 route별로 하위 Langflow flow를 API 호출하는 구조입니다.
v1은 Run Flow 노드 기반, v2는 tool call 기반이고, v3는 Langflow Run API URL을 직접 호출하는 방식입니다.

## 1. 목표

1. Smart Router의 route별 output port 구조에 맞춘다.
2. route branch마다 하위 flow의 Run API URL만 입력하면 동작하게 한다.
3. 사용자 원문은 Smart Router route message가 아니라 `Chat Input.message`에서 그대로 하위 flow에 전달한다.
4. router는 제품 token, pandas function case, 공정/제품 조건을 해석하지 않고 하위 flow에 위임한다.
5. 하위 flow의 실제 채팅 답변을 `Chat Output`에서 바로 볼 수 있게 한다.

## 2. 최종 구조

route마다 아래 노드 묶음을 하나씩 둡니다.

```text
Smart Router.<route output>
-> 01 Route API 요청 생성기
-> 02 선택 Flow API 호출기
-> 03 Router API 응답 정리기
-> Chat Output / Data Output
```

`direct_answer`, `clarification`처럼 하위 flow가 필요 없는 route는 이 branch를 만들지 않고 Smart Router 출력 메시지를 바로 Chat Output으로 보냅니다.

## 3. 01 Route API 요청 생성기

`01`은 하위 flow API 호출 요청을 만드는 노드입니다.
화면에서 직접 입력하는 값은 `하위 Flow API URL` 하나만 남깁니다.

| 입력 | 설명 |
| --- | --- |
| `원문 입력` | `Chat Input.message`를 연결합니다. 저장 flow의 raw text도 줄바꿈, `WITH`, `--` 주석을 보존합니다. |
| `선택 Route 신호` | Smart Router의 해당 route output을 연결합니다. route message는 `{"route":"metadata_qa"}` 같은 JSON을 권장합니다. |
| `하위 Flow API URL` | 해당 하위 flow의 Langflow Run API URL입니다. |

내부 자동 처리:

| 항목 | 처리 방식 |
| --- | --- |
| route | Smart Router route message에서 읽음 |
| selected_flow | route mapping으로 자동 추론하고, 매핑이 없으면 URL 마지막 path를 사용 |
| input_kind | `*_saving` route는 `raw_text`, 나머지는 `question`으로 자동 추론 |
| input_type/output_type | `chat`으로 고정 |

## 4. 02 선택 Flow API 호출기

`02`는 `01.route_request`를 받아 실제 Langflow Run API를 호출합니다.
화면에 연결할 최종 메시지는 `02`에서 직접 쓰지 않고 `03`에서 정리합니다.

기본 호출 payload:

```json
{
  "input_value": "사용자 원문",
  "input_type": "chat",
  "output_type": "chat"
}
```

하위 flow 응답 처리:

- 하위 flow가 `api_response` 구조화 응답을 반환하면 그 값을 `selected_flow_response`로 추출합니다.
- 하위 flow가 Chat Output 메시지만 반환하면 Langflow 응답 안의 `outputs/results/message/text`, `artifacts/message`, `display_message` 등을 찾아 `message`로 정리합니다.
- API URL이 없거나 route 신호가 비어 있으면 HTTP 호출을 하지 않고 오류 응답을 반환합니다.

## 5. 03 Router API 응답 정리기

`03`은 router branch의 최종 output을 정리합니다.
출력은 두 개만 사용합니다.

| 출력 | 타입 | 용도 |
| --- | --- | --- |
| `API 응답` | Data | Web/API에서 읽을 구조화 응답입니다. `response_type=routed_flow_execution` envelope를 포함합니다. |
| `채팅 표시 메시지` | Message | Langflow Playground/Chat Output에 보여줄 최종 텍스트입니다. |

`API 메시지`처럼 구조화 응답을 JSON 문자열로 다시 감싸는 출력은 제거했습니다.

예시 envelope:

```json
{
  "response_type": "routed_flow_execution",
  "status": "ok",
  "route": "metadata_qa",
  "selected_flow": "metadata_qa_flow",
  "message": "현재 조회 가능한 데이터셋은 ...",
  "display_message": "현재 조회 가능한 데이터셋은 ...",
  "selected_flow_response": {},
  "route_decision": {},
  "trace": {}
}
```

## 6. 새 route 추가 방법

1. Smart Router route table에 새 route row를 추가한다.
2. Route Message는 `{"route":"new_route"}` 형식으로 넣는다.
3. 새 route output 뒤에 `01 -> 02 -> 03` 노드 묶음을 복사한다.
4. 새 `01`의 `하위 Flow API URL`에 호출할 Langflow Run API URL만 입력한다.
5. `Chat Input.message`를 새 `01.original_input`에 연결한다.
6. `Smart Router.new_route`를 새 `01.route_signal`에 연결한다.
7. `03.display_message`를 Chat Output에 연결하고, 필요하면 `03.api_response`를 Data Output에 연결한다.

## 7. 검증 기준

- route별 `01` 화면에는 수동 입력 필드가 API URL 중심으로 단순하게 보인다.
- 사용자 질문이 Smart Router route message가 아니라 원문 그대로 하위 flow에 전달된다.
- 하위 flow API 호출 성공 후 실제 flow의 답변 텍스트가 `03.display_message`로 나온다.
- Web/API 확인용 구조화 응답은 `03.api_response`에서 확인한다.
- router v3는 분석/저장/QA의 세부 의도 해석을 직접 하지 않는다.
