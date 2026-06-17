"""
Contract-test helpers.

assert_status() enforces the AS-IS contract. On this migration branch the new
implementation must reproduce legacy behaviour *exactly* — including known
bugs — so downstream forks that depend on the precise responses keep working.

Two modes:

* No ``current_bug``: a normal assertion — the response must equal ``expected``.

* With ``current_bug``: the endpoint has a documented AS-IS bug, so the response
  must equal that buggy code. This is a STRICT lock:
    - response == current_bug  -> pass (bug reproduced); registered + warned so
      it shows up in the end-of-run inventory.
    - response == expected     -> FAIL: the bug looks fixed. If that fix is
      intentional, update this call (drop ``current_bug``, set ``expected`` to
      the new code) to record it.
    - anything else            -> FAIL: unexpected status.

So "fixing #111 (fully or partially)" is surfaced as a test failure that forces
the assertion to be updated, which is how the suite records that the bug is gone.
"""

import warnings
from collections import Counter


# Module-level registries of bug observations during a test run.
# _BUG_REGISTRY      : bug still present (reproduced) — the expected AS-IS state.
# _FIXED_REGISTRY    : bug no longer present (endpoint returned the corrected
#                      status) — the "unexpectedly fixed" state; the test fails
#                      and the assertion must be updated to record the fix.
# Maps bug description (e.g. "#111: ...") to a hit count.
_BUG_REGISTRY: Counter = Counter()
_FIXED_REGISTRY: Counter = Counter()


def assert_status(
    response, *, expected: int, current_bug: int | None = None, bug: str | None = None
):
    """Assert response.status matches the AS-IS contract.

    Args:
        response: The HTTP response object (must expose ``.status``).
        expected: The status code the endpoint *should* return once the bug
            (if any) is fixed.
        current_bug: The wrong status the endpoint currently returns AS-IS and
            must keep returning on this migration branch. When set, the
            response MUST equal this value or the test fails.
        bug: Free-form description of the bug; typically a tracker reference
            like ``"#111: returns 500 instead of 404"``.

    Examples:
        assert_status(response, expected=200)

        assert_status(
            response,
            expected=404,
            current_bug=500,
            bug="#111: returns 500 instead of 404 on missing file",
        )
    """
    if current_bug is None:
        assert response.status == expected, (
            f"Expected {expected}, got {response.status}"
        )
        return

    if response.status == current_bug:
        if bug:
            _BUG_REGISTRY[bug] += 1
        warnings.warn(
            f"AS-IS API bug still present — {bug} "
            f"(got {current_bug}, should be {expected})",
            stacklevel=2,
        )
        return

    if response.status == expected:
        if bug:
            _FIXED_REGISTRY[bug] += 1
        raise AssertionError(
            f"AS-IS bug appears FIXED — {bug} (got the corrected status "
            f"{expected}, expected the documented buggy status {current_bug}). "
            f"If this fix is intentional, update this assertion: drop "
            f"current_bug= and set expected={expected} so the suite records it."
        )

    raise AssertionError(
        f"Unexpected status for AS-IS bug — {bug}: got {response.status}, "
        f"expected the documented buggy status {current_bug} "
        f"(corrected would be {expected})."
    )


def get_bug_registry() -> Counter:
    """Return the registry of bugs still present (reproduced) this run."""
    return _BUG_REGISTRY


def get_fixed_registry() -> Counter:
    """Return the registry of bugs that appear fixed (diverged) this run."""
    return _FIXED_REGISTRY


def reset_bug_registry() -> None:
    """Clear both registries (mainly for testing the helper itself)."""
    _BUG_REGISTRY.clear()
    _FIXED_REGISTRY.clear()
