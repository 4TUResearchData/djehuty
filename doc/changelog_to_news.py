#!/usr/bin/env python3
"""Insert the top CHANGELOG.md release into doc/news.tex.

CHANGELOG.md is the source of truth for release notes. The LaTeX
documentation pulls news in via `\\input{news}` from djehuty.tex,
so this script reverse-converts the most recent release block in
CHANGELOG.md to LaTeX and inserts it above the existing first
release in doc/news.tex.

Invoked by `just news` at release time.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

COMMIT_RE = re.compile (
    r"\[[0-9a-f]{4,}\]\(https://github\.com/[^/]+/[^/]+/commit/([0-9a-f]+)\)"
)
RELEASE_RE = re.compile (r"^##\s+\[v([\d.]+)\]\s*$", re.MULTILINE)
SUBSECTION_RE = re.compile (r"^###\s+(.+)\s*$", re.MULTILINE)
HASH_MARK = "\x00"


def inline (text: str) -> str:
    """Markdown links + code spans -> LaTeX `\\href` + `\\code`."""
    text = re.sub (
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f"\\href{{{m.group (2)}}}{{{m.group (1)}}}",
        text,
    )
    return re.sub (r"`([^`]+)`", r"\\code{\1}", text)


def render_item (item_md: str) -> str:
    hashes: list[str] = []
    body = COMMIT_RE.sub (lambda m: hashes.append (m.group (1)) or HASH_MARK, item_md)
    body = re.sub (rf"\s*\((?:{HASH_MARK}(?:,\s*)?)+\)\.?\s*$", "", body).rstrip ()
    if body and not body.endswith ("."):
        body += "."
    body = inline (body)
    if not hashes:
        return f"\\item{{{body}}}"
    joined = ",\n    ".join (f"\\commitLink{{{h}}}" for h in hashes)
    return f"\\item{{{body}\n    ({joined}).}}"


def render_top_release (md_text: str) -> tuple[str, str]:
    """Return (version, latex_block) for the first release in CHANGELOG.md."""
    header = RELEASE_RE.search (md_text)
    if header is None:
        raise SystemExit ("No release section ('## [vX.Y]') found in CHANGELOG.md")
    version = header.group (1)
    nxt = RELEASE_RE.search (md_text, header.end ())
    body = md_text[header.end () : nxt.start () if nxt else len (md_text)]

    subs = list (SUBSECTION_RE.finditer (body))
    intro = (body[:subs[0].start ()] if subs else body).strip ()
    label = "release-" + version.replace (".", "-")
    out = [
        f"\\labelWithConsistentHTMLTag{{{label}}}",
        f"\\section*{{Release notes for \\texttt{{v{version}}}.}}",
        "",
    ]
    for para in re.split (r"\n\s*\n", intro) if intro else ():
        if para.strip ():
            out += ["  " + inline (para.strip ()), ""]
    for idx, sub in enumerate (subs):
        end = subs[idx + 1].start () if idx + 1 < len (subs) else len (body)
        items = [ln[2:].strip () for ln in body[sub.end () : end].splitlines () if ln.startswith ("- ")]
        out += [f"\\subsection*{{{sub.group (1).strip ()}}}", "\\begin{itemize}"]
        out += [render_item (i) for i in items]
        out += ["\\end{itemize}", ""]
    return version, "\n".join (out).rstrip () + "\n"


def main () -> int:
    repo = Path (__file__).resolve ().parent.parent
    changelog = repo / "CHANGELOG.md"
    news = repo / "doc" / "news.tex"

    version, latex = render_top_release (changelog.read_text (encoding="utf-8"))
    label = "release-" + version.replace (".", "-")
    news_text = news.read_text (encoding="utf-8")

    if f"\\labelWithConsistentHTMLTag{{{label}}}" in news_text:
        raise SystemExit (
            f"Release v{version} (label {label}) is already in doc/news.tex; nothing to do."
        )
    anchor = re.search (r"\\labelWithConsistentHTMLTag\{release-", news_text)
    if anchor is None:
        raise SystemExit (
            "Could not find an existing release marker in doc/news.tex. "
            "Expected a line starting with \\labelWithConsistentHTMLTag{release-...}."
        )
    news.write_text (news_text[: anchor.start ()] + latex + "\n" + news_text[anchor.start ():], encoding="utf-8")
    print (f"Inserted release v{version} into doc/news.tex.")
    return 0


if __name__ == "__main__":
    sys.exit (main ())
