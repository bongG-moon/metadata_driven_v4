# Metadata QA Flow 연결 가이드

이 flow는 MongoDB에 저장된 `domain`, `table catalog`, `main flow filter` 메타데이터를 읽어서 사용자의 메타데이터 질문에 답변한다.
저장/수정/result store 동작은 하지 않는다.

## 1. 사용 노드

| 번호 | 노드 | 종류 | 역할 |
| --- | --- | --- | --- |
| 00 | `00 메타데이터 QA 요청 로더` | Custom Component | 질문을 표준 페이로드로 변환 |
| 01A | `01A 메타데이터 QA 도메인 로더` | Custom Component | MongoDB domain collection 읽기 |
| 01B | `01B 메타데이터 QA 테이블 카탈로그 로더` | Custom Component | MongoDB table catalog collection 읽기 |
| 01C | `01C 메타데이터 QA 메인 필터 로더` | Custom Component | MongoDB main flow filter collection 읽기 |
| 02 | `02 메타데이터 QA 컨텍스트 생성기` | Custom Component | 질문과 관련된 메타데이터 후보 선별 |
| 03 | `03 메타데이터 QA 변수 생성기` | Custom Component | Prompt Template 입력 변수 생성 |
| 03P | `Prompt Template` | Langflow 기본 노드 | 한국어 QA 프롬프트 작성 |
| 03L | `Agent` 또는 `LLM` | Langflow 기본 노드 | metadata QA 답변 JSON 생성 |
| 04 | `04 메타데이터 QA 응답 정규화기` | Custom Component | LLM 응답을 표준 payload로 정규화 |
| 05 | `05 메타데이터 QA 메시지 어댑터` | Custom Component | Playground용 markdown 생성 |
| 06 | `06 메타데이터 QA API 응답 생성기` | Custom Component | Web/API용 구조화 응답 생성 |
| CO | `Chat Output` | Langflow 기본 노드 | Playground 최종 답변 표시 |

## 2. 노드 연결

아래 순서대로 연결한다.

| 순서 | From output | To input |
| --- | --- | --- |
| 1 | `Chat Input.message` | `00 메타데이터 QA 요청 로더.사용자 질문` |
| 2 | `00 메타데이터 QA 요청 로더.페이로드 출력` | `02 메타데이터 QA 컨텍스트 생성기.페이로드` |
| 3 | `01A 메타데이터 QA 도메인 로더.도메인 메타데이터` | `02 메타데이터 QA 컨텍스트 생성기.도메인 메타데이터` |
| 4 | `01B 메타데이터 QA 테이블 카탈로그 로더.테이블 카탈로그` | `02 메타데이터 QA 컨텍스트 생성기.테이블 카탈로그` |
| 5 | `01C 메타데이터 QA 메인 필터 로더.메인 필터` | `02 메타데이터 QA 컨텍스트 생성기.메인 필터` |
| 6 | `02 메타데이터 QA 컨텍스트 생성기.페이로드 출력` | `03 메타데이터 QA 변수 생성기.페이로드` |
| 7 | `02 메타데이터 QA 컨텍스트 생성기.페이로드 출력` | `04 메타데이터 QA 응답 정규화기.페이로드` |
| 8 | `03 메타데이터 QA 변수 생성기.사용자 질문` | `Prompt Template.question` |
| 9 | `03 메타데이터 QA 변수 생성기.메타데이터 컨텍스트 JSON` | `Prompt Template.metadata_context_json` |
| 10 | `03 메타데이터 QA 변수 생성기.출력 스키마 JSON` | `Prompt Template.output_schema_json` |
| 11 | `Prompt Template.message` | `Agent` 또는 `LLM`의 prompt/message 입력 |
| 12 | `Agent` 또는 `LLM`의 응답 Message | `04 메타데이터 QA 응답 정규화기.LLM 응답` |
| 13 | `04 메타데이터 QA 응답 정규화기.페이로드 출력` | `05 메타데이터 QA 메시지 어댑터.페이로드` |
| 14 | `04 메타데이터 QA 응답 정규화기.페이로드 출력` | `06 메타데이터 QA API 응답 생성기.페이로드` |
| 15 | `05 메타데이터 QA 메시지 어댑터.메시지` | `06 메타데이터 QA API 응답 생성기.채팅 표시 메시지` |
| 16 | `05 메타데이터 QA 메시지 어댑터.메시지` | `Chat Output.input` |

Web/API에서 구조화 응답을 확인해야 하면 `06 메타데이터 QA API 응답 생성기.API 응답`을 Langflow API output으로 사용한다.
JSON 문자열 output이 더 안정적인 환경이면 `06 메타데이터 QA API 응답 생성기.API 메시지`를 함께 노출한다.

## 3. Prompt Template 내용

