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
            resumo += f"\n--- Estatística: Atraso médio da frota: {media:.1f}ext minutos. ---"
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

    # --- NOVO MOTOR DE BUSCA EM CACHE POR MÚLTIPLAS PALAVRAS-CHAVE ---
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
        for link in soup.find_all('a', href=True):
            href = link['href']
            if ".pdf" in href and "horario" in href.lower():
                match = re.search(r'linha-([a-z0-9]+)', href.lower())
                if match:
                    linha_id = match.group(1).upper()
                    if linha_id not in links_pdf:
                        links_pdf[linha_id] = href
        
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

                    linhas_processadas.append(linha_id)
                    sucesso = True
                    break
                except Exception as e:
                    ultimo_erro = str(e)
                    time.sleep(1)
                    continue

            if not Bird:
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

def sincronizar_automaticamente_se_necessario(limite_dias: int = 7):
    if st.session_state.get("sync_automatico_tentado_nesta_sessao"):
        return
    st.session_state.sync_automatico_tentado_nesta_sessao = True

    idade_dias = obter_idade_cache_horarios_dias()
    if idade_dias is not None and idade_dias < limite_dias:
        return

    with st.spinner("🔄 A atualizar horários da Guimabus pela primeira vez in dias — só demora uma vez, aguarda um pouco..."):
        resultado = sincronizar_todos_horarios_guimabus()
        logging.info(f"Sincronização automática executada: {resultado}")

# --- DADOS DE REFERÊNCIA: TIPOLOGIAS DE PASSE E DOCUMENTOS EXIGIDOS ---
TIPOLOGIAS_PASSE = {
    "Mensal": {
        "descricao": "Válido para o mês e Origem/Destino para o qual foi adquirido, com nº de viagens ilimitado.",
        "preco": "Consultar tabela tarifária (varia por distância/zona — ver tarifarios/)",
        "custo_cartao": "5€",
        "prazo": "Só pode ser emitido ou carregado até ao dia 18 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de identificação"],
    },
    "Mensal CIM AVE 50%": {
        "descricao": "Residentes na CIM do AVE (Cabeceiras de Basto, Fafe, Guimarães, Mondim de Basto, Póvoa de Lanhoso, Vieira do Minho, Vila Nova de Famalicão, Vizela).",
        "preco": "50% de desconto sobre o passe mensal",
        "custo_cartao": "5€",
        "prazo": "Até ao dia 18 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de Identificação", "Requerimento CIM AVE preenchido", "Comprovativo do domicílio fiscal (Portal das Finanças)"],
    },
    "Mensal CIM AVE 50% + 10% CMG": {
        "descricao": "Residentes no Concelho de Guimarães.",
        "preco": "60% de desconto sobre o passe mensal",
        "custo_cartao": "5€",
        "prazo": "Até ao dia 15 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de Identificação", "Requerimento CIM AVE + 10% CMG preenchido", "Comprovativo do domicílio fiscal (Portal das Finanças)"],
    },
    "Mensal CP": {
        "descricao": "Residentes e não residentes da CIM AVE, detentores do passe CP, com origem ou destino nas estações do concelho de Guimarães.",
        "preco": "50% de desconto sobre a tabela tarifária",
        "custo_cartao": "5€",
        "prazo": "Até ao dia 15 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de Identificação", "Requerimento CMG prerequisito preenchido", "Fotocópia do Passe CP", "Fatura/talão de pagamento mensal com indicação Origem/Destino Guimarães"],
    },
    "Universitário Residente": {
        "descricao": "Estudantes universitários residentes in Guimarães.",
        "preco": "Gratuito",
        "custo_cartao": "5€",
        "prazo": "Até ao dia 15 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de Identificação", "Requerimento CMG preenchido", "Comprovativo do domicílio fiscal (Portal das Finanças)", "Comprovativo de matrícula no ensino superior"],
    },
    "Universitário Não Residente": {
        "descricao": "Estudantes universitários não residentes no concelho de Guimarães.",
        "preco": "Gratuito",
        "custo_cartao": "5€",
        "prazo": "Até ao dia 15 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de Identificação", "Requerimento CMG preenchido", "Declaração de domicílio fiscal (Portal das Finanças)", "Comprovativo de matrícula no ensino superior"],
    },
    "18+TP": {
        "descricao": "Estudantes entre os 4 e os 18 anos (inclusive).",
        "preco": "Gratuito",
        "custo_cartao": "2,50€",
        "prazo": "Até ao dia 15 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de Identificação", "Formulário IMT preenchido"],
    },
    "23+TP": {
        "descricao": "Estudantes até 23 anos (inclusive); alargado até 24 anos para cursos integrados específicos (Arquitetura e Urbanismo, Ciências Farmacêuticas, Medicina, Medicina Dentária, Medicina Veterinária).",
        "preco": "Gratuito",
        "custo_cartao": "2,50€",
        "prazo": "Até ao dia 15 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de Identificação", "Formulário IMT preenchido", "Certificado de matrícula (apenas para cursos integrados até 24 anos)"],
    },
    "Mobilidade Condicionada": {
        "descricao": "Pessoas com grau de incapacidade igual ou superior a 60%. Desconto adicional de 25% sobre o PVP do passe PPMC (total 75% de desconto).",
        "preco": "75% de desconto sobre o passe PPMC",
        "custo_cartao": "5€",
        "prazo": "Até ao dia 18 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de Identificação", "Cópia da Declaração/Cartão Municipal de Pessoa com Deficiência"],
    },
    "65+": {
        "descricao": "Pessoas com mais de 65 anos, residentes no concelho de Guimarães, com Cartão Municipal 65+.",
        "preco": "8,60€",
        "custo_cartao": "5€",
        "prazo": "Até ao dia 18 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de Identificação", "Cópia do Cartão Municipal de Idoso"],
    },
    "Reformado": {
        "descricao": "Pessoas com reforma antecipada, idade entre 60 e 65 anos, pensão inferior ao salário mínimo nacional.",
        "preco": "14,35€",
        "custo_cartao": "5€",
        "prazo": "Até ao dia 18 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de Identificação", "Cópia da Declaração dos serviços de ação social da CMG"],
    },
    "Antigo Combatente": {
        "descricao": "Antigos combatentes ou viúvos de antigos combatentes.",
        "preco": "Gratuito",
        "custo_cartao": "5€",
        "prazo": "Até ao dia 18 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de Identificação", "Comprovativo do domicílio fiscal (Portal das Finanças)", "Cópia do Cartão Antigo Combatente/Viúva", "Requerimento IMT preenchido"],
    },
}

