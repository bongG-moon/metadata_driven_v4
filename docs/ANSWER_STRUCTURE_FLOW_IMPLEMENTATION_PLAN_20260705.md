# Data Analysis / Metadata QA 답변 구조 개선 계획

작성일: 2026-07-05

기준 문서: `docs/ANSWER_STRUCTURE_BENCHMARK_AND_DESIGN_20260704.md`

## 1. 목표

`data_analysis_flow`와 `metadata_qa_flow`의 답변을 현업 사용자가 바로 이해할 수 있는 형태로 개선한다.

핵심 목표는 아래와 같다.

- 단순 숫자/표 나열이 아니라 "무엇을 기준으로 어떤 결과가 나왔는지" 설명한다.
- 기본 답변에는 현업용 결과와 기준만 보여주고, pandas code/trace는 개발자 진단 모드로 분리한다.
- Web/API에서도 같은 구조를 재사용할 수 있도록 `answer_sections` 형태의 구조화 응답을 추가한다.
- 기존 Langflow 연결은 최대한 유지하고, 불필요한 신규 노드를 늘리지 않는다.
- raw metadata, raw_trace, runtime source rows 같은 불필요한 대용량/민감 정보는 답변 구조에 넣지 않는다.

## 2. 현재 답변 구조 점검

### 2.1 Data Analysis Flow

현재 관련 파일:

- `18_answer_variables_builder.py`
- `19_answer_prompt_template_ko.md`
- `20_answer_response_builder.py`
- `21_answer_message_adapter.py`
- `22_api_response_builder.py`

현재 흐름:

```text
18 답변 변수 생성기
-> 19 답변 Prompt Template
-> LLM/Agent
-> 20 답변 응답 생성기
-> 21 답변 메시지 어댑터
-> 22 API 응답 생성기
```

현재 장점:

- `18`은 이미 `answer_context_json`에 `step_outputs`, `function_case_results`, 숫자 표시 정책을 전달한다.
- `19`는 답변을 2~4문장으로 쓰고, 단계형 분석과 숫자 표시 정책을 반영하도록 지시한다.
- `17 pandas 코드 실행기`는 `record_step`, `record_function_case_result` 기반의 중간 결과 기록 구조를 이미 가지고 있다.
- `21`은 기본 답변과 개발자 진단을 `include_diagnostics`로 분리한다.
- `21`은 숫자 10,000 이상을 K 단위로 표시하는 로직을 이미 가지고 있다.
- `22`는 runtime source rows를 제거하고 API 응답을 만든다.

현재 한계:

- `20`은 `answer_message`만 추가하고, 현업 화면용 구조인 `answer_sections`를 만들지 않는다.
- `21`은 메시지 조립을 자체 로직으로 수행하지만, API와 공유할 수 있는 구조화 섹션이 없다.
- `22`는 `answer_sections`를 API 응답에 포함하지 않는다.
- 적용 기준이 "조회 필수 조건"과 "분석 조건"으로 명확히 분리되어 있지 않다.
- 결과 없음과 값 0을 구분해 설명하는 정책이 아직 약하다.
- 제품 token/function case 결과가 메시지에는 보이지만, Web/API가 재사용하기 좋은 구조로 정규화되어 있지 않다.
- 다음 질문 후보가 없다.

### 2.2 Metadata QA Flow

현재 관련 파일:

- `02_metadata_qa_context_builder.py`
- `03_metadata_qa_variables_builder.py`
- `03_metadata_qa_prompt_template_ko.md`
- `04_metadata_qa_response_normalizer.py`
- `05_metadata_qa_message_adapter.py`
- `06_metadata_qa_api_response_builder.py`

현재 흐름:

```text
02 메타데이터 QA 컨텍스트 생성기
-> 03 메타데이터 QA 변수 생성기
-> 03 Prompt Template
-> LLM/Agent
-> 04 응답 정규화기
-> 05 메시지 어댑터
-> 06 API 응답 생성기
```

현재 장점:

- `02`가 raw_trace, raw_text, registration_trace, credential성 key를 제거한다.
- `02`가 질문 기준으로 `answer_mode`를 추론한다.
- 현재 `answer_mode`는 `dataset_sql`, `available_sources`, `calculation_logic_list`, `product_domain_info`, `domain_info`, `general_metadata_search`를 지원한다.
- `03`은 Prompt Template 변수 3개만 제공해 연결이 단순하다.
- `04`는 LLM 응답이 없거나 JSON parsing이 실패해도 fallback 답변을 만든다.
- `06`은 `metadata_qa_context`를 API 응답에서 제거한다.
- `metadata_qa`는 `response_type=metadata_qa`, `direct_response_ready=true` 계약을 가진다.

