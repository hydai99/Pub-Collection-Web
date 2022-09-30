import datetime
import numpy as np
import pandas as pd
import time
import requests
import re
from bs4 import BeautifulSoup as bs
import distance, re
from unidecode import unidecode


# 1 Bio & Medrxiv
def BioMedrxiv_Search(start_date,end_date,keyword):

	## keep track of time
	overall_time = time.time()

	### build the url string
	## url with keyword
	base_url = 'http://biorxiv.org/search/{:s}'.format(keyword)+'%20'

	## add journal selection (biorxiv & medrxiv)
	base_url += 'jcode%3Abiorxiv%7C%7Cmedrxiv'

	## date range string
	date_str = 'limit_from%3A' + start_date + '%20limit_to%3A' + end_date
	base_url += '%20' + date_str

	## fixed formatting
	num_page_results = 10
	base_url += '%20numresults%3A' + str(num_page_results) + '%20sort%3Apublication-date%20direction%3Adescending%20format_result%3Acondensed'

	## List to store data
	title = []
	author_list = []
	url = []
	version_number = []
	version=[]
	doi=[]
	title=[]

	### once the string has been built, access site
	# initialize number of pages to loop through
	page = 0

	## loop through other pages of search if they exist
	while True:
		# keep user aware of status
		print('BioMedrxiv: Fetching search results {:d} to {:d}...'.format(num_page_results*page+1, num_page_results*(page+1)))

		# access url and pull html data
		if page == 0:
			url_response = requests.post(base_url)
			html = bs(url_response.text, features='html.parser')

			# find out how many results there are, and make sure don't pull more than user wants
			num_results_text = html.find(
				'div', attrs={'class': 'highwire-search-summary'}).text.strip().split()[0]
			if num_results_text == 'No':
				return(print('No results found matching search criteria.'))

		else:
			page_url = base_url + '?page=' + str(page)
			url_response = requests.post(page_url)
			html = bs(url_response.text, features='html.parser')


		articles = html.find_all('li', attrs={'class': 'search-result'})
		for article in articles:
			# Get the item header
			citation = article.find('div', attrs={'class': 'highwire-article-citation'})
			version += [citation.get('data-pisa-master')]
			version_number += [citation.get('data-pisa')[-1:]]  #base['Version number'] = [x[-1:] for x in base["Version"]]
			#atom_paths += [citation.get('data-apath')]

			# Get the DOI
			doipan = article.find('span', attrs={'class': 'highwire-cite-metadata-doi'})
			doi += [doipan.text.strip().replace('doi: https://doi.org/', '')]

			# Get the other info
			title += [article.find('span',attrs={'class': 'highwire-cite-title'}).text.strip().replace("\n", "")]
			#date += [article.find('span', attrs={'class': 'published-label'})]  # test
			url += [article.find('a', href=True)['href']]

			# Now collect author information
			authors = article.find_all(
				'span', attrs={'class': 'highwire-citation-author'})
			all_authors = []
			for author in authors:
				all_authors.append(author.text.replace(',',';'))  # check
			time.sleep(.2)
			author_list += [all_authors]

		if (page+1)*num_page_results >= int(num_results_text):
			break

		page += 1


	full_records_df = pd.DataFrame(np.column_stack([title, np.array(author_list, dtype=object), version,version_number, doi,url]),
								columns=['title', 'author list',
											'version','version number', 'doi',  'url']
								)
	# change author format
	#full_records_df = full_records_df.assign(author_list=full_records_df['author list'].astype(str).apply(lambda x: ','.join(x.replace("[", "").replace("'", "").replace("]", "").split(','))))
	
	if len(full_records_df) !=  0:
		full_records_df['author list'] = full_records_df['author list'].astype(
			str).apply(lambda x: x.replace("[", "").replace("'", "").replace("]", ""))

		# change url format
		full_records_df['url'] = full_records_df['url'].apply(
			lambda x: 'http://www.biorxiv.org'+x if not x.startswith('http') else x)

		for row_number,paper_url in enumerate(full_records_df.url):
			articles2 = bs(requests.post(paper_url).text, features='html.parser')
			full_records_df.loc[row_number, 'all affiliations'] = ("; ".join([i.get_text() for i in articles2.find_all('span', 'nlm-institution')]))
			#full_records_df.loc[row_number,'affiliations list']= ("; ".join(set([i.get_text() for i in articles2.find_all('span', 'nlm-institution')])))
			#full_records_df.loc[row_number,'epost date'] = articles2.select('div.panel-pane.pane-custom.pane-1 > div')[0].get_text().split('\xa0')[1][:-3]
			full_records_df.loc[row_number,'epost date'] = datetime.datetime.strptime(articles2.select('div.panel-pane.pane-custom.pane-1 > div')[0].get_text().split('\xa0')[1][:-3], '%B %d, %Y').strftime('%m/%d/%Y')
			full_records_df.loc[row_number,'abstract'] = articles2.find('div', attrs={'class': 'section abstract'}).text.replace('Abstract', '').replace('ABSTRACT', '').replace('\n', '')
			time.sleep(.5)
		for i,aff in enumerate(full_records_df['all affiliations']):
			all=[]
			if aff=='':
				info_url=full_records_df['url'][i]+'.article-info'
				articles3 = bs(requests.post(info_url).text, features='lxml')
				all +=[i.get_text() for i in articles3.find_all('address')]
				full_records_df.loc[i,'all affiliations']=re.sub(r'\n*\t*[0-9]*', '', "; ".join(all)).replace(';;',';').replace('  ',' ').strip(' ')

		full_records_df['affiliations list'] = full_records_df['all affiliations'].apply(
			lambda x: x if ';' not in str(x) else '; '.join(sorted(set(y.strip() for y in (x.split(';'))))))  # if x=='' else x
		full_records_df.loc[:,'save datetime'] = datetime.datetime.now().strftime('%m/%d/%Y') # when we save it
		full_records_df.loc[:, 'journal'] = full_records_df.loc[:, 'url'].apply(lambda x: x[x.rfind('rxiv')-3:x.rfind('rxiv')+4])
		#full_records_df.loc[:, 'epost date']=full_records_df.loc[:, 'epost date'].apply(lambda x: datetime.datetime.strptime(x, '%B %d, %Y').strftime('%m/%d/%Y'))
		full_records_df.loc[:, 'version']=full_records_df.loc[:, 'version'].apply(lambda x: x.split(';')[1])

	## keep user informed on task ended about record number
	print('BioMedrxiv: Fetched {:d} records in {:.1f} seconds.'.format(len(full_records_df), time.time() - overall_time))

	return(full_records_df)

