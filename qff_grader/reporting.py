"""Korean terminal output and portable JSON/CSV grading reports."""

import csv
from io import StringIO
import json
import os
from pathlib import Path
import tempfile


STATUS_LABELS = {
    "correct": "정답", "wrong": "오답 포함", "invalid": "입력 형식 오류",
    "blocked": "선행 문항 확인 필요", "incomplete": "미제출 문항 있음",
    "missing": "미제출", "error": "채점 오류", "pass": "충족", "fail": "미충족",
}


def number(value):
    return "—" if value is None else f"{value:g}"


def _failed_checks(exercise):
    return [item for item in exercise.get("checks", []) if item.get("status") != "pass"]


def format_report(result):
    """Return a readable report without including submitted circuits or answers."""
    status = result.get("status", "error")
    lines = ["QFF 로컬 채점 결과", f"판정: {STATUS_LABELS.get(status, status)}"]
    if result.get("message"):
        lines.append(result["message"])
    if result.get("feedback_code"):
        lines.append(f"진단 코드: {result['feedback_code']}")
    if result.get("basic_score") is not None:
        lines.extend([
            f"기본 점수: {number(result['basic_score'])} / {number(result.get('max_basic'))}",
            f"추가 점수: {number(result.get('bonus_score'))} / {number(result.get('max_bonus'))}",
            f"합계: {number(result.get('total_score'))} / {number(result.get('max_total'))}",
        ])
    for exercise_id, exercise in result.get("exercises", {}).items():
        title = exercise.get("title", "")
        label = STATUS_LABELS.get(exercise.get("status"), exercise.get("status", ""))
        bonus = " [추가]" if exercise.get("kind") == "bonus" or exercise.get("optional") else ""
        lines.append(f"\n{exercise_id}{bonus} {title}: "
                     f"{number(exercise.get('score'))} / {number(exercise.get('max_score'))} ({label})")
        for group in exercise.get("groups", []):
            title = group.get("title", group.get("id", ""))
            maximum = group.get("max_score", group.get("points"))
            lines.append(f"  {title}: {number(group.get('score'))} / {number(maximum)}")
        for check in _failed_checks(exercise):
            lines.append(f"  · {check.get('id', '')}: {check.get('message', '조건을 충족하지 않습니다.')}")
    return "\n".join(lines) + "\n"


def format_rubric(rubric):
    lines = ["QFF 공식 배점표",
             f"기본 {number(rubric['max_basic'])}점 + 추가 {number(rubric['max_bonus'])}점 "
             f"= 최대 {number(rubric['max_total'])}점"]
    for exercise_id, exercise in rubric["exercises"].items():
        kind = "추가" if exercise["kind"] == "bonus" else "기본"
        lines.append(f"\n{exercise_id} [{kind}] {exercise['title']}: {number(exercise['max_score'])}점")
        for group in exercise.get("groups", []):
            lines.append(f"  {group['title']}: {number(group['points'])}점")
    return "\n".join(lines) + "\n"


def _atomic_write(path, text, *, encoding="utf-8"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding=encoding, newline="", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def write_json_report(result, path):
    _atomic_write(path, json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2) + "\n")


def write_csv_report(result, path):
    """Write an Excel-friendly UTF-8 BOM CSV, one row per exercise/group/total."""
    output = StringIO(newline="")
    fields = ("row_type", "exercise_id", "group_id", "title", "kind", "status", "score", "max_score", "feedback")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for exercise_id, exercise in result.get("exercises", {}).items():
        writer.writerow({
            "row_type": "exercise", "exercise_id": exercise_id,
            "title": exercise.get("title", ""), "kind": exercise.get("kind", ""),
            "status": exercise.get("status", ""), "score": exercise.get("score"),
            "max_score": exercise.get("max_score"),
            "feedback": " | ".join(f"{check.get('id', '')}: {check.get('message', '')}"
                                    for check in _failed_checks(exercise)),
        })
        for group in exercise.get("groups", []):
            writer.writerow({
                "row_type": "group", "exercise_id": exercise_id, "group_id": group.get("id", ""),
                "title": group.get("title", ""), "kind": exercise.get("kind", ""),
                "status": group.get("status", ""), "score": group.get("score"),
                "max_score": group.get("max_score", group.get("points")),
            })
    for kind, title in (("basic", "기본 점수"), ("bonus", "추가 점수"), ("total", "합계")):
        writer.writerow({"row_type": "total", "title": title, "kind": kind,
                         "status": result.get("status", ""), "score": result.get(f"{kind}_score"),
                         "max_score": result.get(f"max_{kind}"), "feedback": result.get("message", "")})
    _atomic_write(path, output.getvalue(), encoding="utf-8-sig")
