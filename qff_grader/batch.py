"""Regrade received data files without executing participant source code."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from io import StringIO
import json
from pathlib import Path
import stat
import sys
from uuid import uuid4
import zipfile
import zlib

from . import __version__
from .cli import _positive_timeout, run_isolated, worker_failure
from .contracts import parse_json
from .models import InvalidSubmission, LIMITS
from .reporting import _atomic_write, write_json_report

ZIP_BYTES = 16 * 1024 * 1024
ZIP_EXPANDED_BYTES = 32 * 1024 * 1024
MANIFEST_BYTES = 64 * 1024
MAX_FILES = 1000
ZIP_MEMBERS = {"submission.json", "result.json", "manifest.json", "result.csv"}
REPORT_NAMES = {"manifest.json", "result.json", "latest.json", "summary.json", "audit.json"}
CSV_FIELDS = ("source", "team_id_unverified", "submission_id_unverified", "submission_sha256",
              "status", "basic_score", "bonus_score", "total_score", "metadata_warning", "message", "report")


def _bounded_read(stream, limit):
    value = stream.read(limit + 1)
    if len(value) > limit:
        raise InvalidSubmission("파일 크기 제한을 초과했습니다.")
    return value


def _metadata(raw):
    if raw is None:
        return {}, ""
    try:
        manifest = parse_json(raw, max_bytes=MANIFEST_BYTES)
        if type(manifest) is not dict:
            raise InvalidSubmission("manifest는 JSON 객체여야 합니다.")
        values = {}
        for field in ("team_id", "submission_id"):
            value = manifest.get(field, manifest.get("attempt_id", "") if field == "submission_id" else "")
            if type(value) is not str or len(value) > 200:
                raise InvalidSubmission("manifest 식별 정보 형식이 잘못되었습니다.")
            values[field] = value
        values["manifest"] = manifest
        return values, ""
    except (ValueError, InvalidSubmission) as exc:
        return {}, f"메타데이터를 읽을 수 없습니다: {exc}"


def read_received(path):
    """Return bounded answer bytes and unverified metadata; never extract a ZIP."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        with path.open("rb") as stream:
            return _bounded_read(stream, LIMITS.payload_bytes), {}, ""
    if path.suffix.lower() != ".zip":
        raise InvalidSubmission("제출 JSON 또는 ZIP만 읽을 수 있습니다.")
    if path.stat().st_size > ZIP_BYTES:
        raise InvalidSubmission("제출 ZIP은 16 MiB 이하여야 합니다.")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        names = [item.filename for item in members]
        if len(names) != len(set(names)):
            raise InvalidSubmission("ZIP 안에 중복 파일명이 있습니다.")
        if "submission.json" not in names or set(names) - ZIP_MEMBERS:
            raise InvalidSubmission("ZIP 루트에는 submission.json과 제공된 결과·manifest 파일만 허용합니다.")
        if sum(item.file_size for item in members) > ZIP_EXPANDED_BYTES:
            raise InvalidSubmission("ZIP 내부 파일의 총 크기가 32 MiB를 초과했습니다.")
        for item in members:
            mode = item.external_attr >> 16
            if item.is_dir() or stat.S_ISLNK(mode) or item.flag_bits & 1:
                raise InvalidSubmission("ZIP 디렉터리·링크·암호화 파일은 허용하지 않습니다.")
            if item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise InvalidSubmission("ZIP의 압축 형식을 지원하지 않습니다.")
        if archive.getinfo("submission.json").file_size > LIMITS.payload_bytes:
            raise InvalidSubmission("제출 JSON이 8 MiB 제한을 초과했습니다.")
        with archive.open("submission.json") as stream:
            raw = _bounded_read(stream, LIMITS.payload_bytes)
        manifest_raw = None
        if "manifest.json" in names:
            if archive.getinfo("manifest.json").file_size > MANIFEST_BYTES:
                raise InvalidSubmission("manifest가 64 KiB 제한을 초과했습니다.")
            with archive.open("manifest.json") as stream:
                manifest_raw = _bounded_read(stream, MANIFEST_BYTES)
    metadata, warning = _metadata(manifest_raw)
    return raw, metadata, warning


