import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode,  DataReturnMode, JsCode
import datetime
import all_function as af


st.header('Publication Report')

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Input Start Date", value=pd.to_datetime("2022-06-01"))
with col2:
    end_date = st.date_input("Input End Date", value=pd.to_datetime("today"))

start = start_date.strftime("%Y-%m-%d")
end = end_date.strftime("%Y-%m-%d")

st.write('The time period you choose is: '+str(start_date)+' ~ '+str(end_date))

##### coding
# 1. Select author list   # 需要确定下
author=pd.read_excel('database/Biohub authors.xlsx')  #  biohub author

intramural=author[author['Campus (simple)'] == 'Biohub']
investigator=author.loc[author['Role'] == 'Investigator']
#author.loc[((author['Campus (simple)'] == 'Biohub') & (author['Role'] == 'Investigator')]
df_a=author.loc[(author['Campus (simple)'] == 'Biohub') | (author['Role'] == 'Investigator') ]

# 2. Choose publication & prerpint within specific time period  # 指定时间内的pub & pre
df = pd.read_csv('database/basedb.csv', encoding='utf-8-sig')
df.fillna('', inplace=True)

# 2.1 Exclude 'review list'
with open('database/list of review journals.txt') as file:
    review_list = [line.rstrip() for line in file]

df=df[~df['journal'].isin(review_list)]
df['b_au']=df[['biohub author','possible biohub author','corresponding author']].agg(', '.join, axis=1).str.replace(', , ',', ').str.strip(', ')


# 2.2 divided into two categories: publication and preprint #得把date格式改一下然后。换成date
preprint_list=['biorxiv','bioRxiv','medrxiv','medRxiv','arxiv','arXiv']
preprint = df[df['journal'].isin(preprint_list)]
publication = df[~df['journal'].isin(preprint_list)]

df['epost date'] = pd.to_datetime(df['epost date'])  


pre_condition = (df['epost date'] >= start) & (df['epost date'] <= end) & (df['journal'].isin(preprint_list))
p1_pre=df.loc[pre_condition]

pub_condition = (df['epost date'] >= start) & (df['epost date'] <= end) & (~df['journal'].isin(preprint_list))
p1_pub=df.loc[pub_condition]

########
tab1, tab2, tab3 = st.tabs(["summary report", "summary table", "author table"])

with tab1:
    
    p1="#### Biohub intramural research program – Papers published and preprints first-deposited \n\nIncludes papers, conference proceedings, and preprints published or first-deposited since the last Biohub All-Hands meeting that cite Biohub affiliation or funding and that include a Biohub employee as a co-author (we may easily have missed something, so please feel free to send Bill Burkholder any additions or corrections)\n"
    
    # Record: Publication
    p1 +='##### Papers (Research articles, methods papers, reviews, etc.) and conference proceedings:\n'
    for ind,row in p1_pub.iterrows():
        # check unique of b_au
        if row['corresponding author'] !='':
            p1 +='- **'+row['b_au']+" of "+row['corresponding author']+"’s lab at "+', '.join(row['corresponding author institution'].split(',')[0:2])+'**\n\n  '+row['title']+' PMID: '+str(row['pmid'])+'\n'
        else:
            p1 +='- **'+row['b_au']+'**\n\n  '+row['title']+' PMID: '+str(row['pmid'])+'\n'

    # Record: Prerprint
    p1 += "\n\n##### Preprints\n"
    for ind,row in p1_pre.iterrows():
        # check unique of b_au
        if row['corresponding author'] !='':
            p1 +='- **'+row['b_au']+" of "+row['corresponding author']+"’s lab at "+', '.join(row['corresponding author institution'].split(',')[0:2])+'**\n\n  '+row['title']+' doi: '+str(row['doi'])+'\n'
        else:
            p1 +='- **'+row['b_au']+'**\n\n  '+row['title']+' doi: '+str(row['doi'])+'\n'
    
    st.markdown(p1)    

    st.download_button(label='Download Report',data=p1,file_name='Report.md')

with tab2:
    st.header("summary table")
   # st.image("https://static.streamlit.io/examples/dog.jpg", width=200)
   
    df2=pd.DataFrame(columns =['Biohub staff authors', 'All authors'],index = ['Papers (Research articles, methods papers, reviews, etc.) and conference proceedings', 'Preprints', 'Total'])

    df2.iloc[0,1]= p1_pub.shape[0]
    df2.iloc[1,1]= p1_pre.shape[0]
    df2.iloc[2,1]=df2.iloc[0,1]+df2.iloc[1,1]

    df2.iloc[0,0]=p1_pub[( p1_pub['biohub author']!='') | ( p1_pub['possible biohub author']!='')].shape[0]
    df2.iloc[1,0]=p1_pre[( p1_pre['biohub author']!='') | ( p1_pre['possible biohub author']!='')].shape[0]
    df2.iloc[2,0]=df2.iloc[0,0]+df2.iloc[1,0]


    st.markdown("#### Papers published and preprints first-deposited \n")
    st.write(df2)
    
    st.download_button(label='Download Report',data=df2.to_csv().encode('utf-8'),file_name='Overall Report.csv')

with tab3:
    st.header("Individual Author Report ( need to check dataset) ")
   
    df3=df.iloc[df[df['b_au']!=''].index,:]
    df3['b_au'] = df3['b_au'].map(lambda x:x.split(', '))  # Q: split by '; '
    df3=df3.explode('b_au')
    t=pd.DataFrame(df3.groupby('b_au')['record id'].count()).rename(columns={'record id':'Compliance'}) 
    t.index.name = None
    #t=t[t.index.isin(author['MatchName'])]

    p3=pd.DataFrame(columns =['Total articles as corresponding author','Qualifying articles as corresponding author','Qualifying articles as corresponding author with preprints','Compliance'],index = author['MatchName'])
    p3.index.name = None
    p3['Compliance'].fillna(t['Compliance'])
    
    st.write(p3)
    
    st.download_button(label='Download Report',data=p3.to_csv().encode('utf-8'),file_name='Individual Author Report.csv')
