"""Student-facing serialization guard.

Every student route's response body passes through student_safe() so a
demographic key can never leave the server on a student surface — a bug
upstream becomes a loud 500, not a leak.
"""

import logging

from reflectool.output_format import PrivacyViolation, assert_no_demographics

logger = logging.getLogger(__name__)


def student_safe(payload):
    assert_no_demographics(payload)
    return payload


__all__ = ["student_safe", "assert_no_demographics", "PrivacyViolation", "logger"]
