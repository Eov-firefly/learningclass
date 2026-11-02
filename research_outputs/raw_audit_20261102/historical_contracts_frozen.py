"""Declared interface contracts. No gold answer is used by stopping decisions."""
import re
import math
from decimal import Decimal, InvalidOperation

MARKER = re.compile(r'(?m)^####[ \t]*')
NUMBER = r'[+-]?(?:\d+)(?:\.\d+)?'
CONTRACTS = {'strict', 'wrapper_balanced_strict', 'closure_tolerant', 'closure_balanced', 'last_marked'}


def strict_answer(text, kind, choices='ABCDE', online=False):
    """Exact frozen v5.1 answer grammar, including the online newline rule."""
    matches = list(MARKER.finditer(text))
    if not matches:
        return None
    value = r'[A-E]' if kind == 'choice' else NUMBER
    ending = r'[ \t]*\r?\n\s*' if online else r'\s*'
    m = re.fullmatch('(' + value + ')' + ending, text[matches[-1].end():])
    prediction = m.group(1) if m else None
    if kind == 'choice' and prediction is not None and prediction not in choices:
        return None
    return prediction


def allowed_choices(prompt):
    m = re.search(r'using ([A-Z]+)\.', prompt)
    if not m:
        raise ValueError('Cannot recover instance-specific allowed choices from prompt')
    return m.group(1)


def same_answer(prediction, gold, kind):
    if prediction is None:
        return False
    if kind == 'numeric':
        try:
            return Decimal(str(prediction)) == Decimal(str(gold))
        except InvalidOperation:
            return False
    return str(prediction) == str(gold)


def marked_value(text, kind, choices='ABCDE'):
    """Last line-start marker; return value, unmatched suffix, value end position."""
    matches = list(MARKER.finditer(text))
    if not matches:
        return None, None, None
    m = matches[-1]
    pattern = NUMBER if kind == 'numeric' else '[A-E]'
    value = re.match(pattern, text[m.end():])
    if value is None:
        return None, None, None
    if kind == 'choice' and value.group() not in choices:
        return None, None, None
    end = m.end() + value.end()
    return value.group(), text[end:], end


def wrapper_balanced(text):
    """Limited wrapper check, NOT a complete Markdown/LaTeX grammar."""
    fences = []
    for line in text.splitlines():
        m = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        if not m:
            continue
        token, rest = m.groups()
        if fences:
            if token[0] == fences[-1][0] and len(token) >= len(fences[-1]) and not rest.strip():
                fences.pop()
        else:
            fences.append(token)
    if fences:
        return False
    for left, right in [(r'\[', r'\]'), (r'\(', r'\)')]:
        depth = 0
        for match in re.finditer(re.escape(left) + '|' + re.escape(right), text):
            depth += 1 if match.group() == left else -1
            if depth < 0:
                return False
        if depth:
            return False
    if len(re.findall(r'(?<!\\)\$\$', text)) % 2:
        return False
    stack = []
    for action, env in re.findall(r'\\(begin|end)\{([^}]+)\}', text):
        if action == 'begin':
            stack.append(env)
        elif not stack or stack.pop() != env:
            return False
    return not stack


def parse(text, kind, choices='ABCDE', eos=False, contract='strict'):
    if kind not in {'numeric', 'choice'}:
        raise ValueError(kind)
    if contract not in CONTRACTS:
        raise ValueError(contract)
    if contract in {'strict', 'wrapper_balanced_strict'}:
        value = strict_answer(text, kind, choices, online=not eos)
        if contract == 'wrapper_balanced_strict' and not wrapper_balanced(text):
            return None
        return value
    value, suffix, end = marked_value(text, kind, choices)
    if value is None:
        return None
    if contract == 'last_marked':
        # Diagnostic extraction, not a semantic endpoint or original legacy parser.
        if suffix and not (suffix[0].isspace() or suffix.startswith((r'\]', r'\)', '$', '`'))):
            return None
        return value
    if contract in {'closure_tolerant','closure_balanced'}:
        # Only syntactic closing tokens after the value; does not accept prose.
        tail = re.sub(r'\\end\{[^}]+\}|\\\]|\\\)|\$\$|`{3,}|~{3,}|\s+', '', suffix)
        if tail:
            return None
    # A cap without a newline after the answer is not a completion certificate.
    if not eos and '\n' not in suffix:
        return None
    if contract in {'wrapper_balanced_strict','closure_balanced'} and not wrapper_balanced(text):
        return None
    return value


def score(text, kind, gold, choices='ABCDE', eos=False, contract='strict'):
    pred = parse(text, kind, choices, eos, contract)
    return {'prediction': pred, 'valid': pred is not None,
            'correct': same_answer(pred, gold, kind)}
