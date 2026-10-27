"""Deterministic arithmetic for at most six qubits (local grader implementation)."""

from dataclasses import dataclass
import itertools

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator, Statevector, partial_trace

from .circuits import unitary_circuit
from .contracts import PARTIES

INPUTS = ((0, 0, 0), (0, 1, 1), (1, 0, 1), (1, 1, 0))
PAULIS = {"I": np.eye(2, dtype=complex), "X": np.array([[0, 1], [1, 0]], complex),
          "Y": np.array([[0, -1j], [1j, 0]], complex), "Z": np.diag([1., -1.])}
SINGLE_STATES = {"0": np.array([1, 0], complex), "1": np.array([0, 1], complex),
                 "+": np.array([1, 1], complex) / np.sqrt(2),
                 "-": np.array([1, -1], complex) / np.sqrt(2),
                 "+i": np.array([1, 1j], complex) / np.sqrt(2),
                 "-i": np.array([1, -1j], complex) / np.sqrt(2)}
BELL_STATES = {"Phi+": np.array([1, 0, 0, 1], complex) / np.sqrt(2),
               "Phi-": np.array([1, 0, 0, -1], complex) / np.sqrt(2),
               "Psi+": np.array([0, 1, 1, 0], complex) / np.sqrt(2),
               "Psi-": np.array([0, 1, -1, 0], complex) / np.sqrt(2)}
GHZ = np.zeros(8, complex)
GHZ[[0, 7]] = 1 / np.sqrt(2)
GHZ_RHO = np.outer(GHZ, GHZ.conj())
COIN_RHO = np.diag([.5, 0, 0, 0, 0, 0, 0, .5]).astype(complex)


def matrix_close(actual, expected, policy):
    a, b = np.asarray(actual), np.asarray(expected)
    return a.shape == b.shape and bool(np.all(np.abs(a - b) <= policy.atol + policy.rtol * np.abs(b)))


def state(qc, initial=None):
    unitary = Operator(unitary_circuit(qc)).data
    return unitary[:, 0] if initial is None else unitary @ initial


def density(vector):
    return np.outer(vector, vector.conj())


def reduced_density(qc, traced):
    return partial_trace(Statevector(state(qc)), list(traced)).data


def fidelity(vector, target):
    return float(abs(np.vdot(target, vector)) ** 2)


def purity(rho):
    return float(np.trace(rho @ rho).real)


def expectation(rho, op):
    return float(np.trace(rho @ op).real)


def observable(qc):
    unitary = Operator(unitary_circuit(qc)).data
    return unitary.conj().T @ PAULIS["Z"] @ unitary


def signed_pauli(label):
    return (-1 if label.startswith("-") else 1) * PAULIS[label.lstrip("-")]


def pauli_label(op, policy):
    for axis in ("X", "Y", "Z"):
        for sign in ("", "-"):
            if matrix_close(op, signed_pauli(sign + axis), policy):
                return sign + axis
    return None


def bell_pair():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    return qc


def alice_encoder():
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    qc.h(0)
    return qc


def graph_pair():
    qc = bell_pair()
    qc.h(1)
    return qc


def empty_bob(n):
    return QuantumCircuit(n, 2 * n)


def broken_bob():
    qc = QuantumCircuit(1, 2)
    with qc.if_test((qc.clbits[0], 1)):
        qc.x(0)
    with qc.if_test((qc.clbits[1], 1)):
        qc.z(0)
    return qc


@dataclass
class Channel:
    kraus: dict
    dimension: int

    def universal_branches(self, policy):
        result = {}
        for label, k in self.kraus.items():
            scale2 = float(np.trace(k.conj().T @ k).real / self.dimension)
            if scale2 <= policy.atol:
                result[label] = False
                continue
            # K/scale must be the identity up to a branch-dependent global phase.
            normalized = k / np.sqrt(scale2)
            overlap = np.trace(normalized) / self.dimension
            phase = overlap / abs(overlap) if abs(overlap) > policy.atol else 1
            result[label] = matrix_close(normalized, phase * np.eye(self.dimension), policy)
        return result

    def complete(self, policy):
        total = sum(k.conj().T @ k for k in self.kraus.values())
        return matrix_close(total, np.eye(self.dimension), policy)

    def universal(self, policy):
        return self.complete(policy) and all(self.universal_branches(policy).values())

    def mean_fidelity(self, vector):
        return float(sum(abs(np.vdot(vector, k @ vector)) ** 2 for k in self.kraus.values()))

    def branch_fidelity(self, label):
        # Fidelity of the normalized Choi pure state to the identity-channel Choi state.
        k = self.kraus[label]
        denominator = self.dimension * np.trace(k.conj().T @ k).real
        return float(abs(np.trace(k)) ** 2 / denominator) if denominator > 0 else 0.

    def unitary_measurement_branches(self, policy):
        for k in self.kraus.values():
            scale2 = float(np.trace(k.conj().T @ k).real / self.dimension)
            if scale2 <= policy.atol or not matrix_close(k.conj().T @ k / scale2,
                                                        np.eye(self.dimension), policy):
                return False
        return self.complete(policy)


def teleport_channel(pair, alice, bob, n=1):
    """Extract all Kraus matrices, rather than probing a finite list of input states.

    n=2 ordering: Q0,Q1,A0,A1,B0,B1; c0,c1,c2,c3 measure q0,q2,q1,q3.
    Rows/columns keep B0/Q0 as the least significant qubit.
    """
    nq = 3 * n
    pre = QuantumCircuit(nq)
    pre.compose(unitary_circuit(pair), list(range(n, nq)), inplace=True)
    for i in range(n):
        pre.compose(unitary_circuit(alice), [i, n + i], inplace=True)
    u = Operator(pre).data
    measured = [q for i in range(n) for q in (i, n + i)]
    result = {}
    for branch in range(2 ** (2 * n)):
        bits = [(branch >> i) & 1 for i in range(2 * n)]
        prefix = sum(bit << q for bit, q in zip(bits, measured))
        rows = [(out << (2 * n)) | prefix for out in range(2 ** n)]
        k = u[np.ix_(rows, range(2 ** n))]
        correction = Operator(unitary_circuit(bob, bits)).data
        result[f"{branch:0{2 * n}b}"] = correction @ k
    return Channel(result, 2 ** n)


def strategy_rate(strategy):
    return sum((strategy[0][x] ^ strategy[1][y] ^ strategy[2][z]) == ((x + y + z) // 2) % 2
               for x, y, z in INPUTS) / 4


def classical_statistics():
    histogram = {str(k): 0 for k in range(5)}
    for strategy in itertools.product(itertools.product((0, 1), repeat=2), repeat=3):
        histogram[str(round(4 * strategy_rate(strategy)))] += 1
    return histogram


def game(rho, bases):
    observables = {p: {str(b): observable(bases[p][str(b)]) for b in (0, 1)} for p in PARTIES}
    values = []
    for x, y, z in INPUTS:
        op = np.kron(observables[PARTIES[2]][str(z)],
                     np.kron(observables[PARTIES[1]][str(y)], observables[PARTIES[0]][str(x)]))
        values.append(expectation(rho, op))
    m = values[0] - sum(values[1:])
    return {"E": dict(zip(("E000", "E011", "E101", "E110"), values)), "M": m,
            "win": .5 + m / 8, "observables": observables}
