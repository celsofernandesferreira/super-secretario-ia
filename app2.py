import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="centered")

st.title("💼 O Teu Super Secretário de Produtividade")
st.write("Cola notas desorganizadas ou faz uma pergunta sobre o criador desta IA!")

# Coloca a tua chave aqui
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)

PROMPT_SISTEMA = """
Tu és um Assistente de Produtividade Executivo de Elite e uma IA conversacional avançada. 

Deves analisar o que o utilizador escreve e adaptar a tua resposta a 3 cenários possíveis:

1. TAREFAS E NOTAS DESORGANIZADAS:
Se o utilizador colar textos longos, notas de reuniões ou pedir para organizar algo, aplica o teu formato de elite com 3 etapas:
- ETAPA 1: Lista de Tarefas (Action Items) por prioridade.
- ETAPA 2: Rascunho de email/mensagem (se aplicável).
- ETAPA 3: Resumo Executivo (2 a 3 linhas).

2. PERGUNTAS SOBRE O TEU CRIADOR:
Se perguntarem quem te criou, age como o representante oficial do Celso Ferreira. Responde de forma profissional: O Celso tem 34 anos, reside em Guimarães, e é um profissional focado em Infraestrutura IT, Cloud e Automação. Possui o Google IT Support Professional Certificate, certificação de Nível 4 em Automação e Sistemas Digitais, e estuda Engenharia Informática.

3. CONVERSA GERAL E DÚVIDAS:
Se o utilizador fizer uma pergunta normal (ex: perguntas de cultura geral, dúvidas de tecnologia, pedir concelhos, saber sobre uma cidade), ignora as regras acima e responde de forma natural, direta e prestável, como um assistente inteligente normal faria.
"""

### 👤 REGRA ESPECIAL: Perguntas sobre o Criador (Celso)
Se o utilizador perguntar sobre quem te criou, a experiência do Celso ou o seu perfil, deves ignorar as etapas acima e agir como o representante oficial do Celso Ferreira. 
Responde de forma profissional: O Celso tem 34 anos, reside em Guimarães, e é um profissional focado em Infraestrutura IT, Cloud e Automação. Possui o Google IT Support Professional Certificate, certificação de Nível 4 em Automação e Sistemas Digitais, e estuda Engenharia Informática. Tem experiência prática na criação de laboratórios corporativos com Windows Server, Active Directory e automação em PowerShell.
"""

texto_bruto = st.text_area("O que queres que eu organize (ou o que queres saber)?", height=150)

if st.button("Processar 🚀"):
    if GOOGLE_API_KEY == "COLA_AQUI_A_TUA_CHAVE_NOVA" or not GOOGLE_API_KEY:
        st.warning("⚠️ Ainda te falta colocar a tua chave gratuita da API no código!")
    elif not texto_bruto:
        st.info("Por favor, escreve ou cola algum texto primeiro.")
    else:
        with st.spinner("O agente está a raciocinar..."):
            try:
                model = genai.GenerativeModel(
                    model_name="gemini-3-flash-preview",
                    system_instruction=PROMPT_SISTEMA
                )
                response = model.generate_content(texto_bruto)
                
                st.success("✨ Trabalho Concluído:")
                st.markdown(response.text)
                
                # A Vingança: O Botão de Download
                st.download_button(
                    label="📥 Descarregar Plano de Ação (Ficheiro .txt)",
                    data=response.text,
                    file_name="plano_de_acao.txt",
                    mime="text/plain"
                )
            except Exception as e:
                st.error(f"Erro de ligação: {e}")
