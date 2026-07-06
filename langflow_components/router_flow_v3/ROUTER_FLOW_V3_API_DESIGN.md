# Router Flow v3 API 호출 방식 설계

`router_flow_v3`는 Smart Router로 route를 고른 뒤, 선택된 branch에서 하위 Langflow flow를 Run API로 호출하는 구조입니다.
v3는 Run Flow/Tool Call 방식이 아니라 API 호출 방식으로 고정합니다.

## 1. 설계 목표

1. 사용자가 입력한 원문이 하위 flow의 `input_value`로 그대로 들어간다.
2. route branch마다 필요한 값은 `하위 Flow API URL`과 필요한 경우 `Langflow API 키`뿐이다.
3. router v3는 하위 flow 응답을 구조화 envelope로 감싸지 않고 Message만 반환한다.
4. API 응답 형식이 필요하면 각 하위 flow 안에서 해당 Message 형식을 만들도록 한다.
5. route명/flow명 alias mapping 같은 중복 설정을 router 컴포넌트 안에 두지 않는다.

## 2. 최종 구조

```text
Chat Input.message
  -> Smart Router.input

Smart Router.<route output>
  -> 01 선택 Flow API 메시지 호출기.flow_input

01 선택 Flow API 메시지 호출기.message
  -> Chat Output.input
```

`direct_answer`, `clarification`처럼 하위 flow가 필요 없는 route는 Smart Router Route Message를 바로 Chat Output에 연결합니다.

## 3. Smart Router Route Message 정책

API 호출 route의 Route Message는 비웁니다.
Langflow Smart Router는 Route Message가 있으면 원문 대신 Route Message를 output으로 내보낼 수 있기 때문입니다.

| route 유형 | Route Message |
| --- | --- |
| data analysis / metadata QA / saving / dummy flow 호출 | 비움 |
| direct answer / clarification | 사용자에게 보여줄 문장 |

## 4. API 호출 컴포넌트

`01 선택 Flow API 메시지 호출기`는 하나의 output만 제공합니다.

| 구분 | 값 |
| --- | --- |
| 입력 | `Flow 입력`, `하위 Flow API URL`, `Langflow API 키`, `제한 시간(초)` |
| 출력 | `메시지` |
| API payload | `input_value`, `input_type=chat`, `output_type=chat` |

## 5. 응답 처리

Langflow API 응답은 버전과 flow 구성에 따라 nested 구조가 조금씩 다를 수 있습니다.
컴포넌트는 아래 후보를 재귀적으로 찾아 첫 번째 Message 텍스트를 반환합니다.

- `display_message`
- `answer_message`
- `message`
- `text`
- `content`
- `outputs/results/message/text`
- JSON 문자열 안의 `api_response.message`

하지만 router v3의 최종 output은 항상 Message 하나입니다.

## 6. 검증 기준

- route output에 원문이 들어오면 API payload의 `input_value`가 원문과 같다.
- route output에 `{"route":"..."}`만 들어오면 API 호출을 막고 Route Message를 비우라는 안내를 반환한다.
- 하위 flow가 Chat Output 메시지를 반환하면 `01.message`에 그 텍스트가 나온다.
- 컴포넌트 파일은 하나만 존재한다.
- 테스트와 문서에는 예전 3단계 노드나 별도 구조화 envelope 안내가 남아 있지 않다.
