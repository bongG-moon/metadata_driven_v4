# Dummy Table Catalog Authoring Flow 연결 가이드

실제 MongoDB 저장 없이 table catalog authoring 응답 계약을 검증하는 개발용 flow다.

| 순서 | From | To |
| --- | --- | --- |
| 1 | `Chat Input.message` | `00 더미 테이블 카탈로그 등록 요청 로더.원문 텍스트` |
| 2 | `00 더미 테이블 카탈로그 등록 요청 로더.페이로드 출력` | `01 더미 테이블 카탈로그 등록 응답 생성기.페이로드` |
| 3 | `01 더미 테이블 카탈로그 등록 응답 생성기.메시지` | `Chat Output.input` |

Web/API에서 사용할 때는 `01 더미 테이블 카탈로그 등록 응답 생성기.API 응답`도 Langflow API output으로 노출한다.