# 2 arxiv
def Arxiv_Search(start_date,keyword):
    # initialize number of pages to loop through
    page=0
    num_page_results = 10

    ## keep track of time
    overall_time = time.time()

    ## url with keyword
    base_url = 'https://search.arxiv.org/?query={:s}'.format(keyword)+'&qid=1658694569062ler_nCnN_1505998205&byDate=1'

    ## List to store data
    title = []
    author_list = []
    url = []
    Epost_date = []
    version=[]
    doi=[]
    abstract=[]
    pdf_url=[]
    #id=[]
    start_date=datetime.datetime.strptime(start_date, '%Y-%m-%d').strftime('%m/%d/%Y')

    ### once the string has been built, access site
    ## loop through other pages of search if they exist
    while True:
        stop='No'
            # keep user aware of status
        print('Arxiv: Fetching search results {:d} to {:d}...'.format(num_page_results*(page+1)-9, num_page_results*(page+1)-1))

        # access url and pull html data
        if page == 0:
            url_response = requests.post(base_url)
            html = bs(url_response.text, features='html.parser')

            # find out how many results there are, and make sure don't pull more than user wants
            if html.p.get_text() =='No Results.':
                return(print('No results found matching search criteria.'))
            num_results_text = html.p.get_text().split('of')[1].split('.')[0].strip()

        else:
            page_url = base_url + '&startat='+str(page*num_page_results)
            url_response = requests.post(page_url)
            html = bs(url_response.text, features='html.parser')

        articles = html.find_all('td', attrs={'class': 'snipp'})
        for article in articles:
            ori_date= article.find('span', attrs={'class': 'age'}).text.replace('; Indexed ','')  # format: 'Apr 9, 2022'
            ori_date= datetime.datetime.strptime(ori_date, '%b %d, %Y').strftime('%m/%d/%Y')
            if ori_date < start_date:  #search page1 nearest date
                stop='Yes'
                break

            Epost_date += [ori_date]
                # = submit date = 'post date'
            title += [article.find('span',attrs={'class': 'title'}).text.replace("\n", "").replace("  ", " ")]
            #doi += [article.find('a', attrs={'class': 'url'}).text.split('abs/')[1].spilt('/')[0]] #test
            url += [article.find('a', attrs={'class': 'url'}).text]
            #url += ['https://search.arxiv.org/'+article.find('a', href=True)['href']

        if (page+1)*num_page_results >= int(num_results_text) or stop=='Yes' :
            break
        time.sleep(1)
        page += 1

    for paper_url in url:
            article2 = bs(requests.get(paper_url).text, features="html.parser")
            #id += [article2.find('meta', attrs={'name': 'citation_arxiv_id'})['content']]
            abstract += [article2.find("meta",  attrs={'name': 'citation_abstract'})['content'].replace("\n","").strip( )]
            pdf_url +=[article2.find('meta', attrs={'name': 'citation_pdf_url'})['content']]
            doi += [article2.find('meta', attrs={'name': 'citation_doi'})['content']]
            version += [article2.find_all('span', attrs={'class': 'arxivid'})[-1].text.replace('\n','').split(' ')[0]]
            author_list += [article2.find('div', attrs={'class': 'authors'}).text.replace('Authors:','')]
            time.sleep(.5)
    full_records_df = pd.DataFrame(np.column_stack([title, Epost_date,url,abstract,pdf_url,doi,version,author_list]),
                    columns=['title', 'epost date', 'url','abstract','pdf url','doi','version','author list'] )

    if len(full_records_df) !=  0:
        full_records_df.loc[:,'save datetime'] = datetime.datetime.now().strftime('%m/%d/%Y') # when we save it
        full_records_df.loc[:, 'journal'] = 'arxiv'
        #full_records_df.loc[:, 'version']=full_records_df.loc[:, 'version'].apply(lambda x: x.split(';')[1])

    ## keep user informed on task ended about record number
    print('Arxiv: Fetched {:d} records in {:.1f} seconds.'.format(len(full_records_df), time.time() - overall_time))

    return(full_records_df)

