"""Grade returned circuits and computed experimental results, never notebook prose."""
from collections import Counter
import math
from dataclasses import dataclass, field
import numpy as np
from qiskit import QuantumCircuit
from . import physics as p
from . import __version__
from .circuits import decode_answers, decode_qpy, unitary_circuit
from .contracts import CIRCUITS, PARTIES, validate_envelope
from .models import ExerciseResult, GradePolicy, InvalidSubmission, DEFAULT_POLICY
from .problem_sets import DEFAULT_PROBLEM_SET


class DependencyUnavailable(ValueError):
    pass


@dataclass
class Context:
    policy: GradePolicy = DEFAULT_POLICY
    circuits: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    cache: dict = field(default_factory=dict)

    def alice_for_two_qubits(self):
        alice = self.circuits.get("2-2", {}).get("alice")
        if alice is None:
            raise DependencyUnavailable("2-2의 alice_encoder 회로가 필요합니다.")
        channel = p.teleport_channel(p.bell_pair(), alice, p.empty_bob(1))
        if not channel.unitary_measurement_branches(self.policy):
            raise DependencyUnavailable("2-2의 Alice 회로가 유효한 Bell 측정을 구성해야 합니다.")
        return alice

    def transfer(self):
        c = self.circuits.get("2-2", {})
        if not all(k in c for k in ("pair", "alice", "bob")):
            raise DependencyUnavailable("2-2의 세 전송 회로가 필요합니다.")
        if "transfer" not in self.cache:
            self.cache["transfer"] = p.teleport_channel(c["pair"], c["alice"], c["bob"])
        return self.cache["transfer"]

    def quantum(self, require_valid=False):
        c = self.circuits.get("3-2", {})
        if not all(k in c for k in ("resource", "local_bases")) or any(
                bit not in c["local_bases"].get(party, {}) for party in PARTIES for bit in ("0", "1")):
            raise DependencyUnavailable("3-2의 GHZ 준비와 여섯 측정 회로가 필요합니다.")
        if "quantum" not in self.cache:
            rho = p.density(p.state(c["resource"]))
            self.cache["quantum"] = (rho, p.game(rho, c["local_bases"]))
        rho, report = self.cache["quantum"]
        if require_valid and (not p.matrix_close(rho, p.GHZ_RHO, self.policy) or
                not all(self.policy.close(e, target) for e, target in zip(report["E"].values(), (1,-1,-1,-1)))):
            raise DependencyUnavailable("3-2의 GHZ 준비·전략을 먼저 완성하세요.")
        return rho, report


def own(ctx, r):
    return ctx.circuits.get(r.exercise_id, {})


def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(float(value))
    except (ValueError, OverflowError):
        return False


def numeric(r, ctx, key, actual, expected, category="numerical"):
    try:
        value = as_complex(actual)
        passed = abs(value.imag) <= ctx.policy.atol and ctx.policy.close(value.real, expected)
    except (ValueError, TypeError, OverflowError):
        passed = False
    r.check(key, bool(passed), category,
            "반환값이 정확한 계산 결과와 일치해야 합니다.")


def required_gates(r, qc, expected, suffix=""):
    actual = [i.operation.name for i in qc.data if i.operation.name != "barrier"]
    r.check("circuit.required_gates" + suffix, actual == expected, "circuit",
            "명시된 게이트 순서와 초기 상태 준비를 지켜야 합니다.")


def preparation(r, ctx, key, qc, target, initial=None):
    r.check(key, ctx.policy.close(p.fidelity(p.state(qc, initial), target), 1), "circuit",
            "지정 입력에서 목표 상태를 준비해야 합니다. 전역 위상은 무시합니다.")


def channel_checks(r, ctx, channel):
    r.check("circuit.channel_complete", channel.complete(ctx.policy), "circuit")
    for label, valid in channel.universal_branches(ctx.policy).items():
        r.check("circuit.branch." + label, valid, "circuit",
                "이 분기에서 모든 입력과 얽힘을 올바르게 전송해야 합니다.")


def sequence(r, ctx, length):
    value = ctx.outputs.get(r.exercise_id)
    if type(value) is not list or len(value) != length:
        r.issue("format.results", f"이 함수는 길이 {length}인 tuple/list를 반환해야 합니다.")
        return None
    return value


