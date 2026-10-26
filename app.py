"""Kamu Analiz Merkezi - internet connected, deployable Flask service.
External sources are best-effort and never silently fabricated.
"""
import os,re,json,io,csv,html,sqlite3
from urllib.parse import urlparse,quote_plus
from datetime import datetime
from flask import Flask,request,jsonify,render_template,send_file
import requests
from bs4 import BeautifulSoup

ROOT=os.path.dirname(__file__)
app=Flask(__name__)
app.config['MAX_CONTENT_LENGTH']=200*1024*1024
DATA=json.load(open(os.path.join(ROOT,'data','fiyatlar.json'),encoding='utf-8'))
# SQLite stores user-entered rates between process restarts. On ephemeral hosting,
# download a JSON backup; for durable hosting set DATABASE_PATH to a persistent disk.
DB_PATH=os.environ.get('DATABASE_PATH',os.path.join(ROOT,'rayicler.sqlite3'))
def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute('CREATE TABLE IF NOT EXISTS rates (period TEXT NOT NULL, code TEXT NOT NULL, price REAL NOT NULL, source TEXT NOT NULL, PRIMARY KEY(period,code))')
def read_rates():
    with sqlite3.connect(DB_PATH) as con:
        return {(p,c):{'fiyat':v,'kaynak':src} for p,c,v,src in con.execute('SELECT period,code,price,source FROM rates')}
def save_rate(period,code,price,source):
    with sqlite3.connect(DB_PATH) as con:
        con.execute('INSERT OR REPLACE INTO rates VALUES (?,?,?,?)',(period,code,price,source))
    RATES[(period,code)]={'fiyat':price,'kaynak':source}
init_db()
RATES=read_rates()
UA={'User-Agent':'Mozilla/5.0 (compatible; KamuAnalizArastirma/1.0; public-document-reader)'}
DOMAINS=('birimfiyat.com','www.birimfiyat.com','birimfiyat.net','www.birimfiyat.net','kgm.gov.tr','www.kgm.gov.tr','csb.gov.tr','webdosya.csb.gov.tr','herpoz.com','www.herpoz.com','birimanaliz.com','www.birimanaliz.com')
SEED={'KGM/15.150/K':{'poz':'KGM/15.150/K','tanim':'Figüre (kum, çakıl, kil, kırmataş, tüvenan, stabilize vb. malzeme)','birim':'m³','girdiler':[{'poz':'10.100.1062','eski_poz':'01.501','tanim':'Düz işçi (inşaat işçisi)','birim':'Saat','miktar':0.25}], 'kaynak':'https://www.birimfiyat.com/poz/kgm/yol-k%C3%B6pr%C3%BC/kgm-15.150-k-fig%C3%BCre-%28kum%2C-%C3%A7akil%2C-kirmatas%2C-t%C3%BCvenan-stabilize-vb-malzeme%29','not':'Önceden kaydedilmiş örnek analiz: üçüncü taraf siteden alınmıştır. Canlı kaynaktan tekrar doğrulanamadığında kesin doğrulanmış analiz sayılmaz.'}}

def number(v):
    s=str(v).strip().replace('\u00a0','').replace(' ','').replace('₺','').replace('TL','')
    if ',' in s: s=s.replace('.','').replace(',','.')
    elif s.count('.')>1:s=s.replace('.','')
    return float(s)

def allowed(url):
    u=urlparse(url)
    return u.scheme=='https' and u.hostname in DOMAINS and not u.username and not u.password

def fetch(url):
    if not allowed(url):raise ValueError('Bu kaynak alan adına erişim izni verilmedi.')
    r=requests.get(url,headers=UA,timeout=12,allow_redirects=False)
    if r.status_code in (301,302,303,307,308):
        dest=requests.compat.urljoin(url,r.headers.get('Location',''))
        if not allowed(dest):raise ValueError('Yönlendirme güvenli kaynak listesi dışında.')
        r=requests.get(dest,headers=UA,timeout=12,allow_redirects=False)
    r.raise_for_status()
    if len(r.content)>8*1024*1024:raise ValueError('Kaynak boyutu çok büyük.')
    return r

def search_web(poz):
    # Best effort public search, no bypass of login or paywalls.
    q=quote_plus('"'+poz+'" analiz miktar')
    urls=[]
    for base in ('https://www.bing.com/search?q=','https://www.google.com/search?q='):
        try:
            r=requests.get(base+q,headers=UA,timeout=9)
            soup=BeautifulSoup(r.text,'html.parser')
            for a in soup.select('a[href]'):
                href=a.get('href','')
                if href.startswith('/url?q='):href=href.split('/url?q=',1)[1].split('&',1)[0]
                if allowed(href) and href not in urls:urls.append(href)
            if urls:break
        except requests.RequestException:continue
    return urls[:10]

