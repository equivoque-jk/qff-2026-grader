"""Fixed, transparent partial credit for the published QFF problem set."""

from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
import json
import math


@lru_cache(maxsize=1)
def _rubric():
    value = json.loads(files("qff_grader").joinpath("rubric.json").read_text(encoding="utf-8"))
    totals = {"basic": 0.0, "bonus": 0.0}
    for exercise_id, exercise in value["exercises"].items():
        group_ids = set()
        maximum = 0.0
        for group in exercise["groups"]:
            if (group["id"] in group_ids or not group["checks"] or
                    not math.isfinite(group["points"]) or group["points"] <= 0):
                raise RuntimeError(f"Invalid installed scoring group: {exercise_id}/{group['id']}")
            group_ids.add(group["id"])
            maximum += group["points"]
        if not math.isclose(maximum, exercise["max_score"], abs_tol=1e-9):
            raise RuntimeError(f"Installed rubric total does not match: {exercise_id}")
        totals[exercise["kind"]] += maximum
    if (totals != {"basic": 100.0, "bonus": 20.0} or
            value["max_basic"] != 100 or value["max_bonus"] != 20 or value["max_total"] != 120):
        raise RuntimeError("Installed QFF rubric must total 100 basic + 20 bonus points")
    return value


def rubric_snapshot():
    """Return a caller-owned JSON-serializable copy of the official rubric."""
    return deepcopy(_rubric())


def score_result(result):
    """Attach reproducible partial credit to checker results, in place, and return it.

    A group earns its listed points only when every listed check exists and passes.
    Missing, failed, invalid, and dependency-blocked checks receive zero for that
    group. Duplicate check IDs must all pass, preventing a later success from
    hiding an earlier failure. Status and feedback from the checker are preserved.
    Empty or missing submissions never receive points for simply being present.
    """
    rubric = _rubric()
    exercises = result.setdefault("exercises", {})
    totals = {"basic": 0.0, "bonus": 0.0}
    for exercise_id, spec in rubric["exercises"].items():
        exercise = exercises.setdefault(exercise_id, {
            "exercise_id": exercise_id,
            "status": "missing",
            "passed": None,
            "checks": [],
        })
        checks_by_id = {}
        for check in exercise.get("checks", []):
            checks_by_id.setdefault(check["id"], []).append(check["status"])
        groups = []
        for group in spec["groups"]:
            missing = [key for key in group["checks"] if key not in checks_by_id]
            nonpassing = [key for key in group["checks"]
                          if key in checks_by_id and any(status != "pass" for status in checks_by_id[key])]
            passed = not missing and not nonpassing
            observed = {status for key in group["checks"] for status in checks_by_id.get(key, [])}
            if passed:
                status = "pass"
            elif "blocked" in observed or (missing and exercise.get("status") == "blocked"):
                status = "blocked"
            elif nonpassing:
                status = "fail"
            else:
                status = "missing"
            groups.append({
                "id": group["id"], "title": group["title"],
                "score": group["points"] if passed else 0,
                "max_score": group["points"], "status": status,
                "checks": list(group["checks"]),
                "missing_checks": missing, "nonpassing_checks": nonpassing,
            })
        score = round(sum(group["score"] for group in groups), 6)
        exercise.update({"title": spec["title"], "kind": spec["kind"],
                         "score": score, "max_score": spec["max_score"], "groups": groups})
        totals[spec["kind"]] += score
    basic = round(totals["basic"], 6)
    bonus = round(totals["bonus"], 6)
    total = round(basic + bonus, 6)
    result.update({"rubric_version": rubric["version"], "basic_score": basic,
                   "max_basic": rubric["max_basic"], "bonus_score": bonus,
                   "max_bonus": rubric["max_bonus"], "total_score": total,
                   "max_total": rubric["max_total"], "score": total})
    return result
