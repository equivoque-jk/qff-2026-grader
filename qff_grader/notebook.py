"""One-run notebook workflow: collect once, grade, preserve and download a snapshot.

Files and hashes help match a report to an answer snapshot; they are not signatures
or official submission receipts. No network submission or notebook upload occurs.
"""

from datetime import datetime, timezone
import hashlib
import importlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import uuid
import zipfile

from . import __version__


CORE_VERSIONS = {"qiskit": "2.3.1", "numpy": "2.2.6", "psutil": "7.2.2"}
NOTEBOOK_VERSIONS = {"qiskit-aer": "0.17.2", "matplotlib": "3.10.8", "pylatexenc": "2.10"}


class RuntimeSetupError(RuntimeError):
    """Installation or stale imported modules must be fixed before collecting work."""


def check_runtime(*, require_notebook=False):
    """Validate supported Python and pinned installed/loaded dependency versions.

    This check never installs packages or restarts the user's Python runtime.
    It returns version metadata, or raises RuntimeSetupError with a setup remedy.
    """
    if not (3, 10) <= sys.version_info[:2] < (3, 14):
        raise RuntimeSetupError("Python 3.10–3.13이 필요합니다. 지원되는 새 런타임을 선택하세요 (권장: 3.12).")
    required = {**CORE_VERSIONS, **(NOTEBOOK_VERSIONS if require_notebook else {})}
    installed = {}
    problems = []
    for distribution, expected in required.items():
        try:
            installed[distribution] = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            problems.append(f"{distribution} 미설치 (필요: {expected})")
            continue
        if installed[distribution] != expected:
            problems.append(f"{distribution} {installed[distribution]} (필요: {expected})")
    if problems:
        raise RuntimeSetupError("채점 환경 설치를 먼저 완료하세요: " + "; ".join(problems)
                                + ". 제공된 wheel 설치 셀을 실행하고, 이미 import했다면 런타임을 재시작하세요.")
    for distribution, expected in required.items():
        module_name = distribution.replace("-", "_")
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            raise RuntimeSetupError(f"{distribution}을 불러올 수 없습니다. 제공된 설치 셀을 실행한 뒤 "
                                    "런타임을 재시작하고 처음부터 실행하세요.") from exc
        loaded = getattr(module, "__version__", None)
        if loaded is not None and str(loaded) != expected:
            raise RuntimeSetupError(f"{distribution}: 현재 메모리에 {loaded}, 설치된 버전은 {expected}입니다. "
                                    "런타임을 재시작하고 처음부터 실행하세요.")
    return {"python": ".".join(map(str, sys.version_info[:3])), "packages": installed}


def reset_submission_state(namespace):
    """Remove known answer functions and the final output before Run All definitions.

    Helpers, user notes, package imports and unrelated names are preserved. This
    function does not reset the Python runtime or delete saved submission files.
    """
    from .api import BUILDERS, RESULT_BUILDERS

    names = set(RESULT_BUILDERS.values()) | {"classical_search", "_qff_final_result"}
    def visit(spec):
        if type(spec) is tuple:
            names.add(spec[0])
        elif type(spec) is dict:
            for item in spec.values():
                visit(item)
    visit(BUILDERS)
    removed = []
    for name in sorted(names):
        if name in namespace:
            del namespace[name]
            removed.append(name)
    return removed


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _new_file(path, raw):
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _replace_json(path, value):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=".latest-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _append_history(path, record):
    # One append per completed artifact, rather than rewriting or merging prior scores.
    raw = json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _offer_download(archive):
    """Use Colab's download only if its module is actually available."""
    try:
        from google.colab import files
    except ImportError:
        try:
            from IPython import get_ipython
            from IPython.display import FileLink, display
            if get_ipython() is not None:
                display(FileLink(os.path.relpath(archive, Path.cwd()), result_html_prefix="제출 ZIP 다운로드: "))
                return "file_link"
        except ImportError:
            pass
        return "local_path"
    files.download(str(archive))
    return "colab_download"


