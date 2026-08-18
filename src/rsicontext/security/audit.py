"""Conservative AST, import, and filesystem-capability audit for policies."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_DEFAULT_ALLOWED_IMPORTS: Final = frozenset(
    {
        "collections",
        "dataclasses",
        "functools",
        "heapq",
        "itertools",
        "json",
        "math",
        "operator",
        "pathlib",
        "re",
        "rsicontext.policy",
        "statistics",
        "string",
        "typing",
    }
)

_FORBIDDEN_IMPORTS: Final = frozenset(
    {
        "aiohttp",
        "asyncio",
        "builtins",
        "ctypes",
        "ftplib",
        "http",
        "httpx",
        "imaplib",
        "importlib",
        "marshal",
        "multiprocessing",
        "os",
        "paramiko",
        "pickle",
        "poplib",
        "pty",
        "requests",
        "secrets",
        "shutil",
        "smtplib",
        "socket",
        "subprocess",
        "sys",
        "telnetlib",
        "tempfile",
        "urllib",
        "webbrowser",
        "websockets",
        "xmlrpc",
    }
)

_DANGEROUS_CALLS: Final = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "eval",
        "exec",
        "getattr",
        "globals",
        "help",
        "input",
        "locals",
        "memoryview",
        "setattr",
        "vars",
    }
)

_WRITE_METHODS: Final = frozenset(
    {
        "chmod",
        "hardlink_to",
        "link_to",
        "mkdir",
        "move",
        "remove",
        "rename",
        "replace",
        "rmdir",
        "symlink_to",
        "touch",
        "truncate",
        "unlink",
        "write",
        "write_bytes",
        "write_text",
        "writelines",
    }
)

_READ_METHODS: Final = frozenset({"read_bytes", "read_text"})


@dataclass(frozen=True, slots=True)
class SecurityViolation:
    """One precise reason a policy cannot receive execution capability."""

    code: str
    message: str
    filename: str
    line: int = 0
    column: int = 0


@dataclass(frozen=True, slots=True)
class AuditReport:
    """Complete static-audit result; violations are never silently dropped."""

    files: tuple[str, ...]
    violations: tuple[SecurityViolation, ...]

    @property
    def safe(self) -> bool:
        """Whether the policy passed every configured check."""

        return not self.violations

    def require_safe(self) -> None:
        """Raise a structured error if any capability violation was found."""

        if self.violations:
            raise PolicySecurityError(self)


class PolicySecurityError(ValueError):
    """Raised when an audited policy exceeds its capabilities."""

    def __init__(self, report: AuditReport) -> None:
        self.report = report
        summary = "; ".join(
            f"{item.filename}:{item.line}:{item.column} [{item.code}] {item.message}"
            for item in report.violations[:5]
        )
        if len(report.violations) > 5:
            summary += f"; and {len(report.violations) - 5} more"
        super().__init__(summary)


@dataclass(frozen=True, slots=True)
class PolicyCapabilities:
    """Explicit capabilities granted to policy source before execution."""

    allowed_imports: frozenset[str] = _DEFAULT_ALLOWED_IMPORTS
    read_roots: tuple[Path, ...] = ()
    max_files: int = 64
    max_file_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        if self.max_files <= 0 or self.max_file_bytes <= 0:
            raise ValueError("policy audit limits must be positive")
        if any(
            module.split(".", maxsplit=1)[0] in _FORBIDDEN_IMPORTS
            for module in self.allowed_imports
        ):
            raise ValueError("forbidden imports cannot be granted by policy capabilities")
        normalized_roots: list[Path] = []
        for root in self.read_roots:
            resolved = root.resolve()
            if not resolved.is_dir():
                raise ValueError(f"policy read root must be an existing directory: {root}")
            normalized_roots.append(resolved)
        object.__setattr__(self, "read_roots", tuple(normalized_roots))


class PolicyAuditor:
    """Audit policy code without importing or executing it."""

    def __init__(self, capabilities: PolicyCapabilities | None = None) -> None:
        self.capabilities = capabilities or PolicyCapabilities()

    def audit_source(self, source: str, *, filename: str = "<policy>") -> AuditReport:
        """Parse and audit source text. Syntax errors become violations."""

        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as exc:
            return AuditReport(
                files=(filename,),
                violations=(
                    SecurityViolation(
                        "SYNTAX",
                        exc.msg,
                        filename,
                        exc.lineno or 0,
                        exc.offset or 0,
                    ),
                ),
            )
        visitor = _PolicyVisitor(
            capabilities=self.capabilities,
            filename=filename,
            source_directory=_source_directory(filename),
        )
        visitor.visit(tree)
        return AuditReport(files=(filename,), violations=tuple(visitor.violations))

    def enforce_source(self, source: str, *, filename: str = "<policy>") -> None:
        """Require source to pass; this still does not execute the source."""

        self.audit_source(source, filename=filename).require_safe()

    def audit_tree(self, root: str | Path) -> AuditReport:
        """Audit all and only regular ``.py`` files in a policy directory."""

        policy_root = Path(root)
        violations: list[SecurityViolation] = []
        if policy_root.is_symlink():
            return AuditReport(
                files=(),
                violations=(
                    SecurityViolation("PATH_SYMLINK", "policy root cannot be a symlink", str(root)),
                ),
            )
        try:
            resolved_root = policy_root.resolve(strict=True)
        except OSError:
            return AuditReport(
                files=(),
                violations=(
                    SecurityViolation("PATH_MISSING", "policy root does not exist", str(root)),
                ),
            )
        if not resolved_root.is_dir():
            return AuditReport(
                files=(),
                violations=(
                    SecurityViolation("PATH_TYPE", "policy root must be a directory", str(root)),
                ),
            )

        entries = sorted(resolved_root.rglob("*"))
        files: list[Path] = []
        for entry in entries:
            relative = entry.relative_to(resolved_root).as_posix()
            if entry.is_symlink():
                violations.append(
                    SecurityViolation(
                        "PATH_SYMLINK", "symlinks are forbidden in policy artifacts", relative
                    )
                )
                continue
            if entry.is_dir():
                if entry.name == "__pycache__":
                    violations.append(
                        SecurityViolation(
                            "PATH_CACHE", "compiled-code directories are forbidden", relative
                        )
                    )
                continue
            if not entry.is_file():
                violations.append(
                    SecurityViolation("PATH_TYPE", "non-regular policy entry", relative)
                )
                continue
            if entry.suffix != ".py":
                violations.append(
                    SecurityViolation(
                        "PATH_EXTENSION", "policy artifacts may contain only .py files", relative
                    )
                )
                continue
            files.append(entry)

        if len(files) > self.capabilities.max_files:
            violations.append(
                SecurityViolation(
                    "LIMIT_FILES",
                    f"policy contains {len(files)} files; limit is {self.capabilities.max_files}",
                    str(resolved_root),
                )
            )

        audited_files: list[str] = []
        for path in files[: self.capabilities.max_files]:
            relative = path.relative_to(resolved_root).as_posix()
            audited_files.append(relative)
            try:
                size = path.stat().st_size
            except OSError as exc:
                violations.append(SecurityViolation("PATH_READ", str(exc), relative))
                continue
            if size > self.capabilities.max_file_bytes:
                violations.append(
                    SecurityViolation(
                        "LIMIT_SIZE",
                        f"policy file exceeds {self.capabilities.max_file_bytes} bytes",
                        relative,
                    )
                )
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                violations.append(SecurityViolation("PATH_READ", str(exc), relative))
                continue
            result = self.audit_source(source, filename=str(path))
            violations.extend(result.violations)
        return AuditReport(tuple(audited_files), tuple(violations))

    def audit_path(self, root: str | Path) -> AuditReport:
        """Alias for :meth:`audit_tree`, emphasizing path-capability checks."""

        return self.audit_tree(root)

    def enforce_tree(self, root: str | Path) -> None:
        """Require an entire policy tree to pass without executing it."""

        self.audit_tree(root).require_safe()


class _PolicyVisitor(ast.NodeVisitor):
    def __init__(
        self,
        *,
        capabilities: PolicyCapabilities,
        filename: str,
        source_directory: Path | None,
    ) -> None:
        self.capabilities = capabilities
        self.filename = filename
        self.source_directory = source_directory
        self.violations: list[SecurityViolation] = []
        self.import_aliases: dict[str, str] = {}
        self.dangerous_aliases: set[str] = set()
        self.direct_call_nodes: set[int] = set()
        self.scope_stack = ["module"]

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._audit_stateful_decorators(node.decorator_list)
        self._audit_mutable_defaults(node.args, node)
        self.scope_stack.append("function")
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._audit_stateful_decorators(node.decorator_list)
        self._audit_mutable_defaults(node.args, node)
        self.scope_stack.append("function")
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope_stack.append("class")
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._audit_mutable_defaults(node.args, node)
        self.scope_stack.append("function")
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            module = alias.name
            self._check_import(module, node)
            local_name = alias.asname or module.split(".", maxsplit=1)[0]
            self.import_aliases[local_name] = module
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            self._add("IMPORT_RELATIVE", "relative imports are not allowed", node)
            self.generic_visit(node)
            return
        module = node.module or ""
        self._check_import(module, node)
        for alias in node.names:
            local_name = alias.asname or alias.name
            imported_name = alias.name.split(".", maxsplit=1)[0]
            if imported_name in _FORBIDDEN_IMPORTS:
                self._add(
                    "IMPORT_FORBIDDEN",
                    f"imported attribute grants forbidden capability: {alias.name}",
                    node,
                )
                self.import_aliases[local_name] = imported_name
            else:
                self.import_aliases[local_name] = f"{module}.{alias.name}"
            if alias.name in _DANGEROUS_CALLS:
                self.dangerous_aliases.add(local_name)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__"):
            self._add("INTROSPECTION", "dunder attribute access is not allowed", node)
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        self._add("STATE_GLOBAL", "global state mutation is not allowed", node)
        self.generic_visit(node)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self._add("STATE_GLOBAL", "nonlocal state mutation is not allowed", node)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == "__builtins__":
            self._add("INTROSPECTION", "__builtins__ access is not allowed", node)
        if isinstance(node.ctx, ast.Load) and (
            node.id in _DANGEROUS_CALLS or node.id in {"open", "print"}
        ):
            parent_is_direct_call = id(node) in self.direct_call_nodes
            if not parent_is_direct_call:
                self._add(
                    "CAPABILITY_VALUE", f"capability cannot be used as a value: {node.id}", node
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self.direct_call_nodes.add(id(node.func))
        call_name = _call_name(node.func)
        simple_name = call_name.rsplit(".", maxsplit=1)[-1]
        if (
            call_name in _DANGEROUS_CALLS
            or call_name in self.dangerous_aliases
            or simple_name in self.dangerous_aliases
        ):
            self._add("DYNAMIC_CODE", f"call to {simple_name} is forbidden", node)
        if self._calls_forbidden_import(call_name):
            self._add("CAPABILITY_CALL", f"call through forbidden module: {call_name}", node)
        if simple_name in _WRITE_METHODS:
            self._add("FILE_WRITE", f"filesystem write operation is forbidden: {simple_name}", node)
        elif simple_name == "open":
            self._audit_open(node)
        elif simple_name in _READ_METHODS:
            self._audit_path_method(node)
        elif simple_name == "print" and any(keyword.arg == "file" for keyword in node.keywords):
            self._add("FILE_WRITE", "print(..., file=...) is forbidden", node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if self.scope_stack[-1] in {"module", "class"} and _is_mutable_state(node.value):
            self._add("STATE_MUTABLE", "module and class state must be immutable literals", node)
        if any(_is_shared_attribute(target) for target in node.targets):
            self._add("STATE_MUTABLE", "shared attribute mutation is not allowed", node)
        source_name = _call_name(node.value)
        if source_name in _DANGEROUS_CALLS or source_name in self.dangerous_aliases:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.dangerous_aliases.add(target.id)
            self._add("DYNAMIC_CODE", f"aliasing {source_name} is forbidden", node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if _is_shared_attribute(node.target):
            self._add("STATE_MUTABLE", "shared attribute mutation is not allowed", node)
        if node.value is not None:
            if self.scope_stack[-1] in {"module", "class"} and _is_mutable_state(node.value):
                self._add(
                    "STATE_MUTABLE", "module and class state must be immutable literals", node
                )
            source_name = _call_name(node.value)
            if source_name in _DANGEROUS_CALLS or source_name in self.dangerous_aliases:
                if isinstance(node.target, ast.Name):
                    self.dangerous_aliases.add(node.target.id)
                self._add("DYNAMIC_CODE", f"aliasing {source_name} is forbidden", node)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if _is_shared_attribute(node.target):
            self._add("STATE_MUTABLE", "shared attribute mutation is not allowed", node)
        self.generic_visit(node)

    def _audit_stateful_decorators(self, decorators: list[ast.expr]) -> None:
        for decorator in decorators:
            name = (
                _call_name(decorator.func)
                if isinstance(decorator, ast.Call)
                else _call_name(decorator)
            )
            if name.rsplit(".", maxsplit=1)[-1] in {"cache", "cached_property", "lru_cache"}:
                self._add("STATE_MUTABLE", f"stateful decorator is forbidden: {name}", decorator)

    def _audit_mutable_defaults(self, arguments: ast.arguments, node: ast.AST) -> None:
        defaults = (*arguments.defaults, *(value for value in arguments.kw_defaults if value))
        if any(_is_mutable_state(value) for value in defaults):
            self._add("STATE_MUTABLE", "mutable function defaults are not allowed", node)

    def _check_import(self, module: str, node: ast.AST) -> None:
        root = module.split(".", maxsplit=1)[0]
        if root in _FORBIDDEN_IMPORTS:
            self._add("IMPORT_FORBIDDEN", f"import grants forbidden capability: {root}", node)
        elif module not in self.capabilities.allowed_imports:
            self._add("IMPORT_NOT_ALLOWED", f"import is not allowlisted: {module}", node)

    def _calls_forbidden_import(self, call_name: str) -> bool:
        first = call_name.split(".", maxsplit=1)[0]
        imported = self.import_aliases.get(first, "")
        return imported.split(".", maxsplit=1)[0] in _FORBIDDEN_IMPORTS

    def _audit_open(self, node: ast.Call) -> None:
        mode_node: ast.expr | None = None
        path_node: ast.expr | None = None
        if isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            if isinstance(receiver, ast.Call) and _call_name(receiver.func).endswith("Path"):
                path_node = receiver.args[0] if receiver.args else None
            if node.args:
                mode_node = node.args[0]
        else:
            path_node = node.args[0] if node.args else None
            if len(node.args) >= 2:
                mode_node = node.args[1]
        for keyword in node.keywords:
            if keyword.arg == "mode":
                mode_node = keyword.value
        mode = "r" if mode_node is None else _literal_string(mode_node)
        if mode is None:
            self._add("FILE_MODE_DYNAMIC", "dynamic file modes are forbidden", node)
            return
        if any(character in mode for character in "wax+"):
            self._add("FILE_WRITE", f"write-capable open mode is forbidden: {mode!r}", node)
            return
        for keyword in node.keywords:
            if keyword.arg in {"file", "path"}:
                path_node = keyword.value
        self._audit_path_node(path_node, node)

    def _audit_path_method(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Attribute):
            self._add("FILE_PATH_DYNAMIC", "cannot prove filesystem read path", node)
            return
        receiver = node.func.value
        if isinstance(receiver, ast.Call) and _call_name(receiver.func).endswith("Path"):
            path_node = receiver.args[0] if receiver.args else None
            self._audit_path_node(path_node, node)
            return
        self._add("FILE_PATH_DYNAMIC", "cannot prove filesystem read path", node)

    def _audit_path_node(self, path_node: ast.expr | None, node: ast.AST) -> None:
        literal = _literal_string(path_node) if path_node is not None else None
        if literal is None:
            self._add("FILE_PATH_DYNAMIC", "dynamic filesystem paths are forbidden", node)
            return
        if not self.capabilities.read_roots:
            self._add("FILE_READ", "policy has no filesystem read capability", node)
            return
        candidate = Path(literal)
        if not candidate.is_absolute():
            if self.source_directory is None:
                self._add("FILE_PATH_DYNAMIC", "relative read path has no trusted base", node)
                return
            candidate = self.source_directory / candidate
        resolved = candidate.resolve(strict=False)
        if not any(_is_within(resolved, root) for root in self.capabilities.read_roots):
            self._add("FILE_READ", f"read path is outside allowed roots: {literal!r}", node)

    def _add(self, code: str, message: str, node: ast.AST) -> None:
        self.violations.append(
            SecurityViolation(
                code,
                message,
                self.filename,
                getattr(node, "lineno", 0),
                getattr(node, "col_offset", 0),
            )
        )


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _literal_string(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_mutable_state(node: ast.AST) -> bool:
    if isinstance(
        node,
        (ast.Call, ast.Dict, ast.DictComp, ast.List, ast.ListComp, ast.Set, ast.SetComp),
    ):
        return True
    if isinstance(node, (ast.Tuple, ast.UnaryOp)):
        return any(_is_mutable_state(child) for child in ast.iter_child_nodes(node))
    return False


def _is_shared_attribute(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and _call_name(node).split(".", maxsplit=1)[0] != "self"


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _source_directory(filename: str) -> Path | None:
    if filename.startswith("<") and filename.endswith(">"):
        return None
    return Path(filename).resolve(strict=False).parent


def codes(violations: Iterable[SecurityViolation]) -> frozenset[str]:
    """Return violation codes for compact assertions and reporting."""

    return frozenset(violation.code for violation in violations)
