# Router Flow v2 연결 가이드 - Tool Call 기반

이 문서는 기존 `router_flow`의 Smart Router 방식과 별도로, Agent가 `Run Flow` tool을 호출해서 하위 flow를 실행하는 v2 구조를 설명한다.
운영 안정성은 기존 Smart Router 방식이 더 높고, v2는 tool call 기반 agentic routing을 검증하기 위한 대안 구조다.

## 1. 최종 구조

```text
Chat Input
-> Agent 또는 Tool Calling Agent
   -> Run Flow Tool: data_analysis_flow
   -> Run Flow Tool: metadata_qa_flow
   -> Run Flow Tool: domain_saving_flow
   -> Run Flow Tool: table_catalog_saving_flow
   -> Run Flow Tool: main_flow_filters_saving_flow
   -> Run Flow Tool: dummy_* flows
-> Chat Output
```

핵심 원칙:

- 하위 flow 실행은 `Run Flow` 컴포넌트의 Tool Mode로 처리한다.
- Agent는 route를 JSON으로 출력하지 않고, 알맞은 tool action을 직접 호출한다.
- 각 `Run Flow` 노드에서 대상 flow를 dropdown으로 미리 선택한다. flow 이름을 변수로 전달하지 않는다.
- 제품 token 매칭, pandas function case 선택, 공정/제품 조건 해석은 `data_analysis_flow` 안에서 처리한다.
- 메타데이터 저장 요청의 원문은 Agent가 요약하거나 수정하지 않고 saving tool의 `raw_text`로 그대로 전달한다.
- dummy tool은 사용자가 명시적으로 dummy 또는 `route_hint=dummy_*`를 요청한 경우에만 호출한다.
- 모호한 요청은 tool을 호출하지 않고 짧은 확인 질문을 반환한다.

## 2. 권장 사용 범위

| 구분 | Smart Router 방식 | Tool Call v2 방식 |
| --- | --- | --- |
| 운영 Web/API | 권장 | 비권장 |
| Playground 실험 | 권장 | 가능 |
| route가 눈에 보여야 하는 경우 | 권장 | 부적합 |
| Agent가 tool을 자율 선택하는 실험 | 제한적 | 권장 |
| `api_response` 구조를 그대로 Web에 전달 | 권장 | LLM 요약 위험 있음 |
| 복합 agent 동작 확장 | 제한적 | 가능 |

v2는 Agent 최종 답변이 tool 결과를 요약할 수 있으므로, Web/API에서 구조화된 `response_type`, `data`, `trace`, `answer_sections`를 안정적으로 받아야 하는 경우에는 기존 `router_flow`를 우선 사용한다.

## 3. 노드 구성

### 3.1 기본 노드

| 순서 | 노드 | 설정 |
| --- | --- | --- |
| 1 | `Chat Input` | 사용자 입력 수신 |
| 2 | `Language Model` | Agent가 사용할 LLM 설정 |
| 3 | `Agent` 또는 `Tool Calling Agent` | system prompt는 `SYSTEM_PROMPT_KO.md` 사용 |
| 4 | `Run Flow - Data Analysis Tool` | flow=`data_analysis_flow`, Tool Mode on |
| 5 | `Run Flow - Metadata QA Tool` | flow=`metadata_qa_flow`, Tool Mode on |
| 6 | `Run Flow - Domain Saving Tool` | flow=`domain_saving_flow`, Tool Mode on |
| 7 | `Run Flow - Table Catalog Saving Tool` | flow=`table_catalog_saving_flow`, Tool Mode on |
| 8 | `Run Flow - Main Flow Filter Saving Tool` | flow=`main_flow_filters_saving_flow`, Tool Mode on |
| 9 | `Run Flow - Dummy ... Tool` | 필요한 dummy flow만 추가, Tool Mode on |
| 10 | `Chat Output` | Agent 최종 답변 표시 |

### 3.2 연결

| From | To |
| --- | --- |
| `Chat Input.message` | `Agent.input` 또는 `Tool Calling Agent.input_value` |
| `Language Model.output` | `Agent.model` 또는 `Tool Calling Agent.llm` |
| 각 `Run Flow.Toolset` 또는 `Run Flow.Tool` | `Agent.Tools` 또는 `Tool Calling Agent.tools` |
| `Agent.message/output` | `Chat Output.input` |

Langflow 버전에 따라 Agent 입력 포트명이 다를 수 있다.
핵심은 `Chat Input`은 Agent의 사용자 입력으로, 모든 Run Flow tool output은 Agent의 Tools 입력으로 연결하는 것이다.

## 4. Run Flow Tool 설정 절차

각 하위 flow마다 아래 절차를 반복한다.

