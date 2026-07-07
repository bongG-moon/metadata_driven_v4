# Dummy Data Analysis Flow 연결 가이드

이 flow는 실제 분석 품질 검증용이 아니라 router, Web parser, session, 다운로드 링크 등 외부 계약을 빠르게 확인하기 위한 개발용 flow다.
다만 Playground에서 실제 `data_analysis_flow` 응답과 비슷하게 보이도록 `answer_sections` 기반의 서비스형 답변, 결과 테이블, 적용 기준, 중간 분석 산출물, helper 실행 결과를 포함한다.

## 노드 연결

| 순서 | From | To |
| --- | --- | --- |
| 1 | `Chat Input.message` | `00 더미 분석 요청 로더.사용자 질문` |
| 2 | `00 더미 분석 요청 로더.페이로드 출력` | `01 더미 분석 응답 생성기.페이로드` |
| 3 | `01 더미 분석 응답 생성기.메시지` | `Chat Output.input` |

API 응답을 확인해야 하는 canvas에서는 `01 더미 분석 응답 생성기.API 응답`도 Langflow API output으로 노출한다.

## 출력 계약

`01 더미 분석 응답 생성기.API 응답`은 실제 `data_analysis_flow`의 최종 응답과 같은 기본 형태를 가진다.

- `response_type=data_analysis`
- `status=ok`
- `answer_message`: 순수 답변 문장
- `message`, `display_message`: Playground/Web 표시용 markdown
- `answer_sections.summary`
- `answer_sections.result_table`
- `answer_sections.applied_criteria`
- `answer_sections.evidence`
- `answer_sections.notices`
- `answer_sections.next_questions`
- `request`
- `metadata_refs`
- `intent_plan.retrieval_jobs`
- `intent_plan.pandas_execution_plan`
- `source_results`
- `analysis.analysis_code`
- `analysis.step_outputs`
- `analysis.function_case_results`
- `data.rows`, `data.columns`, `data.row_count`
- `trace.inspection.intent`
- `trace.inspection.data_retrieval`
- `trace.inspection.pandas_execution`

## 표시 메시지 섹션

`01 더미 분석 응답 생성기.메시지`는 아래 섹션을 포함한다.

```text
### 답변
### 결과 테이블
### 적용 기준
### 중간 분석 산출물
### helper 실행 결과
### 참고
### 다음에 볼 만한 질문
```

제품 token 매칭이 필요 없는 더미 질문에서는 `helper 실행 결과`의 helper 매칭 상세가 생략될 수 있다.
의도 분석, 데이터 조회, pandas 코드는 채팅 메시지 본문에 직접 붙이지 않고 `intent_plan`, `source_results`, `analysis.analysis_code`, `trace.inspection`에 남긴다.

## 더미 시나리오

질문에 포함된 단어에 따라 아래 fixture를 반환한다.

| 질문 단서 | 응답 시나리오 |
| --- | --- |
| `RG 32G`, `BG공정`, `BG 공정` | 제품 token 매칭 후 BG공정 생산량/재공수량 집계 |
| `L-218`, `SBM` | 전일 L-218K8H 제품 SBM공정 생산 실적 집계 |
| 그 외 | D/A 공정 생산량 상위 제품 예시 |
