import pandas as pd, numpy as np
df=pd.read_csv('merged_raw.csv',dtype=str)
df=df[df.dt!='dt'].dropna(subset=['dt'])
num=lambda s: pd.to_numeric(s.str.replace('+','',regex=False).str.replace(',','',regex=False),errors='coerce')
for c in df.columns[2:]: df[c]=num(df[c])
df=df.drop_duplicates(['dt','code'])
print(len(df), df.dt.min(), df.dt.max(), df.code.nunique())
df.to_pickle('inv.pkl')
print(df[['samo_fund','penfnd_etc','orgn','frgnr_invsr','fnnc_invt','acc_trde_prica']].describe().T[['mean','std']])
