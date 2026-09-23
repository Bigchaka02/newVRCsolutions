"""Small, dependency-free minifiers used by build.py.

They are deliberately conservative: comments and layout whitespace go, but
nothing is renamed or reordered, so the output behaves exactly like the
readable sources in src/assets/.
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------
# CSS
# --------------------------------------------------------------------------

# Comments and strings in one pass, so an apostrophe in a comment is not a string.
_CSS_TOKENS = re.compile(r'/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)


def css(source: str) -> str:
    # Park strings (including data: URIs) so the rewrites below can't touch them.
    parked: list[str] = []

    def park(match: re.Match) -> str:
        if match.group(0).startswith("/*"):
            return " "
        parked.append(match.group(0))
        return f"\0{len(parked) - 1}\0"

    out = _CSS_TOKENS.sub(park, source)
    out = re.sub(r"\s+", " ", out)
    # Whitespace is safe to drop around these. Not around ":" in selectors
    # (".a :hover" differs from ".a:hover"), nor "+"/"-" (calc() needs them).
    out = re.sub(r"\s*([{};,>])\s*", r"\1", out)
    out = re.sub(r":\s+", ":", out)
    out = out.replace(";}", "}")
    return re.sub(r"\0(\d+)\0", lambda m: parked[int(m.group(1))], out).strip()


# --------------------------------------------------------------------------
# JavaScript
# --------------------------------------------------------------------------

# A "/" after one of these (or at the start) begins a regex literal, not a division.
_REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_KEYWORDS = ("return", "typeof", "case", "do", "else", "in", "of", "void", "yield", "await")
# Spaces next to these are never needed. "+", "-" and "/" are left alone.
_TIGHT = set("{}()[],;:=<>?&|!")


def js(source: str) -> str:
    """Strip comments, indentation and blank lines; keep every newline that
    separates statements, so automatic semicolon insertion is unaffected."""
    out: list[str] = []
    i, n = 0, len(source)
    # Stack of open template literals; each entry counts "{" depth inside ${ }.
    templates: list[int] = []

    def last_significant() -> str:
        for chunk in reversed(out):
            stripped = chunk.rstrip()
            if stripped:
                return stripped
        return ""

    def regex_allowed() -> bool:
        prev = last_significant()
        if not prev:
            return True
        if prev[-1] in _REGEX_AFTER:
            return True
        word = re.search(r"[A-Za-z_$][\w$]*$", prev)
        return bool(word and word.group(0) in _REGEX_KEYWORDS)

    def read_template_chunk(start: int, j: int) -> int:
        """Copy template text from start, scanning from j, until the closing ` or a ${."""
        while j < n:
            ch = source[j]
            if ch == "\\":
                j += 2
                continue
            if ch == "`":
                out.append(source[start:j + 1])
                templates.pop()
                return j + 1
            if ch == "$" and j + 1 < n and source[j + 1] == "{":
                out.append(source[start:j + 2])
                return j + 2
            j += 1
        raise ValueError("unterminated template literal")

    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""

        if ch == "/" and nxt == "/":
            end = source.find("\n", i)
            i = n if end == -1 else end
            continue
        if ch == "/" and nxt == "*":
            end = source.find("*/", i + 2)
            if end == -1:
                raise ValueError("unterminated block comment")
            i = end + 2
            continue
        if ch in "\"'":
            j = i + 1
            while source[j] != ch:
                j += 2 if source[j] == "\\" else 1
            out.append(source[i:j + 1])
            i = j + 1
            continue
        if ch == "`":
            templates.append(0)
            i = read_template_chunk(i, i + 1)
            continue
        if templates and ch == "{":
            templates[-1] += 1
        if templates and ch == "}":
            if templates[-1] == 0:
                i = read_template_chunk(i, i + 1)
                continue
            templates[-1] -= 1
        if ch == "/" and regex_allowed():
            j, in_class = i + 1, False
            while True:
                c = source[j]
                if c == "\\":
                    j += 2
                    continue
                if c == "[":
                    in_class = True
                elif c == "]":
                    in_class = False
                elif c == "/" and not in_class:
                    break
                j += 1
            j += 1
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1  # flags
            out.append(source[i:j])
            i = j
            continue
        if ch in " \t\r\n":
            j = i
            while j < n and source[j] in " \t\r\n":
                j += 1
            gap = source[i:j]
            prev = last_significant()
            following = source[j] if j < n else ""
            if not prev or not following:
                pass
            elif "\n" in gap:
                out.append("\n")
            elif prev[-1] in _TIGHT or following in _TIGHT:
                pass
            else:
                out.append(" ")
            i = j
            continue
        out.append(ch)
        i += 1

    text = "".join(out)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{2,}", "\n", text).strip() + "\n"


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

_KEEP_HTML = re.compile(r"(<(pre|textarea|script)\b.*?</\2>)", re.S | re.I)


def html(source: str) -> str:
    """Drop indentation, blank lines and comments. Inline spacing is kept, so
    text renders exactly as before; <pre>, <textarea> and <script> are untouched."""
    parts = _KEEP_HTML.split(source)
    out = []
    # split() with two groups yields: text, whole-match, tag-name, text, ...
    for index in range(0, len(parts), 3):
        text = re.sub(r"<!--(?!\[).*?-->", "", parts[index], flags=re.S)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        out.append(re.sub(r"\n{2,}", "\n", text))
        if index + 1 < len(parts):
            out.append(parts[index + 1])
    return "".join(out).strip() + "\n"
