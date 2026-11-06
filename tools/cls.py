import re, sys, collections
path = sys.argv[1]
lines = []
for l in open(path, encoding='utf-8', errors='replace'):
    m = re.match(r'^([0-9A-F]{16})\s+([A-Z][A-Z0-9.]*)\s*(.*?)\s*(;.*)?$', l.rstrip('\n'))
    if not m: continue
    lines.append((int(m.group(1), 16), m.group(2), m.group(3)))
idx = {a: i for i, (a, _, _) in enumerate(lines)}

def regnum(r):
    m = re.match(r'^[XW](\d+)$', r)
    return int(m.group(1)) if m else None

def defines(op, ops, rn):
    if op in ('STR', 'STRB', 'STRH', 'STP', 'CMP', 'CMN', 'TST', 'B', 'BR', 'CBZ', 'CBNZ', 'TBZ', 'TBNZ', 'RET', 'STUR', 'STURB', 'STURH') or op.startswith('B.'):
        return False
    parts = [p.strip() for p in ops.split(',')]
    if not parts: return False
    if op in ('LDP',):
        return regnum(parts[0]) == rn or regnum(parts[1]) == rn
    if op in ('BL', 'BLR'):
        return rn <= 18
    return regnum(parts[0]) == rn

def classify(i, rn, depth=0):
    j = i - 1
    while j >= 0 and i - j < 60:
        a, op, ops = lines[j]
        if op in ('RET',) : return 'ARG?'
        if defines(op, ops, rn):
            return op + ' ' + re.sub(r'[XW]\d+', 'R', ops)
        j -= 1
    return 'FAR'

out = collections.Counter()
detail = collections.defaultdict(list)
for i, (a, op, ops) in enumerate(lines):
    if op == 'LDRSH' and '#0x2E]' in ops:
        m = re.search(r'\[(X\d+),#0x2E\]', ops)
        rn = regnum(m.group(1))
        c = classify(i, rn)
        out[c] += 1
        detail[c].append('%X' % a)
for c, n in out.most_common():
    print(n, c, " ".join(detail[c]))
