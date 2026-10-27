"""Notebook API: collect the user's own functions, then grade serialized data."""
from io import BytesIO
import base64
import json
from pathlib import Path
import numpy as np
import qiskit
from qiskit import QuantumCircuit, qpy
from qiskit.quantum_info import DensityMatrix
from .contracts import VERSION, CONTRACT, ORDER, REQUIRED, OPTIONAL, PARTIES, STATES, BELLS, QPY_VERSION, tree_limits
from .models import LIMITS, InvalidSubmission

# Each function is called once per declared argument, before any grader calculations.
BUILDERS = {
    "1-1": {"circuit": ("build_circuit_1_1",)},
    "1-2": {"circuit": ("build_circuit_1_2",)},
    "1-3": {"by_initial": {s: ("build_circuit_1_3", s) for s in STATES}},
    "1-4": {"basis": ("discrimination_basis",)},
    "1-5": {"by_target": {s: ("bell_transform", s) for s in BELLS}},
    "1-6": {"ghz": ("build_ghz_state",), "coin": ("build_coin_flip_state",), "basis": ("correlation_basis",)},
    "2-2": {"pair": ("shared_pair",), "alice": ("alice_encoder",), "bob": ("bob_decoder",)},
    "2-4": {"bell_from_b_plus": ("bell_pair_from_b_plus",), "bob_graph": ("bob_graph_decoder",)},
    "3-2": {"resource": ("build_ghz3",), "local_bases": {
        p: {str(bit): ("local_basis", p, bit) for bit in (0, 1)} for p in PARTIES}},
    "2-5": {"pair4": ("shared_pairs_2q",), "bob2": ("bob_decoder_2q",)},
}
RESULT_BUILDERS = {"2-1": "teleportation_diagnosis", "2-3": "teleportation_validation",
                   "3-3": "mermin_report", "3-4": "resource_comparison", "3-5": "phase_noise_metrics"}
DEPENDENCIES = {"2-3": ("2-2",), "2-4": ("2-2",), "2-5": ("2-2",),
                "3-3": ("3-2",), "3-4": ("3-2",), "3-5": ("3-2",)}


def encode_circuit(qc):
    if type(qc) is not QuantumCircuit:
        raise TypeError("QuantumCircuit를 반환해야 합니다.")
    with BytesIO() as stream:
        qpy.dump(qc, stream, version=QPY_VERSION)
        raw = stream.getvalue()
    if len(raw) > LIMITS.qpy_bytes:
        raise ValueError("회로 크기가 256 KiB 제한을 초과했습니다.")
    return {"answer_type": "quantum_circuit_qpy", "encoding": "base64",
            "qiskit_version": qiskit.__version__, "qpy_version": QPY_VERSION,
            "data": base64.b64encode(raw).decode("ascii")}


def normalize(value):
    if isinstance(value, DensityMatrix):
        value = value.data
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, complex):
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, (tuple, list)):
        return [normalize(v) for v in value]
    if isinstance(value, dict):
        if any(type(k) is not str for k in value):
            raise TypeError("결과 dict의 key는 문자열이어야 합니다.")
        return {k: normalize(v) for k, v in value.items()}
    if value is None or type(value) in (int, float, bool, str):
        return value
    raise TypeError("반환값은 회로 또는 명시된 수치/배열 형식이어야 합니다.")


def selected_exercises(exercises=None, include_optional=False):
    selected = set(REQUIRED if exercises is None else exercises)
    if isinstance(exercises, str):
        selected = {exercises}
    if include_optional is True or include_optional == "auto":
        selected.update(OPTIONAL)
    elif include_optional is not False and include_optional is not None:
        selected.update([include_optional] if isinstance(include_optional, str) else include_optional)
    if selected - set(ORDER):
        raise ValueError("알 수 없는 문항 ID입니다: " + ", ".join(sorted(selected - set(ORDER))))
    if not selected:
        return []
    for ex in tuple(selected):
        selected.update(DEPENDENCIES.get(ex, ()))
    return [ex for ex in ORDER if ex in selected]


