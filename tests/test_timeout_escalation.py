"""
Contract: every failure branch of _process_job that can carry a skill config
runs the escalation post-step. The asyncio.TimeoutError handler shipped
without it, so session timeouts were a silent dead end system-wide — no
retry at the skill's escalation model, no level-1 self-diagnose (found by
the atlas-momo-research smoke run, 2026-08-07). This is the same class of
regression as the 0/516 post_review bug: a branch quietly missing its
post-steps. Source-level AST check keeps the test hermetic (no DB/session
machinery required to pin the guarantee).
"""
import ast
from pathlib import Path

MAIN = Path(__file__).parent.parent / "src" / "runner" / "main.py"


def _awaited_names(nodes: list[ast.stmt]) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.Module(body=nodes, type_ignores=[])):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _timeout_handler() -> ast.ExceptHandler:
    tree = ast.parse(MAIN.read_text())
    process_job = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "_process_job"
    )
    for node in ast.walk(process_job):
        if isinstance(node, ast.ExceptHandler) and node.type is not None:
            t = node.type
            if (isinstance(t, ast.Attribute) and t.attr == "TimeoutError") or (
                isinstance(t, ast.Name) and t.id == "TimeoutError"
            ):
                return node
    raise AssertionError("_process_job has no asyncio.TimeoutError handler")


class TestTimeoutEscalation:
    def test_timeout_branch_refetches_job(self):
        # Without the refetch, resolved_skill is stale-None on the detached
        # instance and level-0 escalation silently degrades (post_review bug
        # pattern).
        assert "_refetch_job" in _awaited_names(_timeout_handler().body)

    def test_timeout_branch_escalates(self):
        assert "_maybe_escalate" in _awaited_names(_timeout_handler().body)

    def test_timeout_branch_still_fails_the_job(self):
        assert "_finish_job" in _awaited_names(_timeout_handler().body)
