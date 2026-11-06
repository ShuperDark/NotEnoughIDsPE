"""Audit: LDRB/LDRSB [Xn,#8] not referenced in Tweak.xm whose base MAY be a Block
(some reaching definition is Block-like) or a BlockGraphics. Usage: audit.py Tweak.xm"""
import sys
exec(open('rd.py').read().split("if __name__ == '__main__':")[0])
tw = open(sys.argv[1], errors='replace').read().lower()
covered = set(int(x, 16) for x in re.findall(r'0x(1[0-9a-f]{8})\b', tw))
GRAPHICS = 'unk_10126A100'

allthis = set(blockfuncs)   # methods in Block vtables (also shared ones)

def kinds_any(F, i, rn, depth=0, seen=None):
    """set of kinds of every reaching def; 'unknown' for anything not recognised"""
    if depth > 8: return {'unknown'}
    defs = reaching_defs(F, i, rn)
    if defs is None: return {'unknown'}
    out = set()
    for d in defs:
        if d == 'ENTRY':
            fn = 'sub_%X' % F.fs
            if rn == 0 and fn in allthis: out.add('this' if fn in thisfuncs else 'this-shared')
            else: out.add('arg')
            continue
        a, op, ops = lines[d]
        p = [x.strip() for x in ops.split(',')]
        if op == 'MOV' and len(p) == 2 and regnum(p[1]) is not None and p[1].startswith('X'):
            out |= kinds_any(F, d, regnum(p[1]), depth + 1); continue
        if op == 'BL' and rn == 0:
            out.add('getBlock' if p[0] in RETURNS_BLOCK else 'call:' + p[0]); continue
        if op == 'LDR' and p[0].startswith('X'):
            rest = ','.join(p[1:])
            m = re.match(r'\[(X\d+),(X\d+|W\d+)(,.*)?\]$', rest)
            if m:
                defs2 = reaching_defs(F, d, int(m.group(1)[1:])) or []
                syms = set(lines[x][2].split(',')[1].strip() for x in defs2 if x != 'ENTRY' and lines[x][1] == 'ADRL')
                if MBLOCKS in syms: out.add('mBlocks[i]')
                elif GRAPHICS in syms: out.add('graphics[i]')
                else: out.add('unknown')
                continue
            m2 = re.match(r'\[(X\d+)(?:,#(.+))?\]$', rest)
            if m2:
                sym = re.search(r'(qword_[0-9A-F]+)@PAGEOFF', m2.group(2) or '')
                if sym and sym.group(1) in statics: out.add('static'); continue
                out.add('field'); continue
        out.add('unknown')
    return out

BLOCKY = {'this', 'this-shared', 'getBlock', 'mBlocks[i]', 'static'}
rows = []
for i, (a, op, ops) in enumerate(lines):
    if op in ('LDRB', 'LDRSB') and re.search(r'^W\d+, \[X\d+,#8\]$', ops) and a not in covered:
        rn = int(re.search(r'\[X(\d+),#8\]', ops).group(1))
        F = get_func(a)
        k = kinds_any(F, i, rn)
        if k & BLOCKY or 'graphics[i]' in k:
            rows.append(('%X' % a, 'sub_%X' % F.fs, ops, '+'.join(sorted(k))))
import collections
c = collections.Counter(r[3] for r in rows)
for k, v in c.most_common(): print(v, k)
with open('audit_rows.txt', 'w') as f:
    for r in rows: f.write(' '.join(r) + '\n')
print(len(rows))
