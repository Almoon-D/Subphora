"""Turn the template into a project, once: names, author, GitHub user and dates.

Usage::

    python3 scripts/init_project.py <name> [--author "Your Name"] [--github-user <user>]

``<name>`` is the Python package name: lowercase letters, digits and underscores. The script
rewrites every tracked text file, renames ``src/myproject``, removes the template's usage
section from the README, dates the inherited decisions today, reports any placeholder left and
deletes itself. Session 00 runs it (docs/sessions/00-plan.md).
"""

import argparse
import datetime as dt
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

PLACEHOLDER = "myproject"
NAME_RE = re.compile(r"[a-z][a-z0-9_]*")
USAGE_SECTION_RE = re.compile(r"^## Cómo usar esta plantilla.*?(?=^## )", re.MULTILINE | re.DOTALL)
DATE_LINE_RE = re.compile(r"^- Date: \d{4}-\d{2}-\d{2}", re.MULTILINE)
INHERITED_DECISIONS = ("0001-repository-from-template.md", "0002-template-review.md")
LEFTOVERS = (
    "myproject",
    "Your Name",
    "<tu-usuario>",
    "One sentence: what this project does and for whom.",
    "Una frase: qué hace y para quién.",
)


def tracked_files(root: Path) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=root, check=True, capture_output=True, text=True
    ).stdout
    return [root / line for line in out.splitlines() if line]


def rewrite(path: Path, transform: Callable[[str], str]) -> None:
    text = path.read_text(encoding="utf-8")
    new = transform(text)
    if new != text:
        path.write_text(new, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("name")
    parser.add_argument("--author")
    parser.add_argument("--github-user")
    args = parser.parse_args()
    if not NAME_RE.fullmatch(args.name):
        print(f"{args.name!r}: use lowercase letters, digits and underscores", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1]
    this = Path(__file__).resolve()
    replacements = {PLACEHOLDER: args.name}
    if args.author:
        replacements["Your Name"] = args.author
    if args.github_user:
        replacements["<tu-usuario>"] = args.github_user

    files = [p for p in tracked_files(root) if p.resolve() != this and p.is_file()]
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new = text
        for old, value in replacements.items():
            new = new.replace(old, value)
        if new != text:
            path.write_text(new, encoding="utf-8")

    rewrite(root / "README.md", lambda t: USAGE_SECTION_RE.sub("", t, count=1))
    today = dt.date.today().isoformat()
    for decision in INHERITED_DECISIONS:
        rewrite(
            root / "docs" / "decisions" / decision,
            lambda t: DATE_LINE_RE.sub(f"- Date: {today}", t, count=1),
        )
    (root / "src" / PLACEHOLDER).rename(root / "src" / args.name)
    this.unlink()

    old_src, new_src = f"src/{PLACEHOLDER}/", f"src/{args.name}/"
    current = [
        root / str(path.relative_to(root)).replace(old_src, new_src, 1)
        for path in tracked_files(root)
    ]
    left = [
        f"{path.relative_to(root)}: {marker}"
        for path in current
        if path.is_file() and path.suffix not in {".lock"}
        for marker in LEFTOVERS
        if marker in path.read_text(encoding="utf-8", errors="ignore")
    ]
    print(f"Renamed to {args.name}. Next: uv lock && make check, then commit.")
    if left:
        print("Placeholders left (fill them in):\n  " + "\n  ".join(left))
    return 0


if __name__ == "__main__":
    sys.exit(main())
