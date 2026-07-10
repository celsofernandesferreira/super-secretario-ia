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
import math
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
def inicializar_bd():
    conn = sqlite3.connect("agente_memoria.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
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
            ultima_atualizacao TEXT
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
        conn = sqlite3.connect("agente_memoria.db")
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
        conn = sqlite3.connect("agente_memoria.db")
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
        conn = sqlite3.connect("agente_memoria.db")
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

# --- SISTEMA DE PESQUISA JSON & GEOLOCALIZAÇÃO RÁPIDA ---
def normalizar_nome_pesquisa(texto):
    if not texto: return ""
    t = texto.lower().strip()
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'[^a-z0-9]', '_', t)
    t = re.sub(r'_+', '_', t).strip('_')
    return t

@st.cache_data
def carregar_mapa_estatico():
    try:
        with open("geo_guimaraes.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Erro ao carregar geo_guimaraes.json: {e}")
        return {}

MAPA_LOCAL = carregar_mapa_estatico()

def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c * 1000

def encontrar_paragem_mais_proxima(local_nome: str):
    """Encontra a paragem de autocarro mais próxima de qualquer café, rua ou fábrica."""
    if not MAPA_LOCAL:
        return "O mapa estático não está carregado. Verifica o ficheiro geo_guimaraes.json."
    chave_pesquisa = normalizar_nome_pesquisa(local_nome)
    local_encontrado = None
    for chave, dados in MAPA_LOCAL.items():
        if chave_pesquisa in chave or chave in chave_pesquisa:
            local_encontrado = dados
            break
    if not local_encontrado:
        return f"Não consegui localizar '{local_nome}' no mapa estático de Guimarães."
    
    lat_origem = local_encontrado["lat"]
    lon_origem = local_encontrado["lon"]
    paragem_mais_proxima = None
    menor_distancia = float('inf')
    
    for chave, dados in MAPA_LOCAL.items():
        if dados.get("tipo") in ["bus_stop", "public_transport"]:
            dist = calcular_distancia(lat_origem, lon_origem, dados["lat"], dados["lon"])
            if dist < menor_distancia:
                menor_distancia = dist
                paragem_mais_proxima = dados["nome_real"]
                
    if paragem_mais_proxima:
        return f"O local '{local_encontrado['nome_real']}' fica a {int(menor_distancia)} metros da paragem de autocarro '{paragem_mais_proxima}'."
    else:
        return "Encontrei o local, mas não existem paragens de autocarro nas imediações."

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

# 5. Inicialização da API do Gemini
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    st.error("Erro: Chave API em falta nos Secrets do Streamlit.")
    logging.error("Falha ao inicializar a aplicação: Chave API ausente nos Secrets.")
    st.stop()

# --- INTEGRAÇÃO FACEBOOK RSS (AI DRIVEN) ---
@st.cache_data(ttl=3600)
def obter_avisos_facebook():
    url_rss = "https://rss.app/feeds/xF3kb9tGqqFDxAsF.xml"
    avisos_ativos = []
    agora = datetime.now(ZoneInfo("Europe/Lisbon"))
    data_hoje_str = agora.strftime("%d de %B de %Y")

    try:
        response = requests.get(url_rss, timeout=10)
        soup = BeautifulSoup(response.content, "xml") 
        itens = soup.find_all("item")
        posts = []
        
        for i, item in enumerate(itens[:10]):
            titulo = item.find("title").text if item.find("title") else "Aviso"
            content_encoded = item.find("content:encoded")
            desc = content_encoded.text if content_encoded else (item.find("description").text if item.find("description") else "")
            texto_limpo = BeautifulSoup(desc, "html.parser").get_text(separator=" ").strip()
            
            enclosure = item.find("enclosure")
            img_url = enclosure.get("url") if enclosure and enclosure.get("url") else ""
            if not img_url and desc:
                img_match = re.search(r'src="([^"]+)"', desc)
                if img_match:
                    img_url = img_match.group(1)
            
            posts.append({"id": i, "titulo": titulo, "texto": texto_limpo, "imagem": img_url})

        prompt = f"""
        Hoje é {data_hoje_str}. Analisa os posts abaixo.
        1. Identifica a data limite de cada aviso.
        2. Se a data limite já passou em relação a {data_hoje_str}, considera o aviso EXPIROU.
        3. Se o aviso é sobre obras/trânsito/greves, prioridade 5. Caso contrário, prioridade 1.
        4. Devolve APENAS um JSON: [ {{"id": 0, "prioridade": 5}}, ... ] (apenas os ATIVOS).
        Posts: {json.dumps(posts, ensure_ascii=False)}
        """
        model = genai.GenerativeModel("gemini-3.5-flash")
        resp = model.generate_content(prompt)
        match = re.search(r'\[(.*?)\]', resp.text, re.DOTALL)
        
        if match:
            resultado = json.loads("[" + match.group(1) + "]")
            for r in resultado:
                p = next((x for x in posts if x["id"] == r["id"]), None)
                if p:
                    avisos_ativos.append({"texto": p["texto"], "imagem": p["imagem"], "prioridade": r["prioridade"]})
            avisos_ativos.sort(key=lambda x: x["prioridade"], reverse=True)
            
    except Exception as e:
        logging.error(f"Erro RSS com AI: {e}")
    return avisos_ativos

def renderizar_rodape_anuncios(anuncios_ativos, ui):
    if not anuncios_ativos: return
    
    dados_js = json.dumps(anuncios_ativos)
    
    html_rodape = f"""
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
        <div class="disclaimer">
            {ui['ad_disclaimer']}
        </div>
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
        const anuncios = {dados_js};
        let indice = 0;
        const txt = document.getElementById('ticker-text');
        const img = document.getElementById('ticker-img');
        const container = document.querySelector('.text-container');

        async function correrAviso() {{
            const a = anuncios[indice];
            
            txt.innerText = "🚨 " + (a.texto || a.titulo || "{ui['ad_notice']}");
            
            if (a.imagem && a.imagem.trim() !== "") {{
                img.src = a.imagem;
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
            
            function animar() {{
                pos -= 2; 
                txt.style.left = pos + "px";
                if (pos < -txt.offsetWidth) {{
                    indice = (indice + 1) % anuncios.length;
                    setTimeout(correrAviso, 2000); 
                }} else {{
                    requestAnimationFrame(animar);
                }}
            }}
            animar();
        }}
        correrAviso();
    </script>
    """
    components.html(html_rodape, height=170)

