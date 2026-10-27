"""Wire format for function return values; no prose or quiz answers."""
from importlib.resources import files
import json
import math
from .models import InvalidSubmission, LIMITS
from .problem_sets import DEFAULT_PROBLEM_SET

ORDER = DEFAULT_PROBLEM_SET.order
OPTIONAL = DEFAULT_PROBLEM_SET.optional
REQUIRED = DEFAULT_PROBLEM_SET.required
VERSION = DEFAULT_PROBLEM_SET.notebook_version
CONTRACT = DEFAULT_PROBLEM_SET.contract
QISKIT_VERSION = "2.3.1"
QPY_VERSION = 17
PARTIES = ("Alice", "Bob", "Charlie")
STATES = ("0", "1", "+", "-")
BELLS = ("Phi+", "Phi-", "Psi+", "Psi-")
GENERAL = ("h", "x", "z", "cx")
LOCAL = ("h", "x", "z")
GAME_LOCAL = ("h", "s", "sdg", "x", "z")
def circuit(nq, nc=0, gates=GENERAL, conditional=False):
    return (nq, nc, gates, conditional)
CIRCUITS = {
    "1-1": {"circuit": circuit(1)},
    "1-2": {"circuit": circuit(1)},
    "1-3": {"by_initial": {s: circuit(1) for s in STATES}},
    "1-4": {"basis": circuit(1, gates=LOCAL)},
    "1-5": {"by_target": {s: circuit(2) for s in BELLS}},
    "1-6": {"ghz": circuit(3), "coin": circuit(4), "basis": circuit(3, gates=LOCAL)},
    "2-1": {},
    "2-2": {"pair": circuit(2), "alice": circuit(2), "bob": circuit(1, 2, LOCAL, True)},
    "2-3": {},
    "2-4": {"bell_from_b_plus": circuit(2), "bob_graph": circuit(1, 2, LOCAL, True)},
    "3-1": {},
    "3-2": {"resource": circuit(3), "local_bases": {
        p: {str(bit): circuit(1, gates=GAME_LOCAL) for bit in (0, 1)} for p in PARTIES}},
    "3-3": {}, "3-4": {},
    "2-5": {"pair4": circuit(4), "bob2": circuit(2, 4, LOCAL, True)},
    "3-5": {},
}

def schema_issues(value, spec, path):
    if isinstance(spec, dict):
        if "$enum" in spec:
            return [] if type(value) is str and value in spec["$enum"] else [f"{path}: 허용 문자열이 필요합니다."]
        if "$list" in spec:
            rule = spec["$list"]
            if type(value) is not list:
                return [f"{path}: list가 필요합니다."]
            if rule["length"] is not None and len(value) != rule["length"]:
                return [f"{path}: list 길이가 맞지 않습니다."]
            return [issue for i, v in enumerate(value)
                    for issue in schema_issues(v, rule["item"], f"{path}[{i}]")]
        if type(value) is not dict:
            return [f"{path}: dict가 필요합니다."]
        issues = [f"{path}.{k}: 필드가 없습니다." for k in spec if k not in value]
        issues += [f"{path}: 정의되지 않은 필드가 있습니다." for k in value if k not in spec]
        for key in spec.keys() & value.keys():
            issues.extend(schema_issues(value[key], spec[key], f"{path}.{key}"))
        return sorted(set(issues))
    if spec == "bool":
        valid = type(value) is bool
    elif spec == "integer":
        valid = type(value) is int
    elif spec == "number":
        try:
            valid = type(value) in (int, float) and math.isfinite(float(value))
        except (ValueError, OverflowError):
            valid = False
    else:
        raise RuntimeError("Unknown internal schema type")
    return [] if valid else [f"{path}: 유효한 {spec} 값이 필요합니다."]


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidSubmission("JSON에 중복 key가 있습니다.")
        result[key] = value
    return result


def _no_constant(_):
    raise InvalidSubmission("JSON에 NaN 또는 Infinity를 사용할 수 없습니다.")


def tree_limits(value):
    nodes = 0

    def visit(v, depth):
        nonlocal nodes
        nodes += 1
        if nodes > LIMITS.json_nodes or depth > LIMITS.json_depth:
            raise InvalidSubmission("JSON 구조 크기 제한을 초과했습니다.")
        if type(v) is dict:
            if len(v) > LIMITS.list_length or any(type(k) is not str for k in v):
                raise InvalidSubmission("JSON 객체의 key 형식 또는 크기가 잘못되었습니다.")
            for item in v.values():
                visit(item, depth + 1)
        elif type(v) is list:
            if len(v) > LIMITS.list_length:
                raise InvalidSubmission("JSON list 크기 제한을 초과했습니다.")
            for item in v:
                visit(item, depth + 1)
        elif type(v) is float:
            if not math.isfinite(v):
                raise InvalidSubmission("JSON에 NaN 또는 Infinity를 사용할 수 없습니다.")
        elif v is not None and type(v) not in (str, bool, int):
            raise InvalidSubmission("JSON 기본 타입만 제출할 수 있습니다.")

    visit(value, 0)


def parse_json(raw, *, max_bytes=LIMITS.payload_bytes):
    if len(raw) > max_bytes:
        raise InvalidSubmission("제출 파일이 8 MiB 제한을 초과했습니다.")
    try:
        value = json.loads(raw, object_pairs_hook=_no_duplicate_keys, parse_constant=_no_constant)
        tree_limits(value)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, InvalidSubmission):
            raise
        raise InvalidSubmission("올바른 UTF-8 JSON 제출 파일이 필요합니다.") from None
    return value


def validate_envelope(bundle, *, problem_set=DEFAULT_PROBLEM_SET):
    tree_limits(bundle)
    expected = {"schema_version", "notebook_version", "contract", "exercises"}
    if type(bundle) is not dict or set(bundle) != expected:
        raise InvalidSubmission("제출 envelope의 필드가 맞지 않습니다.")
    if type(bundle["schema_version"]) is not int or bundle["schema_version"] != 1:
        raise InvalidSubmission("schema_version 1이 필요합니다.")
    if bundle["notebook_version"] != problem_set.notebook_version or bundle["contract"] != problem_set.contract:
        raise InvalidSubmission("설치된 패키지의 문제 버전·제출 계약과 일치하는 제출이 필요합니다.")
    entries = bundle["exercises"]
    if type(entries) is not dict or any(ex not in problem_set.order for ex in entries):
        raise InvalidSubmission("알려진 문항으로 구성한 exercises 객체가 필요합니다.")
    return entries
