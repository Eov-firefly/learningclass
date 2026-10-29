"""Shared, CPU-only protocol utilities. No inference or gold-label imports."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT.parent / 'experiments_v89'
sys.path.insert(0, str(ENGINE))
from janus_min.spec import MODEL_SPECS, compile_case, digest

POLICIES = ['grammar', 'full', 'xgrammar', 'sequence_score', 'deterministic']
CONDITIONS = ['fixed8', 'exact_min', 'wide']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    data = Path(path).read_bytes()
    if data and not data.endswith(b'\n'):
        raise ValueError('unfinished JSONL; preserve and repair explicitly: ' + str(path))
    return [json.loads(line) for line in data.splitlines()]


def atomic(path, obj):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def source_hash():
    paths = (list(ROOT.glob('*.py')) + list((ENGINE / 'janus_min').glob('*.py'))
             + list((ENGINE / 'prototype').glob('*.py')))
    return digest({str(p.relative_to(ROOT.parent)): sha(p) for p in sorted(paths)})


def fingerprint(row):
    # Includes option order and labels, normalizes whitespace only.
    return digest({'question': ' '.join(row['question'].split()),
                   'options': [(k, ' '.join(v.split())) for k, v in row['options'].items()]})


def validate_public(rows):
    ids, texts, short_ids = set(), set(), set()
    for r in rows:
        if set(r) != {'question_id', 'split', 'question', 'options'}:
            raise ValueError('public rows must contain only question_id/split/question/options')
        q = r['question_id']
        if not isinstance(q, str) or not q or not isinstance(r['question'], str) or not r['question']:
            raise ValueError('invalid question')
        opts = r['options']
        if (not isinstance(opts, dict) or len(opts) < 2 or
                any(not isinstance(k, str) or not k or not isinstance(v, str) or not v for k, v in opts.items()) or
                len(set(opts.values())) != len(opts)):
            raise ValueError('options must have unique, nonempty labels and texts')
        key = fingerprint(r)
        short = q.split(':')[-1][:8]
        if q in ids or key in texts or short in short_ids:
            raise ValueError('duplicate question/text or eight-character artifact ID collision')
        ids.add(q); texts.add(key); short_ids.add(short)


def jobs(public, languages, model, shard=0, shards=1):
    result = []
    for i, case in enumerate(public):
        if i % shards != shard:
            continue
        lang = languages[model][case['question_id']]
        for condition in CONDITIONS:
            for policy in POLICIES:
                j = dict(question_id=case['question_id'], model=model, track='matched',
                         encoding='option_text', condition=condition, cap=lang['budgets'][condition],
                         policy=policy, repeat=0, split='eval')
                j['request_id'] = digest(j)[:24]
                result.append(j)
    return sorted(result, key=lambda j: digest({'order_seed': 20261029, 'job': j}))


def load_protocol(directory, check_source=True):
    directory = Path(directory)
    plan = json.loads((directory / 'protocol.json').read_text())
    # Workers do not read or hash scoring.jsonl. Its hash is verified by analysis.
    for name in ['public.jsonl', 'languages.json', 'models.json']:
        if sha(directory / name) != plan['files'][name]:
            raise ValueError('frozen input changed: ' + name)
    if check_source and source_hash() != plan['source_sha256']:
        raise ValueError('source changed since freeze; create a new protocol directory')
    public = read_jsonl(directory / 'public.jsonl')
    validate_public(public)
    return (plan, public, json.loads((directory / 'languages.json').read_text()),
            json.loads((directory / 'models.json').read_text()))


def assignment(devices):
    if len(devices) not in {2, 4} or len(set(devices)) != len(devices) or any(not d for d in devices):
        raise ValueError('supply two or four distinct CUDA device identifiers')
    shards = len(devices) // 2
    return [(m, s, shards, devices[i * shards + s])
            for i, m in enumerate(MODEL_SPECS) for s in range(shards)]