현재 한계:

- `answer_mode`가 아직 현업 질문 유형을 충분히 세분화하지 못한다.
- `03`의 출력 스키마가 `answer_message`, `summary`, `table`, `source_refs`, `warnings` 중심이라 답변 섹션 구조가 약하다.
- `04`는 `answer_type` 또는 `answer_sections`를 만들지 않는다.
- `05`는 항상 `답변`, `등록된 Query Template`, `관련 메타데이터`, `사용한 메타데이터`, `경고/오류` 형태라 질문 유형별 표현이 부족하다.
- SQL은 잘 분리되어 있지만, dataset 설명/필수 조건/용어 정의/공정 그룹/제품 조건/사용 예시 같은 현업용 구조가 약하다.
- Web/API에서 metadata QA를 카드/탭 형태로 표현할 구조가 부족하다.

## 3. 개선 원칙

1. 기존 Langflow output port 이름은 유지한다.
2. 신규 노드 추가보다 기존 `20`, `21`, `22`, `04`, `05`, `06` 확장을 우선한다.
3. LLM은 자연어 답변을 만들고, 표/적용 기준/근거 섹션은 deterministic builder가 만든다.
4. Chat Markdown과 API JSON이 같은 의미를 말하도록 `answer_sections`를 공통 계약으로 둔다.
5. 기본 답변에는 pandas code, raw trace, 전체 MongoDB context를 노출하지 않는다.
6. 개발자 진단이 필요한 경우 `include_diagnostics=true`에서만 intent/retrieval/pandas code를 보여준다.
7. metadata QA는 실제 생산량/재공수량을 계산하지 않고, 필요한 경우 data analysis route가 맞다고 안내한다.

## 4. Data Analysis Flow 개선 계획

### 4.1 `18_answer_variables_builder.py`

목표: LLM이 더 좋은 첫 문장을 쓰도록 필요한 요약 정보를 제공한다.

수정 방향:

- `answer_context_json`에 아래 항목을 추가한다.

```json
{
  "applied_criteria": {
    "required_params": {},
    "analysis_filters": {},
    "group_by": [],
    "metrics": [],
    "datasets": []
  },
  "result_interpretation_hints": {
    "is_empty_result": false,
    "has_zero_values": false,
    "primary_metric_columns": [],
    "primary_dimension_columns": []
  },
  "next_question_candidates": []
}
```

주의:

- LLM prompt output port는 추가하지 않는다.
- `answer_context_json` 내부만 확장해 기존 연결을 유지한다.

### 4.2 `19_answer_prompt_template_ko.md`

목표: LLM 답변은 본문 문장에 집중하게 한다.

수정 방향:

- "표는 직접 만들지 말고 핵심 해석만 작성" 규칙을 더 명확히 한다.
- "0과 데이터 없음은 구분" 규칙을 추가한다.
- "적용 기준은 answer_context_json.applied_criteria를 참고" 규칙을 추가한다.
- 제품 token/function case 관련 표현은 공통 prompt에 직접 쓰지 않고 `domain_answer_guidance` Text Input에만 둔다.

### 4.3 `20_answer_response_builder.py`

목표: `answer_sections`를 생성하는 중심 위치로 사용한다.

수정 방향:

- 기존 `answer_message` 저장은 유지한다.
- `next_payload["answer_sections"]`를 새로 만든다.
- `answer_sections`는 deterministic helper로 payload에서 구성한다.

권장 구조:

```json
{
  "summary": {
    "headline": "LLM answer_message",
    "basis": []
  },
  "result_table": {
    "columns": [],
    "rows": [],
    "display_rows": [],
    "row_count": 0,
    "preview_limit": 10
  },
  "applied_criteria": {
    "required_params": {},
    "analysis_filters": {},
    "retrieval_filters": {},
    "group_by": [],
    "metrics": [],
    "datasets": []
  },
  "evidence": {
    "datasets": [],
    "calculation_rules": [],
    "step_outputs": [],
    "function_case_results": []
  },
  "notices": [],
  "downloads": [],
  "next_questions": []
}
```

