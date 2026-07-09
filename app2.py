import streamlit as st
import google.generativeai as genai
import requests
import os
import glob
import streamlit.components.v1 as components
import logging
import sqlite3
import json
import re
import io
import time
import threading
import pdfplumber
import unicodedata
import folium
import math
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# --- LANGUAGE DICTIONARY ---
UI_TEXT = {
    "PT": {
        "title": "💼 O Teu Super Secretário de Produtividade",
        "toast_score": "💾 Recorde de {name} ({score} pas.) guardado com sucesso!",
        "sidebar_panel": "⚙️ Painel do Agente",
        "clear_history": "🗑️ Limpar O Meu Histórico",
        "entertainment": "🕹️ Entretenimento",
        "close_game": "Fechar Jogo X",
        "open_game": "Abrir Mini-Game 👾",
        "transport_tickets": "🎫 Títulos de Transporte",
        "close_ticket": "Fechar Pedido de Passe X",
        "request_ticket": "Pedir Passe 🎫",
        "developer": "👨‍💻 Desenvolvedor",
        "dev_desc": "**Celso Ferreira**\n*À procura de emprego na área de IT / Informática.*\n📞 Contacto: **917 486 683**",
        "status": "Estado: **Online**\nModelo Nativo: `Gemini-3.5-Flash`",
        "admin_area": "🔒 Área de Administrador",
        "login_admin": "Entrar como administrador",
        "admin_pass": "Password de administrador",
        "login_btn": "Entrar",
        "wrong_pass": "Password incorreta.",
        "admin_active": "Sessão de administrador activa.",
        "web_auto": "🕷️ Automação Web",
        "sync_all": "🔄 Sincronizar Todos os Horários (Scraping)",
        "rebuild_index": "🗺️ Reconstruir Índice de Paragens",
        "discover_parish": "📍 Descobrir Freguesia de Cada Paragem",
        "sync_tickets": "🔄 Sincronizar Títulos e Tarifário",
        "logout_admin": "Sair da área de administrador",
        "telemetry_db": "📊 Telemetria e BD",
        "export_db": "📥 Exportar DB SQLite (.db)",
        "view_logs": "👁️ Ver Logs do Sistema",
        "global_history": "🗄️ Histórico Permanente Global (BD)",
        "chat_input": "Como posso ajudar hoje?",
        "speak": "Falar",
        "download_txt": "📥 Descarregar Resposta (.txt)",
        "initial_msg": "Olá, Celso! Sou o teu **Agente de Produtividade de Elite**.\n\nEstou pronto para te apoiar em três frentes:\n1. **Modo Executivo:** Monitorização da frota Guimabus e consulta à Knowledge Base.\n2. **Modo Tech Recruiter:** Diz-me *'Quero treinar para uma entrevista'* para simularmos testes técnicos em inglês.\n3. **Modo Helpdesk Técnico:** Envia-me um problema de IT ou avaria e eu mostro-te como o Celso resolveria a situação.\n\nComo posso ajudar hoje?",
        "game_title": "🚌 Guimabus Arcade: Cabine de Condução 🚌",
        "game_play": "Play ▶",
        "game_pause": "Pause ⏸",
        "game_reset": "Reset 🔄",
        "game_save": "Gravar 💾",
        "game_name": "Teu Nome",
        "game_pax": "Passageiros",
        "game_top10": "🏆 TOP 10 MOTORISTAS",
        "game_gameover": "FIM DA LINHA",
        "game_transported": "Transportaste",
        "game_type_name": "Digita o teu nome no painel abaixo.",
        "game_alert": "Por favor introduz o teu nome!",
        "ad_disclaimer": "⚠️ Aviso importante: Esta é uma ferramenta de apoio e verificação preliminar. Não é um canal oficial de submissão à Guimabus.",
        "ad_notice": "Aviso",
        "ticket_title": "🎫 Pedido de Passe — Guimabus",
        "ticket_warning": "⚠️ **Aviso importante:** este formulário é uma ferramenta de apoio e verificação preliminar. **Não é um canal oficial de submissão.**",
        "ticket_updated": "📅 Dados atualizados em:",
        "ticket_wizard": "🧭 Não sabes qual tipologia é a tua? Responde a estas perguntas",
        "ticket_age": "A tua idade",
        "ticket_resident": "Resides no concelho de Guimarães?",
        "ticket_student": "És estudante?",
        "ticket_level": "Que nível de ensino?",
        "ticket_level_opt1": "Até 18 anos",
        "ticket_level_opt2": "Até 23 anos",
        "ticket_level_opt3": "Ensino Superior",
        "ticket_disability": "Grau de incapacidade ≥ 60%?",
        "ticket_veteran": "Antigo combatente ou viúvo(a)?",
        "ticket_retirement": "Reforma antecipada (60-65 anos)?",
        "ticket_cp": "Já tens passe CP?",
        "ticket_recommend_btn": "🔍 Recomendar tipologia",
        "ticket_suitable": "A(s) tipologia(s) mais indicada(s):",
        "ticket_default": "O passe **Mensal** normal é provavelmente a opção aplicável.",
        "ticket_choose": "Escolhe a tipologia:",
        "ticket_desc": "**Descrição:**",
        "ticket_price": "**Preço:**",
        "ticket_card": "**Custo do cartão:**",
        "ticket_deadline": "**Prazo / Recarregamento:**",
        "ticket_docs_req": "**Documentos necessários para esta tipologia:**",
        "ticket_verify_btn": "🔍 Verificar documentos carregados",
        "ticket_upload_warn": "Carrega pelo menos um documento.",
        "ticket_analyzing": "A analisar os documentos (em memória)...",
        "processing_audio": "A processar e a transcrever o teu áudio...",
        "processing_agent": "Agente a processar contexto e ferramentas...",
        "api_limit": "🚫 Limite diário gratuito da API do Gemini esgotado. Tenta novamente mais tarde.",
        "model_error": "🚫 Não foi possível obter resposta de nenhum modelo disponível neste momento.",
        "visitor": "Visitante",
        "agent": "Agente",
        "robot_reading": "O robô está a ler o site da Guimabus...",
        "rebuild_index_spinner": "A reconstruir o índice a partir da cache já existente...",
        "ask_osm": "A perguntar ao OpenStreetMap onde fica cada paragem...",
        "robot_reading_tickets": "O robô está a ler titulos/ e tarifarios/...",
        "audio_error": "Erro ao processar o ficheiro de voz:"
    },
    "EN": {
        "title": "💼 Your Super Productivity Secretary",
        "toast_score": "💾 Score for {name} ({score} pax) saved successfully!",
        "sidebar_panel": "⚙️ Agent Panel",
        "clear_history": "🗑️ Clear My History",
        "entertainment": "🕹️ Entertainment",
        "close_game": "Close Game X",
        "open_game": "Open Mini-Game 👾",
        "transport_tickets": "🎫 Transport Tickets",
        "close_ticket": "Close Ticket Request X",
        "request_ticket": "Request Ticket 🎫",
        "developer": "👨‍💻 Developer",
        "dev_desc": "**Celso Ferreira**\n*Looking for IT / Computer Science roles.*\n📞 Contact: **917 486 683**",
        "status": "Status: **Online**\nNative Model: `Gemini-3.5-Flash`",
        "admin_area": "🔒 Administrator Area",
        "login_admin": "Login as Administrator",
        "admin_pass": "Admin Password",
        "login_btn": "Login",
        "wrong_pass": "Incorrect password.",
        "admin_active": "Admin session active.",
        "web_auto": "🕷️ Web Automation",
        "sync_all": "🔄 Sync All Schedules (Scraping)",
        "rebuild_index": "🗺️ Rebuild Stop Index",
        "discover_parish": "📍 Discover Parish for Each Stop",
        "sync_tickets": "🔄 Sync Tickets and Tariff",
        "logout_admin": "Logout of Administrator Area",
        "telemetry_db": "📊 Telemetry and DB",
        "export_db": "📥 Export SQLite DB (.db)",
        "view_logs": "👁️ View System Logs",
        "global_history": "🗄️ Global Permanent History (DB)",
        "chat_input": "How can I help you today?",
        "speak": "Speak",
        "download_txt": "📥 Download Response (.txt)",
        "initial_msg": "Hello, Celso! I am your **Elite Productivity Agent**.\n\nI am ready to support you on three fronts:\n1. **Executive Mode:** Guimabus fleet monitoring and Knowledge Base consultation.\n2. **Tech Recruiter Mode:** Tell me *'I want to train for an interview'* to simulate technical tests in English.\n3. **Tech Helpdesk Mode:** Send me an IT problem or failure and I will show you how Celso would solve the situation.\n\nHow can I help you today?",
        "game_title": "🚌 Guimabus Arcade: Driving Cabin 🚌",
        "game_play": "Play ▶",
        "game_pause": "Pause ⏸",
        "game_reset": "Reset 🔄",
        "game_save": "Save 💾",
        "game_name": "Your Name",
        "game_pax": "Passengers",
        "game_top10": "🏆 TOP 10 DRIVERS",
        "game_gameover": "END OF THE LINE",
        "game_transported": "You transported",
        "game_type_name": "Type your name below.",
        "game_alert": "Please enter your name!",
        "ad_disclaimer": "⚠️ Important Notice: This is a support and preliminary verification tool. It is not an official Guimabus submission channel.",
        "ad_notice": "Notice",
        "ticket_title": "🎫 Guimabus Ticket Request",
        "ticket_warning": "⚠️ **Important warning:** this form is a support and preliminary verification tool. **It is not an official submission channel.**",
        "ticket_updated": "📅 Data updated on:",
        "ticket_wizard": "🧭 Don't know which type fits you? Answer these questions",
        "ticket_age": "Your age",
        "ticket_resident": "Do you reside in the Guimarães municipality?",
        "ticket_student": "Are you a student?",
        "ticket_level": "Education level?",
        "ticket_level_opt1": "Up to 18 years",
        "ticket_level_opt2": "Up to 23 years",
        "ticket_level_opt3": "Higher Education",
        "ticket_disability": "Disability degree ≥ 60%?",
        "ticket_veteran": "War veteran or widow(er)?",
        "ticket_retirement": "Early retirement (60-65 years)?",
        "ticket_cp": "Already have a CP train pass?",
        "ticket_recommend_btn": "🔍 Recommend ticket type",
        "ticket_suitable": "Most suitable type(s):",
        "ticket_default": "The standard **Mensal** pass is likely your best option.",
        "ticket_choose": "Choose the ticket type:",
        "ticket_desc": "**Description:**",
        "ticket_price": "**Price:**",
        "ticket_card": "**Card Cost:**",
        "ticket_deadline": "**Deadline / Recharge:**",
        "ticket_docs_req": "**Required documents for this type:**",
        "ticket_verify_btn": "🔍 Verify uploaded documents",
        "ticket_upload_warn": "Upload at least one document.",
        "ticket_analyzing": "Analyzing documents (in memory)...",
        "processing_audio": "Processing and transcribing your audio...",
        "processing_agent": "Agent processing context and tools...",
        "api_limit": "🚫 Gemini API daily free limit reached. Please try again later.",
        "model_error": "🚫 Could not get a response from any available models right now.",
        "visitor": "Visitor",
        "agent": "Agent",
        "robot_reading": "The robot is reading the Guimabus website...",
        "rebuild_index_spinner": "Rebuilding index from existing cache...",
        "ask_osm": "Querying OpenStreetMap for each stop's parish...",
        "robot_reading_tickets": "The robot is reading tickets/ and tariff/...",
        "audio_error": "Error processing voice file:"
    }
}

