from flask import Flask, render_template_string, jsonify, request
from werkzeug.utils import secure_filename
import pandas as pd
import os
import time
from threading import Thread
import webbrowser
import subprocess
import shutil

app = Flask(__name__)

# Script çalışma durumu
script_running = False
script_process = None

# Dosya yükleme ayarları
UPLOAD_FOLDER = '.'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Dosya yolları
CIKIS_DOSYASI = "temizlenmis_katalog.xlsx"
GIRIS_DOSYASI = "GüneşProducts_20251222_203037.xlsx"  # Varsayılan, yükleme ile değişebilir

def get_progress():
    """İlerlemeyi hesapla"""
    try:
        # Toplam ürün sayısı
        df_input = pd.read_excel(GIRIS_DOSYASI)
        # İlk satır teknik kodlar olabilir
        if len(df_input) > 0 and df_input.iloc[0].get('Başlık', '').startswith('TITLE'):
            total = len(df_input) - 1
        else:
            total = len(df_input)
        
        # İşlenen ürün sayısı
        if os.path.exists(CIKIS_DOSYASI):
            df_output = pd.read_excel(CIKIS_DOSYASI)
            processed = len(df_output)
        else:
            processed = 0
        
        # Son güncelleme zamanı
        if os.path.exists(CIKIS_DOSYASI):
            last_update = time.ctime(os.path.getmtime(CIKIS_DOSYASI))
        else:
            last_update = "Henüz dosya oluşturulmadı"
        
        # Son işlenen ürünler
        if processed > 0:
            last_products = df_output.tail(5)[['Orijinal_Baslik', 'Temiz_Baslik']].to_dict('records')
        else:
            last_products = []
        
        return {
            'total': total,
            'processed': processed,
            'remaining': total - processed,
            'percentage': round((processed / total * 100) if total > 0 else 0, 1),
            'last_update': last_update,
            'last_products': last_products,
            'is_complete': processed >= total
        }
    except Exception as e:
        return {
            'error': str(e),
            'total': 0,
            'processed': 0,
            'remaining': 0,
            'percentage': 0,
            'last_update': 'Hata',
            'last_products': [],
            'is_complete': False
        }

