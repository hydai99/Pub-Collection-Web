# streamlit run frontend.py --global.dataFrameSerialization="legacy"

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode,  DataReturnMode, JsCode

st.set_page_config(page_title='Biohub: Publication & Preprint',layout='wide')
st.header('Biohub publication search result.')

##### 0. load data
base = pd.read_csv('database/basedb.csv', encoding='utf-8-sig')
allchangedb_old= pd.read_csv( 'database/changedb (old version).csv', encoding='utf-8-sig')
allchangedb_new= pd.read_csv('database/changedb (new version).csv' , encoding='utf-8-sig')
alldeletedb= pd.read_csv('database/deletedb.csv' , encoding='utf-8-sig')
pub_pre= pd.read_csv('database/matched pub-preprint.csv',encoding='utf-8-sig')

##### 1. table selection
def table_select(table_option):
    if table_option == 'basedb':
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
    #df.reset_index(drop=True,inplace=True)
    return df

left,right=st.columns(2)
with left:
    table_option = st.selectbox(
        'Which table you would like to check?',
        #('matched pub-preprint', 'basedb', 'changedb (old version)', 'changedb (new version)', 'deletedb'))
        ('basedb', 'changedb (old version)', 'changedb (new version)', 'matched pub-preprint','deletedb'))
with right:
    format_select = st.radio(
    "What's table format you want?",
    ('short format','full text'))

df=table_select(table_option)


col1, col2 = st.columns(2) #[3, 1]
with col1:
    #### add search bar
    search = st.text_input('Enter search words: (Case Ignore)')

    if search:
        ind = []
        for i in df.columns:
            ind += list(df.loc[df[i].astype(str).str.lower()
                        .str.contains(search.lower())].index)
        df = df.iloc[list(set(ind)), :]
        reload_data = True


#####
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
#gb.configure_pagination(enabled=True, paginationAutoPageSize=True, paginationPageSize=10)
grid_options = gb.build()
grid_response = AgGrid(
    df,
    grid_options,
    update_mode=GridUpdateMode.VALUE_CHANGED | GridUpdateMode.SELECTION_CHANGED,
    enable_enterprise_modules=True
)

with col2:
    #### edit button
    st.write('If you confirm to edit data, click button below.')
    edit = st.button('Confirm edit!')

    if edit:
        df = grid_response['data']
        df.to_csv('database/'+table_option+'.csv', encoding='utf-8-sig', index=False)
        st.write('Edit successful!')


#### 2) compare & detail function
st.subheader('Detail & Compare Records')

sel_row = grid_response['selected_rows']  # type: list

def compre_sel(sel_df):
    sel_df.columns = sel_df.loc['title']
    sel_df = sel_df.drop(['save datetime', 'title'])
    sel_df.reset_index(inplace=True)
    #sel_df.reset_index(drop=True, inplace=True)

    gb_sel = GridOptionsBuilder.from_dataframe(sel_df)
    gb_sel.configure_column('index',  pinned='left',weight=20)  ###
    gb_sel.configure_default_column(autoHeight=True, groupable=True,
                                    wrapText=True,  value=True, enableRowGroup=True, aggFunc='sum')
    gb_sel.configure_columns(
        column_names=sel_df.columns, maxWidth=1700/sel_df.shape[1])
    grid_options_sel = gb_sel.build()
    grid_table_sel = AgGrid(sel_df, grid_options_sel, update_mode=GridUpdateMode.VALUE_CHANGED | GridUpdateMode.SELECTION_CHANGED,
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
        dmatch=dmatch.transpose()
        compre_sel(dmatch)


        m = dmatch.shape[1]
        if m==2 or m==3:
            if m==2:
                col1, col2, col3 = st.columns((1, 3, 3))
            if m==3:
                col1, col2, col3, col4 = st.columns((1, 2, 2,2))
                button_phold3 = col3.empty()
                do_action3 = button_phold1.button('Change to this', key=3)

            button_phold1 = col2.empty()
            do_action1 = button_phold1.button('Change to this', key=1)

            button_phold2 = col3.empty()
            do_action2 = button_phold2.button('Change to this', key=2)

            def change(do_action, i):
                if do_action:
                    x=pd.DataFrame(sel_row)['doi'].values[0]

                    base.loc[base.loc[:, 'doi'].str.contains(x), :].to_csv( 'database/changedb (old version).csv',  mode='a', index=False, header=False, encoding='utf-8-sig')

                    base.loc[base.loc[:, 'doi'].str.contains(x), 'match result']=dmatch.loc['journal',dmatch.columns.values[i-1]]+' '+dmatch.loc['doi',dmatch.columns.values[i-1]]
                    base.to_csv('database/basedb.csv', encoding='utf-8-sig', index=False)

                    base.loc[base.loc[:, 'doi'].str.contains(x), :].to_csv('database/changedb (new version).csv' , mode='a', index=False, header=False,  encoding='utf-8-sig')

                    pub_pre.loc[pub_pre.loc[:, 'doi'].str.contains(x), 'match result']=dmatch.loc['journal',dmatch.columns.values[i-1]]+' '+dmatch.loc['doi',dmatch.columns.values[i-1]]
                    pub_pre.to_csv('database/matched pub-preprint.csv',encoding='utf-8-sig', index=False)

                    st.write('Done')

                    import time
                    time.sleep(1)

                    pyautogui.hotkey("ctrl","F5")

            change(do_action1, 1)
            change(do_action2, 2)

            if m==3:
                change(do_action3, 3)

        if m>=4:
            st.write('sorry please change manually.')


        dmatch = pd.DataFrame()



if len(sel_row) > 1:
    sel_df = pd.DataFrame(sel_row).transpose()
    compre_sel(sel_df)