def parse_analysis(html_text,poz,url):
    soup=BeautifulSoup(html_text,'html.parser')
    tables=soup.find_all('table')
    for table in tables:
        heads=' '.join(table.stripped_strings).lower()[:1000]
        if not ('miktar' in heads and ('rayiç' in heads or 'poz' in heads)):continue
        rows=table.find_all('tr')
        header=[];found=[]
        for tr in rows:
            cols=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'],recursive=False)]
            if not cols:continue
            if not header and any('miktar' in c.lower() for c in cols):
                header=[c.lower().replace('ı','i').replace('ç','c') for c in cols];continue
            if not header:continue
            def idx(*terms):
                return next((i for i,h in enumerate(header) if any(t in h for t in terms)),None)
            pi=idx('rayic no','poz no','rayic','poz'); mi=idx('miktar');ti=idx('tanim','aciklama');bi=idx('birim');ei=idx('onceki')
            if mi is None or pi is None or max(pi,mi)>=len(cols):continue
            code=cols[pi].strip(); raw=cols[mi].strip()
            if not re.match(r'^(?:\d{2}\.\d{2,4}\.\d{2,4}|\d{2}\.\d{3}(?:/\w+)?|KGM[/\w.\-]+)$',code,re.I):continue
            try:qty=number(raw)
            except (ValueError,TypeError):continue
            if qty<=0:continue
            found.append({'poz':code,'eski_poz':cols[ei] if ei is not None and ei<len(cols) else '', 'tanim':cols[ti] if ti is not None and ti<len(cols) else '', 'birim':cols[bi] if bi is not None and bi<len(cols) else '', 'miktar':qty})
        if found:
            return {'poz':poz,'tanim':soup.title.get_text(' ',strip=True)[:180] if soup.title else poz,'birim':'','girdiler':found,'kaynak':url,'not':'Web tablosundan otomatik ayrıştırıldı; miktarları kaynakla karşılaştırın.', 'kaynak_durumu':'canlı web tablosundan okundu'}
    return None

def analyze_record(rec,period,margin):
    output=[];subtotal=0;missing=[]
    for item in rec['girdiler']:
        code=item['poz'].upper(); key=(period,code)
        rate=RATES.get(key)
        if rate is None and item.get('eski_poz'):rate=RATES.get((period,item['eski_poz'].upper()))
        amount=round(item['miktar']*rate['fiyat'],4) if rate else None
        if amount is None:missing.append(code)
        else:subtotal+=amount
        output.append({**item,'rayic':rate['fiyat'] if rate else None,'tutar':amount,'rayic_kaynak':rate['kaynak'] if rate else None})
    complete=not missing
    return {'analiz':rec,'girdiler':output,'donem':period,'eksikler':missing,'tam':complete,'karsiz':round(subtotal,2) if complete else None,'karli':round(subtotal*(1+margin/100),2) if complete else None,'kar_orani':margin}

@app.get('/')
def home():return render_template('index.html')

@app.get('/api/health')
def health():return jsonify(ok=True,version='1.0',kayit=len(DATA),rayic=len(RATES))

@app.get('/api/prices')
def prices():
    q=request.args.get('q','').casefold().strip(); agency=request.args.get('kurum','');period=request.args.get('donem',''); limit=min(int(request.args.get('limit','100')),500)
    rows=[r for r in DATA if (not agency or r['kurum']==agency) and (not period or r['donem']==period) and (not q or q in (r['poz']+' '+r['tanim']).casefold())]
    return jsonify(total=len(rows),rows=rows[:limit])

@app.get('/api/rates')
def rates():
    period=request.args.get('donem','2026-10')
    return jsonify(rows=[{'donem':p,'poz':code,**v} for (p,code),v in RATES.items() if p==period])

@app.post('/api/rates')
def add_rate():
    x=request.get_json(force=True); period=x.get('donem','2026-10');code=str(x.get('poz','')).strip().upper()
    if not re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])',period) or not code:return jsonify(error='Dönem veya poz geçersiz.'),400
    try:v=number(x['fiyat']);assert v>=0
    except (ValueError,KeyError,AssertionError):return jsonify(error='Rayiç fiyatı geçersiz.'),400
    save_rate(period,code,v,'Kullanıcı tarafından girildi')
    return jsonify(ok=True)