@app.route('/')
def index():
    progress = get_progress()
    
    html_template = """
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Ürün İşleme Dashboard</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                padding: 40px;
            }
            h1 {
                color: #333;
                margin-bottom: 30px;
                text-align: center;
                font-size: 2.5em;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }
            .stat-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
            }
            .stat-card h3 {
                font-size: 0.9em;
                opacity: 0.9;
                margin-bottom: 10px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .stat-card .value {
                font-size: 3em;
                font-weight: bold;
                margin-bottom: 5px;
            }
            .stat-card.complete {
                background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            }
            .progress-container {
                margin: 40px 0;
            }
            .progress-bar {
                width: 100%;
                height: 40px;
                background: #e0e0e0;
                border-radius: 20px;
                overflow: hidden;
                box-shadow: inset 0 2px 5px rgba(0,0,0,0.1);
            }
            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                transition: width 0.5s ease;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
                font-size: 1.1em;
            }
            .progress-fill.complete {
                background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%);
            }
            .last-update {
                text-align: center;
                color: #666;
                margin-top: 20px;
                font-size: 0.9em;
            }
            .products-section {
                margin-top: 40px;
            }
            .products-section h2 {
                color: #333;
                margin-bottom: 20px;
                font-size: 1.8em;
            }
            .product-item {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 15px;
                border-left: 4px solid #667eea;
            }
            .product-item .original {
                color: #666;
                font-size: 0.9em;
                margin-bottom: 8px;
                text-decoration: line-through;
            }
            .product-item .clean {
                color: #333;
                font-weight: bold;
                font-size: 1.1em;
            }
            .refresh-btn {
                position: fixed;
                bottom: 30px;
                right: 30px;
                background: #667eea;
                color: white;
                border: none;
                padding: 15px 30px;
                border-radius: 50px;
                font-size: 1em;
                cursor: pointer;
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
                transition: transform 0.2s;
            }
            .refresh-btn:hover {
                transform: scale(1.05);
            }
            .auto-refresh {
                text-align: center;
                color: #666;
                margin-top: 20px;
                font-size: 0.85em;
            }
            .control-panel {
                text-align: center;
                margin: 30px 0;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 15px;
            }
            .start-btn {
                background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                color: white;
                border: none;
                padding: 15px 40px;
                border-radius: 50px;
                font-size: 1.2em;
                font-weight: bold;
                cursor: pointer;
                box-shadow: 0 5px 20px rgba(17, 153, 142, 0.4);
                transition: transform 0.2s;
                margin: 0 10px;
            }
            .start-btn:hover {
                transform: scale(1.05);
            }
            .start-btn:disabled {
                background: #ccc;
                cursor: not-allowed;
                transform: none;
            }
            .stop-btn {
                background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
                color: white;
                border: none;
                padding: 15px 40px;
                border-radius: 50px;
                font-size: 1.2em;
                font-weight: bold;
                cursor: pointer;
                box-shadow: 0 5px 20px rgba(235, 51, 73, 0.4);
                transition: transform 0.2s;
                margin: 0 10px;
            }
            .stop-btn:hover {
                transform: scale(1.05);
            }
            .status-message {
                margin-top: 15px;
                padding: 10px;
                border-radius: 10px;
                font-weight: bold;
            }
            .status-message.success {
                background: #d4edda;
                color: #155724;
            }
            .status-message.error {
                background: #f8d7da;
                color: #721c24;
            }
            .upload-section {
                background: #f8f9fa;
                padding: 25px;
                border-radius: 15px;
                margin: 30px 0;
                text-align: center;
            }
            .upload-section h3 {
                color: #333;
                margin-bottom: 15px;
            }
            .file-input-wrapper {
                position: relative;
                display: inline-block;
                margin: 15px 0;
            }
            .file-input-wrapper input[type=file] {
                position: absolute;
                left: -9999px;
            }
            .file-input-label {
                display: inline-block;
                padding: 12px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-radius: 50px;
                cursor: pointer;
                font-weight: bold;
                transition: transform 0.2s;
            }
            .file-input-label:hover {
                transform: scale(1.05);
            }
            .file-name {
                margin-top: 10px;
                color: #666;
                font-size: 0.9em;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Ürün İşleme Dashboard</h1>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Toplam Ürün</h3>
                    <div class="value">{{ progress.total }}</div>
                </div>
                <div class="stat-card">
                    <h3>İşlenen</h3>
                    <div class="value">{{ progress.processed }}</div>
                </div>
                <div class="stat-card">
                    <h3>Kalan</h3>
                    <div class="value">{{ progress.remaining }}</div>
                </div>
                <div class="stat-card {% if progress.is_complete %}complete{% endif %}">
                    <h3>İlerleme</h3>
                    <div class="value">{{ progress.percentage }}%</div>
                </div>
            </div>
            
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill {% if progress.is_complete %}complete{% endif %}" 
                         style="width: {{ progress.percentage }}%">
                        {% if progress.percentage > 10 %}{{ progress.percentage }}%{% endif %}
                    </div>
                </div>
            </div>
            
            <div class="last-update">
                📅 Son Güncelleme: {{ progress.last_update }}
            </div>
            
            <div class="upload-section">
                <h3>📁 Excel Dosyası Yükle</h3>
                <form id="uploadForm" enctype="multipart/form-data">
                    <div class="file-input-wrapper">
                        <input type="file" id="fileInput" name="file" accept=".xlsx,.xls" onchange="handleFileSelect(this)">
                        <label for="fileInput" class="file-input-label">📎 Dosya Seç</label>
                    </div>
                    <div id="fileName" class="file-name"></div>
                    <button type="button" class="start-btn" onclick="uploadFile()" style="margin-top: 15px;">
                        ⬆️ Yükle
                    </button>
                </form>
                <div id="uploadMessage"></div>
            </div>
            
            <div class="control-panel">
                <h2 style="margin-bottom: 20px; color: #333;">🎮 Kontrol Paneli</h2>
                <button id="startBtn" class="start-btn" onclick="startScript()">
                    ▶️ Başlat
                </button>
                <button id="stopBtn" class="stop-btn" onclick="stopScript()" style="display: none;">
                    ⏹️ Durdur
                </button>
                <div id="statusMessage"></div>
            </div>
            
            {% if progress.last_products %}
            <div class="products-section">
                <h2>📋 Son İşlenen Ürünler</h2>
                {% for product in progress.last_products %}
                <div class="product-item">
                    <div class="original">{{ product.Orijinal_Baslik[:100] }}...</div>
                    <div class="clean">{{ product.Temiz_Baslik }}</div>
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            <div class="auto-refresh">
                ⏱️ Otomatik yenileme: Her 3 saniyede bir güncellenir
            </div>
        </div>
        
        <button class="refresh-btn" onclick="location.reload()">🔄 Yenile</button>
        
        <script>
            let scriptRunning = false;
            
            // Script durumunu kontrol et
            function checkScriptStatus() {
                fetch('/api/progress')
                    .then(response => response.json())
                    .then(data => {
                        scriptRunning = data.script_running || false;
                        updateButtons();
                    });
            }
            
            function updateButtons() {
                const startBtn = document.getElementById('startBtn');
                const stopBtn = document.getElementById('stopBtn');
                
                if (scriptRunning) {
                    startBtn.style.display = 'none';
                    stopBtn.style.display = 'inline-block';
                } else {
                    startBtn.style.display = 'inline-block';
                    stopBtn.style.display = 'none';
                }
            }
            
            function startScript() {
                const startBtn = document.getElementById('startBtn');
                const statusMsg = document.getElementById('statusMessage');
                
                startBtn.disabled = true;
                statusMsg.innerHTML = '<div class="status-message">⏳ Başlatılıyor...</div>';
                
                fetch('/api/start', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            statusMsg.innerHTML = '<div class="status-message success">✅ ' + data.message + '</div>';
                            scriptRunning = true;
                            updateButtons();
                        } else {
                            statusMsg.innerHTML = '<div class="status-message error">❌ ' + data.message + '</div>';
                        }
                        startBtn.disabled = false;
                    })
                    .catch(error => {
                        statusMsg.innerHTML = '<div class="status-message error">❌ Hata: ' + error + '</div>';
                        startBtn.disabled = false;
                    });
            }
            
            function stopScript() {
                const stopBtn = document.getElementById('stopBtn');
                const statusMsg = document.getElementById('statusMessage');
                
                stopBtn.disabled = true;
                statusMsg.innerHTML = '<div class="status-message">⏳ Durduruluyor...</div>';
                
                fetch('/api/stop', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            statusMsg.innerHTML = '<div class="status-message success">✅ ' + data.message + '</div>';
                            scriptRunning = false;
                            updateButtons();
                        } else {
                            statusMsg.innerHTML = '<div class="status-message error">❌ ' + data.message + '</div>';
                        }
                        stopBtn.disabled = false;
                    })
                    .catch(error => {
                        statusMsg.innerHTML = '<div class="status-message error">❌ Hata: ' + error + '</div>';
                        stopBtn.disabled = false;
                    });
            }
            
            // İlk durum kontrolü
            checkScriptStatus();
            updateButtons();
            
            // Otomatik yenileme
            setInterval(function() {
                location.reload();
            }, 3000);
            
            // Script durumunu her 2 saniyede kontrol et
            setInterval(checkScriptStatus, 2000);
            
            // Dosya seçimi
            function handleFileSelect(input) {
                const fileName = input.files[0] ? input.files[0].name : '';
                document.getElementById('fileName').textContent = fileName || '';
            }
            
            // Dosya yükleme
            function uploadFile() {
                const fileInput = document.getElementById('fileInput');
                const uploadMsg = document.getElementById('uploadMessage');
                
                if (!fileInput.files[0]) {
                    uploadMsg.innerHTML = '<div class="status-message error">❌ Lütfen bir dosya seçin!</div>';
                    return;
                }
                
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                
                uploadMsg.innerHTML = '<div class="status-message">⏳ Yükleniyor...</div>';
                
                fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        uploadMsg.innerHTML = '<div class="status-message success">✅ ' + data.message + '<br>📊 Toplam: ' + data.total + ' ürün</div>';
                        // Sayfayı yenile
                        setTimeout(() => location.reload(), 2000);
                    } else {
                        uploadMsg.innerHTML = '<div class="status-message error">❌ ' + data.message + '</div>';
                    }
                })
                .catch(error => {
                    uploadMsg.innerHTML = '<div class="status-message error">❌ Hata: ' + error + '</div>';
                });
            }
        </script>
    </body>
    </html>
    """
    
    return render_template_string(html_template, progress=progress)

