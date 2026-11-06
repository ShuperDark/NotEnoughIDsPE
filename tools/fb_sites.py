"""Stage 4e: every call of getBlockAndData / getBlockID that stage 4c did not widen
(and that no other stage handles) -> fallback producers (vanilla layout)."""
import re, json, bisect
funcs=sorted(int(x,16) for x in open('funcs.txt'))
def fs(a): return funcs[bisect.bisect_right(funcs,a)-1]
EXCLUDE_FNS={0x1007AA488,0x1003B3DA0,0x10034F7D4,0x10065C6D4,0x1006A62DC,0x1006C6FF8,0x100659448}
acc=set(int(c,16) for g in json.load(open('c4_sites.json')) for c in g['calls'])
out=[]
for l in open('insns.txt',encoding='utf-8',errors='replace'):
    m=re.match(r'^([0-9A-F]{16})\s+(BL|B)\s+sub_10079A(1FC|014)\s*$',l.rstrip())
    if not m: continue
    a=int(m.group(1),16)
    if a in acc or fs(a) in EXCLUDE_FNS: continue
    out.append((a,1 if m.group(3)=='1FC' else 0,m.group(2)=='B'))
print(len(out), sum(1 for x in out if x[1]==0),'fb', sum(1 for x in out if x[2]),'tail')
with open('fb_sites.inc','w') as f:
    for a,k,t in out: f.write('\t{0x%x, %d, %d},\n'%(a,k,int(t)))