# 3 pubmed 
def Pubmed_search(start_date, end_date, keyword):

    #search_term=keyword+'[ad] '+start_date+':'+end_date+'[dp]'  # eg. biohub[ad] 2022/07/23:2022/07/26[dp]

    # initialize number of pages to loop through
    page=1
    num_page_results = 10

    ## keep track of time
    overall_time = time.time()

    ## List to store data
    title = []
    author_list = []
    url = []
    Epost_date = []
    publish_date=[]
    doi=[]
    abstract=[]
    pmid=[]  
    journal = []
    article_source=[]
    affiliations_list=[]

    ## url with keyword
    if start_date =='None':
        base_url = 'https://pubmed.ncbi.nlm.nih.gov/?term={:s}%5Bad%5D&'.format(keyword)+'format=abstract&sort=date&size='+str(num_page_results)
    else:
        base_url = 'https://pubmed.ncbi.nlm.nih.gov/?term={:s}%5Bad%5D+'.format(keyword)+(start_date+'%3A'+end_date).replace('/','%2F')+'%5Bdp%5D&format=abstract&sort=date&size='+str(num_page_results)

    ### once the string has been built, access site
    ## loop through other pages of search if they exist
    while True:
        # keep user aware of status
        print('Pubmed: Fetching search results {:d} to {:d}...'.format(num_page_results*page-9, num_page_results*page))

        # access url and pull html data
        if page == 1:
            url_response = requests.get(base_url)
            html = bs(url_response.text, features='html.parser')

            # find out how many results there are, and make sure don't pull more than user wants
            if html.find('div',attrs={'class': 'results-amount'}).text.replace('\n','').strip(' ')=='No results were found.':
                return(print('No results found matching search criteria.'))

            num_results_text = html.find('meta', attrs={'name': 'log_resultcount'})['content']

        else:
            page_url = base_url +'&page='+str(page)
            url_response = requests.get(page_url)
            html = bs(url_response.text, features='html.parser')

        articles = html.find_all('div', attrs={'class': 'results-article'})
        for article in articles:
            title += [article.find('h1',attrs={'class': 'heading-title'}).text.replace('\n','').strip()]

            if article.find('span', attrs={'class': 'secondary-date'}):
                ori_date1 = article.find('span', attrs={'class': 'secondary-date'}).text.replace('\n', '').replace('eCollection','').replace(
                    'Epub ', '').replace('Print ','').strip().strip('.')  # change format: now "Epub 2022 Jun 23."
                try:
                    ori_date1= datetime.datetime.strptime(ori_date1, '%Y %b %d').strftime('%m/%d/%Y')
                except:
                    try:
                        ori_date1= datetime.datetime.strptime(ori_date1, '%Y %b').strftime('%m/%Y')
                    except:
                        pass
            else:
                ori_date1=''
            Epost_date += [ori_date1]

            if article.find('span', attrs={'class': 'cit'}):
                ori_date2= article.find('span', attrs={'class': 'cit'}).text.replace('eCollection','').strip('.').split(';')[0]
                try:
                    ori_date2= datetime.datetime.strptime(ori_date2, '%Y %b %d').strftime('%m/%d/%Y')
                except:
                    try:
                        ori_date2= datetime.datetime.strptime(ori_date2, '%Y %b').strftime('%m/%Y')
                    except:
                        pass
            else:
                ori_date2=''
            publish_date += [ori_date2]

            url += [article.find('a',attrs={'class': 'id-link'})['href']]
            pmid += [article.find('strong', attrs={'class': 'current-id'}).text.replace('\n','') ] 
            abstract += [article.find('div',attrs={'class': 'abstract'}).text.replace('\n','').replace('Abstract','').strip(' ')]
            doi += [article.find('span',attrs={'class': 'citation-doi'}).text.replace('\n','').replace('doi: ','').strip()] 

            author_w_num=article.find('div', attrs={'class': 'authors-list'}).text.replace('\xa0','').replace('\n','').strip().replace('              ','')
            author_list += [re.sub(r'[0-9]', '', author_w_num).replace('  ','').replace(',',';')]

            #all_authors = []
            #for author in article.find_all('a', attrs={'class': 'full-name'}):
            #    all_authors.append(author.text)
            #author_list += [all_authors]

            journal += [article.find('button',attrs={'class': 'journal-actions-trigger trigger'}).text.replace('\n','').strip()]
            article_source += [article.find('span',attrs={'class': 'cit'}).text]
            affiliations_list += [article.find('ul', attrs={'class': 'item-list'}).text.replace('\n','')]

        if page*num_page_results >= int(num_results_text):
            break
        time.sleep(1)
        page += 1

    full_records_df = pd.DataFrame(np.column_stack([title,Epost_date,publish_date,url,pmid,abstract,doi,author_list,journal,article_source,affiliations_list]),
                        columns=['title', 'epost date','publish date', 'url','PMID','abstract','doi','author list','journal','article_source','affiliations list'] )

    if len(full_records_df) !=  0:
        full_records_df.loc[:,'save datetime'] = datetime.datetime.now().strftime('%m/%d/%Y') # when we save it

    ## keep user informed on task ended about record number
    print('Pubmed: Fetched {:d} records in {:.1f} seconds.'.format(len(full_records_df), time.time() - overall_time))

    return(full_records_df)


