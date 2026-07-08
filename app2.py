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
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

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
    # Tabela de histórico global
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_global (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            session_id TEXT,
            role TEXT,
            content TEXT
        )
    """)
    # Tabela: Sistema de High Scores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS high_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            nome TEXT,
            pontor INTEGER
        )
    """)
    # Tabela: Cache de Horários Locais (Evita queries constantes à Web)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_horarios (
            linha TEXT PRIMARY KEY,
            url TEXT,
            conteudo_txt TEXT,
            ultima_atualizacao TEXT
        )
    """)
    # Tabela: Cache das Tipologias de Passe (scraped de guimabus.pt/titulos/)
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
    # Tabela: Cache do Tarifário (scraped de guimabus.pt/tarifarios/, PDF)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_tarifario (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            url_pdf TEXT,
            conteudo_txt TEXT,
            ultima_atualizacao TEXT
        )
    """)
    # Tabela: Índice Paragem <-> Linha (construído a partir do texto dos horários já em cache),
    # usado para sugerir transbordos entre linhas.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_paragens_linha (
            linha TEXT,
            paragem TEXT,
            PRIMARY KEY (linha, paragem)
        )
    """)
    # Tabela: Título/descrição de cada linha (ex: "171 Quintães - Guimarães (via S. Torcato e Atães)").
    # Os títulos mencionam frequentemente freguesias que os nomes de paragem, por si só, não indicam.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_titulo_linha (
            linha TEXT PRIMARY KEY,
            titulo TEXT,
            ultima_atualizacao TEXT
        )
    """)
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

# Inicializa a BD no arranque
inicializar_bd()

# 3. Configuração da página 
st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="wide")
st.title("💼 O Teu Super Secretário de Produtividade")

# Identificador único de sessão
if "session_id" not in st.session_state:
    st.session_state.session_id = datetime.now().strftime("%H%M%S%f")

# --- CAPTURA DE RECORDES VIA URL ---
query_params = st.query_params
if "save_nome" in query_params and "save_pontos" in query_params:
    nome_recorde = query_params["save_nome"].upper()
    pontos_recorde = int(query_params["save_pontos"])
    
    guardar_score_bd(nome_recorde, pontos_recorde)
    st.toast(f"💾 Recorde de {nome_recorde} ({pontos_recorde} pas.) guardado com sucesso!")
    
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

# --- INTEGRAÇÃO FACEBOOK RSS (COM INTELIGÊNCIA ARTIFICIAL PARA DATAS) ---
@st.cache_data(ttl=3600)
def obter_avisos_facebook():
    """
    Lê os últimos 10 avisos do Facebook e usa a Inteligência Artificial para ler
    as datas no meio do texto, mostrando apenas os que estão ativos no dia de hoje.
    """
    url_rss = "https://rss.app/feeds/xF3kb9tGqqFDxAsF.xml"
    avisos_ativos = []

    try:
        # 1. Obter os dados do RSS
        response = requests.get(url_rss, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "xml") 
        itens = soup.find_all("item")
        
        posts_para_analisar = []
        for i, item in enumerate(itens[:10]): # Analisamos os últimos 10 posts
            texto_titulo = item.find("title").text if item.find("title") else "Aviso Guimabus"
            desc = item.find("description")
            desc_text = desc.text if desc else ""
            
            # Tentar extrair a imagem
            imagem_url = ""
            enclosure = item.find("enclosure")
            if enclosure and enclosure.get("url"):
                imagem_url = enclosure.get("url")
            elif desc_text:
                img_match = re.search(r'src="([^"]+)"', desc_text)
                if img_match:
                    imagem_url = img_match.group(1)
            
            # Limpar as tags HTML da descrição para não confundir a IA
            texto_limpo = texto_titulo
            if desc_text:
                texto_limpo += " - " + BeautifulSoup(desc_text, "html.parser").get_text(separator=" ").strip()
            
            posts_para_analisar.append({
                "id": i,
                "titulo": texto_titulo,
                "texto_completo": texto_limpo,
                "imagem": imagem_url
            })
            
        if not posts_para_analisar:
            return []

        # 2. --- O CÉREBRO DA OPERAÇÃO: FILTRAGEM DINÂMICA COM IA ---
        agora = datetime.now(ZoneInfo("Europe/Lisbon"))
        meses_pt = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
        data_hoje_pt = f"{agora.day} de {meses_pt[agora.month - 1]} de {agora.year}"

        prompt_filtro = f"""
        Hoje é {data_hoje_pt}. Aqui tens uma lista de publicações do Facebook da Guimabus em JSON.
        Lê o 'texto_completo' de cada uma.
        
        CRITÉRIOS DE SELEÇÃO:
        - Seleciona tudo o que seja alteração de percurso, greves ou obras.
        - Se a publicação descreve um evento ou obra com data, inclui-a se o período de validade abranger o dia de hoje OU se for um evento futuro que acontecerá nos próximos 7 dias.
        - Se for um aviso urgente publicado há menos de 48 horas, inclui-o sempre.
        - Exclui avisos de datas passadas que já terminaram.
        
        Devolve APENAS um array JSON com os IDs das publicações que devem aparecer. Ex: [0, 2].
        
        REGRAS DE SELEÇÃO ESTRITAS:
        1. Se a publicação menciona um intervalo de datas (ex: "de 1 de abril a 20 de maio") e o dia de hoje ({data_hoje_pt}) ESTÁ dentro desse intervalo, deves selecioná-la.
        2. Se a publicação refere uma data passada que já terminou, NÃO a seleciones.
        3. Se a publicação refere uma data futura que ainda não começou, NÃO a seleciones.
        4. Se for um aviso genérico ou urgente (ex: "Amanhã greve", "Acidente na nacional") publicado há menos de 48 horas, seleciona-o.
        
        Devolve APENAS E ESTRITAMENTE um array JSON com os IDs numéricos das publicações que estão ATIVAS para o dia de hoje. 
        Exemplo: [0, 3]. Se não houver nenhuma ativa, devolve []. Não escrevas absolutamente mais nenhum texto além do JSON.
        
        Publicações a analisar:
        {json.dumps([{"id": p["id"], "texto_completo": p["texto_completo"]} for p in posts_para_analisar], ensure_ascii=False)}
        """
        
        match_json = None
        try:
            model_filtro = genai.GenerativeModel("gemini-3.5-flash")
            resp = model_filtro.generate_content(prompt_filtro, request_options={"timeout": 15})
            
            # Procuramos o array [ ] na resposta da IA
            match_json = re.search(r'\[(.*?)\]', resp.text, re.DOTALL)
            if match_json:
                try:
                    ids_ativos = json.loads("[" + match_json.group(1) + "]")
                    for p in posts_para_analisar:
                        if p["id"] in ids_ativos:
                            avisos_ativos.append({"texto": p["titulo"], "imagem": p["imagem"]})
                except ValueError:
                    pass
        except Exception as e_ai:
            logging.error(f"Erro no LLM a filtrar datas do RSS: {e_ai}")
            
        # Fallback de Segurança: Se a IA falhou (ex: API em baixo) mostramos apenas o último post para não quebrar a aplicação
        if not avisos_ativos and not match_json: 
            avisos_ativos.append({"texto": posts_para_analisar[0]["titulo"], "imagem": posts_para_analisar[0]["imagem"]})

    except Exception as e:
        logging.error(f"Erro ao obter Facebook RSS: {e}")
        
    return avisos_ativos

def renderizar_rodape_anuncios(anuncios_ativos):
    if not anuncios_ativos: 
        return
        
    dados_js = json.dumps(anuncios_ativos)
    
    html_rodape = f"""
    <div id="footer-container" style="
        position: fixed; bottom: 0; left: 0; width: 100%; 
        background-color: #1e1e1e; color: white; z-index: 9999; 
        padding: 20px; border-top: 4px solid #2ecc71; 
        display: flex; align-items: center; justify-content: center; 
        font-family: sans-serif; box-shadow: 0px -4px 20px rgba(0,0,0,0.8);
    ">
        <div id="ticker-content" style="display: flex; align-items: center; max-width: 1200px; width: 100%;">
            <img id="ticker-img" src="" style="max-height: 120px; border-radius: 8px; margin-right: 25px; display: none; cursor: pointer; border: 2px solid #555;" onclick="window.open(this.src, '_blank');">
            <span id="ticker-text" style="font-size: 20px; font-weight: bold; line-height: 1.4;"></span>
        </div>
    </div>

    <script>
        const anuncios = {dados_js};
        let indice = 0;
        
        function atualizar() {{
            const a = anuncios[indice];
            const imgElement = document.getElementById('ticker-img');
            const textElement = document.getElementById('ticker-text');
            
            // Define o texto com verificação de segurança
            textElement.innerText = "🚨 AVISO: " + (a.texto || a.titulo || "Sem descrição disponível");
            
            // Define a imagem com verificação de segurança
            if (a.imagem && a.imagem.startsWith('http')) {{
                imgElement.src = a.imagem;
                imgElement.style.display = "block";
            }} else {{
                imgElement.style.display = "none";
            }}
            
            // Passa para o próximo
            indice = (indice + 1) % anuncios.length;
        }}
        
        // Arranca
        atualizar();
        // Muda de aviso a cada 10 segundos
        setInterval(atualizar, 10000);
    </script>
    """
    components.html(html_rodape, height=160)

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

