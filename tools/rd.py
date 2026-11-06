"""Reaching-definition based classification of LDRB [Xn,#8] sites: is Xn a Block*?

A site is accepted only if EVERY definition of Xn that can reach the load (over the
control-flow graph of its function) yields a Block*. Function entry counts as a
definition: accepted only for x0 ('this') in methods that appear only in Block vtables.
Blocks with unknown predecessors (jump-table targets, landing pads) make the site fail.
"""
import re, json, bisect, collections, sys

lines = []
for l in open('insns.txt', encoding='utf-8', errors='replace'):
    m = re.match(r'^([0-9A-F]{16})\s+([A-Z][A-Z0-9.]*)\s*(.*?)\s*(;.*)?$', l.rstrip('\n'))
    if m:
        lines.append((int(m.group(1), 16), m.group(2), m.group(3)))
addrs = [a for a, _, _ in lines]
idx = {a: i for i, a in enumerate(addrs)}
labels = set(int(x, 16) for x in open('labels.txt'))
funcs = sorted(int(x, 16) for x in open('funcs.txt'))
statics = set(x.strip() for x in open('blockstatics.txt'))
blockfuncs = set(json.load(open('blockfuncs.json')))
vts = [int(x, 16) for x in json.load(open('blockvts.json'))]
dcq = {}
for l in open('dcq.txt'):
    a, s = l.split(); dcq[int(a, 16)] = s
invt = set()
for v in vts:
    k = 0
    while (v + 8 * k) in dcq and k < 400:
        invt.add(v + 8 * k); k += 1
outside = collections.Counter(s for a, s in dcq.items() if a not in invt)
thisfuncs = set(f for f in blockfuncs if outside[f] == 0)

RETURNS_BLOCK = {'sub_10079971C', 'sub_10079FDA0', 'sub_100388330'}
MBLOCKS = 'unk_1012D1860'

def func_range(a):
    i = bisect.bisect_right(funcs, a) - 1
    s = funcs[i]
    e = funcs[i + 1] if i + 1 < len(funcs) else s + 0x100000
    return s, e

def regnum(r):
    m = re.match(r'^[XW](\d+)$', r.strip())
    return int(m.group(1)) if m else None

NOWRITE = ('CMP', 'CMN', 'TST', 'B', 'BR', 'RET', 'CBZ', 'CBNZ', 'TBZ', 'TBNZ', 'CCMP', 'CCMN', 'FCMP', 'FCMPE', 'PRFM', 'NOP', 'DMB', 'DSB', 'ISB', 'BRK', 'HINT')
def dest_regs(op, ops):
    if op in ('BL', 'BLR'):
        return set(range(0, 19))
    if op.startswith('ST') or op in NOWRITE or op.startswith('B.'):
        r = set()
    else:
        p = [x.strip() for x in ops.split(',')]
        r = set()
        if p:
            n = regnum(p[0])
            if n is not None: r.add(n)
        if op in ('LDP', 'LDNP', 'LDPSW', 'LDAXP', 'LDXP') and len(p) > 1:
            n = regnum(p[1])
            if n is not None: r.add(n)
    if '!' in ops or re.search(r'\],#', ops):
        m = re.search(r'\[(X\d+)', ops)
        if m: r.add(int(m.group(1)[1:]))
    if op in ('STXR', 'STLXR', 'STXP', 'STLXP'):   # status register
        n = regnum(ops.split(',')[0])
        if n is not None: r.add(n)
    return r

# ------------------------------------------------------------------ CFG per function
class Func:
    pass

fcache = {}
def get_func(a):
    fs, fe = func_range(a)
    if fs in fcache: return fcache[fs]
    F = Func(); F.fs = fs; F.fe = fe
    i0 = idx.get(fs, bisect.bisect_left(addrs, fs))
    i1 = bisect.bisect_left(addrs, fe)
    F.i0, F.i1 = i0, i1
    # block leaders
    leaders = {i0}
    succ_targets = {}
    for i in range(i0, i1):
        a, op, ops = lines[i]
        if lines[i][0] in labels: leaders.add(i)
        if op == 'B' or op.startswith('B.') or op in ('CBZ', 'CBNZ', 'TBZ', 'TBNZ', 'BR', 'RET'):
            if i + 1 < i1: leaders.add(i + 1)
    leaders = sorted(leaders)
    F.bstart = leaders
    F.block_of = {}
    for bi, s in enumerate(leaders):
        e = leaders[bi + 1] if bi + 1 < len(leaders) else i1
        for i in range(s, e): F.block_of[i] = bi
    nb = len(leaders)
    preds = [set() for _ in range(nb)]
    known_target = [False] * nb
    for bi, s in enumerate(leaders):
        e = (leaders[bi + 1] if bi + 1 < nb else i1) - 1
        a, op, ops = lines[e]
        tgt = None
        m = re.search(r'\b(?:loc|sub|def|jpt|j)_([0-9A-F]+)\b', ops)
        if m: tgt = int(m.group(1), 16)
        fall = (bi + 1 < nb)
        if op == 'B':
            fall = False
        elif op in ('RET', 'BR'):
            fall = False; tgt = None
        elif not (op.startswith('B.') or op in ('CBZ', 'CBNZ', 'TBZ', 'TBNZ')):
            tgt = None
        if tgt is not None and tgt in idx and fs <= tgt < fe:
            tb = F.block_of[idx[tgt]]
            if lines[leaders[tb]][0] == tgt:
                preds[tb].add(bi); known_target[tb] = True
        if fall:
            preds[bi + 1].add(bi)
    # a block that starts at a label nobody branches to (jump table, landing pad) has unknown preds
    F.unknown = [False] * nb
    for bi, s in enumerate(leaders):
        if bi == 0: continue
        if lines[s][0] in labels and not known_target[bi] and not (bi - 1 in preds[bi] and False):
            # labels reached only by fall-through are fine if IDA labelled them for another reason?
            # be conservative: unknown unless some known branch targets it
            F.unknown[bi] = True
    F.preds = preds
    fcache[fs] = F
    return F

