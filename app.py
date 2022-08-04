import all_function as af
import streamlit as st
import numpy as np
import pandas as pd
import datetime
import datacompy
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from os.path import exists as file_exists

st.set_page_config(page_title='Biohub: Publication & Preprint',layout='wide')

st.header('Biohub publication search result.')
st.subheader('Hongyu Dai: Summer internship project')

# streamlit run demo2.py --global.dataFrameSerialization="legacy"


#########################
##### load database

base = pd.read_csv('basedb.csv', encoding='utf-8-sig')
base.fillna('', inplace=True)

dailyresult = datetime.datetime.today().strftime('%Y-%m-%d') + '_4searchresult.csv'
if file_exists('Daily Output\\'+dailyresult):
    new = pd.read_csv('Daily Output\\'+dailyresult, encoding='utf-8-sig')
    new.fillna('', inplace=True)

else:
    try:
        start=(datetime.datetime.strptime(max(base['save datetime']), '%m/%d/%Y')-datetime.timedelta(days=5)).strftime('%Y-%m-%d')
    except:
        start=(datetime.datetime.strptime(max(base['save datetime']), '%Y-%m-%d')-datetime.timedelta(days=5)).strftime('%Y-%m-%d')
    new = af.Bibliometrics_Collect(start)


##### update database
# only check row post after start date
fstart=datetime.datetime.strptime(start, '%Y-%m-%d').strftime('%m/%d/%Y')

#base_check = base[(base['epost date'] >= fstart) | (base['publish date'] >= fstart )]
base_check = base[(base['save datetime'] >= fstart)]


### delete db
#compy = datacompy.Compare(base_check, new, join_columns=['doi'])
#deletedb = compy.df1_unq_rows
#base = base.drop(index=deletedb.index)

### changedb: Store new / old versions of modified records
compy1 = datacompy.Compare(base_check, new, join_columns=['doi'])
compy2 = datacompy.Compare(base_check, new, join_columns=base.columns[2:-3])
changedb_new = pd.concat([compy2.df2_unq_rows, compy1.df2_unq_rows,
                         compy1.df2_unq_rows]).drop_duplicates(keep=False)
changedb_old = base.loc[base['doi'].isin(changedb_new['doi'])]
changedb_new.loc[:, 'record id'] = list(changedb_old['record id'])
changedb_new['record change number'] += 1

# totally new rcord (first time occur)
completelynewdb = new.loc[-new.doi.isin(base.doi)]
completelynewdb.loc[:, 'record id'] = range(
    int(max(base['record id'])+1), int(max(base['record id']) + len(completelynewdb)+1))

# remove changed record
base = base.drop(index=changedb_old.index)
base = pd.concat([base, changedb_new, completelynewdb]).sort_values(
    by=['record id']).reset_index(drop=True)

# save db
changedb_old.to_csv('changedb old.csv', mode='a', index=False, header=False, encoding='utf-8-sig')
changedb_new.to_csv('changedb new.csv', mode='a', index=False, header=False, encoding='utf-8-sig')
#deletedb.to_csv('deletedb.csv', mode='a', index=False,header=False, encoding='utf-8-sig')


#########################
####  preprint match
preprint_source = ['biorxiv', 'medrxiv', 'arxiv']
preprint = base[base['journal'].isin(preprint_source)]
publication = base[~base['journal'].isin(preprint_source)]

mid = 1
for i in publication.index:
    for j in preprint.index:
        preprint.loc[j, 'simTitles'] = af.similarity(
            publication.loc[i, 'title'], preprint.loc[j, 'title'])
        preprint.loc[j, 'sameFirstAuthor'] = af.sameFirstAuthorNameAndInitial(
            publication.loc[i, 'author list'], preprint.loc[j, 'author list'])

    match_candidate = preprint.loc[(preprint['simTitles'] >= 0.8) | ((preprint['simTitles'] >= 0.1) & (
        preprint['sameFirstAuthor'])), :].sort_values(by=['simTitles'], ascending=False)

    #if there are match candidate, do following process
    if match_candidate.empty == False:
        # 3: Journal column's index. 4: Publication notes.  8: DOI. 30:'New Note'
        match_candidate.loc[:, 'note'] = match_candidate.loc[:, 'journal'] + \
            ' ' + match_candidate.loc[:,'doi'].apply(lambda x: x.split('/')[-1])
        publication.loc[i, 'match result'] = match_candidate.loc[:, 'note'].str.cat(
            sep=' ; ')  # .values
        publication.loc[i, 'match id'] = mid

        # also write note in preprint
        preprint.loc[preprint['record id'] == match_candidate.iloc[0, 0],
                     'match result'] = 'Now published in '+publication.loc[i, 'journal']+publication.loc[i, 'doi']
        preprint.loc[preprint['record id'] ==
                     match_candidate.iloc[0, 0], 'match id'] = mid
        mid += 1

