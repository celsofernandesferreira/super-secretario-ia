# Super Secretário IA — Assistente de Elite (Guimabus / Recrutador / Projeto)

*Read this in English: [jump to the English version](##🇬🇧english-version) below.*

---

## 🇵🇹 Versão em Português

### Visão geral

Aplicação em **Streamlit** que funciona como agente de IA multi-modo, construída pelo **Celso Ferreira**,
usando a API do **Google Gemini** com *function calling* (chamadas de ferramentas em tempo real). O
objetivo é servir três públicos diferentes a partir da mesma interface de chat: utilizadores da rede de
transportes Guimabus, recrutadores interessados no percurso profissional do Celso, e qualquer pessoa
curiosa sobre como o próprio projeto foi construído.

A app deteta automaticamente, a partir das palavras da pergunta, qual dos três "modos" (personas/prompts
de sistema) deve responder — não há um menu de seleção manual.

### Os três modos

#### 1. Modo Guimabus (transportes)
Foco em automação e infraestrutura à volta da rede de autocarros da Guimabus, em Guimarães:
- Estado da frota em tempo real.
- Consulta de horários (com cache local, para não sobrecarregar os servidores oficiais a cada pedido).
- Planeamento de trajetos com transbordo — incluindo a partir de **qualquer local** (café, rua, morada),
  não só nomes exatos de paragens, resolvendo a localização primeiro pelo mapa estático e depois,
  em último recurso, por geocodificação em tempo real (OpenStreetMap/Nominatim).
- Consulta de tarifário e tipologias de passe, e verificação de documentos para pedidos de passe (usando
  o Gemini para analisar imagens/PDFs enviados).
- Uma **rede de segurança anti-alucinação**: perguntas sobre trajetos/horários passam por uma verificação
  que confirma se o modelo realmente chamou uma ferramenta real (em vez de responder "de cabeça"); se não
  chamou, o sistema força uma segunda tentativa em que é obrigado a consultar dados reais antes de
  responder. Isto existe porque, sem esta rede, o modelo por vezes inventava linhas e horários inteiros
  que não existiam.

#### 2. Modo Recrutador
Dirigido a quem quer conhecer o Celso profissionalmente:
- Responde sobre CV, competências e percurso, **sempre a partir da Knowledge Base** (ficheiros `.md` na
  pasta `knowledge/`) — nunca inventa datas, empresas ou tecnologias que não estejam documentadas.
- Se lhe disserem "quero treinar para uma entrevista", muda de papel e conduz uma simulação de entrevista
  técnica em inglês, uma pergunta de cada vez.
- Se lhe derem um problema técnico/de IT, demonstra como o Celso o resolveria, passo a passo — uma forma
  de um recrutador "ver" o raciocínio técnico do Celso em ação, sem precisar de o entrevistar ao vivo.

#### 3. Modo Projeto
Explica esta própria aplicação a quem perguntar — arquitetura, tecnologias usadas, propósito.

### Outras funcionalidades

- **Rodapé de avisos**: lê o feed RSS da página de Facebook da Guimabus, filtra e prioriza avisos —
  obras/eventos com data de fim conhecida mantêm-se ativos até essa data passar; posts genéricos ficam
  ativos ~1 semana. Tudo corre a rodar no rodapé via JavaScript, sem custo de API adicional.
- **Painel de administração** (sidebar, protegido por password) — força sincronizações manuais, consulta
  logs de auditoria, limpa o histórico da sessão.
- **Suporte bilingue** (PT/EN) — a interface e as respostas do agente adaptam-se ao idioma escolhido nos
  botões do topo.
- **Jogo escondido** com tabela de recordes — um extra lúdico incluído na app.

### Estrutura de ficheiros esperada

```
.
├── app.py                  # A aplicação (este ficheiro)
├── requirements.txt
├── geo_guimaraes.json      # Mapa estático de paragens e locais (lat/lon/tipo)
├── knowledge/              # Ficheiros .md com informação de referência (ex: CV do Celso)
│   └── *.md
├── agente_memoria.db       # Base de dados SQLite (criada/gerida automaticamente em runtime)
└── auditoria_agente.log    # Log de erros/auditoria (criado automaticamente)
```

### Configuração (Secrets)

No `.streamlit/secrets.toml` (ou nas *Secrets* do Streamlit Cloud):

```toml
GOOGLE_API_KEY = "a-tua-chave-da-api-do-gemini"
ADMIN_PASSWORD = "password-do-painel-de-admin"   # opcional, mas necessária para o painel de admin
```

### Instalação e execução local

```bash
pip install -r requirements.txt
streamlit run app.py
```

Na primeira execução (ou sempre que a cache tiver mais de 7 dias), a app entra automaticamente num modo
de "sincronização inicial" — descarrega e processa horários, tarifário e o índice de paragens antes de
libertar o chat para uso. Isto pode demorar 1–2 minutos.

### Arquitetura técnica (resumo)

| Componente | Tecnologia | Função |
|---|---|---|
| Interface | Streamlit | Chat, sidebar, formulários, rodapé |
| Modelo de IA | Google Gemini (function calling) | Conversação, decisão de qual ferramenta chamar. Cascata de resiliência: se `gemini-3.5-flash` falhar (ex: limite de *rate*), tenta automaticamente `gemini-3.1-flash-lite` e depois `gemini-2.5-flash` |
| Base de dados | SQLite (`agente_memoria.db`) | Cache de horários, tarifário, índice de paragens, histórico, high scores |
| Geolocalização | `geo_guimaraes.json` + OpenStreetMap/Nominatim | Localizar paragens e pontos de interesse |
| Scraping | `requests` + `pdfplumber` + `BeautifulSoup` | Ler PDFs oficiais de horários e o feed RSS do Facebook |
| Mapas | `folium` | Gerar mapas HTML de trajetos |
| Verificação de documentos | Gemini (visão) | Validar imagens/PDFs de pedidos de passe |

### Notas técnicas importantes

- **Anti-alucinação:** ver secção do Modo Guimabus acima — é o mecanismo mais importante da app do ponto
  de vista de fiabilidade.
- **Cache local:** horários, tarifários e índice de paragens ficam em cache no SQLite, sincronizados
  automaticamente a cada 7 dias (configurável em `check_sync_needed(limite_dias=7)`).
- **Localização de sítios:** usa primeiro o mapa estático (`geo_guimaraes.json`); se não encontrar,
  recorre a geocodificação em tempo real via OpenStreetMap/Nominatim como *fallback*.
- **Nomes de colunas SQL e chaves JSON permanecem em português** no código-fonte, mesmo na versão
  traduzida para inglês, por serem parte do formato de dados já persistido (ver `EXPLICACAO_DO_PROJETO.md`
  para detalhe completo desta decisão).

### Notas técnicas

- A geocodificação em tempo real (Nominatim) tem *rate limit* de 1 pedido/segundo do serviço público;
  os resultados são validados por relevância e ficam em cache 24h para reduzir pedidos repetidos.
- A deteção de qual "modo" usar é feita por palavras-chave, otimizada para os casos de uso mais comuns.
- O rodapé de avisos usa o `FetchRSS` para transformar a página de Facebook da Guimabus num feed RSS.
- O login de administrador usa `hmac.compare_digest` (comparação em tempo constante) e bloqueia o acesso
  por 5 minutos ao fim de 5 tentativas falhadas.

### 🗺️ Possíveis extensões futuras

- **Testes automatizados**: `recommend_pass_types` (motor de recomendação de passes) é lógica
  determinística, sem dependência da API — é o candidato ideal para os primeiros testes unitários
  (`pytest`), sem precisar de chave do Gemini nem de rede.
- **Indicador de frescura da cache na UI**: mostrar ao utilizador, por exemplo na sidebar, há quantos dias
  os horários/tarifário foram sincronizados pela última vez.
- **`requirements.txt` com versões fixadas** (`==x.y.z`), para reprodutibilidade do ambiente.
- **Ficheiro `LICENSE`** — ainda não definido; para um projeto de portefólio open-source, MIT é uma opção
  comum e permissiva.

### 👨‍💻 Autor

**Celso Ferreira** — à procura de oportunidades em IT / Informática.
🔗 [LinkedIn](https://www.linkedin.com/in/celso-ferreira-ab0830134/) | [GitHub](https://github.com/celsofernandesferreira)

Para uma explicação bloco a bloco de como o código funciona, consulta `EXPLICACAO_DO_PROJETO.md`.

---
---

## 🇬🇧 English Version

### Overview

A **Streamlit** application that works as a multi-mode AI agent, built by **Celso Ferreira**, using the
**Google Gemini** API with *function calling* (real-time tool calls). Its goal is to serve three
different audiences from the same chat interface: users of the Guimabus public transport network,
recruiters interested in Celso's professional background, and anyone curious about how the project itself
was built.

The app automatically detects, from the wording of the question, which of the three "modes"
(personas/system prompts) should answer — there is no manual mode-selection menu.

### The three modes

#### 1. Guimabus Mode (public transport)
Focused on automation and infrastructure around the Guimabus bus network in Guimarães, Portugal:
- Real-time fleet status.
- Schedule lookups (locally cached, so the official servers aren't hit on every request).
- Route planning with transfers — including from **any place** (café, street, address), not just exact
  stop names, resolving the location first via the static map and, as a last resort, via live geocoding
  (OpenStreetMap/Nominatim).
- Fare table and pass type lookups, plus document verification for pass applications (using Gemini to
  analyse uploaded images/PDFs).
- An **anti-hallucination safety net**: questions about routes/schedules go through a check that confirms
  whether the model actually called a real tool (instead of answering "off the top of its head"); if it
  didn't, the system forces a second attempt where it is required to consult real data before answering.
  This exists because, without this safety net, the model would sometimes invent entire bus lines and
  schedules that didn't exist.

#### 2. Recruiter Mode
Aimed at anyone who wants to get to know Celso professionally:
- Answers questions about his CV, skills and background, **always sourced from the Knowledge Base**
  (`.md` files in the `knowledge/` folder) — it never invents dates, companies or technologies that
  aren't documented.
- If told "I want to train for an interview", it switches roles and runs a technical interview simulation
  in English, one question at a time.
- If given a technical/IT problem, it demonstrates step by step how Celso would solve it — a way for a
  recruiter to "see" Celso's technical reasoning in action without a live interview.

#### 3. Project Mode
Explains this very application to anyone who asks — architecture, technologies used, purpose.

### Other features

- **Notices footer**: reads the RSS feed from the Guimabus Facebook page, filters and prioritises
  notices — roadworks/events with a known end date stay active until that date passes; generic posts
  stay active for ~1 week. Everything scrolls in the footer via JavaScript, with no extra API cost.
- **Admin panel** (sidebar, password-protected) — forces manual syncs, checks audit logs, clears the
  session history.
- **Bilingual support** (PT/EN) — the interface and the agent's replies adapt to the language chosen via
  the buttons at the top.
- **Hidden mini-game** with a leaderboard — a fun extra bundled with the app.

### Expected file structure

```
.
├── app.py                  # The application (this file)
├── requirements.txt
├── geo_guimaraes.json      # Static map of stops and places (lat/lon/type)
├── knowledge/              # .md files with reference information (e.g. Celso's CV)
│   └── *.md
├── agente_memoria.db       # SQLite database (automatically created/managed at runtime)
└── auditoria_agente.log    # Error/audit log (created automatically)
```

### Configuration (Secrets)

In `.streamlit/secrets.toml` (or in Streamlit Cloud's *Secrets*):

```toml
GOOGLE_API_KEY = "your-gemini-api-key"
ADMIN_PASSWORD = "admin-panel-password"   # optional, but required for the admin panel
```

### Local installation and run

```bash
pip install -r requirements.txt
streamlit run app.py
```

On first run (or whenever the cache is older than 7 days), the app automatically enters an "initial sync"
mode — it downloads and processes schedules, fares and the stop index before releasing the chat for use.
This can take 1–2 minutes.

### Technical architecture (summary)

| Component | Technology | Role |
|---|---|---|
| Interface | Streamlit | Chat, sidebar, forms, footer |
| AI model | Google Gemini (function calling) | Conversation, deciding which tool to call. Resilience cascade: if `gemini-3.5-flash` fails (e.g. rate limit), it automatically retries with `gemini-3.1-flash-lite` and then `gemini-2.5-flash` |
| Database | SQLite (`agente_memoria.db`) | Schedule/fare cache, stop index, chat history, high scores |
| Geolocation | `geo_guimaraes.json` + OpenStreetMap/Nominatim | Finding stops and points of interest |
| Scraping | `requests` + `pdfplumber` + `BeautifulSoup` | Reading official schedule PDFs and the Facebook RSS feed |
| Maps | `folium` | Generating HTML route maps |
| Document verification | Gemini (vision) | Validating images/PDFs for pass applications |

### Important technical notes

- **Anti-hallucination:** see the Guimabus Mode section above — this is the app's most important
  mechanism from a reliability standpoint.
- **Local cache:** schedules, fares and the stop index are cached in SQLite, automatically synced every 7
  days (configurable in `check_sync_needed(limite_dias=7)`).
- **Finding places:** the static map (`geo_guimaraes.json`) is tried first; if not found, it falls back
  to live geocoding via OpenStreetMap/Nominatim.
- **SQL column names and JSON keys remain in Portuguese** in the source code, even in the English-
  translated version, because they are part of an already-persisted data format (see
  `EXPLICACAO_DO_PROJETO.md` for the full reasoning behind this decision).

### Technical notes

- Live geocoding (Nominatim) has a rate limit of 1 request/second on the public service; results are
  validated for relevance and cached for 24h to reduce repeated calls.
- Which "mode" to use is detected via keywords, tuned for the most common use cases.
- The notices footer uses `FetchRSS` to turn the Guimabus Facebook page into an RSS feed.
- Admin login uses `hmac.compare_digest` (constant-time comparison) and locks access for 5 minutes after
  5 failed attempts.

### 🗺️ Possible future extensions

- **Automated tests**: `recommend_pass_types` (the pass-recommendation engine) is deterministic logic
  with no API dependency — it's the ideal candidate for the first unit tests (`pytest`), with no need
  for a Gemini key or network access.
- **Cache-freshness indicator in the UI**: show the user, e.g. in the sidebar, how many days it's been
  since schedules/fares were last synced.
- **Pin versions in `requirements.txt`** (`==x.y.z`) for reproducible environments.
- **Add a `LICENSE` file** — not yet defined; for an open-source portfolio project, MIT is a common,
  permissive choice.

### 👨‍💻 Author

**Celso Ferreira** — looking for IT / Computer Science opportunities.
🔗 [LinkedIn](https://www.linkedin.com/in/celso-ferreira-ab0830134/) | [GitHub](https://github.com/celsofernandesferreira)

For a block-by-block explanation of how the code works, see `EXPLICACAO_DO_PROJETO.md`.
