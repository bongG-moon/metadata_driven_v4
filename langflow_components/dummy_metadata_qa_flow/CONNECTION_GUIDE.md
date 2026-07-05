# Dummy Metadata QA Flow 연결 가이드

이 flow는 실제 MongoDB metadata 조회 없이 router/Web 계약을 빠르게 검증하기 위한 개발용 flow다.
실제 `metadata_qa_flow`와 같은 `response_type=metadata_qa`, `answer_sections`, `metadata_qa.items`, `data.rows`, `source_refs`, markdown `message` 형태를 반환한다.

| 순서 | From | To |
| --- | --- | --- |
| 1 | `Chat Input.message` | `00 더미 메타데이터 QA 요청 로더.사용자 질문` |
| 2 | `00 더미 메타데이터 QA 요청 로더.페이로드 출력` | `01 더미 메타데이터 QA 응답 생성기.페이로드` |
| 3 | `01 더미 메타데이터 QA 응답 생성기.메시지` | `Chat Output.input` |

Web/API에서 사용할 때는 `01 더미 메타데이터 QA 응답 생성기.API 응답`도 Langflow API output으로 노출한다.

## 표시 메시지 섹션

`01 더미 메타데이터 QA 응답 생성기.메시지`는 실제 Metadata QA 답변처럼 아래 섹션을 우선 포함한다.

```text
### 답변
### 한눈에 보기
### 조회 가능한 데이터 / 계산/분석 로직 / 등록된 용어 정의 등 상세 표
### 등록된 Query Template
### 다음에 물어볼 수 있는 질문
### 사용한 메타데이터
### 참고
```

상세 표 제목과 SQL 섹션은 질문 유형에 따라 달라지거나 생략될 수 있다.

## 더미 응답 fixture

질문에 포함된 단어에 따라 아래 유형의 더미 답변을 반환한다.

| 질문 단서 | 응답 유형 |
| --- | --- |
| `쿼리`, `SQL`, `query` | 생산량 데이터셋 query_template 예시 |
| `계산`, `로직`, `함수` | 계산/특화 함수 metadata list 예시 |
| `POP` | POP 제품 도메인 조건 예시 |
| `조회 가능`, `연결`, `필수`, `등록된 데이터셋`, `데이터셋 목록` | 조회 가능한 dataset 목록 예시 |
| 그 외 | 생산량 domain metadata 예시 |

이 flow는 MongoDB를 조회하지 않고, metadata를 저장하지도 않는다.
