import json,sys,math
from collections import Counter,defaultdict
def sign_p(k,n):
    # two-sided exact binomial
    from math import comb
    if n==0: return 1
    t=sum(comb(n,i) for i in range(0,n+1) if abs(i-n/2)>=abs(k-n/2))
    return min(1,t/2**n)
for f in sys.argv[1:]:
    r=json.load(open(f)); v=list(r.values())
    c=Counter(x["verdict"] for x in v)
    dec=c["base"]+c["other"]
    sev=lambda xs,s:sum(1 for e in xs if isinstance(e,dict) and e.get("severity")==s)
    eb=[sev(x["errors_base"],"major") for x in v]; eo=[sev(x["errors_other"],"major") for x in v]
    mb=[sev(x["errors_base"],"minor") for x in v]; mo=[sev(x["errors_other"],"minor") for x in v]
    marg=Counter((x["verdict"],x["margin"]) for x in v)
    pd=Counter((x["verdict"],x["play_differs"]) for x in v)
    print(f"\n== {f.split('/')[-1]}  n={len(v)}  {dict(c)}  base share of decided={c['base']/dec:.2f}  p={sign_p(c['base'],dec):.3f}")
    print(f"   major errors: base {sum(eb)} (memos with >=1: {sum(1 for x in eb if x)})  other {sum(eo)} ({sum(1 for x in eo if x)})")
    print(f"   minor errors: base {sum(mb)}  other {sum(mo)}")
    print("   margins:",dict(marg))
    print("   play_differs:",dict(pd))
    bys=defaultdict(Counter)
    for x in v: bys[x["stratum"]][x["verdict"]]+=1
    print("   by stratum:",{k:dict(c2) for k,c2 in bys.items()})