1. canvas에 `Run Flow` 컴포넌트를 추가한다.
2. Run Flow의 flow dropdown에서 대상 flow를 선택한다.
3. refresh를 눌러 선택한 flow의 입력/출력 구조를 반영한다.
4. 컴포넌트 메뉴에서 `Tool Mode`를 켠다.
5. `Edit Tool Actions`에서 action slug, name, description을 `TOOL_DESCRIPTIONS.md` 기준으로 수정한다.
6. Run Flow의 Toolset/Tool output을 Agent의 Tools 입력에 연결한다.
7. Playground에서 tool call detail을 열어 tool input이 빈 문자열이 아닌지 확인한다.

주의:

- 실제 flow 실행 tool은 Route Message 같은 중간 메시지를 쓰지 않는다.
- saving tool의 입력은 `raw_text` 의미를 가진다. Agent가 원문을 다시 쓰면 안 된다.
- data/metadata QA tool의 입력은 `question` 의미를 가진다.
- Run Flow의 대상 flow는 변수 입력이 아니라 각 Run Flow 노드 설정에서 고정한다.
- 선택한 하위 flow의 첫 입력 컴포넌트에는 `tool_mode=True`가 있어야 agent-controlled 입력으로 안정적으로 노출된다.
- `empty_question` 또는 `empty_raw_text` 오류가 나오면 tool 선택은 되었지만 입력값이 하위 flow의 첫 입력으로 전달되지 않은 것이다.

### 4.1 Metadata QA Tool 필수 확인

`run_metadata_qa`에서 아래처럼 나오면 입력 매핑 문제다.

```text
오류: {"type": "empty_question", "message": "메타데이터 QA 질문이 비어 있습니다."}
```

이 오류는 MongoDB 조회 실패가 아니다.
tool은 호출되었지만 agent 입력이 `metadata_qa_flow` 내부의 `Chat Input` 또는 `00 메타데이터 QA 요청 로더.사용자 질문`에 들어가지 않은 상태다.

data analysis flow와 metadata QA flow 모두 `Chat Input.message -> 00 요청 로더.사용자 질문` 구조라면 wrapper flow는 추가하지 않는다.
이 경우 차이는 보통 flow 구조가 아니라 `Run Flow`가 언제 refresh되었는지, 그리고 Tool Action이 어떤 입력을 agent-controlled parameter로 잡고 있는지에서 발생한다.

확인 순서는 아래와 같다.

1. `metadata_qa_flow` 안에 실제 `Chat Input` 노드가 있고, 그 출력이 `00 메타데이터 QA 요청 로더.사용자 질문`으로 연결되어 있는지 확인한다.
2. `metadata_qa_flow` 자체를 Playground에서 직접 실행해 같은 질문이 정상 동작하는지 먼저 확인한다.
3. router v2의 `Run Flow - Metadata QA Tool`에서 대상 flow가 `metadata_qa_flow`인지 확인한다.
4. `metadata_qa_flow`를 저장한 뒤 router v2의 Run Flow에서 refresh를 다시 누른다. Chat Input 연결 전 상태로 refresh된 tool action은 질문을 빈 값으로 넘길 수 있다.
5. Tool Mode를 껐다가 다시 켠다.
6. `Edit Tool Actions`에서 입력값이 빈 문자열로 고정되어 있지 않은지 확인한다. 보통은 `Input controlled by the agent` 상태여야 한다.
7. Playground tool call detail에서 tool input이 `현재 조회가능한 dataset list와 필수 para정보를 알려줘`처럼 실제 질문으로 들어갔는지 확인한다.

`empty_question`이 사라진 뒤에도 데이터가 비어 있으면 그때는 MongoDB 로더 문제다.
01A/01B/01C 로더 상태가 아래처럼 보여야 정상이다.

```text
ok / agent_v4_table_catalog_items / 9건
```

`skipped / ... / 0건`이면 Langflow 실행 환경에 `MONGODB_URI`가 없거나, 로더의 고급 입력 `MongoDB 연결 URI`가 비어 있는 상태다.
`error / ... / 0건`이면 URI, 네트워크, 인증, collection 이름을 확인한다.

## 5. Tool 목록

