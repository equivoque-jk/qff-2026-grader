"""Offline CLI with a fixed scoring policy and portable worker supervision."""

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import psutil

from . import __version__
from .contracts import parse_json
from .models import InvalidSubmission, LIMITS
from .reporting import format_report, format_rubric, write_csv_report, write_json_report


def worker_failure(code, message):
    return {"grader_version": f"qff-grader@{__version__}", "status": "error", "passed": None,
            "score": None, "feedback_code": code, "message": message, "exercises": {}}


def _usage(process):
    """Read only the owned worker PID; the exact simulator creates no children."""
    try:
        with process.oneshot():
            memory = process.memory_info().rss
            times = process.cpu_times()
            return memory, times.user + times.system
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return 0, 0


def _stop(process):
    if process.poll() is None:
        process.kill()
    process.communicate()


def run_isolated(bundle, *, timeout=LIMITS.worker_wall_seconds):
    """Grade a JSON bundle under official defaults without executing source code."""
    if type(timeout) not in (float, int) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("채점 시간 제한은 0보다 큰 유한한 초 단위 수여야 합니다.")
    try:
        request = json.dumps({"submission": bundle}, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        return {"status": "invalid", "passed": False, "score": None,
                "feedback_code": "INVALID_SUBMISSION", "message": "JSON 기본 타입으로 제출하세요.", "exercises": {}}
    env = os.environ.copy()
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        env[key] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    package_root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = package_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    start = time.monotonic()
    peak_memory = peak_cpu = 0
    try:
        with tempfile.TemporaryDirectory(prefix="qff-grade-") as work:
            # File-backed stdin avoids a full pipe preventing resource polling.
            with tempfile.TemporaryFile(dir=work) as input_stream:
                input_stream.write(request.encode("utf-8"))
                input_stream.seek(0)
                with subprocess.Popen([sys.executable, "-m", "qff_grader.worker"], stdin=input_stream,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                      cwd=work, env=env) as process:
                    watched = psutil.Process(process.pid)
                    while True:
                        remaining = timeout - (time.monotonic() - start)
                        if remaining <= 0:
                            _stop(process)
                            return worker_failure("WORKER_TIMEOUT", "채점 시간 제한을 초과했습니다.")
                        try:
                            memory, cpu = _usage(watched)
                        except psutil.Error:
                            _stop(process)
                            return worker_failure("WORKER_LIMITS_UNAVAILABLE", "채점 프로세스의 자원 사용량을 확인할 수 없습니다.")
                        peak_memory = max(peak_memory, memory)
                        peak_cpu = max(peak_cpu, cpu)
                        if memory > LIMITS.worker_memory_bytes:
                            _stop(process)
                            return worker_failure("WORKER_MEMORY", "채점 메모리 제한을 초과했습니다.")
                        if cpu > LIMITS.worker_cpu_seconds:
                            _stop(process)
                            return worker_failure("WORKER_CPU", "채점 CPU 시간 제한을 초과했습니다.")
                        try:
                            output, _ = process.communicate(timeout=min(.1, remaining))
                            break
                        except subprocess.TimeoutExpired:
                            continue
                    return_code = process.returncode
    except (OSError, psutil.Error):
        return worker_failure("WORKER_START", "채점 프로세스를 시작하거나 감시할 수 없습니다.")
    if return_code != 0:
        return worker_failure("WORKER_EXIT", "채점 프로세스가 비정상 종료되었습니다. 설치 환경을 확인하세요.")
    try:
        result = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        return worker_failure("WORKER_RESPONSE", "채점 응답을 읽을 수 없습니다.")
    if type(result) is not dict or "status" not in result:
        return worker_failure("WORKER_RESPONSE", "채점 응답 형식이 잘못되었습니다.")
    result["execution_limits"] = {
        "wall_seconds": timeout, "cpu_seconds": LIMITS.worker_cpu_seconds,
        "memory_bytes": LIMITS.worker_memory_bytes, "memory_mode": "psutil_rss_monitor",
        "elapsed_seconds": round(time.monotonic() - start, 4),
        "observed_peak_rss_bytes": peak_memory, "observed_cpu_seconds": round(peak_cpu, 4),
    }
    return result


def _positive_timeout(value):
    try:
        timeout = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("초 단위 숫자가 필요합니다.") from None
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("0보다 큰 유한한 초 단위 수가 필요합니다.")
    return timeout


def main(argv=None):
    parser = argparse.ArgumentParser(description="QFF 오프라인 자동 채점 — 기본 100점 + 추가 20점")
    parser.add_argument("submission", nargs="?", type=Path, help="노트북이 저장한 submission.json")
    parser.add_argument("--output", type=Path, help="자세한 결과 JSON 저장 경로")
    parser.add_argument("--csv", type=Path, help="문항·세부항목별 점수 CSV 저장 경로")
    parser.add_argument("--rubric", action="store_true", help="공식 배점표 표시 (제출 파일 불필요)")
    parser.add_argument("--timeout", type=_positive_timeout, default=LIMITS.worker_wall_seconds,
                        help=f"채점 프로세스 대기 제한 초 (기본 {LIMITS.worker_wall_seconds})")
    parser.add_argument("--version", action="version", version=f"qff-grade {__version__}")
    args = parser.parse_args(argv)
    if args.rubric:
        if args.submission or args.output or args.csv:
            parser.error("--rubric은 제출 파일·결과 저장 옵션과 함께 사용할 수 없습니다.")
        from .scoring import rubric_snapshot

        sys.stdout.write(format_rubric(rubric_snapshot()))
        return 0
    if args.submission is None:
        parser.error("제출 JSON 경로 또는 --rubric을 지정하세요.")
    paths = [path.resolve() for path in (args.submission, args.output, args.csv) if path is not None]
    if len(paths) != len(set(paths)):
        parser.error("제출 JSON과 결과 JSON·CSV 경로는 서로 달라야 합니다.")
    try:
        with args.submission.open("rb") as stream:
            bundle = parse_json(stream.read(LIMITS.payload_bytes + 1))
    except (OSError, ValueError, InvalidSubmission) as exc:
        print(f"입력 오류: {exc}", file=sys.stderr)
        return 2
    result = run_isolated(bundle, timeout=args.timeout)
    sys.stdout.write(format_report(result))
    try:
        if args.output:
            write_json_report(result, args.output)
            print(f"결과 JSON: {args.output.resolve()}")
        if args.csv:
            write_csv_report(result, args.csv)
            print(f"결과 CSV: {args.csv.resolve()}")
    except (OSError, ValueError) as exc:
        print(f"결과 파일을 저장할 수 없습니다: {exc}", file=sys.stderr)
        return 3
    if result["status"] == "correct":
        return 0
    if result["status"] == "error":
        return 3
    return 2 if result["status"] == "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