# 3.2 pubmed search 2. using api
import math
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from collections import OrderedDict
from tqdm import tqdm_notebook as tqdm

def Pubmed_search2(start_date, end_date):

    #BASEURL_INFO = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi'
    BASEURL_SRCH = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
    BASEURL_FTCH = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'

    # parameters
    SOURCE_DB    = 'pubmed'     #pubmed, nuccore, nucest, nucgss, popset, protein
    TERM         = 'biohub[ad]'     # Entrez text query.   # (zuckerb* AND biohub) OR "cz biohub" OR "czi biohub"
    DATE_TYPE    = 'pdat'       # Type of date used to limit a search. The allowed values vary between Entrez databases, but common values are 'mdat' (modification date), 'pdat' (publication date) and 'edat' (Entrez date). Generally an Entrez database will have only two allowed values for datetype.
    start_date  = datetime.datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y/%m/%d')
    end_date  = datetime.datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y/%m/%d')
    
    SEP          = ' ; '
    BATCH_NUM    = 2000

    def mkquery(base_url, params):
        base_url += '?'
        for key, value in zip(params.keys(), params.values()):
            base_url += '{key}={value}&'.format(key=key, value=value)
        url = base_url[0:len(base_url) - 1]
        print('request url is: ' + url)
        return url

    def getXmlFromURL(base_url, params):
        response = requests.get(mkquery(base_url, params))
        return ET.fromstring(response.text)

    def getTextFromNode(root, path, fill='', mode=0, attrib='attribute'):
        if (root.find(path) == None):
            return fill
        else:
            if mode == 0:
                return root.find(path).text
            if mode == 1:
                return root.find(path).get(attrib)

    rootXml = getXmlFromURL(BASEURL_SRCH, {
        'db': SOURCE_DB,
        'term': TERM,
        'usehistory': 'y',
        'datetype': DATE_TYPE,
        'mindate': start_date,
        'maxdate': end_date})

    Count = rootXml.find('Count').text
    QueryKey = rootXml.find('QueryKey').text
    WebEnv = urllib.parse.quote(rootXml.find('WebEnv').text)

    articleDics = []
    authorArticleDics = []


    def getTextFromNode(root, path, fill='', mode=0, attrib='attribute'):
        if (root.find(path) == None):
            return fill
        else:
            if mode == 0:
                return root.find(path).text
            if mode == 1:
                return root.find(path).get(attrib)


    def pushData(rootXml):
        for article in rootXml.iter('PubmedArticle'):
            # get article info
            articleDic = {
                'title'        : getTextFromNode(article, 'MedlineCitation/Article/ArticleTitle', ''),
                'epost date'   : '/'.join([date.text if date.text != None else ''  for date in article.findall('MedlineCitation/Article/ArticleDate/')]),  # YYYY/MM/DD
                'publish date' : '/'.join([date.text if date.text != None else ''  for date in article.findall('PubmedData/History/PubMedPubDate[@PubStatus="pubmed"]/')]),  # YYYY/MM/DD
                'pmid'                    : getTextFromNode(article, 'MedlineCitation/PMID', ''),
                'abstract'                : getTextFromNode(article, 'MedlineCitation/Article/Abstract/AbstractText', ''),
                'doi'                     : getTextFromNode(article, 'MedlineCitation/Article/ELocationID[@EIdType="doi"]', ''),
                'author list'                 : SEP.join([author.find('ForeName').text + ' ' +  author.find('LastName').text if author.find('CollectiveName') == None else author.find('CollectiveName').text for author in article.findall('MedlineCitation/Article/AuthorList/')]),
                'journal'            : getTextFromNode(article, 'MedlineCitation/Article/Journal/Title', ''),
                'keyword'                 : SEP.join([keyword.text if keyword.text != None else ''  for keyword in article.findall('MedlineCitation/KeywordList/')])
                #'AuthorIdentifiers'       : SEP.join([getTextFromNode(author, 'Identifier', 'None') for author in article.findall('MedlineCitation/Article/AuthorList/')]),
                #'AuthorIdentifierSources' : SEP.join([getTextFromNode(author, 'Identifier', 'None', 1, 'Source') for author in article.findall('MedlineCitation/Article/AuthorList/')]),
            }
            articleDics.append(OrderedDict(articleDic))

            if article.find('MedlineCitation/MeshHeadingList/MeshHeading/') != None:
                tmp = article

            # get author info
            for author in article.findall('MedlineCitation/Article/AuthorList/'):

                # publish author ID
                # * It's only random id. not use for identify author. if you want to identify author, you can use identifier.
                authorId = str(uuid.uuid4())

                # author article
                authorArticleDic = {
                    'authorId'         : authorId,
                    'pmid'             : getTextFromNode(article, 'MedlineCitation/PMID', ''),
                    'name'             : getTextFromNode(author, 'ForeName') + ' ' +  getTextFromNode(author,'LastName') if author.find('CollectiveName') == None else author.find('CollectiveName').text,
                    'identifier'       : getTextFromNode(author, 'Identifier', '') ,
                    'identifierSource' : getTextFromNode(author, 'Identifier', '', 1, 'Source'),
                }
                
                affiliations = list()
                if author.find("./AffiliationInfo/Affiliation") is not None:
                    for affil in author.findall("./AffiliationInfo/Affiliation"):
                        affiliations.append(affil.text)
                authorArticleDic['affiliation']= "; ".join(affiliations)
        
                authorArticleDics.append(OrderedDict(authorArticleDic))

    # ceil
    iterCount = math.ceil(int(Count) / BATCH_NUM)

    # get all data
    for i in tqdm(range(iterCount)):
        rootXml = getXmlFromURL(BASEURL_FTCH, {
            'db': SOURCE_DB,
            'query_key': QueryKey,
            'WebEnv': WebEnv,
            'retstart': i * BATCH_NUM,
            'retmax': BATCH_NUM,
            'retmode': 'xml'})
        
        pushData(rootXml)

    # deal with data
    AuthorInfo=pd.DataFrame(authorArticleDics)
    #Articlesinfo.to_csv('pubmed api.csv', mode='a', index=False, header=False, encoding='utf-8-sig')

    Articlesinfo=pd.DataFrame(articleDics)
    Articlesinfo['url']=Articlesinfo['pmid'].apply(lambda x: 'https://pubmed.ncbi.nlm.nih.gov/'+x)

    for ind,i in enumerate(AuthorInfo['affiliation']):
        if '@' in i:
            AuthorInfo.loc[ind,'ISEmail']='Yes'
        
        if ('Biohub' or 'BioHub' or 'biohub' or 'BIOHUB') in i:
            AuthorInfo.loc[ind,'ISBiohub author']='Yes'


    # apply standard author name.
    # extract biohub author for each pmid. put them into right field
    add_bha=AuthorInfo.loc[(AuthorInfo['ISBiohub author']=='Yes'),['pmid','name','affiliation']]  # biohub author  
    add_coa=AuthorInfo.loc[(AuthorInfo['ISEmail']=='Yes'),['pmid','name','affiliation']] # Corresponding author  

    d2=add_bha.groupby('pmid', as_index=False).agg(sum)[['pmid','name']].rename(columns={'name':'Biohub author'})
    d3=add_coa.groupby('pmid', as_index=False).agg(sum)[['pmid','name']].rename(columns={'name':'Corresponding author'})

    d2['pmid']=d2['pmid'].astype(str)
    d3['pmid']=d3['pmid'].astype(str)

    Articlesinfo=pd.merge(Articlesinfo,d2,how='left',on=['pmid'])
    Articlesinfo=pd.merge(Articlesinfo,d3,how='left',on=['pmid'])

    #AuthorInfo.to_csv('pubmed api author.csv',index=False, encoding='utf-8-sig')
    AuthorInfo.to_csv('pubmed api author.csv', mode='a', index=False, header=False, encoding='utf-8-sig')
    print('Pubmed: Fetched '+Count+' records.')
    
    return Articlesinfo