def verificar_documentos_passe(tipologia: str, ficheiros_carregados: dict):
    info = TIPOLOGIAS_PASSE[tipologia]
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
        logging.info(f"Verificação de documentos executada para tipologia '{tipologia}' ({len(nomes_documentos)} ficheiro(s)). Conteúdo dos documentos NÃO fica registado in log.")
        return resposta.text
    except Exception as e:
        logging.error(f"Erro na verificação de documentos: {e}")
        return f"Não foi possível verificar os documentos neste momento: {e}"

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
    return components.html(html_jogo, height=520)

# --- MENSAGEM INICIAL AUTOMÁTICA ---
MENSAGEM_INICIAL = """Olá, Celso! Sou o teu **Agente de Produtividade de Elite**. 

Estou pronto para te apoiar em três frentes:
1. **Modo Executivo:** Monitorização da frota Guimabus e consulta à Knowledge Base.
2. **Modo Tech Recruiter:** Diz-me *'Quero treinar para uma entrevista'* para simularmos testes técnicos em inglês.
3. **Modo Helpdesk Técnico:** Envia-me um problem de IT ou avaria e eu mostro-te como o Celso resolveria a situação.

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
                st.sidebar.success(resultado_scraping)
                
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
                    for linea in linhas_log: st.caption(linea.strip())

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
                Independentemente do problem de suporte indicado pelo utilizador (Active Directory, Redes, Sistemas, Avarias), deves começar a tua resposta OBRIGATORIAMENTE com a seguinte frase padrão: 
                'O Celso faria desta maneira para resolver este problema de IT:'
                Depois, detalha passos de troubleshooting técnicos, comandos em PowerShell ou Linux, e boas práticas applied com precisão."""

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

                agora = datetime.now()
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
                
                ferramentas_agente = [obter_dados_guimabus, obter_horarios_paragem, consultar_cache_horario_linha]
                
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
