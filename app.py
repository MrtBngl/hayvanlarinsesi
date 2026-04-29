import os
import requests
import random
from flask import Flask, render_template, request
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

print(f"✓ Currents API: {'VAR' if CURRENTS_API_KEY else 'YOK'}")
print(f"✓ GNews API: {'VAR' if GNEWS_API_KEY else 'YOK'}")

CURRENTS_URL = "https://api.currentsapi.services/v1/search"
GNEWS_URL = "https://gnews.io/api/v4/search"

news_pool = {
    'articles': [],
    'last_shown': [],
    'timestamp': None,
    'timeout': 21600
}

# === SADECE BARİZ ALAKASIZLARI ENGELLE ===
BLOCKED_KEYWORDS = [
    # Burç/Astroloji (kesin red)
    'burç', 'burcu', 'burçlar', 'astroloji', 'yıldız falı', 'günlük burç', 
    'haftalık burç', 'koç burcu', 'boğa burcu', 'ikizler burcu',
    'yengeç burcu', 'aslan burcu', 'başak burcu', 'terazi burcu', 'akrep burcu',
    'yay burcu', 'oğlak burcu', 'kova burcu', 'balık burcu',
    
    # Spor maçları (kesin red)
    'maç sonucu', 'maç özeti', 'gol', 'asist', 'sarı kart', 'kırmızı kart',
    'penaltı', 'ofsayt', 'şampiyonlar ligi', 'uefa', 'fifa',
    'transfer haberi', 'teknik direktör', 'futbolcu', 'basketbol', 'voleybol', 'tenis', 'spor haber',
    'super lig', 'nba', 'nfl', 'mlb', 'nhl','galatasaray', 'fenerbahçe', 'beşiktaş', 'trabzonspor', 'başakşehir',
    
    # Siyaset (kesin red)
    'erdoğan', 'kılıçdaroğlu', 'bahçeli', 'akşener', 'seçim sonucu',
    'oy oranı', 'milletvekili adayı', 'parti kongre', 'hükümet kararı',
    'bakan açıklaması', 'tbmm', 'meclis oturumu','savaş', 'diplomasi', 'nato', 'ab', 'avrupa birliği', 'amerika', 'rusya', 'çin',
    'suriye', 'ırak', 'afganistan', 'iran', 'israil', 'filistin',
    
    # Yemek tarifleri (kesin red)
    'kebap tarifi', 'döner tarifi', 'köfte nasıl yapılır', 'et yemeği',
    'hayvan eti', 'kasaplık',
    # din (kesin red)
    'cami', 'kilise', 'sinagog', 'tapınak', 'imam', 'papaz', 'rahip', 'din adamı', 'dini lider', 'dini tören',
    'vahiy', 'kutsal kitap', 'dua', 'ibadet', 'orasyon', 'hacı', 'hac', 'umre', 'müslüman', 'hristiyan', 'yahudi',
    # Oyun (kesin red)
    'minecraft', 'fortnite', 'pubg', 'oyun karakteri',
    
    # İnsan şiddeti (kesin red)
    'adam öldürme', 'kadın cinayeti', 'çocuk istismarı',
]

# === POZİTİF PUANLAMA ===
POSITIVE_SCORES = {
    # Güçlü bağlam (10 puan)
    'hayvan barınağı': 10, 'hayvan koruma': 10, 'hayvan hakları': 10,
    'hayvan istismarı': 10, 'sokak hayvanı': 10, 'sahipsiz hayvan': 10,
    'hayvan kurtarma': 10, 'veteriner klinik': 10, 'doğa koruma': 10,
    'nesli tükenen': 10, 'yaban hayatı': 10,
    
    # Orta bağlam (5 puan)
    'barınak': 5, 'veteriner': 5, 'rehabilitasyon': 5, 'sahiplenme': 5,
    'yaban': 5, 'sokak': 5, 'sahipsiz': 5, 'yaralı': 5,
    
    # Temel kelimeler (3 puan)
    'köpek': 3, 'kedi': 3, 'kuş': 3, 'at': 3, 'balık': 3,
    'tavşan': 3, 'kaplumbağa': 3, 'papağan': 3, 'kartal': 3,
    'leylek': 3, 'tilki': 3, 'ayı': 3, 'kurt': 3,
    'yunus': 3, 'balina': 3, 'fok': 3, 'penguen': 3,
    
    # Yardımcı (2 puan)
    'mama': 2, 'aşı': 2, 'tedavi': 2, 'bakım': 2, 'yuva': 2,
}