생성 기준:

- `result_table.rows`는 raw value를 유지한다.
- `result_table.display_rows`는 표시용 숫자 포맷을 적용한다.
- `required_params`는 `intent_plan.retrieval_jobs[*].required_params` 또는 `source_results[*].applied_params`에서 만든다.
- `analysis_filters`는 pandas filter/function case/groupby 조건에서 만든다.
- `datasets`는 `source_results`의 dataset/source alias를 기준으로 만든다.
- `step_outputs`, `function_case_results`는 compact preview만 넣는다.
- `notices`에는 dummy data 여부, row 없음, warnings/errors 요약을 넣는다.

### 4.4 `21_answer_message_adapter.py`

목표: Chat/Playground 메시지는 `answer_sections`를 우선 사용한다.

수정 방향:

- `answer_sections`가 있으면 그 구조를 기준으로 markdown을 만든다.
- 없으면 현재 fallback 로직을 유지한다.
- 기본 섹션 순서를 아래로 변경한다.

```text
### 답변
### 결과
### 적용 기준
### 분석 과정 요약
### 제품/조건 매핑 결과
### 데이터 다운로드
### 참고
```

개발자 모드:

- `include_diagnostics=true`일 때만 기존 `의도 분석`, `데이터 조회`, `pandas 코드/실행` 섹션을 추가한다.

주의:

- `function_name=match_product_tokens` 같은 내부 helper 이름을 기본 메시지에 직접 강조하지 않는다.
- 사용자가 입력한 제품 표현과 매핑된 제품 조건/row를 보여주는 방식으로 표현한다.

### 4.5 `22_api_response_builder.py`

목표: Web/API가 Chat Markdown을 파싱하지 않고 구조화 응답을 읽게 한다.

수정 방향:

- API 응답에 `answer_sections`를 추가한다.
- 기존 `message`, `answer_message`, `display_message`, `data`, `analysis`, `trace`는 호환을 위해 유지한다.
- runtime source rows 제거 정책은 유지한다.

### 4.6 Data Analysis 검증

추가 테스트:

- `20_answer_response_builder`가 `answer_sections`를 만든다.
- `21_answer_message_adapter`가 `answer_sections` 기준으로 `답변/결과/적용 기준`을 표시한다.
- `include_diagnostics=false`에서는 pandas code가 나오지 않는다.
- `include_diagnostics=true`에서는 pandas code가 나온다.
- 숫자 10,000 이상은 표시용 섹션에서 K 단위로 보이고 raw `data.rows`는 원값을 유지한다.
- `row_count=0`은 "결과 행 없음"으로 표시하고, metric 값 0은 "0"으로 표시한다.
- 제품 token/function case 결과가 있으면 매핑 결과 섹션에 표시된다.

## 5. Metadata QA Flow 개선 계획

### 5.1 `02_metadata_qa_context_builder.py`

목표: 현업 질문 유형을 더 정확히 분류한다.

현재 `answer_mode`를 아래처럼 확장한다.

| 신규/개선 answer_mode | 예시 질문 | 답변 목적 |
| --- | --- | --- |
| `available_sources` | 지금 조회 가능한 데이터가 뭐야? | 데이터 목록과 필수 조건 |
| `dataset_detail` | production_today는 뭐야? | 특정 데이터셋 설명 |
| `required_params` | production 조회할 때 필수 조건은 뭐야? | 필수 파라미터/형식 |
| `dataset_sql` | 생산량 데이터 쿼리 보여줘 | query_template |
| `term_definition` | 생산량은 어떤 컬럼이야? | 도메인 용어 정의 |
| `process_group` | DA공정에는 뭐가 포함돼? | 공정 그룹/세부 공정 |
| `product_condition` | HBM 제품 조건은 뭐야? | 제품군 조건 |
| `product_token_rule` | RG 32G DDR4 FBGA 96 DDP는 어떻게 찾는 거야? | 제품 token 해석 규칙 |
| `calculation_logic_list` | 등록된 계산 로직 보여줘 | 계산/분석 recipe 목록 |
| `question_to_dataset` | 이 질문은 어떤 데이터로 답해? | 질문에 필요한 데이터/조건 안내 |
| `data_analysis_redirect` | 오늘 DA공정 생산량 값 알려줘 | 실제 데이터 분석 route 안내 |
| `general_metadata_search` | 기타 | 관련 메타데이터 후보 |

