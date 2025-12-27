#!/usr/bin/env python3
import argparse
import os
import re
from pathlib import Path

TEMPLATE_EXTS = {".html", ".htm", ".txt"}
PY_EXTS = {".py"}

PATTERNS = [
    # Templates
    ("TEMPLATE_FLOATFORMAT", re.compile(r"\|\s*floatformat\s*:\s*(\d+)")),
    ("TEMPLATE_LOCALIZE", re.compile(r"{%\s*localize\s+on\s*%}|{%\s*localize\s*%}")),
    ("TEMPLATE_L10N", re.compile(r"\|\s*localize\s*")),
    ("TEMPLATE_INTCOMMA", re.compile(r"\|\s*intcomma\s*")),
    ("TEMPLATE_HUMANIZE", re.compile(r"{%\s*load\s+humanize\s*%}")),

    # Python (مؤشرات شائعة لمشاكل الفواصل/التحويل لنص)
    ("PYTHON_FSTRING_COMMA", re.compile(r"f[\"'].*\{[^}]*:,[^}]*\}.*[\"']")),
    ("PYTHON_FORMAT_COMMA", re.compile(r"\.format\([^)]*:,|\{[^}]*:,[^}]*\}")),
    ("PYTHON_LOCALE", re.compile(r"\bimport\s+locale\b|\blocale\.")),
    ("PYTHON_PANDAS_TO_EXCEL", re.compile(r"\.to_excel\s*\(")),
    ("PYTHON_ASTYPE_STR", re.compile(r"\.astype\s*\(\s*str\s*\)")),
    ("PYTHON_STR_DECIMAL", re.compile(r"\bstr\s*\(\s*[^)]+\s*\)")),
]

# تعديلات تلقائية "آمنة نسبيًا" للقوالب:
# - استبدال |floatformat:N بـ |num:N (يعطي نقطة دائمًا)
# - إضافة {% load numfmt %} أعلى القالب إذا كان يستخدم num ولم يكن محمّلًا
RE_FLOATFORMAT = re.compile(r"\|\s*floatformat\s*:\s*(\d+)")
RE_LOAD_NUMFMT = re.compile(r"{%\s*load\s+numfmt\s*%}")
RE_TEMPLATE_TAG_BLOCK = re.compile(r"^\s*({%.*?%}\s*)+", re.DOTALL)

def iter_files(root: Path, include_py=True, include_templates=True):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if include_templates and ext in TEMPLATE_EXTS and "templates" in p.parts:
            yield p
        elif include_py and ext in PY_EXTS:
            yield p

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def write_text_with_backup(p: Path, content: str, make_backup=True):
    if make_backup:
        bak = p.with_suffix(p.suffix + ".bak")
        if not bak.exists():
            bak.write_text(read_text(p), encoding="utf-8")
    p.write_text(content, encoding="utf-8")

def find_matches(text: str):
    hits = []
    for name, rx in PATTERNS:
        for m in rx.finditer(text):
            start = max(0, m.start() - 60)
            end = min(len(text), m.end() + 60)
            snippet = text[start:end].replace("\n", "\\n")
            hits.append((name, m.group(0), snippet))
    return hits

def add_load_numfmt_if_needed(text: str) -> str:
    if "|num:" not in text and "|num " not in text:
        return text
    if RE_LOAD_NUMFMT.search(text):
        return text

    # نحاول إدراج {% load numfmt %} بعد أول كتلة template tags (مثل extends/load)
    m = RE_TEMPLATE_TAG_BLOCK.match(text)
    if m:
        insert_pos = m.end()
        return text[:insert_pos] + "{% load numfmt %}\n" + text[insert_pos:]
    else:
        return "{% load numfmt %}\n" + text

def fix_template(text: str) -> str:
    # 1) floatformat -> num
    text2 = RE_FLOATFORMAT.sub(lambda m: f"|num:{m.group(1)}", text)
    # 2) add load numfmt if needed
    text2 = add_load_numfmt_if_needed(text2)
    return text2

def main():
    ap = argparse.ArgumentParser(description="Audit/auto-fix decimal/thousand separator formatting issues.")
    ap.add_argument("--root", default=".", help="Project root (default: current dir)")
    ap.add_argument("--report", default="decimal_audit_report.txt", help="Report output path")
    ap.add_argument("--fix-templates", action="store_true", help="Auto-fix templates: floatformat -> num and add {% load numfmt %}")
    ap.add_argument("--no-backup", action="store_true", help="Do not create .bak backups")
    ap.add_argument("--skip-py", action="store_true", help="Skip scanning .py files")
    ap.add_argument("--skip-templates", action="store_true", help="Skip scanning template files under templates/")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    make_backup = not args.no_backup

    lines = []
    changed = []

    for f in iter_files(root, include_py=not args.skip_py, include_templates=not args.skip_templates):
        text = read_text(f)
        hits = find_matches(text)
        if hits:
            lines.append(f"\n=== {f} ===")
            for name, token, snippet in hits:
                lines.append(f"- {name}: {token}")
                lines.append(f"  ...{snippet}...")

        if args.fix_templates and ("templates" in f.parts) and (f.suffix.lower() in TEMPLATE_EXTS):
            new_text = fix_template(text)
            if new_text != text:
                write_text_with_backup(f, new_text, make_backup=make_backup)
                changed.append(str(f))

    report_path = Path(args.report).resolve()
    report_path.write_text("\n".join(lines) if lines else "No matches found.\n", encoding="utf-8")

    print(f"[OK] Report written to: {report_path}")
    if args.fix_templates:
        print(f"[OK] Templates changed: {len(changed)}")
        if changed:
            print("    - " + "\n    - ".join(changed))

if __name__ == "__main__":
    main()
