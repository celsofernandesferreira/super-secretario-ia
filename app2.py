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
import pdfplumber
import unicodedata
import folium
import email.utils
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
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
        "robot_reading": "O robô está a ler os dados. Por favor aguarda...",
        "rebuild_index_spinner": "A reconstruir o índice a partir da cache já existente...",
        "ask_osm": "A perguntar ao OpenStreetMap onde fica cada paragem...",
        "robot_reading_tickets": "O robô está a ler titulos/ e tarifarios/...",
        "audio_error": "Erro ao processar o ficheiro de voz:",
        "updating_system": "**SISTEMA EM ATUALIZAÇÃO:** A descarregar novos horários e pacotes de dados. O agente está temporariamente bloqueado para evitar falhas. Por favor, aguarda (pode demorar 1-2 minutos)..."
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
        "robot_reading": "The robot is reading the data. Please wait...",
        "rebuild_index_spinner": "Rebuilding index from existing cache...",
        "ask_osm": "Querying OpenStreetMap for each stop's parish...",
        "robot_reading_tickets": "The robot is reading tickets/ and tariff/...",
        "audio_error": "Error processing voice file:",
        "updating_system": "**SYSTEM UPDATING:** Downloading new schedules and data packages. The agent is temporarily locked to avoid failures. Please wait (may take 1-2 minutes)..."
    }
}

