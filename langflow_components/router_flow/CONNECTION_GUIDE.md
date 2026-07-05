# Router Flow 연결 가이드

이 문서는 v4 router flow의 단일 기준 문서다.
이전의 route-flow map 내용까지 이 문서에 합쳤으므로, Smart Router route와 Run Flow 연결은 이 문서만 보고 구성한다.

## 1. 최종 구조

Router flow는 별도 custom component 없이 Langflow 기본 노드만 사용한다.

```text
Chat Input
-> Smart Router
-> route별 Run Flow
-> route별 Chat Output 또는 API/Data Output
```

핵심 원칙:

- Router는 사용자의 요청을 어떤 flow로 보낼지만 판단한다.
- 제품 token 매핑, pandas function case 선택, 공정/제품 조건 해석은 `data_analysis_flow` 안에서 처리한다.
- 메타데이터 원문은 router에서 수정하지 않고 saving flow로 그대로 전달한다.
- Run Flow 대상 flow는 변수 입력이 아니라 각 Run Flow 노드 설정에서 미리 선택한다.
- `selected_flow`는 Run Flow에 변수로 연결하는 값이 아니라, route branch에 배치한 Run Flow 노드에서 미리 선택할 대상 flow 이름이다.
- `direct_answer`와 `clarification`은 Run Flow를 만들지 않고 Smart Router message를 Chat Output으로 바로 보낸다.
- `flow_error`는 Smart Router routes table에 넣는 route가 아니다. 실행된 subflow가 오류 응답을 반환한다.

## 2. Smart Router 설정

`Chat Input.message`를 `Smart Router.Input`에 연결한다.

Smart Router routes table에는 아래 값을 넣는다.
실제 flow를 실행하는 route는 `Route Message`를 비워 원래 입력을 Run Flow로 보내고, direct/clarification route만 메시지를 채운다.

| Route Name | selected_flow | Input Mode | Output Type | Route Description | Route Message |
| --- | --- | --- | --- | --- | --- |
| `data_analysis` | `data_analysis_flow` | `question` | `data_analysis` | 생산량, 재공, 투입, 제품별 집계처럼 실제 제조 데이터를 조회/분석해야 하는 질문 |  |
| `metadata_qa` | `metadata_qa_flow` | `question` | `metadata_qa` | 등록된 데이터셋 목록, 컬럼 설명, 저장된 메타데이터, 등록 규칙을 조회/설명하는 질문 |  |
| `domain_saving` | `domain_saving_flow` | `raw_text` | `metadata_authoring` | 업무 용어, 공정 그룹, 분석 규칙, 특화 함수 설명을 domain metadata로 등록하는 요청 |  |
| `table_catalog_saving` | `table_catalog_saving_flow` | `raw_text` | `metadata_authoring` | 데이터셋, source_type, query_template, required_params, columns를 table catalog metadata로 등록하는 요청 |  |
| `main_flow_filter_saving` | `main_flow_filters_saving_flow` | `raw_text` | `metadata_authoring` | DATE, OPER_NAME, ORG 같은 공통 필터 정의를 main flow filter metadata로 등록하는 요청 |  |
| `dummy_data_analysis` | `dummy_data_analysis_flow` | `question` | `data_analysis` | `route_hint=dummy_data_analysis`처럼 개발/스모크 테스트용 더미 분석을 명시한 요청 |  |
| `dummy_metadata_qa` | `dummy_metadata_qa_flow` | `question` | `metadata_qa` | `route_hint=dummy_metadata_qa`처럼 메타데이터 QA 응답 shape만 빠르게 테스트하는 요청 |  |
| `dummy_domain_saving` | `dummy_domain_saving_flow` | `raw_text` | `metadata_authoring` | `route_hint=dummy_domain_saving`처럼 domain saving 응답 shape만 테스트하는 요청 |  |
| `dummy_table_catalog_saving` | `dummy_table_catalog_saving_flow` | `raw_text` | `metadata_authoring` | `route_hint=dummy_table_catalog_saving`처럼 table catalog saving 응답 shape만 테스트하는 요청 |  |
| `dummy_main_flow_filter_saving` | `dummy_main_flow_filter_saving_flow` | `raw_text` | `metadata_authoring` | `route_hint=dummy_main_flow_filter_saving`처럼 main filter saving 응답 shape만 테스트하는 요청 |  |
| `direct_answer` | router direct | `question` | `direct_answer` | 인사, 도움말, 사용 범위 안내처럼 하위 flow 실행 없이 답할 수 있는 요청 | 안녕하세요. 제조 데이터 분석, 메타데이터 QA, 메타데이터 등록을 도와드릴 수 있습니다.<br><br>예를 들어 이렇게 물어볼 수 있습니다.<br>- 데이터 분석: 오늘 DA공정 생산량 알려줘<br>- 메타데이터 QA: 지금 조회 가능한 데이터셋과 필수 조건을 보여줘<br>- 메타데이터 등록: DA 공정 그룹은 D/A1~D/A6로 등록해줘<br><br>원하는 내용을 자연어로 입력해 주세요. |
| `clarification` | router direct | `question` | `clarification` | 분석/조회/등록 중 어느 요청인지 불명확한 입력 | 무엇을 확인하면 될지 조금만 더 알려주세요.<br><br>아래 중 어떤 요청인지 알려주시면 바로 이어서 처리하겠습니다.<br>- 데이터 분석: 기준일, 공정, 제품, 보고 싶은 지표를 알려주세요. 예: 오늘 DA공정 생산량 알려줘<br>- 메타데이터 QA: 확인할 데이터셋, 컬럼, 계산 로직, 등록 규칙을 알려주세요. 예: production_today 필수 조건 보여줘<br>- 메타데이터 등록: 등록할 원문과 metadata 종류를 알려주세요. 예: DA 공정 그룹을 domain metadata로 등록해줘 |

