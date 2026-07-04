# Langflow Node Connection Guide Index

현재 권장 구조는 main router가 질문 유형을 분류하고, Smart Router route output이 route별로 미리 선택된 `Run Flow` 노드 하나로 입력을 보내는 방식입니다. router 내부에서 하위 flow를 API로 다시 호출하지 않습니다.
`Run Flow`는 flow 이름을 변수로 받아 실행 대상을 고르는 노드가 아니며, 각 Run Flow 노드에서 대상 flow를 먼저 선택해야 동적 입력 포트가 열립니다.

먼저 읽을 문서:

| Guide | When to read |
| --- | --- |
| `langflow_components/router_flow/CONNECTION_GUIDE.md` | main router canvas를 만들 때 |
| `docs/ROUTED_RUN_FLOW_SESSION_WIRING_GUIDE.md` | subflow session load/write 규칙을 확인할 때 |
| `langflow_components/data_analysis_flow/CONNECTION_GUIDE.md` | 실제 데이터 조회/분석 flow를 만들 때 |
| `langflow_components/metadata_qa_flow/CONNECTION_GUIDE.md` | metadata/catalog/help 답변 flow를 만들 때 |
| `langflow_components/report_generation_flow/CONNECTION_GUIDE.md` | 리포트 생성 branch를 붙일 때 |
| `langflow_components/operations_diagnosis_flow/CONNECTION_GUIDE.md` | 운영 진단 branch를 붙일 때 |
| `langflow_components/session_state_flow/CONNECTION_GUIDE.md` | 대화별 state load/write를 연결할 때 |

## Common Runtime Rule

main router flow:

```text
Chat Input
-> Smart Router
-> route별로 미리 선택된 Run Flow 노드 하나
-> 선택 route의 subflow 응답
-> Chat Output
```

subflow:

```text
Chat Input
-> 00 MongoDB Session State Loader
-> 00 Request Loader
-> subflow logic
-> Final API Response
-> 01 MongoDB Session State Writer

Final Message
-> Chat Output
```

## Common Component Rules

- 하위 flow의 00 request loader는 `Question`과 `Previous State`만 직접 연결합니다.
- session id는 별도 포트로 연결하지 않고 Chat/API message 또는 final API response에서 자동 추론합니다.
- main router는 subflow payload를 조립하지 않습니다.
- router flow에는 별도 custom request loader, route normalizer, execution adapter를 두지 않습니다.
- Smart Router route output을 route별로 미리 선택한 Run Flow 노드의 동적 입력 포트에 연결합니다.
- direct router canvas에서는 여러 native Run Flow output을 한 노드에 무리하게 모으지 않습니다. 이 구조는 선택되지 않은 branch까지 기다릴 수 있습니다.
- Web/API에서 router를 사용할 때는 선택된 subflow의 API/Data output을 우선 파싱합니다. subflow가 Message만 반환하면 message-only 응답으로 처리합니다.
- custom component는 standalone 파일로 동작해야 하며 sibling helper import를 사용하지 않습니다.
- input 이름과 output 이름이 같은 component 안에서 겹치지 않게 합니다.