# Dicionário auxiliar para mapeamento rápido de paragens críticas que dão problemas na API
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
    
    # Tenta traduzir pelo dicionário rápido primeiro
    for nome_p, id_p in DICIONARIO_PARAGENS_CONHECIDAS.items():
        if nome_p in origem_texto:
            id_numérico = id_p
            break
            
    # Se encontramos um ID numérico ou se o input já era um número, faz a query à API real
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
            pass # Se falhar a API ou der sem previsão, cai direto no motor de busca inteligente abaixo

    # --- MOTOR DE BUSCA EM CACHE POR MÚLTIPLAS PALAVRAS-CHAVE ---
    try:
        # Remove termos comuns que possam poluir a pesquisa estruturada
        termos_pesquisa = re.sub(r'\b(estou|na|no|em|paragem|para|ir|as|os|a|o|da|do|linhas|linha|central|guimaraes|guimarães|tenho|quais|quero)\b', '', origem_texto).split()
        if not termos_pesquisa:
            termos_pesquisa = [origem_texto]

        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        
        # Constrói dinamicamente uma cláusula WHERE que força a correspondência de TODAS as palavras-chave (ex: "vaca" AND "negra")
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
                
                # Extrai as linhas do texto plano para isolar tabelas e rotas relevantes
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
    """
    Varrimento dinâmico de todos os PDFs de horários da página oficial da Guimabus.
    Lê os buffers binários em memória e processa as tabelas de texto via pdfplumber.
    """
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
                        # O texto visível do link normalmente é o título da linha, ex:
                        # "171 Quintães - Guimarães (via S. Torcato e Atães)" — isto menciona
                        # freguesias que os nomes de paragem, por si só, não indicam.
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
                                texto_extraido.append(f"[PÁGINA {idx+1} - TEXTO]\n{texto_pag}")

                            try:
                                tabelas = pagina.extract_tables()
                                for t_idx, tabela in enumerate(tabelas):
                                    linhas_tabela = ["\t".join(cell if cell else "" for cell in linha) for linha in tabela]
                                    texto_extraido.append(f"[PÁGINA {idx+1} - TABELA {t_idx+1}]\n" + "\n".join(linhas_tabela))
                            except Exception as e_tabela:
                                logging.warning(f"Não foi possível extrair tabelas da página {idx+1} da linha {linha_id}: {e_tabela}")

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
            cursor.execute("SELECT conteudo_txt, ultima_atualizacao FROM cache_horarios WHERE linha = ?", (candidato,))
            resultado = cursor.fetchone()
            if resultado:
                break
        conn.close()
        
        if resultado:
            return f"Horários em Cache para a Linha {linha_id} (Atualizado em {resultado[1]}):\n\n{resultado[0]}"
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
    """Devolve há quantos dias foi a última sincronização de títulos/tarifário, ou None se nunca correu."""
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
    """Devolve quantas associações linha-paragem existem no índice, para saber se está vazio."""
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

def sincronizar_automaticamente_se_necessario(limite_dias: int = 7):
    if st.session_state.get("sync_automatico_tentado_nesta_sessao"):
        return
    st.session_state.sync_automatico_tentado_nesta_sessao = True

    idade_horarios = obter_idade_cache_horarios_dias()
    if idade_horarios is None or idade_horarios >= limite_dias:
        with st.spinner("🔄 A atualizar horários da Guimabus pela primeira vez há dias — só demora uma vez, aguarda um pouco..."):
            resultado = sincronizar_todos_horarios_guimabus()
            logging.info(f"Sincronização automática de horários executada: {resultado}")
            resultado_indice = construir_indice_paragens()
            logging.info(resultado_indice)
    elif obter_contagem_indice_paragens() == 0:
        # Os horários já estavam frescos, mas o índice de paragens (tabela nova) ainda
        # nunca foi construído a partir deles — sem isto, ficaria vazio indefinidamente
        # até os horários voltarem a expirar daqui a 7 dias.
        with st.spinner("🗺️ A construir o índice de paragens pela primeira vez..."):
            resultado_indice = construir_indice_paragens()
            logging.info(f"Índice de paragens construído (cache de horários já estava fresca): {resultado_indice}")

    idade_titulos = obter_idade_cache_titulos_dias()
    if idade_titulos is None or idade_titulos >= limite_dias:
        with st.spinner("🔄 A atualizar tipologias de passe e tarifário — só demora uma vez, aguarda um pouco..."):
            resultado = sincronizar_titulos_e_tarifario()
            logging.info(f"Sincronização automática de títulos/tarifário executada: {resultado}")

# --- SCRAPING DINÂMICO: TIPOLOGIAS DE PASSE E TARIFÁRIO ---
# Em vez de dados fixos no código, isto vai sempre buscar à página oficial, porque as
# tipologias, preços e documentos exigidos podem mudar (a Guimabus já mudou preços/regras
# no passado sem aviso). Segue o mesmo padrão de cache + auto-sincronização dos horários.

TIPOLOGIAS_PASSE_FALLBACK = {
    "Mensal": {
        "descricao": "Válido para o mês e Origem/Destino para o qual foi adquirido, com nº de viagens ilimitado.",
        "preco": "Consultar tabela tarifária",
        "custo_cartao": "5€",
        "prazo": "Só pode ser emitido ou carregado até ao dia 18 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de identificação"],
    },
}
# ^ Fallback mínimo só para o formulário nunca ficar completamente vazio antes da primeira
# sincronização bem-sucedida. Os dados reais e completos vêm sempre do scraping abaixo.