Additional Instructions에는 아래 내용을 넣는다.

```text
제조 데이터 조회/분석 질문은 data_analysis로 보낸다.
metadata의 의미, 등록 내용, 데이터셋/컬럼 설명을 묻는 질문은 metadata_qa로 보낸다.
metadata를 새로 등록하거나 수정하라는 요청은 saving route로 보낸다.
제품 token 매핑, pandas 함수 선택, 공정/제품 조건 해석은 여기서 판단하지 않는다.
불명확한 경우 data_analysis로 추측하지 말고 clarification 또는 Else 안내 branch로 보낸다.
개발 테스트용 dummy route는 사용자가 명시적으로 dummy 테스트를 요청했거나 route hint 성격의 입력을 준 경우에만 선택한다.
인사, 도움말, 사용법처럼 하위 flow 실행이 필요 없는 요청은 direct_answer로 보낸다. direct_answer는 기능 범위와 대표 예시를 함께 안내한다.
모호한 요청은 clarification 또는 Else 안내 branch로 보내고, 사용자가 다음에 어떤 정보를 추가하면 되는지 알려준다.
```

## 3. Route Description과 Route Message

| 항목 | 의미 | 입력 원칙 |
| --- | --- | --- |
| `Route Description` | Smart Router가 어떤 route를 고를지 판단할 때 보는 설명 | 모든 route에 구체적으로 작성 |
| `Route Message` | route가 선택된 뒤 다음 노드로 전달되는 메시지 | 실제 flow 실행 route는 비우고 direct/clarification만 작성 |

실제 flow 실행 route에서 `Route Message`를 채우면 원래 사용자 질문이 Run Flow로 전달되지 않는다.
따라서 `data_analysis`, `metadata_qa`, saving, dummy route는 반드시 `Route Message`를 비운다.

direct/clarification은 별도 flow를 실행하지 않으므로 Route Message 또는 Else Message가 최종 답변이 된다.

## 4. Route별 Run Flow 연결

각 flow 실행 route마다 `Run Flow` 노드를 하나씩 만든다.
Run Flow 노드의 flow 선택 dropdown에서 대상 flow를 직접 선택한 뒤 refresh한다.
refresh 후 보이는 동적 입력 포트에 Smart Router의 해당 route output을 연결한다.

