import collections, json
ent = {}
for l in open('dcq.txt'):
    a, s = l.split()
    ent[int(a, 16)] = s
BASE = 0x101146080
N = 113
base = [ent.get(BASE + 8 * k) for k in range(N)]
votes = collections.Counter()
for a, s in ent.items():
    for k in range(2, N):
        if base[k] == s:
            votes[a - 8 * k] += 1
vts = sorted(a for a, v in votes.items() if v >= 30)
# vtable length: continue while entries exist (stop at gap or at another vtable start - 16)
funcs = set()
info = []
for v in vts:
    k = 0
    while (v + 8 * k) in ent and k < 400:
        if k > 0 and (v + 8 * k + 16) in set(vts):  # next vtable header starts
            break
        funcs.add(ent[v + 8 * k])
        k += 1
    info.append((hex(v), votes[v], k))
print(len(vts), 'block vtables')
for i in info[:10]: print(i)
json.dump(sorted(funcs), open('blockfuncs.json', 'w'))
json.dump([hex(v) for v in vts], open('blockvts.json', 'w'))
print(len(funcs), 'functions')