def collect_submission(namespace, *, exercises=None, include_optional=False):
    """Only call explicitly named participant functions, in the participant's runtime.

    This is not a sandbox. Operator CLI reads the resulting JSON without executing
    notebook/source code. Errors are local diagnostics, never executable payloads.
    """
    errors = []
    selected = selected_exercises(exercises, include_optional)
    entries = {}
    call_states = {}
    def call(ex, path, spec, circuit=True):
        name, *args = spec
        state = "error"
        try:
            if name not in namespace:
                state = "missing"
                raise NameError(f"{name} 함수를 먼저 작성·실행하세요.")
            func = namespace[name]
            if not callable(func):
                raise TypeError(f"{name}은 호출 가능한 함수여야 합니다.")
            value = func(*args)
            value = encode_circuit(value) if circuit else normalize(value)
            # Malformed or excessively nested values invalidate their field only,
            # preserving the actual envelope depth, including circuit submaps.
            guarded = value
            for component in reversed(path.split(".")):
                guarded = {component: guarded}
            tree_limits({"exercises": {ex: guarded}})
            # Reject NaN early, with a useful function-level message.
            serialized = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if not circuit and len(serialized) > 256 * 1024:
                raise InvalidSubmission("수치 반환값이 256 KiB 제한을 초과했습니다.")
            state = "returned"
            return value
        except Exception as exc:
            if isinstance(exc, NotImplementedError):
                state = "unimplemented"
            errors.append({"exercise": ex, "field": path, "function": name,
                           "code": state, "message": f"{type(exc).__name__}: {str(exc)[:300]}"})
            return None
        finally:
            call_states.setdefault(ex, []).append(state)
    def tree(ex, spec, path="circuit_answers"):
        if type(spec) is tuple:
            return call(ex, path, spec)
        return {k: tree(ex, v, path + "." + k) for k, v in spec.items()}
    for ex in selected:
        circuits = tree(ex, BUILDERS.get(ex, {}))
        result = None
        if ex == "3-1":
            circuits = {"search_result": call(ex, "circuit_answers.search_result", ("classical_search",), False)}
        if ex in RESULT_BUILDERS:
            result = call(ex, "results", (RESULT_BUILDERS[ex],), False)
        entries[ex] = {"results": result, "circuit_answers": circuits}
    if include_optional == "auto":
        # Try optional functions once. Only wholly missing/NotImplemented work is
        # omitted; actual errors or partly implemented exercises remain visible.
        omitted = {ex for ex in OPTIONAL if ex in entries and call_states.get(ex)
                   and all(state in {"missing", "unimplemented"} for state in call_states[ex])}
        for ex in omitted:
            del entries[ex]
        errors = [error for error in errors if error["exercise"] not in omitted]
    return {"schema_version": 1, "notebook_version": VERSION, "contract": CONTRACT, "exercises": entries}, errors


def build_submission(namespace, *, exercises=None, include_optional=False):
    """Return the transport bundle. For collection diagnostics use collect_submission."""
    return collect_submission(namespace, exercises=exercises, include_optional=include_optional)[0]


def save_submission(namespace, path, *, exercises=None, include_optional=False):
    bundle, errors = collect_submission(namespace, exercises=exercises, include_optional=include_optional)
    raw = json.dumps(bundle, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    if len(raw.encode("utf-8")) > LIMITS.payload_bytes:
        raise InvalidSubmission("제출 크기가 8 MiB 제한을 초과했습니다.")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(raw, encoding="utf-8")
    if errors:
        print("미완성/오류 함수:")
        for error in errors:
            print(f"  {error['exercise']} {error['function']}: {error['message']}")
    print(f"제출 파일 저장: {output.resolve()}")
    return output


def grade_all(namespace, *, exercises=None, include_optional=False, show=True):
    from .cli import run_isolated
    bundle, errors = collect_submission(namespace, exercises=exercises, include_optional=include_optional)
    result = run_isolated(bundle)
    result["collection_errors"] = errors
    if show:
        print(format_report(result, exercises=selected_exercises(exercises, include_optional)))
    return result


def grade_exercise(exercise_id, namespace, *, show=True):
    return grade_all(namespace, exercises=[exercise_id], show=show)


def format_report(result, *, exercises=None):
    lines = [f"QFF 자동채점 — {result.get('status', 'error')}"]
    if result.get("score") is None:
        return "\n".join(lines + [result.get("message", "채점 결과를 확인하세요.")])
    lines.append(f"기본 {result['basic_score']:g}/100 · 추가 {result['bonus_score']:g}/20 · 합계 {result['total_score']:g}/120")
    for ex, item in result.get("exercises", {}).items():
        if exercises is not None and ex not in exercises:
            continue
        lines.append(f"  {ex:>3}  {item['score']:6g}/{item['max_score']:g}  {item['status']}")
        for check in item.get("checks", []):
            if check["status"] != "pass":
                lines.append(f"       {check['id']}: {check.get('message', check['status'])}")
    for error in result.get("collection_errors", []):
        lines.append(f"  {error['function']}: {error['message']}")
    return "\n".join(lines)