| Smart Router output | Run Flow 노드에서 선택할 flow | Run Flow에서 연결할 입력 | Run Flow 출력 연결 |
| --- | --- | --- | --- |
| `data_analysis` | `data_analysis_flow` | `00 분석 요청 로더.사용자 질문`에 해당하는 질문 입력 포트 | `21 답변 메시지 어댑터.메시지` 또는 최종 Message output -> Chat Output |
| `metadata_qa` | `metadata_qa_flow` | `00 메타데이터 QA 요청 로더.사용자 질문`에 해당하는 질문 입력 포트 | `05 메타데이터 QA 메시지 어댑터.메시지` -> Chat Output |
| `domain_saving` | `domain_saving_flow` | `00 도메인 등록 요청 로더.Raw Text`에 해당하는 raw text 입력 포트 | `09 도메인 등록 메시지 어댑터.메시지` -> Chat Output |
| `table_catalog_saving` | `table_catalog_saving_flow` | `00 테이블 카탈로그 등록 요청 로더.Raw Text`에 해당하는 raw text 입력 포트 | `09 테이블 카탈로그 등록 메시지 어댑터.메시지` -> Chat Output |
| `main_flow_filter_saving` | `main_flow_filters_saving_flow` | `00 메인 플로우 필터 등록 요청 로더.Raw Text`에 해당하는 raw text 입력 포트 | `09 메인 플로우 필터 등록 메시지 어댑터.메시지` -> Chat Output |
| `dummy_data_analysis` | `dummy_data_analysis_flow` | `00 더미 분석 요청 로더.사용자 질문`에 해당하는 질문 입력 포트 | `01 더미 분석 응답 생성기.메시지` -> Chat Output |
| `dummy_metadata_qa` | `dummy_metadata_qa_flow` | `00 더미 메타데이터 QA 요청 로더.사용자 질문`에 해당하는 질문 입력 포트 | `01 더미 메타데이터 QA 응답 생성기.메시지` -> Chat Output |
| `dummy_domain_saving` | `dummy_domain_saving_flow` | `00 더미 도메인 등록 요청 로더.Raw Text`에 해당하는 raw text 입력 포트 | `01 더미 도메인 등록 응답 생성기.메시지` -> Chat Output |
| `dummy_table_catalog_saving` | `dummy_table_catalog_saving_flow` | `00 더미 테이블 카탈로그 등록 요청 로더.Raw Text`에 해당하는 raw text 입력 포트 | `01 더미 테이블 카탈로그 등록 응답 생성기.메시지` -> Chat Output |
| `dummy_main_flow_filter_saving` | `dummy_main_flow_filter_saving_flow` | `00 더미 메인 필터 등록 요청 로더.Raw Text`에 해당하는 raw text 입력 포트 | `01 더미 메인 필터 등록 응답 생성기.메시지` -> Chat Output |

Run Flow의 실제 포트명은 선택한 flow를 refresh한 뒤 Langflow 화면에 열리는 이름을 따른다.
위 표의 `00 ...` 노드명은 대상 flow 내부에서 어떤 입력으로 연결되어야 하는지 확인하기 위한 기준이다.

### 4.1 Web/API 호출용 출력 연결

Playground에서 눈으로 확인할 때는 각 subflow의 `message` 출력을 `Chat Output`으로 연결한다.
하지만 Web에서 router flow를 Langflow API로 호출할 때는 화면 표시용 `message`가 아니라 구조화된 `api_response` 계열 Data 출력을 최종 output으로 노출한다.

| 호출되는 flow | Playground 표시용 출력 | Web/API에서 router flow 밖으로 내보낼 출력 |
| --- | --- | --- |
| `data_analysis_flow` | `21 답변 메시지 어댑터.message` | `22 API 응답 생성기.api_response` |
| `metadata_qa_flow` | `05 메타데이터 QA 메시지 어댑터.message` | `06 메타데이터 QA API 응답 생성기.api_response` |
| `domain_saving_flow` | `09 도메인 등록 메시지 어댑터.message` | `10 도메인 등록 API 응답 생성기.api_response` |
| `table_catalog_saving_flow` | `09 테이블 카탈로그 등록 메시지 어댑터.message` | `10 테이블 카탈로그 등록 API 응답 생성기.api_response` |
| `main_flow_filter_saving_flow` | `09 메인 플로우 필터 등록 메시지 어댑터.message` | `10 메인 플로우 필터 등록 API 응답 생성기.api_response` |

정리하면 아래 기준을 따른다.

- Langflow Playground/Chat 확인용: 각 flow의 `message`
- Web/API 구조화 응답용: 각 flow의 `api_response`
- `api_message`: `Data` 연결이 불안정하거나 Message output만 읽는 환경을 위한 예비 출력

Web에서 route flow 하나를 호출해 실제 응답 JSON을 받아야 한다면, 선택된 branch의 `api_response`를 최종 `Data Output`으로 노출한다.
Smart Router branch를 여러 개 두는 구조에서는 branch별 `api_response` output을 각각 노출하거나, 현재 Langflow 버전에서 제공하는 rendezvous 노드가 있을 때만 하나로 모은다.
Web은 `Chat Output` 텍스트를 API 계약으로 파싱하지 않고, `response_type`, `direct_response_ready`, `message`, `data`, `trace`가 들어 있는 `api_response`를 기준으로 화면을 렌더링한다.

## 5. Metadata QA Subflow 내부 연결

`metadata_qa_flow`는 아래처럼 구성한다.

