import all_function as af
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(page_title='Biohub: Publication & Preprint',layout='wide')

st.header('Biohub publication search result.')
st.subheader('Hongyu Dai: Summer internship project')

# streamlit run app.py --global.dataFrameSerialization="legacy"


######################### create website
##### load data
base=pd.read_csv( 'base.csv', encoding='utf-8-sig')
allchangedb_old= pd.read_csv( 'changedb old.csv', encoding='utf-8-sig')
allchangedb_new= pd.read_csv('changedb new.csv' , encoding='utf-8-sig')
alldeletedb= pd.read_csv('deletedb.csv' , encoding='utf-8-sig')
pub_pre= pd.read_csv('match pub-pre.csv',encoding='utf-8-sig')


### 1. table selection
table_option = st.selectbox(
    'Which table you would like to check?',
    ('base', 'changedb (old version)', 'changedb (new version)', 'matched pub-preprint','deletedb')) 

def table_select(table_option):
    if table_option == 'base':
        df = base
    if table_option == 'changedb (old version)':
        df = allchangedb_old
    if table_option == 'changedb (new version)':
        df = allchangedb_new
    if table_option == 'matched pub-preprint':
        df = pub_pre
    if table_option == 'deletedb':
        df = alldeletedb
    df.fillna('', inplace=True)
    return df

df=table_select(table_option)
df_ori=df.copy()

#### format selection
format_select = st.radio(
    "What's table format you want?",
    ('short format','full text'))

#### add search bar
search = st.text_input('Enter search words:')

if search:
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

def compre_sel(sel_df):
    sel_df.columns = sel_df.loc['title']
    sel_df = sel_df.drop(['save datetime', 'title'])
    sel_df.reset_index(inplace=True)

    gb_sel = GridOptionsBuilder.from_dataframe(sel_df)
    gb_sel.configure_column('index',  pinned='left')
    gb_sel.configure_default_column(autoHeight=True, groupable=True,
                                    wrapText=True,  value=True, enableRowGroup=True, aggFunc='sum')
    gb_sel.configure_columns(column_names=sel_df.columns,maxWidth=1100/len(sel_row))
    grid_options_sel = gb_sel.build()
    grid_table_sel = AgGrid(sel_df, grid_options_sel, update_mode=GridUpdateMode.SELECTION_CHANGED,
                            enable_enterprise_modules=True)  # fit_columns_on_grid_load=True


if len(sel_row) == 1:
    st.json(sel_row[0])

    match_result= pd.DataFrame(sel_row)['match result'].values[0]
    if match_result !='':
        dmatch=pd.DataFrame()
        search_dois = match_result.split(' ; ')
        for j in search_dois:
            search_doi=j.split('10.')[-1]
            dmatch=pd.concat([dmatch,base.loc[base.loc[:,'doi'].str.contains(search_doi)]])

        st.subheader('Possible Match Result')
        compre_sel(dmatch.transpose())
        dmatch=pd.DataFrame()


if len(sel_row) > 1:
    sel_df = pd.DataFrame(sel_row).transpose()
    compre_sel(sel_df)