수정 방향:

- `_infer_answer_mode` keyword rule을 확장한다.
- `_candidate_rows`를 answer_mode별로 다르게 만든다.
- dataset detail에는 `display_name`, `dataset_family`, `source_type`, `db_key`, `required_params`, `quantity columns`, `filter_mappings` 요약을 넣는다.
- process group에는 `aliases`, `processes` 또는 관련 payload를 사람이 읽기 좋은 row로 만든다.
- product condition에는 조건식을 사람이 읽기 좋은 row로 만든다.
- 실제 수량을 물은 질문은 metadata QA가 계산하지 않도록 `data_analysis_redirect`로 분류한다.

### 5.2 `03_metadata_qa_variables_builder.py`

목표: LLM 출력 스키마를 섹션형으로 확장한다.

수정 방향:

- output port는 유지한다.
- `_output_schema()`를 아래 구조로 확장한다.

```json
{
  "answer_type": "string",
  "answer_message": "string",
  "answer_sections": {
    "summary": {},
    "detail_table": {},
    "sql_blocks": [],
    "usage_examples": [],
    "related_items": [],
    "route_hint": {},
    "warnings": []
  },
  "source_refs": []
}
```

주의:

- `response_policy` 같은 별도 output은 만들지 않는다.
- Prompt Template 변수는 계속 `question`, `metadata_context_json`, `output_schema_json` 3개만 유지한다.

### 5.3 `03_metadata_qa_prompt_template_ko.md`

목표: 답변 유형별 작성 규칙을 명시한다.

수정 방향:

- 먼저 `answer_type`을 고르게 한다.
- 실제 수량 조회 질문이면 계산하지 말고 `data_analysis_redirect` 안내를 반환하게 한다.
- SQL은 사용자가 명시적으로 쿼리/SQL을 물은 경우에만 넣게 한다.
- table은 질문 유형에 맞는 이름과 컬럼을 사용하게 한다.
- raw_trace/raw_text/credential/전체 dump 금지 규칙은 유지한다.

### 5.4 `04_metadata_qa_response_normalizer.py`

목표: LLM 응답이 불안정해도 항상 현업용 섹션 구조를 만든다.

수정 방향:

- parsed 응답에서 `answer_type`, `answer_sections`를 읽는다.
- 없으면 context의 `answer_mode` 기준으로 fallback `answer_sections`를 만든다.
- 기존 `metadata_qa.summary`, `metadata_qa.items`, `metadata_qa.sql_blocks`, `data`는 호환 유지한다.
- 새 필드를 추가한다.

```json
{
  "answer_type": "dataset_detail",
  "answer_sections": {},
  "metadata_qa": {
    "answer_mode": "dataset_detail",
    "source_refs": [],
    "sql_blocks": []
  }
}
```

### 5.5 `05_metadata_qa_message_adapter.py`

목표: 질문 유형별로 읽기 쉬운 markdown을 만든다.

수정 방향:

- `answer_sections`가 있으면 우선 사용한다.
- 없으면 현재 로직을 fallback으로 유지한다.
- 기존 `### 관련 메타데이터` 단일 표 제목을 answer_type별 제목으로 바꾼다.

권장 섹션:

```text
### 답변
### 등록 정보 / 데이터 목록 / 용어 정의 / 공정 그룹 / 제품 조건
### Query Template
### 사용 예시
### 관련 메타데이터
### 참고
```

표 제목 예:

- `available_sources`: `### 조회 가능한 데이터`
- `dataset_detail`: `### 데이터셋 등록 정보`
- `required_params`: `### 필수 조회 조건`
- `term_definition`: `### 등록된 용어 정의`
- `process_group`: `### 공정 그룹`
- `product_condition`: `### 제품 조건`
- `calculation_logic_list`: `### 계산/분석 로직`

### 5.6 `06_metadata_qa_api_response_builder.py`

목표: Web/API에서 metadata QA를 카드/탭 형태로 표현할 수 있게 한다.

수정 방향:

- API 응답에 `answer_type`과 `answer_sections`를 추가한다.
- 기존 `response_type=metadata_qa`, `direct_response_ready=true`는 유지한다.
- `metadata_qa_context` 제거 정책은 유지한다.

### 5.7 Metadata QA 검증

추가 테스트 질문:

