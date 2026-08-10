"""
Static, pre-execution safety check for Python code.
Refuses code that attempts to escape the sandbox boundary - writing to
system paths, or using low-level modules that could bypass container
isolation - BEFORE it is ever sent to the executor. This makes refusal
a hard gate the model cannot route around, rather than relying on the
model to decline such requests on its own.

This is a best-effort static layer, not a substitute for the container
isolation itself (--network none, --read-only, non-root user, etc.) -
those remain the actual enforcement boundary. This layer exists so the
agent refuses obviously out-of-scope requests outright instead of
finding a workaround.
"""

import ast

RESTRICTED_MODULES = {"socket", "subprocess", "ctypes"}
DANGEROUS_OS_CALLS = {"system", "popen", "exec", "execv", "execve", "remove", "unlink", "rmdir"}


class SafetyViolation(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def check_code_safety(code: str) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return  # let execution itself surface the syntax error normally

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in RESTRICTED_MODULES:
                    raise SafetyViolation(
                        f"Use of restricted module '{alias.name}' is not allowed."
                    )

        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in RESTRICTED_MODULES:
                raise SafetyViolation(
                    f"Use of restricted module '{node.module}' is not allowed."
                )

        if isinstance(node, ast.Attribute) and node.attr in DANGEROUS_OS_CALLS:
            raise SafetyViolation(f"Use of 'os.{node.attr}' is not allowed.")

        if isinstance(node, ast.Call):
            func_name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if func_name == "open" and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    path = first_arg.value
                    if path.startswith("/") and not path.startswith("/tmp"):
                        raise SafetyViolation(
                            f"Writing to system path '{path}' is not allowed."
                        )