# --- FUNÇÕES DE CONTEXTO / FERRAMENTAS (TOOLS) ---
def _extrair_lista_veiculos(dados):
    if isinstance(dados, list):
        return dados
    if isinstance(dados, dict):
        for chave in ("vehicles", "data", "results", "items", "veiculos"):
            valor = dados.get(chave)
            if isinstance(valor, list):
                return valor
        for valor in dados.values():
            if isinstance(valor, list):
                return valor
    return []

def _primeiro_valor(dicionario, chaves, default=None):
    for chave in chaves:
        if isinstance(dicionario, dict) and chave in dicionario and dicionario[chave] is not None:
            return dicionario[chave]
    return default

DICIONARIO_PARAGENS_CONHECIDAS = {
    "vaca negra": "1103",
    "central": "1001",
    "hospital": "1045",
    "universidade": "1022",
    "estacao": "1005"
}

@st.cache_data(ttl=60)
def obter_dados_guimabus(route_id: str = None):
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    url = "https://gmr.elevensystems.pt/api/locations"
    params = {"passengerInfo": "true"}
    if route_id:
        params["routeId"] = route_id

    try:
        response = requests.get(url, headers=headers, params=params, timeout=8)
        response.raise_for_status()

        try:
            dados = response.json()
        except ValueError:
            return "Não foi possível ler os dados da Guimabus (resposta em formato inesperado)."

        veiculos = _extrair_lista_veiculos(dados)
        if not veiculos:
            linha_txt = f" da linha {route_id}" if route_id else ""
            return f"Não há autocarros{linha_txt} em circulação neste momento."

        total_atraso = 0
        count_com_atraso = 0
        resumo = "Dados de frota em tempo real (Guimabus):\n"
        for bus in veiculos:
            id_bus = _primeiro_valor(bus, ["id", "vehicleId", "vehicle_id", "code"], "N/A")
            linha = _primeiro_valor(bus, ["line", "lineName", "route", "routeShortName", "routeId"], None)
            status = _primeiro_valor(bus, ["busStatus", "status", "state"], "N/A")
            atraso = _primeiro_valor(bus, ["delay", "delayMinutes", "delay_min"], None)

            linha_txt = f" (Linha {linha})" if linha else ""
            atraso_txt = f"{atraso}min" if atraso is not None else "desconhecido"
            resumo += f"- Autocarro {id_bus}{linha_txt}: Status {status} (Atraso: {atraso_txt})\n"

            if isinstance(atraso, (int, float)):
                total_atraso += atraso
                count_com_atraso += 1

        if count_com_atraso > 0:
            media = total_atraso / count_com_atraso
            resumo += f"\n--- Estatística: Atraso médio da frota: {media:.1f} minutos. ---"
        return resumo
    except Exception as e:
        return f"Erro na ligação ao tracking: {e}"

@st.cache_data(ttl=30)
def obter_horarios_paragem(stop_id: str):
    if not stop_id:
        return "É necessário indicar o ID da paragem."
    
    origem_texto = str(stop_id).strip().lower()
    id_numérico = None
    
    for nome_p, id_p in DICIONARIO_PARAGENS_CONHECIDAS.items():
        if nome_p in origem_texto:
            id_numérico = id_p
            break
            
    if id_numérico or origem_texto.isdigit():
        target_id = id_numérico if id_numérico else origem_texto
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        url = f"https://gmr.elevensystems.pt/api/stops/{target_id}/routes"
        params = {"shape": "true", "passengerInfo": "true"}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=5)
            response.raise_for_status()
            dados = response.json()
            rotas = _extrair_lista_veiculos(dados)
            if rotas:
                resumo = f"Horários/previsões em tempo real para a paragem {target_id}:\n"
                for rota in rotas:
                    linha = _primeiro_valor(rota, ["line", "lineName", "route", "routeShortName", "routeId"], "N/A")
                    destino = _primeiro_valor(rota, ["destination", "headsign", "direction"], None)
                    eta = _primeiro_valor(rota, ["eta", "etaMinutes", "waitTime", "waitingTime", "arrivalTime", "nextArrival"], None)
                    destino_txt = f" → {destino}" if destino else ""
                    eta_txt = f"{eta} min" if eta is not None else "sem previsão"
                    resumo += f"- Linha {linha}{destino_txt}: {eta_txt}\n"
                return resumo
        except Exception:
            pass

    try:
        termos_pesquisa = re.sub(r'\b(estou|na|no|em|paragem|para|ir|as|os|a|o|da|do|linhas|linha|central|guimaraes|guimarães|tenho|quais|quero)\b', '', origem_texto).split()
        if not termos_pesquisa:
            termos_pesquisa = [origem_texto]

        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        
        condicoes = " AND ".join(["conteudo_txt LIKE ?" for _ in termos_pesquisa])
        valores = [f"%{termo}%" for termo in termos_pesquisa]
        
        query_sql = f"SELECT linha, conteudo_txt FROM cache_horarios WHERE {condicoes}"
        cursor.execute(query_sql, valores)
        linhas_encontradas = cursor.fetchall()
        conn.close()
        
        if linhas_encontradas:
            resultado_busca = f"Varri a cache de horários local e identifiquei com sucesso as linhas que contêm referências a '{stop_id}':\n"
            for row in linhas_encontradas:
                num_linha = row[0]
                texto_completo = row[1]
                
                linhas_texto = texto_completo.split("\n")
                trecho_relevante = []
                for l in linhas_texto:
                    if any(termo in l.lower() for termo in termos_pesquisa) or "página" in l.lower() or "tabela" in l.lower():
                        trecho_relevante.append(l)
                
                contexto_linha = "\n".join(trecho_relevante[:25])
                resultado_busca += f"\n--- MAPEAMENTO AUTOMÁTICO DETETADO: LINHA {num_linha} ---\n{contexto_linha}\n"
            
            return resultado_busca
            
    except Exception as e_db:
        logging.error(f"Erro no varrimento avançado de texto em BD: {e_db}")

    return f"Não foi possível obter informação em tempo real nem encontrar registos em cache para a localização '{stop_id}'."

