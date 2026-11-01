import pandas as pd, numpy as np, json, os
def load(sym,col='close'):
    d=pd.read_csv(f'{sym}.csv',dtype={'date':str}).dropna(subset=[col])
    d=d[['date',col]].rename(columns={col:sym}); return d
us=None
for s in ['GSPC','IXIC','SOX','TNX','VIX','DXY']:
    d=load(s); us=d if us is None else us.merge(d,on='date',how='outer')
us=us.sort_values('date').reset_index(drop=True)
for s in ['GSPC','IXIC','SOX','DXY']:
    us[s+'_r']=us[s].pct_change(fill_method=None)*100
us['TNX_d']=us['TNX'].diff()*10      # %p -> bp
us['VIX_d']=us['VIX'].diff()
us=us.dropna(subset=['GSPC_r','SOX_r'])
us['usdate']=us['date']

sec=pd.read_csv('kr_sector_daily.csv',dtype={'date':str})
kdates=pd.DataFrame({'date':sorted(sec['date'].unique())})
kdates['di']=kdates['date'].astype(int)
us['di']=us['date'].astype(int)
# for each KR date, the last US date strictly before it
m=pd.merge_asof(kdates.sort_values('di'),
                us[['di','usdate','GSPC_r','IXIC_r','SOX_r','TNX_d','VIX_d','DXY_r']].sort_values('di'),
                on='di',direction='backward',allow_exact_matches=False)
m=m.dropna(subset=['SOX_r'])
print("aligned KR days:",len(m), m['date'].min(),m['date'].max())
sec=sec.merge(m[['date','usdate','GSPC_r','IXIC_r','SOX_r','TNX_d','VIX_d','DXY_r']],on='date')
sec.to_csv('joined.csv',index=False)

rows=[]
for s,g in sec.groupby('sector'):
    if len(g)<300: continue
    y=g['mean'].values
    r={'sector':s,'n':len(g)}
    for x,lab in [('SOX_r','SOX'),('GSPC_r','SPX'),('IXIC_r','NDX'),('TNX_d','TNXbp'),('DXY_r','DXY')]:
        xv=g[x].values
        b=np.polyfit(xv,y,1)[0]; c=np.corrcoef(xv,y)[0,1]
        r[f'b_{lab}']=b; r[f'r_{lab}']=c
    rows.append(r)
df=pd.DataFrame(rows).sort_values('b_SOX',ascending=False)
pd.set_option('display.width',200)
print(df.to_string(index=False,float_format=lambda v:f"{v:7.3f}"))
df.to_csv('transfer_beta.csv',index=False)