def sublist(r, value, length, label):
    if type(value) is not list or len(value) != length:
        r.issue("format.results." + label, f"{label}: 길이 {length}인 tuple/list가 필요합니다.")
        return None
    return value


def check_1_1(ctx, r):
    qc = own(ctx, r).get("circuit")
    if qc is not None:
        required_gates(r, qc, ["x"])
        preparation(r, ctx, "circuit.initial_zero_to_one", qc, p.SINGLE_STATES["1"])


def check_1_2(ctx, r):
    qc = own(ctx, r).get("circuit")
    if qc is not None:
        required_gates(r, qc, ["h"])
        preparation(r, ctx, "circuit.initial_zero_to_plus", qc, p.SINGLE_STATES["+"])


def check_1_3(ctx, r):
    for label, qc in own(ctx, r).get("by_initial", {}).items():
        prefix = {"0": [], "1": ["x"], "+": ["h"], "-": ["x", "h"]}[label]
        required_gates(r, qc, prefix + ["h", "h"], "." + label)
        preparation(r, ctx, "circuit.initial." + label, qc, p.SINGLE_STATES[label])


def check_1_4(ctx, r):
    qc = own(ctx, r).get("basis")
    if qc is not None:
        label = p.pauli_label(p.observable(qc), ctx.policy)
        r.check("circuit.discriminate_plus_minus", label in ("X", "-X"), "circuit")


def check_1_5(ctx, r):
    initial = np.array([0,1,0,0], complex)
    for label, qc in own(ctx, r).get("by_target", {}).items():
        preparation(r, ctx, "circuit.target." + label, qc, p.BELL_STATES[label], initial)


def check_1_6(ctx, r):
    c = own(ctx, r)
    if "ghz" in c:
        preparation(r, ctx, "circuit.ghz", c["ghz"], p.GHZ)
    if "coin" in c:
        r.check("circuit.coin_reduced_state", p.matrix_close(p.reduced_density(c["coin"], [3]),
                p.COIN_RHO, ctx.policy), "circuit")
    if "basis" in c:
        u = p.Operator(unitary_circuit(c["basis"])).data
        left, right = (np.diag(u @ rho @ u.conj().T).real for rho in (p.GHZ_RHO, p.COIN_RHO))
        r.check("circuit.local_basis_distinguishes", not p.matrix_close(left, right, ctx.policy), "circuit")


def check_2_1(ctx, r):
    result = sequence(r, ctx, 3)
    if result is None:
        return
    broken = p.teleport_channel(p.bell_pair(), p.alice_encoder(), p.broken_bob())
    failed, masked = [], []
    for label, state in p.SINGLE_STATES.items():
        (masked if ctx.policy.close(broken.mean_fidelity(state), 1) else failed).append(label)
    for key, actual, expected in (("failed_inputs", result[0], failed), ("masked_inputs", result[1], masked)):
        valid = type(actual) is list and all(type(v) is str for v in actual)
        r.check("output." + key, valid and Counter(actual) == Counter(expected), "numerical",
                "여섯 기준 입력을 누락·중복 없이 분류하세요. 순서는 무관합니다.")
    branches = sublist(r, result[2], 4, "plus_branch_fidelities")
    if branches is not None:
        psi = p.SINGLE_STATES["+"]
        for label, actual in zip(("00","01","10","11"), branches):
            out = broken.kraus[label] @ psi
            expected = float(abs(np.vdot(psi, out)) ** 2 / np.vdot(out, out).real)
            numeric(r, ctx, "output.plus_branch." + label, actual, expected)


def check_2_2(ctx, r):
    c = own(ctx, r)
    if "pair" in c:
        preparation(r, ctx, "circuit.shared_phi_plus", c["pair"], p.BELL_STATES["Phi+"])
    if all(k in c for k in ("pair","alice","bob")):
        channel_checks(r, ctx, ctx.transfer())


def as_complex(value):
    if finite_number(value):
        return complex(value)
    if type(value) is dict and set(value) == {"real", "imag"}:
        if all(finite_number(x) for x in value.values()):
            return complex(value["real"], value["imag"])
    raise ValueError("유한한 실수/복소수가 필요합니다.")