def sincronizar_titulos_guimabus():
    """Faz scraping de https://guimabus.pt/titulos/ e guarda cada tipologia de passe
    (descrição, preço, custo do cartão, prazo, documentos exigidos) na cache local."""
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
            return "Não foi possível identificar nenhuma tipologia de passe na página (estrutura da página pode ter mudado)."

        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        timestamp_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tipologias_processadas = []

        for bloco in blocos:
            linhas_bloco = bloco.split("\n")
            if not linhas_bloco:
                continue
            nome_tipologia = linhas_bloco[0].strip()
            if not nome_tipologia:
                continue

            resto_texto = "\n".join(linhas_bloco[1:])

            match_prazo = re.search(r'(S\u00f3 podem ser emitidos.*?\.)', resto_texto, re.IGNORECASE)
            prazo = match_prazo.group(1).strip() if match_prazo else "Prazo não indicado na página."

            match_preco = re.search(r'Pre\u00e7o:\s*(.+)', resto_texto)
            if match_preco:
                preco = match_preco.group(1).strip()
            elif re.search(r'\bGRATUITO\b', resto_texto, re.IGNORECASE):
                preco = "Gratuito"
            else:
                match_desconto = re.search(r'(\d{1,3}%\s*de desconto[^\n.]*\.)', resto_texto, re.IGNORECASE)
                preco = match_desconto.group(1).strip() if match_desconto else "Consultar tabela tarifária"

            match_cartao = re.search(r'Custo do cart\u00e3o:\s*([\d,]+\u20ac)', resto_texto)
            custo_cartao = match_cartao.group(1).strip() if match_cartao else "Não indicado"

            match_descricao = re.match(r'(.*?)(?:Pre\u00e7o:|GRATUITO|Gratuito|\*\*Documentos necess\u00e1rios)', resto_texto, re.DOTALL)
            descricao = match_descricao.group(1).strip().replace("\n", " ") if match_descricao else ""

            match_docs = re.search(r'\*\*Documentos necess\u00e1rios:\*\*(.*?)(?:S\u00f3 podem ser emitidos|$)', resto_texto, re.DOTALL)
            documentos = []
            if match_docs:
                candidatos_doc = [d.strip() for d in match_docs.group(1).split("\n") if d.strip()]
                for d in candidatos_doc:
                    if re.match(r'^(Custo do cart\u00e3o|Pre\u00e7o)', d, re.IGNORECASE):
                        continue
                    documentos.append(d)
            if not documentos:
                documentos = ["Cartão de Cidadão / Documento de Identificação (verificar página oficial para lista completa)"]

            cursor.execute("""
                INSERT OR REPLACE INTO cache_titulos (tipologia, descricao, preco, custo_cartao, prazo, documentos_json, ultima_atualizacao)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (nome_tipologia, descricao, preco, custo_cartao, prazo, json.dumps(documentos, ensure_ascii=False), timestamp_atual))
            tipologias_processadas.append(nome_tipologia)

        conn.commit()
        conn.close()

        msg = f"Sincronização de titles concluída: {len(tipologias_processadas)} tipologias encontradas ({', '.join(tipologias_processadas)})."
        logging.info(msg)
        return msg

    except Exception as e:
        error_msg = f"Falha ao sincronizar títulos de passe: {e}"
        logging.error(error_msg)
        return error_msg

def sincronizar_tarifario_guimabus():
    """Vai a https://guimabus.pt/tarifarios/, encontra o PDF da tabela tarifária atual
    (o nome do ficheiro muda todos os anos) e extrai o texto para a cache local."""
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
            return "Não foi encontrado nenhum PDF de tarifário na página (estrutura pode ter mudado)."

        pdf_response = requests.get(url_pdf, headers=headers, timeout=20)
        pdf_response.raise_for_status()

        texto_extraido = []
        with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
            for idx, pagina in enumerate(pdf.pages):
                texto_pag = pagina.extract_text(layout=True)
                if texto_pag:
                    texto_extraido.append(f"[PÁGINA {idx+1} - TEXTO]\n{texto_pag}")
                try:
                    tabelas = pagina.extract_tables()
                    for t_idx, tabela in enumerate(tabelas):
                        linhas_tabela = ["\t".join(cell if cell else "" for cell in linha) for linha in tabela]
                        texto_extraido.append(f"[PÁGINA {idx+1} - TABELA {t_idx+1}]\n" + "\n".join(linhas_tabela))
                except Exception as e_tabela:
                    logging.warning(f"Não foi possível extrair tabelas da página {idx+1} do tarifário: {e_tabela}")

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

        msg = f"Sincronização do tarifário concluída (fonte: {url_pdf})."
        logging.info(msg)
        return msg

    except Exception as e:
        error_msg = f"Falha ao sincronizar tarifário: {e}"
        logging.error(error_msg)
        return error_msg

def sincronizar_titulos_e_tarifario():
    """Corre as duas sincronizações (títulos + tarifário) e devolve um resumo combinado."""
    resultado_titulos = sincronizar_titulos_guimabus()
    resultado_tarifario = sincronizar_tarifario_guimabus()
    return f"{resultado_titulos}\n{resultado_tarifario}"

# --- ÍNDICE PARAGEM <-> LINHA (para sugerir transbordos) ---
def _extrair_paragens_de_texto(texto: str):
    """Lê o texto de um horário (já extraído do PDF) e devolve o conjunto de nomes de paragem
    encontrados. Cada linha de horário tem o formato 'Nome da Paragem  07:20 08:10 - 09:40 ...',
    por isso procuramos linhas que terminem em pelo menos 3 tokens de hora (HH:MM) ou '-'."""
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
    """Percorre todo o texto de horários já em cache e reconstrói o índice paragem<->linha.
    Deve ser chamado depois de sincronizar_todos_horarios_guimabus()."""
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
        msg = f"Índice de paragens reconstruído: {total_paragens} associações linha-paragem, a partir de {len(linhas_cache)} linhas em cache."
        logging.info(msg)
        return msg
    except Exception as e:
        error_msg = f"Falha ao construir índice de paragens: {e}"
        logging.error(error_msg)
        return error_msg

def _normalizar_nome_paragem(texto: str):
    """Os horários oficiais usam abreviaturas (ex: 'S. Torcato' em vez de 'São Torcato'),
    mas as pessoas escrevem por extenso. Sem isto, uma pesquisa por 'São Torcato' nunca
    encontra 'S. Torcato' no texto, mesmo sendo exatamente a mesma paragem. Também removemos
    acentos/diacríticos (ex: 'gonca' precisa de encontrar 'Gonça' — para o computador,
    'c' e 'ç' são caracteres completamente diferentes sem esta normalização)."""
    t = texto.lower().strip()
    t = re.sub(r'\bsão\b', 's.', t)
    t = re.sub(r'\bsanta\b', 'sta.', t)
    t = re.sub(r'\bsanto\b', 'sto.', t)
    t = t.replace('.', '')
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def planear_viagem_com_transbordo(origem: str, destino: str):
    """Ferramenta do agente: dado o nome (aproximado) de uma paragem de origem e de destino,
    procura no índice local (construído a partir dos horários reais já em cache) se existe uma
    linha direta, ou sugere um ponto de transbordo (uma paragem comum a uma linha que passa na
    origem e uma linha que passa no destino).

    NOTA IMPORTANTE: isto só identifica QUAIS linhas usar e ONDE fazer transbordo, com base nos
    nomes de paragem encontrados no texto dos horários. NÃO calcula automaticamente se os horários
    das duas viagens encaixam a tempo — para isso, o agente deve depois consultar os horários
    completos de cada linha sugerida (com consultar_cache_horario_linha) e cruzar os horários ele
    próprio, com base na hora atual do sistema."""
    if not origem or not destino:
        return "É necessário indicar a paragem de origem e a paragem de destino."

    origem_norm = _normalizar_nome_paragem(origem)
    destino_norm = _normalizar_nome_paragem(destino)

    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT linha, paragem FROM cache_paragens_linha")
        todas = cursor.fetchall()
        conn.close()
    except Exception as e:
        return f"Erro ao consultar o índice de paragens: {e}"

    if not todas:
        return ("O índice de paragens ainda não foi construído. Peça ao administrador para "
                "sincronizar os horários (isso constrói o índice automaticamente).")

    linhas_origem = set()
    paragens_origem_encontradas = set()
    linhas_destino = set()
    paragens_destino_encontradas = set()
    mapa_linha_paragens = {}  # linha -> set de paragens (para calcular interseção depois)

    for linha_id, paragem in todas:
        mapa_linha_paragens.setdefault(linha_id, set()).add(paragem)
        paragem_norm = _normalizar_nome_paragem(paragem)
        if origem_norm in paragem_norm:
            linhas_origem.add(linha_id)
            paragens_origem_encontradas.add(paragem)
        if destino_norm in paragem_norm:
            linhas_destino.add(linha_id)
            paragens_destino_encontradas.add(paragem)

    if not linhas_origem:
        linhas_origem, titulos_origem = _procurar_linhas_por_titulo(origem_norm)
        aviso_origem_por_titulo = bool(linhas_origem)
    else:
        aviso_origem_por_titulo = False
    if not linhas_destino:
        linhas_destino, titulos_destino = _procurar_linhas_por_titulo(destino_norm)
        aviso_destino_por_titulo = bool(linhas_destino)
    else:
        aviso_destino_por_titulo = False

    if not linhas_origem:
        return (f"Não encontrei nenhuma paragem nem nenhuma linha cujo título mencione '{origem}' "
                f"nos dados em cache. Confirma o nome (pode ser uma freguesia servida por uma linha "
                f"cujo título não a menciona explicitamente).")
    if not linhas_destino:
        return (f"Não encontrei nenhuma paragem nem nenhuma linha cujo título mencione '{destino}' "
                f"nos dados em cache. Confirma o nome (pode ser uma freguesia servida por uma linha "
                f"cujo título não a menciona explicitamente).")

    aviso_precisao = ""
    if aviso_origem_por_titulo:
        aviso_precisao += (f"\n⚠️ Nota: '{origem}' não corresponde a uma paragem exata — foi encontrada "
                           f"apenas porque o TÍTULO da linha menciona essa freguesia/localidade "
                           f"(ex: {', '.join(titulos_origem[:2])}). A paragem exata a usar pode ter outro nome.")
    if aviso_destino_por_titulo:
        aviso_precisao += (f"\n⚠️ Nota: '{destino}' não corresponde a uma paragem exata — foi encontrada "
                           f"apenas porque o TÍTULO da linha menciona essa freguesia/localidade "
                           f"(ex: {', '.join(titulos_destino[:2])}). A paragem exata a usar pode ter outro nome.")

    linhas_diretas = linhas_origem & linhas_destino
    if linhas_diretas:
        resumo = f"Encontrei linha(s) DIRETA(S) entre '{origem}' e '{destino}' (sem transbordo):\n"
        for linha_id in linhas_diretas:
            resumo += f"- Linha {linha_id}\n"
        resumo += f"\nParagens correspondentes à origem: {', '.join(sorted(paragens_origem_encontradas))}"
        resumo += f"\nParagens correspondentes ao destino: {', '.join(sorted(paragens_destino_encontradas))}"
        resumo += "\n\nPróximo passo: consulta os horários desta(s) linha(s) com consultar_cache_horario_linha para dar a hora exata ao utilizador."
        resumo += aviso_precisao
        return resumo

    # Sem linha direta - procurar ponto de transbordo: paragem comum a uma linha da origem e uma linha do destino
    stops_linhas_origem = set()
    for linha_id in linhas_origem:
        stops_linhas_origem |= mapa_linha_paragens.get(linha_id, set())
    stops_linhas_destino = set()
    for linha_id in linhas_destino:
        stops_linhas_destino |= mapa_linha_paragens.get(linha_id, set())

    transbordos_candidatos = stops_linhas_origem & stops_linhas_destino
    # remove as próprias paragens de origem/destino da lista de candidatos a transbordo
    transbordos_candidatos -= paragens_origem_encontradas
    transbordos_candidatos -= paragens_destino_encontradas

    if not transbordos_candidatos:
        return (f"Não encontrei nenhuma linha direta nem um ponto de transbordo óbvio entre '{origem}' e "
                f"'{destino}' com os dados que tenho em cache. Pode ser necessário mais do que um transbordo, "
                f"ou o nome da paragem pode não estar exatamente como no horário oficial.")

    resumo = f"Não há linha direta entre '{origem}' e '{destino}'. Sugestão de transbordo:\n\n"
    for paragem_transbordo in sorted(transbordos_candidatos):
        linhas_ate_transbordo = [l for l in linhas_origem if paragem_transbordo in mapa_linha_paragens.get(l, set())]
        linhas_desde_transbordo = [l for l in linhas_destino if paragem_transbordo in mapa_linha_paragens.get(l, set())]
        resumo += f"- Via **{paragem_transbordo}**: apanha a linha {'/'.join(linhas_ate_transbordo)} desde '{origem}', desce em '{paragem_transbordo}', e apanha a linha {'/'.join(linhas_desde_transbordo)} até '{destino}'.\n"

    resumo += ("\nPróximo passo: consulta os horários completos de cada linha sugerida (com "
               "consultar_cache_horario_linha) e cruza os horários tu próprio para escolher a combination "
               "que encaixa melhor com a hora atual, dando margem para a troca de autocarro.")
    resumo += aviso_precisao
    return resumo

def _procurar_linhas_por_titulo(termo_norm: str):
    """Fallback quando o termo (ex: uma freguesia) não corresponde a nenhuma paragem exata:
    procura nos TÍTULOS das linhas (ex: '171 Quintães - Guimarães (via S. Torcato e Atães)'),
    que muitas vezes mencionam freguesias que os nomes de paragem, por si só, não indicam."""
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT linha, titulo FROM cache_titulo_linha")
        todos_titulos = cursor.fetchall()
        conn.close()
    except Exception as e:
        logging.error(f"Erro ao consultar títulos de linha: {e}")
        return set(), []

    linhas_encontradas = set()
    titulos_encontrados = []
    for linha_id, titulo in todos_titulos:
        if not titulo:
            continue
        titulo_norm = _normalizar_nome_paragem(titulo)
        if termo_norm in titulo_norm:
            linhas_encontradas.add(linha_id)
            titulos_encontrados.append(f"Linha {linha_id}: {titulo}")
    return linhas_encontradas, titulos_encontrados

def obter_tipologias_cache():
    """Lê as tipologias de passe da cache local (SQLite). Se a cache estiver vazia
    (primeira execução antes de qualquer sincronização), usa um fallback mínimo."""
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT tipologia, descricao, preco, custo_cartao, prazo, documentos_json FROM cache_titulos ORDER BY tipologia")
        linhas = cursor.fetchall()
        conn.close()

        if not linhas:
            return TIPOLOGIAS_PASSE_FALLBACK, None

        resultado = {}
        for tipologia, descricao, preco, custo_cartao, prazo, documentos_json in linhas:
            try:
                documentos = json.loads(documentos_json)
            except Exception:
                documentos = [documentos_json]
            resultado[tipologia] = {
                "descricao": descricao,
                "preco": preco,
                "custo_cartao": custo_cartao,
                "prazo": prazo,
                "documentos": documentos,
            }

        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(ultima_atualizacao) FROM cache_titulos")
        ultima_atualizacao = cursor.fetchone()[0]
        conn.close()

        return resultado, ultima_atualizacao
    except Exception as e:
        logging.error(f"Erro ao ler cache de tipologias: {e}")
        return TIPOLOGIAS_PASSE_FALLBACK, None

def consultar_tarifario_cache():
    """Ferramenta do agente: lê o texto do tarifário (tabela de preços) guardado em cache."""
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT conteudo_txt, ultima_atualizacao FROM cache_tarifario WHERE id = 1")
        resultado = cursor.fetchone()
        conn.close()
        if resultado:
            return f"Tabela tarifária (atualizada em {resultado[1]}):\n\n{resultado[0]}"
        return "O tarifário ainda não foi sincronizado. Peça ao administrador para rodar a Sincronização Geral."
    except Exception as e:
        return f"Erro na leitura da cache do tarifário: {e}"

def consultar_tipologias_cache_tool():
    """Ferramenta do agente: lê as tipologias de passe e documentos exigidos, guardados em cache."""
    tipologias, ultima_atualizacao = obter_tipologias_cache()
    if not tipologias:
        return "Não existem tipologias de passe em cache."
    aviso_idade = f" (dados de {ultima_atualizacao})" if ultima_atualizacao else " (dados de fallback, ainda sem sincronização)"
    resumo = f"Tipologias de passe disponíveis{aviso_idade}:\n\n"
    for nome, info in tipologias.items():
        docs_txt = "; ".join(info["documentos"])
        resumo += f"- **{nome}**: {info['descricao']} Preço: {info['preco']}. Custo do cartão: {info['custo_cartao']}. Prazo: {info['prazo']}. Documentos: {docs_txt}.\n"
    return resumo


def verificar_documentos_passe(tipologia: str, ficheiros_carregados: dict):
    tipologias_atuais, _ = obter_tipologias_cache()
    info = tipologias_atuais.get(tipologia, {"documentos": ["documento não especificado"]})
    partes = [
        f"Vais rever documentos carregados por um utilizador que pediu um passe do tipo '{tipologia}'.\n"
        f"Documentos exigidos para este tipo de passe: {', '.join(info['documentos'])}.\n\n"
        "Para CADA documento carregado abaixo (pela ordem em que aparecem), diz:\n"
        "1. Que tipo de documento parece ser (com base só no que vês, sem inventar).\n"
        "2. Se parece corresponder a um dos documentos exigidos para esta tipologia, e a qual.\n"
        "3. Se está legível e completo, ou se falta algo/está cortado/ilegível.\n"
        "NÃO tentes confirmar a autenticidade legal do documento — isso não é possível nem é o teu papel. "
        "Isto é só uma verificação preliminar de forma/tipo para ajudar o utilizador a não se esquecer de nada. "
        "Sê direto e claro, em Português de Portugal. No fim, diz também se falta carregar algum dos documentos exigidos "
        "que não foram fornecidos."
    ]

    nomes_documentos = []
    for nome_doc, ficheiro in ficheiros_carregados.items():
        if ficheiro is None:
            continue
        nomes_documentos.append(nome_doc)
        try:
            dados_bytes = ficheiro.getvalue()
            mime = ficheiro.type or "application/octet-stream"
            partes.append(f"\n--- Documento carregado para: '{nome_doc}' ---")
            partes.append({"mime_type": mime, "data": dados_bytes})
        except Exception as e:
            logging.error(f"Erro ao ler ficheiro carregado '{nome_doc}': {e}")

    if not nomes_documentos:
        return "Nenhum documento foi carregado ainda."

    try:
        model_verificacao = genai.GenerativeModel("gemini-3.5-flash")
        resposta = model_verificacao.generate_content(partes, request_options={"timeout": 40})
        logging.info(f"Verificação de documentos executada para tipologia '{tipologia}' ({len(nomes_documentos)} ficheiro(s)). Conteúdo dos documentos NÃO fica registado em log.")
        return resposta.text
    except Exception as e:
        logging.error(f"Erro na verificação de documentos: {e}")
        return f"Não foi possível verificar os documentos neste momento: {e}"

def recomendar_tipologias_passe(respostas: dict, tipologias_disponiveis: dict):
    """Aplica regras simples (idade, estudante, residência, etc.) às tipologias REAIS
    disponíveis na cache, e devolve as que parecem aplicáveis à pessoa. As regras espelham
    os critérios descritos em guimabus.pt/titulos/ — se a Guimabus mudar os critérios, os
    NOMES das tipologias na cache podem mudar e estas regras precisam de ser revistas."""
    idade = respostas.get("idade")
    estudante = respostas.get("estudante")
    nivel_estudo = respostas.get("nivel_estudo")
    residente_gmr = respostas.get("residente_gmr")
    incapacidade_60 = respostas.get("incapacidade_60")
    antigo_combatente = respostas.get("antigo_combatente")
    usa_passe_cp = respostas.get("usa_passe_cp")
    reforma_antecipada = respostas.get("reforma_antecipada")

    candidatas = []

    def _tem(nome_parcial):
        for nome in tipologias_disponiveis:
            if nome_parcial.lower() in nome.lower():
                return nome
        return None

    if antigo_combatente and _tem("Antigo Combatente"):
        candidatas.append(_tem("Antigo Combatente"))

    if incapacidade_60 and _tem("Mobilidade Condicionada"):
        candidatas.append(_tem("Mobilidade Condicionada"))

    if idade is not None and idade >= 65 and residente_gmr and _tem("65+"):
        candidatas.append(_tem("65+"))

    if reforma_antecipada and idade is not None and 60 <= idade < 65 and _tem("Reformado"):
        candidatas.append(_tem("Reformado"))

    if estudante:
        if nivel_estudo == "superior":
            if residente_gmr and _tem("Universitário Residente"):
                candidatas.append(_tem("Universitário Residente"))
            elif _tem("Universitário Não Residente"):
                candidatas.append(_tem("Universitário Não Residente"))
        elif nivel_estudo == "ate_18" and _tem("18+TP"):
            candidatas.append(_tem("18+TP"))
        elif nivel_estudo == "ate_23" and _tem("23+TP"):
            candidatas.append(_tem("23+TP"))

    if usa_passe_cp and _tem("Mensal CP"):
        candidatas.append(_tem("Mensal CP"))

    # Se nada específico se aplicar, sugere as opções de passe mensal com desconto conforme residência
    if not candidatas:
        if residente_gmr and _tem("CIM AVE 50% + 10% CMG"):
            candidatas.append(_tem("CIM AVE 50% + 10% CMG"))
        elif residente_gmr and _tem("CIM AVE 50%"):
            candidatas.append(_tem("CIM AVE 50%"))
        elif _tem("Mensal") and not _tem("CIM") :
            # tipologia genérica "Mensal" (evita apanhar variantes CIM/CP por engano)
            for nome in tipologias_disponiveis:
                if nome.strip().lower() == "mensal":
                    candidatas.append(nome)
                    break

    # Remove duplicados mantendo ordem
    vistos = set()
    candidatas_unicas = []
    for c in candidatas:
        if c and c not in vistos:
            vistos.add(c)
            candidatas_unicas.append(c)

    return candidatas_unicas

def renderizar_pedido_passe():
    st.subheader("🎫 Pedido de Passe — Guimabus")
    st.info(
        "⚠️ **Aviso importante:** este formulário é uma ferramenta de apoio e verificação preliminar. "
        "**Não é um canal oficial de submissão à Guimabus** — depois de confirmares aqui que os teus "
        "documentos parecem corretos, ainda precisas de os entregar/carregar através dos canais oficiais "
        "da Guimabus (loja física ou formulário oficial). "
        "**Os documentos que carregares aqui não são guardados** — são analisados em memória e descartados "
        "logo a seguir; não ficam gravados em nenhum ficheiro, base de dados ou log desta aplicação."
    )

    TIPOLOGIAS_PASSE, ultima_atualizacao = obter_tipologias_cache()
    if ultima_atualizacao:
        st.caption(f"📅 Dados de tipologias atualizados em: {ultima_atualizacao} (sincronizados automaticamente de guimabus.pt/titulos/)")
    else:
        st.warning("⚠️ Estes dados ainda são um fallback mínimo — a sincronização com o site oficial ainda não correu. Pede ao Celso para entrar como admin e sincronizar.")

    with st.expander("🧭 Não sabes qual tipologia é a tua? Responde a estas perguntas", expanded=False):
        col1, col2 = st.columns(2)
        idade = col1.number_input("A tua idade", min_value=0, max_value=120, value=25, step=1, key="wizard_idade")
        residente_gmr = col2.checkbox("Resides no concelho de Guimarães?", key="wizard_residente")

        estudante = st.checkbox("És estudante?", key="wizard_estudante")
        nivel_estudo = None
        if estudante:
            nivel_estudo = st.radio(
                "Que nível de ensino?",
                options=["ate_18", "ate_23", "superior"],
                format_func=lambda x: {"ate_18": "Até 18 anos (básico/secundário)", "ate_23": "Até 23-24 anos (secundário tardio)", "superior": "Ensino superior"}[x],
                key="wizard_nivel"
            )

        col3, col4 = st.columns(2)
        incapacidade_60 = col3.checkbox("Grau de incapacidade ≥ 60%?", key="wizard_incapacidade")
        antigo_combatente = col4.checkbox("Antigo combatente ou viúvo(a)?", key="wizard_combatente")

        col5, col6 = st.columns(2)
        reforma_antecipada = col5.checkbox("Reforma antecipada (60-65 anos, pensão baixa)?", key="wizard_reforma")
        usa_passe_cp = col6.checkbox("Já tens passe CP (comboio)?", key="wizard_cp")

        if st.button("🔍 Recomendar tipologia", key="wizard_recomendar"):
            respostas = {
                "idade": idade,
                "residente_gmr": residente_gmr,
                "estudante": estudante,
                "nivel_estudo": nivel_estudo,
                "incapacidade_60": incapacidade_60,
                "antigo_combatente": antigo_combatente,
                "reforma_antecipada": reforma_antecipada,
                "usa_passe_cp": usa_passe_cp,
            }
            recomendadas = recomendar_tipologias_passe(respostas, TIPOLOGIAS_PASSE)
            if recomendadas:
                st.success(f"Com base nas tuas respostas, a(s) tipologia(s) mais indicada(s): **{' / '.join(recomendadas)}**")
                st.caption("Seleciona essa tipologia no menu abaixo para veres os documentos necessários. Esta recomendação é orientativa — a decisão final é sempre da Guimabus.")
            else:
                st.warning("Não consegui associar as tuas respostas a nenhuma tipologia com desconto especial — o passe **Mensal** normal é provavelmente a opção aplicável.")

    tipologia_escolhida = st.selectbox("Escolhe a tipologia do passe que pretendes pedir:", list(TIPOLOGIAS_PASSE.keys()))
    info = TIPOLOGIAS_PASSE[tipologia_escolhida]

    st.markdown(f"**Descrição:** {info['descricao']}")
    st.markdown(f"**Preço:** {info['preco']}  |  **Custo do cartão:** {info['custo_cartao']}")
    st.caption(f"⏰ {info['prazo']}")

    st.markdown("**Documentos necessários para esta tipologia:**")
    ficheiros_carregados = {}
    for i, nome_doc in enumerate(info["documentos"]):
        ficheiros_carregados[nome_doc] = st.file_uploader(
            f"📄 {nome_doc}",
            type=["pdf", "png", "jpg", "jpeg"],
            key=f"upload_passe_{tipologia_escolhida}_{i}"
        )

    if st.button("🔍 Verificar documentos carregados", use_container_width=True):
        algum_carregado = any(f is not None for f in ficheiros_carregados.values())
        if not algum_carregado:
            st.warning("Carrega pelo menos um documento antes de pedir a verificação.")
        else:
            with st.spinner("A analisar os documentos (em memória, sem gravar nada)..."):
                resultado = verificar_documentos_passe(tipologia_escolhida, ficheiros_carregados)
            st.markdown("### Resultado da verificação preliminar")
            st.markdown(resultado)
            st.caption("Lembra-te: esta verificação é só um apoio automático e não substitui a validação oficial da Guimabus.")

# --- INTERFACE: MINI-GAME TOTALMENTE INTEGRADO (COM DIREÇÕES CORRIGIDAS) ---
def renderizar_jogo():
    top_scores = obter_top_10()
    json_scores = json.dumps(top_scores)

    html_jogo = """
    <div style="text-align:center; background-color:#111; padding:15px; border-radius:10px; font-family:sans-serif;">
        <h3 style="color:#2ecc71; margin-top:0; margin-bottom:10px;">🚌 Guimabus Arcade: Cabine de Condução 🚌</h3>
        
        <canvas id="stage" width="650" height="360" style="border:2px solid #2ecc71; background-color:#000; display:block; margin:0 auto; touch-action:none;"></canvas>
        
        <div style="margin-top: 10px;">
            <button id="btnAction" onclick="toggleGame()" style="padding: 6px 15px; background:#2ecc71; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">Play ▶</button>
            <input type="text" id="nomeInput" placeholder="Teu Nome aqui" maxlength="10" style="display:none; padding: 5px; border-radius:4px; border:1px solid #2ecc71; background:#222; color:white; width:120px; margin-left:10px; vertical-align:middle; text-transform:uppercase;">
            <button id="btnGravar" onclick="gravarRecorde()" style="display:none; padding: 6px 15px; background:#f1c40f; color:black; border:none; border-radius:5px; font-weight:bold; cursor:pointer; margin-left:5px; vertical-align:middle;">Gravar 💾</button>
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
            var snake, dx, dy, apple, score, velocidadeMs;
            var proximaDirecao = null;
            var gameInterval = null;
            var gameStarted = false;
            var gameOver = false;
            
            var leaderboard = JSON.parse('JSON_SCORES_PLACEHOLDER');

            function novaMaca() {
                var pos;
                do {
                    pos = {
                        x: Math.floor(Math.random() * cols) * tnt,
                        y: Math.floor(Math.random() * rows) * tnt
                    };
                } while (snake.some(function(s) { return s.x === pos.x && s.y === pos.y; }));
                return pos;
            }

            function estadoInicial() {
                snake = [{x:160, y:160}, {x:140, y:160}, {x:120, y:160}];
                dx = tnt; dy = 0;
                proximaDirecao = null;
                score = 0;
                velocidadeMs = 180;
                apple = novaMaca();
                gameOver = false;
                nomeInput.style.display = 'none';
                btnGravar.style.display = 'none';
            }
            estadoInicial();
            
            function drawScene() {
                ctx.fillStyle = '#222222'; ctx.fillRect(0, 0, gameWidth, canvas.height);
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
                ctx.lineWidth = 1;
                for(var i=tnt; i<canvas.height; i+=tnt) {
                    ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(gameWidth, i); ctx.stroke();
                }

                ctx.fillStyle = '#2ecc71'; ctx.fillRect(gameWidth, 0, 3, canvas.height);

                // Passenger
                ctx.fillStyle = '#3498db'; ctx.beginPath();
                ctx.arc(apple.x + tnt/2, apple.y + tnt/2, (tnt-4)/2, 0, 2 * Math.PI); ctx.fill();
                ctx.fillStyle = '#ffffff'; ctx.beginPath();
                ctx.arc(apple.x + tnt/2, apple.y + tnt/2, (tnt-12)/2, 0, 2 * Math.PI); ctx.fill();
                
                // Bus
                for(var i=0; i<snake.length; i++) {
                    if (i === 0) {
                        ctx.fillStyle = '#27ae60'; ctx.fillRect(snake[i].x, snake[i].y, tnt-1, tnt-1);
                        ctx.fillStyle = '#f1c40f';
                        if (dx > 0) { ctx.fillRect(snake[i].x + tnt - 4, snake[i].y + 2, 3, 3); ctx.fillRect(snake[i].x + tnt - 4, snake[i].y + tnt - 6, 3, 3); }
                        else if (dx < 0) { ctx.fillRect(snake[i].x + 1, snake[i].y + 2, 3, 3); ctx.fillRect(snake[i].x + 1, snake[i].y + tnt - 6, 3, 3); }
                        else if (dy < 0) { ctx.fillStyle = '#2ecc71'; ctx.fillRect(snake[i].x + 1, snake[i].y + 1, tnt-3, tnt-3); }
                        else if (dy > 0) { ctx.fillRect(snake[i].x + 2, snake[i].y + tnt - 4, 3, 3); ctx.fillRect(snake[i].x + tnt - 6, snake[i].y + tnt - 4, 3, 3); }
                    } else {
                        ctx.fillStyle = '#2ecc71'; ctx.fillRect(snake[i].x + 1, snake[i].y + 1, tnt-3, tnt-3);
                        ctx.fillStyle = '#2c3e50'; ctx.fillRect(snake[i].x + 4, snake[i].y + 4, tnt-9, tnt-9);
                    }
                }
                
                if(snake.length > 1) {
                    var textPos = snake[1];
                    ctx.fillStyle = '#ffffff'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'center';
                    ctx.fillText('GMR', textPos.x + tnt/2, textPos.y + tnt/2 + 3);
                }

                ctx.fillStyle = '#ffffff'; ctx.font = 'bold 14px sans-serif'; ctx.textAlign = 'start';
                ctx.fillText('Passageiros: ' + (score / 10), 15, 25);

                // Leaderboard
                ctx.fillStyle = '#151515'; ctx.fillRect(gameWidth + 3, 0, canvas.width - gameWidth - 3, canvas.height);
                ctx.fillStyle = '#2ecc71'; ctx.font = 'bold 14px sans-serif';
                ctx.fillText('🏆 TOP 10 MOTORISTAS', gameWidth + 15, 30);
                
                ctx.font = '12px sans-serif';
                for(var k=0; k<10; k++) {
                    var yPos = 65 + (k * 26);
                    ctx.fillStyle = (k === 0) ? '#f1c40f' : ((k===1) ? '#bdc3c7' : ((k===2) ? '#e67e22' : '#ffffff'));
                    
                    var medalha = (k===0)?"1º ":((k===1)?"2º ":((k===2)?"3º ":(k+1)+"º "));
                    if (leaderboard[k]) {
                        var item = leaderboard[k];
                        ctx.fillText(medalha + item[0], gameWidth + 15, yPos);
                        ctx.textAlign = 'end';
                        ctx.fillText(item[1] + ' pas.', canvas.width - 15, yPos);
                        ctx.textAlign = 'start';
                    } else {
                        ctx.fillStyle = '#444';
                        ctx.fillText(medalha + '------', gameWidth + 15, yPos);
                    }
                }
                
                if (gameOver) {
                    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)'; ctx.fillRect(0, 0, gameWidth, canvas.height);
                    ctx.fillStyle = '#e74c3c'; ctx.font = 'bold 22px sans-serif'; ctx.textAlign = 'center';
                    ctx.fillText('FIM DA LINHA', gameWidth/2, canvas.height/2 - 20);
                    ctx.fillStyle = '#ffffff'; ctx.font = '14px sans-serif';
                    ctx.fillText('Transportaste ' + (score / 10) + ' passageiros!', gameWidth/2, canvas.height/2 + 5);
                    ctx.font = '11px sans-serif'; ctx.fillStyle = '#f1c40f';
                    ctx.fillText('Digita o teu nome no painel abaixo.', gameWidth/2, canvas.height/2 + 30);
                    ctx.textAlign = 'start';
                }
            }
            
            function game() {
                if (gameOver) return;
                if (proximaDirecao) {
                    if (proximaDirecao.dx !== -dx || proximaDirecao.dy !== -dy) {
                        dx = proximaDirecao.dx; dy = proximaDirecao.dy;
                    }
                    proximaDirecao = null;
                }
                var head = {x: snake[0].x + dx, y: snake[0].y + dy};
                if (head.x < 0) head.x = gameWidth - tnt;
                else if (head.x >= gameWidth) head.x = 0;
                if (head.y < 0) head.y = canvas.height - tnt;
                else if (head.y >= canvas.height) head.y = 0;

                var vaiComer = (head.x === apple.x && head.y === apple.y);
                var corpoParaVerificar = vaiComer ? snake : snake.slice(0, snake.length - 1);
                for (var i = 0; i < corpoParaVerificar.length; i++) { 
                    if (corpoParaVerificar[i].x === head.x && corpoParaVerificar[i].y === head.y) {
                        triggerGameOver(); return;
                    } 
                }
                snake.unshift(head);
                if (vaiComer) {
                    score += 10;
                    if (score % 50 === 0 && velocidadeMs > 80) {
                        velocidadeMs -= 10;
                        clearInterval(gameInterval); gameInterval = setInterval(game, velocidadeMs);
                    }
                    apple = novaMaca();
                } else { snake.pop(); }
                drawScene();
            }
            
            function toggleGame() {
                if (gameOver) { resetGame(); return; }
                if (!gameStarted) {
                    gameStarted = true; btnAction.innerText = "Pause ⏸";
                    gameInterval = setInterval(game, velocidadeMs);
                } else {
                    gameStarted = false; btnAction.innerText = "Play ▶"; clearInterval(gameInterval);
                }
            }
            function triggerGameOver() {
                gameOver = true; gameStarted = false; clearInterval(gameInterval);
                btnAction.innerText = "Reset 🔄";
                if((score/10) > 0) {
                    nomeInput.style.display = 'inline-block';
                    btnGravar.style.display = 'inline-block';
                    nomeInput.focus();
                }
                drawScene();
            }
            function resetGame() { 
                estadoInicial(); gameOver = false; gameStarted = true;
                btnAction.innerText = "Pause ⏸"; gameInterval = setInterval(game, velocidadeMs);
                drawScene();
            }
            function gravarRecorde() {
                var nome = nomeInput.value.trim().toUpperCase();
                if(!nome) { alert('Por favor introduz o teu nome!'); return; }
                btnGravar.disabled = true;
                btnGravar.innerText = "💾...";
                
                var finalScore = (score / 10);
                window.parent.location.search = "?save_nome=" + encodeURIComponent(nome) + "&save_pontos=" + finalScore;
            }
            function mudarDirecao(dir) {
                if (!gameStarted || gameOver) return;
                if(dir === 'esquerda' && dx === 0) proximaDirecao = {dx:-tnt, dy:0};
                if(dir === 'cima' && dy === 0) proximaDirecao = {dx:0, dy:-tnt};
                if(dir === 'direita' && dx === 0) proximaDirecao = {dx:tnt, dy:0};
                if(dir === 'baixo' && dy === 0) proximaDirecao = {dx:0, dy:tnt};
            }
            document.addEventListener('keydown', function(e) {
                var mapa = {37:'esquerda', 38:'cima', 39:'direita', 40:'baixo'};
                if (mapa[e.keyCode]) { e.preventDefault(); mudarDirecao(mapa[e.keyCode]); }
            });
            document.querySelectorAll('button[data-dir]').forEach(function(btn) {
                btn.addEventListener('click', function() { mudarDirecao(btn.getAttribute('data-dir')); });
            });
            drawScene();
        </script>
    </div>
    """.replace("JSON_SCORES_PLACEHOLDER", json_scores)
    return components.html(html_jogo, height=650)

# --- MENSAGEM INICIAL AUTOMÁTICA ---
MENSAGEM_INICIAL = """Olá, Celso! Sou o teu **Agente de Produtividade de Elite**. 