def calculate_score(title, description):
    """Habere puan ver"""
    text = (title + " " + description).lower()
    title_lower = title.lower()
    
    # 1. Kesin red kontrolü
    for blocked in BLOCKED_KEYWORDS:
        if blocked in text:
            return -1
    
    score = 0
    
    # 2. Pozitif puanlama
    for keyword, points in POSITIVE_SCORES.items():
        if keyword in text:
            score += points
        if keyword in title_lower:  # Başlıkta 2x
            score += points
    
    # 3. Çoklu hayvan bonusu
    animals = ['köpek', 'kedi', 'kuş', 'at', 'balık', 'tavşan']
    found = [a for a in animals if a in text]
    if len(found) >= 2:
        score += 5
    
    # 4. Başlık hayvanla başlıyorsa
    if title_lower.split() and title_lower.split()[0] in animals:
        score += 3
    
    return score

def get_category(text):
    text = text.lower()
    cats = {
        'Hukuk & Mevzuat': ['5199', 'kanun', 'yasa', 'meclis', 'hukuk', 'mahkeme'],
        'Hayvan Hakları': ['şiddet', 'istismar', 'işkence', 'hakları', 'dövme'],
        'Sağlık & Bilim': ['veteriner', 'sağlık', 'hastalık', 'ameliyat', 'tedavi'],
        'Kurtarma & Barınak': ['barınak', 'kurtar', 'sahiplen', 'sokak hayvanı'],
        'Yaban Hayatı': ['yaban', 'vahşi', 'nesli tükenen', 'doğa koruma'],
        'Deniz Yaşamı': ['deniz', 'balık', 'balina', 'yunus', 'fok'],
        'Kuş Dünyası': ['kuş', 'leylek', 'kartal', 'papağan', 'şahin'],
    }
    scores = {cat: sum(2 for w in words if w in text) for cat, words in cats.items()}
    return max(scores, key=scores.get) if scores else 'Evcil Hayvan'

def process_article(art, source_type):
    """Haberi işle"""
    if source_type == 'currents':
        title = str(art.get('title', ''))
        desc = str(art.get('description', ''))
        url = art.get('url', '#')
        img = art.get('image')
        source = str(art.get('author', 'Haber'))[:20]
        date_str = art.get('published', '').split(' ')[0]
    else:
        title = str(art.get('title', ''))
        desc = str(art.get('description', ''))
        url = art.get('url', '#')
        img = art.get('image')
        src_obj = art.get('source', {})
        source = str(src_obj.get('name', 'Haber') if isinstance(src_obj, dict) else 'Haber')[:20]
        date_str = art.get('publishedAt', '')[:10]
    
    # Puan hesapla
    score = calculate_score(title, desc)
    if score < 0:
        return None
    
    # Tarih
    try:
        formatted_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d %b %Y')
    except:
        formatted_date = "Güncel"
    
    # Resim
    if not img or img == 'None':
        img = 'https://images.unsplash.com/photo-1541781774459-bb2af2f05b55?w=800'
    
    text = (title + " " + desc).lower()
    
    return {
        'title': title,
        'description': desc[:160] + '...' if len(desc) > 160 else desc,
        'image_url': img,
        'link': url,
        'source': source,
        'date': formatted_date,
        'category': get_category(text),
        'read_time': '3 dk okuma',
        'score': score
    }

def fetch_currents():
    if not CURRENTS_API_KEY:
        return []
    
    try:
        params = {
            'apiKey': CURRENTS_API_KEY,
            'keywords': "hayvan OR köpek OR kedi OR barınak OR veteriner OR yaban",
            'language': 'tr',
            'page_size': 50
        }
        
        print(f"\n🌐 CURRENTS API...")
        response = requests.get(CURRENTS_URL, params=params, timeout=15)
        print(f"   Status: {response.status_code}")
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        raw_news = data.get('news', [])
        print(f"   Ham: {len(raw_news)}")
        
        result = []
        rejected = 0
        
        for art in raw_news:
            processed = process_article(art, 'currents')
            if processed:
                result.append(processed)
            else:
                rejected += 1
        
        print(f"   ✅ {len(result)} kabul | ⛔ {rejected} red")
        return result
        
    except Exception as e:
        print(f"   ❌ Hata: {e}")
        return []