def check_2_3(ctx, r):
    result = sequence(r, ctx, 3)
    if result is None:
        return
    try:
        rows = result[2]
        if type(rows) is not list or len(rows) != 2 or any(type(row) is not list or len(row) != 2 for row in rows):
            raise ValueError
        rho = np.array([[as_complex(v) for v in row] for row in rows])
        r.check("output.bob_average_density", p.matrix_close(rho, np.eye(2)/2, ctx.policy), "numerical")
    except (ValueError, TypeError):
        r.issue("format.results.bob_average_density", "Bob의 2×2 평균 밀도행렬을 반환하세요.")
    channel = ctx.transfer()
    if not channel.universal(ctx.policy):
        raise DependencyUnavailable("2-3의 전송 검증에는 완성한 2-2 회로가 필요합니다.")
    # Identity channel is proved on every branch, including all 26 notebook probes.
    numeric(r, ctx, "output.mean_fidelity", result[0], 1)
    numeric(r, ctx, "output.min_fidelity", result[1], 1)


def check_2_4(ctx, r):
    c = own(ctx, r)
    if "bell_from_b_plus" in c:
        initial = np.array([1,0,1,0], complex) / np.sqrt(2)
        preparation(r, ctx, "circuit.bell_from_b_plus", c["bell_from_b_plus"], p.BELL_STATES["Phi+"], initial)
    if "bob_graph" in c:
        channel_checks(r, ctx, p.teleport_channel(p.graph_pair(), ctx.alice_for_two_qubits(), c["bob_graph"]))


def check_3_1(ctx, r):
    c = own(ctx, r)
    if "search_result" in c:
        claimed, strategy = c["search_result"]
        achieved = p.strategy_rate(strategy)
        numeric(r, ctx, "search.maximum_rate", claimed, .75)
        numeric(r, ctx, "search.strategy_is_optimal", achieved, .75)
        numeric(r, ctx, "search.claim_matches_strategy", claimed, achieved, "consistency")


def check_3_2(ctx, r):
    c = own(ctx, r)
    if "resource" in c:
        preparation(r, ctx, "circuit.ghz_resource", c["resource"], p.GHZ)
    _, report = ctx.quantum()
    for key, expected in zip(("E000","E011","E101","E110"), (1,-1,-1,-1)):
        numeric(r, ctx, "circuit.game." + key, report["E"][key], expected, "circuit")


def check_3_3(ctx, r):
    result = sequence(r, ctx, 4)
    if result is None:
        return
    _, report = ctx.quantum(require_valid=True)
    for name, actual, expected in (("E", result[0], list(report["E"].values())),
                                   ("win", result[1], [1,1,1,1])):
        values = sublist(r, actual, 4, name)
        if values is not None:
            for bits, v, target in zip(("000","011","101","110"), values, expected):
                numeric(r, ctx, "output." + name + "." + bits, v, target)
    numeric(r, ctx, "output.M", result[2], report["M"])
    numeric(r, ctx, "output.p_win", result[3], report["win"])


def check_3_4(ctx, r):
    result = sequence(r, ctx, 5)
    if result is None:
        return
    numeric(r, ctx, "output.classical_best", result[4], .75)
    _, quantum = ctx.quantum(require_valid=True)
    coin = p.game(p.COIN_RHO, ctx.circuits["3-2"]["local_bases"])
    for name, actual, expected in zip(("ghz_M","ghz_p_win","coin_M","coin_p_win"), result[:4],
            (quantum["M"],quantum["win"],coin["M"],coin["win"])):
        numeric(r, ctx, "output." + name, actual, expected)


def check_2_5(ctx, r):
    c = own(ctx, r)
    if "pair4" in c:
        target = QuantumCircuit(4)
        target.h([0,1]); target.cx(0,2); target.cx(1,3)
        preparation(r, ctx, "circuit.two_bell_pairs", c["pair4"], p.state(target))
    if all(k in c for k in ("pair4", "bob2")):
        channel_checks(r, ctx, p.teleport_channel(c["pair4"], ctx.alice_for_two_qubits(), c["bob2"], n=2))


def check_3_5(ctx, r):
    result = sequence(r, ctx, 4)
    if result is None:
        return
    rho, plus = ctx.quantum(require_valid=True)
    z = np.kron(np.eye(4), p.PAULIS["Z"])
    minus = p.game(z @ rho @ z, ctx.circuits["3-2"]["local_bases"])
    for probability, actual in zip((0,0.1,0.25,0.5), result):
        values = sublist(r, actual, 2, str(probability))
        if values is not None:
            for name, v, target in (("M", values[0], (1-probability)*plus["M"]+probability*minus["M"]),
                                    ("p_win", values[1], (1-probability)*plus["win"]+probability*minus["win"])):
                numeric(r, ctx, f"noise.{probability}.{name}", v, target)


