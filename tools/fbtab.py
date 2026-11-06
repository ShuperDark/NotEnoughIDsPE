"""7e: table lookups indexed by the 1-byte BlockID of a FullBlock (LDRB Wn, [Xm] a few insns before an ADRL of one of the 7 block-ID tables). Run in the folder with insns.txt."""
import re
TABLES={'unk_1012D1860':'mBlocks','unk_10126A100':'graphics','unk_1012D20A0':'lightBlock','unk_1012D21A0':'emission','unk_1012D22A0':'solid','dword_1012D23A0':'translucency','unk_1012D27A0':'shouldTick'}
L=[l.rstrip('\n') for l in open('insns.txt',errors='replace')]
for i,l in enumerate(L):
    m=re.match(r'^([0-9A-F]{16})\s+ADRL\s+X\d+, (\w+)',l)
    if m and m.group(2) in TABLES:
        for j in range(max(0,i-4),i):
            m2=re.match(r'^([0-9A-F]{16})\s+LDRB\s+W\d+, \[X\d+\]$',L[j].split(';')[0].strip())
            if m2: print(m2.group(1),TABLES[m.group(2)])