@app.post('/api/rates/upload')
def upload_rates():
    f=request.files.get('file');period=request.form.get('donem','2026-10')
    if not f or not re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])',period):return jsonify(error='Dosya veya dönem hatalı.'),400
    raw=f.read(); name=f.filename.lower();added=[];warnings=[]
    if name.endswith('.csv'):
        content=raw.decode('utf-8-sig',errors='replace'); dialect=csv.Sniffer().sniff(content[:1024],delimiters=';,\t')
        for row in csv.DictReader(io.StringIO(content),dialect=dialect):
            row={k.strip().lower():v for k,v in row.items() if k}
            code=(row.get('poz') or row.get('poz no') or row.get('rayiç no') or '').strip().upper()
            price=row.get('fiyat') or row.get('rayiç') or row.get('birim fiyat')
            try:
                if code and price:added.append((code,number(price)))
            except ValueError: warnings.append('Geçersiz sayı: '+code)
    elif name.endswith('.pdf'):
        import fitz
        doc=fitz.open(stream=raw,filetype='pdf')
        # PDF tables vary. Extract only conservative one-line code / price matches.
        pat=re.compile(r'(?<![\w/])(10\.\d{3}\.\d{4}|\d{2}\.\d{3}(?:/[A-Za-z0-9-]+)?|04\.\d{3}(?:[/\-][A-Za-z0-9]+)?)(?![\w/])')
        money=re.compile(r'(?<!\d)(\d{1,3}(?:[ .]\d{3})*,\d{2})(?!\d)')
        for page in doc:
            for line in page.get_text('text').splitlines():
                m=pat.search(line); prices=money.findall(line)
                if m and prices:
                    try:added.append((m.group(1),number(prices[-1])))
                    except ValueError:pass
        warnings.append('PDF satır ayrıştırması otomatik yapıldı. Çok satırlı tablolar eksik kalabilir; aktarılan rayiçleri doğrulayın.')
    else:return jsonify(error='Yalnızca PDF veya CSV kabul edilir.'),400
    for code,price in added:save_rate(period,code.upper(),price,f.filename+' (yüklenen dosya; doğrulama gerekli)')
    return jsonify(ok=True,adet=len(added),uyarilar=warnings,ornek=[{'poz':c,'fiyat':v} for c,v in added[:8]])

@app.post('/api/analyze')
def analyze():
    x=request.get_json(force=True);poz=str(x.get('poz','')).strip().upper();period=x.get('donem','2026-10')
    if not poz or len(poz)>100:return jsonify(error='Poz numarası girin.'),400
    try:margin=float(x.get('kar',25));assert 0<=margin<=100
    except (ValueError,AssertionError):return jsonify(error='Kâr oranı geçersiz.'),400
    rec=None;attempts=[]
    url=x.get('url','').strip()
    if url:
        if not allowed(url):return jsonify(error='Yalnızca izin verilen kaynak sitelerinin HTTPS bağlantıları kullanılabilir.'),400
        attempts=[url]
    else:
        attempts=search_web(poz)
        if poz in SEED:attempts.insert(0,SEED[poz]['kaynak'])
    for link in dict.fromkeys(attempts[:8]):
        try:
            response=fetch(link)
            if 'pdf' in response.headers.get('Content-Type','').lower():continue
            rec=parse_analysis(response.text,poz,link)
            if rec:break
        except (requests.RequestException,ValueError):continue
    if not rec and not url and poz in SEED:
        rec={**SEED[poz], 'kaynak_durumu':'önceden kaydedilmiş; canlı erişim doğrulanamadı'}
    if not rec:return jsonify(error='Erişilebilir ve sayısal miktar içeren analiz bulunamadı. Kaynak bağlantısını yapıştırabilir veya farklı poz deneyebilirsiniz.',aranan=attempts[:8]),404
    return jsonify(**analyze_record(rec,period,margin),aranan=attempts[:8],kaynak_durumu=rec.get('kaynak_durumu','canlı web tablosundan okundu'))

@app.get('/api/export')
def export_rates():
    rows=[{'donem':p,'poz':c,**v} for (p,c),v in RATES.items()]
    return jsonify(rows=rows,created=datetime.utcnow().isoformat()+'Z')

@app.post('/api/import')
def import_rates():
    x=request.get_json(force=True);n=0
    for r in x.get('rows',[]):
        try:
            p=r['donem'];c=r['poz'].upper();v=number(r['fiyat'])
            if re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])',p):save_rate(p,c,v,r.get('kaynak','JSON içe aktarma'));n+=1
        except (KeyError,TypeError,ValueError):continue
    return jsonify(ok=True,adet=n)

if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))
