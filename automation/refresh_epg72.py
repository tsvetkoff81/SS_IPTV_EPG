"""Public XMLTV assembler. Contains no playlist, subscriber URLs or credentials."""
import base64, argparse, bisect, collections, concurrent.futures, copy, datetime as dt
import gzip, hashlib, json, os, pathlib, sys, time, unicodedata, urllib.request
from lxml import etree as E
UTC=dt.timezone.utc
def normalized(s):
    return ''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum() or c=='+')
def timestamp(s):
    try:
        s=s.strip()
        if len(s)!=20 or s[14]!=' ': return None
        return dt.datetime.fromisoformat(s[:4]+'-'+s[4:6]+'-'+s[6:8]+'T'+s[8:10]+':'+s[10:12]+':'+s[12:14]+s[15:18]+':'+s[18:20]).astimezone(UTC)
    except (ValueError,AttributeError): return None
def dump(path,obj):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
    os.replace(tmp,path)
def download(item,cache):
    source,url=item; path=cache/(source+'.xml.gz'); tmp=path.with_suffix('.download')
    try:
        if not url.startswith('https://') or '?' in url or '@' in url: raise ValueError()
        start=time.monotonic()
        req=urllib.request.Request(url,headers={'User-Agent':'SS-IPTV-public-EPG/1.0'})
        with urllib.request.urlopen(req,timeout=40) as res,tmp.open('wb') as out:
            if not res.geturl().startswith('https://'): raise ValueError()
            size=0
            while True:
                b=res.read(1024*1024)
                if not b: break
                size+=len(b)
                if size>256*1024*1024 or time.monotonic()-start>300: raise ValueError()
                out.write(b)
        with tmp.open('rb') as f:
            if f.read(2)!=b'\x1f\x8b': raise ValueError()
        os.replace(tmp,path)
        return source,{'status':'downloaded','bytes':size}
    except Exception as ex:
        tmp.unlink(missing_ok=True)
        return source,{'status':'failed','error':type(ex).__name__}
def collect(path,needed,now,end):
    good=set(); result=collections.defaultdict(list); invalid=0; channel_count=0
    # No external entities, network or DTDs. Clear elements to bound memory.
    with (gzip.open(path,'rb') if path.suffix=='.gz' else path.open('rb')) as f:
        for _,e in E.iterparse(f,events=('end',),tag=('channel','programme'),resolve_entities=False,load_dtd=False,no_network=True,huge_tree=True):
            if e.tag=='channel':
                channel_count+=1; cid=e.get('id')
                if cid in needed:
                    names={normalized(n.text or '') for n in e.findall('display-name')}
                    if names.intersection(needed[cid]): good.add(cid)
            else:
                cid=e.get('channel')
                if cid in good:
                    a=timestamp(e.get('start')); b=timestamp(e.get('stop'))
                    if not a or not b or b<=a or not any((n.text or '').strip() for n in e.findall('title')):invalid+=1
                    elif a<end and b>now:
                        p=copy.deepcopy(e); p.tail=None
                        for icon in p.findall('icon'):p.remove(icon)
                        result[cid].append((a,b,p))
            e.clear()
            while e.getprevious() is not None: del e.getparent()[0]
    if not channel_count: raise ValueError('No XMLTV channels')
    return result,invalid
def continuous(programmes,now):
    stop=now
    for a,b,_ in sorted(programmes,key=lambda x:(x[0],x[1])):
        if b<=stop:continue
        if a>stop:break
        stop=b
    return max(0,(stop-now).total_seconds()/3600)
def merge(lists,now):
    # Prefer the verified publisher with the longest unbroken horizon.
    # On equal coverage the configured source order wins.
    ordered=sorted(enumerate(lists),key=lambda x:(continuous(x[1],now),sum((min(b,now+dt.timedelta(hours=72))-max(a,now)).total_seconds() for a,b,_ in x[1]),-x[0]),reverse=True)
    accepted=[]; starts=[]; seen=set(); duplicates=conflicts=0
    for _,programmes in ordered:
        for a,b,p in sorted(programmes,key=lambda x:(x[0],x[1])):
            key=(a,b,tuple((n.get('lang',''),n.text or '') for n in p.findall('title')))
            if key in seen:duplicates+=1;continue
            at=bisect.bisect_left(starts,a)
            if (at>0 and accepted[at-1][1]>a) or (at<len(accepted) and accepted[at][0]<b):
                conflicts+=1;continue
            seen.add(key);starts.insert(at,a);accepted.insert(at,(a,b,p))
    return accepted,duplicates,conflicts
