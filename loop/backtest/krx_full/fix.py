import csv,os
p='2025.csv'
rows=list(csv.reader(open(p,encoding='utf-8')))
keep=[r for r in rows[1:] if r[0]!='20250110']
f=open(p+'.tmp','w',newline='',encoding='utf-8'); w=csv.writer(f); w.writerow(rows[0]); w.writerows(keep); f.close()
os.replace(p+'.tmp',p); print(len(rows)-1-len(keep))
