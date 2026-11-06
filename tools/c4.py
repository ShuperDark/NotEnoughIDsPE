"""Stage 4c: which getBlockAndData / getBlockID call sites can take the wide result.
getBlockAndData (0x10079A1FC) -> neid_getBlockAndData3: out = {id lo, id hi, data}
getBlockID      (0x10079A014) -> neid_getBlockID2:      out = {id lo, id hi}
A site is accepted when, in its function,
  * every access to the out bytes [v, v+W) (W = 3 or 2, frame offsets from IDA's
    var names) is an LDRB/LDURB of the id byte (v) or, for FullBlock, of the data
    byte (v+1); nothing else reads/writes them, no address of them escapes except
    the x8 setup of producer calls of the same kind into the same slot;
  * every use of a loaded id (inside its basic block, value must die there) is:
    CMP/CMN #imm, CBZ/CBNZ, index into one of the 7 block tables, STRB/STURB
    (truncates, as before), AND #0xFF.
Output: c4_sites.json  [{call, kind, ids:[addr], datas:[addr]}...]"""
exec(open('rd.py').read().split("if __name__ == '__main__':")[0])
exec(open('slots.py').read().split('res = collections.Counter()')[0].split("exec(open('rd.py')")[1].split('\n',1)[1])
import json, collections
EXCLUDE_FNS = {0x1007AA488, 0x1003B3DA0,   # Level::destroyBlock (4d), RenderChunkBuilder::_tessellateQueues (5a)
               0x10034F7D4, 0x10065C6D4, 0x1006A62DC, 0x1006C6FF8,   # terrain particle senders (4d-2)
               0x100659448}   # Entity::_playMovementSound (4c-2)
PROD = {'sub_10079A1FC': ('fb', 3), 'sub_10079A014': ('id', 2)}
TABLES={'unk_1012D1860','unk_10126A100','unk_1012D20A0','unk_1012D21A0','unk_1012D22A0','dword_1012D23A0','unk_1012D27A0'}
def is_table(F,i,rn):
    d=reaching_defs(F,i,rn)
    if not d or 'ENTRY' in d: return False
    return all(lines[x][1]=='ADRL' and lines[x][2].split(',')[1].strip() in TABLES for x in d)
def regs_read(op,ops):
    regs=[int(m) for m in re.findall(r'\b[XW](\d+)\b',ops)]
    if op.startswith('ST') or op in ('CMP','CMN','TST','CBZ','CBNZ','TBZ','TBNZ','BR','BLR','RET','CCMP','BFI','BFXIL','BFM','MOVK'): return set(regs)   # BFI/BFXIL/BFM/MOVK also read their destination
    if op in ('LDP','LDNP','LDPSW','LDAXP','LDXP'): return set(regs[2:])   # both first registers are destinations
    return set(regs[1:])
def check_use(F,j,rd_):
    o,p=lines[j][1],lines[j][2]
    if o in ('CMP','CMN') and re.match(r'W\d+, (#|W\d+$)',p): return None
    if o in ('CBZ','CBNZ') and re.match(r'[XW]%d,'%rd_,p): return None
    if o in ('STRB','STURB') and p.startswith('W%d,'%rd_) and not re.search(r'\[X%d'%rd_,p): return None
    if o=='AND' and re.match(r'W\d+, W%d, #0xFF$'%rd_,p): return None
    m=re.match(r'[XWSDBH]\d+, \[X(\d+),[XW](\d+)(,(LSL|UXTW|SXTW)#\d+|,UXTW|,SXTW)?\]$',p)
    if o in ('LDR','LDRB','LDRSB','STRB','STR','LDRSW') and m and int(m.group(2))==rd_ and int(m.group(1))!=rd_ and is_table(F,j,int(m.group(1))): return None
    return 'use:'+o+' '+p
def succs(F,bi):
    if not hasattr(F,'succ'):
        F.succ=[[] for _ in F.bstart]
        for b,ps in enumerate(F.preds):
            for q in ps: F.succ[q].append(b)
    return F.succ[bi]
