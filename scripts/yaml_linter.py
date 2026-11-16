#!/usr/bin/env python3
"""
Recursively applies yamllint to all YAML files under a selected directory,
with an optional auto-fix pass for common fixable violations.

Usage:
    python yaml_linter.py [directory] [options]

Requirements:
    pip install yamllint
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

YAML_EXTENSIONS = {".yaml", ".yml"}


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def resolve_roots(pattern: str) -> list[Path]:
    """
    Resolve a path argument into a list of existing directories.

    Handles three cases:
      1. Plain directory path     → [Path(pattern)]
      2. Shell glob pattern       → all matching directories (e.g. /etc/device*/arch)
      3. Glob with no matches     → error

    The pattern is always interpreted relative to the filesystem root so
    absolute globs like /etc/device*/arch work correctly on all platforms.
    Uses Python's pathlib.Path.glob on the parent portion, then filters
    for directories matching the final component(s).
    """
    import glob as _glob

    # If no wildcard characters, treat as a plain path
    if not any(c in pattern for c in ("*", "?", "[")):
        p = Path(pattern)
        if not p.exists():
            print(f"Error: Path '{pattern}' does not exist.", file=sys.stderr)
            sys.exit(2)
        if not p.is_dir():
            print(f"Error: '{pattern}' is not a directory.", file=sys.stderr)
            sys.exit(2)
        return [p.resolve()]

    # Expand the glob (recursive=True supports **)
    matches = [Path(m) for m in _glob.glob(pattern, recursive=True)]
    dirs = sorted(m.resolve() for m in matches if m.is_dir())

    if not dirs:
        # Maybe the shell already expanded it and passed multiple args —
        # nothing matched at the Python level either.
        print(
            f"Error: Glob pattern '{pattern}' matched no directories.",
            file=sys.stderr,
        )
        sys.exit(2)

    return dirs


def find_yaml_files(roots: list[Path]) -> list[Path]:
    """Recursively find all YAML files under one or more root directories."""
    seen: set[Path] = set()
    files: list[Path] = []
    for root in roots:
        for p in root.rglob("*"):
            rp = p.resolve()
            if p.is_file() and p.suffix.lower() in YAML_EXTENSIONS and rp not in seen:
                seen.add(rp)
                files.append(p)
    return sorted(files)


# ---------------------------------------------------------------------------
# Linting
# ---------------------------------------------------------------------------

def run_yamllint(file: Path, config: str | None, strict: bool, quiet: bool) -> tuple[int, list[str]]:
    """Run yamllint on a single file. Returns (returncode, output_lines)."""
    cmd = ["yamllint", "--format", "parsable"]
    if config:
        cmd += ["-c", config]
    if strict:
        cmd.append("-s")
    if quiet:
        cmd.append("-q")
    cmd.append(str(file))

    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = (proc.stdout + proc.stderr).strip()
    return proc.returncode, output.splitlines() if output else []


def lint_files(
    files: list[Path],
    config: str | None,
    strict: bool,
    quiet: bool,
) -> dict[str, list[str]]:
    """Lint all files. Returns {filepath: [issue_line, ...]} for files with issues."""
    results: dict[str, list[str]] = {}
    for file in files:
        rc, lines = run_yamllint(file, config, strict, quiet)
        if rc != 0 and lines:
            results[str(file)] = lines
    return results


def parse_issues(lines: list[str]) -> list[dict]:
    """
    Parse yamllint parsable-format lines into structured dicts.
    Format: filepath:line:col: [level] message (rule-name)
    """
    pattern = re.compile(r".+:(\d+):(\d+): \[(error|warning)\] (.+) \((.+)\)")
    issues = []
    for line in lines:
        m = pattern.match(line)
        if m:
            issues.append({
                "line": int(m.group(1)),
                "col": int(m.group(2)),
                "level": m.group(3),
                "message": m.group(4),
                "rule": m.group(5),
            })
    return issues


# ---------------------------------------------------------------------------
# Auto-fix helpers (text-level)
# ---------------------------------------------------------------------------

def fix_trailing_spaces(text_lines: list[str]) -> list[str]:
    """Remove trailing whitespace from every line."""
    return [line.rstrip() for line in text_lines]


def fix_new_line_at_end(text_lines: list[str]) -> list[str]:
    """Ensure the file ends with exactly one blank entry (→ trailing newline)."""
    while text_lines and text_lines[-1] == "":
        text_lines.pop()
    text_lines.append("")  # becomes trailing \n when joined with \n
    return text_lines


def fix_empty_lines(text_lines: list[str], max_empty: int = 1) -> list[str]:
    """Collapse runs of more than max_empty consecutive blank lines."""
    result: list[str] = []
    blank_count = 0
    for line in text_lines:
        if line == "":
            blank_count += 1
            if blank_count <= max_empty:
                result.append(line)
        else:
            blank_count = 0
            result.append(line)
    return result


def fix_indentation(text_lines: list[str], indent_width: int = 2) -> list[str]:
    """Convert leading tabs to spaces (each tab → indent_width spaces)."""
    fixed = []
    for line in text_lines:
        if line.startswith("\t"):
            stripped = line.lstrip("\t")
            tab_count = len(line) - len(stripped)
            line = " " * (tab_count * indent_width) + stripped
        fixed.append(line)
    return fixed


def fix_colons(text_lines: list[str]) -> list[str]:
    """
    Ensure a space follows colons in key: value pairs.
    Skips URLs (://) and colons already followed by whitespace.
    """
    fixed = []
    for line in text_lines:
        new_line = re.sub(r'(?<!["\']):(?!//|[\s\n])', ': ', line)
        fixed.append(new_line)
    return fixed


def fix_truthy(text_lines: list[str]) -> list[str]:
    """
    Replace non-standard truthy values (yes/no/on/off) with true/false.
    Only replaces bare scalar values after a mapping key (': ').
    """
    pattern = re.compile(
        r'^(\s*[\w\-]+\s*:\s*)(yes|no|on|off)\s*$',
        re.IGNORECASE,
    )
    fixed = []
    for line in text_lines:
        m = pattern.match(line)
        if m:
            val = m.group(2).lower()
            replacement = "true" if val in ("yes", "on") else "false"
            line = m.group(1) + replacement
        fixed.append(line)
    return fixed


def fix_document_start(text_lines: list[str]) -> list[str]:
    """Remove bare '---' document-start markers at the top if they cause issues."""
    # yamllint's document-start rule warns when '---' is missing or present
    # depending on config; we just ensure a single leading '---' when present
    # is not duplicated.
    seen = False
    fixed = []
    for line in text_lines:
        if line.strip() == "---":
            if not seen:
                seen = True
                fixed.append(line)
            # drop duplicate document-start markers
        else:
            fixed.append(line)
    return fixed


# ---------------------------------------------------------------------------
# Line-length fixer
# ---------------------------------------------------------------------------

# Regex helpers used by fix_line_length
_RE_MAPPING_KEY   = re.compile(r'^(\s*)([\w\-./]+\s*:\s+)(.*)')   # key: long value
_RE_LIST_ITEM     = re.compile(r'^(\s*-\s+)(.*)')                  # - long value
_RE_FLOW_SEQ      = re.compile(r'^(\s*[\w\-./]+\s*:\s*)(\[.*\])\s*$')  # key: [a, b, c]
_RE_FLOW_MAP      = re.compile(r'^(\s*[\w\-./]+\s*:\s*)(\{.*\})\s*$')  # key: {a: 1}
_RE_COMMENT       = re.compile(r'^\s*#')                           # comment line


def _indent_of(line: str) -> str:
    """Return the leading whitespace of a line."""
    return line[: len(line) - len(line.lstrip())]


def _wrap_scalar(value: str, prefix: str, body_indent: str, max_len: int) -> list[str]:
    """
    Wrap a plain scalar string value that is too long.

    Emits a YAML block scalar:
      key: >-
        wrapped line one
        wrapped line two

    prefix     = full text before the value  (e.g. "  description: ")
    body_indent = indentation for every body line  (e.g. "    ")
    max_len    = max allowed line length
    """
    import textwrap

    # Strip surrounding quotes if present so we can re-emit cleanly
    stripped = value
    if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
        stripped = value[1:-1]

    # >- folds single newlines to spaces (good for long single-line strings)
    # |- keeps literal newlines (good for pre-formatted multiline strings)
    block_indicator = "|-" if "\n" in stripped else ">-"

    # Available width for each body line
    body_width = max(40, max_len - len(body_indent))

    if "\n" in stripped:
        body_lines = stripped.splitlines()
    else:
        body_lines = textwrap.wrap(stripped, width=body_width) or [stripped]

    result = [f"{prefix}{block_indicator}"]
    for bl in body_lines:
        result.append(f"{body_indent}{bl}")
    return result


def _wrap_flow_collection(
    line_prefix: str,
    collection: str,
    indent: str,
    max_len: int,
    is_seq: bool,
) -> list[str]:
    """
    Convert a flow sequence [a, b, c] or flow map {k: v} that is too long
    into a block collection spanning multiple lines.

    is_seq=True  →  block sequence (- item per line)
    is_seq=False →  block mapping (key: value per line)
    """
    inner = collection.strip()[1:-1]  # strip [ ] or { }
    # Split on commas that are not inside nested brackets/braces/quotes
    items = _split_flow_items(inner)
    child_indent = indent + "  "

    # Strip trailing space/colon from the key prefix for clean output
    clean_prefix = line_prefix.rstrip()

    if is_seq:
        result = [clean_prefix]
        for item in items:
            result.append(f"{child_indent}- {item.strip()}")
    else:
        # flow map {k: v, k2: v2} → block map
        result = [clean_prefix]
        for item in items:
            result.append(f"{child_indent}{item.strip()}")
    return result


def _split_flow_items(s: str) -> list[str]:
    """
    Split a comma-separated flow collection string respecting nested
    brackets, braces, and quoted strings.
    """
    items: list[str] = []
    depth = 0
    buf: list[str] = []
    in_quote: str = ""
    for ch in s:
        if in_quote:
            buf.append(ch)
            if ch == in_quote:
                in_quote = ""
        elif ch in ('"', "'"):
            in_quote = ch
            buf.append(ch)
        elif ch in ("[", "{"):
            depth += 1
            buf.append(ch)
        elif ch in ("]", "}"):
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        items.append("".join(buf).strip())
    return [i for i in items if i]


def _fix_long_line(line: str, max_len: int) -> list[str]:
    """
    Attempt to wrap a single line that exceeds max_len.
    Returns a list of replacement lines (may be just [line] if no fix applied).
    """
    # Never touch comment lines — wrapping a comment changes semantics
    if _RE_COMMENT.match(line):
        return [line]

    # Already within limit (shouldn't happen but be safe)
    if len(line) <= max_len:
        return [line]

    indent = _indent_of(line)

    # ── Case 1: flow sequence  key: [a, b, c, ...]
    m = _RE_FLOW_SEQ.match(line)
    if m:
        prefix, collection = m.group(1), m.group(2)
        wrapped = _wrap_flow_collection(prefix, collection, indent, max_len, is_seq=True)
        if wrapped != [line]:
            return wrapped

    # ── Case 2: flow mapping  key: {k: v, ...}
    m = _RE_FLOW_MAP.match(line)
    if m:
        prefix, collection = m.group(1), m.group(2)
        wrapped = _wrap_flow_collection(prefix, collection, indent, max_len, is_seq=False)
        if wrapped != [line]:
            return wrapped

    # ── Case 3: plain scalar mapping  key: long string value
    m = _RE_MAPPING_KEY.match(line)
    if m:
        prefix_indent, key_part, value = m.group(1), m.group(2), m.group(3)
        # Only wrap plain scalars and quoted strings, not anchors/aliases/etc.
        if value and not value.startswith(("&", "*", "|", ">", "{")):
            # Skip values that are a single unbreakable token (URLs, file paths, hashes)
            if " " not in value.strip():
                return [line]
            full_prefix = prefix_indent + key_part
            body_indent = prefix_indent + "  "
            wrapped = _wrap_scalar(value, full_prefix, body_indent, max_len)
            if len(wrapped) > 1:
                return wrapped

    # ── Case 4: list item  - long string value
    m = _RE_LIST_ITEM.match(line)
    if m:
        list_prefix, value = m.group(1), m.group(2)   # list_prefix = "    - "
        if value and not value.startswith(("&", "*", "|", ">")):
            if " " not in value.strip():
                return [line]
            body_indent = " " * len(list_prefix)
            wrapped = _wrap_scalar(value, list_prefix, body_indent, max_len)
            if len(wrapped) > 1:
                return wrapped

    # ── Case 5: bare indented text (block scalar body line that is itself too long)
    # These lines have leading spaces and plain prose — word-wrap in place.
    if indent and line.strip() and not line.strip().startswith(("-", "{", "[", "&", "*", "|", ">")):
        import textwrap
        body_width = max(40, max_len - len(indent))
        words = line.strip()
        # Skip single unbreakable tokens (URLs, paths, hashes)
        if " " not in words:
            return [line]
        wrapped_words = textwrap.wrap(words, width=body_width)
        if len(wrapped_words) > 1:
            return [f"{indent}{w}" for w in wrapped_words]

    # No structural fix possible — return unchanged
    return [line]


def fix_line_length(
    text_lines: list[str],
    max_len: int = 120,
) -> list[str]:
    """
    Wrap lines that exceed max_len characters.

    Handles:
      • Plain scalar values (key: very long string)  → YAML block scalar (>-)
      • Quoted scalar values                          → YAML block scalar (>-)
      • Flow sequences  (key: [a, b, c])             → block sequence
      • Flow mappings   (key: {k: v})                → block mapping
      • List item values (- very long string)        → block scalar
      • Comment lines and structural lines           → left unchanged

    Runs up to 3 passes so that lines introduced by the first pass
    (e.g. long block-scalar body lines) are also wrapped.
    """
    for _ in range(3):
        result: list[str] = []
        changed = False
        for line in text_lines:
            if len(line) > max_len:
                fixed = _fix_long_line(line, max_len)
                result.extend(fixed)
                if fixed != [line]:
                    changed = True
            else:
                result.append(line)
        text_lines = result
        if not changed:
            break
    return text_lines


# ---------------------------------------------------------------------------
# Rule → fixer mapping
# ---------------------------------------------------------------------------

FIXABLE_RULE_MAP: dict[str, callable] = {
    "trailing-spaces":        fix_trailing_spaces,
    "new-line-at-end-of-file": fix_new_line_at_end,
    "empty-lines":            fix_empty_lines,
    "indentation":            fix_indentation,
    "colons":                 fix_colons,
    "truthy":                 fix_truthy,
    "document-start":         fix_document_start,
    "line-length":            fix_line_length,
}


# ---------------------------------------------------------------------------
# Auto-fix orchestration
# ---------------------------------------------------------------------------

def _extract_max_len(issues: list[dict], default: int = 120) -> int:
    """
    Pull the configured max line length from yamllint's message text.
    yamllint emits: "line too long (N > M characters)"
    Returns M if found, otherwise default.
    """
    pat = re.compile(r'line too long \(\d+ > (\d+) characters?\)')
    for issue in issues:
        if issue["rule"] == "line-length":
            m = pat.search(issue["message"])
            if m:
                return int(m.group(1))
    return default


def autofix_file(file: Path, issues: list[dict], backup: bool) -> tuple[bool, set[str]]:
    """
    Apply all fixable rules to a file in-place.
    Returns (was_changed, set_of_fixed_rules).
    """
    rules_present = {i["rule"] for i in issues}
    rules_to_fix = rules_present & FIXABLE_RULE_MAP.keys()

    if not rules_to_fix:
        return False, set()

    original = file.read_text(encoding="utf-8")
    lines = original.splitlines()

    for rule in rules_to_fix:
        if rule == "line-length":
            max_len = _extract_max_len(issues)
            lines = fix_line_length(lines, max_len=max_len)
        else:
            lines = FIXABLE_RULE_MAP[rule](lines)

    fixed_text = "\n".join(lines)
    # Guarantee single trailing newline regardless of what fixers produced
    fixed_text = fixed_text.rstrip("\n") + "\n"

    if fixed_text == original:
        return False, set()

    if backup:
        shutil.copy2(file, file.with_suffix(file.suffix + ".bak"))

    file.write_text(fixed_text, encoding="utf-8")
    return True, rules_to_fix


def autofix_pass(
    files: list[Path],
    issues_map: dict[str, list[str]],
    backup: bool,
) -> dict[str, set[str]]:
    """
    Run auto-fix on every file that has fixable issues.
    Returns {filepath: set_of_fixed_rules} for files that were actually changed.
    """
    fixed_summary: dict[str, set[str]] = {}
    for filepath, raw_lines in issues_map.items():
        issues = parse_issues(raw_lines)
        changed, fixed_rules = autofix_file(Path(filepath), issues, backup)
        if changed:
            fixed_summary[filepath] = fixed_rules
    return fixed_summary


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

LEVEL_ICON = {"error": "🔴", "warning": "🟡"}
CONTEXT_LINES = 2  # source lines shown above/below the offending line


def _read_source_lines(filepath: str) -> list[str]:
    """Read file lines (1-indexed access via [lineno-1]). Returns [] on failure."""
    try:
        return Path(filepath).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _format_issue_block(issue: dict, src: list[str]) -> list[str]:
    """
    Format a single issue as a multi-line block:

        🔴 line 12, col 5 · [error] trailing spaces  (trailing-spaces)
           10 │   key: value
           11 │
        ▶  12 │   bad line with spaces   
              │       ^
           13 │   next: line
    """
    lineno: int = issue["line"]
    col: int = issue["col"]
    level: str = issue["level"]
    message: str = issue["message"]
    rule: str = issue["rule"]
    icon = LEVEL_ICON.get(level, "•")

    out: list[str] = []
    out.append(f"  {icon}  line {lineno}, col {col}  ·  [{level}] {message}  ({rule})")

    if not src:
        return out

    # Snippet: CONTEXT_LINES before and after, with the error line highlighted
    start = max(1, lineno - CONTEXT_LINES)
    end = min(len(src), lineno + CONTEXT_LINES)
    gutter = len(str(end))  # width for line-number column

    for i in range(start, end + 1):
        raw = src[i - 1]  # file lines are 0-indexed in the list
        # Replace tabs with spaces for column-accurate display
        display_line = raw.replace("\t", "    ")
        if i == lineno:
            out.append(f"  {'▶':>{gutter+1}}  {i:{gutter}d} │ {display_line}")
            # Column pointer (clamp to visible width)
            pointer_col = max(1, col) - 1
            out.append(f"  {'':>{gutter+1}}  {'':{gutter}s}   {'':>{pointer_col}}^")
        else:
            out.append(f"  {'':>{gutter+1}}  {i:{gutter}d} │ {display_line}")

    return out


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(
    all_files: list[Path],
    issues_before: dict[str, list[str]],
    issues_after: dict[str, list[str]] | None,
    fixed_summary: dict[str, set[str]] | None,
) -> int:
    total = len(all_files)
    autofix_ran = issues_after is not None

    print("\n" + "=" * 60)
    print("  YAML Lint Report")
    print("=" * 60)

    if autofix_ran and fixed_summary:
        print(f"\n🔧  Auto-fixed {len(fixed_summary)} file(s):")
        for fp, rules in fixed_summary.items():
            print(f"    {fp}")
            print(f"      Rules applied: {', '.join(sorted(rules))}")

    final_issues = issues_after if autofix_ran else issues_before

    if not final_issues:
        qualifier = " after auto-fix" if autofix_ran else ""
        print(f"\n✅  All {total} file(s) passed linting{qualifier}.\n")
        return 0

    remaining = len(final_issues)
    note = " (manual fix required)" if autofix_ran else ""
    print(f"\n❌  {remaining} file(s) still have issues{note}:\n")

    for filepath, raw_lines in final_issues.items():
        print(f"  📄  {filepath}")
        src = _read_source_lines(filepath)
        issues = parse_issues(raw_lines)

        for issue in issues:
            for line in _format_issue_block(issue, src):
                print(line)
            print()

    passed = total - remaining
    print("-" * 60)
    print(f"  Total      : {total}")
    print(f"  Passed     : {passed}")
    print(f"  Failed     : {remaining}")
    if autofix_ran and fixed_summary:
        auto_resolved = len(issues_before) - remaining
        print(f"  Auto-fixed : {auto_resolved}")
    print("-" * 60 + "\n")

    if autofix_ran and final_issues:
        unfixable = set()
        for raw_lines in final_issues.values():
            for issue in parse_issues(raw_lines):
                if issue["rule"] not in FIXABLE_RULE_MAP:
                    unfixable.add(issue["rule"])
        if unfixable:
            print("  Rules requiring manual fix: " + ", ".join(sorted(unfixable)))
            print()

    return 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recursively lint all YAML files in a directory (or glob pattern) "
            "using yamllint, with optional auto-fix for common issues."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Auto-fixable rules:
  {chr(10)+'  '.join(sorted(FIXABLE_RULE_MAP))}

Path / glob examples:
  python yaml_linter.py ./configs
  python yaml_linter.py '/etc/device*/arch'
  python yaml_linter.py 'services/**/config'
  python yaml_linter.py '/opt/app-*/conf' --fix
  python yaml_linter.py '/etc/device*/arch' --fix --no-backup -c .yamllint.yml

Notes:
  • Quote glob patterns to prevent the shell from expanding them prematurely.
  • ** matches any number of path segments (recursive wildcard).
  • Only directories matched by the pattern are scanned; plain files are skipped.
        """,
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help=(
            "Directory path or glob pattern to scan. "
            "Wildcards *, ?, ** and [...] are supported. "
            "Quote the pattern to prevent premature shell expansion. "
            "Default: current directory."
        ),
    )
    parser.add_argument(
        "-c", "--config",
        metavar="CONFIG",
        help="Path to a custom yamllint config file",
    )
    parser.add_argument(
        "-s", "--strict",
        action="store_true",
        help="Return non-zero exit code on warnings as well as errors",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Output only error-level problems (suppress warnings)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix common issues in-place before reporting",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating .bak backup files when auto-fixing (default: backups on)",
    )
    args = parser.parse_args()

    # Check yamllint is installed
    try:
        subprocess.run(["yamllint", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print(
            "Error: 'yamllint' is not installed.\n"
            "Install it with:  pip install yamllint",
            file=sys.stderr,
        )
        sys.exit(2)

    # Resolve the directory argument — plain path or glob pattern
    roots = resolve_roots(args.directory)

    if len(roots) == 1:
        print(f"Scanning: {roots[0]}")
    else:
        print(f"Glob pattern '{args.directory}' matched {len(roots)} director(ies):")
        for r in roots:
            print(f"  {r}")

    yaml_files = find_yaml_files(roots)

    if not yaml_files:
        print("No YAML files found.")
        sys.exit(0)

    print(f"Found {len(yaml_files)} YAML file(s). Linting...\n")

    # First lint pass
    issues_before = lint_files(yaml_files, args.config, args.strict, args.quiet)

    fixed_summary: dict[str, set[str]] | None = None
    issues_after: dict[str, list[str]] | None = None

    if args.fix and issues_before:
        backup = not args.no_backup
        if backup:
            print("💾  Backup enabled — originals saved as <file>.bak\n")
        print("🔧  Running auto-fix...\n")
        fixed_summary = autofix_pass(yaml_files, issues_before, backup)

        # Second lint pass to show remaining issues
        issues_after = lint_files(yaml_files, args.config, args.strict, args.quiet)
    elif args.fix and not issues_before:
        issues_after = {}
        fixed_summary = {}

    exit_code = print_report(yaml_files, issues_before, issues_after, fixed_summary)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