REGISTRY = {"1-1": check_1_1, "1-2": check_1_2, "1-3": check_1_3, "1-4": check_1_4,
            "1-5": check_1_5, "1-6": check_1_6, "2-1": check_2_1, "2-2": check_2_2,
            "2-3": check_2_3, "2-4": check_2_4, "3-1": check_3_1, "3-2": check_3_2,
            "3-3": check_3_3, "3-4": check_3_4, "2-5": check_2_5, "3-5": check_3_5}
RESULT_EXERCISES = {"2-1", "2-3", "3-3", "3-4", "3-5"}


def failure_result(message, status="invalid", code="INVALID_SUBMISSION"):
    return {"grader_version": f"qff-grader@{__version__}", "status": status, "passed": False,
            "score": None, "feedback_code": code, "message": message, "exercises": {}}


def grade_bundle(bundle, *, policy=DEFAULT_POLICY):
    if policy != DEFAULT_POLICY:
        raise ValueError("이 버전의 배점은 고정 수치 정책과 함께 사용합니다.")
    try:
        entries = validate_envelope(bundle)
    except InvalidSubmission as exc:
        return failure_result(str(exc))
    ctx, results = Context(policy), {}
    for ex in DEFAULT_PROBLEM_SET.order:
        if ex not in entries:
            continue
        r = results[ex] = ExerciseResult(ex)
        value = entries[ex]
        if type(value) is not dict or set(value) != {"results", "circuit_answers"}:
            r.issue("format.exercise", "문항에는 results와 circuit_answers가 필요합니다.")
            continue
        ctx.outputs[ex] = value["results"]
        if ex not in RESULT_EXERCISES and value["results"] is not None:
            r.issue("format.results", "회로/탐색 문항의 results는 null이어야 합니다.")
        def decode_tree(v, spec, path):
            if type(spec) is tuple:
                try:
                    return decode_qpy(v, spec)
                except InvalidSubmission as exc:
                    r.issue("format." + path, path + ": " + str(exc))
                    return None
            if type(v) is not dict:
                r.issue("format." + path, path + ": dict가 필요합니다.")
                return {}
            output = {}
            for key in spec:
                child = decode_tree(v.get(key), spec[key], path + "." + key)
                if child is not None:
                    output[key] = child
            for key in v.keys() - spec.keys():
                r.issue("format." + path + "." + key, "정의되지 않은 회로 항목입니다.")
            return output
        if ex == "3-1":
            try:
                ctx.circuits[ex] = decode_answers(ex, value["circuit_answers"])
            except InvalidSubmission as exc:
                r.issue("format.circuit_answers", str(exc))
        else:
            ctx.circuits[ex] = decode_tree(value["circuit_answers"], CIRCUITS[ex], "circuit_answers")
    for ex, r in results.items():
        if any(c["id"] == "format.exercise" for c in r.checks):
            continue
        try:
            REGISTRY[ex](ctx, r)
        except DependencyUnavailable as exc:
            r.issue("dependency.circuit", str(exc), "blocked", "dependency")
    encoded = {ex: r.as_dict() for ex, r in results.items()}
    missing = [ex for ex in DEFAULT_PROBLEM_SET.required if ex not in entries]
    statuses = {r["status"] for r in encoded.values()}
    status = next((s for s in ("error", "invalid", "wrong", "blocked") if s in statuses),
                  "incomplete" if missing else "correct")
    from .scoring import score_result
    return score_result({"grader_version": f"qff-grader@{__version__}",
        "notebook_version": DEFAULT_PROBLEM_SET.notebook_version,
        "problem_set": DEFAULT_PROBLEM_SET.snapshot(), "policy": policy.as_dict(),
        "status": status, "passed": status == "correct", "score": None,
        "summary": {"submitted": len(encoded), "required_missing": missing,
            **{s: sum(r["status"] == s for r in encoded.values()) for s in ("correct","wrong","invalid","blocked")}},
        "exercises": encoded})