def id_uses_ok(F,i,rd_):
    """forward over the CFG from the load until every path redefines rd_"""
    work=[(F.block_of[i],i+1)]; seen=set()
    while work:
        bi,start=work.pop()
        end=(F.bstart[bi+1] if bi+1<len(F.bstart) else F.i1)
        dead=False
        for j in range(start,end):
            o,p=lines[j][1],lines[j][2]
            if o in ('BL','BLR'):
                if rd_<=7: return 'call'
                if rd_<=18: dead=True; break
                continue
            if o=='RET':
                if rd_==0: return 'returned'
                dead=True; break
            if o=='BR': return 'indirect-branch'
            if rd_ in regs_read(o,p):
                r=check_use(F,j,rd_)
                if r: return r
            if rd_ in dest_regs(o,p): dead=True; break
        if dead: continue
        nxt=succs(F,bi)
        if not nxt:
            # falls off the end (tail call B sub_ / unknown): be safe
            last=lines[end-1]
            if last[1]=='B' and 'sub_' in last[2]: return 'tail-call' if rd_<=7 else None
            return 'no-successor'
        for b in nxt:
            if F.unknown[b]: return 'unknown-successor'
            if b not in seen: seen.add(b); work.append((b,F.bstart[b]))
        if len(seen)>200: return 'too-far'
    return None
REASONS=[]
stats=collections.Counter(); groups=collections.defaultdict(list)
for i,(a,op,ops) in enumerate(lines):
    if op!='BL' or ops.strip() not in PROD: continue
    kind,W=PROD[ops.strip()]; F=get_func(a)
    slot=None
    for j in range(i-1, max(F.i0,i-12)-1, -1):
        jo,jops=lines[j][1],lines[j][2]
        if 8 in dest_regs(jo,jops):
            m=re.match(r'X8, (SP|X29), #(.+)$',jops)
            if jo in ('ADD','SUB') and m: slot=frame_off('[%s,#%s]'%(m.group(1),m.group(2)))
            break
    if slot is None: stats[(kind,'no-stack-slot')]+=1; continue
    groups[(F.fs,slot[1],kind)].append(i)
out=[]
for (fs,v,kind),calls in groups.items():
    W=3 if kind=='fb' else 2
    F=get_func(lines[calls[0]][0]); reason=None; ids=[]; datas=[]
    setups=set()
    for c in calls:
        for j in range(c-1, max(F.i0,c-12)-1, -1):
            if 8 in dest_regs(lines[j][1],lines[j][2]): setups.add(j); break
    for k in range(F.i0,F.i1):
        ko,kops=lines[k][1],lines[k][2]
        if k in setups: continue
        m=re.match(r'X\d+, (SP|X29), #(.+)$',kops)
        if ko in ('ADD','SUB') and m:
            fo=frame_off('[%s,#%s]'%(m.group(1),m.group(2)))
            # An address that starts inside our bytes [v, v+W) lets a callee read/write
            # them: reject. An address that starts before v is safe: an object there that
            # reached v+2 would also cover v..v+1, which vanilla itself reads after the
            # producer, so it cannot be live/written in between.
            if fo and v <= fo[1] < v+W: reason='address-escape'; break
            continue
        fo=frame_off(kops)
        if not fo: continue
        sz=access_size(ko,kops) or 8
        lo,hi=fo[1],fo[1]+sz
        if hi<=v or lo>=v+W: continue
        if ko in ('LDRB','LDURB') and lo==v:
            r=id_uses_ok(F,k,int(re.match(r'W(\d+)',kops).group(1)))
            if r: reason='id-'+r; break
            ids.append(k)
        elif ko in ('LDRB','LDURB') and lo==v+1 and kind=='fb': datas.append(k)
        else: reason='other-access:'+ko+' '+kops; break
    if not reason and not ids and not datas: reason='unused'
    if not reason and fs in EXCLUDE_FNS: reason='handled-elsewhere'
    if not reason:
        # LDRB [SP,#imm] -> LDRH needs an even imm
        for k in ids:
            if lines[k][1]=='LDRB' and re.search(r'\[SP,',lines[k][2]) and (v % 2): reason='odd-slot'
    if reason: REASONS.extend([reason]*len(calls))
    key=reason.split(':')[0] if reason else 'OK'
    stats[(kind,key)]+=len(calls)
    if not reason:
        out.append({'fn':'%X'%fs,'kind':kind,'calls':['%X'%lines[c][0] for c in calls],'ids':['%X'%lines[k][0] for k in ids],'datas':['%X'%lines[k][0] for k in datas]})
for k,c in sorted(stats.items()): print(k,c)
import collections as _c
print(_c.Counter(re.sub(r"[XW]d+","R",r.split(":",1)[1]) for r in REASONS if r.startswith("id-use")).most_common(25))
print(_c.Counter(re.sub(r"#.*","#..",r.split(":",1)[1]) for r in REASONS if r.startswith("other-access")).most_common(12))
json.dump(out,open('c4_sites.json','w'),indent=0)
print('accepted groups',len(out),'calls',sum(len(g['calls']) for g in out),'id loads',sum(len(g['ids']) for g in out),'data loads',sum(len(g['datas']) for g in out))