# 1. CONFIGURAÇÃO DE LOGS (Auditoria Técnica)
logging.basicConfig(
    filename="auditoria_agente.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)

# 2. CONFIGURAÇÃO DA BASE DE DADOS (SQLite Persistente com High Scores e Cache de Horários)
def get_db_connection():
    conn = sqlite3.connect("agente_memoria.db", timeout=15.0) 
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    return conn

def inicializar_bd():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_global (
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
            nome TEXT,
            pontor INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_horarios (
            linha TEXT PRIMARY KEY,
            url TEXT,
            conteudo_txt TEXT,
            last_updated TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_titulos (
            tipologia TEXT PRIMARY KEY,
            descricao TEXT,
            preco TEXT,
            custo_cartao TEXT,
            prazo TEXT,
            documentos_json TEXT,
            ultima_atualizacao TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_tarifario (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            url_pdf TEXT,
            conteudo_txt TEXT,
            ultima_atualizacao TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_paragens_linha (
            linha TEXT,
            paragem TEXT,
            PRIMARY KEY (linha, paragem)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_titulo_linha (
            linha TEXT PRIMARY KEY,
            titulo TEXT,
            ultima_atualizacao TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_paragem_freguesia (
            paragem TEXT PRIMARY KEY,
            freguesia TEXT,
            fonte TEXT,
            ultima_atualizacao TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nos_geograficos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT, 
            nome TEXT,
            freguesia TEXT,
            latitude REAL,
            longitude REAL,
            linhas_associadas TEXT, 
            ultima_atualizacao TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nome_nos ON nos_geograficos(nome);")

    conn.commit()
    conn.close()

def guardar_mensagem_bd(session_id, role, content):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO historico_global (timestamp, session_id, role, content) VALUES (?, ?, ?, ?)",
            (timestamp, session_id, role, content)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Erro ao gravar na Base de Dados: {e}")

def obter_top_10():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT nome, pontor FROM high_scores ORDER BY pontor DESC, id ASC LIMIT 10")
        resultados = cursor.fetchall()
        conn.close()
        return resultados
    except Exception as e:
        logging.error(f"Erro ao ler High Scores: {e}")
        return []

def guardar_score_bd(nome, pontor):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute(
            "INSERT INTO high_scores (timestamp, nome, pontor) VALUES (?, ?, ?)",
            (timestamp, nome, pontor)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Erro ao gravar High Score: {e}")

inicializar_bd()

# 3. Configuração da página 
st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="wide")

# Inicialização do Dicionário e Toggle
if "language" not in st.session_state:
    st.session_state.language = "PT"
ui = UI_TEXT[st.session_state.language]

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

if "session_id" not in st.session_state:
    st.session_state.session_id = datetime.now().strftime("%H%M%S%f")

# --- CAPTURA DE RECORDES VIA URL ---
query_params = st.query_params
if "save_nome" in query_params and "save_pontos" in query_params:
    nome_recorde = query_params["save_nome"].upper()
    pontos_recorde = int(float(query_params["save_pontos"]))
    
    guardar_score_bd(nome_recorde, pontos_recorde)
    st.toast(ui["toast_score"].replace("{name}", nome_recorde).replace("{score}", str(pontos_recorde)))
    
    st.query_params.clear()
    st.rerun()

# 4. Injeção de CSS Avançado
st.markdown("""
    <style>
        .stChatInputContainer { position: relative; }
        .stChatInputContainer textarea { padding-left: 55px !important; }
        div[data-testid="stAudioInput"] {
            position: absolute; left: 12px; bottom: 8px; z-index: 9999;
            width: 38px !important; height: 38px !important; background: transparent !important;
        }
        div[data-testid="stAudioInput"] > div { background: transparent !important; border: none !important; padding: 0 !important; box-shadow: none !important; }
        div[data-testid="stAudioInput"] label { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# 5. Inicialização da API do Gemini
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    st.error("Erro: Chave API em falta nos Secrets do Streamlit.")
    st.stop()

# --- NATIVE DATE EXTRACTOR ---
def extrair_data_futura(texto):
    PT_MONTHS = {
        "janeiro": 1, "jan": 1, "fevereiro": 2, "fev": 2, "março": 3, "mar": 3,
        "abril": 4, "abr": 4, "maio": 5, "mai": 5, "junho": 6, "jun": 6,
        "julho": 7, "jul": 7, "agosto": 8, "ago": 8, "setembro": 9, "set": 9,
        "outubro": 10, "out": 10, "novembro": 11, "nov": 11, "dezembro": 12, "dez": 12
    }
    
    now = datetime.now()
    current_year = now.year
    found_dates = []

    for m in re.finditer(r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b', texto):
        dia, mes = int(m.group(1)), int(m.group(2))
        ano = int(m.group(3)) if m.group(3) else current_year
        if ano < 100: ano += 2000
        try: found_dates.append(datetime(ano, mes, dia))
        except ValueError: pass

    for m in re.finditer(r'\b(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(\d{4}))?\b', texto.lower()):
        dia = int(m.group(1))
        mes_str = m.group(2)
        ano = int(m.group(3)) if m.group(3) else current_year
        if mes_str in PT_MONTHS:
            try: found_dates.append(datetime(ano, PT_MONTHS[mes_str], dia))
            except ValueError: pass

    if found_dates: return max(found_dates) 
    return None

# --- FACEBOOK RSS INTEGRATION ---
@st.cache_data(ttl=3600)
def obter_avisos_facebook():
    rss_url = "https://rss.app/feeds/xF3kb9tGqqFDxAsF.xml"
    active_warnings = []
    
    agora_utc = datetime.now(timezone.utc)
    agora_local = datetime.now()

    try:
        response = requests.get(rss_url, timeout=10)
        soup = BeautifulSoup(response.content, "xml") 
        items = soup.find_all("item")
        
        for item in items[:15]: 
            title = item.find("title").text if item.find("title") else "Warning"
            content_encoded = item.find("content:encoded")
            desc = content_encoded.text if content_encoded else (item.find("description").text if item.find("description") else "")
            clean_text = BeautifulSoup(desc, "html.parser").get_text(separator=" ").strip()
            
            enclosure = item.find("enclosure")
            img_url = enclosure.get("url") if enclosure and enclosure.get("url") else ""
            if not img_url and desc:
                img_match = re.search(r'src="([^"]+)"', desc)
                if img_match: img_url = img_match.group(1)
            
            texto_minusculas = clean_text.lower() + " " + title.lower()
            
            if any(palavra in texto_minusculas for palavra in ["resolvido", "terminado", "já passou", "reaberto"]):
                continue

            data_fim_texto = extrair_data_futura(texto_minusculas)
            
            if data_fim_texto:
                if data_fim_texto < agora_local: continue
                prioridade_calculada = 30 
                
            else:
                pub_date_node = item.find("pubDate")
                dias_passados = 0
                if pub_date_node:
                    try:
                        data_post = email.utils.parsedate_to_datetime(pub_date_node.text)
                        dias_passados = (agora_utc - data_post).days
                    except Exception: pass
                
                if dias_passados > 7: continue
                prioridade_calculada = 10 - dias_passados 
                
                palavras_criticas = ["obra", "obras", "trânsito", "greve", "corte", "condicionamento", "interrupção", "aviso", "urgente"]
                if any(kw in texto_minusculas for kw in palavras_criticas): prioridade_calculada += 20
            
            texto_final = clean_text if len(clean_text) > 5 else title
            active_warnings.append({"text": texto_final, "image": img_url, "priority": prioridade_calculada})
            
        active_warnings.sort(key=lambda x: x["priority"], reverse=True)
        return active_warnings[:4]
            
    except Exception as e:
        logging.error(f"RSS Native Error: {e}")
        
    return active_warnings

def renderizar_rodape_anuncios(active_ads, ui):
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
        .disclaimer {{ background: #2a2a2a; color: #eee; font-size: 13px; padding: 6px 20px; text-align: center; font-weight: bold; border-bottom: 1px solid #444; }}
        .content-area {{ display: flex; align-items: center; flex: 1; padding: 0 20px; }}
        .img-box {{ flex: 0 0 120px; display: flex; align-items: center; justify-content: center; }}
        #ticker-img {{ max-height: 90px; border-radius: 6px; cursor: pointer; border: 2px solid #555; }}
        .text-container {{ flex: 1; overflow: hidden; position: relative; height: 100px; }}
        #ticker-text {{ position: absolute; white-space: nowrap; font-size: 20px; font-weight: bold; top: 35px; left: 50%; }}
    </style>
    
    <div class="footer-wrapper">
        <div class="disclaimer">{ui['ad_disclaimer']}</div>
        <div class="content-area">
            <div class="img-box"><img id="ticker-img" src="" onclick="window.open(this.src, '_blank');"></div>
            <div class="text-container"><div id="ticker-text"></div></div>
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
                img.src = a.image; img.style.display = "block"; img.style.visibility = "visible";
            }} else {{ img.style.display = "none"; }}
            
            txt.style.animation = 'none'; txt.offsetHeight; txt.style.animation = 'scroll-left 25s linear infinite';
            
            let pos = container.offsetWidth / 2;
            txt.style.left = pos + "px";
            
            function animate() {{
                pos -= 2; txt.style.left = pos + "px";
                if (pos < -txt.offsetWidth) {{ index = (index + 1) % ads.length; setTimeout(runTicker, 2000); }} 
                else {{ requestAnimationFrame(animate); }}
            }}
            animate();
        }}
        runTicker();
    </script>
    """
    components.html(footer_html, height=170)

# --- GEOGRAPHIC FUNCTIONS ---
def _normalizar_nome_paragem(texto: str):
    t = re.sub(r'\bsão\b', 's.', texto.lower().strip())
    t = re.sub(r'\bsanta\b', 'sta.', t)
    t = re.sub(r'\bsanto\b', 'sto.', t).replace('.', '')
    t = unicodedata.normalize('NFKD', t)
    return re.sub(r'\s+', ' ', ''.join(c for c in t if not unicodedata.combining(c))).strip()

def normalize_search_name(text):
    if not text: return ""
    t = text.lower().strip()
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return re.sub(r'_+', '_', re.sub(r'[^a-z0-9]', '_', t)).strip('_')

@st.cache_data
def load_static_map():
    try:
        with open("geo_guimaraes.json", "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return {}

LOCAL_MAP = load_static_map()

def calculate_distance(lat1, lon1, lat2, lon2):
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) * 1000 

def find_closest_stop(location_name: str):
    if not LOCAL_MAP: return "Static map is not loaded. Check the geo_guimaraes.json file."
    search_key = normalize_search_name(location_name)
    found_location = next((data for key, data in LOCAL_MAP.items() if search_key in key or key in search_key), None)
    if not found_location: return f"Could not locate '{location_name}' in the static map."

    lat_origin, lon_origin = found_location["lat"], found_location["lon"]
    closest_stop, shortest_dist = None, float('inf')

    for key, data in LOCAL_MAP.items():
        if data.get("type") in ["bus_stop", "public_transport"]:
            dist = calculate_distance(lat_origin, lon_origin, data["lat"], data["lon"])
            if dist < shortest_dist: shortest_dist, closest_stop = dist, data["nome_real"]

    if closest_stop: return f"The location '{found_location['nome_real']}' is {int(shortest_dist)} meters away from the '{closest_stop}' bus stop."
    return "Location found, but no bus stops in the vicinity."

def generate_google_maps_link(location_name: str):
    nome_norm = _normalizar_nome_paragem(location_name)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nome, latitude, longitude FROM nos_geograficos 
        WHERE _normalizar_nome_paragem(nome) LIKE ? LIMIT 1
    """, (f"%{nome_norm}%",))
    resultado = cursor.fetchone()
    conn.close()
    
    if resultado:
        nome_real, lat, lon = resultado
        link_maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        return f"📍 Encontrei a localização exata de '{nome_real}'. Podes abrir diretamente no Google Maps aqui: {link_maps}"
    
    return f"Não consegui encontrar coordenadas GPS em cache para '{location_name}'."

def consultar_base_geografica_tool(termo_pesquisa: str):
    """Procura na base de dados geográfica (JSON e SQLite) por locais, POIs, ruas ou paragens, devolvendo coordenadas e freguesia."""
    if not termo_pesquisa: return "É necessário indicar um termo de pesquisa."
    termo_norm = _normalizar_nome_paragem(termo_pesquisa)
    resultados = []
    
    if LOCAL_MAP:
        for chave, dados in LOCAL_MAP.items():
            if termo_norm in chave or chave in termo_norm:
                resultados.append(f"[JSON] {dados.get('nome_real', chave)} (Tipo: {dados.get('tipo', 'poi')}) - Lat: {dados['lat']}, Lon: {dados['lon']}")
    try:
        conn = get_db_connection()
        db_data = conn.execute("SELECT tipo, nome, freguesia, latitude, longitude FROM nos_geograficos").fetchall()
        conn.close()
        for r in db_data:
            nome_bd_norm = _normalizar_nome_paragem(r[1]) if r[1] else ""
            if termo_norm in nome_bd_norm or nome_bd_norm in termo_norm:
                freg = f" (Freguesia: {r[2]})" if r[2] else ""
                resultados.append(f"[SQLite] {r[1]}{freg} (Tipo: {r[0]}) - Lat: {r[3]}, Lon: {r[4]}")
    except Exception as e:
        pass
    
    if resultados:
        return f"Encontrei {len(resultados)} locais para '{termo_pesquisa}':\n" + "\n".join(resultados[:20])
    return f"Não encontrei '{termo_pesquisa}' no JSON nem na base de dados local."

def generate_line_map_html(linha_id):
    os.makedirs("maps", exist_ok=True)
    conn = get_db_connection()
    line_stops = [row[0] for row in conn.execute("SELECT stop FROM stop_line_cache WHERE line = ? OR line = ?", (linha_id, str(linha_id).zfill(3))).fetchall()]
    conn.close()
    
    if not line_stops: return "No cached stops for this line."
    
    route_coordinates, stops_with_coords = [], []
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
        folium.Marker(location=[p["lat"], p["lon"]], popup=folium.Popup(f"<b>Stop:</b> {p['name']}<br><b>Line:</b> {linha_id}", max_width=300), icon=folium.Icon(color="green", icon="bus", prefix="fa")).add_to(map_obj)
        
    if len(route_coordinates) > 1: folium.PolyLine(route_coordinates, color="blue", weight=3, opacity=0.7).add_to(map_obj)
        
    file_path = f"maps/linha_{linha_id}.html"
    map_obj.save(file_path)
    return file_path

# --- CONTEXT TOOLS ---
def _extrair_lista_veiculos(dados):
    if isinstance(dados, list): return dados
    if isinstance(dados, dict):
        for key in ("vehicles", "data", "results", "items", "veiculos"):
            if isinstance(data.get(key), list): return data.get(key)
        for val in data.values():
            if isinstance(val, list): return val
    return []

def _primeiro_valor(dicionario, chaves, default=None):
    for chave in chaves:
        if isinstance(dicionario, dict) and chave in dicionario and dicionario[chave] is not None:
            return dicionario[chave]
    return default

DICIONARIO_PARAGENS_CONHECIDAS = {"vaca negra": "1103", "central": "1001", "hospital": "1045", "universidade": "1022", "estacao": "1005"}

@st.cache_data(ttl=60)
def obter_dados_guimabus(route_id: str = None):
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    params = {"passengerInfo": "true"}
    if route_id: params["routeId"] = route_id
    try:
        response = requests.get("https://gmr.elevensystems.pt/api/locations", headers=headers, params=params, timeout=8)
        response.raise_for_status()
        try: data = response.json()
        except ValueError: return "Unable to read Guimabus data."
        vehicles = _extrair_lista_veiculos(data)
        if not vehicles: return f"There are currently no buses in circulation."

        total_delay, delayed_count, summary = 0, 0, "Real-time fleet data (Guimabus):\n"
        for bus in vehicles:
            bus_id = _primeiro_valor(bus, ["id", "vehicleId", "vehicle_id", "code"], "N/A")
            line = _first_value(bus, ["line", "lineName", "route", "routeShortName", "routeId"], None)
            status = _first_value(bus, ["busStatus", "status", "state"], "N/A")
            delay = _first_value(bus, ["delay", "delayMinutes", "delay_min"], None)

            line_txt = f" (Line {line})" if line else ""
            delay_txt = f"{delay}min" if delay is not None else "unknown"
            summary += f"- Bus {bus_id}{line_txt}: Status {status} (Delay: {delay_txt})\n"

            if isinstance(delay, (int, float)):
                total_delay += delay
                delayed_count += 1

        if delayed_count > 0: summary += f"\n--- Statistic: Average fleet delay: {total_delay / delayed_count:.1f} minutes. ---"
        return summary
    except Exception as e: return f"Tracking connection error: {e}"

@st.cache_data(ttl=30)
def obter_horarios_paragem(stop_id: str):
    if not stop_id: return "Stop ID is required."
    source_text = str(stop_id).strip().lower()
    numeric_id = next((id_p for name_p, id_p in DICIONARIO_PARAGENS_CONHECIDAS.items() if name_p in source_text), None)
            
    if numeric_id or source_text.isdigit():
        target_id = numeric_id if numeric_id else source_text
        try:
            response = requests.get(f"https://gmr.elevensystems.pt/api/stops/{target_id}/routes", headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}, params={"shape": "true", "passengerInfo": "true"}, timeout=5)
            response.raise_for_status()
            routes = _extrair_lista_veiculos(response.json())
            if routes:
                summary = f"Real-time forecasts for stop {target_id}:\n"
                for route in routes:
                    line = _first_value(route, ["line", "lineName", "route", "routeShortName", "routeId"], "N/A")
                    dest = _first_value(route, ["destination", "headsign", "direction"], None)
                    eta = _first_value(route, ["eta", "etaMinutes", "waitTime", "waitingTime", "arrivalTime", "nextArrival"], None)
                    summary += f"- Line {line}{f' → {dest}' if dest else ''}: {f'{eta} min' if eta is not None else 'no forecast'}\n"
                return summary
        except Exception: pass

    try:
        search_terms = re.sub(r'\b(estou|na|no|em|paragem|para|ir|as|os|a|o|da|do|linhas|linha|central|guimaraes|guimarães|tenho|quais|quero)\b', '', source_text).split()
        if not search_terms: search_terms = [source_text]
        conn = get_db_connection()
        query_sql = f"SELECT linha, conteudo_txt FROM cache_horarios WHERE {' AND '.join(['conteudo_txt LIKE ?' for _ in search_terms])}"
        found_lines = conn.execute(query_sql, [f"%{term}%" for term in search_terms]).fetchall()
        conn.close()
        
        if found_lines:
            search_result = f"Scanned local schedule cache and identified lines referencing '{stop_id}':\n"
            for row in found_lines:
                relevant_snippet = [l for l in row[1].split("\n") if any(term in l.lower() for term in search_terms) or "página" in l.lower() or "tabela" in l.lower()]
                search_result += f"\n--- AUTOMATIC MAPPING DETECTED: LINE {row[0]} ---\n{chr(10).join(relevant_snippet[:25])}\n"
            return search_result
    except Exception: pass
    return f"Could not fetch information for location '{stop_id}'."

def sincronizar_todos_horarios_guimabus():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get("https://guimabus.pt/horarios-linhas/", headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        pdf_links, line_titles = {}, {}
        for link in soup.find_all('a', href=True):
            if ".pdf" in link['href'] and "horario" in link['href'].lower():
                match = re.search(r'linha-([a-z0-9]+)', link['href'].lower())
                if match and match.group(1).upper() not in pdf_links:
                    pdf_links[match.group(1).upper()] = link['href']
                    if link.get_text(strip=True): line_titles[match.group(1).upper()] = link.get_text(strip=True)
        
        if not pdf_links: return "No schedule PDF files found on the main page."
        
        conn = get_db_connection()
        processed_lines = []
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for line_id, pdf_url in pdf_links.items():
            for attempt in range(2):
                try:
                    pdf_resp = requests.get(pdf_url, headers=headers, timeout=20)
                    if pdf_resp.status_code != 200: time.sleep(1); continue
                    extracted_text = []
                    with pdfplumber.open(io.BytesIO(pdf_resp.content)) as pdf:
                        for idx, page in enumerate(pdf.pages):
                            page_text = page.extract_text(layout=True)
                            if page_text: extracted_text.append(f"[PAGE {idx+1}]\n{page_text}")
                            time.sleep(0.05) 
                    final_content = "\n\n".join(extracted_text) or "PDF is image-based or copy-protected."

                    conn.execute("INSERT OR REPLACE INTO cache_horarios (linha, url, conteudo_txt, last_updated) VALUES (?, ?, ?, ?)", (line_id, pdf_url, final_content, current_timestamp))
                    if line_id in line_titles:
                        conn.execute("INSERT OR REPLACE INTO cache_titulo_linha (linha, titulo, ultima_atualizacao) VALUES (?, ?, ?)", (line_id, line_titles[line_id], current_timestamp))
                    processed_lines.append(line_id)
                    break
                except Exception: time.sleep(1); continue
            time.sleep(0.2)
        conn.commit(); conn.close()
        return f"Sync completed: {len(processed_lines)}/{len(pdf_links)} PDFs downloaded!"
    except Exception as e: return f"Scraping failed: {e}"

def consultar_cache_horario_linha(line_id: str):
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
        result = next((conn.execute("SELECT conteudo_txt, url, last_updated FROM cache_horarios WHERE linha = ?", (c,)).fetchone() for c in candidates if conn.execute("SELECT conteudo_txt, url, last_updated FROM cache_horarios WHERE linha = ?", (c,)).fetchone()), None)
        conn.close()
        
        if result: return f"Cached Schedules for Line {line_id} (Updated on {result[2]}):\n\n{result[0]}{f'{chr(10)}{chr(10)}🔗 Official Link: {result[1]}' if result[1] else ''}"
        return f"No cached schedules for line {line_id}."
    except Exception as e: return f"SQLite read error: {e}"

def len_knowledge_base():
    return "".join(f"\n--- CONTENT FROM {os.path.basename(file)} ---\n{open(file, 'r', encoding='utf-8').read()}" for file in glob.glob("knowledge/*.md")) or "No extra documentation found."

def obter_idade_cache_horarios_dias():
    try:
        conn = get_db_connection()
        res = conn.execute("SELECT MAX(ultima_atualizacao) FROM cache_horarios").fetchone()
        conn.close()
        return (datetime.now() - datetime.strptime(res[0], "%Y-%m-%d %H:%M:%S")).days if res and res[0] else None
    except Exception: return None

def obter_idade_cache_titulos_dias():
    try:
        conn = get_db_connection()
        res = conn.execute("SELECT MAX(ultima_atualizacao) FROM cache_titulos").fetchone()
        conn.close()
        return (datetime.now() - datetime.strptime(res[0], "%Y-%m-%d %H:%M:%S")).days if res and res[0] else None
    except Exception: return None

def obter_contagem_indice_paragens():
    try:
        conn = get_db_connection()
        res = conn.execute("SELECT COUNT(*) FROM cache_paragens_linha").fetchone()
        conn.close()
        return res[0] if res else 0
    except Exception: return 0

# --- SISTEMA BLOQUEANTE DE SINCRONIZAÇÃO NO ARRANQUE ---
def verificar_necessidade_sync(limite_dias: int = 7):
    if st.session_state.get("sync_checked"): return False

    idade_horarios = obter_idade_cache_horarios_dias()
    idade_titulos = obter_idade_cache_titulos_dias()
    idx_count = obter_contagem_indice_paragens()

    needs_sch = idade_horarios is None or idade_horarios >= limite_dias
    needs_idx = idx_count == 0
    needs_tkt = idade_titulos is None or idade_titulos >= limite_dias
    needs_geo = False

    try:
        conn = get_db_connection()
        count_geo = conn.execute("SELECT COUNT(*) FROM nos_geograficos WHERE tipo LIKE 'poi_%'").fetchone()[0]
        needs_geo = (count_geo == 0)
        conn.close()
    except Exception:
        pass

    if needs_sch or needs_idx or needs_tkt or needs_geo:
        st.session_state.is_updating = True
        st.session_state.update_tasks = {"sch": needs_sch, "idx": needs_idx, "tkt": needs_tkt, "geo": needs_geo}
    else:
        st.session_state.is_updating = False

    st.session_state.sync_checked = True
    return st.session_state.is_updating

# --- SCRAPING DINÂMICO: TIPOLOGIAS DE PASSE E TARIFÁRIO ---
TIPOLOGIAS_PASSE_FALLBACK = {"Mensal": {"descricao": "Valid for the month. Unlimited trips.", "preco": "Consult tariff", "custo_cartao": "5€", "prazo": "18th", "documentos": ["ID Card"]}}

def sincronizar_titulos_guimabus():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get("https://guimabus.pt/titulos/", headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup.find_all(['nav', 'footer', 'form', 'script', 'style']): tag.decompose()
        full_text = soup.get_text(separator="\n")
        normalized_text = "\n".join([l.strip() for l in full_text.split("\n") if l.strip()])
        blocos = re.split(r'\nPASSE[.\s]*\n', "\n" + normalized_text)[1:]
        if not blocos: return "No ticket types found."

        conn = get_db_connection()
        cursor = conn.cursor()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for block in blocos:
            lines = block.split("\n")
            if not lines or not lines[0].strip(): continue
            type_name = lines[0].strip()
            
            price, card_cost, deadline = "Consult tariff table", "Not specified", "Deadline not specified on website."
            docs_list, description_lines = [], []
            parsing_mode = "desc"
            
            for line in lines[1:]:
                line_lower = line.lower()
                line_stripped = line.strip()
                
                if not line_stripped: continue
                    
                if "só podem ser" in line_lower or "até ao dia" in line_lower or ("carregamento" in line_lower and "mês" in line_lower):
                    deadline = line_stripped
                    parsing_mode = "deadline"
                    continue
                    
                if "preço:" in line_lower:
                    val = re.split(r'preço:', line, flags=re.IGNORECASE)[1].strip()
                    if val: price = val
                    parsing_mode = "price"
                    continue
                    
                if line_lower == "gratuito":
                    price = "Gratuito"
                    parsing_mode = "price"
                    continue
                    
                if "custo do cartão:" in line_lower:
                    val = re.split(r'custo do cartão:', line, flags=re.IGNORECASE)[1].strip()
                    if val: card_cost = val
                    parsing_mode = "card"
                    continue
                    
                if "documentos necessários:" in line_lower:
                    parsing_mode = "docs"
                    val = re.split(r'documentos necessários:', line, flags=re.IGNORECASE)[1].strip()
                    if val: docs_list.append(val)
                    continue
                    
                if parsing_mode == "desc": description_lines.append(line_stripped)
                elif parsing_mode == "docs": docs_list.append(line_stripped)
                elif parsing_mode == "deadline": deadline += " " + line_stripped
                elif parsing_mode == "price" and price in ["Consult tariff table", ""]:
                    price = line_stripped
                    parsing_mode = "done" 
                elif parsing_mode == "card" and card_cost in ["Not specified", ""]:
                    card_cost = line_stripped
                    parsing_mode = "done"

            description = " ".join(description_lines)
            if not docs_list: docs_list = ["ID Card / Identification Document"]

            cursor.execute("INSERT OR REPLACE INTO cache_titulos (tipologia, descricao, preco, custo_cartao, prazo, documentos_json, ultima_atualizacao) VALUES (?, ?, ?, ?, ?, ?, ?)", (type_name, description, price, card_cost, deadline, json.dumps(docs_list, ensure_ascii=False), ts))
            
        conn.commit()
        conn.close()
        return "Ticket sync complete."
    except Exception as e: return f"Failed to sync ticket types: {e}"

def sincronizar_tarifario_guimabus():
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
                if txt: extracted.append(f"[PÁGINA {idx+1}]\n{txt}")
                time.sleep(0.05) 
        final_content = "\n\n".join(extracted) or "Image-based PDF."
        
        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO cache_tarifario (id, url_pdf, conteudo_txt, ultima_atualizacao) VALUES (1, ?, ?, ?)", (pdf_url, final_content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); conn.close()
        return "Tariff sync complete."
    except Exception as e: return f"Failed to sync tariff: {e}"

def sincronizar_titulos_e_tarifario(): return f"{sincronizar_titulos_guimabus()}\n{sincronizar_tarifario_guimabus()}"

def _extrair_paragens_de_texto(texto: str):
    paragens = set()
    padrao = re.compile(r'^(?P<nome>.+?)\s+(?P<horarios>(?:-|\d{1,2}:\d{2})(?:\s+(?:-|\d{1,2}:\d{2})){2,})\s*$')
    for line in texto.split("\n"):
        line = line.strip()
        if not line or "|" in line or line.startswith("[PAGE") or line.startswith("[P"): continue
        m = padrao.match(line)
        if m and len(m.group("nome").strip(" -\t")) >= 3: paragens.add(m.group("nome").strip(" -\t"))
    return paragens

def construir_indice_paragens():
    try:
        conn = get_db_connection()
        cached_lines = conn.execute("SELECT linha, conteudo_txt FROM cache_horarios").fetchall()
        conn.execute("DELETE FROM cache_paragens_linha")
        count = 0
        for line_id, content in cached_lines:
            if not content: continue
            for stop in _extrair_paragens_de_texto(content):
                conn.execute("INSERT OR IGNORE INTO cache_paragens_linha (linha, paragem) VALUES (?, ?)", (line_id, stop))
                count += 1
        conn.commit(); conn.close()
        return f"Stop index rebuilt: {count} associations."
    except Exception as e: return f"Failed to build index: {e}"

def _procurar_linhas_por_titulo(termo_norm: str):
    try:
        conn = get_db_connection()
        all_titles = conn.execute("SELECT linha, titulo FROM cache_titulo_linha").fetchall()
        conn.close()
    except Exception: return set(), []
    
    found_lines, found_titles = set(), []
    for line_id, title in all_titles:
        if title and re.search(r'\b' + re.escape(termo_norm) + r'\b', _normalizar_nome_paragem(title)):
            found_lines.add(line_id); found_titles.append(f"Linha {line_id}: {title}")
    return found_lines, found_titles

def enriquecer_paragens_com_freguesia(progresso_callback=None):
    try:
        conn = get_db_connection()
        all_stops = [row[0] for row in conn.execute("SELECT DISTINCT paragem FROM cache_paragens_linha").fetchall()]
        already_done = {row[0] for row in conn.execute("SELECT paragem FROM cache_paragem_freguesia").fetchall()}
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
            conn.execute("INSERT OR REPLACE INTO cache_paragem_freguesia (paragem, freguesia, fonte, ultima_atualizacao) VALUES (?, ?, ?, ?)", (stop, parish, "nominatim" if parish else "no_result", ts))
            if progress_callback: progress_callback(idx + 1, len(pending), stop)
        except Exception: pass
        time.sleep(1.1)
    conn.commit(); conn.close()
    return "Enrichment completed."

def obter_freguesia_de_paragem(nome_paragem: str):
    try:
        conn = get_db_connection()
        all_data = conn.execute("SELECT paragem, freguesia FROM cache_paragem_freguesia WHERE freguesia IS NOT NULL").fetchall()
        conn.close()
    except Exception: return None

    norm_name = _normalizar_nome_paragem(nome_paragem)
    for stop, parish in all_data:
        stop_norm = _normalizar_nome_paragem(stop)
        if re.search(r'\b' + re.escape(norm_name) + r'\b', stop_norm) or re.search(r'\b' + re.escape(stop_norm) + r'\b', norm_name): return parish
    return None

def procurar_paragens_por_freguesia(nome_freguesia: str):
    try:
        conn = get_db_connection()
        all_data = conn.execute("SELECT paragem, freguesia FROM cache_paragem_freguesia WHERE freguesia IS NOT NULL").fetchall()
        conn.close()
    except Exception: return []
    norm_parish = _normalizar_nome_paragem(nome_freguesia)
    return [stop for stop, parish in all_data if re.search(r'\b' + re.escape(norm_parish) + r'\b', _normalizar_nome_paragem(parish))]

def planear_viagem_com_transbordo(origem: str, destino: str):
    if not origem or not destino: return "You must provide an origin stop and a destination stop."
    norm_orig, norm_dest = _normalizar_nome_paragem(origem), _normalizar_nome_paragem(destino)
    
    try:
        conn = get_db_connection()
        all_data = conn.execute("SELECT linha, paragem FROM cache_paragens_linha").fetchall()
        conn.close()
    except Exception: return "Error querying stop index."
    
    if not all_data: return "Index not built."

    orig_lines, dest_lines, line_stops_map = set(), set(), {}
    found_orig, found_dest = set(), set()
    for l_id, s in all_data:
        line_stops_map.setdefault(l_id, set()).add(s)
        s_norm = _normalizar_nome_paragem(s)
        if re.search(r'\b' + re.escape(norm_orig) + r'\b', s_norm): orig_lines.add(l_id); found_orig.add(s)
        if re.search(r'\b' + re.escape(norm_dest) + r'\b', s_norm): dest_lines.add(l_id); found_dest.add(s)

    warn_o_title = warn_d_title = False
    o_titles, d_titles = [], []
    if not orig_lines: orig_lines, o_titles = _search_lines_by_title(norm_orig); warn_o_title = bool(orig_lines)
    if not dest_lines: dest_lines, d_titles = _search_lines_by_title(norm_dest); warn_d_title = bool(dest_lines)

    if not orig_lines: return f"Could not find '{origem}'."
    if not dest_lines: return f"Could not find '{destino}'."

    warn_msg = ("\n⚠️ Title used for Origin." if warn_o_title else "") + ("\n⚠️ Title used for Dest." if warn_d_title else "")

    if orig_lines & dest_lines:
        return f"DIRECT line(s) between '{origem}' and '{destino}':\n" + "\n".join(f"- Line {l}" for l in (orig_lines & dest_lines)) + warn_msg

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

def consultar_freguesia_paragem_tool(nome: str):
    if not nome: return "Name required."
    parish = obter_freguesia_de_paragem(nome)
    if parish: return f"Stop '{nome}' is in {parish}."
    stops = procurar_paragens_por_freguesia(nome)
    if stops: return f"Stops in '{nome}': {', '.join(stops)}."
    return f"No info for '{nome}'."

def obter_tipologias_cache():
    try:
        conn = get_db_connection()
        rows = conn.execute("SELECT tipologia, descricao, preco, custo_cartao, prazo, documentos_json FROM cache_titulos ORDER BY tipologia").fetchall()
        last_updated = conn.execute("SELECT MAX(ultima_atualizacao) FROM cache_titulos").fetchone()[0]
        conn.close()
        if not rows: return TIPOLOGIAS_PASSE_FALLBACK, None
        
        result = {}
        for type_name, desc, price, card_cost, deadline, docs_json in rows:
            try: docs = json.loads(docs_json)
            except Exception: docs = [docs_json]
            result[type_name] = {"descricao": desc, "preco": price, "custo_cartao": card_cost, "prazo": deadline, "documentos": docs}
        return result, last_updated
    except Exception: return TIPOLOGIAS_PASSE_FALLBACK, None

def consultar_tarifario_cache():
    try:
        conn = get_db_connection()
        res = conn.execute("SELECT conteudo_txt, ultima_atualizacao FROM cache_tarifario WHERE id = 1").fetchone()
        conn.close()
        return f"Tariff (updated {res[1]}):\n\n{res[0]}" if res else "Not synchronized."
    except Exception as e: return str(e)

def consultar_tipologias_cache_tool():
    types, up = obter_tipologias_cache()
    if not types: return "No types."
    return f"Types ({up}):\n\n" + "\n".join(f"- **{n}**: {i['descricao']} Preço: {i['preco']}" for n, i in types.items())

def verificar_documentos_passe(tipologia: str, ficheiros_carregados: dict):
    current_types, _ = obter_tipologias_cache()
    info = current_types.get(tipologia, {"documentos": ["unspecified document"]})
    partes = [
        f"Review uploaded documents for a '{tipologia}' ticket.\nRequired: {', '.join(info['documentos'])}.\n"
        "State for EACH: 1. Type 2. Matches required? 3. Legible? Mention missing ones."
    ]
    for n, f in ficheiros_carregados.items():
        if f is None: continue
        partes.extend([f"\n--- Document: '{n}' ---", {"mime_type": f.type or "application/octet-stream", "data": f.getvalue()}])
    if len(partes) == 1: return "No documents uploaded."
    try:
        return genai.GenerativeModel("gemini-3.5-flash").generate_content(partes, request_options={"timeout": 40}).text
    except Exception as e: return f"Error: {e}"

def recomendar_tipologias_passe(respostas: dict, available_types: dict):
    c = []
    def _h(p): return next((n for n in available_types if p.lower() in n.lower()), None)
    if respostas.get("antigo_combatente") and _h("Antigo Combatente"): c.append(_h("Antigo Combatente"))
    if respostas.get("incapacidade_60") and _h("Mobilidade Condicionada"): c.append(_h("Mobilidade Condicionada"))
    if respostas.get("idade", 0) >= 65 and respostas.get("residente_gmr") and _h("65+"): c.append(_h("65+"))
    if respostas.get("estudante"):
        if respostas.get("nivel_estudo") == "superior":
            c.append(_h("Universitário Residente") if respostas.get("residente_gmr") else _h("Universitário Não Residente"))
        elif respostas.get("nivel_estudo") == "ate_18": c.append(_h("18+TP"))
        elif respostas.get("nivel_estudo") == "ate_23": c.append(_h("23+TP"))
    
    c = [x for x in c if x]
    if not c:
        if respostas.get("residente_gmr") and _h("CIM AVE 50% + 10% CMG"): c.append(_h("CIM AVE 50% + 10% CMG"))
        elif _h("Mensal") and not _h("CIM"): c.append(next(n for n in available_types if n.strip().lower() == "mensal"))
    return list(dict.fromkeys(c))

def renderizar_pedido_passe(ui):
    st.subheader(ui["ticket_title"])
    st.info(ui["ticket_warning"])

    TICKET_TYPES, last_update = obter_tipologias_cache()
    if last_update: st.caption(f"{ui['ticket_updated']} {last_update}")

    with st.expander(ui["ticket_wizard"], expanded=False):
        col1, col2 = st.columns(2)
        age = col1.number_input(ui["ticket_age"], min_value=0, max_value=120, value=25, step=1, key="wizard_idade")
        gmr_resident = col2.checkbox(ui["ticket_resident"], key="wizard_residente")

        student = st.checkbox(ui["ticket_student"], key="wizard_estudante")
        study_level = None
        if student:
            level_map = {"ate_18": ui["ticket_level_opt1"], "ate_23": ui["ticket_level_opt2"], "superior": ui["ticket_level_opt3"]}
            study_level = st.radio(ui["ticket_level"], options=list(level_map.keys()), format_func=lambda x: level_map[x], key="wizard_nivel")

        col3, col4 = st.columns(2)
        disability_60 = col3.checkbox(ui["ticket_disability"], key="wizard_incapacidade")
        veteran = col4.checkbox(ui["ticket_veteran"], key="wizard_combatente")

        col5, col6 = st.columns(2)
        early_retirement = col5.checkbox(ui["ticket_retirement"], key="wizard_reforma")
        uses_cp_pass = col6.checkbox(ui["ticket_cp"], key="wizard_cp")

        if st.button(ui["ticket_recommend_btn"], key="wizard_recomendar"):
            ans = {"idade": age, "residente_gmr": gmr_resident, "estudante": student, "nivel_estudo": study_level, "incapacidade_60": disability_60, "antigo_combatente": veteran, "reforma_antecipada": early_retirement, "usa_passe_cp": uses_cp_pass}
            rec = recomendar_tipologias_passe(ans, TICKET_TYPES)
            if rec: st.success(f"{ui['ticket_suitable']} **{' / '.join(rec)}**")
            else: st.warning(ui["ticket_default"])

    chosen_type = st.selectbox(ui["ticket_choose"], list(TICKET_TYPES.keys()))
    info = TICKET_TYPES[chosen_type]

    st.markdown(f"{ui['ticket_desc']} {info['descricao']}\n{ui['ticket_price']} {info['preco']} | {ui['ticket_card']} {info['custo_cartao']}\n{ui['ticket_deadline']} {info.get('prazo', '')}")
    st.markdown(ui["ticket_docs_req"])
    ficheiros = {}
    for i, doc_name in enumerate(info["documentos"]):
        ficheiros[doc_name] = st.file_uploader(f"📄 {doc_name}", type=["pdf", "png", "jpg", "jpeg"], key=f"upload_pass_{chosen_type}_{i}")

    if st.button(ui["ticket_verify_btn"], use_container_width=True):
        if not any(f is not None for f in ficheiros.values()): st.warning(ui["ticket_upload_warn"])
        else:
            with st.spinner(ui["ticket_analyzing"]):
                st.markdown(verificar_documentos_passe(chosen_type, ficheiros))

def renderizar_jogo(ui):
    json_scores = json.dumps(obter_top_10())
    html_jogo = f"""
    <div style="text-align:center; background-color:#111; padding:15px; border-radius:10px; font-family:sans-serif;">
        <h3 style="color:#2ecc71; margin-top:0; margin-bottom:10px;">{ui['game_title']}</h3>
        <canvas id="stage" width="650" height="360" style="border:2px solid #2ecc71; background-color:#000; display:block; margin:0 auto; touch-action:none;"></canvas>
        <div style="margin-top: 10px;">
            <button id="btnAction" onclick="toggleGame()" style="padding: 6px 15px; background:#2ecc71; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">{ui['game_play']}</button>
            <input type="text" id="nomeInput" placeholder="{ui['game_name']}" maxlength="10" style="display:none; padding: 5px; border-radius:4px; border:1px solid #2ecc71; background:#222; color:white; width:120px; margin-left:10px; vertical-align:middle; text-transform:uppercase;">
            <button id="btnGravar" onclick="gravarRecorde()" style="display:none; padding: 6px 15px; background:#f1c40f; color:black; border:none; border-radius:5px; font-weight:bold; cursor:pointer; margin-left:5px; vertical-align:middle;">{ui['game_save']}</button>
        </div>
        <div style="margin-top: 15px; display: inline-block; width: 100%; text-align: center;">
            <div style="margin-bottom: 5px;">
                <button data-dir="cima" style="padding: 12px 24px; background: #34495e; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 18px;">▲</button>
            </div>
            <div style="display: flex; justify-content: center; gap: 10px;">
                <button data-dir="esquerda" style="padding: 12px 24px; background: #34495e; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 18px;">◀</button>
                <button data-dir="baixo" style="padding: 12px 24px; background: #34495e; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 18px;">▼</button>
                <button data-dir="direita" style="padding: 12px 24px; background: #34495e; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 18px;">▶</button>
            </div>
        </div>
        <script>
            var canvas = document.getElementById('stage');
            var ctx = canvas.getContext('2d');
            var btnAction = document.getElementById('btnAction');
            var nomeInput = document.getElementById('nomeInput');
            var btnGravar = document.getElementById('btnGravar');
            
            var tnt = 20;
            var gameWidth = 400;
            var cols = gameWidth / tnt, rows = canvas.height / tnt;
            var snake, dx, dy, apple, score, velocidadeMs, proximaDirecao, gameInterval, gameStarted, gameOver;
            var leaderboard = {json_scores};

            function novaMaca() {{
                var pos;
                do {{ pos = {{x: Math.floor(Math.random() * cols) * tnt, y: Math.floor(Math.random() * rows) * tnt}}; }} 
                while (snake.some(function(s) {{ return s.x === pos.x && s.y === pos.y; }}));
                return pos;
            }}

            function estadoInicial() {{
                snake = [{{x:160, y:160}}, {{x:140, y:160}}, {{x:120, y:160}}];
                dx = tnt; dy = 0; proximaDirecao = null; score = 0; velocidadeMs = 180;
                apple = novaMaca(); gameOver = false;
                nomeInput.style.display = 'none'; btnGravar.style.display = 'none';
            }}
            estadoInicial();
            
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
                        ctx.textAlign = 'end'; ctx.fillText(leaderboard[k][1] + ' pas.', canvas.width - 15, yPos); ctx.textAlign = 'start';
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
                if (proximaDirecao) {{ if (proximaDirecao.dx !== -dx || proximaDirecao.dy !== -dy) {{ dx = proximaDirecao.dx; dy = proximaDirecao.dy; }} proximaDirecao = null; }}
                var head = {{x: snake[0].x + dx, y: snake[0].y + dy}};
                if (head.x < 0) head.x = gameWidth - tnt; else if (head.x >= gameWidth) head.x = 0;
                if (head.y < 0) head.y = canvas.height - tnt; else if (head.y >= canvas.height) head.y = 0;

                var vaiComer = (head.x === apple.x && head.y === apple.y);
                for (var i = 0; i < (vaiComer ? snake.length : snake.length-1); i++) {{ 
                    if (snake[i].x === head.x && snake[i].y === head.y) {{ triggerGameOver(); return; }} 
                }}
                snake.unshift(head);
                if (vaiComer) {{
                    score += 10;
                    if (score % 50 === 0 && velocidadeMs > 80) {{ velocidadeMs -= 10; clearInterval(gameInterval); gameInterval = setInterval(gameLoop, velocidadeMs); }}
                    apple = novaMaca();
                }} else {{ snake.pop(); }}
                drawScene();
            }}
            
            function toggleGame() {{
                if (gameOver) {{ resetGame(); return; }}
                if (!gameStarted) {{ gameStarted = true; btnAction.innerText = "{ui['game_pause']}"; gameInterval = setInterval(gameLoop, velocidadeMs); }} 
                else {{ gameStarted = false; btnAction.innerText = "{ui['game_play']}"; clearInterval(gameInterval); }}
            }}
            function triggerGameOver() {{
                gameOver = true; gameStarted = false; clearInterval(gameInterval); btnAction.innerText = "{ui['game_reset']}";
                if((score/10) > 0) {{ nomeInput.style.display = 'inline-block'; btnGravar.style.display = 'inline-block'; nomeInput.focus(); }}
                drawScene();
            }}
            function resetGame() {{ 
                estadoInicial(); gameOver = false; gameStarted = true;
                btnAction.innerText = "{ui['game_pause']}"; gameInterval = setInterval(gameLoop, velocidadeMs); drawScene();
            }}
            function gravarRecorde() {{
                var nome = nomeInput.value.trim().toUpperCase();
                if(!nome) {{ alert("{ui['game_alert']}"); return; }}
                btnGravar.disabled = true; btnGravar.innerText = "💾...";
                try {{
                    var url = new URL(window.parent.location.href);
                    url.searchParams.set("save_nome", nome);
                    url.searchParams.set("save_pontos", (score / 10));
                    window.parent.location.href = url.toString();
                }} catch(e) {{
                    alert("Erro de segurança ao tentar gravar o score.");
                }}
            }}
            function mudarDirecao(dir) {{
                if (!gameStarted || gameOver) return;
                if(dir === 'esquerda' && dx === 0) proximaDirecao = {{dx:-tnt, dy:0}};
                if(dir === 'cima' && dy === 0) proximaDirecao = {{dx:0, dy:-tnt}};
                if(dir === 'direita' && dx === 0) proximaDirecao = {{dx:tnt, dy:0}};
                if(dir === 'baixo' && dy === 0) proximaDirecao = {{dx:0, dy:tnt}};
            }}
            document.addEventListener('keydown', function(e) {{
                var map = {{37:'esquerda', 38:'cima', 39:'direita', 40:'baixo'}};
                if (map[e.keyCode]) {{ e.preventDefault(); mudarDirecao(map[e.keyCode]); }}
            }});
            document.querySelectorAll('button[data-dir]').forEach(function(btn) {{
                btn.addEventListener('click', function() {{ mudarDirecao(btn.getAttribute('data-dir')); }});
            }});
            drawScene();
        </script>
    </div>
    """
    return components.html(html_jogo, height=650)

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": ui["initial_msg"]}]

if len(st.session_state.messages) == 1 and st.session_state.messages[0]["role"] == "assistant":
    st.session_state.messages[0]["content"] = ui["initial_msg"]

if "jogo_ativo" not in st.session_state:
    st.session_state.jogo_ativo = False

with st.sidebar:
    st.header(ui["sidebar_panel"])
    if st.button(ui["clear_history"], use_container_width=True):
        st.session_state.messages = [{"role": "assistant", "content": ui["initial_msg"]}]
        st.session_state.jogo_ativo = False
        st.rerun()
    st.divider()

    st.subheader(ui["entertainment"])
    btn_game_text = ui["close_game"] if st.session_state.jogo_ativo else ui["open_game"]
    if st.button(btn_game_text, use_container_width=True):
        st.session_state.jogo_ativo = not st.session_state.jogo_ativo
        st.rerun()
    st.divider()

    st.subheader(ui["transport_tickets"])
    if "passe_ativo" not in st.session_state:
        st.session_state.passe_ativo = False
    btn_ticket_text = ui["close_ticket"] if st.session_state.passe_ativo else ui["request_ticket"]
    if st.button(btn_ticket_text, use_container_width=True):
        st.session_state.passe_ativo = not st.session_state.passe_ativo
        st.rerun()
    st.divider()
    
    st.sidebar.subheader(ui["developer"])
    st.sidebar.info(ui["dev_desc"])
    st.sidebar.divider()
    
    st.write(ui["status"])
    st.sidebar.divider()
    
    st.sidebar.subheader(ui["admin_area"])
    if "admin_autenticado" not in st.session_state:
        st.session_state.admin_autenticado = False

    if not st.session_state.admin_autenticado:
        with st.sidebar.expander(ui["login_admin"]):
            password_input = st.text_input(ui["admin_pass"], type="password", key="admin_pwd")
            if st.button(ui["login_btn"], key="admin_login_btn"):
                if password_input and password_input == st.secrets.get("ADMIN_PASSWORD", None):
                    st.session_state.admin_autenticado = True
                    st.rerun()
                else:
                    st.sidebar.error(ui["wrong_pass"])
    else:
        st.sidebar.success(ui["admin_active"])
        
        st.sidebar.subheader(ui["web_auto"])
        if st.sidebar.button(ui["sync_all"], use_container_width=True):
            with st.spinner(ui["robot_reading"]):
                st.sidebar.success(sincronizar_todos_horarios_guimabus())
                st.sidebar.success(construir_indice_paragens())

        if st.sidebar.button(ui["rebuild_index"], use_container_width=True):
            with st.spinner(ui["rebuild_index_spinner"]):
                st.sidebar.success(construir_indice_paragens())

        if st.sidebar.button(ui["discover_parish"], use_container_width=True):
            st.sidebar.caption(ui["ask_osm"])
            barra_progresso = st.sidebar.progress(0.0)
            texto_progresso = st.sidebar.empty()
            def _atualizar_progresso(atual, total, paragem_atual):
                barra_progresso.progress(atual / total)
                texto_progresso.caption(f"{atual}/{total}: {paragem_atual}")
            st.sidebar.success(enriquecer_paragens_com_freguesia(progresso_callback=_atualizar_progresso))

        if st.sidebar.button(ui["sync_tickets"], use_container_width=True):
            with st.spinner(ui["robot_reading_tickets"]):
                st.sidebar.success(sincronizar_titulos_e_tarifario())
                
        if st.sidebar.button(ui["logout_admin"], key="admin_logout_btn"):
            st.session_state.admin_autenticado = False
            st.rerun()

        st.sidebar.subheader(ui["telemetry_db"])
        if os.path.exists("agente_memoria.db"):
            with open("agente_memoria.db", "rb") as f:
                st.sidebar.download_button(ui["export_db"], f, "agente_memoria.db", "application/octet-stream", use_container_width=True)

        with st.sidebar.expander(ui["view_logs"]):
            if os.path.exists("auditoria_agente.log"):
                with open("auditoria_agente.log", "r", encoding="utf-8") as f:
                    for linha in f.readlines()[-10:]: st.caption(linha.strip())

        with st.sidebar.expander(ui["global_history"]):
            if os.path.exists("agente_memoria.db"):
                conn = get_db_connection()
                for r in reversed(conn.execute("SELECT timestamp, session_id, role, content FROM historico_global ORDER BY id DESC LIMIT 30").fetchall()):
                    hora_min = r[0].split(" ")[1] if " " in r[0] else r[0]
                    st.markdown(f"**{'🟢' if r[2]=='user' else '🤖'} [{hora_min}] {ui['visitor'] if r[2]=='user' else ui['agent']} ({r[1]}):** {r[3]}")
                    st.divider()
                conn.close()

if st.session_state.jogo_ativo:
    renderizar_jogo(ui)

if st.session_state.get("passe_ativo"):
    renderizar_pedido_passe(ui)

avisos_hoje = obter_avisos_facebook()
if avisos_hoje:
    renderizar_rodape_anuncios(avisos_hoje, ui)

for message in st.session_state.messages:
    avatar_tipo = "💼" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar_tipo):
        if message["role"] == "assistant" and "```html" in message["content"].lower():
            blocos = re.split(r'```[hH][tT][mM][lL]', message["content"])
            st.markdown(blocos[0], unsafe_allow_html=True)
            for bloco in blocos[1:]:
                if "```" in bloco:
                    codigo_html, resto_texto = bloco.split("```", 1)
                    components.html(codigo_html.strip(), height=450, scrolling=True)
                    st.markdown(resto_texto, unsafe_allow_html=True)
                else:
                    components.html(bloco.strip(), height=450, scrolling=True)
        else:
            st.markdown(message["content"])

is_updating = verificar_necessidade_sync(limite_dias=7)

if is_updating:
    st.error(ui["updating_system"], icon="⏳")
    
    with st.spinner(ui["robot_reading"]):
        tasks = st.session_state.update_tasks
        
        if tasks.get("sch"):
            sincronizar_todos_horarios_guimabus()
            construir_indice_paragens()
        elif tasks.get("idx"):
            construir_indice_paragens()
        
        if tasks.get("tkt"):
            sincronizar_titulos_e_tarifario()
            
        if tasks.get("geo"):
            importar_pois_guimaraes()
            
    st.session_state.is_updating = False
    st.rerun()

prompt_texto = st.chat_input(ui["chat_input"])
audio_file = st.audio_input(ui["speak"])

prompt = None
tipo_input = "Texto"

if "ultimo_audio_processado_id" not in st.session_state:
    st.session_state.ultimo_audio_processado_id = None

if prompt_texto:
    prompt = prompt_texto
elif audio_file:
    audio_id_atual = audio_file.file_id if hasattr(audio_file, "file_id") else audio_file.name

    if audio_id_atual != st.session_state.ultimo_audio_processado_id:
        st.session_state.ultimo_audio_processado_id = audio_id_atual
        tipo_input = "Áudio"
        with st.spinner(ui["processing_audio"]):
            try:
                audio_data = audio_file.read()
                model_transcrever = genai.GenerativeModel("gemini-3.5-flash")
                response_transcricao = model_transcrever.generate_content([
                    "Transcreve estritamente o áudio fornecido para texto, mantendo a pontuação correta e no idioma original. Não adiciones comentários extras.",
                    {"mime_type": "audio/wav", "data": audio_data}
                ])
                prompt = response_transcricao.text.strip()
            except Exception as e:
                st.error(f"{ui['audio_error']} {e}")

if prompt:
    guardar_mensagem_bd(st.session_state.session_id, "user", prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="💼"):
        with st.spinner(ui["processing_agent"]):
            try:
                contexto_base = len_knowledge_base()
                
                LANGUAGE_INSTRUCTION = "CRUCIAL LANGUAGE RULE: You MUST respond entirely in European Portuguese (pt-PT)." if st.session_state.language == "PT" else "CRUCIAL LANGUAGE RULE: You MUST respond entirely in English."

                SCHEDULE_INSTRUCTION = (
                    "MANDATÓRIO: Sempre que te pedirem horários ou linhas, tens de apresentar OBRIGATORIAMENTE as horas de partida/chegada do horário pedido lendo a cache da ferramenta `consultar_cache_horario_linha`. NUNCA mandes apenas o link sem mostrares o horário no texto. No final da tua resposta, tens OBRIGATORIAMENTE de colocar o link: 'Consulta o horário oficial aqui: [LINK DA LINHA]'." 
                    if st.session_state.language == "PT" else 
                    "MANDATORY: Whenever asked about schedules or lines, you MUST present the actual departure/arrival times by reading the cache from the `query_line_schedule_cache` tool. NEVER just send the link without showing the times in your text. At the very end of your response, you MUST include the link: 'Check the official schedule here: [LINE LINK]'."
                )

                VISUAL_CARD_INSTRUCTION = (
                    "NOVA REGRA DE UX (CARTÃO VISUAL): Se o utilizador pedir uma viagem com transbordo ou horários de mais que uma linha, apresenta a resposta normalmente mas, no final, PERGUNTA OBRIGATORIAMENTE: 'Queres que eu gere um cartão visual com o resumo desta viagem?'. "
                    "SE (e apenas se) o utilizador já tiver respondido 'sim' a essa pergunta, deves gerar OBRIGATORIAMENTE um bloco de código HTML contendo um cartão de embarque moderno, com CSS integrado elegante, cores da Guimabus (verde #2ecc71 e cinza escuro), cantos arredondados e ícones (usa emojis), detalhando a origem, transbordo, destino e as respetivas horas. "
                    "Envolve o código HTML OBRIGATORIAMENTE num bloco de código markdown (```html ... ```) para que o sistema o possa renderizar graficamente como uma imagem iterativa."
                    if st.session_state.language == "PT" else 
                    "NEW UX RULE (VISUAL CARD): If the user asks for a trip with a transfer or schedules for more than one line, present the response normally but, at the end, YOU MUST ASK: 'Do you want me to generate a visual card summarizing this trip?'. "
                    "IF (and only if) the user has answered 'yes' to that question, YOU MUST generate an HTML code block containing a modern boarding pass card, with elegant integrated CSS, Guimabus colors (green #2ecc71 and dark gray), rounded corners and icons (use emojis), detailing the origin, transfer, destination, and respective times. "
                    "You MUST wrap the HTML code in a markdown code block (```html ... ```) so the system can render it graphically."
                )

                PROMPT_EXECUTIVO = f"""Tu és o Assistente Executivo de Elite do Celso Ferreira.
                És um Agente focado em automação, suporte e infraestrutura IT.

                {LANGUAGE_INSTRUCTION}

                Tens estas ferramentas relacionadas com a frota local da Guimabus:
                - obter_dados_guimabus: estado em tempo real da frota.
                - obter_horarios_paragem: previsão de tempos de espera para uma paragem específica.
                - consultar_cache_horario_linha: consulta a cache local para ler os horários e tabelas fixas.
                - consultar_tipologias_cache_tool: lê as tipologias de passe.
                - consultar_tarifario_cache: lê a tabela tarifária completa.
                - planear_viagem_com_transbordo: dado o nome de uma paragem de origem e destino, diz se há linha direta ou sugere transbordo.
                - consultar_freguesia_paragem_tool: diz em que freguesia fica uma paragem.
                - gerar_link_google_maps: recebe o nome de um local e devolve um link direto do Google Maps.
                - consultar_base_geografica_tool: pesquisa na base de dados geográfica (JSON e SQLite) por qualquer local, Ponto de Interesse (POI), rua ou paragem, retornando as coordenadas e tipo.
                - find_closest_stop: descobre a paragem oficial de autocarro mais próxima de qualquer café, fábrica ou ponto de interesse.

                MANDATORY PLANNING LOGIC:
                1. If the location IS NOT A STOP (e.g., cafe, factory), use the "find_closest_stop" tool FIRST.
                2. Use "planear_viagem_com_transbordo" com os nomes exatos das paragens.
                3. {SCHEDULE_INSTRUCTION}
                4. {VISUAL_CARD_INSTRUCTION}

                TOOL CALLING EXECUTION RULE - CRITICAL:
                NEVER describe the steps you will take to search. NEVER try to calculate routes mentally or guess stops without the tools giving you that information. CALL THE TOOLS silently. Only write the final text after having the tools' response.

                ANTI-HALLUCINATION RULE — THE MOST IMPORTANT OF ALL:
                NEVER invent, estimate, or "fill in" data that the tools did not provide. ALWAYS use the information in "[CURRENT SYSTEM DATE AND TIME]". If the tool does not tell you how to go from X to Y, apologize and state clearly and honestly that you do not have that connection available in the database."""
                
                PROMPT_RECRUITER = """You are an expert IT Technical Recruiter interviewing Celso Ferreira for an IT role.
                Conduct the interview strictly in English. Ask one tough, deep technical or behavioral question at a time.
                Evaluate Celso's response professionally based on IT best practices and keep the interviewer persona realistic."""
                
                PROMPT_HELPDESK_TUTOR = f"""Tu és um Tutor Técnico de Helpdesk e Suporte de IT.
                O teu objetivo é atuar como uma fonte interminável de resolução de problemas de IT.
                
                {LANGUAGE_INSTRUCTION}

                Independentemente do problema de suporte, deves começar a tua resposta OBRIGATORIAMENTE com a seguinte frase padrão: 
                'O Celso faria desta maneira para resolver este problema de IT:' (if PT) ou 'Celso would solve this IT problem like this:' (if EN)."""

                prompt_normalizado = prompt.lower()
                gatilhos_helpdesk = ["problema", "helpdesk", "ticket", "avaria", "erro", "servidor", "computador", "rede", "suporte", "falha", "problem", "error", "server", "computer", "network", "support"]
                
                if "entrevista" in prompt_normalizado or "interview" in prompt_normalizado:
                    prompt_sistema_ativo = PROMPT_RECRUITER
                elif any(word in prompt_normalizado for word in gatilhos_helpdesk):
                    prompt_sistema_ativo = PROMPT_HELPDESK_TUTOR
                else:
                    prompt_sistema_ativo = PROMPT_EXECUTIVO

                historico_api = []
                for msg in st.session_state.messages[:-1]:
                    if msg["content"] not in [ui["initial_msg"], UI_TEXT["PT"]["initial_msg"], UI_TEXT["EN"]["initial_msg"]]:
                        role_api = "model" if msg["role"] == "assistant" else "user"
                        historico_api.append({"role": role_api, "parts": [msg["content"]]})
                
                agora = datetime.now(ZoneInfo("Europe/Lisbon"))
                contexto_data = f"[DATA E HORA ATUAL DO SISTEMA: {agora.strftime('%Y-%m-%d %H:%M')}.]"

                prompt_enriquecido = f"{contexto_data}\n\n{contexto_base}\n\nUser Prompt: {prompt}"
                agent_tools = [obter_dados_guimabus, obter_horarios_paragem, consultar_cache_horario_linha, consultar_tipologias_cache_tool, consultar_tarifario_cache, planear_viagem_com_transbordo, consultar_freguesia_paragem_tool, gerar_link_google_maps, gerar_mapa_linha_html, find_closest_stop, consultar_base_geografica_tool]
                
                candidatos_modelo = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]
                response = None
                ultimo_erro_modelo = None

                for nome_modelo in candidatos_modelo:
                    try:
                        model = genai.GenerativeModel(model_name=nome_modelo, system_instruction=prompt_sistema_ativo, tools=agent_tools)
                        chat = model.start_chat(history=historico_api, enable_automatic_function_calling=True)
                        response = chat.send_message(prompt_enriquecido, request_options={"timeout": 25})
                        break
                    except Exception as e:
                        ultimo_erro_modelo = e
                        continue

                if response is None:
                    if ultimo_erro_modelo is not None and "429" in str(ultimo_erro_modelo):
                        st.error(ui["api_limit"])
                    else:
                        st.error(ui["model_error"])
                    st.stop()

                full_response = response.text
                
                if "```html" in full_response.lower():
                    blocos = re.split(r'```[hH][tT][mM][lL]', full_response)
                    st.markdown(blocos[0], unsafe_allow_html=True)
                    for bloco in blocos[1:]:
                        if "```" in bloco:
                            codigo_html, resto_texto = bloco.split("```", 1)
                            components.html(codigo_html.strip(), height=450, scrolling=True)
                            st.markdown(resto_texto, unsafe_allow_html=True)
                        else:
                            components.html(bloco.strip(), height=450, scrolling=True)
                else:
                    st.markdown(full_response)
                
                guardar_mensagem_bd(st.session_state.session_id, "assistant", full_response)
                st.download_button(ui["download_txt"], full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"Erro detetado no pipeline do agente: {e}")
