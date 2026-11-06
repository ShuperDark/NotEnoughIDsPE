exec(open('rd.py').read().split("if __name__ == '__main__':")[0])
import json
done=set(int(x[0],16) for x in json.load(open('blockid_sites.json')))
# functions that call the Block constructor with their own x0 ("this") -> constructors of Block subclasses
ctors=set()
for i,(a,op,ops) in enumerate(lines):
    if op=='BL' and ops.strip()=='sub_1007D7E20':
        F=get_func(a)
        k=value_kind_entry=reaching_defs(F,i,0)
        # x0 at the call must come from x0 at entry (possibly through MOV)
        ok=True
        def src(F,i,rn,d=0):
            ds=reaching_defs(F,i,rn)
            if not ds: return False
            for x in ds:
                if x=='ENTRY':
                    if rn!=0: return False
                    continue
                a2,op2,ops2=lines[x]; p=[t.strip() for t in ops2.split(',')]
                if op2=='MOV' and len(p)==2 and regnum(p[1]) is not None and d<6:
                    if not src(F,x,regnum(p[1]),d+1): return False
                else: return False
            return True
        if src(F,i,0): ctors.add(F.fs)
ctors.add(0x1007D7E20)
thisfuncs |= set('sub_%X'%f for f in ctors)
res=[]
for i,(a,op,ops) in enumerate(lines):
    if op in ('LDRB','LDRSB') and re.search(r'\[X\d+,#8\]$',ops) and a not in done:
        F=get_func(a)
        if F.fs not in ctors: continue
        rn=int(re.search(r'\[X(\d+),#8\]',ops).group(1))
        k=value_kind(F,i,rn)
        if k and k<= {'this','static','getBlock','mBlocks[i]','mBlocks[k]'}:
            res.append('%X'%a)
print(len(ctors),'ctors;',len(res),'new sites'); print(res)
json.dump(res,open('ctor_sites.json','w'))
