"""Fixed numerical policy, limits and diagnostic results."""

from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class GradePolicy:
    atol: float
    rtol: float
    label: str

    def __post_init__(self):
        for number in (self.atol, self.rtol):
            if type(number) not in (int, float) or not math.isfinite(number) or number < 0:
                raise ValueError("허용오차는 0 이상의 유한한 수여야 합니다.")
        if not self.label or type(self.label) is not str:
            raise ValueError("정책 이름이 필요합니다.")

    def close(self, actual, expected):
        return abs(actual - expected) <= self.atol + self.rtol * abs(expected)

    def as_dict(self):
        return {"label": self.label, "atol": self.atol, "rtol": self.rtol}

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {"atol", "rtol", "label"}:
            raise ValueError("정책에는 label, atol, rtol만 지정하세요.")
        return cls(**value)


@dataclass(frozen=True)
class Limits:
    # Engineering limits, not a depth/gate-count scoring rubric.
    payload_bytes: int = 8 * 1024 * 1024
    qpy_bytes: int = 256 * 1024
    instructions: int = 1024
    control_depth: int = 8
    json_depth: int = 24
    json_nodes: int = 16000
    list_length: int = 128
    worker_wall_seconds: int = 30
    worker_cpu_seconds: int = 20
    worker_memory_bytes: int = 1536 * 1024 * 1024


LIMITS = Limits()


@dataclass
class ExerciseResult:
    exercise_id: str
    checks: list = field(default_factory=list)

    def check(self, check_id, passed, category="concept", message=None):
        status = "pass" if passed else "fail"
        self.checks.append({"id": check_id, "category": category, "status": status,
                            "message": message or ("조건을 충족합니다." if passed else "조건을 충족하지 않습니다.")})

    def issue(self, check_id, message, status="invalid", category="format"):
        self.checks.append({"id": check_id, "category": category, "status": status,
                            "message": message})

    def as_dict(self):
        states = {item["status"] for item in self.checks}
        if "error" in states:
            status, passed = "error", None
        elif "invalid" in states:
            status, passed = "invalid", False
        elif "fail" in states:
            status, passed = "wrong", False
        elif "blocked" in states:
            status, passed = "blocked", None
        else:
            status, passed = "correct", True
        return {"exercise_id": self.exercise_id, "status": status, "passed": passed,
                "score": None, "checks": self.checks}


class InvalidSubmission(ValueError):
    """Safe, participant-facing validation message (never an internal traceback)."""


DEFAULT_POLICY = GradePolicy(atol=1e-6, rtol=0.0, label="qff-2026-exact-v1")
