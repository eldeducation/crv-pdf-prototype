"""Preserve every selected frame while limiting FFmpeg expression-tree depth."""
import re

_SELECTION = re.compile(r"^select='(?P<terms>eq\(n,[0-9]+\)(?:\+eq\(n,[0-9]+\))*)'(?P<tail>,showinfo,scale=[0-9]+:-1)$")


def balanced_sum(terms):
    if not terms:
        raise ValueError("No frame selectors")
    if len(terms) == 1:
        return terms[0]
    middle = len(terms) // 2
    return "(" + balanced_sum(terms[:middle]) + "+" + balanced_sum(terms[middle:]) + ")"


def balance_filter(value):
    matched = _SELECTION.fullmatch(value)
    if not matched:
        return value
    terms = matched["terms"].split("+")
    return "select='" + balanced_sum(terms) + "'" + matched["tail"]


def balance_command(command):
    updated = list(command)
    for index, part in enumerate(command[:-1]):
        if part == "-vf":
            updated[index + 1] = balance_filter(command[index + 1])
    return updated


if __name__ == "__main__":
    import runpy
    from unittest.mock import patch
    import claude_real_video.core as core
    original = core._run

    def compatible_run(command):
        return original(balance_command(command))

    with patch.object(core, "_run", compatible_run):
        runpy.run_path("/worker/crv_worker.py", run_name="__main__")