def discover_received(source):
    source = Path(source).resolve()
    if not source.is_dir():
        raise ValueError("입력 경로에는 받은 제출 파일을 모은 폴더를 지정하세요.")
    files = []
    for path in source.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        name = path.name.lower()
        if path.suffix.lower() == ".zip" or (path.suffix.lower() == ".json" and
                name not in REPORT_NAMES and not name.endswith("_result.json")):
            files.append(path)
            if len(files) > MAX_FILES:
                raise ValueError(f"한 번에 최대 {MAX_FILES}개 제출 파일을 처리할 수 있습니다.")
    if not files:
        raise ValueError("채점할 제출 JSON 또는 ZIP이 없습니다.")
    return sorted(files)


def _csv_text(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    # Quote text formulas even when spreadsheet software strips leading spaces.
    if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def regrade_directory(source, output, *, timeout=LIMITS.worker_wall_seconds):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or source in output.parents:
        raise ValueError("결과 폴더는 입력 폴더 밖에 지정하세요. 이전 결과의 재수집을 방지합니다.")
    inputs = discover_received(source)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12]
    run_dir = output / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, path in enumerate(inputs, 1):
        folder = run_dir / f"{index:04d}"
        folder.mkdir()
        relative = path.relative_to(source).as_posix()
        metadata, warning, digest, raw = {}, "", "", None
        try:
            raw, metadata, warning = read_received(path)
            digest = hashlib.sha256(raw).hexdigest()
            claimed_hash = metadata.get("manifest", {}).get("submission_sha256")
            if claimed_hash is not None and claimed_hash != digest:
                warning = (warning + " / " if warning else "") + "manifest의 답안 해시가 실제 파일과 다릅니다."
            bundle = parse_json(raw)
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, NotImplementedError,
                EOFError, zlib.error) as exc:
            result = {"grader_version": f"qff-grader@{__version__}", "status": "invalid", "passed": False,
                      "score": None, "feedback_code": "RECEIVED_FILE_INVALID", "message": str(exc)[:500],
                      "exercises": {}}
        else:
            try:
                result = run_isolated(bundle, timeout=timeout)
            except Exception as exc:
                result = worker_failure("BATCH_GRADING_ERROR", f"채점 실행 오류: {type(exc).__name__}")
        if raw is not None:
            (folder / "submission.json").write_bytes(raw)
        write_json_report(result, folder / "result.json")
        write_json_report({"source": relative, "submission_sha256": digest,
                           "metadata_unverified": metadata, "metadata_warning": warning}, folder / "audit.json")
        rows.append({"source": relative, "team_id_unverified": metadata.get("team_id", ""),
                     "submission_id_unverified": metadata.get("submission_id", ""),
                     "submission_sha256": digest, "status": result.get("status", "error"),
                     "basic_score": result.get("basic_score"), "bonus_score": result.get("bonus_score"),
                     "total_score": result.get("total_score"), "metadata_warning": warning,
                     "message": result.get("message", ""), "report": f"{index:04d}/result.json"})
    text = StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows({key: _csv_text(value) for key, value in row.items()} for row in rows)
    _atomic_write(run_dir / "scores.csv", text.getvalue(), encoding="utf-8-sig")
    summary = {"batch_id": run_id, "grader_version": __version__, "source_directory": str(source),
               "received_count": len(rows), "counts_by_status": {status: sum(r["status"] == status for r in rows)
                   for status in sorted({r["status"] for r in rows})},
               "selection_policy": "all_received_attempts_no_official_selection", "rows": rows}
    write_json_report(summary, run_dir / "summary.json")
    return run_dir, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="QFF 제출 JSON·ZIP 일괄 재채점 (참가자 소스 실행 없음)")
    parser.add_argument("input_dir", type=Path, help="받은 제출 파일만 모은 폴더")
    parser.add_argument("--output", required=True, type=Path, help="입력 폴더 밖의 결과 저장 폴더")
    parser.add_argument("--timeout", type=_positive_timeout, default=LIMITS.worker_wall_seconds)
    parser.add_argument("--version", action="version", version=f"qff-grade-batch {__version__}")
    args = parser.parse_args(argv)
    try:
        run_dir, summary = regrade_directory(args.input_dir, args.output, timeout=args.timeout)
    except (OSError, ValueError) as exc:
        print(f"일괄 채점 오류: {exc}", file=sys.stderr)
        return 2
    print(f"재채점 {summary['received_count']}건 완료: {run_dir}")
    print(f"전체 점수표: {run_dir / 'scores.csv'}")
    print("팀 정보·시각은 참가자 입력입니다. 공식 접수 기록으로 최종 제출을 선정하세요.")
    statuses = set(summary["counts_by_status"])
    if "error" in statuses:
        return 3
    if "invalid" in statuses:
        return 2
    return 0 if statuses == {"correct"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