Prompt Template에는 [03_metadata_qa_prompt_template_ko.md](./03_metadata_qa_prompt_template_ko.md)의 내용을 그대로 넣는다.

템플릿 변수는 세 개만 사용한다.

| Prompt 변수 | 연결할 output |
| --- | --- |
| `question` | `03 메타데이터 QA 변수 생성기.사용자 질문` |
| `metadata_context_json` | `03 메타데이터 QA 변수 생성기.메타데이터 컨텍스트 JSON` |
| `output_schema_json` | `03 메타데이터 QA 변수 생성기.출력 스키마 JSON` |

응답 정책은 Prompt Template 본문에 고정 문구로 들어 있으므로 별도 노드 출력으로 연결하지 않는다.

`04 메타데이터 QA 응답 정규화기`는 LLM 응답 또는 fallback 결과를 `answer_type`과 `answer_sections`로 정규화한다. `answer_type`은 데이터 목록, 데이터셋 설명, 필수 조건, SQL, 용어 정의, 공정 그룹, 제품 조건, 계산 로직, 실제 분석 route 안내 같은 질문 유형을 나타낸다. `05 메타데이터 QA 메시지 어댑터`와 `06 메타데이터 QA API 응답 생성기`는 이 구조를 우선 사용한다.

## 4. MongoDB 설정

기본 collection은 아래 env 값을 사용한다.

```text
MONGODB_DATABASE=datagov
MONGODB_DOMAIN_COLLECTION=agent_v4_domain_items
MONGODB_TABLE_CATALOG_COLLECTION=agent_v4_table_catalog_items
MONGODB_MAIN_FLOW_FILTER_COLLECTION=agent_v4_main_flow_filters
```

`MONGODB_RESULT_COLLECTION`은 사용하지 않는다.
이 flow는 메타데이터를 읽고 답변만 생성한다.

## 5. Router 연결

Router flow에서 metadata QA route는 아래처럼 연결한다.

```text
Smart Router.metadata_qa
  -> Run Flow(metadata_qa_flow).질문 입력 포트
  -> Run Flow(metadata_qa_flow).Message
  -> Chat Output(metadata_qa 응답)
```

Smart Router의 `metadata_qa` route는 `Route Message`를 비워둔다.
그래야 원래 사용자 질문이 `metadata_qa_flow`로 그대로 전달된다.

### 5.1 Tool Call Router v2 연결

`router_flow_v2`에서 `metadata_qa_flow`를 Run Flow tool로 사용할 때도 최종 대상은 동일하다.
Run Flow에서 `metadata_qa_flow`를 선택하고 refresh한 뒤 Tool Mode를 켠다.

이 flow의 첫 입력인 `00 메타데이터 QA 요청 로더.사용자 질문`은 agent가 제어해야 하는 입력이므로 코드상 `tool_mode=True`로 지정되어 있다.
Run Flow tool call 결과에 아래 오류가 나오면 MongoDB 문제가 아니라 질문 입력 매핑 문제다.

```text
{"type": "empty_question", "message": "메타데이터 QA 질문이 비어 있습니다."}
```

이 경우 `router_flow_v2/CONNECTION_GUIDE.md`의 `Metadata QA Tool 필수 확인` 절차에 따라 Run Flow refresh와 Tool Mode 재설정을 먼저 확인한다.

질문 입력이 정상인데도 데이터가 비어 있으면 01A/01B/01C MongoDB 로더 상태를 본다.
상태가 `skipped / ... / 0건`이면 `MONGODB_URI`가 Langflow 실행 환경에 없거나 로더 고급 입력이 비어 있는 것이다.
상태가 `error / ... / 0건`이면 MongoDB 연결, 인증, collection 이름을 확인한다.

## 6. 검증 질문

아래 질문으로 flow 동작을 확인한다.

```text
생산량과 관련해서 등록된 도메인 정보들 보여줄래?
지금 등록된 계산 로직들이 어떤 것들이 있는지 list 보여줘.
생산량 데이터 관련 쿼리문은 어떤 건지 알려줘.
지금 조회 가능한 데이터들이 뭐가 있고 각 데이터의 연결방식과 필수 조건은 뭐야?
POP 제품은 도메인 정보가 어떻게 등록되어 있어?
```

## 7. 지시사항 체크

- 메타데이터 원문 구조를 변형해서 MongoDB에 다시 저장하지 않는다.
- raw trace, raw text, LLM raw response, credential은 prompt와 응답에서 제거한다.
- 실제 데이터 조회, pandas 실행, result store 저장은 하지 않는다.
- Prompt Template과 Agent/LLM은 Langflow 기본 노드를 사용한다.
- custom component 안에 최종 QA prompt를 하드코딩하지 않고 별도 Prompt Template 파일로 제공한다.