def finalize_submission(namespace, output_dir="qff_submissions", download=True, team_id=""):
    """Collect once and save the exact graded snapshot as a unique attempt.

    All basic exercises are collected. Optional exercises are omitted only when
    all their functions are missing or raise NotImplementedError. Actual errors
    and partial work are retained. A worker/setup failure never becomes zero or
    replaces latest.json, which points to the latest successfully graded attempt.
    Wrong/partial answers with a computed score are successfully graded attempts.

    Returned data contains the score result plus attempt_id/artifacts. Each attempt
    directory is new and never overwritten. Colab storage is temporary: download
    the ZIP and save the notebook separately before discarding the runtime.
    """
    check_runtime()
    if team_id is None:
        team_id = ""
    if type(team_id) is not str or len(team_id) > 200 or any(ord(char) < 32 for char in team_id):
        raise ValueError("team_id는 제어 문자가 없는 200자 이하 문자열이어야 합니다.")
    from .api import collect_submission, format_report
    from .cli import run_isolated
    from .contracts import OPTIONAL, parse_json
    from .reporting import write_csv_report

    bundle, collection_errors = collect_submission(namespace, include_optional="auto")
    submission_bytes = _json_bytes(bundle)
    # Grading and export both use this frozen transport snapshot, not another call
    # to participant functions or a mutable reference returned by a function.
    snapshot = parse_json(submission_bytes)
    submission_hash = _sha256(submission_bytes)
    result = run_isolated(snapshot)
    attempt_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    result["collection_errors"] = collection_errors
    result["attempt_id"] = attempt_id
    result["submission_sha256"] = submission_hash
    graded = (result.get("status") != "error" and type(result.get("total_score")) in (int, float)
              and math.isfinite(result["total_score"]))
    root = Path(output_dir).resolve()
    attempt = root / "attempts" / attempt_id
    attempt.mkdir(parents=True, exist_ok=False)
    submission_path = attempt / "submission.json"
    result_path = attempt / "result.json"
    csv_path = attempt / "result.csv"
    manifest_path = attempt / "manifest.json"
    archive_path = attempt / f"QFF_{attempt_id}.zip"
    result_bytes = _json_bytes(result)
    _new_file(submission_path, submission_bytes)
    _new_file(result_path, result_bytes)
    write_csv_report(result, csv_path)
    manifest = {
        "schema_version": 1, "attempt_id": attempt_id, "team_id": team_id, "created_at": created_at,
        "grader_version": f"qff-grader@{__version__}", "notebook_version": snapshot["notebook_version"],
        "contract": snapshot["contract"], "rubric_version": result.get("rubric_version"),
        "submission_sha256": submission_hash,
        "file_hashes": {"submission.json": submission_hash, "result.json": _sha256(result_bytes),
                        "result.csv": _sha256(csv_path.read_bytes())},
        "grading_completed": graded, "grading_status": result.get("status"),
        "selected_exercises": list(snapshot["exercises"]),
        "omitted_optional": sorted(OPTIONAL - set(snapshot["exercises"])),
        "collection_errors": collection_errors,
    }
    _new_file(manifest_path, _json_bytes(manifest))
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in (submission_path, result_path, csv_path, manifest_path):
            archive.write(path, arcname=path.name)
    record = {
        "attempt_id": attempt_id, "created_at": created_at, "team_id": team_id,
        "grading_completed": graded, "status": result.get("status"),
        "basic_score": result.get("basic_score"), "bonus_score": result.get("bonus_score"),
        "total_score": result.get("total_score"), "submission_sha256": submission_hash,
        "attempt_dir": str(attempt.relative_to(root)), "archive": str(archive_path.relative_to(root)),
    }
    history_path, latest_path = root / "history.jsonl", root / "latest.json"
    _append_history(history_path, record)
    if graded:
        _replace_json(latest_path, record)
    result["artifacts"] = {
        "attempt_dir": str(attempt), "submission": str(submission_path), "result": str(result_path),
        "manifest": str(manifest_path), "csv": str(csv_path), "archive": str(archive_path),
        "history": str(history_path), "latest": str(latest_path) if latest_path.exists() else None,
    }
    print(format_report(result))
    if manifest["omitted_optional"]:
        print("미작성 선택 문항 제외: " + ", ".join(manifest["omitted_optional"]))
    print(f"실행 기록: {attempt_id}")
    print(f"제출 ZIP: {archive_path}")
    if not graded:
        print("채점을 완료하지 못했습니다. 이 실행은 진단용으로 저장했고 이전 최신 점수 기록은 유지했습니다.")
    print("ZIP과 작성한 노트북을 저장한 뒤 공지된 제출 경로에 제출하세요. 이 실행은 서버로 제출하지 않습니다.")
    if download:
        try:
            result["download"] = _offer_download(archive_path)
        except Exception as exc:
            result["download"] = "manual_download_required"
            print(f"자동 다운로드를 시작하지 못했습니다 ({type(exc).__name__}). 위 ZIP 파일을 직접 다운로드하세요.")
    else:
        result["download"] = "disabled"
    return result
