"""Declared interface contracts. No gold answer is used by stopping decisions."""
import re
from decimal import Decimal, InvalidOperation

MARKER = re.compile(r'(?m)^[ \t]*####[ \t]*')
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)'


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
    pattern = NUMBER if kind == 'numeric' else '[' + re.escape(choices) + ']'
    value = re.match(pattern, text[m.end():])
    if value is None:
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
    elif suffix.strip():
        return None
    # A cap without a newline after the answer is not a completion certificate.
    if not eos and '\n' not in suffix:
        return None
    if contract in {'wrapper_balanced_strict','closure_balanced'} and not wrapper_balanced(text):
        return None
    if contract not in {'strict', 'wrapper_balanced_strict', 'closure_tolerant', 'closure_balanced'}:
        raise ValueError(contract)
    return value


def score(text, kind, gold, choices='ABCDE', eos=False, contract='strict'):
    pred = parse(text, kind, choices, eos, contract)
    return {'prediction': pred, 'valid': pred is not None,
            'correct': same_answer(pred, gold, kind)}


class EntropyGate:
    """New explicit reference: EMA of signed successive entropy differences.

    H_t is measured from pre-token logits for generated token t. Compare abs(EMA)
    to threshold; no stability comparison at t=1. This is not certified v5 code.
    """
    def __init__(self, threshold=0.01, window=5, min_steps=21, alpha=2/11):
        self.threshold, self.window, self.min_steps, self.alpha = threshold, window, min_steps, alpha
        self.previous = self.ema = None
        self.streak = 0

    def update(self, step, entropy):
        if self.previous is not None:
            delta = entropy - self.previous
            self.ema = delta if self.ema is None else self.alpha * delta + (1-self.alpha) * self.ema
            self.streak = self.streak + 1 if abs(self.ema) < self.threshold else 0
        self.previous = entropy
        return step >= self.min_steps and self.streak >= self.window
