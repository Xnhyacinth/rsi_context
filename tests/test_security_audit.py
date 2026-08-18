from pathlib import Path

import pytest

from rsicontext.security import (
    PolicyAuditor,
    PolicyCapabilities,
    PolicySecurityError,
)


def violation_codes(source: str) -> set[str]:
    return {violation.code for violation in PolicyAuditor().audit_source(source).violations}


def test_pure_policy_with_allowlisted_imports_passes() -> None:
    source = """
import math
import re
from collections import Counter

def select(query: str, chunks: list[str]) -> list[str]:
    words = Counter(re.findall(r"[a-z]+", query.lower()))
    return sorted(chunks, key=lambda chunk: -sum(words.values()) + math.floor(len(chunk) / 10))
"""
    report = PolicyAuditor().audit_source(source)
    assert report.safe
    report.require_safe()


def test_audit_allows_re_compile_inside_functions() -> None:
    source = """
import re

def select(query: str) -> list[str]:
    pattern = re.compile(r"[A-Za-z]+-[0-9]+")
    return pattern.findall(query)
"""
    report = PolicyAuditor().audit_source(source)
    assert report.safe
    report.require_safe()


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import socket\nsocket.create_connection(('example.com', 80))\n", "IMPORT_FORBIDDEN"),
        ("import subprocess as sp\nsp.run(['true'])\n", "IMPORT_FORBIDDEN"),
        ("from subprocess import run as launch\nlaunch(['true'])\n", "CAPABILITY_CALL"),
        ("result = eval('1 + 1')\n", "DYNAMIC_CODE"),
        ("calculate = eval\nresult = calculate('1 + 1')\n", "DYNAMIC_CODE"),
        ("exec('x = 1')\n", "DYNAMIC_CODE"),
        ("result = compile('1', '<policy>', 'eval')\n", "DYNAMIC_CODE"),
        ("import functools\nf = functools.partial(eval, '1+1')\nf()\n", "CAPABILITY_VALUE"),
        ("reader = open\nreader('/tmp/out', 'w')\n", "CAPABILITY_VALUE"),
        ("list(map(eval, ['1+1']))\n", "CAPABILITY_VALUE"),
        ("(lambda function: function('/tmp/out', 'w'))(open)\n", "CAPABILITY_VALUE"),
        ("open('/tmp/out', 'w').write('x')\n", "FILE_WRITE"),
        ("from pathlib import Path\nPath('/tmp/out').open('w')\n", "FILE_WRITE"),
        ("from pathlib import Path\nPath('/tmp/out').write_text('x')\n", "FILE_WRITE"),
        ("from pathlib import os\nos.system('id')\n", "IMPORT_FORBIDDEN"),
        (
            "from rsicontext.registry.preflight import subprocess\nsubprocess.run(['id'])\n",
            "IMPORT_NOT_ALLOWED",
        ),
        ("import rsicontext.registry.preflight\n", "IMPORT_NOT_ALLOWED"),
        ("import random\n", "IMPORT_NOT_ALLOWED"),
        ("from .helper import score\n", "IMPORT_RELATIVE"),
        ("counter = 0\ndef select():\n    global counter\n    counter += 1\n", "STATE_GLOBAL"),
        (
            "def outer():\n    counter = 0\n    def select():\n"
            "        nonlocal counter\n        counter += 1\n",
            "STATE_GLOBAL",
        ),
        ("_STATE = []\ndef select(value):\n    _STATE.append(value)\n", "STATE_MUTABLE"),
        (
            "class Policy:\n    seen = {}\n"
            "    def select(self, value):\n        self.seen[value] = True\n",
            "STATE_MUTABLE",
        ),
        (
            "class Policy:\n    calls = 0\n    def select(self):\n        Policy.calls += 1\n",
            "STATE_MUTABLE",
        ),
        (
            "import functools\n@functools.lru_cache\ndef call_count():\n    return 1\n",
            "STATE_MUTABLE",
        ),
        (
            "def select(value, seen=[]):\n    seen.append(value)\n    return len(seen)\n",
            "STATE_MUTABLE",
        ),
        ("select = lambda value, seen={}: seen.setdefault(value, 1)\n", "STATE_MUTABLE"),
    ],
)
def test_audit_rejects_network_subprocess_dynamic_code_and_writes(
    source: str, expected: str
) -> None:
    assert expected in violation_codes(source)


def test_read_access_requires_literal_path_under_an_explicit_root(tmp_path: Path) -> None:
    allowed = tmp_path / "visible"
    allowed.mkdir()
    evidence = allowed / "evidence.txt"
    evidence.write_text("evidence", encoding="utf-8")
    capabilities = PolicyCapabilities(read_roots=(allowed,))
    auditor = PolicyAuditor(capabilities)

    assert auditor.audit_source(f"open({str(evidence)!r}).read()\n").safe
    outside = tmp_path / "sealed.txt"
    assert "FILE_READ" in {
        violation.code
        for violation in auditor.audit_source(f"open({str(outside)!r}).read()\n").violations
    }
    assert "FILE_PATH_DYNAMIC" in {
        violation.code
        for violation in auditor.audit_source("open(user_supplied_path).read()\n").violations
    }


def test_tree_audit_rejects_non_python_files_and_symlinks(tmp_path: Path) -> None:
    policy = tmp_path / "policy"
    policy.mkdir()
    (policy / "select.py").write_text("def select():\n    return []\n", encoding="utf-8")
    (policy / "payload.sh").write_text("exit 0\n", encoding="utf-8")
    (policy / "linked.py").symlink_to(policy / "select.py")

    report = PolicyAuditor().audit_tree(policy)
    codes = {violation.code for violation in report.violations}
    assert {"PATH_EXTENSION", "PATH_SYMLINK"} <= codes
    with pytest.raises(PolicySecurityError):
        report.require_safe()
