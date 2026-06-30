import streamlit as st
import google.generativeai as genai
import requests

# Configuração da página
st.set_page_config(page_title="Super Secretário IA", page_icon="💼")
st.title("💼 O Teu Super Secretário de Produtividade")

# Configuração da API
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    st.error("Erro: Chave API em falta nos Secrets.")
    st.stop()

# --- FUNÇÕES DE CONTEXTO ---
def obter_dados_guimabus():
    # URL da API de tracking (verificada)
    url = "https://tracking.elevensystems.pt/api/gmr/vehicles"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            dados = response.json()
            if not dados: return "Nenhum autocarro detetado no momento."
            
            resumo = "Dados de frota em tempo real:\n"
            for bus in dados:
                resumo += f"- Autocarro {bus.get('id', 'N/A')}: Status {bus.get('busStatus', 'N/A')} (Atraso: {bus.get('delay', 0)}min)\n"
            return resumo
        else:
            return f"Erro de ligação: {response.status_code}"
    except Exception as e:
        return f"Tracking temporariamente indisponível. Erro: {e}"

def ler_ficheiros_pessoais():
    # Lê a biografia do Celso se o ficheiro existir
    try:
        with open("biografia.md", "r", encoding="utf-8") as f:
            return f"\n--- BIOGRAFIA DO CELSO ---\n{f.read()}"
    except FileNotFoundError:
        return "\n--- Nota: Ficheiro biografia.md não encontrado. ---"

# --- CONFIGURAÇÃO DO MODELO ---
PROMPT_SISTEMA = """
Tu és um Assistente Executivo de Elite. 
Sempre que o utilizador perguntar por algo, consulta primeiro o contexto fornecido (Bio e Dados de Tracking). 
Se perguntarem sobre o Celso Ferreira: Tem 34 anos, reside em Guimarães, profissional de Infraestrutura IT, Cloud e Automação, com certificação Google IT Support e Nível 4 em Automação.
"""

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- INTERFACE ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

model = genai.GenerativeModel("gemini-3.5-flash", system_instruction=PROMPT_SISTEMA)

# --- FLUXO DE CHAT ---
if prompt := st.chat_input("Como posso ajudar hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("A consultar dados..."):
            try:
                # Montar contexto enriquecido
                contexto = ler_ficheiros_pessoais()
                if any(word in prompt.lower() for word in ["autocarro", "horário", "tracking", "onde está"]):
                    contexto += "\n" + obter_dados_guimabus()
                
                prompt_enriquecido = f"{contexto}\n\nPergunta do Utilizador: {prompt}"
                response = model.generate_content(prompt_enriquecido)
                
                full_response = response.text
                st.markdown(full_response)
                
                # Botão de Download
                st.download_button("📥 Descarregar resposta (.txt)", full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.error(f"Erro ao processar: {e}")