# --- FERRAMENTA: AUTOMAÇÃO INTEGRAL DE RASPAGEM DE PDFs ---
def sincronizar_todos_horarios_guimabus():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    url_principal = "https://guimabus.pt/horarios-linhas/"
    
    try:
        response = requests.get(url_principal, headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links_pdf = {}
        titulos_linha = {}
        for link in soup.find_all('a', href=True):
            href = link['href']
            if ".pdf" in href and "horario" in href.lower():
                match = re.search(r'linha-([a-z0-9]+)', href.lower())
                if match:
                    linha_id = match.group(1).upper()
                    if linha_id not in links_pdf:
                        links_pdf[linha_id] = href
                        texto_link = link.get_text(strip=True)
                        if texto_link:
                            titulos_linha[linha_id] = texto_link
        
        if not links_pdf:
            return "Nenhum ficheiro PDF de horários localizado na página principal."
        
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        
        linhas_processadas = []
        linhas_falhadas = []
        timestamp_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for linha_id, url_pdf in links_pdf.items():
            sucesso = False
            ultimo_erro = None
            for tentativa in range(2):
                try:
                    pdf_response = requests.get(url_pdf, headers=headers, timeout=20)
                    if pdf_response.status_code != 200:
                        ultimo_erro = f"HTTP {pdf_response.status_code}"
                        time.sleep(1)
                        continue

                    texto_extraido = []
                    with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
                        for idx, pagina in enumerate(pdf.pages):
                            texto_pag = pagina.extract_text(layout=True)
                            if texto_pag:
                                texto_extraido.append(f"[PÁGINA {idx+1}]\n{texto_pag}")

                    conteudo_final = "\n\n".join(texto_extraido)
                    if not conteudo_final.strip():
                        conteudo_final = "PDF em formato de imagem ou protegido contra leitura."

                    cursor.execute("""
                        INSERT OR REPLACE INTO cache_horarios (linha, url, conteudo_txt, ultima_atualizacao)
                        VALUES (?, ?, ?, ?)
                    """, (linha_id, url_pdf, conteudo_final, timestamp_atual))

                    if linha_id in titulos_linha:
                        cursor.execute("""
                            INSERT OR REPLACE INTO cache_titulo_linha (linha, titulo, ultima_atualizacao)
                            VALUES (?, ?, ?)
                        """, (linha_id, titulos_linha[linha_id], timestamp_atual))

                    linhas_processadas.append(linha_id)
                    sucesso = True
                    break
                except Exception as e:
                    ultimo_erro = str(e)
                    time.sleep(1)
                    continue

            if not sucesso:
                linhas_falhadas.append(linha_id)
                logging.error(f"Falha ao processar o PDF da linha {linha_id} após 2 tentativas: {ultimo_erro}")

            time.sleep(0.4)

        conn.commit()
        conn.close()
        
        msg_sucesso = f"Sincronização concluída: {len(linhas_processadas)}/{len(links_pdf)} PDFs descarregados e convertidos na BD local!"
        if linhas_falhadas:
            msg_sucesso += f" Falharam: {', '.join(linhas_falhadas)}."
        logging.info(msg_sucesso)
        return msg_sucesso
        
    except Exception as e:
        error_msg = f"Falha na automação de scraping dos PDFs: {e}"
        logging.error(error_msg)
        return error_msg

def consultar_cache_horario_linha(linha_id: str):
    try:
        entrada = str(linha_id).strip().upper()
        if not entrada:
            return "É necessário indicar o número da linha."

        candidatos = [entrada]
        if entrada.isdigit():
            sem_zeros = entrada.lstrip('0') or '0'
            if sem_zeros not in candidatos:
                candidatos.append(sem_zeros)
            com_tres_digitos = entrada.zfill(3)
            if com_tres_digitos not in candidatos:
                candidatos.append(com_tres_digitos)

        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        resultado = None
        for candidato in candidatos:
            cursor.execute("SELECT conteudo_txt, url, ultima_atualizacao FROM cache_horarios WHERE linha = ?", (candidato,))
            resultado = cursor.fetchone()
            if resultado:
                break
        conn.close()
        
        if resultado:
            conteudo_txt, url_pdf, ultima_atualizacao = resultado
            link_txt = f"\n\n🔗 Link oficial para confirmares: {url_pdf}" if url_pdf else ""
            return f"Horários em Cache para a Linha {linha_id} (Atualizado em {ultima_atualizacao}):\n\n{conteudo_txt}{link_txt}"
        return f"Não existem horários em cache para a linha {linha_id}. Peça ao administrador para rodar a Sincronização Geral."
    except Exception as e:
        return f"Erro na leitura da cache SQLite: {e}"

def len_knowledge_base():
    contexto = ""
    files = glob.glob("knowledge/*.md")
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            contexto += f"\n--- CONTEÚDO DE {os.path.basename(file)} ---\n{f.read()}"
    return contexto if contexto else "Sem documentação extra encontrada na Knowledge Base."

def obter_idade_cache_horarios_dias():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(ultima_atualizacao) FROM cache_horarios")
        resultado = cursor.fetchone()
        conn.close()
        if not resultado or not resultado[0]:
            return None
        ultima = datetime.strptime(resultado[0], "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - ultima).days
    except Exception as e:
        logging.error(f"Erro ao verificar idade da cache de horários: {e}")
        return None

def obter_idade_cache_titulos_dias():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(ultima_atualizacao) FROM cache_titulos")
        resultado = cursor.fetchone()
        conn.close()
        if not resultado or not resultado[0]:
            return None
        ultima = datetime.strptime(resultado[0], "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - ultima).days
    except Exception as e:
        logging.error(f"Erro ao verificar idade da cache de títulos: {e}")
        return None

def obter_contagem_indice_paragens():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cache_paragens_linha")
        resultado = cursor.fetchone()
        conn.close()
        return resultado[0] if resultado else 0
    except Exception as e:
        logging.error(f"Erro ao contar índice de paragens: {e}")
        return 0

# --- NOVAS FUNÇÕES GEOGRÁFICAS (OVERPASS, FOLIUM, MAPS) ---
def importar_pois_guimaraes():
    query = """
    [out:json][timeout:25];
    area["name"="Guimarães"]->.searchArea;
    (
      node["amenity"~"hospital|clinic|doctors|pharmacy|cafe|restaurant|school|university"](area.searchArea);
      node["tourism"~"museum|attraction|monument"](area.searchArea);
      node["shop"~"supermarket|mall|bakery"](area.searchArea);
    );
    out center;
    """
    url = "https://overpass-api.de/api/interpreter"
    try:
        response = requests.post(url, data={'data': query}, timeout=30)
        dados = response.json()
        
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        pois_guardados = 0
        for elemento in dados.get('elements', []):
            tags = elemento.get('tags', {})
            nome_poi = tags.get('name')
            tipo_poi = tags.get('amenity', tags.get('tourism', tags.get('shop', 'poi')))
            
            if nome_poi and 'lat' in elemento and 'lon' in elemento:
                lat = elemento['lat']
                lon = elemento['lon']
                cursor.execute("""
                    INSERT OR IGNORE INTO nos_geograficos (tipo, nome, latitude, longitude, ultima_atualizacao)
                    VALUES (?, ?, ?, ?, ?)
                """, (f"poi_{tipo_poi}", nome_poi, lat, lon, timestamp))
                pois_guardados += 1
                
        conn.commit()
        conn.close()
        return f"Sucesso: {pois_guardados} Pontos de Interesse (Hospitais, Cafés, etc.) guardados na BD local!"
    except Exception as e:
        return f"Erro na extração de POIs: {e}"

def importar_ruas_freguesia(nome_freguesia):
    url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:25];
    area["name"="Guimarães"]->.searchArea;
    area["name"="{nome_freguesia}"]->.freguesiaArea;
    way["highway"](area.searchArea)(area.freguesiaArea);
    out tags center;
    """
    try:
        response = requests.post(url, data={'data': query}, timeout=30)
        dados = response.json()
        
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        ruas_guardadas = set()
        for elemento in dados.get('elements', []):
            tags = elemento.get('tags', {})
            nome_rua = tags.get('name')
            if nome_rua and 'center' in elemento:
                lat = elemento['center']['lat']
                lon = elemento['center']['lon']
                if nome_rua not in ruas_guardadas:
                    cursor.execute("""
                        INSERT OR IGNORE INTO nos_geograficos (tipo, nome, freguesia, latitude, longitude, ultima_atualizacao)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, ("rua", nome_rua, nome_freguesia, lat, lon, timestamp))
                    ruas_guardadas.add(nome_rua)
                    
        conn.commit()
        conn.close()
        return f"Sucesso: {len(ruas_guardadas)} ruas importadas para {nome_freguesia}."
    except Exception as e:
        return f"Erro na extração Overpass: {e}"

def gerar_mapa_linha_html(linha_id):
    os.makedirs("maps", exist_ok=True)
    conn = sqlite3.connect("agente_memoria.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.paragem, g.latitude, g.longitude, g.freguesia 
        FROM cache_paragens_linha p
        JOIN nos_geograficos g ON _normalizar_nome_paragem(p.paragem) = _normalizar_nome_paragem(g.nome)
        WHERE p.linha = ? AND g.latitude IS NOT NULL
    """, (linha_id,))
    paragens = cursor.fetchall()
    conn.close()
    
    if not paragens:
        return "Sem dados geográficos suficientes para esta linha."
    
    mapa = folium.Map(location=[paragens[0][1], paragens[0][2]], zoom_start=13, tiles="OpenStreetMap")
    coordenadas_rota = []
    
    for nome, lat, lon, freguesia in paragens:
        coordenadas_rota.append([lat, lon])
        popup_text = f"<b>Paragem:</b> {nome}<br><b>Freguesia:</b> {freguesia}<br><b>Linha:</b> {linha_id}"
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_text, max_width=300),
            icon=folium.Icon(color="green", icon="bus", prefix="fa")
        ).add_to(mapa)
    
    if len(coordenadas_rota) > 1:
        folium.PolyLine(coordenadas_rota, color="blue", weight=3, opacity=0.7).add_to(mapa)
    
    caminho_ficheiro = f"maps/linha_{linha_id}.html"
    mapa.save(caminho_ficheiro)
    return caminho_ficheiro

def gerar_link_google_maps(local_nome: str):
    chave_pesquisa = normalizar_nome_pesquisa(local_nome)
    
    if MAPA_LOCAL:
        for chave_mapa, dados_local in MAPA_LOCAL.items():
            if chave_pesquisa in chave_mapa or chave_mapa in chave_pesquisa:
                nome_real = dados_local["nome_real"]
                lat = dados_local["lat"]
                lon = dados_local["lon"]
                link_maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
                return f"📍 Encontrei a localização exata de '{nome_real}'. Podes abrir no Google Maps aqui: {link_maps}"
    
    nome_norm = _normalizar_nome_paragem(local_nome)
    conn = sqlite3.connect("agente_memoria.db")
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
    
    return f"Não consegui encontrar coordenadas GPS em cache para '{local_nome}'."

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
        conn = sqlite3.connect("agente_memoria.db")
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
TIPOLOGIAS_PASSE_FALLBACK = {
    "Mensal": {
        "descricao": "Válido para o mês e Origem/Destino para o qual foi adquirido, com nº de viagens ilimitado.",
        "preco": "Consultar tabela tarifária",
        "custo_cartao": "5€",
        "prazo": "Só pode ser emitido ou carregado até ao dia 18 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de identificação"],
    },
}

def sincronizar_titulos_guimabus():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    url = "https://guimabus.pt/titulos/"

    try:
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        for tag in soup.find_all(['nav', 'footer', 'form', 'script', 'style']):
            tag.decompose()

        texto_completo = soup.get_text(separator="\n")
        linhas_texto = [l.strip() for l in texto_completo.split("\n")]
        linhas_texto = [l for l in linhas_texto if l]
        texto_normalizado = "\n".join(linhas_texto)

        blocos = re.split(r'\nPASSE\n', "\n" + texto_normalizado)
        blocos = [b for b in blocos[1:]]

        if not blocos:
            return "Não foi possível identificar nenhuma tipologia de passe na página."

        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        timestamp_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tipologias_processadas = []

        for bloco in blocos:
            linhas_bloco = bloco.split("\n")
            if not linhas_bloco: continue
            nome_tipologia = linhas_bloco[0].strip()
            if not nome_tipologia: continue

            preco, custo_cartao, prazo = "Consultar tabela tarifária", "Não indicado", "Prazo não indicado na página."
            documentos, description_lines = [], []
            parsing_mode = "desc"

            for linha in linhas_bloco[1:]:
                linha_lower = linha.lower()
                linha_stripped = linha.strip()

                if not linha_stripped: continue

                if "só podem ser" in linha_lower or "até ao dia" in linha_lower or ("carregamento" in linha_lower and "mês" in linha_lower):
                    prazo = linha_stripped
                    parsing_mode = "prazo"
                    continue

                if "preço:" in linha_lower:
                    val = re.split(r'preço:', linha, flags=re.IGNORECASE)[1].strip()
                    if val: preco = val
                    parsing_mode = "preco"
                    continue

                if linha_lower == "gratuito":
                    preco = "Gratuito"
                    parsing_mode = "preco"
                    continue

                if "custo do cartão:" in linha_lower:
                    val = re.split(r'custo do cartão:', linha, flags=re.IGNORECASE)[1].strip()
                    if val: custo_cartao = val
                    parsing_mode = "cartao"
                    continue

                if "documentos necessários:" in linha_lower:
                    parsing_mode = "docs"
                    val = re.split(r'documentos necessários:', linha, flags=re.IGNORECASE)[1].strip()
                    if val: documentos.append(val)
                    continue

                if parsing_mode == "desc":
                    description_lines.append(linha_stripped)
                elif parsing_mode == "docs":
                    documentos.append(linha_stripped)
                elif parsing_mode == "prazo":
                    prazo += " " + linha_stripped
                elif parsing_mode == "preco" and preco in ["Consultar tabela tarifária", ""]:
                    preco = linha_stripped
                    parsing_mode = "done"
                elif parsing_mode == "cartao" and custo_cartao in ["Não indicado", ""]:
                    custo_cartao = linha_stripped
                    parsing_mode = "done"

            descricao = " ".join(description_lines)
            if not documentos:
                documentos = ["Cartão de Cidadão / Documento de Identificação"]

            cursor.execute("""
                INSERT OR REPLACE INTO cache_titulos (tipologia, descricao, preco, custo_cartao, prazo, documentos_json, ultima_atualizacao)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (nome_tipologia, descricao, preco, custo_cartao, prazo, json.dumps(documentos, ensure_ascii=False), timestamp_atual))
            tipologias_processadas.append(nome_tipologia)

        conn.commit()
        conn.close()
        return f"Sincronização de títulos concluída: {len(tipologias_processadas)} tipologias encontradas."
    except Exception as e:
        return f"Falha ao sincronizar títulos de passe: {e}"

def sincronizar_tarifario_guimabus():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    url_pagina = "https://guimabus.pt/tarifarios/"

    try:
        response = requests.get(url_pagina, headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        url_pdf = None
        for link in soup.find_all('a', href=True):
            href = link['href']
            if ".pdf" in href.lower() and ("tarifa" in href.lower() or "tabela" in href.lower()):
                url_pdf = href
                break
        if not url_pdf:
            for link in soup.find_all('a', href=True):
                if ".pdf" in link['href'].lower():
                    url_pdf = link['href']
                    break

        if not url_pdf:
            return "Não foi encontrado nenhum PDF de tarifário na página."

        pdf_response = requests.get(url_pdf, headers=headers, timeout=20)
        pdf_response.raise_for_status()

        texto_extraido = []
        with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
            for idx, pagina in enumerate(pdf.pages):
                texto_pag = pagina.extract_text(layout=True)
                if texto_pag:
                    texto_extraido.append(f"[PÁGINA {idx+1}]\n{texto_pag}")

        conteudo_final = "\n\n".join(texto_extraido)
        if not conteudo_final.strip():
            conteudo_final = "PDF em formato de imagem ou protegido contra leitura."

        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        timestamp_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT OR REPLACE INTO cache_tarifario (id, url_pdf, conteudo_txt, ultima_atualizacao)
            VALUES (1, ?, ?, ?)
        """, (url_pdf, conteudo_final, timestamp_atual))
        conn.commit()
        conn.close()

        return f"Sincronização do tarifário concluída (fonte: {url_pdf})."

    except Exception as e:
        return f"Falha ao sincronizar tarifário: {e}"

def sincronizar_titulos_e_tarifario():
    resultado_titulos = sincronizar_titulos_guimabus()
    resultado_tarifario = sincronizar_tarifario_guimabus()
    return f"{resultado_titulos}\n{resultado_tarifario}"

# --- ÍNDICE PARAGEM <-> LINHA (para sugerir transbordos) ---
def _extrair_paragens_de_texto(texto: str):
    paragens = set()
    padrao = re.compile(r'^(?P<nome>.+?)\s+(?P<horarios>(?:-|\d{1,2}:\d{2})(?:\s+(?:-|\d{1,2}:\d{2})){2,})\s*$')
    for linha_texto in texto.split("\n"):
        linha_texto = linha_texto.strip()
        if not linha_texto or "|" in linha_texto or linha_texto.startswith("[PÁGINA") or linha_texto.startswith("[P"):
            continue
        m = padrao.match(linha_texto)
        if m:
            nome = m.group("nome").strip(" -\t")
            if len(nome) >= 3:
                paragens.add(nome)
    return paragens

def construir_indice_paragens():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT linha, conteudo_txt FROM cache_horarios")
        linhas_cache = cursor.fetchall()

        cursor.execute("DELETE FROM cache_paragens_linha")
        total_paragens = 0
        for linha_id, conteudo_txt in linhas_cache:
            if not conteudo_txt:
                continue
            paragens = _extrair_paragens_de_texto(conteudo_txt)
            for paragem in paragens:
                cursor.execute(
                    "INSERT OR IGNORE INTO cache_paragens_linha (linha, paragem) VALUES (?, ?)",
                    (linha_id, paragem)
                )
                total_paragens += 1
        conn.commit()
        conn.close()
        return f"Índice de paragens reconstruído: {total_paragens} associações linha-paragem."
    except Exception as e:
        return f"Falha ao construir índice de paragens: {e}"

def _normalizar_nome_paragem(texto: str):
    t = texto.lower().strip()
    t = re.sub(r'\bsão\b', 's.', t)
    t = re.sub(r'\bsanta\b', 'sta.', t)
    t = re.sub(r'\bsanto\b', 'sto.', t)
    t = t.replace('.', '')
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def _procurar_linhas_por_titulo(termo_norm: str):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT linha, titulo FROM cache_titulo_linha")
        todos_titulos = cursor.fetchall()
        conn.close()
    except Exception as e:
        return set(), []

    linhas_encontradas = set()
    titulos_encontrados = []
    for linha_id, titulo in todos_titulos:
        if not titulo:
            continue
        titulo_norm = _normalizar_nome_paragem(titulo)
        if re.search(r'\b' + re.escape(termo_norm) + r'\b', titulo_norm):
            linhas_encontradas.add(linha_id)
            titulos_encontrados.append(f"Linha {linha_id}: {titulo}")
    return linhas_encontradas, titulos_encontrados

def enriquecer_paragens_com_freguesia(progresso_callback=None):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT paragem FROM cache_paragens_linha")
        todas_paragens = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT paragem FROM cache_paragem_freguesia")
        ja_feitas = {row[0] for row in cursor.fetchall()}
        conn.close()
    except Exception as e:
        return f"Erro ao preparar o enriquecimento: {e}"

    paragens_a_fazer = [p for p in todas_paragens if p not in ja_feitas]
    if not paragens_a_fazer:
        return "Todas as paragens já têm freguesia associada — nada a fazer."

    headers = {'User-Agent': 'SuperSecretarioIA-Guimaraes/1.0'}
    conn = sqlite3.connect("agente_memoria.db")
    cursor = conn.cursor()
    timestamp_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sucesso, falha = 0, 0

    for idx, paragem in enumerate(paragens_a_fazer):
        try:
            resp = requests.get("https://nominatim.openstreetmap.org/search", params={"q": f"{paragem}, Guimarães, Portugal", "format": "json", "addressdetails": 1, "countrycodes": "pt", "limit": 1}, headers=headers, timeout=10)
            resp.raise_for_status()
            resultados = resp.json()
            freguesia = None
            if resultados:
                endereco = resultados[0].get("address", {})
                freguesia = (endereco.get("suburb") or endereco.get("city_district") or endereco.get("village") or endereco.get("town") or endereco.get("municipality"))

            if freguesia:
                cursor.execute("INSERT OR REPLACE INTO cache_paragem_freguesia (paragem, freguesia, fonte, ultima_atualizacao) VALUES (?, ?, ?, ?)", (paragem, freguesia, "nominatim", timestamp_atual))
                sucesso += 1
            else:
                cursor.execute("INSERT OR REPLACE INTO cache_paragem_freguesia (paragem, freguesia, fonte, ultima_atualizacao) VALUES (?, ?, ?, ?)", (paragem, None, "sem_resultado", timestamp_atual))
                falha += 1

            if progresso_callback: progresso_callback(idx + 1, len(paragens_a_fazer), paragem)

        except Exception:
            falha += 1
        time.sleep(1.1)

    conn.commit()
    conn.close()
    return f"Enriquecimento de freguesias concluído: {sucesso} associadas, {falha} falhas."

def obter_freguesia_de_paragem(nome_paragem: str):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT paragem, freguesia FROM cache_paragem_freguesia WHERE freguesia IS NOT NULL")
        todas = cursor.fetchall()
        conn.close()
    except Exception:
        return None

    nome_norm = _normalizar_nome_paragem(nome_paragem)
    for paragem, freguesia in todas:
        paragem_norm = _normalizar_nome_paragem(paragem)
        if re.search(r'\b' + re.escape(nome_norm) + r'\b', paragem_norm) or re.search(r'\b' + re.escape(paragem_norm) + r'\b', nome_norm):
            return freguesia
    return None

def procurar_paragens_por_freguesia(nome_freguesia: str):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT paragem, freguesia FROM cache_paragem_freguesia WHERE freguesia IS NOT NULL")
        todas = cursor.fetchall()
        conn.close()
    except Exception:
        return []

    freguesia_norm = _normalizar_nome_paragem(nome_freguesia)
    return [paragem for paragem, freguesia in todas if re.search(r'\b' + re.escape(freguesia_norm) + r'\b', _normalizar_nome_paragem(freguesia))]

def planear_viagem_com_transbordo(origem: str, destino: str):
    if not origem or not destino: return "É necessário indicar a paragem de origem e a paragem de destino."
    origem_norm, destino_norm = _normalizar_nome_paragem(origem), _normalizar_nome_paragem(destino)

    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT linha, paragem FROM cache_paragens_linha")
        todas = cursor.fetchall()
        conn.close()
    except Exception as e:
        return f"Erro ao consultar o índice de paragens: {e}"

    if not todas: return "O índice de paragens ainda não foi construído."

    linhas_origem, linhas_destino = set(), set()
    paragens_origem_encontradas, paragens_destino_encontradas = set(), set()
    mapa_linha_paragens = {}

    for linha_id, paragem in todas:
        mapa_linha_paragens.setdefault(linha_id, set()).add(paragem)
        paragem_norm = _normalizar_nome_paragem(paragem)
        if re.search(r'\b' + re.escape(origem_norm) + r'\b', paragem_norm):
            linhas_origem.add(linha_id); paragens_origem_encontradas.add(paragem)
        if re.search(r'\b' + re.escape(destino_norm) + r'\b', paragem_norm):
            linhas_destino.add(linha_id); paragens_destino_encontradas.add(paragem)

    aviso_o, aviso_d = False, False
    if not linhas_origem: linhas_origem, titulos_o = _procurar_linhas_por_titulo(origem_norm); aviso_o = bool(linhas_origem)
    if not linhas_destino: linhas_destino, titulos_d = _procurar_linhas_por_titulo(destino_norm); aviso_d = bool(linhas_destino)

    aviso_o_freg, aviso_d_freg = None, None
    if not linhas_origem:
        paragens_da_freguesia = procurar_paragens_por_freguesia(origem)
        if paragens_da_freguesia:
            for paragem_freg in paragens_da_freguesia:
                for linha_id, paragem_indice in todas:
                    if _normalizar_nome_paragem(paragem_freg) == _normalizar_nome_paragem(paragem_indice):
                        linhas_origem.add(linha_id); paragens_origem_encontradas.add(paragem_indice)
            if linhas_origem: aviso_o_freg = paragens_da_freguesia

    if not linhas_destino:
        paragens_da_freguesia = procurar_paragens_por_freguesia(destino)
        if paragens_da_freguesia:
            for paragem_freg in paragens_da_freguesia:
                for linha_id, paragem_indice in todas:
                    if _normalizar_nome_paragem(paragem_freg) == _normalizar_nome_paragem(paragem_indice):
                        linhas_destino.add(linha_id); paragens_destino_encontradas.add(paragem_indice)
            if linhas_destino: aviso_d_freg = paragens_da_freguesia

    if not linhas_origem: return f"Não encontrei origem '{origem}'."
    if not linhas_destino: return f"Não encontrei destino '{destino}'."

    aviso_precisao = ""
    if aviso_o: aviso_precisao += f"\n⚠️ Nota: '{origem}' encontrada pelo TÍTULO da linha."
    if aviso_d: aviso_precisao += f"\n⚠️ Nota: '{destino}' encontrada pelo TÍTULO da linha."
    if aviso_o_freg: aviso_precisao += f"\n📍 '{origem}' é freguesia."
    if aviso_d_freg: aviso_precisao += f"\n📍 '{destino}' é freguesia."

    linhas_diretas = linhas_origem & linhas_destino
    if linhas_diretas:
        resumo = f"Encontrei linha(s) DIRETA(S) entre '{origem}' e '{destino}':\n"
        for l in linhas_diretas: resumo += f"- Linha {l}\n"
        return resumo + aviso_precisao

    stops_o, stops_d = set(), set()
    for l in linhas_origem: stops_o |= mapa_linha_paragens.get(l, set())
    for l in linhas_destino: stops_d |= mapa_linha_paragens.get(l, set())

    transbordos = (stops_o & stops_d) - paragens_origem_encontradas - paragens_destino_encontradas
    if not transbordos: return f"Não encontrei transbordo óbvio entre '{origem}' e '{destino}'."

    resumo = f"Não há linha direta. Sugestão de transbordo:\n\n"
    for t in sorted(transbordos):
        l_to = [l for l in linhas_origem if t in mapa_linha_paragens.get(l, set())]
        l_from = [l for l in linhas_destino if t in mapa_linha_paragens.get(l, set())]
        resumo += f"- Via **{t}**: apanha linha {'/'.join(l_to)} e depois linha {'/'.join(l_from)}.\n"

    return resumo + aviso_precisao

def consultar_freguesia_paragem_tool(nome: str):
    if not nome: return "É necessário indicar o nome."
    freguesia = obter_freguesia_de_paragem(nome)
    if freguesia: return f"A paragem '{nome}' fica na freguesia de {freguesia}."
    paragens = procurar_paragens_por_freguesia(nome)
    if paragens: return f"Paragens em '{nome}': {', '.join(paragens)}."
    return f"Não tenho informação para '{nome}'."

def obter_tipologias_cache():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT tipologia, descricao, preco, custo_cartao, prazo, documentos_json FROM cache_titulos ORDER BY tipologia")
        linhas = cursor.fetchall()
        cursor.execute("SELECT MAX(ultima_atualizacao) FROM cache_titulos")
        ultima_atualizacao = cursor.fetchone()[0]
        conn.close()

        if not linhas: return TIPOLOGIAS_PASSE_FALLBACK, None

        resultado = {}
        for tip, desc, preco, cartao, prazo, docs_json in linhas:
            try: docs = json.loads(docs_json)
            except: docs = [docs_json]
            resultado[tip] = {"descricao": desc, "preco": preco, "custo_cartao": cartao, "prazo": prazo, "documentos": docs}
        return resultado, ultima_atualizacao
    except Exception:
        return TIPOLOGIAS_PASSE_FALLBACK, None

def consultar_tarifario_cache():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT conteudo_txt, ultima_atualizacao FROM cache_tarifario WHERE id = 1")
        res = cursor.fetchone()
        conn.close()
        if res: return f"Tabela tarifária ({res[1]}):\n\n{res[0]}"
        return "Tarifário não sincronizado."
    except Exception as e: return f"Erro cache tarifário: {e}"

def consultar_tipologias_cache_tool():
    tipologias, upd = obter_tipologias_cache()
    if not tipologias: return "Sem tipologias em cache."
    resumo = f"Tipologias ({upd}):\n\n"
    for n, i in tipologias.items():
        resumo += f"- **{n}**: {i['descricao']} Preço: {i['preco']}. Prazo: {i['prazo']}.\n"
    return resumo

def verificar_documentos_passe(tipologia: str, ficheiros_carregados: dict):
    tipologias_atuais, _ = obter_tipologias_cache()
    info = tipologias_atuais.get(tipologia, {"documentos": ["não especificado"]})
    partes = [f"Rever docs para '{tipologia}'. Exigido: {', '.join(info['documentos'])}.\nPara cada doc: tipo, corresponde?, legível?"]

    nomes = []
    for nome, fich in ficheiros_carregados.items():
        if fich is None: continue
        nomes.append(nome)
        partes.extend([f"\n--- Documento: '{nome}' ---", {"mime_type": fich.type or "application/octet-stream", "data": fich.getvalue()}])

    if not nomes: return "Nenhum documento carregado."
    try: return genai.GenerativeModel("gemini-3.5-flash").generate_content(partes, request_options={"timeout": 40}).text
    except Exception as e: return f"Erro ao verificar: {e}"

def recomendar_tipologias_passe(respostas: dict, tipologias_disponiveis: dict):
    cand = []
    def _tem(n): return next((k for k in tipologias_disponiveis if n.lower() in k.lower()), None)

    if respostas.get("antigo_combatente") and _tem("Antigo Combatente"): cand.append(_tem("Antigo Combatente"))
    if respostas.get("incapacidade_60") and _tem("Mobilidade Condicionada"): cand.append(_tem("Mobilidade Condicionada"))
    if respostas.get("idade", 0) >= 65 and respostas.get("residente_gmr") and _tem("65+"): cand.append(_tem("65+"))
    if respostas.get("reforma_antecipada") and 60 <= respostas.get("idade", 0) < 65 and _tem("Reformado"): cand.append(_tem("Reformado"))
    if respostas.get("estudante"):
        if respostas.get("nivel_estudo") == "superior":
            cand.append(_tem("Universitário Residente") if respostas.get("residente_gmr") else _tem("Universitário Não Residente"))
        elif respostas.get("nivel_estudo") == "ate_18" and _tem("18+TP"): cand.append(_tem("18+TP"))
        elif respostas.get("nivel_estudo") == "ate_23" and _tem("23+TP"): cand.append(_tem("23+TP"))
    if respostas.get("usa_passe_cp") and _tem("Mensal CP"): cand.append(_tem("Mensal CP"))

    if not cand:
        if respostas.get("residente_gmr") and _tem("CIM AVE 50% + 10% CMG"): cand.append(_tem("CIM AVE 50% + 10% CMG"))
        elif respostas.get("residente_gmr") and _tem("CIM AVE 50%"): cand.append(_tem("CIM AVE 50%"))
        elif _tem("Mensal") and not _tem("CIM"):
            cand.append(next(n for n in tipologias_disponiveis if n.strip().lower() == "mensal"))

    return list(dict.fromkeys([c for c in cand if c]))

def renderizar_pedido_passe(ui):
    st.subheader(ui["ticket_title"])
    st.info(ui["ticket_warning"])

    TICKET_TYPES, last_update = obter_tipologias_cache()
    if last_update: st.caption(f"{ui['ticket_updated']} {last_update}")

    with st.expander(ui["ticket_wizard"], expanded=False):
        col1, col2 = st.columns(2)
        idade = col1.number_input(ui["ticket_age"], min_value=0, max_value=120, value=25, step=1, key="wizard_idade")
        residente_gmr = col2.checkbox(ui["ticket_resident"], key="wizard_residente")

        estudante = st.checkbox(ui["ticket_student"], key="wizard_estudante")
        nivel_estudo = None
        if estudante:
            level_map = {"ate_18": ui["ticket_level_opt1"], "ate_23": ui["ticket_level_opt2"], "superior": ui["ticket_level_opt3"]}
            nivel_estudo = st.radio(ui["ticket_level"], options=list(level_map.keys()), format_func=lambda x: level_map[x], key="wizard_nivel")

        col3, col4 = st.columns(2)
        incapacidade_60 = col3.checkbox(ui["ticket_disability"], key="wizard_incapacidade")
        antigo_combatente = col4.checkbox(ui["ticket_veteran"], key="wizard_combatente")

        col5, col6 = st.columns(2)
        reforma_antecipada = col5.checkbox(ui["ticket_retirement"], key="wizard_reforma")
        usa_passe_cp = col6.checkbox(ui["ticket_cp"], key="wizard_cp")

        if st.button(ui["ticket_recommend_btn"], key="wizard_recomendar"):
            ans = {"idade": idade, "residente_gmr": residente_gmr, "estudante": estudante, "nivel_estudo": nivel_estudo, "incapacidade_60": incapacidade_60, "antigo_combatente": antigo_combatente, "reforma_antecipada": reforma_antecipada, "usa_passe_cp": usa_passe_cp}
            rec = recomendar_tipologias_passe(ans, TICKET_TYPES)
            if rec: st.success(f"{ui['ticket_suitable']} **{' / '.join(rec)}**")
            else: st.warning(ui["ticket_default"])

    tipologia_escolhida = st.selectbox(ui["ticket_choose"], list(TICKET_TYPES.keys()))
    info = TICKET_TYPES[tipologia_escolhida]

    st.markdown(f"{ui['ticket_desc']} {info['descricao']}\n{ui['ticket_price']} {info['preco']} | {ui['ticket_card']} {info['custo_cartao']}\n{ui['ticket_deadline']} {info.get('prazo', '')}")
    st.markdown(ui["ticket_docs_req"])
    ficheiros = {}
    for i, doc_name in enumerate(info["documentos"]):
        ficheiros[doc_name] = st.file_uploader(f"📄 {doc_name}", type=["pdf", "png", "jpg", "jpeg"], key=f"upload_pass_{tipologia_escolhida}_{i}")

    if st.button(ui["ticket_verify_btn"], use_container_width=True):
        if not any(f is not None for f in ficheiros.values()): st.warning(ui["ticket_upload_warn"])
        else:
            with st.spinner(ui["ticket_analyzing"]):
                st.markdown(verificar_documentos_passe(tipologia_escolhida, ficheiros))

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

# --- INICIALIZAÇÃO DE ESTADOS ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": ui["initial_msg"]}]

if len(st.session_state.messages) == 1 and st.session_state.messages[0]["role"] == "assistant":
    st.session_state.messages[0]["content"] = ui["initial_msg"]

if "jogo_ativo" not in st.session_state:
    st.session_state.jogo_ativo = False

# --- SIDEBAR DE ELITE ---
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
    st.rerun() # Refresh força a libertação do input box abaixo.

with st.sidebar:
    st.header(ui["sidebar_panel"])
    if st.button(ui["clear_history"], use_container_width=True):
        st.session_state.messages = [{"role": "assistant", "content": ui["initial_msg"]}]
        st.session_state.jogo_ativo = False
        st.rerun()
    st.divider()

    st.subheader(ui["entertainment"])
    texto_botao_jogo = ui["close_game"] if st.session_state.jogo_ativo else ui["open_game"]
    if st.button(texto_botao_jogo, use_container_width=True):
        st.session_state.jogo_ativo = not st.session_state.jogo_ativo
        st.rerun()
    st.divider()

    st.subheader(ui["transport_tickets"])
    if "passe_ativo" not in st.session_state:
        st.session_state.passe_ativo = False
    texto_botao_passe = ui["close_ticket"] if st.session_state.passe_ativo else ui["request_ticket"]
    if st.button(texto_botao_passe, use_container_width=True):
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
                conn = sqlite3.connect("agente_memoria.db")
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
        st.markdown(message["content"])

# --- EXECUÇÃO BLOQUEANTE E RESILIENTE DE ATUALIZAÇÕES INICIAIS ---
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
    st.rerun() # Refresh força a libertação do input box abaixo.

# Input só é renderizado de facto depois da função de bloqueio estar livre
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
                    "MANDATÓRIO: Sempre que o utilizador perguntar como ir de um local para outro, ou pedir horários, tens OBRIGATORIAMENTE de apresentar as horas de partida/chegada lendo a cache da ferramenta `consultar_cache_horario_linha`. NUNCA mandes apenas as linhas ou os links sem mostrar os horários no texto. Após descobrires as linhas (seja rota direta ou transbordo), FAZ SEMPRE query aos horários dessas linhas. No final da resposta, coloca os links oficiais." 
                    if st.session_state.language == "PT" else 
                    "MANDATORY: Whenever asked for directions or schedules, you MUST present the departure/arrival times by using the `consultar_cache_horario_linha` tool for the suggested lines. NEVER just output the lines without schedules. Always query the schedules for the lines you find. At the end, include the official links."
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
                - encontrar_paragem_mais_proxima : procura a paragem mais proxima de uma freguesia ou local

                MANDATORY PLANNING LOGIC:
                1. Use "planear_viagem_com_transbordo" com os nomes exatos das paragens.
                2. {SCHEDULE_INSTRUCTION}
                3. - encontrar_paragem_mais_proxima: descobre a paragem oficial de autocarro mais próxima de qualquer café, fábrica ou ponto de interesse geográfico (baseado no JSON estático de distâncias).
                4. Se o utilizador pedir direções ou como ir para/de um local que NÃO É UMA PARAGEM (como um café, restaurante, loja ou fábrica), tu DEVES usar primeiro a ferramenta "encontrar_paragem_mais_proxima" para descobrir qual é a paragem da Guimabus que fica perto desse local.
                5. Nunca associar freguesias a paragens apenas as linhas
                6. Sempre que solicitar um horario fornecer todos os horarios para o dia indicado, caso nao indique nenhum dia, os horarios são do proprio dia
                7. Cada Freguesia tem varias paragens tens de procurar quais são depois indicas a paragem mais distante do Destino
                
                REGRA ANTI-ALUCINAÇÃO — A MAIS IMPORTANTE DE TODAS:
                NUNCA inventes, estimes ou "preenchas" dados que as ferramentas ou a Knowledge Base não te deram. NUNCA assumas ou inventes uma data a partir de memória. Se não encontrares a informação na base de dados, pede desculpa e diz de forma clara que a informação não se encontra disponível."""
                
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
                
                ferramentas_agente = [obter_dados_guimabus, obter_horarios_paragem, consultar_cache_horario_linha, consultar_tipologias_cache_tool, consultar_tarifario_cache, planear_viagem_com_transbordo, consultar_freguesia_paragem_tool, gerar_link_google_maps, encontrar_paragem_mais_proxima]
                
                candidatos_modelo = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]
                response = None
                ultimo_erro_modelo = None

                for nome_modelo in candidatos_modelo:
                    try:
                        model = genai.GenerativeModel(model_name=nome_modelo, system_instruction=prompt_sistema_ativo, tools=ferramentas_agente)
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
                st.markdown(full_response)
                
                guardar_mensagem_bd(st.session_state.session_id, "assistant", full_response)
                st.download_button(ui["download_txt"], full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"Erro detetado no pipeline do agente: {e}")