# 1. LOGGING CONFIGURATION (Technical Audit)
logging.basicConfig(
    filename="agent_audit.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)

# 2. DATABASE CONFIGURATION (Persistent SQLite with Concurrency Safety)
def get_db_connection():
    """Returns a highly concurrent SQLite connection."""
    conn = sqlite3.connect("agent_memory.db", timeout=15.0) # 15s timeout to prevent locking errors
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    return conn

def initialize_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS global_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            session_id TEXT,
            role TEXT,
            content TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS high_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            name TEXT,
            score INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedule_cache (
            line TEXT PRIMARY KEY,
            url TEXT,
            content_txt TEXT,
            last_updated TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_cache (
            ticket_type TEXT PRIMARY KEY,
            description TEXT,
            price TEXT,
            card_cost TEXT,
            deadline TEXT,
            documents_json TEXT,
            last_updated TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tariff_cache (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            url_pdf TEXT,
            content_txt TEXT,
            last_updated TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stop_line_cache (
            line TEXT,
            stop TEXT,
            PRIMARY KEY (line, stop)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS line_title_cache (
            line TEXT PRIMARY KEY,
            title TEXT,
            last_updated TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stop_parish_cache (
            stop TEXT PRIMARY KEY,
            parish TEXT,
            source TEXT,
            last_updated TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS geographic_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT, 
            name TEXT,
            parish TEXT,
            latitude REAL,
            longitude REAL,
            associated_lines TEXT, 
            last_updated TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_node_names ON geographic_nodes(name);")

    conn.commit()
    conn.close()

def save_message_db(session_id, role, content):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO global_history (timestamp, session_id, role, content) VALUES (?, ?, ?, ?)",
            (timestamp, session_id, role, content)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Error saving to Database: {e}")

def get_top_10_scores():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, score FROM high_scores ORDER BY score DESC, id ASC LIMIT 10")
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        logging.error(f"Error reading High Scores: {e}")
        return []

def save_score_db(name, score):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute(
            "INSERT INTO high_scores (timestamp, name, score) VALUES (?, ?, ?)",
            (timestamp, name, score)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Error saving High Score: {e}")

initialize_db()

# 3. Page Configuration
st.set_page_config(page_title="Super Secretary AI", page_icon="💼", layout="wide")

# Init Language State First
if "language" not in st.session_state:
    st.session_state.language = "PT"
ui = UI_TEXT[st.session_state.language]

# Header with Top-Right Language Flags
col1, col2, col3 = st.columns([12, 1, 1])
with col1:
    st.title(ui["title"])
with col2:
    if st.button("🇵🇹 PT", use_container_width=True):
        st.session_state.language = "PT"
        st.rerun()
with col3:
    if st.button("🇬🇧 EN", use_container_width=True):
        st.session_state.language = "EN"
        st.rerun()

# Unique Session Identifier
if "session_id" not in st.session_state:
    st.session_state.session_id = datetime.now().strftime("%H%M%S%f")

# URL Parameters for Arcade High Scores (Improved Capture)
query_params = st.query_params
if "save_name" in query_params and "save_score" in query_params:
    record_name = query_params["save_name"].upper()
    record_score = int(float(query_params["save_score"]))
    
    save_score_db(record_name, record_score)
    toast_msg = ui["toast_score"].replace("{name}", record_name).replace("{score}", str(record_score))
    st.toast(toast_msg)
    
    st.query_params.clear()
    st.rerun()

# 4. Advanced CSS Injection
st.markdown("""
    <style>
        .stChatInputContainer {
            position: relative;
        }
        .stChatInputContainer textarea {
            padding-left: 55px !important;
        }
        div[data-testid="stAudioInput"] {
            position: absolute;
            left: 12px;
            bottom: 8px;
            z-index: 9999;
            width: 38px !important;
            height: 38px !important;
            background: transparent !important;
        }
        div[data-testid="stAudioInput"] > div {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
            box-shadow: none !important;
        }
        div[data-testid="stAudioInput"] label {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)

# 5. Gemini API Initialization
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    st.error("Error: API Key missing in Streamlit Secrets.")
    st.stop()

# --- FACEBOOK RSS INTEGRATION ---
@st.cache_data(ttl=3600)
def get_facebook_warnings():
    rss_url = "https://rss.app/feeds/xF3kb9tGqqFDxAsF.xml"
    active_warnings = []
    
    now = datetime.now(ZoneInfo("Europe/Lisbon"))
    today_str = now.strftime("%d de %B de %Y") 

    try:
        response = requests.get(rss_url, timeout=10)
        soup = BeautifulSoup(response.content, "xml") 
        items = soup.find_all("item")
        posts = []
        
        for i, item in enumerate(items[:10]):
            title = item.find("title").text if item.find("title") else "Warning"
            content_encoded = item.find("content:encoded")
            desc = content_encoded.text if content_encoded else (item.find("description").text if item.find("description") else "")
            clean_text = BeautifulSoup(desc, "html.parser").get_text(separator=" ").strip()
            
            enclosure = item.find("enclosure")
            img_url = enclosure.get("url") if enclosure and enclosure.get("url") else ""
            
            if not img_url and desc:
                img_match = re.search(r'src="([^"]+)"', desc)
                if img_match:
                    img_url = img_match.group(1)
            
            posts.append({
                "id": i, 
                "title": title, 
                "text": clean_text, 
                "image": img_url
            })

        prompt = f"""
        Today is {today_str}. Analyze the posts below.
        1. Identify the expiration date of each warning.
        2. If the expiration date has passed relative to {today_str}, consider the warning EXPIRED.
        3. If the warning is about roadworks/traffic/strikes (obras/trânsito/greves), priority 5. Otherwise, priority 1.
        4. Return ONLY a JSON array: [ {{"id": 0, "priority": 5}}, ... ] (only the ACTIVE ones).
        Posts: {json.dumps(posts, ensure_ascii=False)}
        """
        
        model = genai.GenerativeModel("gemini-3.5-flash")
        resp = model.generate_content(prompt)
        match = re.search(r'\[(.*?)\]', resp.text, re.DOTALL)
        
        if match:
            result = json.loads("[" + match.group(1) + "]")
            for r in result:
                p = next((x for x in posts if x["id"] == r["id"]), None)
                if p:
                    active_warnings.append({
                        "text": p["text"], 
                        "image": p["image"], 
                        "priority": r["priority"]
                    })
            active_warnings.sort(key=lambda x: x["priority"], reverse=True)
            
    except Exception as e:
        logging.error(f"RSS Error: {e}")
    return active_warnings

def render_ad_footer(active_ads, ui):
    if not active_ads: return
    js_data = json.dumps(active_ads)
    
    footer_html = f"""
    <style>
        .footer-wrapper {{
            position: fixed; bottom: 0; left: 0; width: 100%; height: 160px;
            background-color: #1e1e1e; color: white; z-index: 9999;
            border-top: 4px solid #2ecc71; box-shadow: 0px -4px 20px rgba(0,0,0,0.8);
            display: flex; flex-direction: column; overflow: hidden;
        }}
        .disclaimer {{
            background: #2a2a2a; color: #eee; font-size: 13px; padding: 6px 20px;
            text-align: center; font-weight: bold; border-bottom: 1px solid #444;
        }}
        .content-area {{ 
            display: flex; align-items: center; flex: 1; padding: 0 20px; 
        }}
        .img-box {{ flex: 0 0 120px; display: flex; align-items: center; justify-content: center; }}
        #ticker-img {{ max-height: 90px; border-radius: 6px; cursor: pointer; border: 2px solid #555; }}
        .text-container {{ flex: 1; overflow: hidden; position: relative; height: 100px; }}
        #ticker-text {{ 
            position: absolute; white-space: nowrap; font-size: 20px; 
            font-weight: bold; top: 35px; left: 50%;
        }}
    </style>
    
    <div class="footer-wrapper">
        <div class="disclaimer">{ui['ad_disclaimer']}</div>
        <div class="content-area">
            <div class="img-box">
                <img id="ticker-img" src="" onclick="window.open(this.src, '_blank');">
            </div>
            <div class="text-container">
                <div id="ticker-text"></div>
            </div>
        </div>
    </div>

    <script>
        const ads = {js_data};
        let index = 0;
        const txt = document.getElementById('ticker-text');
        const img = document.getElementById('ticker-img');
        const container = document.querySelector('.text-container');

        async function runTicker() {{
            const a = ads[index];
            txt.innerText = "🚨 " + (a.text || a.title || "{ui['ad_notice']}");
            
            if (a.image && a.image.trim() !== "") {{
                img.src = a.image;
                img.style.display = "block";
                img.style.visibility = "visible";
            }} else {{
                img.style.display = "none";
            }}
            
            txt.style.animation = 'none';
            txt.offsetHeight;
            txt.style.animation = 'scroll-left 25s linear infinite';
            
            let pos = container.offsetWidth / 2;
            txt.style.left = pos + "px";
            
            function animate() {{
                pos -= 2; 
                txt.style.left = pos + "px";
                if (pos < -txt.offsetWidth) {{
                    index = (index + 1) % ads.length;
                    setTimeout(runTicker, 2000); 
                }} else {{
                    requestAnimationFrame(animate);
                }}
            }}
            animate();
        }}
        runTicker();
    </script>
    """
    components.html(footer_html, height=170)

# --- GEOGRAPHIC FUNCTIONS ---
def normalize_search_name(text):
    if not text: return ""
    t = text.lower().strip()
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'[^a-z0-9]', '_', t)
    t = re.sub(r'_+', '_', t).strip('_')
    return t

@st.cache_data
def load_static_map():
    try:
        with open("geo_guimaraes.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {}

LOCAL_MAP = load_static_map()

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0 
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c * 1000 

def find_closest_stop(location_name: str):
    if not LOCAL_MAP:
        return "Static map is not loaded. Check the geo_guimaraes.json file."
    search_key = normalize_search_name(location_name)
    found_location = None

    for key, data in LOCAL_MAP.items():
        if search_key in key or key in search_key:
            found_location = data
            break

    if not found_location:
        return f"Could not locate '{location_name}' in the static map of Guimarães."

    lat_origin = found_location["lat"]
    lon_origin = found_location["lon"]

    closest_stop = None
    shortest_distance = float('inf')

    for key, data in LOCAL_MAP.items():
        if data.get("type") in ["bus_stop", "public_transport"]:
            dist = calculate_distance(lat_origin, lon_origin, data["lat"], data["lon"])
            if dist < shortest_distance:
                shortest_distance = dist
                closest_stop = data["nome_real"]

    if closest_stop:
        return f"The location '{found_location['nome_real']}' is {int(shortest_distance)} meters away from the '{closest_stop}' bus stop."
    else:
        return "Location found, but no bus stops in the vicinity."

def generate_google_maps_link(location_name: str):
    if not LOCAL_MAP:
        return "Static map not properly loaded."
    search_key = normalize_search_name(location_name)
    
    for map_key, local_data in LOCAL_MAP.items():
        if search_key in map_key or map_key in search_key:
            real_name = local_data["nome_real"]
            lat = local_data["lat"]
            lon = local_data["lon"]
            maps_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            return f"📍 Found exact location for '{real_name}'. Open in Google Maps here: {maps_link}"
            
    return f"Could not find '{location_name}' in Guimarães static map."

def generate_line_map_html(line_id):
    os.makedirs("maps", exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stop FROM stop_line_cache WHERE line = ? OR line = ?", (line_id, str(line_id).zfill(3)))
    line_stops = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    if not line_stops: return "No cached stops for this line."
    
    route_coordinates = []
    stops_with_coords = []
    for stop in line_stops:
        search_key = normalize_search_name(stop)
        for k, v in LOCAL_MAP.items():
            if search_key in k or k in search_key:
                route_coordinates.append([v["lat"], v["lon"]])
                stops_with_coords.append({"name": stop, "lat": v["lat"], "lon": v["lon"]})
                break
    
    if not stops_with_coords: return "Not enough geographic data to map this line."
        
    map_obj = folium.Map(location=[stops_with_coords[0]["lat"], stops_with_coords[0]["lon"]], zoom_start=13, tiles="OpenStreetMap")
    for p in stops_with_coords:
        popup_text = f"<b>Stop:</b> {p['name']}<br><b>Line:</b> {line_id}"
        folium.Marker(
            location=[p["lat"], p["lon"]],
            popup=folium.Popup(popup_text, max_width=300),
            icon=folium.Icon(color="green", icon="bus", prefix="fa")
        ).add_to(map_obj)
        
    if len(route_coordinates) > 1:
        folium.PolyLine(route_coordinates, color="blue", weight=3, opacity=0.7).add_to(map_obj)
        
    file_path = f"maps/line_{line_id}.html"
    map_obj.save(file_path)
    return file_path

# --- CONTEXT TOOLS ---
def _extract_vehicle_list(data):
    if isinstance(data, list): return data
    if isinstance(data, dict):
        for key in ("vehicles", "data", "results", "items", "veiculos"):
            val = data.get(key)
            if isinstance(val, list): return val
        for val in data.values():
            if isinstance(val, list): return val
    return []

def _first_value(dictionary, keys, default=None):
    for key in keys:
        if isinstance(dictionary, dict) and key in dictionary and dictionary[key] is not None:
            return dictionary[key]
    return default

KNOWN_STOPS_DICTIONARY = {"vaca negra": "1103", "central": "1001", "hospital": "1045", "universidade": "1022", "estacao": "1005"}

@st.cache_data(ttl=60)
def get_guimabus_data(route_id: str = None):
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    url = "https://gmr.elevensystems.pt/api/locations"
    params = {"passengerInfo": "true"}
    if route_id: params["routeId"] = route_id
    try:
        response = requests.get(url, headers=headers, params=params, timeout=8)
        response.raise_for_status()
        try: data = response.json()
        except ValueError: return "Unable to read Guimabus data."
        vehicles = _extract_vehicle_list(data)
        if not vehicles: return f"There are currently no buses in circulation."

        total_delay = 0
        delayed_count = 0
        summary = "Real-time fleet data (Guimabus):\n"
        for bus in vehicles:
            bus_id = _first_value(bus, ["id", "vehicleId", "vehicle_id", "code"], "N/A")
            line = _first_value(bus, ["line", "lineName", "route", "routeShortName", "routeId"], None)
            status = _first_value(bus, ["busStatus", "status", "state"], "N/A")
            delay = _first_value(bus, ["delay", "delayMinutes", "delay_min"], None)

            line_txt = f" (Line {line})" if line else ""
            delay_txt = f"{delay}min" if delay is not None else "unknown"
            summary += f"- Bus {bus_id}{line_txt}: Status {status} (Delay: {delay_txt})\n"

            if isinstance(delay, (int, float)):
                total_delay += delay
                delayed_count += 1

        if delayed_count > 0:
            avg_delay = total_delay / delayed_count
            summary += f"\n--- Statistic: Average fleet delay: {avg_delay:.1f} minutes. ---"
        return summary
    except Exception as e:
        return f"Tracking connection error: {e}"

@st.cache_data(ttl=30)
def get_stop_schedules(stop_id: str):
    if not stop_id: return "Stop ID is required."
    source_text = str(stop_id).strip().lower()
    numeric_id = None
    for name_p, id_p in KNOWN_STOPS_DICTIONARY.items():
        if name_p in source_text:
            numeric_id = id_p
            break
            
    if numeric_id or source_text.isdigit():
        target_id = numeric_id if numeric_id else source_text
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        url = f"https://gmr.elevensystems.pt/api/stops/{target_id}/routes"
        params = {"shape": "true", "passengerInfo": "true"}
        try:
            response = requests.get(url, headers=headers, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            routes = _extract_vehicle_list(data)
            if routes:
                summary = f"Real-time forecasts for stop {target_id}:\n"
                for route in routes:
                    line = _first_value(route, ["line", "lineName", "route", "routeShortName", "routeId"], "N/A")
                    dest = _first_value(route, ["destination", "headsign", "direction"], None)
                    eta = _first_value(route, ["eta", "etaMinutes", "waitTime", "waitingTime", "arrivalTime", "nextArrival"], None)
                    dest_txt = f" → {dest}" if dest else ""
                    eta_txt = f"{eta} min" if eta is not None else "no forecast"
                    summary += f"- Line {line}{dest_txt}: {eta_txt}\n"
                return summary
        except Exception: pass

    try:
        search_terms = re.sub(r'\b(estou|na|no|em|paragem|para|ir|as|os|a|o|da|do|linhas|linha|central|guimaraes|guimarães|tenho|quais|quero)\b', '', source_text).split()
        if not search_terms: search_terms = [source_text]
        conn = get_db_connection()
        cursor = conn.cursor()
        conditions = " AND ".join(["content_txt LIKE ?" for _ in search_terms])
        values = [f"%{term}%" for term in search_terms]
        query_sql = f"SELECT line, content_txt FROM schedule_cache WHERE {conditions}"
        cursor.execute(query_sql, values)
        found_lines = cursor.fetchall()
        conn.close()
        
        if found_lines:
            search_result = f"Scanned local schedule cache and identified lines referencing '{stop_id}':\n"
            for row in found_lines:
                num_line = row[0]
                text_lines = row[1].split("\n")
                relevant_snippet = []
                for l in text_lines:
                    if any(term in l.lower() for term in search_terms) or "página" in l.lower() or "tabela" in l.lower():
                        relevant_snippet.append(l)
                line_context = "\n".join(relevant_snippet[:25])
                search_result += f"\n--- AUTOMATIC MAPPING DETECTED: LINE {num_line} ---\n{line_context}\n"
            return search_result
    except Exception as e_db:
        pass
    return f"Could not fetch information for location '{stop_id}'."

def sync_all_guimabus_schedules():
    headers = {'User-Agent': 'Mozilla/5.0'}
    main_url = "https://guimabus.pt/horarios-linhas/"
    try:
        response = requests.get(main_url, headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        pdf_links = {}
        line_titles = {}
        for link in soup.find_all('a', href=True):
            href = link['href']
            if ".pdf" in href and "horario" in href.lower():
                match = re.search(r'linha-([a-z0-9]+)', href.lower())
                if match:
                    line_id = match.group(1).upper()
                    if line_id not in pdf_links:
                        pdf_links[line_id] = href
                        link_text = link.get_text(strip=True)
                        if link_text: line_titles[line_id] = link_text
        
        if not pdf_links: return "No schedule PDF files found on the main page."
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        processed_lines = []
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for line_id, pdf_url in pdf_links.items():
            success = False
            for attempt in range(2):
                try:
                    pdf_resp = requests.get(pdf_url, headers=headers, timeout=20)
                    if pdf_resp.status_code != 200:
                        time.sleep(1); continue
                    extracted_text = []
                    with pdfplumber.open(io.BytesIO(pdf_resp.content)) as pdf:
                        for idx, page in enumerate(pdf.pages):
                            page_text = page.extract_text(layout=True)
                            if page_text: extracted_text.append(f"[PAGE {idx+1}]\n{page_text}")
                            time.sleep(0.05) # Yield CPU to prevent UI freezing
                    final_content = "\n\n".join(extracted_text)
                    if not final_content.strip(): final_content = "PDF is image-based or copy-protected."

                    cursor.execute("INSERT OR REPLACE INTO schedule_cache (line, url, content_txt, last_updated) VALUES (?, ?, ?, ?)", (line_id, pdf_url, final_content, current_timestamp))
                    if line_id in line_titles:
                        cursor.execute("INSERT OR REPLACE INTO line_title_cache (line, title, last_updated) VALUES (?, ?, ?)", (line_id, line_titles[line_id], current_timestamp))
                    processed_lines.append(line_id)
                    success = True
                    break
                except Exception:
                    time.sleep(1); continue
            time.sleep(0.2)
        conn.commit(); conn.close()
        return f"Sync completed: {len(processed_lines)}/{len(pdf_links)} PDFs downloaded!"
    except Exception as e:
        return f"Scraping failed: {e}"

def query_line_schedule_cache(line_id: str):
    try:
        user_input = str(line_id).strip().upper()
        if not user_input: return "Line number is required."
        candidates = [user_input]
        if user_input.isdigit():
            no_zeros = user_input.lstrip('0') or '0'
            if no_zeros not in candidates: candidates.append(no_zeros)
            three_digits = user_input.zfill(3)
            if three_digits not in candidates: candidates.append(three_digits)

        conn = get_db_connection()
        cursor = conn.cursor()
        result = None
        for candidate in candidates:
            cursor.execute("SELECT content_txt, url, last_updated FROM schedule_cache WHERE line = ?", (candidate,))
            result = cursor.fetchone()
            if result: break
        conn.close()
        
        if result:
            content_txt, pdf_url, last_updated = result
            link_txt = f"\n\n🔗 Official Link: {pdf_url}" if pdf_url else ""
            return f"Cached Schedules for Line {line_id} (Updated on {last_updated}):\n\n{content_txt}{link_txt}"
        return f"No cached schedules for line {line_id}."
    except Exception as e: return f"SQLite read error: {e}"

def get_knowledge_base_content():
    context = ""
    for file in glob.glob("knowledge/*.md"):
        with open(file, "r", encoding="utf-8") as f: context += f"\n--- CONTENT FROM {os.path.basename(file)} ---\n{f.read()}"
    return context if context else "No extra documentation found."

def get_schedule_cache_age_days():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(last_updated) FROM schedule_cache")
        result = cursor.fetchone()
        conn.close()
        if not result or not result[0]: return None
        return (datetime.now() - datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")).days
    except Exception: return None

def get_ticket_cache_age_days():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(last_updated) FROM ticket_cache")
        result = cursor.fetchone()
        conn.close()
        if not result or not result[0]: return None
        return (datetime.now() - datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")).days
    except Exception: return None

def get_stop_index_count():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM stop_line_cache")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0
    except Exception: return 0

def auto_sync_if_needed(day_limit: int = 7):
    if st.session_state.get("auto_sync_attempted_this_session"): return
    st.session_state.auto_sync_attempted_this_session = True
    
    sch_age = get_schedule_cache_age_days()
    if sch_age is None or sch_age >= day_limit:
        threading.Thread(target=sync_all_guimabus_schedules, daemon=True).start()
    elif get_stop_index_count() == 0:
        threading.Thread(target=build_stop_index, daemon=True).start()
        
    tkt_age = get_ticket_cache_age_days()
    if tkt_age is None or tkt_age >= day_limit:
        threading.Thread(target=sync_tickets_and_tariff, daemon=True).start()

FALLBACK_TICKET_TYPES = {"Mensal": {"description": "Valid for the month. Unlimited trips.", "price": "Consult tariff", "card_cost": "5€", "deadline": "18th", "documents": ["ID Card"]}}

def sync_guimabus_tickets():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get("https://guimabus.pt/titulos/", headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup.find_all(['nav', 'footer', 'form', 'script', 'style']): tag.decompose()
        full_text = soup.get_text(separator="\n")
        normalized_text = "\n".join([l.strip() for l in full_text.split("\n") if l.strip()])
        blocks = re.split(r'\nPASSE\n', "\n" + normalized_text)[1:]
        if not blocks: return "No ticket types found."

        conn = get_db_connection()
        cursor = conn.cursor()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for block in blocks:
            lines = block.split("\n")
            if not lines or not lines[0].strip(): continue
            type_name = lines[0].strip()
            rest = "\n".join(lines[1:])
            
            # Improved robust regex for capturing deadlines correctly
            m_dead = re.search(r'([Ss]ó\s+podem\s+ser\s+(?:emitidos|carregados).*?\.|[Oo]\s+carregamento.*?\.)', rest, re.DOTALL | re.IGNORECASE)
            deadline = m_dead.group(1).strip().replace('\n', ' ') if m_dead else "Deadline not specified on website."

            m_price = re.search(r'Preço:\s*(.+)', rest)
            if m_price: price = m_price.group(1).strip()
            elif re.search(r'\bGRATUITO\b', rest, re.IGNORECASE): price = "Gratuito"
            else: price = "Consult tariff table"

            m_card = re.search(r'Custo do cartão:\s*([\d,]+€)', rest)
            card_cost = m_card.group(1).strip() if m_card else "Not specified"

            m_desc = re.match(r'(.*?)(?:Preço:|GRATUITO|Gratuito|\*\*Documentos necessários)', rest, re.DOTALL)
            description = m_desc.group(1).strip().replace("\n", " ") if m_desc else ""

            m_docs = re.search(r'\*\*Documentos necessários:\*\*(.*?)(?:Só podem ser emitidos|[Oo] carregamento|$)', rest, re.DOTALL)
            docs_list = [d.strip() for d in m_docs.group(1).split("\n") if d.strip() and not re.match(r'^(Custo do cartão|Preço)', d, re.IGNORECASE)] if m_docs else ["ID Card"]

            cursor.execute("INSERT OR REPLACE INTO ticket_cache (ticket_type, description, price, card_cost, deadline, documents_json, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?)", (type_name, description, price, card_cost, deadline, json.dumps(docs_list, ensure_ascii=False), ts))
        conn.commit(); conn.close()
        return "Ticket sync complete."
    except Exception as e: return f"Failed to sync ticket types: {e}"

def sync_guimabus_tariff():
    try:
        response = requests.get("https://guimabus.pt/tarifarios/", headers={'User-Agent': 'Mozilla/5.0'}, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        pdf_url = next((link['href'] for link in soup.find_all('a', href=True) if ".pdf" in link['href'].lower()), None)
        if not pdf_url: return "No tariff PDF found."
        
        pdf_resp = requests.get(pdf_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        pdf_resp.raise_for_status()
        extracted = []
        with pdfplumber.open(io.BytesIO(pdf_resp.content)) as pdf:
            for idx, page in enumerate(pdf.pages):
                txt = page.extract_text(layout=True)
                if txt: extracted.append(f"[PAGE {idx+1}]\n{txt}")
                time.sleep(0.05) # Yield CPU
        final_content = "\n\n".join(extracted) or "Image-based PDF."
        
        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO tariff_cache (id, url_pdf, content_txt, last_updated) VALUES (1, ?, ?, ?)", (pdf_url, final_content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); conn.close()
        return "Tariff sync complete."
    except Exception as e: return f"Failed to sync tariff: {e}"

def sync_tickets_and_tariff():
    return f"{sync_guimabus_tickets()}\n{sync_guimabus_tariff()}"

def _extract_stops_from_text(text: str):
    stops = set()
    pattern = re.compile(r'^(?P<name>.+?)\s+(?P<schedules>(?:-|\d{1,2}:\d{2})(?:\s+(?:-|\d{1,2}:\d{2})){2,})\s*$')
    for line in text.split("\n"):
        line = line.strip()
        if not line or "|" in line or line.startswith("[PAGE") or line.startswith("[P"): continue
        m = pattern.match(line)
        if m and len(m.group("name").strip(" -\t")) >= 3: stops.add(m.group("name").strip(" -\t"))
    return stops

def build_stop_index():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT line, content_txt FROM schedule_cache")
        cached_lines = cursor.fetchall()
        cursor.execute("DELETE FROM stop_line_cache")
        
        count = 0
        for line_id, content in cached_lines:
            if not content: continue
            for stop in _extract_stops_from_text(content):
                cursor.execute("INSERT OR IGNORE INTO stop_line_cache (line, stop) VALUES (?, ?)", (line_id, stop))
                count += 1
        conn.commit(); conn.close()
        return f"Stop index rebuilt: {count} associations."
    except Exception as e: return f"Failed to build index: {e}"

def _normalize_stop_name(text: str):
    t = re.sub(r'\bsão\b', 's.', text.lower().strip())
    t = re.sub(r'\bsanta\b', 'sta.', t)
    t = re.sub(r'\bsanto\b', 'sto.', t).replace('.', '')
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', t).strip()

def _search_lines_by_title(norm_term: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT line, title FROM line_title_cache")
        all_titles = cursor.fetchall()
        conn.close()
    except Exception: return set(), []
    
    found_lines, found_titles = set(), []
    for line_id, title in all_titles:
        if title and re.search(r'\b' + re.escape(norm_term) + r'\b', _normalize_stop_name(title)):
            found_lines.add(line_id)
            found_titles.append(f"Line {line_id}: {title}")
    return found_lines, found_titles

def enrich_stops_with_parish(progress_callback=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT stop FROM stop_line_cache")
        all_stops = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT stop FROM stop_parish_cache")
        already_done = {row[0] for row in cursor.fetchall()}
        conn.close()
    except Exception: return "Error preparing enrichment."

    pending = [p for p in all_stops if p not in already_done]
    if not pending: return "All stops enriched."

    conn = get_db_connection()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for idx, stop in enumerate(pending):
        try:
            resp = requests.get("https://nominatim.openstreetmap.org/search", params={"q": f"{stop}, Guimarães, Portugal", "format": "json", "addressdetails": 1, "countrycodes": "pt", "limit": 1}, headers={'User-Agent': 'SuperSecretaryAI'}, timeout=10)
            resp.raise_for_status()
            res = resp.json()
            parish = res[0].get("address", {}).get("suburb") or res[0].get("address", {}).get("city_district") if res else None
            conn.execute("INSERT OR REPLACE INTO stop_parish_cache (stop, parish, source, last_updated) VALUES (?, ?, ?, ?)", (stop, parish, "nominatim" if parish else "no_result", ts))
            if progress_callback: progress_callback(idx + 1, len(pending), stop)
        except Exception: pass
        time.sleep(1.1)
    conn.commit(); conn.close()
    return "Enrichment completed."

def get_parish_from_stop(stop_name: str):
    try:
        conn = get_db_connection()
        all_data = conn.execute("SELECT stop, parish FROM stop_parish_cache WHERE parish IS NOT NULL").fetchall()
        conn.close()
    except Exception: return None

    norm_name = _normalize_stop_name(stop_name)
    for stop, parish in all_data:
        stop_norm = _normalize_stop_name(stop)
        if re.search(r'\b' + re.escape(norm_name) + r'\b', stop_norm) or re.search(r'\b' + re.escape(stop_norm) + r'\b', norm_name):
            return parish
    return None

def find_stops_by_parish(parish_name: str):
    try:
        conn = get_db_connection()
        all_data = conn.execute("SELECT stop, parish FROM stop_parish_cache WHERE parish IS NOT NULL").fetchall()
        conn.close()
    except Exception: return []
    norm_parish = _normalize_stop_name(parish_name)
    return [stop for stop, parish in all_data if re.search(r'\b' + re.escape(norm_parish) + r'\b', _normalize_stop_name(parish))]

def plan_trip_with_transfer(origin: str, destination: str):
    if not origin or not destination: return "You must provide an origin stop and a destination stop."
    norm_orig, norm_dest = _normalize_stop_name(origin), _normalize_stop_name(destination)
    
    try:
        conn = get_db_connection()
        all_data = conn.execute("SELECT line, stop FROM stop_line_cache").fetchall()
        conn.close()
    except Exception: return "Error querying stop index."
    
    if not all_data: return "Index not built."

    orig_lines, dest_lines, line_stops_map = set(), set(), {}
    found_orig, found_dest = set(), set()
    for l_id, s in all_data:
        line_stops_map.setdefault(l_id, set()).add(s)
        s_norm = _normalize_stop_name(s)
        if re.search(r'\b' + re.escape(norm_orig) + r'\b', s_norm): orig_lines.add(l_id); found_orig.add(s)
        if re.search(r'\b' + re.escape(norm_dest) + r'\b', s_norm): dest_lines.add(l_id); found_dest.add(s)

    warn_o_title = warn_d_title = False
    o_titles, d_titles = [], []
    if not orig_lines: orig_lines, o_titles = _search_lines_by_title(norm_orig); warn_o_title = bool(orig_lines)
    if not dest_lines: dest_lines, d_titles = _search_lines_by_title(norm_dest); warn_d_title = bool(dest_lines)

    if not orig_lines: return f"Could not find '{origin}'."
    if not dest_lines: return f"Could not find '{destination}'."

    warn_msg = ("\n⚠️ Title used for Origin." if warn_o_title else "") + ("\n⚠️ Title used for Dest." if warn_d_title else "")

    if orig_lines & dest_lines:
        return f"DIRECT line(s) between '{origin}' and '{destination}':\n" + "\n".join(f"- Line {l}" for l in (orig_lines & dest_lines)) + warn_msg

    o_stops = set.union(*(line_stops_map.get(l, set()) for l in orig_lines))
    d_stops = set.union(*(line_stops_map.get(l, set()) for l in dest_lines))
    transfers = (o_stops & d_stops) - found_orig - found_dest

    if not transfers: return "No transfer found."
    summary = f"No direct line. Suggested transfers:\n\n"
    for t in sorted(transfers):
        l_to = [l for l in orig_lines if t in line_stops_map.get(l, set())]
        l_from = [l for l in dest_lines if t in line_stops_map.get(l, set())]
        summary += f"- Via **{t}**: lines {'/'.join(l_to)} -> '{t}' -> lines {'/'.join(l_from)}.\n"
    return summary + warn_msg

def query_stop_parish_tool(name: str):
    if not name: return "Name required."
    parish = get_parish_from_stop(name)
    if parish: return f"Stop '{name}' is in {parish}."
    stops = find_stops_by_parish(name)
    if stops: return f"Stops in '{name}': {', '.join(stops)}."
    return f"No info for '{name}'."

def get_ticket_types_cache():
    try:
        conn = get_db_connection()
        rows = conn.execute("SELECT ticket_type, description, price, card_cost, deadline, documents_json FROM ticket_cache ORDER BY ticket_type").fetchall()
        last_updated = conn.execute("SELECT MAX(last_updated) FROM ticket_cache").fetchone()[0]
        conn.close()
        if not rows: return FALLBACK_TICKET_TYPES, None
        
        result = {}
        for type_name, desc, price, card_cost, deadline, docs_json in rows:
            try: docs = json.loads(docs_json)
            except Exception: docs = [docs_json]
            result[type_name] = {"description": desc, "price": price, "card_cost": card_cost, "deadline": deadline, "documents": docs}
        return result, last_updated
    except Exception: return FALLBACK_TICKET_TYPES, None

def query_tariff_cache():
    try:
        conn = get_db_connection()
        res = conn.execute("SELECT content_txt, last_updated FROM tariff_cache WHERE id = 1").fetchone()
        conn.close()
        return f"Tariff (updated {res[1]}):\n\n{res[0]}" if res else "Not synchronized."
    except Exception as e: return str(e)

def query_ticket_types_cache_tool():
    types, up = get_ticket_types_cache()
    if not types: return "No types."
    return f"Types ({up}):\n\n" + "\n".join(f"- **{n}**: {i['description']} Price: {i['price']}" for n, i in types.items())

def verify_ticket_documents(ticket_type: str, uploaded_files: dict):
    current_types, _ = get_ticket_types_cache()
    info = current_types.get(ticket_type, {"documents": ["unspecified document"]})
    parts = [
        f"Review uploaded documents for a '{ticket_type}' ticket.\nRequired: {', '.join(info['documents'])}.\n"
        "State for EACH: 1. Type 2. Matches required? 3. Legible? Mention missing ones."
    ]
    for n, f in uploaded_files.items():
        if f is None: continue
        parts.extend([f"\n--- Document: '{n}' ---", {"mime_type": f.type or "application/octet-stream", "data": f.getvalue()}])
    if len(parts) == 1: return "No documents uploaded."
    try:
        return genai.GenerativeModel("gemini-3.5-flash").generate_content(parts, request_options={"timeout": 40}).text
    except Exception as e: return f"Error: {e}"

def recommend_ticket_types(answers: dict, available_types: dict):
    c = []
    def _h(p): return next((n for n in available_types if p.lower() in n.lower()), None)
    if answers.get("veteran") and _h("Antigo Combatente"): c.append(_h("Antigo Combatente"))
    if answers.get("disability_60") and _h("Mobilidade Condicionada"): c.append(_h("Mobilidade Condicionada"))
    if answers.get("age", 0) >= 65 and answers.get("gmr_resident") and _h("65+"): c.append(_h("65+"))
    if answers.get("student"):
        if answers.get("study_level") == "superior":
            c.append(_h("Universitário Residente") if answers.get("gmr_resident") else _h("Universitário Não Residente"))
        elif answers.get("study_level") == "up_to_18": c.append(_h("18+TP"))
        elif answers.get("study_level") == "up_to_23": c.append(_h("23+TP"))
    
    c = [x for x in c if x]
    if not c:
        if answers.get("gmr_resident") and _h("CIM AVE 50% + 10% CMG"): c.append(_h("CIM AVE 50% + 10% CMG"))
        elif _h("Mensal") and not _h("CIM"): c.append(next(n for n in available_types if n.strip().lower() == "mensal"))
    return list(dict.fromkeys(c))

def render_ticket_request(ui):
    st.subheader(ui["ticket_title"])
    st.info(ui["ticket_warning"])

    TICKET_TYPES, last_update = get_ticket_types_cache()
    if last_update: st.caption(f"{ui['ticket_updated']} {last_update}")

    with st.expander(ui["ticket_wizard"], expanded=False):
        col1, col2 = st.columns(2)
        age = col1.number_input(ui["ticket_age"], min_value=0, max_value=120, value=25, step=1, key="wizard_age")
        gmr_resident = col2.checkbox(ui["ticket_resident"], key="wizard_resident")

        student = st.checkbox(ui["ticket_student"], key="wizard_student")
        study_level = None
        if student:
            level_map = {"up_to_18": ui["ticket_level_opt1"], "up_to_23": ui["ticket_level_opt2"], "superior": ui["ticket_level_opt3"]}
            study_level = st.radio(ui["ticket_level"], options=list(level_map.keys()), format_func=lambda x: level_map[x], key="wizard_level")

        col3, col4 = st.columns(2)
        disability_60 = col3.checkbox(ui["ticket_disability"], key="wizard_disability")
        veteran = col4.checkbox(ui["ticket_veteran"], key="wizard_veteran")

        col5, col6 = st.columns(2)
        early_retirement = col5.checkbox(ui["ticket_retirement"], key="wizard_retirement")
        uses_cp_pass = col6.checkbox(ui["ticket_cp"], key="wizard_cp")

        if st.button(ui["ticket_recommend_btn"], key="wizard_recommend"):
            ans = {"age": age, "gmr_resident": gmr_resident, "student": student, "study_level": study_level, "disability_60": disability_60, "veteran": veteran, "early_retirement": early_retirement, "uses_cp_pass": uses_cp_pass}
            rec = recommend_ticket_types(ans, TICKET_TYPES)
            if rec: st.success(f"{ui['ticket_suitable']} **{' / '.join(rec)}**")
            else: st.warning(ui["ticket_default"])

    chosen_type = st.selectbox(ui["ticket_choose"], list(TICKET_TYPES.keys()))
    info = TICKET_TYPES[chosen_type]

    st.markdown(f"{ui['ticket_desc']} {info['description']}\n{ui['ticket_price']} {info['price']} | {ui['ticket_card']} {info['card_cost']}\n{ui['ticket_deadline']} {info['deadline']}")
    st.markdown(ui["ticket_docs_req"])
    uploaded_files = {}
    for i, doc_name in enumerate(info["documents"]):
        uploaded_files[doc_name] = st.file_uploader(f"📄 {doc_name}", type=["pdf", "png", "jpg", "jpeg"], key=f"upload_pass_{chosen_type}_{i}")

    if st.button(ui["ticket_verify_btn"], use_container_width=True):
        if not any(f is not None for f in uploaded_files.values()): st.warning(ui["ticket_upload_warn"])
        else:
            with st.spinner(ui["ticket_analyzing"]):
                st.markdown(verify_ticket_documents(chosen_type, uploaded_files))

def render_arcade_game(ui):
    json_scores = json.dumps(get_top_10_scores())
    html_game = f"""
    <div style="text-align:center; background-color:#111; padding:15px; border-radius:10px; font-family:sans-serif;">
        <h3 style="color:#2ecc71; margin-top:0; margin-bottom:10px;">{ui['game_title']}</h3>
        
        <canvas id="stage" width="650" height="360" style="border:2px solid #2ecc71; background-color:#000; display:block; margin:0 auto; touch-action:none;"></canvas>
        
        <div style="margin-top: 10px;">
            <button id="btnAction" onclick="toggleGame()" style="padding: 6px 15px; background:#2ecc71; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">{ui['game_play']}</button>
            <input type="text" id="nameInput" placeholder="{ui['game_name']}" maxlength="10" style="display:none; padding: 5px; border-radius:4px; border:1px solid #2ecc71; background:#222; color:white; width:120px; margin-left:10px; vertical-align:middle; text-transform:uppercase;">
            <button id="btnSave" onclick="saveRecord()" style="display:none; padding: 6px 15px; background:#f1c40f; color:black; border:none; border-radius:5px; font-weight:bold; cursor:pointer; margin-left:5px; vertical-align:middle;">{ui['game_save']}</button>
        </div>

        <div style="margin-top: 15px; display: inline-block; width: 100%; text-align: center;">
            <div style="margin-bottom: 5px;">
                <button data-dir="up" style="padding: 12px 24px; background: #34495e; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 18px;">▲</button>
            </div>
            <div style="display: flex; justify-content: center; gap: 10px;">
                <button data-dir="left" style="padding: 12px 24px; background: #34495e; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 18px;">◀</button>
                <button data-dir="down" style="padding: 12px 24px; background: #34495e; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 18px;">▼</button>
                <button data-dir="right" style="padding: 12px 24px; background: #34495e; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 18px;">▶</button>
            </div>
        </div>
        
        <script>
            var canvas = document.getElementById('stage');
            var ctx = canvas.getContext('2d');
            var btnAction = document.getElementById('btnAction');
            var nameInput = document.getElementById('nameInput');
            var btnSave = document.getElementById('btnSave');
            
            var tnt = 20;
            var gameWidth = 400;
            var snake, dx, dy, apple, score, speedMs, nextDir, gameInterval, gameStarted, gameOver;
            var leaderboard = {json_scores};

            function newApple() {{
                var pos;
                do {{ pos = {{x: Math.floor(Math.random() * (gameWidth/tnt)) * tnt, y: Math.floor(Math.random() * (canvas.height/tnt)) * tnt}};
                }} while (snake.some(function(s) {{ return s.x === pos.x && s.y === pos.y; }}));
                return pos;
            }}

            function initialState() {{
                snake = [{{x:160, y:160}}, {{x:140, y:160}}, {{x:120, y:160}}];
                dx = tnt; dy = 0; nextDir = null; score = 0; speedMs = 180;
                apple = newApple(); gameOver = false;
                nameInput.style.display = 'none'; btnSave.style.display = 'none';
            }}
            initialState();
            
            function drawScene() {{
                ctx.fillStyle = '#222222'; ctx.fillRect(0, 0, gameWidth, canvas.height);
                ctx.fillStyle = '#2ecc71'; ctx.fillRect(gameWidth, 0, 3, canvas.height);

                ctx.fillStyle = '#3498db'; ctx.beginPath();
                ctx.arc(apple.x + tnt/2, apple.y + tnt/2, (tnt-4)/2, 0, 2 * Math.PI); ctx.fill();
                
                for(var i=0; i<snake.length; i++) {{
                    ctx.fillStyle = (i===0) ? '#27ae60' : '#2ecc71';
                    ctx.fillRect(snake[i].x + 1, snake[i].y + 1, tnt-2, tnt-2);
                }}

                ctx.fillStyle = '#ffffff'; ctx.font = 'bold 14px sans-serif'; ctx.textAlign = 'start';
                ctx.fillText('{ui['game_pax']}: ' + (score / 10), 15, 25);

                ctx.fillStyle = '#151515'; ctx.fillRect(gameWidth + 3, 0, canvas.width - gameWidth - 3, canvas.height);
                ctx.fillStyle = '#2ecc71'; ctx.font = 'bold 14px sans-serif';
                ctx.fillText('{ui['game_top10']}', gameWidth + 15, 30);
                
                ctx.font = '12px sans-serif';
                for(var k=0; k<10; k++) {{
                    var yPos = 65 + (k * 26);
                    ctx.fillStyle = (k===0) ? '#f1c40f' : ((k===1) ? '#bdc3c7' : ((k===2) ? '#e67e22' : '#ffffff'));
                    if (leaderboard[k]) {{
                        ctx.fillText((k+1) + "º " + leaderboard[k][0], gameWidth + 15, yPos);
                        ctx.textAlign = 'end'; ctx.fillText(leaderboard[k][1] + ' pax', canvas.width - 15, yPos); ctx.textAlign = 'start';
                    }} else {{ ctx.fillStyle = '#444'; ctx.fillText((k+1) + 'º ------', gameWidth + 15, yPos); }}
                }}
                
                if (gameOver) {{
                    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)'; ctx.fillRect(0, 0, gameWidth, canvas.height);
                    ctx.fillStyle = '#e74c3c'; ctx.font = 'bold 22px sans-serif'; ctx.textAlign = 'center';
                    ctx.fillText('{ui['game_gameover']}', gameWidth/2, canvas.height/2 - 20);
                    ctx.fillStyle = '#ffffff'; ctx.font = '14px sans-serif';
                    ctx.fillText('{ui['game_transported']} ' + (score / 10) + '!', gameWidth/2, canvas.height/2 + 5);
                    ctx.fillStyle = '#f1c40f'; ctx.fillText('{ui['game_type_name']}', gameWidth/2, canvas.height/2 + 30);
                    ctx.textAlign = 'start';
                }}
            }}
            
            function gameLoop() {{
                if (gameOver) return;
                if (nextDir) {{ if (nextDir.dx !== -dx || nextDir.dy !== -dy) {{ dx = nextDir.dx; dy = nextDir.dy; }} nextDir = null; }}
                var head = {{x: snake[0].x + dx, y: snake[0].y + dy}};
                if (head.x < 0) head.x = gameWidth - tnt; else if (head.x >= gameWidth) head.x = 0;
                if (head.y < 0) head.y = canvas.height - tnt; else if (head.y >= canvas.height) head.y = 0;

                var willEat = (head.x === apple.x && head.y === apple.y);
                for (var i = 0; i < (willEat ? snake.length : snake.length-1); i++) {{ 
                    if (snake[i].x === head.x && snake[i].y === head.y) {{ triggerGameOver(); return; }} 
                }}
                snake.unshift(head);
                if (willEat) {{
                    score += 10;
                    if (score % 50 === 0 && speedMs > 80) {{ speedMs -= 10; clearInterval(gameInterval); gameInterval = setInterval(gameLoop, speedMs); }}
                    apple = newApple();
                }} else {{ snake.pop(); }}
                drawScene();
            }}
            
            function toggleGame() {{
                if (gameOver) {{ resetGame(); return; }}
                if (!gameStarted) {{ gameStarted = true; btnAction.innerText = "{ui['game_pause']}"; gameInterval = setInterval(gameLoop, speedMs); }} 
                else {{ gameStarted = false; btnAction.innerText = "{ui['game_play']}"; clearInterval(gameInterval); }}
            }}
            function triggerGameOver() {{
                gameOver = true; gameStarted = false; clearInterval(gameInterval); btnAction.innerText = "{ui['game_reset']}";
                if((score/10) > 0) {{ nameInput.style.display = 'inline-block'; btnSave.style.display = 'inline-block'; nameInput.focus(); }}
                drawScene();
            }}
            function resetGame() {{ 
                initialState(); gameOver = false; gameStarted = true;
                btnAction.innerText = "{ui['game_pause']}"; gameInterval = setInterval(gameLoop, speedMs); drawScene();
            }}
            function saveRecord() {{
                var name = nameInput.value.trim().toUpperCase();
                if(!name) {{ alert("{ui['game_alert']}"); return; }}
                btnSave.disabled = true; btnSave.innerText = "💾...";
                
                try {{
                    var url = new URL(window.parent.location.href);
                    url.searchParams.set("save_name", name);
                    url.searchParams.set("save_score", (score / 10));
                    window.parent.location.href = url.toString();
                }} catch(e) {{
                    alert("Unable to save data. Security restriction.");
                }}
            }}
            function changeDir(dir) {{
                if (!gameStarted || gameOver) return;
                if(dir === 'left' && dx === 0) nextDir = {{dx:-tnt, dy:0}};
                if(dir === 'up' && dy === 0) nextDir = {{dx:0, dy:-tnt}};
                if(dir === 'right' && dx === 0) nextDir = {{dx:tnt, dy:0}};
                if(dir === 'down' && dy === 0) nextDir = {{dx:0, dy:tnt}};
            }}
            document.addEventListener('keydown', function(e) {{
                var map = {{37:'left', 38:'up', 39:'right', 40:'down'}};
                if (map[e.keyCode]) {{ e.preventDefault(); changeDir(map[e.keyCode]); }}
            }});
            document.querySelectorAll('button[data-dir]').forEach(function(btn) {{
                btn.addEventListener('click', function() {{ changeDir(btn.getAttribute('data-dir')); }});
            }});
            drawScene();
        </script>
    </div>
    """
    return components.html(html_game, height=650)

# --- STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": ui["initial_msg"]}]

if len(st.session_state.messages) == 1 and st.session_state.messages[0]["role"] == "assistant":
    st.session_state.messages[0]["content"] = ui["initial_msg"]

if "game_active" not in st.session_state:
    st.session_state.game_active = False

auto_sync_if_needed(day_limit=7)

# --- SIDEBAR (AGENT MANAGEMENT) ---
with st.sidebar:
    st.header(ui["sidebar_panel"])
    if st.button(ui["clear_history"], use_container_width=True):
        st.session_state.messages = [{"role": "assistant", "content": ui["initial_msg"]}]
        st.session_state.game_active = False
        st.rerun()
    st.divider()

    st.subheader(ui["entertainment"])
    btn_game_text = ui["close_game"] if st.session_state.game_active else ui["open_game"]
    if st.button(btn_game_text, use_container_width=True):
        st.session_state.game_active = not st.session_state.game_active
        st.rerun()
    st.divider()

    st.subheader(ui["transport_tickets"])
    if "ticket_active" not in st.session_state:
        st.session_state.ticket_active = False
    btn_ticket_text = ui["close_ticket"] if st.session_state.ticket_active else ui["request_ticket"]
    if st.button(btn_ticket_text, use_container_width=True):
        st.session_state.ticket_active = not st.session_state.ticket_active
        st.rerun()
    st.divider()
    
    st.sidebar.subheader(ui["developer"])
    st.sidebar.info(ui["dev_desc"])
    st.sidebar.divider()
    
    st.write(ui["status"])
    st.sidebar.divider()
    
    st.sidebar.subheader(ui["admin_area"])
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        with st.sidebar.expander(ui["login_admin"]):
            password_input = st.text_input(ui["admin_pass"], type="password", key="admin_pwd")
            if st.button(ui["login_btn"], key="admin_login_btn"):
                if password_input and password_input == st.secrets.get("ADMIN_PASSWORD", None):
                    st.session_state.admin_authenticated = True
                    st.rerun()
                else:
                    st.sidebar.error(ui["wrong_pass"])
    else:
        st.sidebar.success(ui["admin_active"])
        
        st.sidebar.subheader(ui["web_auto"])
        if st.sidebar.button(ui["sync_all"], use_container_width=True):
            with st.spinner(ui["robot_reading"]):
                st.sidebar.success(sync_all_guimabus_schedules())
                st.sidebar.success(build_stop_index())

        if st.sidebar.button(ui["rebuild_index"], use_container_width=True):
            with st.spinner(ui["rebuild_index_spinner"]):
                st.sidebar.success(build_stop_index())

        if st.sidebar.button(ui["discover_parish"], use_container_width=True):
            st.sidebar.caption(ui["ask_osm"])
            progress_bar = st.sidebar.progress(0.0)
            progress_text = st.sidebar.empty()
            def _update_progress(current, total, current_stop):
                progress_bar.progress(current / total)
                progress_text.caption(f"{current}/{total}: {current_stop}")
            st.sidebar.success(enrich_stops_with_parish(progress_callback=_update_progress))

        if st.sidebar.button(ui["sync_tickets"], use_container_width=True):
            with st.spinner(ui["robot_reading_tickets"]):
                st.sidebar.success(sync_tickets_and_tariff())
                
        if st.sidebar.button(ui["logout_admin"], key="admin_logout_btn"):
            st.session_state.admin_authenticated = False
            st.rerun()

        st.sidebar.subheader(ui["telemetry_db"])
        if os.path.exists("agent_memory.db"):
            with open("agent_memory.db", "rb") as f:
                st.sidebar.download_button(ui["export_db"], f, "agent_memory.db", "application/octet-stream", use_container_width=True)

        with st.sidebar.expander(ui["view_logs"]):
            if os.path.exists("agent_audit.log"):
                with open("agent_audit.log", "r", encoding="utf-8") as f:
                    for line in f.readlines()[-10:]: st.caption(line.strip())

        with st.sidebar.expander(ui["global_history"]):
            if os.path.exists("agent_memory.db"):
                conn = get_db_connection()
                for r in reversed(conn.execute("SELECT timestamp, session_id, role, content FROM global_history ORDER BY id DESC LIMIT 30").fetchall()):
                    hr_min = r[0].split(" ")[1] if " " in r[0] else r[0]
                    st.markdown(f"**{'🟢' if r[2]=='user' else '🤖'} [{hr_min}] {ui['visitor'] if r[2]=='user' else ui['agent']} ({r[1]}):** {r[3]}")
                    st.divider()
                conn.close()

if st.session_state.game_active:
    render_arcade_game(ui)

if st.session_state.get("ticket_active"):
    render_ticket_request(ui)

today_warnings = get_facebook_warnings()
if today_warnings:
    render_ad_footer(today_warnings, ui)

for message in st.session_state.messages:
    avatar_type = "💼" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar_type):
        st.markdown(message["content"])

prompt_text = st.chat_input(ui["chat_input"])
audio_file = st.audio_input(ui["speak"])

prompt = None
input_type = "Text"

if "last_processed_audio_id" not in st.session_state:
    st.session_state.last_processed_audio_id = None

if prompt_text:
    prompt = prompt_text
elif audio_file:
    current_audio_id = audio_file.file_id if hasattr(audio_file, "file_id") else audio_file.name

    if current_audio_id != st.session_state.last_processed_audio_id:
        st.session_state.last_processed_audio_id = current_audio_id
        input_type = "Audio"
        with st.spinner(ui["processing_audio"]):
            try:
                transcription_response = genai.GenerativeModel("gemini-3.5-flash").generate_content([
                    "Transcribe the provided audio strictly to text, maintaining correct punctuation and the original language. Do not add extra comments.",
                    {"mime_type": "audio/wav", "data": audio_file.read()}
                ])
                prompt = transcription_response.text.strip()
            except Exception as e:
                st.error(f"{ui['audio_error']} {e}")

if prompt:
    save_message_db(st.session_state.session_id, "user", prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="💼"):
        with st.spinner(ui["processing_agent"]):
            try:
                base_context = get_knowledge_base_content()
                
                # --- AI LANGUAGE RULE ---
                LANGUAGE_INSTRUCTION = "CRUCIAL LANGUAGE RULE: You MUST respond entirely in European Portuguese (pt-PT)." if st.session_state.language == "PT" else "CRUCIAL LANGUAGE RULE: You MUST respond entirely in English."

                # --- AI SCHEDULE INSTRUCTION (Strictly enforces presenting times + link) ---
                SCHEDULE_INSTRUCTION = (
                    "MANDATÓRIO: Sempre que te pedirem horários ou linhas, tens de apresentar OBRIGATORIAMENTE as horas de partida/chegada do horário pedido lendo a cache da ferramenta `query_line_schedule_cache`. NUNCA mandes apenas o link sem mostrares o horário no texto. No final da tua resposta, tens OBRIGATORIAMENTE de colocar o link: 'Consulta o horário oficial aqui: [LINK DA LINHA]'." 
                    if st.session_state.language == "PT" else 
                    "MANDATORY: Whenever asked about schedules or lines, you MUST present the actual departure/arrival times by reading the cache from the `query_line_schedule_cache` tool. NEVER just send the link without showing the times in your text. At the very end of your response, you MUST include the link: 'Check the official schedule here: [LINE LINK]'."
                )

                EXECUTIVE_PROMPT = f"""You are Celso Ferreira's Elite Executive Assistant.
                You are an Agent focused on automation, IT support, and infrastructure.

                {LANGUAGE_INSTRUCTION}

                You have these tools related to the local Guimabus fleet:
                - get_guimabus_data: real-time fleet status.
                - get_stop_schedules: waiting time forecasts for a specific stop.
                - query_line_schedule_cache: queries the local cache to read fixed schedules and tables.
                - query_ticket_types_cache_tool: reads ticket types.
                - query_tariff_cache: reads the complete tariff table.
                - plan_trip_with_transfer: given an origin and destination stop, tells if there is a direct line or suggests a transfer.
                - query_stop_parish_tool: tells which parish a stop is in.
                - generate_google_maps_link: receives a location name (stop, cafe, hospital, street) and returns a direct Google Maps link.
                - find_closest_stop: discovers the closest official bus stop to any cafe, factory, or point of interest.

                MANDATORY PLANNING LOGIC:
                1. If the location IS NOT A STOP (e.g., cafe, factory), use the "find_closest_stop" tool FIRST.
                2. Use "plan_trip_with_transfer" with the exact stop names.
                3. {SCHEDULE_INSTRUCTION}

                TOOL CALLING EXECUTION RULE - CRITICAL:
                NEVER describe the steps you will take to search. NEVER try to calculate routes mentally or guess stops without the tools giving you that information. CALL THE TOOLS silently. Only write the final text after having the tools' response.

                ANTI-HALLUCINATION RULE — THE MOST IMPORTANT OF ALL:
                NEVER invent, estimate, or "fill in" data that the tools did not provide. ALWAYS use the information in "[CURRENT SYSTEM DATE AND TIME]". If the tool does not tell you how to go from X to Y, apologize and state clearly and honestly that you do not have that connection available in the database."""

                RECRUITER_PROMPT = """You are an expert IT Technical Recruiter interviewing Celso Ferreira for an IT role.
                Conduct the interview strictly in English. Ask one tough, deep technical or behavioral question at a time.
                Evaluate Celso's response professionally based on IT best practices and keep the interviewer persona realistic."""
                
                HELPDESK_TUTOR_PROMPT = f"""You are an IT Helpdesk and Support Technical Tutor.
                Your goal is to act as an endless source of IT problem resolution.

                {LANGUAGE_INSTRUCTION}

                Regardless of the IT issue, you MUST start your answer with: 
                'O Celso faria desta maneira para resolver este problema de IT:' (if in PT) or 'Celso would solve this IT problem like this:' (if in EN)
                Then, detail technical troubleshooting steps, PowerShell or Linux commands, and properly applied best practices."""

                normalized_prompt = prompt.lower()
                helpdesk_triggers = ["problema", "helpdesk", "ticket", "avaria", "erro", "servidor", "computador", "rede", "suporte", "falha", "problem", "error", "server", "computer", "network", "support"]
                
                if "entrevista" in normalized_prompt or "interview" in normalized_prompt:
                    active_system_prompt = RECRUITER_PROMPT
                elif any(word in normalized_prompt for word in helpdesk_triggers):
                    active_system_prompt = HELPDESK_TUTOR_PROMPT
                else:
                    active_system_prompt = EXECUTIVE_PROMPT

                api_history = []
                for msg in st.session_state.messages[:-1]:
                    if msg["content"] != ui["initial_msg"] and msg["content"] != UI_TEXT["PT"]["initial_msg"] and msg["content"] != UI_TEXT["EN"]["initial_msg"]:
                        api_role = "model" if msg["role"] == "assistant" else "user"
                        api_history.append({"role": api_role, "parts": [msg["content"]]})
                
                now = datetime.now(ZoneInfo("Europe/Lisbon"))
                date_context = f"[CURRENT SYSTEM DATE AND TIME: The time is {now.strftime('%Y-%m-%d %H:%M')}.]"

                enriched_prompt = f"{date_context}\n\n{base_context}\n\nUser Prompt: {prompt}"
                agent_tools = [get_guimabus_data, get_stop_schedules, query_line_schedule_cache, query_ticket_types_cache_tool, query_tariff_cache, plan_trip_with_transfer, query_stop_parish_tool, generate_google_maps_link, generate_line_map_html, find_closest_stop]
                
                response = None
                last_model_error = None
                for model_name in ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]:
                    try:
                        chat = genai.GenerativeModel(model_name=model_name, system_instruction=active_system_prompt, tools=agent_tools).start_chat(history=api_history, enable_automatic_function_calling=True)
                        response = chat.send_message(enriched_prompt, request_options={"timeout": 25})
                        break
                    except Exception as e:
                        last_model_error = e

                if response is None:
                    st.error(ui["api_limit"] if "429" in str(last_model_error) else ui["model_error"])
                    st.stop()

                full_response = response.text
                st.markdown(full_response)
                
                save_message_db(st.session_state.session_id, "assistant", full_response)
                st.download_button(ui["download_txt"], full_response, "response.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"Pipeline Error: {e}")