| Tool action slug | 대상 flow | 입력 의미 | 호출 조건 |
| --- | --- | --- | --- |
| `run_data_analysis` | `data_analysis_flow` | `question` | 생산량, 재공, 투입, 장비 ASSIGN 등 실제 제조 데이터 분석 |
| `run_metadata_qa` | `metadata_qa_flow` | `question` | 저장된 메타데이터, 데이터셋, 쿼리, 필수 조건, 도메인 규칙 조회 |
| `save_domain_metadata` | `domain_saving_flow` | `raw_text` | 업무 용어, 공정 그룹, 분석 규칙, 특화 함수 설명 등록 |
| `save_table_catalog_metadata` | `table_catalog_saving_flow` | `raw_text` | 데이터셋, source_type, query_template, required_params 등록 |
| `save_main_flow_filter_metadata` | `main_flow_filters_saving_flow` | `raw_text` | DATE, OPER_NAME, ORG 같은 공통 필터 정의 등록 |
| `run_dummy_data_analysis` | `dummy_data_analysis_flow` | `question` | 명시적 dummy data analysis 테스트 |
| `run_dummy_metadata_qa` | `dummy_metadata_qa_flow` | `question` | 명시적 dummy metadata QA 테스트 |
| `run_dummy_domain_saving` | `dummy_domain_saving_flow` | `raw_text` | 명시적 dummy domain saving 테스트 |
| `run_dummy_table_catalog_saving` | `dummy_table_catalog_saving_flow` | `raw_text` | 명시적 dummy table catalog saving 테스트 |
| `run_dummy_main_flow_filter_saving` | `dummy_main_flow_filter_saving_flow` | `raw_text` | 명시적 dummy main filter saving 테스트 |

tool action 설명 전문은 `TOOL_DESCRIPTIONS.md`를 사용한다.

## 6. Agent System Prompt

Agent의 System Message에는 `SYSTEM_PROMPT_KO.md` 내용을 그대로 넣는다.

중요한 제약:

- 명확한 분석/QA/저장 요청이면 정확히 하나의 tool을 호출한다.
- direct answer와 clarification은 tool을 호출하지 않는다.
- direct answer는 기능 범위와 대표 예시를 함께 안내한다.
- clarification은 분석/QA/등록 중 어떤 요청인지와 추가로 필요한 정보를 선택지로 묻는다.
- tool 결과에 `message` 또는 `display_message`가 있으면 그 내용을 우선 그대로 사용자에게 보여준다.
- tool 결과를 임의로 짧게 요약해서 구조를 깨지 않는다.
- saving 요청의 raw text는 사용자가 입력한 원문 그대로 넘긴다.

## 7. Direct Answer / Clarification

Tool Call v2에서는 `direct_answer`, `clarification` route용 별도 Run Flow를 만들지 않는다.
Agent가 tool을 호출하지 않고 직접 답한다.

예:

| 입력 | 동작 |
| --- | --- |
| 안녕 | tool 호출 없이 제조 데이터 분석, 메타데이터 QA, 메타데이터 등록 기능과 대표 예시 안내 |
| 이 챗봇으로 뭘 할 수 있어? | tool 호출 없이 분석/QA/등록 가능 범위와 입력 예시 안내 |
| 이거 확인해줘 | tool 호출 없이 분석/QA/등록 중 어떤 요청인지, 어떤 정보를 추가하면 되는지 되묻기 |
| 등록해줘 | tool 호출 없이 등록할 원문과 metadata 종류를 되묻기 |

## 8. Web/API 사용 주의

Tool Call v2는 Agent가 tool 결과를 다시 말로 정리하는 구조라서, 기존 flow들의 구조화된 `api_response`를 Web에 그대로 전달하기 어렵다.

따라서 기준은 아래처럼 나눈다.

- Playground/agentic routing 실험: `router_flow_v2`
- Web/API 운영 라우팅: 기존 `router_flow`

만약 v2를 Web에서 써야 한다면 아래 조건을 추가로 만족해야 한다.

1. Agent system prompt에서 tool 결과의 `display_message` 또는 `message`를 그대로 반환하도록 강하게 제한한다.
2. Web은 Agent의 최종 텍스트를 API 계약으로 파싱하지 않는다.
3. 구조화 JSON이 반드시 필요하면 v2가 아니라 기존 Smart Router 방식으로 호출한다.

## 9. 새 Tool 추가 방법

1. 대상 하위 flow가 `message` 또는 `api_response` 계약을 지키는지 확인한다.
2. `Run Flow` 노드를 추가한다.
3. flow dropdown에서 대상 flow를 선택하고 refresh한다.
4. Tool Mode를 켠다.
5. `TOOL_DESCRIPTIONS.md`에 action slug와 설명을 추가한다.
6. `SYSTEM_PROMPT_KO.md`에 호출 조건과 금지 조건을 추가한다.
7. `EXAMPLE_QUESTIONS.md`에 대표 질문을 추가한다.
8. 테스트에 새 tool slug가 포함되도록 갱신한다.

## 10. 지시사항 체크

- router v2는 하위 flow를 API Request로 직접 호출하지 않는다.
- router v2는 제품 token 매칭, pandas function case 선택, 공정 조건 분해를 하지 않는다.
- saving raw text는 요약/수정하지 않는다.
- dummy tool은 명시적 테스트 요청에서만 사용한다.
- 구조화 API가 중요한 운영 경로에서는 기존 Smart Router 방식이 우선이다.
