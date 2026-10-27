"""Local automatic grading for QFF 2026 Q-LINK."""
__version__ = "2.0.3"

def __getattr__(name):
    if name in {"finalize_submission", "check_runtime", "reset_submission_state", "RuntimeSetupError"}:
        from . import notebook
        return getattr(notebook, name)
    if name in {"grade_all", "grade_exercise", "save_submission", "build_submission", "collect_submission", "format_report"}:
        from . import api
        return getattr(api, name)
    if name == "grade_bundle":
        from .grading import grade_bundle
        return grade_bundle
    if name == "rubric_snapshot":
        from .scoring import rubric_snapshot
        return rubric_snapshot
    raise AttributeError(name)

__all__ = ["grade_all", "grade_exercise", "save_submission", "build_submission", "collect_submission", "format_report", "grade_bundle", "rubric_snapshot", "finalize_submission", "check_runtime", "reset_submission_state", "RuntimeSetupError"]
