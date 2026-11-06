import re, collections
exec(open('cls.py').read().split("out = collections.Counter()")[0].replace("path = sys.argv[1]", "path='insns.txt'"))

# For each mItems ADRL site, find the subsequent indexed load from that base and
# trace where the index register comes from.
def find_def(i, rn):
    j = i - 1
    while j >= 0 and i - j < 80:
        a, op, ops = lines[j]
        if op == 'RET':
            return None
        if defines(op, ops, rn):
            return j
        j -= 1
    return None

res = collections.Counter()
for i, (a, op, ops) in enumerate(lines):
    if op == 'ADRL' and 'qword_1012AE238' in ops:
        base = regnum(ops.split(',')[0])
        # follow forward to the first use as base
        for k in range(i + 1, min(i + 40, len(lines))):
            a2, op2, ops2 = lines[k]
            m = re.search(r'\[X%d,([XW]\d+)(?:,(\w+)(?:#(\d+))?)?\]' % base, ops2)
            if m:
                idxr = regnum(m.group(1))
                chain = []
                cur, rr = k, idxr
                for _ in range(4):
                    d = find_def(cur, rr)
                    if d is None:
                        chain.append('?')
                        break
                    da, dop, dops = lines[d]
                    chain.append('%X %s %s' % (da, dop, dops))
                    if dop in ('MOV', 'SXTW', 'SXTH', 'UXTH', 'AND', 'ADD', 'SUB') and regnum(dops.split(',')[1].strip()) is not None and dop != 'AND':
                        cur, rr = d, regnum(dops.split(',')[1].strip())
                        continue
                    break
                print('%X %s %s | %s' % (a2, op2, ops2, ' <- '.join(chain)))
                break
            if defines(op2, ops2, base):
                break
