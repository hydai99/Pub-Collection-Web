import datetime
import numpy as np
import pandas as pd
import time
import requests
import re
from bs4 import BeautifulSoup as bs
import distance, re
from unidecode import unidecode

import math
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from collections import OrderedDict
from tqdm import tqdm_notebook as tqdm



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
			#print(paper_api)
			data=requests.get(url=paper_api).json()['collection'][-1]
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
				
		#full_records_df.loc[:,'save datetime'] = datetime.datetime.now().strftime('%m/%d/%Y') # when we save it

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

			full_records_df.loc[row_number,'author - affiliations']=str(author_aff)
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
			author_list += [article2.find('div', attrs={'class': 'authors'}).text.replace('authors:','')]
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

def Pubmed_search2(start_date, end_date):
	overall_time = time.time()
 
	#BASEURL_INFO = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi'
	BASEURL_SRCH = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
	BASEURL_FTCH = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'

	# parameters
	SOURCE_DB	= 'pubmed'	 #pubmed, nuccore, nucest, nucgss, popset, protein
	#TERM		 = 'biohub[ad]'	 # Entrez text query.   # (zuckerb* AND biohub) OR "cz biohub" OR "czi biohub"
	TERM='(zuckerb*[Affiliation] AND biohub[Affiliation]) OR "cz biohub"[Affiliation] OR "czi biohub"[Affiliation]'
	DATE_TYPE	= 'pdat'	   # Type of date used to limit a search. The allowed values vary between Entrez databases, but common values are 'mdat' (modification date), 'pdat' (publication date) and 'edat' (Entrez date). Generally an Entrez database will have only two allowed values for datetype.
	start_date  = datetime.datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y/%m/%d')
	end_date  = datetime.datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y/%m/%d')
	
	SEP		  = ' ; '
	BATCH_NUM	= 2000

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
					'authorId'		 : authorId,
					'pmid'			 : getTextFromNode(article, 'MedlineCitation/PMID', ''),
					'name'			 : getTextFromNode(author, 'ForeName') + ' ' +  getTextFromNode(author,'LastName') if author.find('CollectiveName') == None else author.find('CollectiveName').text,
					'identifier'	   : getTextFromNode(author, 'Identifier', '') ,
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

	Articlesinfo=pd.DataFrame(articleDics)
	Articlesinfo['url']=Articlesinfo['pmid'].apply(lambda x: 'https://pubmed.ncbi.nlm.nih.gov/'+x)

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

	d2=add_bha.groupby('pmid', as_index=False).agg(sum)[['pmid','name']].rename(columns={'name':'biohub author'})
	d3=add_coa.groupby('pmid', as_index=False).agg(sum)[['pmid','name','affiliation']].rename(columns={'name':'corresponding author','affiliation':'corresponding author institution'}) 

	f = lambda arr: ';'.join(np.unique(arr))
	d4=AuthorInfo.groupby('pmid')['affiliation'].agg([f]).reset_index().rename(columns={'<lambda>':'affiliations list'})

	AuthorInfo['author - affiliations']=AuthorInfo['name']+': '+AuthorInfo['affiliation']
	d5=AuthorInfo.groupby('pmid', as_index=False)['author - affiliations'].agg(sum)

	#d2['pmid']=d2['pmid'].astype(str)
	#d3['pmid']=d3['pmid'].astype(str)
	#d4['pmid']=d4['pmid'].astype(str)

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

	AuthorInfo.to_csv('database/pubmed api author.csv',index=False, encoding='utf-8-sig')
	#AuthorInfo.to_csv('database/pubmed api author.csv', mode='a', index=False, header=False, encoding='utf-8-sig')
	#Articlesinfo.to_csv('pubmed api.csv', mode='a', index=False, header=False, encoding='utf-8-sig')
	print('Pubmed: Fetched '+Count+' records in {:.1f} seconds.'.format(time.time() - overall_time))
	
	return Articlesinfo


#### 4:mathch author with external file
# method 2 seems better

def standardize_name2(df):

	import re
	from namematcher import NameMatcher

	standard=pd.read_excel('database/Biohub authors.xlsx') 
	standard.dropna(how='all', axis=1,inplace=True)	

	#standard.insert(0, 'author id', np.arange(1, len(standard)+1))
	#standard['MatchName2']=standard['MatchName'].apply(lambda x: x.replace(',','')) 

	standard['MatchName3']=standard['First Name']+' '+standard['Middle']+' '+standard['Last Name']

	for ind,i in enumerate(df['authors']):
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
				
		df.loc[ind,'possible biohub author']='; '.join(stand_name_list)
		
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

	df1 = BioMedrxiv_Search2(start_date=start, end_date=end, keyword=Keyword)
	df2 = Arxiv_Search(start_date=start, keyword=Keyword)
	df3 = Pubmed_search2(start_date=start, end_date=end)
	#df3.rename(columns={'pmid':'PMID'}, inplace=True) 

	df = pd.concat([df1, df2, df3])
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
	order = ['record id', 'save datetime', 'biohub author','possible biohub author','corresponding author','corresponding author institution',
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
	df=standardize_name2(df)

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



### pre-publication match

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

