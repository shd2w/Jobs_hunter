"""Canonical rows for additional documented APIs; no eligibility inference."""
from datetime import datetime, timezone
from .sources import plain, POLICIES

def normalize_new(source, data):
    if not isinstance(data,dict): raise ValueError('Invalid source payload')
    entries=data.get('jobs') if source.kind=='jobicy' else data.get('data') if source.kind=='arbeitnow' else (data.get('SearchResult') or {}).get('SearchResultItems')
    if not isinstance(entries,list) or len(entries)>10000: raise ValueError('Invalid source rows')
    rows=[]
    for x in entries:
        try:
            if not isinstance(x,dict): raise ValueError('Invalid row')
            if source.kind=='jobicy':
                row={'title':x.get('jobTitle'),'company':x.get('companyName'),'url':x.get('url'),'location':x.get('jobGeo',''),'description':plain(x.get('jobDescription','')),'external_job_id':str(x.get('id','')),'date_posted':x.get('pubDate',''),'employment_type':', '.join(x.get('jobType') or []),'salary_min':x.get('salaryMin'),'salary_max':x.get('salaryMax'),'salary_currency':x.get('salaryCurrency',''),'salary_period':x.get('salaryPeriod',''),'attribution':'Jobicy'}
            elif source.kind=='arbeitnow':
                created=x.get('created_at');posted=datetime.fromtimestamp(created,timezone.utc).isoformat() if type(created) in (int,float) else ''
                row={'title':x.get('title'),'company':x.get('company_name'),'url':x.get('url'),'location':x.get('location',''),'description':plain(x.get('description','')),'external_job_id':x.get('slug',''),'date_posted':posted,'remote':x.get('remote'),'employment_type':', '.join(x.get('job_types') or []),'attribution':'Arbeitnow'}
            else:
                d=x.get('MatchedObjectDescriptor') or {};details=(d.get('UserArea') or {}).get('Details') or {}
                row={'title':d.get('PositionTitle'),'company':d.get('OrganizationName'),'url':d.get('PositionURI'),'location':d.get('PositionLocationDisplay',''),'external_job_id':d.get('PositionID',''),'date_posted':d.get('PublicationStartDate',''),'deadline':d.get('ApplicationCloseDate',''),'description':'\n'.join(str(details.get(k,'')) for k in ('JobSummary','MajorDuties','Requirements','Education','WhoMayApply','KeyRequirements')),'attribution':'USAJOBS'}
            if source.kind=='jobicy':
                row['salary']=' '.join(str(x[k]) for k in ('salaryMin','salaryMax','salaryCurrency','salaryPeriod') if x.get(k) is not None)
            elif source.kind=='arbeitnow' and type(x.get('remote')) is bool:
                row['description']+='\nSource remote flag: '+str(x['remote'])+'; geographic eligibility requires review.'
            elif source.kind=='usajobs':
                row['description']+='\nAnnouncement closes (as supplied): '+str(row.get('deadline',''))+'\nPublic search result; citizenship and hiring-path eligibility require review.'
            row['source_notice']=POLICIES[source.kind]['notice'];rows.append(row)
        except (ValueError,TypeError,AttributeError,OverflowError,OSError): rows.append({})
    return rows
