import datetime
import numpy as np
import pandas as pd
import time
import requests
import re
from bs4 import BeautifulSoup as bs
import distance, re
from unidecode import unidecode
import unicodedata
import math
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from collections import OrderedDict
from itertools import permutations




# version 2. using api + beautiful soup + author & aff field
def BioMedrxiv_Search2(start_date,end_date,keyword):

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
	doi=[]
	journal=[]
	version=[]
	url=[]

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
			journal += [article.find('span', attrs={'class': 'highwire-cite-metadata-journal highwire-cite-metadata'}).text.strip()]

			# Get the DOI
			doipan = article.find('span', attrs={'class': 'highwire-cite-metadata-doi'})
			doi += [doipan.text.strip().replace('doi: https://doi.org/', '')]

			# Get the other info
			url += [article.find('a', href=True)['href']]	

		if (page+1)*num_page_results >= int(num_results_text):
			break

		page += 1

	full_records_df = pd.DataFrame(np.column_stack([journal,version, doi,url]),
								columns=['journal','version','doi', 'url']
								)
 
	# change author format
	#full_records_df = full_records_df.assign(author_list=full_records_df['Authors2'].astype(str).apply(lambda x: ','.join(x.replace("[", "").replace("'", "").replace("]", "").split(','))))
	
	if len(full_records_df) !=  0:
	 
		# change url format
		full_records_df['url'] = full_records_df['url'].apply(
			lambda x: 'http://www.biorxiv.org'+x if not x.startswith('http') else x)
  
		for i in full_records_df.index:
			paper_api='https://api.biorxiv.org/details/'+full_records_df.loc[i,'journal'].lower()+'/'+full_records_df.loc[i,'doi']+'/na/JSON'
			try:
				data=requests.get(url=paper_api).json()['collection'][-1]
			except:
				continue
			full_records_df.loc[i,'title']=data['title']
			full_records_df.loc[i,'authors2']=data['authors']
			full_records_df.loc[i,'corresponding author']=data['author_corresponding']
			full_records_df.loc[i,'corresponding author institution']=data['author_corresponding_institution']
			full_records_df.loc[i,'version number']=data['version']
			full_records_df.loc[i,'type']=data['type']
			full_records_df.loc[i,'epost date']=datetime.datetime.strptime(data['date'], '%Y-%M-%d').strftime('%m/%d/%Y')
			full_records_df.loc[i,'abstract']=data['abstract']
			full_records_df.loc[i,'published or not']=data['published'] # NA
			if full_records_df.loc[i,'published or not'] != 'NA':
				pub_api='https://api.biorxiv.org/pubs/'+full_records_df.loc[i,'journal']+'/'+full_records_df.loc[i,'doi']+'/na/JSON'
				data2=requests.get(url=pub_api).json()['collection'][-1]
				full_records_df.loc[i,'confirm published doi']=data2['published_doi']
				#full_records_df.loc[i,'published_journal']=data['published_journal']
				#full_records_df.loc[i,'published_date']=data['published_date']
			else:
				full_records_df.loc[i,'published_doi']='No yet.'
				
		for row_number,paper_url in enumerate(full_records_df.url):
			articles2 = bs(requests.post(paper_url).text, features='html.parser') 
			full_records_df.loc[row_number,'authors']= ("; ".join([i['content'] for i in articles2.find_all('meta', attrs={'name': 'citation_author'})]))  
			full_records_df.loc[row_number,'affiliations list']= ("; ".join([i['content'] for i in articles2.find_all('meta', attrs={'name': 'citation_author_institution'})]))
			
			author_aff=[]
			for i in articles2.find_all("meta",  attrs={'name': ['citation_author','citation_author_institution']}):
				author_aff += [i]
	
			m=[] # m: to store more simple version 'author_aff' 
			for i in range(len(author_aff)): 
				if author_aff[i]['name']=="citation_author":
					m.append('author:')
					m.append(author_aff[i]['content'])

				if author_aff[i]['name']=="citation_author_institution":
					m.append(author_aff[i]['content'])

			ind = [i for i,j in enumerate(m) if j=='author:'] # index
			
			# author_aff: store all [author, aff] result
			author_aff=[m[ind[i]+1:(ind[i+1])] if i<len(ind)-1 else m[ind[i]+1:len(m)] for i in range(len(ind))]

			full_records_df.loc[row_number,'author - affiliations']=str(author_aff)[2:-2].replace("'",'')
			for i in author_aff:
				if ('Biohub' or 'BioHub' or 'biohub' or 'BIOHUB') in str(i):
					full_records_df.loc[row_number,'biohub author']=i[0]

		# full_records_df['affiliations list'] = full_records_df['all affiliations'].apply(
		#	lambda x: x if ';' not in str(x) else '; '.join(sorted(set(y.strip() for y in (x.split(';'))))))  # if x=='' else x
		# full_records_df.loc[:, 'version']=full_records_df.loc[:, 'version'].apply(lambda x: x.split(';')[1])

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
			author_list += [article2.find('div', attrs={'class': 'authors'}).text.replace('Authors:','').replace('authors:','').replace(',',';')]
			time.sleep(.5)
	full_records_df = pd.DataFrame(np.column_stack([title, Epost_date,url,abstract,pdf_url,doi,version,author_list]),
					columns=['title', 'epost date', 'url','abstract','pdf url','doi','version','authors'] )

	if len(full_records_df) !=  0:
		full_records_df.loc[:, 'journal'] = 'arxiv'
		#full_records_df.loc[:, 'version']=full_records_df.loc[:, 'version'].apply(lambda x: x.split(';')[1])

	## keep user informed on task ended about record number
	print('Arxiv: Fetched {:d} records in {:.1f} seconds.'.format(len(full_records_df), time.time() - overall_time))

	return(full_records_df)