#### 4:mathch author with external file
# method 2 seems better
def standardize_name(df):

    from thefuzz import fuzz


    standard=pd.read_excel('database/Biohub authors.xlsx')  #database/
    standard.dropna(how='all', axis=1,inplace=True)    

    #standard.insert(0, 'author id', np.arange(1, len(standard)+1))
    #standard['MatchName3']=standard['MatchName'].apply(lambda x: x.replace(',','')) 

    standard['MatchName2']=standard['First Name']+' '+standard['Middle']+' '+standard['Last Name']

    for ind,i in enumerate(df['author list']):
        try:
            i=i.split(';')
        except:
            i=i.split(',')

        stand_name_list=list()
        
        for j in i:
            j=re.sub(r'[^\w]', ' ', j.strip('#'))
                
            for ind2,standard_name in enumerate(standard['MatchName2']):
                if fuzz.token_sort_ratio(j,standard_name)>77:  # 77~82
                    x=standard.loc[ind2,'MatchName']
                    stand_name_list.append(x)
                
        df.loc[ind,'Match biohub author']='; '.join(stand_name_list)
        
    return df


def standardize_name2(df):

    import re
    from namematcher import NameMatcher

    standard=pd.read_excel('Biohub authors.xlsx')  #database/
    standard.dropna(how='all', axis=1,inplace=True)    

    #standard.insert(0, 'author id', np.arange(1, len(standard)+1))
    #standard['MatchName2']=standard['MatchName'].apply(lambda x: x.replace(',','')) 

    standard['MatchName3']=standard['First Name']+' '+standard['Middle']+' '+standard['Last Name']

    for ind,i in enumerate(df['author list']):
        try:
            i=i.split(';')
        except:
            i=i.split(',')

        stand_name_list=list()
        
        for j in i:
            j=re.sub(r'[^\w]', ' ', j.strip('#'))
                
            for ind2,standard_name in enumerate(standard['MatchName3']):
                name_matcher = NameMatcher()
                if name_matcher.match_names(j,standard_name)>0.89:  
                    x=standard.loc[ind2,'MatchName']
                    stand_name_list.append(x)
                
        df.loc[ind,'Match biohub author']='; '.join(stand_name_list)
        
    return df


