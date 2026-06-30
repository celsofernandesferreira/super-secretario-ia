import streamlit as st
import google.generativeai as genai
import requests
import os
import glob
import streamlit.components.v1 as components

# Configuração da página - Mantida a consistência com layout wide
# Configuração da página
st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="wide")
st.title("💼 O Teu Super Secretário de Produtividade")

# Configuração da API com tratamento de erros integrado
# --- INJEÇÃO DE CSS PARA ALINHAR O MICROFONE NA BARRA DE CHAT ---
st.markdown("""
    <style>
        /* Cria um contentor relativo na zona inferior da página */
        .stChatInputContainer {
            position: relative;
            padding-right: 60px !important;
        }
        /* Força o input de áudio a flutuar para o lado direito de forma absoluta */
        div[data-testid="stAudioInput"] {
            position: absolute;
            right: 15px;
            bottom: 4px;
            z-index: 999;
            width: auto !important;
        }
        /* Ajustes visuais para remover labels desnecessárias do microfone */
        div[data-testid="stAudioInput"] label {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

# Configuração da API
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
@@ -104,15 +127,13 @@
with st.sidebar:
    st.header("⚙️ Painel de Controlo")

    # Botão para Limpar Histórico
    if st.button("🗑️ Limpar Histórico de Conversa", use_container_width=True):
        st.session_state.messages = []
        st.session_state.jogo_ativo = False
        st.rerun()

    st.divider()

    # Botão para Ativar/Desativar o Jogo diretamente
    st.subheader("🕹️ Entretenimento")
    texto_botao_jogo = "Fechar Jogo X" if st.session_state.jogo_ativo else "Abrir Mini-Game 👾"
    if st.button(texto_botao_jogo, use_container_width=True):
@@ -132,20 +153,17 @@
"""

# --- INTERFACE PRINCIPAL ---
# O jogo é injetado no topo apenas se o botão correspondente na sidebar estiver ativo
if st.session_state.jogo_ativo:
    renderizar_jogo()

# Mostrar histórico de mensagens estruturadas
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CAPTURA DE ENTRADA (Múltiplas Opções: Texto ou Áudio) ---
# --- CAPTURA DE ENTRADA (Alinhadas por CSS) ---
prompt_texto = st.chat_input("Como posso ajudar hoje?")
audio_file = st.audio_input("Falar com o assistente")
audio_file = st.audio_input("Falar")

# Decidir qual o input válido a ser processado
prompt = None
if prompt_texto:
    prompt = prompt_texto
@@ -161,14 +179,12 @@
    with st.chat_message("assistant"):
        with st.spinner("A consultar dados..."):
            try:
                # 1. Integração Dinâmica da Knowledge Base e API Guimabus
                contexto = ler_knowledge_base()
                if any(word in prompt.lower() for word in ["autocarro", "horário", "tracking", "onde está"]):
                    contexto += "\n" + obter_dados_guimabus()

                prompt_enriquecido = f"{contexto}\n\nPergunta do Utilizador: {prompt}"

                # 2. Execução da Estratégia de Fallback (Resiliência)
                try:
                    model = genai.GenerativeModel("gemini-3.5-flash", system_instruction=PROMPT_SISTEMA)
                    response = model.generate_content(prompt_enriquecido)
@@ -183,7 +199,6 @@
                full_response = response.text
                st.markdown(full_response)

                # Elementos de fecho de interação
                st.download_button("📥 Descarregar (.txt)", full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