| 순서 | From output | To input |
| --- | --- | --- |
| 1 | `Chat Input.message` 또는 `Run Flow(metadata_qa).질문 입력` | `00 메타데이터 QA 요청 로더.사용자 질문` |
| 2 | `00 메타데이터 QA 요청 로더.페이로드 출력` | `02 메타데이터 QA 컨텍스트 생성기.페이로드` |
| 3 | `01A 메타데이터 QA 도메인 로더.도메인 메타데이터` | `02 메타데이터 QA 컨텍스트 생성기.도메인 메타데이터` |
| 4 | `01B 메타데이터 QA 테이블 카탈로그 로더.테이블 카탈로그` | `02 메타데이터 QA 컨텍스트 생성기.테이블 카탈로그` |
| 5 | `01C 메타데이터 QA 메인 필터 로더.메인 필터` | `02 메타데이터 QA 컨텍스트 생성기.메인 필터` |
| 6 | `02 메타데이터 QA 컨텍스트 생성기.페이로드 출력` | `03 메타데이터 QA 변수 생성기.페이로드` |
| 7 | `02 메타데이터 QA 컨텍스트 생성기.페이로드 출력` | `04 메타데이터 QA 응답 정규화기.페이로드` |
| 8 | `03 메타데이터 QA 변수 생성기.사용자 질문` | `Prompt Template.question` |
| 9 | `03 메타데이터 QA 변수 생성기.메타데이터 컨텍스트 JSON` | `Prompt Template.metadata_context_json` |
| 10 | `03 메타데이터 QA 변수 생성기.출력 스키마 JSON` | `Prompt Template.output_schema_json` |
| 11 | `Prompt Template.message` | `Agent` 또는 `LLM` 입력 |
| 12 | `Agent` 또는 `LLM` 응답 | `04 메타데이터 QA 응답 정규화기.LLM 응답` |
| 13 | `04 메타데이터 QA 응답 정규화기.페이로드 출력` | `05 메타데이터 QA 메시지 어댑터.페이로드` |
| 14 | `04 메타데이터 QA 응답 정규화기.페이로드 출력` | `06 메타데이터 QA API 응답 생성기.페이로드` |
| 15 | `05 메타데이터 QA 메시지 어댑터.메시지` | `06 메타데이터 QA API 응답 생성기.채팅 표시 메시지` |
| 16 | `05 메타데이터 QA 메시지 어댑터.메시지` | `Chat Output.input` |

Prompt Template에는 `metadata_qa_flow/03_metadata_qa_prompt_template_ko.md` 내용을 넣는다.
Prompt Template 변수는 `question`, `metadata_context_json`, `output_schema_json` 세 개만 사용한다.
응답 정책은 Prompt Template 본문에 고정 문구로 포함되어 있으므로 별도 노드 출력으로 연결하지 않는다.

## 6. Direct Answer와 Clarification 연결

`direct_answer`와 `clarification`은 Run Flow를 만들지 않는다.
Smart Router output을 바로 최종 출력으로 보낸다.

```text
Smart Router.direct_answer
  -> Chat Output

Smart Router.clarification 또는 Else output
  -> Chat Output
```

direct/clarification은 Route Message를 비우지 않는다.
Route Message를 비우면 원래 사용자 입력이 그대로 나가므로, 안내 문구나 추가 질문 요청 문구를 명시한다.

Else output을 사용할 때는 Smart Router 설정에서 `Include Else Output`을 켠다.
Else Message에는 아래처럼 넣는다.

```text
무엇을 확인하면 될지 조금만 더 알려주세요.

아래 중 어떤 요청인지 알려주시면 바로 이어서 처리하겠습니다.
- 데이터 분석: 기준일, 공정, 제품, 보고 싶은 지표를 알려주세요. 예: 오늘 DA공정 생산량 알려줘
- 메타데이터 QA: 확인할 데이터셋, 컬럼, 계산 로직, 등록 규칙을 알려주세요. 예: production_today 필수 조건 보여줘
- 메타데이터 등록: 등록할 원문과 metadata 종류를 알려주세요. 예: DA 공정 그룹을 domain metadata로 등록해줘
```

## 7. 최종 출력 연결

### 7.1 Branch별 Chat Output 방식

가장 단순하고 권장하는 방식이다.

```text
Run Flow(data_analysis_flow).Message
  -> Chat Output(data_analysis 응답)

Run Flow(metadata_qa_flow).Message
  -> Chat Output(metadata_qa 응답)

Smart Router.direct_answer
  -> Chat Output(direct 응답)

Smart Router.Else 또는 clarification
  -> Chat Output(확인 요청)
```