# 3.2 pubmed search 2. using api

def Pubmed_search2(start_date, end_date,TERM,save_AuthorInfo=True):
	overall_time = time.time()
 
	#BASEURL_INFO = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi'
	BASEURL_SRCH = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
	BASEURL_FTCH = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'

	# parameters
	SOURCE_DB	= 'pubmed'	 #pubmed, nuccore, nucest, nucgss, popset, protein
	#TERM		 = '(zuckerb* AND biohub) OR "cz biohub" OR "czi biohub"' #'biohub[ad]'
 	#TERM='(zuckerb*[Affiliation] AND biohub[Affiliation]) OR "cz biohub"[Affiliation] OR "czi biohub"[Affiliation]'
	DATE_TYPE	= 'pdat'	   # Type of date used to limit a search. The allowed values vary between Entrez databases, but common values are 'mdat' (modification date), 'pdat' (publication date) and 'edat' (Entrez date). Generally an Entrez database will have only two allowed values for datetype.
	start_date  = datetime.datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y/%m/%d')
	end_date  = datetime.datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y/%m/%d')
	
	SEP		  = '; '
	BATCH_NUM	= 2000

	def mkquery(base_url, params):
		base_url += '?'
		for key, value in zip(params.keys(), params.values()):
			base_url += '{key}={value}&'.format(key=key, value=value)
		url = base_url[0:len(base_url) - 1]
		#print('request url is: ' + url)
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
	if Count== '0':
		return None#print('No result FOUND.')

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
				'title'		: getTextFromNode(article, 'MedlineCitation/Article/ArticleTitle', ''),
				'epost date'   : '/'.join([date.text if date.text != None else ''  for date in article.findall('MedlineCitation/Article/ArticleDate/')]),  # YYYY/MM/DD
				'publish date' : '/'.join([date.text if date.text != None else ''  for date in article.findall('PubmedData/History/PubMedPubDate[@PubStatus="pubmed"]/')]),  # YYYY/MM/DD
				'pmid'					: getTextFromNode(article, 'MedlineCitation/PMID', ''),
				'abstract'				: getTextFromNode(article, 'MedlineCitation/Article/Abstract/AbstractText', ''),
				'doi'					 : getTextFromNode(article, 'MedlineCitation/Article/ELocationID[@EIdType="doi"]', ''),
				'authors'				 : SEP.join([author.find('ForeName').text + ' ' +  author.find('LastName').text if author.find('CollectiveName') == None else author.find('CollectiveName').text for author in article.findall('MedlineCitation/Article/AuthorList/')]),
				'journal'			: getTextFromNode(article, 'MedlineCitation/Article/Journal/Title', ''),
				'keyword'				 : SEP.join([keyword.text if keyword.text != None else ''  for keyword in article.findall('MedlineCitation/KeywordList/')])
			}
			if articleDic['abstract']== None:
				articleDic['abstract']=' '.join([(i.text+i.tail).strip() if i.text !=None else '' for i in article.findall('MedlineCitation/Article/Abstract/AbstractText/')])

			articleDics.append(OrderedDict(articleDic))
   
			#if article.find('MedlineCitation/MeshHeadingList/MeshHeading/') != None:
			 #   tmp = article

			# get author info
			for author in article.findall('MedlineCitation/Article/AuthorList/'):

				# publish author ID
				# * It's only random id. not use for identify author. if you want to identify author, you can use identifier.
				authorId = str(uuid.uuid4())

				# author article
				authorArticleDic = {
					'AuthorNo'		 : authorId,
					'pmid'			 : getTextFromNode(article, 'MedlineCitation/PMID', ''),
					'name'			 : getTextFromNode(author, 'ForeName') + ' ' +  getTextFromNode(author,'LastName') if author.find('CollectiveName') == None else author.find('CollectiveName').text,
					'ORCID'	   : getTextFromNode(author, 'Identifier', '') , # identifier
					#'identifierSource' : getTextFromNode(author, 'Identifier', '', 1, 'Source'),
					'LastName': getTextFromNode(author,'LastName'),
         			'ForeName' : getTextFromNode(author, 'ForeName'),
					'Initials': getTextFromNode(author, 'Initials')
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
	for i in range(iterCount):
	#for i in tqdm(range(iterCount),leave=False,disable=True):#delete leave? # use this line if we want progress bar.
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

	Articlesinfo=pd.DataFrame(articleDics)
	Articlesinfo['url']=Articlesinfo['pmid'].apply(lambda x: 'https://pubmed.ncbi.nlm.nih.gov/'+x)
	Articlesinfo['publish date']=Articlesinfo['publish date'].apply(lambda x:  "/".join(x.split('/')[0:3]))

	for ind,i in enumerate(Articlesinfo['pmid']):
		pubmed_url='https://pubmed.ncbi.nlm.nih.gov/'+str(i)+'/?format=pubmed'
		html = bs(requests.get(pubmed_url).text, features='html.parser')

		for i in html.find('pre').string.replace('\r\n      ','').split('\r\n'):
			if i.startswith('COIS'):
				Articlesinfo.loc[ind,'COIS']=i.replace('COIS- ','')
		
	for ind,i in enumerate(AuthorInfo['affiliation']):
		if '@' in i:
			AuthorInfo.loc[ind,'ISEmail']='Yes'
		else:
			AuthorInfo.loc[ind,'ISEmail']=''
		
		if ('Biohub' or 'BioHub' or 'biohub' or 'BIOHUB') in i:
			AuthorInfo.loc[ind,'ISBiohub author']='Yes'
		else:
			AuthorInfo.loc[ind,'ISBiohub author']=''


	# apply standard author name.
	# extract biohub author for each pmid. put them into right field
	add_bha=AuthorInfo.loc[(AuthorInfo['ISBiohub author']=='Yes'),['pmid','name','affiliation']]  # biohub author  
	add_coa=AuthorInfo.loc[(AuthorInfo['ISEmail']=='Yes'),['pmid','name','affiliation']] # Corresponding author  
	add_bha['name']='; '+add_bha['name']
	add_coa['name']='; '+add_coa['name']

	d2=add_bha.groupby('pmid', as_index=False).agg(sum)[['pmid','name']].rename(columns={'name':'biohub author'})
	d3=add_coa.groupby('pmid', as_index=False).agg(sum)[['pmid','name','affiliation']].rename(columns={'name':'corresponding author','affiliation':'corresponding author institution'}) 

	f = lambda arr: '; '.join(np.unique(arr))
	d4=AuthorInfo.groupby('pmid')['affiliation'].agg([f]).reset_index().rename(columns={'<lambda>':'affiliations list'})

	AuthorInfo['author - affiliations']=AuthorInfo['name']+': '+AuthorInfo['affiliation']
	d5=AuthorInfo.groupby('pmid', as_index=False)['author - affiliations'].agg(sum)

	Articlesinfo=pd.merge(Articlesinfo,d2,how='left',on=['pmid'])
	Articlesinfo=pd.merge(Articlesinfo,d3,how='left',on=['pmid'])
	Articlesinfo=pd.merge(Articlesinfo,d4,how='left',on=['pmid'])
	Articlesinfo=pd.merge(Articlesinfo,d5,how='left',on=['pmid'])

	# check if preprint in biorxiv & medrixv. Didn't find method to check arxiv preprint yet.
	for row_number,doi in enumerate(Articlesinfo.doi):
		for server in ['biorxiv','medrxiv']:
			pub_api='https://api.biorxiv.org/pubs/'+server+'/'+doi
			data=requests.get(url=pub_api).json()['collection']
			if data !=[]:
				Articlesinfo.loc[row_number,'confirm preprint doi']=data[-1]['preprint_doi']
				break
			else:
				continue

	AuthorInfo['ORCID'] = AuthorInfo['ORCID'].apply(ORCID_format)
	
	if save_AuthorInfo==True:
		#AuthorInfo.to_csv('database/pubmed api author.csv',index=False, encoding='utf-8-sig')
		AuthorInfo.drop('author - affiliations',axis=1).to_csv('database/pubmed api author.csv', mode='a', index=False, header=False, encoding='utf-8-sig')
	
 	#Articlesinfo.to_csv('pubmed api.csv', mode='a', index=False, header=False, encoding='utf-8-sig')
	print('Pubmed: Fetched '+Count+' records in {:.1f} seconds.'.format(time.time() - overall_time))
	
	Articlesinfo.fillna('',inplace=True)
	Articlesinfo['biohub author']=Articlesinfo['biohub author'].str.strip('; ')
	Articlesinfo['corresponding author']=Articlesinfo['corresponding author'].str.strip('; ')
	return Articlesinfo

# search daily pubmed author
def Pubmed_search_author(start_date,end_date):
    # start_date=end_date
    author=pd.read_excel('database/Biohub authors.xlsx')
    author_list=author['Last Name']+', '+author['First Name']+ '[FAU]'
    df=pd.DataFrame()

    for term in author_list:
        try:
            dt=Pubmed_search2(start_date, end_date,TERM=term,save_AuthorInfo=True)
            dt['biohub author']=term.replace('[FAU]','')
            if isinstance(dt, pd.DataFrame):
                df=pd.concat([df,dt],ignore_index=True)
        except:
            pass
    return df

#### 4.1: mathch author with external file Based on bill function idea.
# preprint
def ORCID_format (orcid):
	try:
		find_orcid = re.search (r"([0-9]{4})-?([0-9]{4})-?([0-9]{4})-?([0-9]{3}[0-9X])", orcid)
	except:
		find_orcid = False
	if find_orcid:
		formatted_orcid = "https://orcid.org/"+find_orcid.group(1)+"-"+find_orcid.group(2)+"-"+find_orcid.group(3)+"-"+find_orcid.group(4)
	else:
		formatted_orcid = "nan"
	return (formatted_orcid)

def strip_accents(text):
	try:
		text = unicode(text, 'utf-8')
	except NameError: # unicode is a default on python 3 
		pass

	text = unicodedata.normalize('NFD', text)\
		.encode('ascii', 'ignore')\
		.decode("utf-8")

	return (str(text))

def text_field_set_null_to_blank (text): 
	if isinstance(text,str):
		return (text)
	else:
		return ("")

def authormatch_pre(df):
    standard=pd.read_excel('database/Biohub authors.xlsx',
                        dtype = { 
                            'Middle' : str,
                            'ORCID' : str,
                            'Cohort' : str,
                            'Email-Preferred' : str,
                            'Email 2' : str},
                        converters = { 
                            'Ambiguous initials' : lambda x: np.where(x == True, True, False),
                            'Ambiguous incomplete full' : lambda x: np.where(x == True, True, False),
                        })
    standard.dropna(how='all', axis=1,inplace=True)	
    for i in standard.columns[2:7]:
        standard[i]=standard[i].apply(strip_accents).str.lower().replace("[","").replace("]","")

    #use a new df to store
    test=standard.iloc[:,2:7]  #后面可以加上2:9, & email相等的话

    for ind,i in enumerate(test['Middle']):
        combines_3=[]
        combines_2=[]
        combines_1=[]
        combines_0=[]
        
        if i=='nmi': # no middle name
            # "FN-NMI" : 3  # firstname lastname  & Lastname firstname
            for result in permutations(test.iloc[ind,1:3], 2):
                combines_3.append(" ".join(result))
            
            # FI-NMI  # firstname[0] lastname  & lastname firstname[0]
            for result in permutations([test.loc[ind,'First Name'][0],test.loc[ind,'Last Name']], 2):
                combines_1.append(" ".join(result))

            if (test.loc[ind,'Nickname'] != test.loc[ind,'First Name']):
                # NN-NMI
                for result in permutations([test.loc[ind,'Nickname'],test.loc[ind,'Last Name']], 2):
                    combines_3.append(" ".join(result))
                    
                # for result in permutations([test.loc[ind,'Nickname'],test.loc[ind,'Last Name'][0]], 2):
                #     combines.append(" ".join(result))
            
        else:
            # FN 
            for result in permutations(test.iloc[ind,1:3], 2):
                combines_2.append(" ".join(result))
                
            # FI-NMI  # firstname[0] lastname  & lastname firstname[0]
            for result in permutations([test.loc[ind,'First Name'][0],test.loc[ind,'Last Name']], 2):
                combines_0.append(" ".join(result))
            
            # FN-MN"            
            combines_3.append(test.loc[ind,'First Name']+' '+test.loc[ind,'Middle'][0]+' '+test.loc[ind,'Last Name'])
            combines_3.append(test.loc[ind,'Last Name']+' '+test.loc[ind,'Middle'][0]+' '+test.loc[ind,'First Name'])
            
            # FN-MI
            combines_3.append(test.loc[ind,'Last Name']+' '+test.loc[ind,'First Name']+' '+test.loc[ind,'Middle'][0])
            
            # FI-MI
            combines_1.append(test.loc[ind,'Last Name']+' '+test.loc[ind,'First Name'][0]+' '+test.loc[ind,'Middle'][0])
            
            if (test.loc[ind,'Nickname'] != test.loc[ind,'First Name']):
                # NN
                for result in permutations([test.loc[ind,'Nickname'],test.loc[ind,'Last Name']], 2):
                    combines_2.append(" ".join(result))
                
            if len(test['Middle'])>1:
                # FN-MN"
                combines_3.append(test.loc[ind,'First Name']+' '+test.loc[ind,'Middle']+' '+test.loc[ind,'Last Name'])
                combines_3.append(test.loc[ind,'Last Name']+' '+test.loc[ind,'Middle']+' '+test.loc[ind,'First Name'])
                
                # FI-MN
                combines_3.append(test.loc[ind,'Last Name']+' '+test.loc[ind,'First Name'][0]+' '+test.loc[ind,'Middle'])
                
        test.loc[ind,'combination3']='; '.join(combines_3)
        test.loc[ind,'combination2']='; '.join(combines_2)
        test.loc[ind,'combination1']='; '.join(combines_1)
        test.loc[ind,'combination0']='; '.join(combines_0)

    test['combination_all']= test['combination0'] + test['combination1'] + test['combination2'] + test['combination3']
    test['combination_23']= test['combination2'] + test['combination3']
    test['combination_01']= test['combination0'] + test['combination1'] 


    df.fillna('', inplace=True)
    preprint_list=['biorxiv','bioRxiv','medrxiv','medRxiv','arxiv','arXiv']
    pre_ind=df[df['journal'].isin(preprint_list)].index
    for ind,i in enumerate(df.loc[pre_ind,'authors']):
        try:
            i=i.split(';')
        except:
            i=i.split(',')

        yes_name_list=list()
        maybe_name_list=list()
        
        for j in i:  # j is every single author name
            j=re.sub(r'[^\w]', ' ', j.strip('#'))
            j=j.replace('  ',' ').strip(' ').replace('-','').lower()

            for ind2 in test.index:
                if j in test.loc[ind2,'combination_01']:
                    x=standard.loc[ind2,'MatchName']
                    maybe_name_list.append(x)
                
                if j in test.loc[ind2,'combination_23']:
                    x=standard.loc[ind2,'MatchName']
                    yes_name_list.append(x)
                    
        df.loc[ind,'possible biohub author']='; '.join(maybe_name_list)
        df.loc[ind,'format biohub author']='; '.join(yes_name_list)

    return df



#### 4.2: mathch author
# pubmed
def authormatch_pub(df):
    authors=pd.read_csv('database/pubmed api author.csv', encoding='utf-8-sig')
    
    condition = set() # for scoring Biohub authors

    Email_address_found = set()

    BiohubAuthors_df = pd.read_excel('database/Biohub authors.xlsx',
                                    dtype = { 
                                        'Middle' : str,
                                        'ORCID' : str,
                                        'Cohort' : str,
                                        'Email-Preferred' : str,
                                        'Email 2' : str},
                                    converters = { 
                                        'Ambiguous initials' : lambda x: np.where(x == True, True, False),
                                        'Ambiguous incomplete full' : lambda x: np.where(x == True, True, False),
                                    })

    BiohubAuthors_df['ORCID'] = BiohubAuthors_df['ORCID'].apply(ORCID_format)

    BiohubAuthors_df['MatchName'] = BiohubAuthors_df['MatchName'].apply(strip_accents)
    BiohubAuthors_df['Last Name'] = BiohubAuthors_df['Last Name'].apply(strip_accents)
    BiohubAuthors_df['First Name'] = BiohubAuthors_df['First Name'].apply(strip_accents)
    BiohubAuthors_df['Nickname'] = BiohubAuthors_df['Nickname'].apply(strip_accents)

    BiohubAuthors_df['Email 2'] = BiohubAuthors_df['Email 2'].apply(text_field_set_null_to_blank)

    BiohubAuthors_df['Length of award'] = BiohubAuthors_df['Length of award'].fillna(0).astype(int)

    BiohubAuthors_df['Award start date'] = BiohubAuthors_df['Award start date'].dt.date
    BiohubAuthors_df['Award end date'] = BiohubAuthors_df['Award end date'].dt.date

    BiohubAuthors_list = BiohubAuthors_df.values.tolist()
    BiohubAuthors_columns = BiohubAuthors_df.columns.tolist()

    biohub_authors = {} # column names are indexed in BiohubAuthors_columns.index("column name")
    biohub_authors_ORCID = {}
    biohub_authors_email = {}
    biohub_authors_variations = {} 
    biohub_authors_awarddates = {}

    name_match_weight = {
        "FN-NMI" : 3, # "FN-NMI" : first name-no middle initial
        "NN-NMI" : 3, # "NN-NMI" : Nickname-no middle initial
        "FN-MN" : 3,  # "FN-MN" : first name-middle name
        "FI-MN" : 3,  # "FI-MN" : first initial-middle name-(when preferred)
        "FN-MI" : 3,  # "FN-MI" : first name-middle initial
        "FN" : 2,     # "FN" : first name, omitting middle initial
        "NN" : 2,     # "NN" : Nickname-omitting middle initial
        "FI-MI" : 1,  # "FI-MI" : first initial-middle initial
        "FI-NMI" : 1, # "FI-NMI" : first initial-no middle initial
        "FI" : 0      # "FI" : first initial-omitting middle initial
    }

    for i in range (len(BiohubAuthors_df)):
        if not BiohubAuthors_df.loc[i]['MatchName'] in biohub_authors_awarddates:
            biohub_authors_awarddates[BiohubAuthors_df.loc[i]['MatchName']] = []
            if  BiohubAuthors_df.loc[i]['Award start date'] ==  BiohubAuthors_df.loc[i]['Award start date']: # check for null
                biohub_authors_awarddates[BiohubAuthors_df.loc[i]['MatchName']].append(BiohubAuthors_df.loc[i]['Award start date'])
                biohub_authors_awarddates[BiohubAuthors_df.loc[i]['MatchName']].append(BiohubAuthors_df.loc[i]['Award end date'])
            else:
                biohub_authors_awarddates[BiohubAuthors_df.loc[i]['MatchName']].append(datetime.date(2000, 1, 1))
                biohub_authors_awarddates[BiohubAuthors_df.loc[i]['MatchName']].append(datetime.date(3000, 1, 1))


    for row in BiohubAuthors_list:
        MatchName = row[BiohubAuthors_columns.index("MatchName")]
        biohub_authors[MatchName] = row
            
        LastName = row[BiohubAuthors_columns.index("Last Name")].lower()
        FirstName = row[BiohubAuthors_columns.index("First Name")].lower()
        find_bracket = FirstName.find("[") # brackets used to indicate use of first initial as alternate to first name: "J[ames]"
        if find_bracket != -1:
            FirstName = FirstName.replace("[","").replace("]","")
        Nickname = row[BiohubAuthors_columns.index("Nickname")].lower()
        Middle = row[BiohubAuthors_columns.index("Middle")].lower()

        EntryName = LastName+", "+FirstName
        EntryFI = LastName+", "+FirstName[0:1]
        if Middle == "nmi":
            biohub_authors_variations[EntryName] = [MatchName, "FN-NMI"] # first name-no middle initial
            biohub_authors_variations[EntryFI] = [MatchName, "FI-NMI"] # first initial-no middle initial
            if Nickname != FirstName:
                EntryName = LastName+", "+Nickname
                biohub_authors_variations[EntryName] = [MatchName, "NN-NMI"] # Nickname-no middle initial
        else:
            biohub_authors_variations[EntryName] = [MatchName, "FN"] # first name, omitting middle initial
            biohub_authors_variations[EntryFI] = [MatchName, "FI"] # first initial-omitting middle initial
            if Nickname != FirstName:
                EntryName = LastName+", "+Nickname
                biohub_authors_variations[EntryName] = [MatchName, "NN"] # Nickname-omitting middle initial
            if len(Middle) > 1:
                EntryName = LastName+", "+FirstName+" "+Middle
                biohub_authors_variations[EntryName] = [MatchName, "FN-MN"] # first name-middle name
            if find_bracket != -1: 
                EntryName = EntryFI+" "+Middle
                biohub_authors_variations[EntryName] = [MatchName, "FI-MN"] # first initial-middle name-preferred
            EntryName = LastName+", "+FirstName+" "+Middle[0:1]
            biohub_authors_variations[EntryName] = [MatchName, "FN-MI"] # first name-middle initial
            EntryName = EntryFI+" "+Middle[0:1]
            if EntryName not in biohub_authors_variations:
                biohub_authors_variations[EntryName] = [MatchName, "FI-MI"] # first initial-middle initial
        
        email_list = re.findall (r"[a-zA-Z][a-zA-Z0-9_.-]*@[a-zA-Z][a-zA-Z0-9_.-]*", row[BiohubAuthors_columns.index("Email-Preferred")]+" "+row[BiohubAuthors_columns.index("Email 2")])
        for item in email_list:
            item = item.lower()
            biohub_authors_email[item] = row[BiohubAuthors_columns.index("MatchName")]
            
        if row[BiohubAuthors_columns.index("ORCID")] != 'nan':
            biohub_authors_ORCID[row[BiohubAuthors_columns.index("ORCID")]] = row[BiohubAuthors_columns.index("MatchName")]

    biohub_authors_variations_full = {} # includes compressed versions of names, omitting spaces, dashes, apostrophes, etc   

    for key,value in biohub_authors_variations.items():
        biohub_authors_variations_full[key] = value
        compress = key.replace(" ","").replace("-","").replace("\'","").replace(",",", ")
        if key[-2:-1] == " " and key[-3:-2] != ",":
            compress = compress[:-1]+key[-2:] # restore the penultimate space if there is one
        if compress != key:
            biohub_authors_variations_full[compress] = value


    # author_fields notes:
    #    "ForeName" includes middle initials
    #    "Initials" includes first name initial
    #    "Email" field may include email addresses for all authors with listed email addresses, not just the current author
    #    "BiohubAuthor" = "investigator", "intramural" (group/platform leader, etc)
    #    "MatchName" = uniform version of matched name for investigator or group leader, used for joining tables
    #    "MatchType" = Abbreviations for first name, first initial, NMI, etc. in biohub_authors_variations_full
    #    "TrustMatch" = Yes, Maybe, No - based on MatchType (if match based on initials) and if there are matching
    #                   or mis-matching ORCID IDs, email addresses, or campus affiliations
    #    "OrcidMatch" = True if record ORCID matches with Biohub author ORCID; False only if there are values for both that don't match
    #    "EmailMatch" = True if record email matches with Biohub author email
    #                       - ignore if there is a mis-match: Affiliation records for an author occasionally include 
    #                         email addresses for co-authors
    #    "AffiliationMatch" = True if record Affiliation includes a match to Biohub author campus affiliation
    #    "Biohub" -> "Chan Zuckerberg Biohub" or variants found in affiliation or email address
    #    "Biohub-Funding" -> "Chan Zuckerberg Biohub" or variants found in grant list
    authors.drop_duplicates(subset=authors.columns[0:10],inplace=True)
    author_fields = ['AuthorNo', 'pmid', 'name', 'ORCID', 'LastName', 'ForeName', 'Initials',
                    'affiliation', 'ISEmail', 'ISBiohub author','Suffix',
                    'BiohubAuthor','MatchName','TrustMatch', 'MatchType','OrcidMatch','EmailMatch',
                    'AffiliationMatch', 'Biohub', 'Biohub-Funding', 'Stanford', 'UCSF',
                    'Berkeley','Email',   'EqualContrib']

    for col in author_fields:
        if col not in authors.columns.to_list():
            authors[col]=''
    authors = authors[author_fields]
    authors.fillna('', inplace=True)

    # score for Biohub authorship

    for i in range(len(authors)):
        Name = strip_accents(authors.loc[i,"LastName"].lower()+", "+authors.loc[i,"ForeName"].lower())
        MatchName = ""
        MatchType = ""
        if Name in biohub_authors_variations_full:
            MatchName = biohub_authors_variations_full[Name][0]
            MatchType = biohub_authors_variations_full[Name][1] 
        else:
            compress = Name.replace(" ","").replace("-","").replace("\'","").replace(",",", ")
            if Name[-2:-1] == " " and Name[-3:-2] != ",":
                compress = compress[:-1]+Name[-2:] # restore the penultimate space if there is one
            if compress != Name and compress in biohub_authors_variations_full:
                MatchName = biohub_authors_variations_full[compress][0]
                MatchType = biohub_authors_variations_full[compress][1] 
            elif len(authors.loc[i,'ForeName'])>=2:
                if authors.loc[i,'ForeName'][-2] != " " and authors.loc[i,'ForeName'].find(" ") != -1:
                    # if the full middle name is given in the Pubmed record, which may not be present in the Biohub author record
                    forename = authors.loc[i,'ForeName'][:authors.loc[i,'ForeName'].find(" ")+2]
                    Name2 = strip_accents(authors.loc[i,'LastName'].lower()+", "+forename.lower())
                    if Name2 in biohub_authors_variations_full:
                        MatchName = biohub_authors_variations_full[Name2][0]
                        MatchType = biohub_authors_variations_full[Name2][1] 
                        print ("Found full middle name for Biohub author",Name,"PMID",authors.loc[i,'pmid'])
                    else:
                        compress = Name2.replace(" ","").replace("-","").replace("\'","").replace(",",", ")
                        if Name2[-2:-1] == " " and Name[-3:-2] != ",":
                            compress = compress[:-1]+Name[-2:] # restore the penultimate space if there is one
                        if compress != Name2:
                            if compress in biohub_authors_variations_full:
                                MatchName = biohub_authors_variations_full[compress][0]
                                MatchType = biohub_authors_variations_full[compress][1] 
                                print ("Found full middle name for Biohub author",Name,"PMID",authors.loc[i,'pmid'])
                    
                # ToDo - backup if there wasn't a match of the author name: 
                # else: 
                #       if the author record has an ORCID ID, try searching for it in the Biohub Author ORCID ID dictionary
                #       and alert user if there is a match; ditto if there is an email address
                
        if MatchName != "":
            authors.loc[i,'MatchName'] = MatchName
            authors.loc[i,"MatchType"] = MatchType
            authors.loc[i,"BiohubAuthor"] = biohub_authors[MatchName][BiohubAuthors_columns.index("Role")]
            authors.loc[i,"AffiliationMatch"] =  authors.iloc[i,author_fields.index(biohub_authors[MatchName][BiohubAuthors_columns.index("Campus (simple)")])]
            if authors.loc[i,"AffiliationMatch"] != True:
                if len(authors.loc[i,"BiohubAuthor"]) > 0:
                    if authors.loc[i,"Biohub"] == True:
                        authors.loc[i,"AffiliationMatch"] = True 
            orcid_from_record = authors.loc[i,"ORCID"]
            orcid_from_biohub_authors = biohub_authors[MatchName][BiohubAuthors_columns.index("ORCID")]
            if orcid_from_record == orcid_from_biohub_authors:
                authors.loc[i,"OrcidMatch"] = True
            elif len(orcid_from_record) > 0:
                if orcid_from_biohub_authors == "nan":
                    print ("ORCID ID found for \""+MatchName+"\" in Pubmed",authors.loc[i,'pmid'],":\n",orcid_from_record,"\n")
                else:
                    authors.loc[i,"OrcidMatch"] = False
                    print ("Mismatched ORCID ID found for \""+MatchName+"\" in Pubmed",authors.loc[i,'pmid'],"\n  ORCID ID in publication:",orcid_from_record,"\n  ORCID ID from \"Biohub authors.xlsx\" file:",orcid_from_biohub_authors,"\n")
            if str(authors.loc[i,'pmid'])+" "+authors.loc[i,'MatchName'] in Email_address_found:
                authors.loc[i,'EmailMatch'] = True
            
            # set TrustMatch:
            if authors.loc[i,"OrcidMatch"] or authors.loc[i,'EmailMatch'] or authors.loc[i,"Biohub"]:
                authors.loc[i,"TrustMatch"] = "Yes"
                condition.add(1)
            elif authors.loc[i,"AffiliationMatch"] and name_match_weight[MatchType] >= 2:
                authors.loc[i,"TrustMatch"] = "Yes"
                condition.add(2)
            elif authors.loc[i,"AffiliationMatch"] != True and name_match_weight[MatchType] >= 2:
                if biohub_authors[MatchName][BiohubAuthors_columns.index("Ambiguous incomplete full")] == True and name_match_weight[MatchType] == 2:
                    authors.loc[i,'TrustMatch'] = "Maybe"
                    condition.add(3)
                else:
                    authors.loc[i,'TrustMatch'] = "Yes"
                    condition.add(4)
            elif authors.loc[i,'AffiliationMatch'] and name_match_weight[MatchType] == 1 and biohub_authors[MatchName][BiohubAuthors_columns.index("Ambiguous initials")] == False:
                authors.loc[i,'TrustMatch'] = "Yes"
                condition.add(5)
            elif authors.loc[i,'AffiliationMatch'] and name_match_weight[MatchType] == 0 and biohub_authors[MatchName][BiohubAuthors_columns.index("Ambiguous initials")] == False:
                authors.loc[i,'TrustMatch'] = "Maybe"
                condition.add(6)
                
            elif authors.loc[i,'AffiliationMatch'] and name_match_weight[MatchType] == 1 and biohub_authors[MatchName][BiohubAuthors_columns.index("Ambiguous initials")] == True:
                authors.loc[i,'TrustMatch'] = "Maybe"
                condition.add(7)
            elif authors.loc[i,'AffiliationMatch'] and name_match_weight[MatchType] == 0 and biohub_authors[MatchName][BiohubAuthors_columns.index("Ambiguous initials")] == True:
                authors.loc[i,'TrustMatch'] = "No"
                condition.add(8)
                
            elif authors.loc[i,'AffiliationMatch'] != True and name_match_weight[MatchType] == 1 and biohub_authors[MatchName][BiohubAuthors_columns.index("Ambiguous initials")] == False:
                authors.loc[i,'TrustMatch'] = "Maybe"
                condition.add(9)
            elif authors.loc[i,'AffiliationMatch'] != True and name_match_weight[MatchType] == 0 and biohub_authors[MatchName][BiohubAuthors_columns.index("Ambiguous initials")] == False:
                authors.loc[i,'TrustMatch'] = "No"
                condition.add(10)
            elif authors.loc[i,'AffiliationMatch'] != True and name_match_weight[MatchType] <= 1 and biohub_authors[MatchName][BiohubAuthors_columns.index("Ambiguous initials")] == True:
                authors.loc[i,'TrustMatch'] = "No"
                condition.add(11)
            else:
                print ("TrustMatch error - didn't match any conditions, Author-PMID",Name,authors[i][author_fields.index("pmid")])
                print (authors.loc[i,'AffiliationMatch'],name_match_weight[MatchType], biohub_authors[MatchName][BiohubAuthors_columns.index("Ambiguous initials")])

            # Suffix match - 
            # for now, no Biohub authors have a suffix; when one does, we'll have to create a field for it; for now:
            
            if len(authors.loc[i,'Suffix'])>0:
                authors.loc[i,'TrustMatch'] = "No"

    authors.to_csv('database/pubmed api author.csv',index=False, encoding='utf-8-sig')		      
    
    # save them to dataframe.
    df['format biohub author']=''
    df.pmid = pd.to_numeric(df.pmid, errors='coerce')
    authors.fillna('',inplace=True)
    authors=authors[ authors['pmid'].isin(list(df['pmid'].astype('Int64')))] 
    
    #return authors
    for ind in authors['pmid'].index:
        if authors.loc[ind,'TrustMatch']=='Yes':
            #if authors.loc[ind,'MatchName'] not in df.loc[df[df['pmid']==authors.loc[ind,'pmid']].index,'biohub author'].str.lower().replace(', ',' '):
            df.loc[df[df['pmid']==authors.loc[ind,'pmid']].index,'format biohub author'] += '; '+authors.loc[ind,'MatchName']
        if authors.loc[ind,'TrustMatch']=='Maybe':
            df.loc[df[df['pmid']==authors.loc[ind,'pmid']].index,'possible biohub author'] += '; '+authors.loc[ind,'MatchName']

    df['format biohub author']=df['format biohub author'].str.strip('; ')
    return df

## author match. for single name input
# return old_name, format_name,possible percent
def authormatch(name):
    test=pd.read_csv('database/biohub author combination.csv', encoding='utf-8-sig')
    degree='no'
    format_name=re.sub(r'[^\w]', ' ', name.strip('#'))
    format_name=format_name.replace('  ',' ').strip(' ').replace('-','').lower()
    
    if name=='':
        return name,format_name,degree
    for ind2 in test.index:
        if format_name in test.loc[ind2,'combination_23']:
            format_name=test.loc[ind2,'MatchName']
            degree='yes'
            return name,format_name,degree
        
        if format_name in test.loc[ind2,'combination_01']:
            format_name=test.loc[ind2,'MatchName']
            degree='maybe'
            return name,format_name,degree
        
    return name,name,degree


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

	df1 = BioMedrxiv_Search2(start_date=start, end_date=end, keyword=Keyword)
	df2 = Arxiv_Search(start_date=start, keyword=Keyword)
	df3 = Pubmed_search2(start_date=start, end_date=end,TERM='(zuckerb* AND biohub) OR "cz biohub" OR "czi biohub"',save_AuthorInfo=True)
	df4 = Pubmed_search_author(start_date=end,end_date=end)

	df = pd.concat([df1, df2, df3,df4])
 
	try:
		df=df.drop_duplicates(subset='pmid', keep="last")
	except:
		pass
	df['record change number'] = 0

	try:
		df['epost date2'] = pd.to_datetime(df['epost date'])
		df['publish date2'] = pd.to_datetime(df['publish date'])
	except:
		df['epost date2'] = df['epost date']#+'nochange'
		df['publish date2'] = df['publish date']#+'nochange'
	
	df.reset_index(drop=True,inplace=True)
	df['date'] = [df.loc[i, 'epost date2'] if ( pd.isnull(df.loc[i, 'publish date'])==True or df.loc[i, 'epost date2'] >= df.loc[i, 'publish date2']) else df.loc[i, 'publish date2'] for i in range(len(df))]
	df = df.sort_values(by=['date'], ascending=True).drop(
		columns=['epost date2', 'publish date2'])
	df['save datetime']=end  # search end date
	#df['save datetime'] = datetime.datetime.now().strftime('%m/%d/%Y') # when we save it

	df.insert(0, 'record id', np.arange(1, len(df)+1))
	order = ['record id', 'save datetime', 'biohub author','possible biohub author','format biohub author','corresponding author','corresponding author institution',
			'journal', 'doi', 'pmid',
   		'title','url','abstract', 'keyword',  'pdf url', 'version',  'version number', 'type', 
      		'date','epost date', 'publish date',
			'authors','authors2', 'affiliations list', 'author - affiliations',
			'published or not', 'confirm published doi',  'confirm preprint doi',
			'possible match result','match id', 'record change number']
	for col in order:
		if col not in df.columns.to_list():
			df[col]=''
	df = df[order]

	df.fillna('', inplace=True)
	df.rename(columns=lambda x: x.lower(), inplace=True)
 
	df=authormatch_pre(df)
	df=authormatch_pub(df)

	filename = end+'_4searchresult.csv'
	df.to_csv('daily output/'+filename,index=False ,encoding='utf-8-sig')
	print('Fetch done.')
	return(df)


def transfer_date_format(df):
	col=['save datetime','epost date','publish date','date']
	for i in col:
		try:
			df[i]=df[i].apply(lambda x: datetime.datetime.strptime(str(x), '%Y-%m-%d %H:%M:%S').strftime('%m/%d/%Y'))
		except:
			continue
	return df



##### pre-publication match
# 1. Compare similarity of title: return a score about similarity of two titles
def similarity(txt1, txt2, func=distance.jaccard): # jaccard = best fit for medrxiv data
	"""Text similarity on tokenized texts"""
	def asTokens(txt):
		# Uniformise
		txt = unidecode(txt)  # change various hyphens: ‐|-|–
		# Expand acronyms
		txt = re.sub('\\bSARS[- ]*CoV[- ]*2\\b', 'Severe Acute Respiratory Syndrome Coronavirus', txt, flags=re.IGNORECASE) # SARS‐CoV			 ‐2 asym...  (special dash + many spaces)
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
	if len(lnfn1) == 1 or len(lnfn2) == 1:					# no comma found
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

