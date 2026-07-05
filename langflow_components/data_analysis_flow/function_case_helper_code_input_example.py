def match_product_tokens(input_text, frame, token_columns=None, output_order=None):
    # 원본 DataFrame을 변경하지 않기 위해 copy본에서 필터링을 수행한다.
    result = frame.copy()
    if result.empty:
        return result

    # 비교 안정성을 위해 값에서 영문/숫자만 남기고 대문자로 정규화한다.
    def _norm(value):
        text = str('' if value is None else value).strip().upper()
        if '.' in text:
            left, right = text.split('.', 1)
            if left.lstrip('-').isdigit() and right and all(ch == '0' for ch in right):
                text = left
        return ''.join(ch for ch in text if ('A' <= ch <= 'Z') or ('0' <= ch <= '9'))

    # 컬럼명은 PKG_TYPE1, MCP NO처럼 표기 차이가 있어도 같은 key로 비교한다.
    def _col_key(value):
        text = str(value).upper()
        chars = []
        prev_sep = False
        for ch in text:
            if ('A' <= ch <= 'Z') or ('0' <= ch <= '9'):
                chars.append(ch)
                prev_sep = False
            elif not prev_sep:
                chars.append('_')
                prev_sep = True
        return ''.join(chars).strip('_')

    # 사용자 입력 문장에서 제품 식별에 필요한 token만 추출한다.
    # 공정/수량/일자처럼 제품 속성이 아닌 흔한 단어는 stopwords로 제거한다.
    def _tokens(value):
        stopwords = {'PRODUCT', 'DEVICE', 'PKG', 'WIP', 'INPUT', 'OUTPUT', 'OUT', 'PRODUCTION', 'TODAY', 'YESTERDAY', 'WB', 'FCB', 'BG', 'SBM'}
        raw_items = []
        current = ''
        for ch in str(value or '').upper():
            if ('A' <= ch <= 'Z') or ('0' <= ch <= '9') or ch in '-_/':
                current += ch
            else:
                if current:
                    raw_items.append(current)
                    current = ''
        if current:
            raw_items.append(current)
        result_tokens = []
        for item in raw_items:
            cleaned = item.strip('-_/')
            if cleaned and cleaned not in stopwords and cleaned not in result_tokens:
                result_tokens.append(cleaned)
        return result_tokens

    # 표준 제품 속성 역할과 실제 데이터 컬럼 alias를 연결한다.
    role_aliases = {
        'TECH': {'TECH'},
        'DEN': {'DEN', 'DENSITY'},
        'MODE': {'MODE'},
        'PKG1': {'PKG_TYPE1', 'PKG1', 'PKG_TYP1'},
        'PKG2': {'PKG_TYPE2', 'PKG2', 'PKG_TYP2'},
        'LEAD': {'LEAD'},
        'MCP_NO': {'MCP_NO', 'MCPNO', 'MCP_SALES_NO', 'MCP_SALE_CD', 'MCPSALENO'},
        'DEVICE': {'DEVICE'},
        'DEVICE_DESC': {'DEVICE_DESC'},
        'TSV_DIE_TYP': {'TSV_DIE_TYP', 'TSV_DIE_TYPE'},
        'ORG': {'ORG', 'ORGANIZ_CD'},
        'FAMILY': {'FAMILY'},
    }

    # token_columns가 주어지면 해당 컬럼만 사용하고, 없으면 알려진 제품 속성 컬럼만 자동 선택한다.
    requested = token_columns if token_columns not in (None, '', [], {}) else []
    if requested and not isinstance(requested, (list, tuple, set)):
        requested = [requested]
    known_aliases = {alias for aliases in role_aliases.values() for alias in aliases}
    columns = [str(column) for column in requested if str(column) in result.columns] if requested else [str(column) for column in result.columns if _col_key(column) in known_aliases]
    groups = [_tokens(part) for part in str(input_text or '').split(',')]
    groups = [group for group in groups if group]
    if not columns or not groups:
        return result

    # 컬럼별 값을 미리 정규화해 token 매칭을 반복해도 같은 전처리를 다시 하지 않게 한다.
    normalized_values = {column: result[column].map(_norm) for column in columns}
    columns_by_role = {role: [] for role in role_aliases}
    columns_by_role['ALL'] = list(columns)
    alias_to_role = {alias: role for role, aliases in role_aliases.items() for alias in aliases}
    for column in columns:
        role = alias_to_role.get(_col_key(column))
        if role:
            columns_by_role[role].append(column)

    def _has_rows(mask):
        return mask is not None and bool(mask.any())

    # 지정한 역할군의 컬럼들에서 token을 exact 또는 prefix 방식으로 찾는다.
    def _match(roles, token, mode):
        selected_columns = []
        for role in roles:
            for column in columns_by_role.get(role, []):
                if column not in selected_columns:
                    selected_columns.append(column)
        combined = None
        for column in selected_columns:
            values = normalized_values[column]
            if mode == 'exact':
                current = values == token
            elif mode == 'contains':
                current = values.str.contains(token, na=False, regex=False)
            elif mode == 'starts_with':
                current = values.str.startswith(token, na=False)
            else:
                current = values == token
            combined = current if combined is None else (combined | current)
        return combined

    # token 하나를 DataFrame mask로 변환한다.
    # 특수 규칙은 여기서 처리한다.
    def _token_mask(raw_token):
        raw_text = str(raw_token or '').strip().upper()
        token = _norm(raw_text)
        if not token:
            return None

        # FC+숫자: PKG1은 FCBGA이고 LEAD는 숫자 부분이다. 예: FC12, FC78, FC344.
        if token.startswith('FC') and token[2:].isdigit():
            pkg_mask = _match(['PKG1'], 'FCBGA', 'exact')
            lead_mask = _match(['LEAD'], token[2:], 'exact')
            return None if pkg_mask is None or lead_mask is None else (pkg_mask & lead_mask)

        # F+숫자: FCBGA/VFBGA/UFBGA 등 package 종류를 특정하지 않고 LEAD만 적용한다. 예: F12, F78, F344.
        if token.startswith('F') and token[1:].isdigit():
            return _match(['LEAD'], token[1:], 'exact')

        # 영문 1자리-숫자3자리(+선택 영숫자) 패턴: MCP_NO 앞부분 입력으로 보고 prefix 조건으로 매칭한다. 예: L-218, B-123, Z-000.
        if _looks_mcp_no_prefix(raw_text):
            return _match(['MCP_NO'], token, 'starts_with')

        # X+숫자: 우선 ORG 컬럼에서 x를 제거한 숫자로 매칭한다. 예: x8, X16, x24.
        if token.startswith('X') and token[1:].isdigit():
            return _match(['ORG'], token[1:], 'exact')

        # token 모양으로 컬럼 역할을 먼저 제한하지 않고, 모든 구조화 제품 후보 속성 컬럼에서 exact 매칭한다.
        # DEVICE_DESC는 자유 텍스트 설명 컬럼이므로 token 포함 여부를 보조적으로 확인한다.
        matched = _match(['ALL'], token, 'exact')
        desc_matched = _match(['DEVICE_DESC'], token, 'contains')
        if matched is None:
            matched = desc_matched
        elif desc_matched is not None:
            matched = matched | desc_matched
        return matched if _has_rows(matched) else None

    def _looks_mcp_no_prefix(value):
        text = str(value or '').strip().upper()
        if '-' not in text:
            return False
        prefix, suffix = text.split('-', 1)
        if len(prefix) != 1 or not ('A' <= prefix <= 'Z'):
            return False
        if len(suffix) < 3 or not suffix[:3].isdigit():
            return False
        return all(('A' <= ch <= 'Z') or ('0' <= ch <= '9') for ch in suffix[3:])

    # 콤마로 나뉜 제품 묶음은 OR로 결합하고, 한 제품 안의 token들은 AND로 결합한다.
    final_mask = None
    for group in groups:
        group_mask = None
        group_failed = False
        for token in group:
            current = _token_mask(token)
            if current is None:
                group_failed = True
                break
            group_mask = current if group_mask is None else (group_mask & current)
        if (group_failed or group_mask is None) and group:
            group_mask = result.index.to_series().map(lambda _: False)
        if group_mask is not None:
            final_mask = group_mask if final_mask is None else (final_mask | group_mask)

    filtered = result if final_mask is None else result[final_mask].copy()

    # 필요하면 결과 컬럼 순서를 호출자가 지정한 순서로 정리한다.
    ordered_columns = output_order if output_order not in (None, '', [], {}) else []
    if ordered_columns and not isinstance(ordered_columns, (list, tuple, set)):
        ordered_columns = [ordered_columns]
    ordered_columns = [column for column in ordered_columns if column in filtered.columns]
    if ordered_columns:
        rest = [column for column in filtered.columns if column not in ordered_columns]
        filtered = filtered[ordered_columns + rest]
    try:
        record_function_case_result('match_product_tokens', input_text, filtered, '제품 속성 token 매칭 결과')
    except Exception:
        pass
    return filtered

def sample_passthrough_helper(input_text, frame, note=None):
    # 여러 helper를 동시에 넣는 형식을 검증하기 위한 더미 helper다.
    # 실제 분석 로직은 수행하지 않고 DataFrame copy만 반환한다.
    result = frame.copy()
    try:
        record_function_case_result('sample_passthrough_helper', input_text, result, str(note or '더미 helper 통과 결과'))
    except Exception:
        pass
    return result
