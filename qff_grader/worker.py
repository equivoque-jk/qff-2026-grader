"""Grade serialized answers in a subprocess monitored by the local CLI.

This boundary contains failures and resource use; it is not a security sandbox.
The worker never executes notebook cells or participant Python source.
"""

import json
import sys

from .models import LIMITS, InvalidSubmission


def main():
    try:
        from .contracts import parse_json
        from .grading import failure_result, grade_bundle

        raw = sys.stdin.buffer.read(LIMITS.payload_bytes + 4097)
        request = parse_json(raw, max_bytes=LIMITS.payload_bytes + 4096)
        if type(request) is not dict or set(request) != {"submission"}:
            raise InvalidSubmission("채점 입력 형식이 잘못되었습니다.")
        # The official policy is a package constant, never participant input.
        result = grade_bundle(request["submission"])
    except InvalidSubmission as exc:
        result = failure_result(str(exc))
    except Exception:
        result = {"status": "error", "passed": None, "score": None,
                  "feedback_code": "GRADER_ERROR", "message": "채점 중 오류가 발생했습니다. 운영진에게 확인하세요.",
                  "exercises": {}}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
