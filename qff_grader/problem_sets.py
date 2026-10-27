"""Immutable public metadata; no checker code, expected answers, or score weights."""

from dataclasses import dataclass
import hashlib
from importlib.resources import files
import json
import re


def fingerprint(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class Exercise:
    id: str
    title: str
    part: str
    optional: bool


@dataclass(frozen=True)
class ProblemSet:
    id: str
    revision: str
    notebook_version: str
    contract: str
    checker_revision: str
    exercises: tuple[Exercise, ...]

    def __post_init__(self):
        for value in (self.id, self.revision, self.notebook_version, self.contract, self.checker_revision):
            if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,95}", value):
                raise ValueError("문항 정의의 ID·버전 형식이 잘못되었습니다.")
        if type(self.exercises) is not tuple or not 1 <= len(self.exercises) <= 100:
            raise ValueError("문항 정의는 1~100개의 문항을 포함해야 합니다.")
        seen = set()
        for item in self.exercises:
            if (not isinstance(item, Exercise) or type(item.id) is not str or
                    not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}", item.id) or item.id in seen or
                    type(item.title) is not str or not 1 <= len(item.title) <= 200 or
                    type(item.part) is not str or not 1 <= len(item.part) <= 32 or type(item.optional) is not bool):
                raise ValueError("문항 ID·이름·구분이 잘못되었거나 중복되었습니다.")
            seen.add(item.id)

    @property
    def key(self):
        return f"{self.id}@{self.revision}"

    @property
    def order(self):
        return tuple(item.id for item in self.exercises)

    @property
    def required(self):
        return tuple(item.id for item in self.exercises if not item.optional)

    @property
    def optional(self):
        return frozenset(item.id for item in self.exercises if item.optional)

    def as_dict(self):
        return {"schema_version": 1, "id": self.id, "revision": self.revision,
                "notebook_version": self.notebook_version, "contract": self.contract,
                "checker_revision": self.checker_revision,
                "exercises": [{"id": item.id, "title": item.title, "part": item.part,
                               "optional": item.optional} for item in self.exercises]}

    def snapshot(self):
        value = self.as_dict()
        return {**value, "fingerprint": fingerprint(value)}

    @classmethod
    def from_dict(cls, value):
        fields = {"schema_version", "id", "revision", "notebook_version", "contract", "checker_revision", "exercises"}
        if (type(value) is not dict or set(value) != fields or type(value["schema_version"]) is not int or
                value["schema_version"] != 1 or type(value["exercises"]) is not list):
            raise ValueError("문항 정의 형식이 잘못되었습니다.")
        if any(type(item) is not dict or set(item) != {"id", "title", "part", "optional"} for item in value["exercises"]):
            raise ValueError("문항 정의 필드가 잘못되었습니다.")
        return cls(*(value[key] for key in ("id", "revision", "notebook_version", "contract", "checker_revision")),
                   tuple(Exercise(**item) for item in value["exercises"]))

    @classmethod
    def from_snapshot(cls, value):
        if type(value) is not dict or "fingerprint" not in value:
            raise ValueError("문항 정의의 snapshot이 필요합니다.")
        metadata = {key: item for key, item in value.items() if key != "fingerprint"}
        if value["fingerprint"] != fingerprint(metadata):
            raise ValueError("문항 정의 snapshot이 변경되었습니다.")
        return cls.from_dict(metadata)


DEFAULT_PROBLEM_SET = ProblemSet.from_dict(json.loads(files("qff_grader").joinpath("problem-set.json").read_text()))
