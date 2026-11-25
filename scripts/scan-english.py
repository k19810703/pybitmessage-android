#!/usr/bin/env python3
"""Report user-visible strings that are not routed through the translator.

    python3 scripts/scan-english.py            # human readable
    python3 scripts/scan-english.py --strict   # exit 1 when anything is found

M6.4.3 asks for a scan whose result is empty. "User visible" here means:

* ``.kv`` values of ``text:`` / ``hint_text:`` / ``title:`` that are quoted
  literals and are **not** wrapped in ``app.tr._(...)``;
* Python string literals passed to ``Label(``/``Button(``/``TextInput(`` as
  ``text=``/``hint_text=``.

Deliberately ignored: ids, colours, font names, BM- address examples, pure
numbers/ports (``'9050'``), ``none``/``true``/``false`` (config values), and
anything already inside a comment.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
KV_DIR = os.path.join(REPO, 'PyBitmessage', 'src', 'bitmessagekivy', 'kv')
PY_DIR = os.path.join(REPO, 'PyBitmessage', 'src', 'bitmessagekivy')

#: value positions that end up rendered to the user
KV_RE = re.compile(
    r"^\s*(?:hint_text|text|title|label_text)\s*:\s*(?P<value>.+?)\s*$")

#: Screens that exist in the tree but can no longer be reached: the drawer entry
#: for the upstream "Payment plan" / credits mock (Google Play / PayPal / BTC)
#: was removed in M6.2.1 because this product has no accounts, no payments and
#: no external services. The files stay for now (M6.5 cleans them up) and are
#: reported separately so the cleanup cannot hide behind "the scan is green".
DEAD_SCREENS = {'payment.kv', 'credits.kv'}
CJK = re.compile(r'[\u4e00-\u9fff]')

#: things that are obviously not prose
SKIP_VALUES = {
    'none', 'true', 'false', 'None', 'True', 'False', '', ' ',
}
SKIP_PATTERN = re.compile(
    r"^(?:[\d.:#%\-+ ]+|BM-\S*|https?://\S+|[a-z_]+)$")
#: Kivy markup / f-strings / expressions are not literal prose
EXPRESSION = re.compile(r"[\[\]{}$]|app\.|\bself\b|\.kv\b|%\(|=\s*")


def _is_literal(value):
    """Return the bare string when *value* is a plain quoted literal."""
    value = value.strip()
    for quote in ("'", '"'):
        if len(value) >= 2 and value.startswith(quote) and value.endswith(quote):
            inner = value[1:-1]
            if quote in inner:
                return None      # concatenation or escapes: give up
            return inner
    return None


def scan_kv(path):
    findings = []
    with open(path, encoding='utf-8') as handle:
        for lineno, raw in enumerate(handle, 1):
            line = raw.rstrip('\n')
            if line.lstrip().startswith('#'):
                continue
            match = KV_RE.match(line)
            if not match:
                continue
            value = match.group('value')
            if value.startswith('app.tr._'):
                continue
            literal = _is_literal(value)
            if literal is None:
                continue
            if literal in SKIP_VALUES or SKIP_PATTERN.match(literal):
                continue
            if not re.search(r'[A-Za-z]{2,}', literal) or CJK.search(literal):
                continue          # numbers/ids, or already Chinese
            findings.append((os.path.relpath(path, REPO), lineno, literal))
    return findings


def scan_py(path):
    findings = []
    with open(path, encoding='utf-8') as handle:
        for lineno, raw in enumerate(handle, 1):
            line = raw.strip()
            if line.startswith('#') or 'app.tr._' in line:
                continue
            for kw in ('text=', 'hint_text=', 'title='):
                index = line.find(kw)
                if index < 0:
                    continue
                rest = line[index + len(kw):]
                literal = _is_literal(rest.rstrip('),').strip())
                if literal is None or literal in SKIP_VALUES:
                    continue
                if not re.search(r'[A-Za-z]{2,}', literal) or CJK.search(literal):
                    continue
                findings.append((os.path.relpath(path, REPO), lineno, literal))
    return findings


def _translation_keys():
    """Keys of the ZH dictionary in mpybit.py (parsed, not imported)."""
    import ast
    path = os.path.join(PY_DIR, 'mpybit.py')
    tree = ast.parse(open(path, encoding='utf-8').read())
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
    return keys


def _unescape(text):
    """Turn ``\\n``/``\\t`` in a .kv literal into the characters they mean.

    Kivy processes those escapes, and so does ``ast`` when it parses the
    dictionary, so a source-level comparison needs the same treatment.
    """
    if '\\' not in text:
        return text
    try:
        return text.encode('latin-1', 'backslashreplace').decode(
            'unicode_escape')
    except Exception:  # noqa: BLE001 - non-ASCII literals keep their form
        return text.replace('\\n', '\n').replace('\\t', '\t')


WRAPPED_RE = re.compile(r"app\.tr\._\(\s*([\"'])(?P<text>.+?)\1\s*\)")


def find_missing_translations(keys):
    """``app.tr._('x')`` whose 'x' is not in the dictionary -> still English."""
    missing = []
    for root in (KV_DIR, PY_DIR):
        for name in sorted(os.listdir(root)):
            if not (name.endswith('.kv') or name.endswith('.py')):
                continue
            path = os.path.join(root, name)
            for lineno, line in enumerate(open(path, encoding='utf-8'), 1):
                if line.lstrip().startswith('#'):
                    continue
                for match in WRAPPED_RE.finditer(line):
                    text = match.group('text')
                    if text in keys or _unescape(text) in keys:
                        continue
                    # ports, hostnames, numbers and string concatenation are
                    # configuration values, not prose to translate
                    if (text in SKIP_VALUES or SKIP_PATTERN.match(text)
                            or '" +' in text or "+ root." in text
                            or not re.search(r'[A-Za-z]{3,}', text)):
                        continue
                    missing.append((os.path.relpath(path, REPO), lineno, text))
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict', action='store_true')
    args = parser.parse_args()

    findings = []
    dead = []
    for name in sorted(os.listdir(KV_DIR)):
        if not name.endswith('.kv'):
            continue
        target = dead if name in DEAD_SCREENS else findings
        target.extend(scan_kv(os.path.join(KV_DIR, name)))
    for name in sorted(os.listdir(PY_DIR)):
        if name.endswith('.py'):
            findings.extend(scan_py(os.path.join(PY_DIR, name)))

    if dead:
        print('⛔ 不可达页面（上游遗留，待删除，不计入验收）：')
        for path, lineno, literal in dead:
            print('  %-46s :%-4d %r' % (path, lineno, literal))
        print('')

    missing = find_missing_translations(_translation_keys())
    if missing:
        print('⚠️  已包 app.tr._() 但字典里没有对应中文（线上会回退英文）：')
        for path, lineno, text in missing:
            print('  %-46s :%-4d %r' % (path, lineno, text[:60]))
        print('')

    if not findings and not missing:
        print('✅ 可达界面里没有未翻译的用户可见英文'
              '（不可达页面 %d 处，见上）' % len(dead))
        return 0

    print('%d 处未走翻译的用户可见英文：\n' % len(findings))
    for path, lineno, literal in findings:
        print('  %-46s :%-4d %r' % (path, lineno, literal))
    return 1 if (args.strict and (findings or missing)) else 0


if __name__ == '__main__':
    sys.exit(main())