선택된 branch만 실행되므로 Playground에서는 선택 branch의 Chat Output만 응답으로 보인다.

### 7.2 Chat Output 하나만 써야 하는 경우

캔버스 정책상 최종 `Chat Output`을 하나만 두고 싶다면, 각 branch 결과를 한 지점으로 모으는 rendezvous가 필요하다.

권장 우선순위:

1. Langflow에 `Notify` / `Listen` 컴포넌트가 있으면 각 branch 끝에 `Notify`, 마지막에 `Listen -> Chat Output`을 둔다.
2. `Notify` / `Listen`을 사용할 수 없으면 branch별 Chat Output을 사용한다.
3. 여러 Run Flow output을 하나의 custom merge 노드에 단순 연결하는 방식은 피한다. 선택되지 않은 branch까지 기다릴 수 있다.

Notify/Listen 방식 예:

```text
Run Flow(data_analysis_flow).Message
  -> Notify(router_response, status=data_analysis)

Run Flow(metadata_qa_flow).Message
  -> Notify(router_response, status=metadata_qa)

Smart Router.direct_answer
  -> Notify(router_response, status=direct_answer)

Smart Router.Else 또는 clarification
  -> Notify(router_response, status=clarification)

Listen(router_response)
  -> Chat Output
```

실제 사용 가능 여부는 현재 Langflow Desktop/서버 버전에서 `Notify` / `Listen` 노드가 제공되는지 확인한다.
Web/API 구조화 응답이 필요하면 Chat Output text만 보지 말고, 선택된 Run Flow의 `API 응답` 또는 구조화 `Data` output을 Langflow API output으로 노출한다. Saving flow는 내부 `10 ... API 응답 생성기.API 응답`을 우선 사용하고, Message output만 안정적으로 읽을 수 있는 환경에서는 `10 ... API 응답 생성기.API 메시지`를 함께 노출한다.

## 8. Runtime Error 처리

`flow_error`는 Smart Router routes table에 넣는 route가 아니다.
선택된 Run Flow 또는 subflow 내부에서 오류가 발생했을 때, 해당 subflow가 `status=error`, `message`, `errors`를 포함한 최종 Message/API 응답으로 반환한다.

처리 원칙:

- 각 subflow 내부에서 오류를 `status=error`, `message`, `errors` 형태로 정리해서 최종 Message/API output으로 반환한다.
- router flow는 오류를 새 route로 다시 분기하지 않는다.
- Web/API는 선택된 subflow 응답의 `status`와 `errors`를 보고 오류 화면을 표시한다.

## 9. 새 Flow 추가 방법

새 flow를 추가할 때 수정 지점은 이 문서와 Langflow canvas다.

1. 이 문서의 Smart Router routes table에 route row를 추가한다.
2. `Route Description`을 구체적으로 작성한다.
3. 실제 flow를 실행하는 route라면 `Route Message`를 비운다.
4. router canvas에 새 `Run Flow` 노드를 추가한다.
5. 새 Run Flow 노드의 flow dropdown에서 대상 flow를 직접 선택하고 refresh한다.
6. Smart Router의 새 route output을 새 Run Flow 입력 포트에 연결한다.
7. 새 flow가 기존 응답 계약을 맞추는지 테스트를 추가한다.

## 10. 더 이상 사용하지 않는 것

Smart Router 최종 구조에서는 아래 custom component chain을 사용하지 않는다.

- router request loader
- deterministic route gate
- route decision variables builder
- route classifier prompt template
- route decision normalizer
- execution request builder
- Native Run Flow result adapter
- router response builder

위 노드들은 `selected_flow`를 실행 대상처럼 다루거나 Web/API envelope를 별도로 감싸기 위한 중간 설계였고, 최종 Smart Router 구조에서는 불필요하다.

## 11. 지시사항 체크

- router는 제품 token 매핑, pandas function case 선택, 공정 조건 분해를 하지 않는다.
- metadata 등록 원문은 route branch로 그대로 전달한다.
- saving route는 domain, table catalog, main flow filter로 나뉜 기존 flow 구조를 유지한다.
- dummy route는 명시적 개발 테스트에서만 사용한다.
- 불명확한 route는 임의 fallback이 아니라 clarification 또는 Else 안내 branch로 보낸다.
- router 내부에서 하위 flow를 API로 호출하지 않는다.
- Run Flow 대상 flow는 변수 입력이 아니라 각 Run Flow 노드 설정에서 미리 선택한다.
