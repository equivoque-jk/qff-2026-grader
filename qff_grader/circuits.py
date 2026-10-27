"""Bounded QPY decoding and canonical standard-gate evaluation. No participant code runs."""

import base64
from io import BytesIO
import math
import struct

import qiskit
from qiskit import QuantumCircuit, qpy
from qiskit.circuit import Barrier, Clbit, IfElseOp
from qiskit.circuit.library import HGate, XGate, ZGate, CXGate, SGate, SdgGate

from .contracts import CIRCUITS, QISKIT_VERSION, QPY_VERSION, schema_issues
from .models import InvalidSubmission, LIMITS

GATES = {"h": HGate, "x": XGate, "z": ZGate, "cx": CXGate, "s": SGate, "sdg": SdgGate}


def validate_circuit(qc, spec):
    nq, nc, allowed, conditional = spec
    if type(qc) is not QuantumCircuit or (qc.num_qubits, qc.num_clbits) != (nq, nc):
        raise InvalidSubmission(f"이 회로는 {nq} qubit·{nc} cbit이어야 합니다.")
    count = 0

    def walk(circuit, depth):
        nonlocal count
        if depth > LIMITS.control_depth:
            raise InvalidSubmission("조건문 중첩 제한을 초과했습니다.")
        if circuit.parameters:
            raise InvalidSubmission("미결합 parameter는 제출할 수 없습니다.")
        try:
            finite_phase = math.isfinite(float(circuit.global_phase))
        except (ValueError, TypeError, OverflowError):
            finite_phase = False
        if not finite_phase:
            raise InvalidSubmission("전역 위상은 유한한 수여야 합니다.")
        for item in circuit.data:
            count += 1
            if count > LIMITS.instructions:
                raise InvalidSubmission("회로 instruction 제한을 초과했습니다.")
            op = item.operation
            if type(op) is Barrier:
                continue
            if type(op) is IfElseOp and conditional:
                condition = op.condition
                if (type(condition) is not tuple or len(condition) != 2 or
                        not isinstance(condition[0], Clbit) or condition[0] not in circuit.clbits or
                        type(condition[1]) not in (int, bool) or condition[1] not in (0, 1)):
                    raise InvalidSubmission("단일 로컬 cbit의 0/1 if_test가 필요합니다.")
                if len(op.blocks) not in (1, 2):
                    raise InvalidSubmission("if_test의 분기 구조가 잘못되었습니다.")
                for block in op.blocks:
                    if (block.num_qubits, block.num_clbits) != (len(item.qubits), len(item.clbits)):
                        raise InvalidSubmission("조건문 block의 bit 연결이 잘못되었습니다.")
                    walk(block, depth + 1)
                continue
            cls = GATES.get(op.name)
            if cls is None or op.name not in allowed:
                raise InvalidSubmission("이 문항에는 허용된 표준 게이트만 사용할 수 있습니다.")
            canonical = cls()
            if (type(op) not in (cls, type(canonical)) or op.num_qubits != canonical.num_qubits or
                    op.num_clbits or op.params or len(item.qubits) != op.num_qubits or item.clbits or
                    (op.name == "cx" and op.ctrl_state != 1)):
                raise InvalidSubmission("custom gate 대신 표준 Qiskit 게이트를 사용하세요.")

    walk(qc, 0)
    return qc