base = pd.concat([publication, preprint]).sort_values(
    by=['record id']).drop(columns=['simTitles', 'sameFirstAuthor'])
base.to_csv('basedb.csv', index=False, encoding='utf-8-sig')


#########################
##### create website
allchangedb_old= pd.read_csv( 'changedb old.csv', encoding='utf-8-sig')
allchangedb_new= pd.read_csv('changedb new.csv' , encoding='utf-8-sig')
#alldeletedb= pd.read_csv('deletedb.csv' , encoding='utf-8-sig')

pub_pre=base[base['match result']!='']
pub_pre.to_csv('match pub-pre.csv', encoding='utf-8-sig')


### 1. table selection
table_option = st.selectbox(
    'Which table you would like to check?',
    ('base', 'changedb (old version)', 'changedb (new version)', 'matched pub-preprint'))  # , 'deletedb'

#@st.cache
if table_option == 'base':
    df = base
if table_option == 'changedb (old version)':
    df = allchangedb_old
if table_option == 'changedb (new version)':
    df = allchangedb_new
if table_option == 'matched pub-preprint':
    df = pub_pre
#if table_option == 'deletedb':
    #df = alldeletedb

df.rename(columns=lambda x: x.title(), inplace=True)
df.fillna('', inplace=True)
df_ori=df.copy()

#### format selection
format_select = st.radio(
    "What's table format you want?",
    ('short format','full text'))

st.write(f"You selected table:{table_option} and format:{format_select}.")

#### add search bar
search = st.text_input('Enter search words:')

if search:
    #df=df[search]
    ind = []
    for i in df.columns:
        ind += list(df.loc[df[i].astype(str).str.contains(search)].index)
    df = df.iloc[list(set(ind)), :]
else:
    df=df_ori


gb = GridOptionsBuilder.from_dataframe(df)
if format_select == 'short format':
    gb.configure_default_column(editable=True, groupable=True, wrapText=True, enableRowGroup=True,
                                aggFunc='sum', sizeColumnsToFit=True) 

if format_select == 'full text':
    gb.configure_default_column(editable=True, groupable=True, wrapText=True, enableRowGroup=True,
                                aggFunc='sum', sizeColumnsToFit=True, autoHeight=True)
    #gb.configure_column(field="Author List", maxWidth=200)  # if want to set for single row

gb.configure_columns(column_names=df.columns, maxWidth=200)  # column_names=[]
gb.configure_selection(selection_mode='multiple', use_checkbox=True)
grid_options = gb.build()
grid_table = AgGrid(df, grid_options, update_mode=GridUpdateMode.SELECTION_CHANGED,
                    enable_enterprise_modules=True)  # , width=20 use old version?  #, allow_unsafe_jscode=True
#new_df = grid_table['data']  # dataframe with after edit value




#### 2) compare & detail function
st.subheader('Detail & Compare Records')

sel_row = grid_table['selected_rows']  # type: list

if len(sel_row) == 1:
    st.json(sel_row[0])

    match_result= pd.DataFrame(sel_row)['Match Result'].values[0]
    if match_result !='':
        dmatch=pd.DataFrame()
        search_dois = match_result.split(' ; ')
        for j in search_dois:
            search_doi=j.split('10.')[-1]
            dmatch=pd.concat([dmatch,base.loc[base.loc[:,'Doi'].str.contains(search_doi)]])

        st.subheader('Show match result:')
        st.dataframe(dmatch.transpose() )
        dmatch=pd.DataFrame()


if len(sel_row) > 1:
	sel_df = pd.DataFrame(sel_row).transpose()   # type: dataframe

	sel_df.columns = sel_df.loc['Title']
	sel_df = sel_df.drop(['Save Datetime', 'Title'])
	sel_df.reset_index(inplace=True)

	gb_sel = GridOptionsBuilder.from_dataframe(sel_df)
	gb_sel.configure_column('index',  pinned='left')
	#gb_sel.configure_pagination(enabled=True)
	gb_sel.configure_default_column(autoHeight=True, groupable=True,
                                 wrapText=True,  value=True, enableRowGroup=True, aggFunc='sum')
	gb_sel.configure_columns(column_names=sel_df.columns,maxWidth=1100/len(sel_row))
	grid_options_sel = gb_sel.build()
	grid_table_sel = AgGrid(sel_df, grid_options_sel, update_mode=GridUpdateMode.SELECTION_CHANGED,
	                        enable_enterprise_modules=True)  # fit_columns_on_grid_load=True