## 5: combine above  
# pre-requirement: create a folder to save everyday search result
def Bibliometrics_Collect(start,
                            end=(datetime.date.today() -
                                datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
                            Keyword='biohub'):
    """
    start = format like '2020-05-10'. default was a week ago. But I'm going to set it as a weeks before our last search date.
        was:
        start = (datetime.date.today() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    end: default is yesterday.
    every search result will save in output folder with date.
    """

    df1 = BioMedrxiv_Search(start_date=start, end_date=end, keyword=Keyword)
    df2 = Arxiv_Search(start_date=start, keyword=Keyword)
    df3 = Pubmed_search(start_date=start, end_date=end, keyword=Keyword)
    df3 = Pubmed_search2(start_date=start, end_date=end, keyword=Keyword)

    df = pd.concat([df1, df2, df3])
    df['record change number'] = 0

    df['epost date2'] = pd.to_datetime(df['epost date'])
    df['publish date2'] = pd.to_datetime(df['publish date'])
    df.reset_index(drop=True,inplace=True)
    df['date'] = [df.loc[i, 'epost date2'] if ( pd.isnull(df.loc[i, 'publish date'])==True or df.loc[i, 'epost date2'] >= df.loc[i, 'publish date2']) else df.loc[i, 'publish date2'] for i in range(len(df))]
    df = df.sort_values(by=['date'], ascending=True).drop(
        columns=['epost date2', 'publish date2'])

    df.insert(0, 'record id', np.arange(1, len(df)+1))
    order = ['record id', 'save datetime', 'author list', 'journal',  'title', 'abstract', 'PMID', 'doi', 'url',
            'version', 'epost date', 'publish date','date',
            'affiliations list', 'all affiliations', 'pdf url',
            'article_source', 'record change number','match result','match id']
    for col in order:
        if col not in df.columns.to_list():
            df[col]=''
    df = df[order]

    df.fillna('', inplace=True)
    df.rename(columns=lambda x: x.lower(), inplace=True)
    df=standardize_name2(df)

    #filename = datetime.datetime.today().strftime('%Y-%m-%d')+'_4searchresult.csv'
    filename = end+'_4searchresult.csv'
    df.to_csv('daily output/'+filename,index=False ,encoding='utf-8-sig')
    print('Fetch done.')
    return(df)


def transfer_date_format(df):
    col=['save datetime','epost date','publish date', 'date']
    for i in col:
        try:
            df[i]=df[i].apply(lambda x: datetime.datetime.strptime(str(x), '%Y-%m-%d %H:%M:%S').strftime('%m/%d/%Y'))
        except:
            continue
    return df



### pre-publication match

# 1. Compare similarity of title: return a score about similarity of two titles
def similarity(txt1, txt2, func=distance.jaccard): # jaccard = best fit for medrxiv data
    """Text similarity on tokenized texts"""
    def asTokens(txt):
        # Uniformise
        txt = unidecode(txt)  # change various hyphens: ‐|-|–
        # Expand acronyms
        txt = re.sub('\\bSARS[- ]*CoV[- ]*2\\b', 'Severe Acute Respiratory Syndrome Coronavirus', txt, flags=re.IGNORECASE) # SARS‐CoV             ‐2 asym...  (special dash + many spaces)
        txt = re.sub('\\bUSA\\b', 'United States of America', txt)
        txt = re.sub('\\bUS\\b', 'United States', txt)
        txt = txt.lower()
        # Tokenize
        blacklist = ['', 'a', 'an', 'and', 'in', 'of', 'on', 'the', 'to']
        tokens = []
        for token in re.split('[^\\w\\d/-]', txt.lower()): # delimiter is non-word except dash (covid-19, non-randomized, open-label)
            if not token in blacklist:
                if len(token) > 1: # in some titles <p> -- tokenized as --> p
                    tokens.append(token if len(token) <= 2 else token[:-1] if token[-1] == 's' else token) # s-stemmer for words with length 3+
        return tokens
    return 1 - func(asTokens(txt1), asTokens(txt2))

# 2. Compare first author: if first author same. return True else, return False
def sameFirstAuthorNameAndInitial(byline1, byline2):
    """Checks if the first author from two bylines is likely to be the same person, accounting for accentuated letters and initials in given names"""
    from unidecode import unidecode
    # e.g., Ana Fernandez-Cruz ~ Ana Fernández Cruz (10.1101/2020.05.22.20110544)
    firstAuthor1 = unidecode(byline1.split(';')[0]).replace('-', ' ')
    firstAuthor2 = unidecode(byline2.split(';')[0]).replace('-', ' ')

    lnfn1 = firstAuthor1.split(',')
    lnfn2 = firstAuthor2.split(',')

    # Comparing last names
    if len(lnfn1) == 1 or len(lnfn2) == 1:                    # no comma found
        return firstAuthor1.lower() == firstAuthor2.lower()
    if lnfn1[0].strip().lower() != lnfn2[0].strip().lower():  # no matching last names
        return False

    # Comparing first names
    fn1 = lnfn1[1].strip()
    fn2 = lnfn2[1].strip()
    # Initials only (unless first names recorded in uppercase by Crossref?)
    if fn1 == fn1.upper() or fn2 == fn2.upper():
        return fn1[0] == fn2[0]

    lenmin = min(3, len(fn1), len(fn2))
    # match on the 3 first characters?
    return fn1[0:lenmin].lower() == fn2[0:lenmin].lower()