- 지금 조회 가능한 데이터가 뭐야?
- production_today는 뭐야?
- production 조회할 때 필수 조건은 뭐야?
- 생산량은 어떤 컬럼으로 계산해?
- DA공정에는 어떤 세부 공정이 있어?
- HBM 제품 조건은 뭐야?
- 생산량 데이터 관련 쿼리문은 뭐야?
- 어제 Mobile제품의 PKG OUT실적은 어떤 데이터로 답해?
- 오늘 DA공정 생산량 알려줘

검증 기준:

- metadata QA는 실제 생산량 값을 계산하지 않는다.
- query_template은 SQL 질문일 때만 노출한다.
- `raw_trace`, `raw_text`, `registration_trace`, credential성 key가 API/message에 나오지 않는다.
- `answer_type`과 `answer_sections`가 API 응답에 포함된다.
- Chat message는 질문 유형별 제목을 사용한다.

## 6. 구현 순서

### Phase 1. Data Analysis 구조화

1. `20_answer_response_builder.py`에 `answer_sections` builder 추가
2. `21_answer_message_adapter.py`가 `answer_sections`를 우선 사용하도록 수정
3. `22_api_response_builder.py`에 `answer_sections` 포함
4. data analysis 단위 테스트 추가
5. 대표 질문 2~3개로 메시지 형태 확인

### Phase 2. Metadata QA answer_type/sections

1. `02_metadata_qa_context_builder.py`의 answer mode 확장
2. `03_metadata_qa_variables_builder.py`의 output schema 확장
3. `03_metadata_qa_prompt_template_ko.md`의 유형별 작성 규칙 보강
4. `04_metadata_qa_response_normalizer.py`의 fallback sections 추가
5. `05_metadata_qa_message_adapter.py`의 유형별 message rendering 추가
6. `06_metadata_qa_api_response_builder.py`에 answer_type/sections 포함
7. metadata QA 질문셋 테스트 추가

### Phase 3. Web/API 연동 점검

1. `web_app/langflow_client.py`가 `answer_sections`를 보존하는지 확인
2. Web 기본 화면은 `display_message`를 그대로 사용하되, 추후 카드 UI에서는 `answer_sections`를 읽을 수 있게 한다
3. 개발자 모드의 pandas 진단 표시가 기존처럼 유지되는지 확인

### Phase 4. 회귀 검증

1. `python -m pytest -q`
2. 대표 data analysis 질문셋 중 단순 집계, 제품 token, 단계형 분석 각 1개 이상 확인
3. metadata QA 질문셋 확인
4. `git diff --check`

## 7. 예상 리스크와 대응

| 리스크 | 대응 |
| --- | --- |
| 답변이 너무 길어짐 | 기본 섹션은 답변/결과/적용 기준까지만 우선 표시하고 나머지는 필요할 때만 |
| LLM이 표를 직접 만들어 중복 표가 생김 | `19` prompt에서 표 생성 금지 강화, `21`에서 markdown table 감지 시 중복 방지 유지 |
| metadata QA가 실제 수량 질문에 답하려 함 | `data_analysis_redirect` answer_type 추가 |
| answer_sections와 기존 data/message가 서로 다른 내용이 됨 | `20`과 `04`에서 deterministic하게 sections 생성 |
| Web 파서가 새 필드를 무시 | 기존 필드는 유지하고 새 필드는 추가만 함 |
| 특정 제조 helper가 공통 prompt에 들어감 | 제품 token/특화 설명은 `domain_answer_guidance` 또는 metadata에만 둠 |

## 8. 최종 권장 방향

Data analysis는 기존 구조가 이미 절반 정도 준비되어 있으므로 `20/21/22` 중심의 확장이 가장 효율적이다. 새 노드를 늘리기보다 `answer_sections`를 payload 내부 계약으로 추가하는 방식이 좋다.

Metadata QA는 현재 후보 검색과 fallback은 잘 되어 있지만 답변 유형 구분이 약하다. `answer_mode`를 현업 질문 유형 기준으로 확장하고, `answer_type + answer_sections`를 표준화하는 것이 가장 큰 개선 포인트다.

두 flow 모두 최종적으로는 아래 원칙을 공유해야 한다.

```text
LLM = 자연어 답변 문장
deterministic builder = 표, 적용 기준, 근거, 다운로드, 경고
message adapter = 현업용 markdown
api builder = Web/API용 구조화 JSON
```
