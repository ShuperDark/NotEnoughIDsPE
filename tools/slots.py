"""For each call to a FullBlock / BlockID producer that returns through x8, find the
stack slot and check whether the bytes after it are used by anything else in the
function (would a wider value fit?)."""
exec(open('rd.py').read().split("if __name__ == '__main__':")[0])
import collections

PRODUCERS = {'sub_10079A014': ('getBlockID', 1), 'sub_10079A1FC': ('getBlockAndData', 2)}
SIZES = {'LDRB': 1, 'LDRSB': 1, 'STRB': 1, 'LDURB': 1, 'STURB': 1, 'LDRH': 2, 'LDRSH': 2, 'STRH': 2, 'LDURH': 2, 'STURH': 2,
         'LDR': 0, 'STR': 0, 'LDUR': 0, 'STUR': 0, 'LDP': 0, 'STP': 0, 'LDRSW': 4}

def frame_off(ops):
    """canonical frame offset from IDA's stack-variable token (var_XX = -0xXX,
    var_sN = +N, arg_N = +N), independent of where SP is at that instruction."""
    m = re.search(r'\[(SP|X29),#(.+?)\]', ops)
    if not m: return None
    toks = re.findall(r'(var_s[0-9A-F]+|var_[0-9A-F]+|arg_[0-9A-F]+)', m.group(2))
    if len(toks) != 1: return None
    t = toks[0]
    if t.startswith('var_s'): v = int(t[5:], 16)
    elif t.startswith('var_'): v = -int(t[4:], 16)
    else: v = 0x10000 + int(t[4:], 16)
    return ('F', v)

def access_size(op, ops):
    s = SIZES.get(op)
    if s is None: return None
    if s: return s
    reg = ops.split(',')[0].strip()
    w = 8 if reg.startswith('X') or reg.startswith('D') else 4 if reg.startswith('W') or reg.startswith('S') else 16 if reg.startswith('Q') else 8
    return w * 2 if op in ('LDP', 'STP') else w

res = collections.Counter()
detail = []
for i, (a, op, ops) in enumerate(lines):
    if op != 'BL': continue
    tgt = ops.strip()
    if tgt not in PRODUCERS: continue
    name, width = PRODUCERS[tgt]
    F = get_func(a)
    # x8 setup before the call
    slot = None
    for j in range(i - 1, max(F.i0, i - 12) - 1, -1):
        jo, jops = lines[j][1], lines[j][2]
        if 8 in dest_regs(jo, jops):
            m = re.match(r'X8, (SP|X29), #(.+)$', jops)
            if jo in ('ADD', 'SUB') and m:
                fo = frame_off('[%s,#%s]' % (m.group(1), m.group(2)))
                if fo:
                    slot = fo
            break
    if slot is None:
        res[(name, 'no-stack-slot')] += 1; continue
    # all frame accesses in the function, normalised to the same base when possible
    used = collections.defaultdict(set)
    for k in range(F.i0, F.i1):
        ko, kops = lines[k][1], lines[k][2]
        fo = frame_off(kops)
        if not fo: continue
        sz = access_size(ko, kops)
        if sz is None: sz = 8
        b, v = fo
        for x in range(v, v + sz): used[b].add((x, k))
    base, v = slot
    extra = [(x, k) for (x, k) in used[base] if v + width <= x < v + 4]
    if extra:
        res[(name, 'neighbour-used')] += 1
    else:
        res[(name, 'free-to-4')] += 1
    detail.append(('%X' % a, name, base, v, len(extra)))
for k, c in sorted(res.items()): print(k, c)

