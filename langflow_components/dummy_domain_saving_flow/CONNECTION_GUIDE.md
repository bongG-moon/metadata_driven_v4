# Dummy Domain Saving Flow 연결 가이드

실제 MongoDB 저장 없이 domain saving 응답 계약을 검증하는 개발용 flow다.

| 순서 | From | To |
| --- | --- | --- |
| 1 | `Chat Input.message` | `00 더미 도메인 등록 요청 로더.원문 텍스트` |
| 2 | `00 더미 도메인 등록 요청 로더.페이로드 출력` | `01 더미 도메인 등록 응답 생성기.페이로드` |
| 3 | `01 더미 도메인 등록 응답 생성기.메시지` | `Chat Output.input` |

Web/API에서 사용할 때는 `01 더미 도메인 등록 응답 생성기.API 응답`도 Langflow API output으로 노출한다.

## 출력 계약

`01 더미 도메인 등록 응답 생성기.API 응답`은 실제 domain saving flow의 최종 응답과 같은 기본 형태를 가진다.

- `response_type=metadata_authoring`
- `metadata_type=domain`
- `status=dry_run`
- `direct_response_ready=true`
- `answer_message`
- `message`, `display_message`
- `answer_sections.summary`
- `answer_sections.key_points`
- `answer_sections.target_table`
- `answer_sections.notices`
- `answer_sections.next_steps`
- `data.rows`, `data.columns`, `data.row_count`
- `metadata_authoring`
- `write_result`

## 표시 메시지 섹션

```text
### 등록 결과
### 한눈에 보기
### 등록 대상 도메인
### 확인할 점
### 다음 단계
```
