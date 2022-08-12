import all_function as af
import pandas as pd
import datetime
import datacompy
from os.path import exists as file_exists

"""
This file contain data process: update, compare, match pre-pub
"""

#########################
##### load database
base = pd.read_csv('database/basedb.csv', encoding='utf-8-sig')
base.fillna('', inplace=True)



try:
    start=(datetime.datetime.strptime(max(base['save datetime']), '%m/%d/%Y')-datetime.timedelta(days=7)).strftime('%Y-%m-%d')
except:
    start=(datetime.datetime.strptime(max(base['save datetime']), '%Y-%m-%d')-datetime.timedelta(days=7)).strftime('%Y-%m-%d')

dailyresult = datetime.datetime.today().strftime('%Y-%m-%d') + '_4searchresult.csv'
if file_exists('daily output/'+dailyresult):
    new = pd.read_csv('daily output/'+dailyresult, encoding='utf-8-sig')
    new.fillna('', inplace=True)
else:
    new = af.Bibliometrics_Collect(start)

new=af.transfer_date_format(new)
base=af.transfer_date_format(base)

##### update database
# only check row post after start date
fstart = datetime.datetime.strptime(
    start, '%Y-%m-%d').strftime('%m/%d/%Y')  #('%Y-%m-%d')



base_check = base[(base['date'] >= fstart)] #save datetime

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
changedb_old.to_csv('database/changedb (old version).csv', mode='a', index=False, header=False, encoding='utf-8-sig')
changedb_new.to_csv('database/changedb (new version).csv', mode='a', index=False, header=False, encoding='utf-8-sig')
deletedb.to_csv('database/deletedb.csv', mode='a', index=False,
                header=False, encoding='utf-8-sig')


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
            ' ' + match_candidate.loc[:,'doi']
        publication.loc[i, 'match result'] = match_candidate.loc[:, 'note'].str.cat(
            sep=' ; ')  # .values
        publication.loc[i, 'match id'] = mid

        # also write note in preprint
        preprint.loc[preprint['record id'] == match_candidate.iloc[0, 0],
                     'match result'] = 'Now published in '+publication.loc[i, 'journal']+' '+publication.loc[i, 'doi']
        preprint.loc[preprint['record id'] ==
                     match_candidate.iloc[0, 0], 'match id'] = mid
        mid += 1

# save
base = pd.concat([publication, preprint]).sort_values(
    by=['record id']).drop(columns=['simTitles', 'sameFirstAuthor'])
base.to_csv('database/basedb.csv', index=False, encoding='utf-8-sig')

pub_pre=base[base['match result']!='']
pub_pre.to_csv('database/matched pub-preprint.csv',index=False, encoding='utf-8-sig')