def decode_qpy(value, spec):
    expected = {"answer_type", "encoding", "qiskit_version", "qpy_version", "data"}
    if type(value) is not dict or set(value) != expected:
        raise InvalidSubmission("QPY envelope의 필드가 맞지 않습니다.")
    if value["answer_type"] != "quantum_circuit_qpy" or value["encoding"] != "base64":
        raise InvalidSubmission("Base64 QPY 회로가 필요합니다.")
    if value["qiskit_version"] != QISKIT_VERSION or qiskit.__version__ != QISKIT_VERSION:
        raise InvalidSubmission("참가자와 grader 모두 Qiskit 2.3.1이 필요합니다.")
    if type(value["qpy_version"]) is not int or value["qpy_version"] != QPY_VERSION:
        raise InvalidSubmission("QPY version 17이 필요합니다.")
    encoded = value["data"]
    if type(encoded) is not str or len(encoded) > 4 * ((LIMITS.qpy_bytes + 2) // 3):
        raise InvalidSubmission("QPY 데이터 형식 또는 크기가 잘못되었습니다.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, UnicodeError):
        raise InvalidSubmission("유효한 Base64 문자열이 필요합니다.") from None
    if len(raw) > LIMITS.qpy_bytes or len(raw) < 20:
        raise InvalidSubmission("QPY 데이터 크기가 잘못되었습니다.")
    # Check program count and wire versions before Qiskit's parser allocates objects.
    header = struct.unpack("!6sBBBBQc", raw[:19])
    if (header[0] != b"QISKIT" or header[1] != QPY_VERSION or
            header[2:5] != (2, 3, 1) or header[5] != 1 or header[6] != b"p" or raw[19:20] != b"q"):
        raise InvalidSubmission("지원하는 버전의 회로 한 개가 담긴 QPY 파일이 필요합니다.")
    try:
        with BytesIO(raw) as stream:
            loaded = qpy.load(stream)
            if len(loaded) != 1 or stream.tell() != len(raw):
                raise InvalidSubmission("QPY에 회로 한 개만 넣고 후행 데이터를 제거하세요.")
        return validate_circuit(loaded[0], spec)
    except InvalidSubmission:
        raise
    except Exception:
        raise InvalidSubmission("QPY 회로를 읽을 수 없습니다.") from None


def decode_answers(exercise_id, value):
    if exercise_id == "3-1":
        if type(value) is not dict or set(value) != {"search_result"}:
            raise InvalidSubmission("classical_search의 search_result가 필요합니다.")
        result = value["search_result"]
        strategy_spec = {"$list": {"length": 3, "item": {
            "$list": {"length": 2, "item": "integer"}}}}
        if (type(result) is not list or len(result) != 2 or
                schema_issues(result[0], "number", "search_result.win_rate") or
                schema_issues(result[1], strategy_spec, "search_result.strategy")):
            raise InvalidSubmission("탐색 결과는 [승률, 세 사람의 출력 전략]이어야 합니다.")
        if any(bit not in (0, 1) for response in result[1] for bit in response):
            raise InvalidSubmission("고전 전략의 출력은 0 또는 1이어야 합니다.")
        return value

    def walk(v, spec):
        if type(spec) is tuple:
            return decode_qpy(v, spec)
        if type(v) is not dict or set(v) != set(spec):
            raise InvalidSubmission("circuit_answers의 필드가 맞지 않습니다.")
        return {key: walk(v[key], child) for key, child in spec.items()}

    return walk(value, CIRCUITS[exercise_id])


def unitary_circuit(qc, classical_bits=None):
    """Materialize one classical branch using fresh canonical gate instances.

    Registers, barriers and serialized custom definitions do not affect the arithmetic.
    This function only receives circuits already checked by validate_circuit.
    """
    result = QuantumCircuit(qc.num_qubits)
    bits = [0] * qc.num_clbits if classical_bits is None else classical_bits

    def walk(circuit, qmap, cmap):
        result.global_phase += float(circuit.global_phase)
        for item in circuit.data:
            op = item.operation
            if type(op) is Barrier:
                continue
            qs = [qmap[circuit.find_bit(bit).index] for bit in item.qubits]
            if type(op) is IfElseOp:
                bit, expected = op.condition
                observed = bits[cmap[circuit.find_bit(bit).index]]
                which = 0 if observed == expected else 1
                if which < len(op.blocks):
                    cs = [cmap[circuit.find_bit(bit).index] for bit in item.clbits]
                    walk(op.blocks[which], qs, cs)
            else:
                result.append(GATES[op.name](), qs)

    walk(qc, list(range(qc.num_qubits)), list(range(qc.num_clbits)))
    return result