def fetch_gnews():
    if not GNEWS_API_KEY:
        print("❌ GNews Key yok!")
        return []
    
    try:
        params = {
            'apikey': GNEWS_API_KEY,
            'q': 'hayvan OR köpek OR kedi OR barınak OR veteriner OR yaban',
            'lang': 'tr',
            'country': 'tr',
            'max': 100
        }
        
        print(f"\n🌐 GNEWS API...")
        response = requests.get(GNEWS_URL, params=params, timeout=15)
        print(f"   Status: {response.status_code}")
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        raw_news = data.get('articles', [])
        print(f"   Ham: {len(raw_news)}")
        
        result = []
        rejected = 0
        
        for art in raw_news:
            if not isinstance(art, dict):
                continue
            processed = process_article(art, 'gnews')
            if processed:
                result.append(processed)
            else:
                rejected += 1
        
        print(f"   ✅ {len(result)} kabul | ⛔ {rejected} red")
        return result
        
    except Exception as e:
        print(f"   ❌ Hata: {e}")
        return []

def fetch_all_news():
    print("\n" + "="*50)
    print("🚀 HABER ÇEKME BAŞLADI")
    print("="*50)
    
    currents = fetch_currents()
    gnews = fetch_gnews()
    
    all_news = currents + gnews
    
    print(f"\n📊 TOPLAM: {len(all_news)} haber")
    
    # Tekrarları kaldır
    seen = set()
    unique = []
    for a in all_news:
        title = a['title'].strip().lower()
        if title and title not in seen:
            seen.add(title)
            unique.append(a)
    
    # Puana göre sırala (yüksekten düşüğe)
    unique.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"✨ Tekrarsız: {len(unique)}")
    if unique:
        scores = [a['score'] for a in unique]
        avg = sum(scores) / len(scores)
        print(f"📈 Ortalama puan: {avg:.1f}")
    print("="*50 + "\n")
    
    return unique

@app.route('/haberler')
def haberler():
    force_refresh = request.args.get('refresh') == '1'
    now = datetime.now()

    if force_refresh or not news_pool['articles'] or not news_pool['timestamp'] or (now - news_pool['timestamp']).seconds > news_pool['timeout']:
        news_pool['articles'] = fetch_all_news()
        news_pool['timestamp'] = now
        news_pool['last_shown'] = []

    available = [a for a in news_pool['articles'] if a['title'] not in news_pool['last_shown']]
    
    if len(available) < 16:
        news_pool['last_shown'] = []
        available = news_pool['articles']

    count = min(len(available), 16)
    
    if count > 0:
        selected = available[:count]  # Puana göre sıralı
        news_pool['last_shown'].extend([n['title'] for n in selected])
    else:
        selected = []

    return render_template('blog.html', news=selected, total=len(news_pool['articles']))

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/iletisim')
def iletisim():
    return render_template('iletisim.html')

@app.route('/gizlilik-politikasi')
def gizlilik():
    return render_template('gizlilik-politikasi.html')

@app.route('/kullanim-sartlari')
def kullanim():
    return render_template('kullanim-sartlari.html')

@app.route('/kvkk')
def kvkk():
    return render_template('kvkk-aydinlatma-metni.html')

@app.route('/ihbar-rehberi')
def ihbar():
    return render_template('hayvan-istismari-ihbar-rehberi.html')

@app.route('/5199-kanun')
def kanun():
    return render_template('hayvan-haklari/5199-hayvanlari-koruma-kanunu.html')

@app.route('/mevzuat-rehberi')
def mevzuat():
    return render_template('hayvan-haklari/hayvan-haklari-mevzuati.html')

@app.route('/sss')
def sss():
    return render_template('hayvan-haklari/hayvan-haklari-sikca-sorulan-sorular.html')

@app.route('/')
def home():
    from datetime import datetime
    now = datetime.now()

    # Haber havuzu doluysa tekrar çekme, boşsa çek
    if not news_pool['articles'] or not news_pool['timestamp'] or \
            (now - news_pool['timestamp']).seconds > news_pool['timeout']:
        news_pool['articles'] = fetch_all_news()
        news_pool['timestamp'] = now
        news_pool['last_shown'] = []

    featured = news_pool['articles'][:3]  # En yüksek puanlı 3 haber
    return render_template('index.html', featured_news=featured)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5500)