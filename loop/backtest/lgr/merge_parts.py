import os,glob,sys,time
HERE=os.path.dirname(os.path.abspath(__file__))
files=sorted(glob.glob(HERE+'/inv_parts/*.csv'))
donef=HERE+'/merged_done.txt'; out=HERE+'/inv_merged.csv'
done=set(open(donef).read().split()) if os.path.exists(donef) else set()
t0=time.time(); n=0
with open(out,'a') as o, open(donef,'a') as d:
    if os.path.getsize(out)==0: o.write(open(files[0]).readline())
    for f in files:
        k=os.path.basename(f)
        if k in done: continue
        if time.time()-t0>100: break
        lines=open(f).read().split('\n')[1:]
        o.write('\n'.join(l for l in lines if l)+'\n'); d.write(k+'\n'); n+=1
print('merged',n,'remain',len(files)-len(done)-n)