def build(config,cache,out,fallback=None,no_download=False):
    out.mkdir(parents=True,exist_ok=True);cache.mkdir(parents=True,exist_ok=True)
    now=dt.datetime.now(UTC); end=now+dt.timedelta(hours=config.get('window_hours',72))
    states={}
    if not no_download:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            states=dict(pool.map(lambda item:download(item,cache),config['source_urls'].items()))
    needed=collections.defaultdict(dict)
    for c in config['channels']:
        for src,m in c['sources'].items():
            needed[src][m['id']]={normalized(n) for n in m['expected_names']}
    datasets={}; invalid=0
    for src,selected in needed.items():
        path=cache/(src+'.xml.gz')
        if not path.exists() or states.get(src,{}).get('status')=='failed':
            states.setdefault(src,{'status':'missing'});continue
        try:
            datasets[src],n=collect(path,selected,now,end);invalid+=n
            states.setdefault(src,{'status':'cached'})
            states[src]['future_ids']=len(datasets[src])
        except Exception as ex: states[src]={'status':'invalid','error':type(ex).__name__}
    old={};old_needed={c['output_id']:{normalized(n) for n in c['names']}|{normalized(c['output_id'])} for c in config['channels']}
    if fallback and fallback.exists():
        old,_=collect(fallback,old_needed,now,end)
    root=E.Element('tv',{'generator-info-name':'SS IPTV verified public XMLTV 72h'})
    all_programmes=[]; horizons={}; counts={}; duplicate_count=conflict_count=0
    for c in config['channels']:
        oid=c['output_id'];lists=[]
        for src in config['source_priority']:
            m=c['sources'].get(src)
            if m and src in datasets:lists.append(datasets[src].get(m['id'],[]))
        if oid in old:lists.append(old[oid])
        merged,dups,conflicts=merge(lists,now)
        duplicate_count+=dups;conflict_count+=conflicts
        ch=E.SubElement(root,'channel',id=oid)
        for name in dict.fromkeys([oid]+c['names']):E.SubElement(ch,'display-name').text=name
        for a,b,p in merged:
            p=copy.deepcopy(p)
            if not config.get('include_descriptions',True):
                for desc in p.findall('desc'):p.remove(desc)
            p.set('channel',oid);all_programmes.append(p)
        horizons[oid]=min(72,continuous(merged,now))
        counts[oid]=len(merged)
    for p in all_programmes:root.append(p)
    future_count=sum(n>0 for n in counts.values())
    old_count=len(old)
    if future_count<config.get('minimum_future_channels',1) or (old_count and future_count<old_count*0.9):
        raise ValueError('Coverage regression; previous publication retained')
    if not any(s.get('future_ids',0) for n,s in states.items() if n in config['source_urls']):
        raise ValueError('No usable automatic source; previous publication retained')
    data=E.tostring(root,xml_declaration=True,encoding='UTF-8',pretty_print=False)
    check=E.fromstring(data,E.XMLParser(resolve_entities=False,load_dtd=False,no_network=True))
    ids=[c.get('id') for c in check.findall('channel')]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate channel IDs')
    if len(check.findall('programme'))!=len(all_programmes):raise ValueError('Programme count changed')
    if any(p.get('channel') not in counts for p in check.findall('programme')):raise ValueError('Orphan programme')
    report={'generated_utc':now.isoformat(),'window_end_utc':end.isoformat(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'xmltv_channel_ids':len(ids),'future_channel_ids':future_count,'programmes':len(all_programmes),'full_24h_ids':sum(v>=24 for v in horizons.values()),'full_48h_ids':sum(v>=48 for v in horizons.values()),'full_72h_ids':sum(v>=72 for v in horizons.values()),'coverage_hours':horizons,'programme_counts':counts,'duplicates_removed':duplicate_count,'overlap_alternatives_rejected':conflict_count,'invalid_programmes_rejected':invalid,'sources':states}
    # Only replace the last good file after every validation has passed.
    tmp=out/'epg.xml.tmp';tmp.write_bytes(data);os.replace(tmp,out/'epg.xml')
    dump(out/'report.json',report)
    return report
def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--cache',required=True);p.add_argument('--output',required=True);p.add_argument('--fallback');p.add_argument('--no-download',action='store_true');a=p.parse_args()
    try:
        raw=pathlib.Path(a.config).read_bytes()
        if a.config.endswith('.gz.b64'):raw=gzip.decompress(base64.b64decode(raw))
        report=build(json.loads(raw),pathlib.Path(a.cache),pathlib.Path(a.output),pathlib.Path(a.fallback) if a.fallback else None,a.no_download)
        print(json.dumps({k:v for k,v in report.items() if k not in ('coverage_hours','programme_counts')},ensure_ascii=True))
    except Exception as ex:
        # No source bodies, exception messages or request URLs in logs.
        print('EPG update failed ('+type(ex).__name__+'); last good publication retained.',file=sys.stderr);return 1
    return 0
if __name__=='__main__':sys.exit(main())