Estou pronto para te apoiar em três frentes:
1. **Modo Executivo:** Monitorização da frota Guimabus e consulta à Knowledge Base.
2. **Modo Tech Recruiter:** Diz-me *'Quero treinar para uma entrevista'* para simularmos testes técnicos em inglês.
3. **Modo Helpdesk Técnico:** Envia-me um problema de IT ou avaria e eu mostro-te como o Celso resolveria a situação.

Como posso ajudar hoje?"""

# --- INICIALIZAÇÃO DE ESTADOS ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": MENSAGEM_INICIAL}]
    logging.info(f"Nova sessão de utilizador iniciada. ID Temporário: {st.session_state.session_id}")

if "jogo_ativo" not in st.session_state:
    st.session_state.jogo_ativo = False

# Mantém a cache de horários sempre fresca sem depender de um admin lembrar-se de clicar
sincronizar_automaticamente_se_necessario(limite_dias=7)

# --- SIDEBAR DE ELITE (GERENCIAMENTO DO AGENTE) ---
with st.sidebar:
    st.header("⚙️ Painel do Agente")
    if st.button("🗑️ Limpar O Meu Histórico", use_container_width=True):
        st.session_state.messages = [{"role": "assistant", "content": MENSAGEM_INICIAL}]
        st.session_state.jogo_ativo = False
        st.rerun()
    st.divider()
    
    st.subheader("🕹️ Entretenimento")
    texto_botao_jogo = "Fechar Jogo X" if st.session_state.jogo_ativo else "Abrir Mini-Game 👾"
    if st.button(texto_botao_jogo, use_container_width=True):
        st.session_state.jogo_ativo = not st.session_state.jogo_ativo
        st.rerun()
    st.divider()

    st.subheader("🎫 Títulos de Transporte")
    if "passe_ativo" not in st.session_state:
        st.session_state.passe_ativo = False
    texto_botao_passe = "Fechar Pedido de Passe X" if st.session_state.passe_ativo else "Pedir Passe 🎫"
    if st.button(texto_botao_passe, use_container_width=True):
        st.session_state.passe_ativo = not st.session_state.passe_ativo
        st.rerun()
    st.divider()
    
    # SECÇÃO: CONTACTO DIRETO E RECRUTAMENTO
    st.sidebar.subheader("👨‍💻 Desenvolvedor")
    st.sidebar.info("""**Celso Ferreira**
