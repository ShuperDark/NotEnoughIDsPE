"""Stage 5b: LDRB Wd, [Xn, #8] that stage 2 did not widen, accepted when the loaded
value is used ONLY as the index into one of the 7 block-ID tables (so it is a block ID).
Uses are followed forward inside the basic block; a value still live at the block end
is rejected (conservative)."""
exec(open('rd.py').read().split("if __name__ == '__main__':")[0])
import json, collections
done=set(int(x[0],16) for x in json.load(open('blockid_sites.json')))|{0x1007D7F8C,0x1007D7F98}
TABLES={'unk_1012D1860','unk_10126A100','unk_1012D20A0','unk_1012D21A0','unk_1012D22A0','dword_1012D23A0','unk_1012D27A0'}
def is_table(F,i,rn):
    d=reaching_defs(F,i,rn)
    if not d or 'ENTRY' in d: return False
    for x in d:
        a,o,p=lines[x]
        if o!='ADRL' or p.split(',')[1].strip() not in TABLES: return False
    return True
def reads(op,ops,r):
    # register numbers read by the instruction (rough: every Xr/Wr operand except the first for non-stores)
    regs=[int(m) for m in re.findall(r'\b[XW](\d+)\b',ops)]
    if op.startswith('ST') or op in ('CMP','CMN','TST','CBZ','CBNZ','TBZ','TBNZ','BR','BLR','RET','CCMP'):
        return r in regs
    return r in regs[1:]
res=collections.Counter(); acc=[]
for i,(a,op,ops) in enumerate(lines):
    if op not in ('LDRB',) or not re.search(r'^W\d+, \[X\d+,#8\]$',ops) or a in done: continue
    F=get_func(a); rd_=int(re.match(r'W(\d+)',ops).group(1))
    bi=F.block_of[i]; end=(F.bstart[bi+1] if bi+1<len(F.bstart) else F.i1)
    uses=[]; ok=True; killed=False
    for j in range(i+1,end):
        o,p=lines[j][1],lines[j][2]
        if reads(o,p,rd_): uses.append(j)
        if rd_ in dest_regs(o,p): killed=True; break
    if not killed: res['live-out']+=1; continue
    if not uses: res['unused']+=1; continue
    for j in uses:
        o,p=lines[j][1],lines[j][2]
        m=re.match(r'[XWSDBH]\d+, \[X(\d+),[XW](\d+)(,(LSL|UXTW|SXTW)#\d+|,UXTW|,SXTW)?\]$',p)
        if o in ('LDR','LDRB','LDRSB','STRB','STR','LDRSW') and m and int(m.group(2))==rd_ and int(m.group(1))!=rd_ and is_table(F,j,int(m.group(1))):
            continue
        ok=False; break
    # The object at Xn must not be a BlockGraphics: BlockGraphics also keeps a
    # 1-byte block ID at +8 (and another field at +9). Reject a base that comes
    # from the BlockGraphics::mBlocks table (the crash at 0x100354C48).
    if ok:
        rn=int(re.search(r'\[X(\d+),#8\]',ops).group(1))
        for d in (reaching_defs(F,i,rn) or []):
            if d=='ENTRY': continue
            m2=re.match(r'X\d+, \[X(\d+),[XW]\d+',lines[d][2])
            if lines[d][1]=='LDR' and m2:
                for x in (reaching_defs(F,d,int(m2.group(1))) or []):
                    if x!='ENTRY' and lines[x][1]=='ADRL' and 'unk_10126A100' in lines[x][2]: ok=False
        if not ok: res['blockgraphics-base']+=1
    if ok: res['table-index']+=1; acc.append('%X'%a)
    else: res['other-use']+=1
print(dict(res)); json.dump(acc,open('use_sites.json','w'))
print(len(acc), acc[:10])
