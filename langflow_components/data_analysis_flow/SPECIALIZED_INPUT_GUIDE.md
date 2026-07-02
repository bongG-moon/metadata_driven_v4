# 데이터 분석 flow 특화 입력 가이드

이 파일은 Langflow에서 특화 프롬프트와 특화 함수 값을 어디에 넣어야 하는지 설명한다.

## 1. 공정 특화 프롬프트 입력 위치

공정/현장별로 임시로 강조해야 하는 해석 규칙이 있으면 아래 위치에 자연어로 입력한다.

바로 복사해서 테스트할 수 있는 값은 `specialized_prompt_input_example_ko.md`에 있다.

| 목적 | 입력 노드 | 입력 포트 | 연결 대상 |
| --- | --- | --- | --- |
| 의도 분석 LLM에 추가 지시 전달 | `02 의도 분석 변수 생성기` | `공정 특화 프롬프트` (`specialized_prompt_text`) | `02.specialized_prompt` -> `03 의도 분석 Prompt Template.specialized_prompt` |

입력하지 않아도 된다. 비워두면 기본 metadata와 공통 prompt만 사용한다.

### 입력 예시

```text
W/B, WB, Wire Bond는 같은 공정 그룹으로 해석한다.
아침재공/BOH는 별도 실시간 snapshot이 없으면 전일 WIP 데이터 기준으로 집계한다.
PKG OUT은 제품별 생산실적 중 PKG 완료 조건을 우선 확인하고, metadata에 정의된 조건이 있으면 그 조건을 따른다.
```

주의사항:

- JSON을 넣을 필요가 없다.
- data catalog의 필수 파라미터를 바꾸는 용도로 쓰지 않는다.
- 특정 질문 하나만 맞추기 위한 과도한 fallback 규칙은 넣지 않는다.
- metadata와 충돌하면 metadata를 우선한다.

## 2. 특화 함수 값은 어디에 넣는가

특화 함수는 Langflow 화면에서 pandas 코드 생성 노드에 직접 입력하는 값이 아니다.

정상 흐름은 아래 순서다.

1. `domain_knowledge.txt` 또는 domain authoring flow를 통해 `pandas_function_cases` metadata를 등록한다.
2. `01a MongoDB 도메인 메타데이터 로더`가 해당 metadata를 읽는다.
3. `01d 메타데이터 후보 생성기`가 의도 분석 LLM에 후보로 전달한다.
4. `03 의도 분석 Prompt Template`이 필요한 경우 `intent_plan.pandas_function_case`를 출력하게 한다.
5. `04 의도 계획 정규화기`가 `pandas_execution_plan` 첫 단계에 `apply_pandas_function_case`를 보강한다.
6. `15 pandas 변수 생성기`가 선택된 함수만 `function_case_context_json`으로 pandas Prompt Template에 전달한다.
7. `17 pandas 코드 실행기`가 실제 helper를 제공하고, 실행 trace에 helper 포함 실행 코드를 남긴다.

## 3. 현재 지원하는 특화 함수

현재 executor에서 제공하는 helper는 아래 2개다.

```text
function_name: match_product_tokens
signature: match_product_tokens(input_text, frame, token_columns=None, output_order=None)
```

용도:

- `RG 32G DDR4 FBGA 96 DDP`
- `SP 16G DDR5 2ND X4 78 FCBGA SDP`
- `DA 16G GDDR6 180`

처럼 제품 속성이 여러 컬럼에 나뉘어 있고, 사용자가 한 문장 token으로 제품을 말하는 경우에 사용한다.

```text
function_name: sample_passthrough_helper
signature: sample_passthrough_helper(input_text, frame, note=None)
```

용도:

- 여러 `pandas_function_cases`가 동시에 선택될 때 `function_case_context_json.available_helpers` 형식을 확인하기 위한 더미 helper다.
- DataFrame을 변경하지 않고 copy를 반환한다.
- 실제 운영 분석에서는 metadata가 명시적으로 선택한 경우에만 사용한다.

Domain Authoring Flow에 넣을 raw text 예시는 `../domain_authoring_flow/pandas_function_cases_raw_text_input_example.md`에 있다.

## 4. 의도 분석 LLM이 출력해야 하는 형태

특화 함수가 필요하다고 판단되면 의도 분석 LLM 응답에 아래 값을 포함해야 한다.

```json
{
  "intent_plan": {
    "pandas_function_case": {
      "key": "product_token_match",
      "function_name": "match_product_tokens",
      "input_text": "RG 32G DDR4 FBGA 96 DDP"
    },
    "pandas_execution_plan": [
      {
        "step": "특화 함수 적용",
        "operation": "apply_pandas_function_case",
        "function_case_key": "product_token_match",
        "function_name": "match_product_tokens",
        "input_text": "RG 32G DDR4 FBGA 96 DDP",
        "source_alias": "production_data"
      }
    ]
  }
}
```

`source_alias`가 여러 개면 각 source에 대해 같은 `input_text`를 적용하도록 단계가 여러 개 생길 수 있다.

특화 함수가 여러 개 필요하면 `pandas_function_cases` 배열을 사용한다.

```json
{
  "intent_plan": {
    "pandas_function_cases": [
      {
        "key": "product_token_match",
        "function_name": "match_product_tokens",
        "input_text": "RG 32G DDR4 FBGA 96 DDP",
        "source_alias": "production_data"
      },
      {
        "key": "sample_passthrough_demo",
        "function_name": "sample_passthrough_helper",
        "input_text": "format demo",
        "source_alias": "production_data"
      }
    ]
  }
}
```

## 5. pandas Prompt Template에서 사용하는 값

`15 pandas 변수 생성기.function_case_context_json`을 `16 pandas Prompt Template.function_case_context_json`에 연결한다.

pandas LLM은 이 값 안의 `available_helpers`에 `match_product_tokens`가 있을 때만 아래처럼 helper를 호출한다.

```python
df = match_product_tokens("RG 32G DDR4 FBGA 96 DDP", sources["production_data"])
```

helper 구현은 LLM이 생성하지 않는다. executor가 제공한다. 다만 `21 답변 메시지 어댑터`는 검증을 위해 helper 구현과 실제 실행 pandas 코드를 함께 표시한다.