*À procura de emprego na área de IT / Informática.*
📞 Contacto: **917 486 683**""")
    st.sidebar.divider()
    
    st.write("Estado: **Online**")
    st.write("Modelo Nativo: `Gemini-3.5-Flash`")
    st.sidebar.divider()
    
    # VISUALIZADOR DE DADOS E EXPORTAÇÃO — SÓ VISÍVEL PARA O ADMINISTRADOR
    st.sidebar.subheader("🔒 Área de Administrador")
    if "admin_autenticado" not in st.session_state:
        st.session_state.admin_autenticado = False

    if not st.session_state.admin_autenticado:
        with st.sidebar.expander("Entrar como administrador"):
            password_input = st.text_input("Password de administrador", type="password", key="admin_pwd")
            if st.button("Entrar", key="admin_login_btn"):
                if password_input and password_input == st.secrets.get("ADMIN_PASSWORD", None):
                    st.session_state.admin_autenticado = True
                    logging.info("Login de administrador bem-sucedido.")
                    st.rerun()
                else:
                    st.sidebar.error("Password incorreta.")
                    logging.warning("Tentativa de login de administrador falhada.")
    else:
        st.sidebar.success("Sessão de administrador activa.")
        
        # BOTÃO EXCLUSIVO DE ADMIN: Dispara o Scraping Automático em Background
        st.sidebar.subheader("🕷️ Automação Web")
        if st.sidebar.button("🔄 Sincronizar Todos os Horários (Scraping)", use_container_width=True):
            with st.spinner("O robô está a ler o site da Guimabus..."):
                resultado_scraping = sincronizar_todos_horarios_guimabus()
                resultado_indice = construir_indice_paragens()
                st.sidebar.success(resultado_scraping)
                st.sidebar.success(resultado_indice)

        if st.sidebar.button("🗺️ Reconstruir Índice de Paragens (sem re-sincronizar)", use_container_width=True):
            with st.spinner("A reconstruir o índice a partir da cache já existente..."):
                st.sidebar.success(construir_indice_paragens())

        if st.sidebar.button("🔄 Sincronizar Títulos e Tarifário", use_container_width=True):
            with st.spinner("O robô está a ler titulos/ e tarifarios/..."):
                resultado_titulos = sincronizar_titulos_e_tarifario()
                st.sidebar.success(resultado_titulos)
                
        if st.sidebar.button("Sair da área de administrador", key="admin_logout_btn"):
            st.session_state.admin_autenticado = False
            st.rerun()

        st.sidebar.subheader("📊 Telemetria e BD")
        if os.path.exists("agente_memoria.db"):
            with open("agente_memoria.db", "rb") as f:
                st.sidebar.download_button("📥 Exportar DB SQLite (.db)", f, "agente_memoria.db", "application/octet-stream", use_container_width=True)

        with st.sidebar.expander("👁️ Ver Logs do Sistema"):
            if os.path.exists("auditoria_agente.log"):
                with open("auditoria_agente.log", "r", encoding="utf-8") as f:
                    linhas_log = f.readlines()[-10:]
                    for linha in linhas_log: st.caption(linha.strip())

        with st.sidebar.expander("🗄️ Histórico Permanente Global (BD) — todas as sessões"):
            if os.path.exists("agente_memoria.db"):
                conn = sqlite3.connect("agente_memoria.db")
                cursor = conn.cursor()
                cursor.execute("SELECT timestamp, session_id, role, content FROM historico_global ORDER BY id DESC LIMIT 30")
                linhas_bd = cursor.fetchall()
                conn.close()
                for r in reversed(linhas_bd):
                    hora_min = r[0].split(" ")[1] if " " in r[0] else r[0]
                    sessao = r[1]
                    if r[2] == "user":
                        st.markdown(f"**🟢 [{hora_min}] Visitante ({sessao}):** {r[3]}")
                    else:
                        st.markdown(f"**🤖 [{hora_min}] Agente ({sessao}):** {r[3]}")
                    st.divider()

# --- ÁREA DO JOGO PRINCIPAL COM LEADERBOARD NATIVO ---
if st.session_state.jogo_ativo:
    renderizar_jogo()

if st.session_state.get("passe_ativo"):
    renderizar_pedido_passe()

# --- RODAPÉ DE AVISOS DO FACEBOOK ---
avisos_hoje = obter_avisos_facebook()
if avisos_hoje:
    renderizar_rodape_anuncios(avisos_hoje)

# Mostrar histórico visual no chat com Avatares Estilizados
for message in st.session_state.messages:
    avatar_tipo = "💼" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar_tipo):
        st.markdown(message["content"])

# --- CAPTURA DE ENTRADA MULTIMODAL ---
prompt_texto = st.chat_input("Como posso ajudar hoje?")
audio_file = st.audio_input("Falar")

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
        with st.spinner("A processar e a transcrever o teu áudio..."):
            try:
                audio_data = audio_file.read()
                model_transcrever = genai.GenerativeModel("gemini-3.5-flash")
                audio_part = {"mime_type": "audio/wav", "data": audio_data}

                response_transcricao = model_transcrever.generate_content([
                    "Transcreve estritamente o áudio fornecido para texto, mantendo a pontuação correta e no idioma original. Não adiciones comentários extras.",
                    audio_part
                ])
                prompt = response_transcricao.text.strip()
                logging.info(f"Transcrição de voz concluída com sucesso: '{prompt}'")
            except Exception as e:
                st.error(f"Erro ao processar o ficheiro de voz: {e}")
                logging.error(f"Falha na transcrição de áudio: {e}")

# --- FLUXO PRINCIPAL DO AGENTE DE ROTEAMENTO (ROUTER DE PERSONAS) ---
if prompt:
    logging.info(f"Input processado [{tipo_input}]: {prompt}")
    guardar_mensagem_bd(st.session_state.session_id, "user", prompt)
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="💼"):
        with st.spinner("Agente a processar contexto e ferramentas..."):
            try:
                contexto_base = len_knowledge_base()
                
                # DEFINIÇÃO DOS PROMPTS DE SISTEMA (MÚLTIPLAS PERSONAS)
                PROMPT_EXECUTIVO = """Tu és o Assistente Executivo de Elite do Celso Ferreira.
                És um Agente focado em automação, suporte e infraestrutura IT.
                Responde de forma concisa em Português de Portugal utilizando sempre a Knowledge Base e ferramentas.

                Tens três ferramentas relacionadas com a frota local da Guimabus:
                - obter_dados_guimabus: estado em tempo real da frota (autocarros em circulação/atrasos). Aceita um "route_id".
                - obter_horarios_paragem: previsão de tempos de espera para uma paragem específica. Aceita tanto o ID numérico como o nome em texto da paragem (ex: "vaca negra").
                - consultar_cache_horario_linha: consulta a cache local da base de dados SQLite para ler os horários e tabelas fixas de uma determinada linha (ex: "101").
                - consultar_tipologias_cache_tool: lê as tipologias de passe (descrição, preço, custo do cartão, prazo, documentos exigidos), sincronizadas automaticamente de guimabus.pt/titulos/.
                - consultar_tarifario_cache: lê a tabela tarifária completa (preços por distância), sincronizada automaticamente de guimabus.pt/tarifarios/.
                - planear_viagem_com_transbordo: dado o nome de uma paragem de origem e uma de destino, diz se há linha direta ou sugere onde fazer transbordo (com base num índice construído a partir dos horários reais). Usa esta ferramenta sempre que o utilizador pedir para ir de um sítio para outro e não for óbvio que linha usar.

                Depois de planear_viagem_com_transbordo indicar quais linhas usar (diretas ou com transbordo), consulta os horários completos dessas linhas com consultar_cache_horario_linha e cruza tu próprio os horários das duas viagens (usando a hora atual do sistema) para dar ao utilizador uma sugestão concreta de que autocarro apanhar em cada troço, com margem de segurança para trocar de autocarro.

                Usa sempre consultar_tipologias_cache_tool e consultar_tarifario_cache para perguntas sobre preços, tipologias de passe ou documentos exigidos — não confies em memória para isto, porque os preços mudam. Se o utilizador quiser efetivamente PEDIR um passe e carregar documentos, informa-o que existe um formulário dedicado na barra lateral ("🎫 Pedir Passe") para isso — esse formulário também tem um pequeno questionário que recomenda a tipologia automaticamente.

                Se o utilizador perguntar "qual o passe/tipologia certo para mim" (ou similar), e ainda não tiver dado informação suficiente, PERGUNTA os critérios relevantes antes de responder (idade, se é estudante e que nível de ensino, se reside no concelho de Guimarães, se tem grau de incapacidade ≥60%, se é antigo combatente, se tem passe CP, se está em reforma antecipada entre os 60-65 anos). Depois de teres essa informação, chama consultar_tipologias_cache_tool e aplica as descrições de cada tipologia (que dizem explicitamente "residente"/"não residente", "estudante", faixas etárias, etc.) para RECOMENDAR a tipologia certa, explicando o porquê com base nos critérios que a pessoa deu. Por exemplo: estudante universitário com 40 anos que vive fora do concelho de Guimarães → "Universitário Não Residente" (não pela idade, mas porque é estudante do ensino superior e não reside no concelho). Não te limites a listar todas as tipologias quando a pessoa já deu informação suficiente para identificar uma específica.

                REGRAS DE OURO PARA MAIOR AUTOMAÇÃO:
                1. Se o utilizador perguntar "Quais as linhas que passam no local X para ir para o local Y" ou apenas "Estou no local X, como vou para Y?", deves chamar OBRIGATORIAMENTE a ferramenta `obter_horarios_paragem` passando o nome da paragem de origem "X".
                2. Com o resultado retornado por esta ferramenta (que varre dinamicamente a cache local de texto por palavras-chave), tu irás descobrir imediatamente no próprio output quais as linhas que contêm essa paragem e o destino. Responde logo com os horários da linha encontrada, calculando os minutos em falta com base na hora atual do sistema. Nunca peças ao utilizador para adivinhar a linha se ela já puder ser descoberta por texto!

                REGRA ANTI-ALUCINAÇÃO — A MAIS IMPORTANTE DE TODAS:
                NUNCA inventes, estimes ou "preenchas" dados que as ferramentas ou a Knowledge Base não te deram. Isto inclui: números de autocarro, atrasos, percursos, horários, nomes/números de linhas, E TAMBÉM datas e dias da semana. Para saber que dia é "hoje" ou "amanhã", usa SEMPRE e apenas a informação em "[DATA E HORA ATUAL DO SISTEMA]" fornecida no início do contexto — nunca assumas ou inventes uma data a partir de memória. NUNCA digas que "consultaste" uma ferramenta, cache ou base de dados que não chamaste de facto. Se as ferramentas devolverem uma lista vazia, um erro, ou "não existem horários em cache", e a Knowledge Base também não tiver essa informação, diz clara e honestamente ao utilizador que não tens essa informação disponível neste momento — nunca substituas por uma resposta que pareça plausível mas seja inventada. É preferível admitir "não sei" do que dar uma resposta errada com aparência de certeza."""
                
                PROMPT_RECRUITER = """You are an expert IT Technical Recruiter interviewing Celso Ferreira for an IT role.
                Conduct the interview strictly in English. Ask one tough, deep technical or behavioral question at a time.
                Evaluate Celso's response professionally based on IT best practices and keep the interviewer persona realistic."""
                
                PROMPT_HELPDESK_TUTOR = """Tu és um Tutor Técnico de Helpdesk e Suporte de IT.
                O teu objetivo é atuar como uma fonte interminável de resolução de problemas de IT.
                Independentemente do problema de suporte indicado pelo utilizador (Active Directory, Redes, Sistemas, Avarias), deves começar a tua resposta OBRIGATORIAMENTE com a seguinte frase padrão: 
                'O Celso faria desta maneira para resolver este problema de IT:'
                Depois, detalha passos de troubleshooting técnicos, comandos em PowerShell ou Linux, e boas práticas aplicadas com precisão."""

                # LÓGICA DO ROUTER EM TEMPO DE EXECUÇÃO
                prompt_normalizado = prompt.lower()
                gatilhos_helpdesk = ["problema", "helpdesk", "ticket", "avaria", "erro", "servidor", "computador", "rede", "suporte", "falha"]
                
                if "entrevista" in prompt_normalizado or "interview" in prompt_normalizado:
                    prompt_sistema_ativo = PROMPT_RECRUITER
                    logging.info("Router selecionou a Persona: IT Technical Recruiter (EN)")
                elif any(word in prompt_normalizado for word in gatilhos_helpdesk):
                    prompt_sistema_ativo = PROMPT_HELPDESK_TUTOR
                    logging.info("Router selecionou a Persona: Tutor de Helpdesk / Modo Celso (PT)")
                else:
                    prompt_sistema_ativo = PROMPT_EXECUTIVO
                    logging.info("Router selecionou a Persona: Assistente Executivo (PT)")

                # Estruturar histórico limpo para o payload da API
                historico_api = []
                for msg in st.session_state.messages[:-1]:
                    if msg["content"] != MENSAGEM_INICIAL:
                        role_api = "model" if msg["role"] == "assistant" else "user"
                        historico_api.append({"role": role_api, "parts": [msg["content"]]})
                
                DIAS_SEMANA_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
                MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

                def _formatar_data_pt(dt):
                    return f"{DIAS_SEMANA_PT[dt.weekday()]}, {dt.day} de {MESES_PT[dt.month - 1]} de {dt.year}"

                # O servidor onde a app corre normalmente usa UTC, não a hora de Portugal —
                # sem isto, "agora" ficava sistematicamente atrasado 1h (ou 2h no inverno).
                # Isto afeta só o texto mostrado ao utilizador; os timestamps internos da BD
                # continuam em hora do servidor, o que não é problema (só servem para comparações
                # relativas entre si, ex: "há quantos dias foi a última sincronização").
                agora = datetime.now(ZoneInfo("Europe/Lisbon"))
                amanha = agora + timedelta(days=1)
                contexto_data = (
                    f"[DATA E HORA ATUAL DO SISTEMA — usa sempre esta informação, nunca a inventes: "
                    f"Hoje é {_formatar_data_pt(agora)}, são {agora.strftime('%H:%M')}. "
                    f"Amanhã será {_formatar_data_pt(amanha)}.]"
                )

                # --- INTERCEÇÃO DE PARAGENS DIRETAMENTE EM PYTHON (PRÉ-ROUTING PREVENTIVO) ---
                contexto_intercecao = ""
                # Se o prompt do utilizador focar uma paragem conhecida ou requisição de rotas
                if any(p in prompt_normalizado for p in ["vaca negra", "hospital", "central", "universidade", "estacao", "paragem", "linhas"]):
                    # Extrai o termo geográfico para a pesquisa por tokens
                    busca_local = "vaca negra" if "vaca negra" in prompt_normalizado else prompt
                    dados_extraidos = obter_horarios_paragem(busca_local)
                    contexto_intercecao = f"\n[DADOS DE CACHE DISPARADOS COMPLEMENTARES: {dados_extraidos}]\n"

                prompt_enriquecido = f"{contexto_data}\n\n{contexto_base}{contexto_intercecao}\n\nUser Prompt: {prompt}"
                
                ferramentas_agente = [obter_dados_guimabus, obter_horarios_paragem, consultar_cache_horario_linha, consultar_tipologias_cache_tool, consultar_tarifario_cache, planear_viagem_com_transbordo]
                
                # Execução Resiliente com Fallback e timeout explícito
                TIMEOUT_SEGUNDOS = 25
                candidatos_modelo = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]

                response = None
                ultimo_erro_modelo = None
                for nome_modelo in candidatos_modelo:
                    try:
                        model = genai.GenerativeModel(
                            model_name=nome_modelo,
                            system_instruction=prompt_sistema_ativo,
                            tools=ferramentas_agente
                        )
                        chat = model.start_chat(history=historico_api, enable_automatic_function_calling=True)
                        response = chat.send_message(
                            prompt_enriquecido,
                            request_options={"timeout": TIMEOUT_SEGUNDOS}
                        )
                        if nome_modelo != candidatos_modelo[0]:
                            logging.warning(f"Modelo principal falhou; resposta obtida com fallback '{nome_modelo}'.")
                            st.info(f"ℹ️ Modelo principal indisponível — resposta gerada com '{nome_modelo}'.")
                        break
                    except Exception as e:
                        ultimo_erro_modelo = e
                        motivo = "limite de quota (429)" if "429" in str(e) else ("timeout" if "timeout" in str(e).lower() or "deadline" in str(e).lower() else str(e))
                        logging.warning(f"Modelo '{nome_modelo}' falhou ({motivo}). A tentar o próximo candidato, se existir.")
                        continue

                if response is None:
                    logging.error(f"Todos os modelos candidatos falharam. Último erro: {ultimo_erro_modelo}")
                    if ultimo_erro_modelo is not None and "429" in str(ultimo_erro_modelo):
                        st.error("🚫 Limite diário gratuito da API do Gemini esgotado. Tenta novamente mais tarde.")
                    else:
                        st.error("🚫 Não foi possível obter resposta de nenhum modelo disponível neste momento.")
                    st.stop()

                full_response = response.text
                st.markdown(full_response)
                
                logging.info(f"Resposta gerada com sucesso ({len(full_response)} caracteres).")
                guardar_mensagem_bd(st.session_state.session_id, "assistant", full_response)
                
                st.download_button("📥 Descarregar Resposta (.txt)", full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"Erro detetado no pipeline do agente: {e}")
                logging.error(f"Falha crítica no pipeline do agente: {e}")