@app.route('/api/progress')
def api_progress():
    """API endpoint for progress"""
    progress = get_progress()
    progress['script_running'] = script_running
    return jsonify(progress)

@app.route('/api/start', methods=['POST'])
def start_script():
    """Script'i başlat"""
    global script_running, script_process
    
    if script_running:
        return jsonify({'status': 'error', 'message': 'Script zaten çalışıyor!'}), 400
    
    try:
        # Script'i arka planda başlat
        script_process = subprocess.Popen(
            ['python3', 'main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        script_running = True
        
        # Script bitince durumu güncelle
        def check_process():
            global script_running
            script_process.wait()
            script_running = False
        
        Thread(target=check_process, daemon=True).start()
        
        return jsonify({'status': 'success', 'message': 'Script başlatıldı!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stop', methods=['POST'])
def stop_script():
    """Script'i durdur"""
    global script_running, script_process
    
    if not script_running or script_process is None:
        return jsonify({'status': 'error', 'message': 'Script çalışmıyor!'}), 400
    
    try:
        script_process.terminate()
        script_running = False
        return jsonify({'status': 'success', 'message': 'Script durduruldu!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Excel dosyası yükle"""
    global GIRIS_DOSYASI
    
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Dosya seçilmedi!'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'Dosya seçilmedi!'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Güvenli dosya adı
            filename = secure_filename(file.filename)
            
            # Eski dosyayı yedekle (varsa)
            if os.path.exists(GIRIS_DOSYASI) and filename != GIRIS_DOSYASI:
                backup_name = f"{GIRIS_DOSYASI}.backup"
                shutil.copy2(GIRIS_DOSYASI, backup_name)
            
            # Yeni dosyayı kaydet
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            # GIRIS_DOSYASI'ı güncelle
            GIRIS_DOSYASI = filename
            
            # main.py'deki dosya adını da güncelle
            try:
                with open('main.py', 'r', encoding='utf-8') as f:
                    content = f.read()
                content = content.replace(
                    f'GIRIS_DOSYASI = "{GIRIS_DOSYASI}"',
                    f'GIRIS_DOSYASI = "{filename}"'
                )
                # Eğer eski dosya adı varsa onu da değiştir
                old_patterns = [
                    'GIRIS_DOSYASI = "laptop.xlsx"',
                    'GIRIS_DOSYASI = "laptopp.xlsx"',
                    'GIRIS_DOSYASI = "GüneşProducts_20251222_203037.xlsx"'
                ]
                for pattern in old_patterns:
                    if pattern in content:
                        content = content.replace(pattern, f'GIRIS_DOSYASI = "{filename}"')
                        break
                
                with open('main.py', 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                print(f"main.py güncellenemedi: {e}")
            
            # Dosya bilgilerini kontrol et
            df = pd.read_excel(filepath)
            total = len(df)
            kategoriler = df['Kategori'].value_counts().to_dict() if 'Kategori' in df.columns else {}
            
            return jsonify({
                'status': 'success',
                'message': f'Dosya yüklendi: {filename}',
                'filename': filename,
                'total': total,
                'kategoriler': kategoriler
            })
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Dosya yüklenirken hata: {str(e)}'}), 500
    
    return jsonify({'status': 'error', 'message': 'Geçersiz dosya formatı! Sadece .xlsx veya .xls dosyaları yüklenebilir.'}), 400

if __name__ == '__main__':
    print("🌐 Dashboard başlatılıyor...")
    print("📊 Tarayıcıda otomatik açılacak: http://localhost:5000")
    print("⏹️  Durdurmak için Ctrl+C")
    
    # Tarayıcıyı aç
    def open_browser():
        time.sleep(1.5)
        webbrowser.open('http://localhost:5000')
    
    Thread(target=open_browser).start()
    
    app.run(debug=True, host='127.0.0.1', port=5000, use_reloader=False)

