"""Optional documented Brave web-search API. Never used without explicit consent."""
import os,json
from urllib.parse import urlencode


def validate_scope(url,credentials):
    from urllib.parse import urlsplit
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname!='api.search.brave.com' or p.port or p.path!='/res/v1/web/search' or p.fragment:
        raise ValueError('Search credentials restricted to Brave search endpoint')
    if set(credentials)!={'X-Subscription-Token'}:
        raise ValueError('Invalid search API headers')
    token=credentials['X-Subscription-Token']
    if not isinstance(token,str) or not 1<=len(token)<=1000 or any(ord(c)<33 or ord(c)>126 for c in token):
        raise ValueError('Invalid search credential')


class BraveSearch:
    """Provider setup is optional, local and material: no account/cost assumed."""
    def __init__(self):
        if os.environ.get('JOBHUNTER_SEARCH_ACCESS_APPROVED')!='1' or os.environ.get('JOBHUNTER_SEARCH_COST_APPROVED')!='1':
            raise ValueError('Search API requires explicit local access and cost approval')
        self.token=os.environ.get('BRAVE_SEARCH_API_KEY','')
        validate_scope('https://api.search.brave.com/res/v1/web/search',{'X-Subscription-Token':self.token})

    def search(self,query):
        from .network import get
        url='https://api.search.brave.com/res/v1/web/search?'+urlencode({
            'q':f'{query.text} {query.region} careers jobs','search_lang':query.language,'count':10})
        body,typ=get(url,credentials={'X-Subscription-Token':self.token},credential_scope='brave_search')
        if 'json' not in typ: raise ValueError('Search provider expected JSON')
        result=json.loads(body)
        rows=result.get('web',{}).get('results')
        if not isinstance(rows,list) or len(rows)>20: raise ValueError('Invalid search response schema')
        return [{'url':row['url'],'origin_url':url,'description':row.get('description','')}
                for row in rows if isinstance(row,dict) and isinstance(row.get('url'),str)]