def reaching_defs(F, i, rn):
    """set of instruction indices defining rn that reach use at i; 'ENTRY' may be included;
    None if an unknown predecessor is reached."""
    res = set()
    seen = set()
    stack = [(F.block_of[i], i - 1)]
    while stack:
        bi, j = stack.pop()
        s = F.bstart[bi]
        found = False
        while j >= s:
            a, op, ops = lines[j]
            if rn in dest_regs(op, ops):
                res.add(j); found = True; break
            j -= 1
        if found: continue
        if bi == 0:
            res.add('ENTRY'); continue
        if F.unknown[bi]:
            return None
        for p in F.preds[bi]:
            if p not in seen:
                seen.add(p)
                pe = (F.bstart[p + 1] if p + 1 < len(F.bstart) else F.i1) - 1
                stack.append((p, pe))
        if not F.preds[bi]:
            return None
    return res

def value_kind(F, i, rn, depth=0):
    """kind of the value of register rn as used at instruction i: a set of kinds or None"""
    if depth > 8: return None
    defs = reaching_defs(F, i, rn)
    if not defs: return None
    kinds = set()
    for d in defs:
        if d == 'ENTRY':
            if rn == 0 and ('sub_%X' % F.fs) in thisfuncs: kinds.add('this')
            else: return None
            continue
        k = def_kind(F, d, rn, depth)
        if k is None: return None
        kinds |= k
    return kinds

def def_kind(F, d, rn, depth):
    a, op, ops = lines[d]
    p = [x.strip() for x in ops.split(',')]
    if op == 'MOV' and len(p) == 2 and p[1].startswith('X') and regnum(p[1]) is not None:
        return value_kind(F, d, regnum(p[1]), depth + 1)
    if op == 'BL' and rn == 0:
        return {'getBlock'} if p[0] in RETURNS_BLOCK else None
    if op == 'LDR' and p[0].startswith('X') and regnum(p[0]) == rn:
        rest = ','.join(p[1:])
        m = re.match(r'\[(X\d+),(X\d+|W\d+)(,.*)?\]$', rest)
        m2 = re.match(r'\[(X\d+)(?:,#(.+))?\]$', rest)
        if m:
            b = address_kind(F, d, int(m.group(1)[1:]))
            return {'mBlocks[i]'} if b == 'mblocks' else None
        if m2:
            base = int(m2.group(1)[1:]); off = m2.group(2) or '0'
            sym = re.search(r'(qword_[0-9A-F]+)@PAGEOFF', off)
            if sym:
                return {'static'} if sym.group(1) in statics else None
            b = address_kind(F, d, base)
            if b == 'static' and off == '0': return {'static'}
            if b == 'mblocks': return {'mBlocks[k]'}
    return None

def address_kind(F, i, rn):
    """'static' if rn at i is the address of a Block static on every path, 'mblocks' for mBlocks"""
    defs = reaching_defs(F, i, rn)
    if not defs or 'ENTRY' in defs: return None
    kinds = set()
    for d in defs:
        a, op, ops = lines[d]
        if op != 'ADRL': return None
        s2 = ops.split(',')[1].strip()
        if s2 in statics: kinds.add('static')
        elif s2 == MBLOCKS: kinds.add('mblocks')
        else: return None
    return kinds.pop() if len(kinds) == 1 else None

if __name__ == '__main__':
    res = collections.Counter()
    sites = []
    total = 0
    for i, (a, op, ops) in enumerate(lines):
        if op in ('LDRB', 'LDRSB') and re.search(r'\[X\d+,#8\]$', ops):
            total += 1
            rn = int(re.search(r'\[X(\d+),#8\]', ops).group(1))
            F = get_func(a)
            k = value_kind(F, i, rn)
            key = '+'.join(sorted(k)) if k else None
            res[key] += 1
            if k: sites.append((a, op, key))
    print('total', total)
    for k, v in res.most_common(): print(k, v)
    json.dump([['%x' % a, op, k] for a, op, k in sites], open('blockid_sites.json', 'w'))
