import csv, os, sys, time
sys.path.insert(0,"..")
import krx_api as K
DATES=['20200403','20200605','20200904','20201204','20210402','20210604','20210903','20211203',
 '20220401','20220603','20220902','20221202','20230407','20230602','20230901','20231201',
 '20240405','20240607','20240906','20241206','20250404','20250605','20250905','20251205',
 '20260403','20260605']
OUT="_krx_pit.csv"
done=set()
if os.path.exists(OUT):
    for r in csv.DictReader(open(OUT,encoding="utf-8")): done.add(r["date"])
fo=open(OUT,"a",newline="",encoding="utf-8"); w=csv.writer(fo)
if fo.tell()==0: w.writerow(["date","code","name","market","close","mktcap","shrs","value"])
n=0
for d in DATES:
    if d in done: continue
    tot=0
    for path,mk in (("sto/stk_bydd_trd","KOSPI"),("sto/ksq_bydd_trd","KOSDAQ")):
        st,data=K.call("/"+path, basDd=d)
        rs=K.rows(data)
        for r in rs:
            try:
                w.writerow([d, r["ISU_CD"].strip(), r["ISU_NM"].strip(), mk,
                            int(r["TDD_CLSPRC"].replace(",","") or 0),
                            int(r["MKTCAP"].replace(",","") or 0),
                            int(r["LIST_SHRS"].replace(",","") or 0),
                            int(r["ACC_TRDVAL"].replace(",","") or 0)])
            except Exception: pass
        tot+=len(rs); time.sleep(0.15)
    fo.flush(); n+=1
    print(d, tot, flush=True)
    if n>=int(sys.argv[1] if len(sys.argv)>1 else 8): break
print("남은", len([d for d in DATES if d not in done])-n)
