# Explicação Completa do Projeto — `app.py`

*Read this in English: [jump to the English version](#english-version) below.*

---

## 🇵🇹 Versão em Português

Este documento explica, **com o máximo de detalhe possível**, o que cada função e bloco de `app.py`
faz, incluindo algoritmos exatos, queries SQL, casos-limite e decisões de desenho — não só um resumo de
alto nível. A ordem segue a ordem do próprio ficheiro.

### Índice
1. Imports
2. `UI_TEXT` — dicionário de idiomas
3. Configuração de logs
4. Base de dados SQLite — esquema completo
5. Sistema de pesquisa e geolocalização
6. Configuração da página, idiomas e Gemini
7. Rodapé de avisos via RSS do Facebook
8. Ferramentas de frota em tempo real
9. Scraping de PDFs de horários + cache (inclui Knowledge Base e diagnósticos de cache)
10. Funções geográficas (Overpass, Folium, Google Maps)
11. Bloqueio de sincronização no arranque
12. Scraping de tipologias de passe e tarifário
13. Índice paragem ↔ linha
14. Planeamento de viagens (motor de transbordos)
15. Passes, tarifário e verificação de documentos
16. Jogo escondido
17. Sidebar administrativa
18. Loop principal do chat e rede anti-alucinação
19. Notas técnicas e possíveis extensões futuras

---

### 1. Imports

`streamlit` desenha toda a interface. `google.generativeai` é o SDK oficial do Gemini. `requests` faz
todos os pedidos HTTP externos (RSS, geocoding Nominatim, Overpass, PDFs oficiais, API de tracking da
Guimabus). `sqlite3` gere a base de dados local `agente_memoria.db` (sem ORM — todas as queries são SQL
puro escrito à mão). `pdfplumber` extrai texto de PDFs preservando o layout (`extract_text(layout=True)`),
o que é essencial para conseguir "ler" tabelas de horários com colunas alinhadas. `folium` gera mapas
Leaflet em HTML puro. `bs4.BeautifulSoup` faz *parsing* tanto de HTML (páginas da Guimabus) como de XML
(feed RSS). Os restantes módulos (`re`, `json`, `math`, `unicodedata`, `datetime`, `zoneinfo`,
`email.utils`, `time`, `io`, `os`, `glob`, `logging`) são da biblioteca padrão do Python — não entram no
`requirements.txt`.

### 2. `UI_TEXT` — dicionário de idiomas

Um dicionário com duas chaves de topo, `"PT"` e `"EN"`, cada uma com dezenas de pares chave→string,
cobrindo **cada** texto visível na interface: título da página, texto de boas-vindas
(`initial_msg`), rótulos de botões da sidebar, mensagens de erro (password incorreta, erro de áudio),
textos do jogo, textos do assistente de pedido de passe, etc. Quando o utilizador clica num botão de
idioma, `st.session_state.language` muda e a app faz `st.rerun()`; no recarregamento,
`ui = UI_TEXT[st.session_state.language]` seleciona o dicionário certo e todo o resto do script usa `ui[...]`
em vez de strings soltas. Isto significa que **acrescentar um novo texto à interface obriga sempre a
adicionar a chave correspondente em ambos os blocos `"PT"` e `"EN"`**, ou a chave falha com `KeyError`
num dos dois idiomas.

### 3. Configuração de logs

```python
logging.basicConfig(filename="auditoria_agente.log", level=logging.INFO, ...)
```
(configuração exata na secção 1 do ficheiro). Todos os `except Exception as e: logging.error(...)`
espalhados pelo código escrevem aqui. Como muitas funções devolvem uma mensagem de erro amigável ao
utilizador/modelo *e* registam o erro técnico completo no log, este ficheiro é a única forma de ver a
`Exception` real (stack trace/mensagem completa) quando algo falha silenciosamente. É lido diretamente
pelo painel de administrador (secção 18), que mostra as últimas 10 linhas.

### 4. Base de dados SQLite — esquema completo

`initialize_db()` corre uma vez no arranque (chamada incondicional logo a seguir à sua definição, linha
340) e cria estas tabelas, todas com `CREATE TABLE IF NOT EXISTS` (seguro para correr sempre):

| Tabela | Colunas | Propósito |
|---|---|---|
| `historico_global` | `id, timestamp, session_id, role, content` | Histórico permanente de todas as mensagens de chat de todas as sessões |
| `high_scores` | `id, timestamp, nome, pontor` | Tabela de recordes do jogo escondido |
| `cache_horarios` | `linha (PK), url, conteudo_txt, ultima_atualizacao` | Texto extraído dos PDFs oficiais de horários, por linha |
| `cache_titulos` | `tipologia (PK), descricao, preco, custo_cartao, prazo, documentos_json, ultima_atualizacao` | Tipologias de passe (scraped da página oficial) |
| `cache_tarifario` | `id (PK, sempre 1), url_pdf, conteudo_txt, ultima_atualizacao` | Texto do PDF de tarifário (tabela única, um único registo) |
| `cache_paragens_linha` | `linha, paragem, PK(linha, paragem)` | Índice linha↔paragem, construído a partir de `cache_horarios` |
| `cache_titulo_linha` | `linha (PK), titulo, ultima_atualizacao` | Título/descrição textual de cada linha (extraído do link na página principal) |
| `cache_paragem_freguesia` | `paragem (PK), freguesia, fonte, ultima_atualizacao` | Associação paragem→freguesia (via geocoding) |
| `nos_geograficos` | `id, tipo, nome, freguesia, latitude, longitude, linhas_associadas, ultima_atualizacao` | Índice geográfico geral: POIs e ruas importados via Overpass |

Também é criado um índice: `CREATE INDEX idx_nome_nos ON nos_geograficos(nome)`.

`save_message_db(session_id, role, content)` insere uma linha em `historico_global` com o timestamp
atual (`%Y-%m-%d %H:%M:%S`). `get_top_10()` lê `high_scores` ordenado por `pontor DESC, id ASC`, limitado
a 10. `save_score_db(nome, pontor)` insere um novo recorde. As três funções envolvem toda a lógica em
`try/except`, devolvendo uma lista vazia (no caso de leitura) ou simplesmente não gravando (no caso de
escrita) em caso de erro, sempre registando no log.

**Nota de compatibilidade crítica:** todos os nomes de tabelas e colunas acima (`linha`, `paragem`,
`tipo`, `nome`, `freguesia`, `preco`, etc.) ficam **sempre em português**, mesmo depois de o resto do
código ter sido traduzido para inglês. A `agente_memoria.db` que já existe em produção tem estas colunas
gravadas fisicamente no ficheiro `.db`; traduzir os nomes no código faria com que todas as queries
deixassem de bater certo com o esquema real, partindo a aplicação inteira sem aviso prévio (erro
`sqlite3.OperationalError: no such column`).

### 5. Sistema de pesquisa e geolocalização rápida

O "cérebro geográfico" da app — o bloco mais afinado ao longo do desenvolvimento.

- **`normalize_search_name(texto)`** — pipeline de normalização geral: minúsculas → remove acentos via
  `unicodedata.normalize('NFKD', ...)` seguido de filtragem de caracteres combinantes → substitui
  qualquer caractere não-alfanumérico por `_` (`re.sub(r'[^a-z0-9]', '_', t)`) → colapsa `_` repetidos →
  remove `_` nas pontas. Ex: `"Café Rio!"` → `"cafe_rio"`.
- **`looks_like_route_request(texto)`** — normaliza o texto e o transforma em `" palavra1 palavra2 ... "`
  (com espaços a rodear, para permitir `in` sem falsos positivos de substring parcial), depois verifica
  se alguma palavra da lista `_ROUTE_KEYWORDS_PT` (ver secção 19) aparece lá dentro. Esta lista inclui
  termos como "linha", "horario", "paragem", "onde fica", "como vou", "café" — propositadamente ampla,
  para capturar tanto pedidos de trajeto explícitos como perguntas de localização como "onde fica o café
  rio", que também precisam de passar por uma ferramenta real.
- **`load_static_map()` / `LOCAL_MAP`** — lê `geo_guimaraes.json` uma única vez (decorado com
  `@st.cache_data`, sem `ttl`, ou seja, fica em cache até a sessão do Streamlit reiniciar) para um
  dicionário Python em memória: `LOCAL_MAP = load_static_map()`. Cada entrada tem a forma
  `{"lat": ..., "lon": ..., "nome_real": ..., "tipo": ...}`. Se o ficheiro não existir ou for inválido,
  devolve `{}` e regista o erro — a app não crasha, mas todas as pesquisas no mapa estático falham
  silenciosamente a partir daí.
- **`calculate_distance(lat1, lon1, lat2, lon2)`** — fórmula de Haversine completa (raio da Terra
  `R = 6371.0` km), devolve a distância em **metros** (multiplica o resultado em km por 1000).
- **`_search_local_map(local_nome)`** — algoritmo de pontuação por sobreposição de palavras: normaliza o
  termo pesquisado, transforma em conjunto de tokens (`set(chave_pesquisa.split("_"))`); para cada
  entrada do `LOCAL_MAP`, calcula `pontuacao = len(tokens_comuns) / len(tokens_pesquisa)`; guarda a
  entrada com maior pontuação; só aceita o resultado se `pontuacao >= 0.5` (pelo menos metade das
  palavras pesquisadas encontradas). Isto é o que permite que "café rio" encontre "Café do Rio" mesmo
  sem correspondência exata.
- **`_geocode_nominatim_place(local_nome)`** — chamada `GET` a
  `https://nominatim.openstreetmap.org/search` com `q=f"{local_nome}, Guimarães, Portugal"`,
  `format=json`, `limit=1`, timeout de 8s, com um `User-Agent` customizado (Nominatim exige um
  User-Agent identificável, caso contrário bloqueia o pedido). Devolve `{"nome_real", "lat", "lon"}` a
  partir do primeiro resultado, ou `None` se não houver resultados ou a chamada falhar.
- **`find_nearest_stop(local_nome)`** — orquestra tudo: tenta `_search_local_map`; se falhar, tenta
  `_geocode_nominatim_place`; se ambos falharem, devolve uma mensagem `"⚠️ NOT CONFIRMED: ..."` (o marcador
  exato que o prompt de sistema instrui o modelo a repetir ao utilizador). Se encontrar o local, percorre
  **todas** as entradas do `LOCAL_MAP` cujo `tipo` seja `"bus_stop"` ou `"public_transport"`, calcula a
  distância a cada uma com `calculate_distance`, e guarda a mais próxima. Se a distância for superior a
  1500 metros, avisa explicitamente que a distância é elevada e pode não ser fiável. A mensagem final
  inclui uma nota extra se a fonte da localização tiver sido o Nominatim em tempo real (menos fiável do
  que o mapa oficial).
- **`search_places_by_type(tipo_local, limite=20)`** — normaliza o tipo pesquisado, percorre todo o
  `LOCAL_MAP` comparando com o campo `tipo` de cada entrada (correspondência bidirecional por substring:
  `tipo_norm in tipo_dado_norm or tipo_dado_norm in tipo_norm`), devolve até `limite` nomes ordenados
  alfabeticamente, com uma nota se houver mais resultados do que os mostrados.

### 6. Configuração da página, idiomas, CSS e Gemini

`st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="wide")` tem de ser sempre o
primeiro comando Streamlit. Os botões de idioma são desenhados como dois `st.empty()` (`lang_pt_slot`,
`lang_en_slot`) dentro de `st.columns([12, 1, 1])`, ao lado do título — os botões clicáveis reais só são
inseridos nesses *slots* mais tarde (secção 18), depois de o bloqueio de arranque libertar a execução.
Segue-se a captura de recordes via parâmetros de URL (`st.query_params`), a injeção de CSS para a caixa
de chat e o botão de gravação de áudio, e por fim `genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])`
dentro de um `try/except` que, em caso de falha (chave em falta), mostra erro e chama `st.stop()`
imediatamente — nenhuma linha seguinte do script corre nesse caso.

### 7. Rodapé de avisos via RSS do Facebook

**`extract_future_date(texto)`** — usa um dicionário `PT_MONTHS` (nomes de meses em português, incluindo
abreviações como "jan", "fev") para reconhecer datas escritas por extenso, mais um padrão *regex* para
datas numéricas (`dd/mm` ou `dd-mm`, opcionalmente com ano). Percorre todas as datas encontradas no texto
e devolve a **mais tardia**, já como `datetime`. Devolve `None` se não encontrar nenhuma.

**`get_facebook_notices()`** — decorada com `@st.cache_data(ttl=3600)` (só faz o pedido HTTP real uma vez
por hora). Faz `requests.get` ao feed RSS (`FetchRSS`, o serviço que transforma a página de Facebook da
Guimabus num feed RSS), usa `BeautifulSoup(response.content, "xml")` para
percorrer até 30 `<item>`. Para cada item:
1. Extrai `title`, `description`/`content:encoded`, limpa tags HTML e junta título+descrição em
   `texto_minusculas` (tudo em minúsculas, para comparação).
2. Extrai a imagem, se houver `<enclosure>`.
3. Guarda uma cópia em `todos_avisos` (plano B, sem qualquer filtro).
4. Se contiver "resolvido", "terminado", "já passou" ou "reaberto" → `continue` (ignora completamente).
5. Chama `extract_future_date`. Se encontrar data futura confirmada e ainda não passada: **Tier 1** —
   prioridade = `1000 - dias_ate_fim` (+50 se tiver palavra crítica: "obra", "greve", "corte",
   "condicionamento", "interrupção", "aviso", "urgente"); mantém-se ativo até essa data passar.
6. Se não encontrar data: **Tier 2** — calcula `dias_passados` a partir do `<pubDate>` do RSS; se
   `dias_passados > 7`, `continue` (ignora); caso contrário prioridade = `7 - dias_passados` (+20 se
   crítico).
7. No final: ordena `avisos_ativos` por prioridade decrescente; se ficar vazio mas `todos_avisos` não,
   devolve os 2 mais recentes deste último (plano B); caso contrário devolve **toda** a lista
   `avisos_ativos`, sem limite de tamanho.

**`render_notices_footer(anuncios_ativos, ui)`** — se a lista vier vazia, `return` imediato (nada é
desenhado, sem erro visível). Caso contrário, monta um bloco HTML/CSS/JS injetado via
`components.html(html_rodape, height=170)` — corre **dentro de um iframe isolado**. Os avisos são
serializados como JSON (`json.dumps`) diretamente para uma variável JavaScript `anuncios`; a função
`correrAviso()` usa `setTimeout` para percorrer o array e atualizar o DOM (texto, imagem), tudo no lado
do cliente, sem custo de API adicional. Por correr num iframe, `position: fixed` no CSS é relativo ao
iframe, não à janela do browser — o rodapé fica onde este componente é chamado no fluxo da página.

### 8. Ferramentas de frota em tempo real

**`_extract_vehicle_list(dados)`** — normaliza a resposta da API, que pode vir como lista direta ou
dentro de um dicionário sob várias chaves possíveis (`"vehicles"`, `"data"`, `"results"`, `"items"`,
`"veiculos"`); se nenhuma bater, procura qualquer valor do dicionário que seja uma lista.

**`_first_value(dicionario, chaves, default=None)`** — devolve o primeiro valor não-`None` entre uma
lista de chaves candidatas (útil porque a API pode nomear o mesmo campo de formas diferentes consoante a
versão do endpoint, ex: `"id"`, `"vehicleId"`, `"vehicle_id"`, `"code"`).

**`DICIONARIO_PARAGENS_CONHECIDAS`** — um pequeno dicionário fixo de atalhos (`"vaca negra": "1103"`,
`"central": "1001"`, `"hospital": "1045"`, `"universidade": "1022"`, `"estacao": "1005"`) para mapear
nomes coloquiais a IDs numéricos reais de paragem na API da Guimabus.

**`get_guimabus_data(route_id=None)`** — decorada com `@st.cache_data(ttl=60)`. Chama
`GET https://gmr.elevensystems.pt/api/locations` com `passengerInfo=true` (e `routeId` se especificado),
timeout de 8s. Para cada veículo devolvido, monta uma linha de resumo com ID, linha, estado e atraso
(usando `_first_value` para tolerar formatos diferentes), e calcula a média de atraso da frota entre os
veículos que reportam esse dado.

**`get_stop_schedule(stop_id)`** — decorada com `@st.cache_data(ttl=30)`. Primeiro tenta mapear o texto
de entrada via `DICIONARIO_PARAGENS_CONHECIDAS`; se o resultado for um ID numérico (ou o próprio input já
for dígitos), chama `GET https://gmr.elevensystems.pt/api/stops/{id}/routes` para obter previsões em
tempo real. **Se isso falhar ou não se aplicar**, cai num *fallback* que faz uma pesquisa textual direta
na cache SQLite: remove *stopwords* portuguesas comuns do texto de entrada (regex com uma lista de
palavras como "estou", "na", "no", "em", "paragem", etc.), usa os termos restantes para construir uma
query `SELECT linha, conteudo_txt FROM cache_horarios WHERE conteudo_txt LIKE ? AND conteudo_txt LIKE ? ...`
(uma condição `LIKE` por termo, todas com `AND`), e para cada linha encontrada extrai só as linhas de
texto que contêm algum dos termos ou as palavras "página"/"tabela", limitando a 25 linhas de contexto.

### 9. Scraping de PDFs de horários + cache

**`sync_all_guimabus_schedules()`** — o processo mais pesado da app. Faz `GET` a
`https://guimabus.pt/horarios-linhas/`, faz *parsing* com `BeautifulSoup(response.text, 'html.parser')`,
percorre todos os `<a href>` que contenham `.pdf` e `horario` no link, extrai o ID da linha via regex
`r'linha-([a-z0-9]+)'` aplicada ao *href* em minúsculas, e guarda também o texto visível do link como
"título" da linha (`titulos_linha`). Para cada linha encontrada:
1. Até 2 tentativas (`for tentativa in range(2)`), com 1 segundo de espera entre elas em caso de falha.
2. Descarrega o PDF (`timeout=20`), verifica `status_code == 200`.
3. Extrai texto **de cada página** com `pagina.extract_text(layout=True)` (preserva alinhamento de
   colunas — essencial para as tabelas de horas), prefixando cada página com `[PÁGINA N]`.
4. Se não conseguir extrair texto nenhum, grava `"PDF em formato de imagem ou protegido contra leitura."`
   como conteúdo (em vez de falhar).
5. Grava em `cache_horarios` via `INSERT OR REPLACE` (chave primária é `linha`, por isso cada
   re-sincronização substitui o registo anterior por completo) e, se houver título, também em
   `cache_titulo_linha`.
6. Entre cada linha processada, `time.sleep(0.4)` — um *rate limit* manual para não sobrecarregar o
   servidor da Guimabus com pedidos em rajada.

Devolve uma mensagem final com a contagem de sucessos/falhas.

**`query_line_schedule_cache(linha_id)`** — normaliza o ID de entrada para maiúsculas; se for só dígitos,
gera candidatos alternativos (sem zeros à esquerda, e com 3 dígitos com zeros à esquerda —
`entrada.zfill(3)`), para tolerar o utilizador escrever "5" quando a linha está gravada como "005" ou
vice-versa. Testa cada candidato na tabela até encontrar um resultado.

**`load_knowledge_base()`** — `glob.glob("knowledge/*.md")`, lê cada ficheiro e concatena todo o
conteúdo, prefixado com `--- CONTEÚDO DE {nome_do_ficheiro} ---`. Este texto é injetado no contexto de
**todas** as chamadas ao Gemini, independentemente do modo ativo.

**`get_schedule_cache_age_days` / `get_pass_cache_age_days`** — fazem `SELECT MAX(ultima_atualizacao)`
na respetiva tabela e calculam `(datetime.now() - ultima).days`. **`get_stop_index_count`** faz
`SELECT COUNT(*) FROM cache_paragens_linha`. Estas três alimentam diretamente `check_sync_needed`
(secção 12).

### 10. Funções geográficas: Overpass, Folium, Google Maps

**`import_guimaraes_pois()`** — envia uma query em linguagem Overpass QL (`[out:json][timeout:25]`) para
`https://overpass-api.de/api/interpreter`, pedindo nós dentro da área "Guimarães" com tags `amenity`
(hospital, clínica, médico, farmácia, café, restaurante, escola, universidade), `tourism` (museu,
atração, monumento) ou `shop` (supermercado, centro comercial, padaria). Para cada elemento devolvido com
nome e coordenadas, insere em `nos_geograficos` com `tipo = f"poi_{tipo_poi}"` (ex: `"poi_cafe"`), usando
`INSERT OR IGNORE` (não duplica se já existir com a mesma chave — embora repare-se que esta tabela não
tem uma *constraint* `UNIQUE` explícita além do `id` autoincrement, por isso `INSERT OR IGNORE` aqui não
impede duplicados reais; é mais uma proteção contra chaves primárias repetidas do que contra dados
duplicados).

**`import_parish_streets(nome_freguesia)`** — query Overpass semelhante, mas para `way["highway"]`
(ruas) dentro da interseção de duas áreas (Guimarães + a freguesia específica), usando um `set()` para
não gravar o mesmo nome de rua duas vezes na mesma execução.

**`generate_line_map_html(linha_id)`** — faz uma query SQL com `JOIN` entre `cache_paragens_linha` e
`nos_geograficos`, comparando os nomes **normalizados** de ambos os lados:
```sql
SELECT p.paragem, g.latitude, g.longitude, g.freguesia 
FROM cache_paragens_linha p
JOIN nos_geograficos g ON _normalize_stop_name(p.paragem) = _normalize_stop_name(g.nome)
WHERE p.linha = ? AND g.latitude IS NOT NULL
```
Desenha um `folium.Map` centrado na primeira paragem, com um marcador por paragem (ícone de autocarro) e
uma `PolyLine` a ligar todas as coordenadas por ordem, gravando o resultado como
`maps/linha_{linha_id}.html`.

> **Nota de implementação:** esta query SQL chama `_normalize_stop_name(...)` diretamente dentro do texto
> SQL, como se fosse uma função nativa do SQLite. Para isso funcionar, a função Python
> `_normalize_stop_name` é registada explicitamente no SQLite via
> `conn.create_function("_normalize_stop_name", 1, _normalize_stop_name)` logo a seguir a cada
> `sqlite3.connect(...)` que a usa, antes de executar a query — tanto em `generate_line_map_html` como em
> `generate_google_maps_link`.

**`generate_google_maps_link(local_nome)`** — cadeia de fallback em 3 níveis: (1) `_search_local_map`
(mapa estático); (2) query SQL a `nos_geograficos` com o mesmo padrão `_normalize_stop_name(...)` dentro
do SQL (mesma técnica referida acima); (3) `_geocode_nominatim_place` (tempo real). Devolve sempre um link no
formato `https://www.google.com/maps/search/?api=1&query={lat},{lon}`, com uma nota indicando a fonte
usada — e um aviso explícito de "não confirmado" quando a fonte é o Nominatim em tempo real.

### 11. Bloqueio de sincronização no arranque

**`check_sync_needed(limite_dias=7)`** — usa `st.session_state.get("sync_checked")` como *flag* para só
correr esta verificação uma vez por sessão (evita recalcular em cada interação do utilizador). Calcula
independentemente:
- `needs_sch` — se a cache de horários não existe ou tem `>= limite_dias` dias.
- `needs_idx` — se `get_stop_index_count() == 0`.
- `needs_tkt` — se a cache de tipologias não existe ou tem `>= limite_dias` dias.
- `needs_geo` — se `SELECT COUNT(*) FROM nos_geograficos WHERE tipo LIKE 'poi_%'` for zero.

Se qualquer uma for verdadeira, marca `st.session_state.is_updating = True` e guarda um dicionário
`update_tasks` com as *flags* individuais — isto permite ao bloco de arranque (secção 18) correr **só**
as sincronizações necessárias, não todas de cada vez.

### 12. Scraping de tipologias de passe e tarifário

**`sync_guimabus_pass_types()`** — faz `GET` a `https://guimabus.pt/titulos/`, remove tags irrelevantes
(`nav`, `footer`, `form`, `script`, `style`) do HTML antes de extrair texto, e depois divide o texto
completo em blocos usando a *string* literal `"\nPASSE\n"` como separador (assume que a página tem a
palavra "PASSE" a marcar o início de cada tipologia). Para cada bloco, corre uma pequena **máquina de
estados** linha a linha (`parsing_mode` alterna entre `"desc"`, `"prazo"`, `"preco"`, `"cartao"`,
`"docs"`, `"done"`), detetando frases-chave como `"preço:"`, `"custo do cartão:"`,
`"documentos necessários:"`, `"só podem ser"`/`"até ao dia"` (para o prazo), e acumulando o resto como
descrição. Grava tudo em `cache_titulos` via `INSERT OR REPLACE`, com os documentos necessários serializados
como JSON (`json.dumps(documentos, ensure_ascii=False)`).

**`sync_guimabus_fare_table()`** — faz `GET` a `https://guimabus.pt/tarifarios/`, procura um link PDF
cujo *href* contenha "tarifa" ou "tabela"; se não encontrar nenhum específico, usa o primeiro PDF que
encontrar na página como *fallback*. Extrai o texto do PDF da mesma forma que
`sync_all_guimabus_schedules`, e grava num único registo (`id = 1`) da tabela `cache_tarifario`.

**`sync_pass_types_and_fares()`** — chama as duas anteriores em sequência e concatena as mensagens de
resultado.

`TIPOLOGIAS_PASSE_FALLBACK` é um dicionário fixo com uma única tipologia ("Mensal") usado como resposta
de emergência em `get_pass_types_cache()` se a tabela `cache_titulos` estiver completamente vazia — para
a app nunca ficar sem nenhuma opção de passe para mostrar.

### 13. Índice paragem ↔ linha

**`_extract_stops_from_text(texto)`** — o coração da extração de paragens a partir do texto scraped dos
PDFs. Usa uma *regex* que procura linhas terminadas em pelo menos 3 "campos de horário" (cada campo é um
`-` literal ou uma hora no formato `HH:MM`), interpretando tudo antes disso como o nome da paragem:
```
^(?P<nome>.+?)\s+(?P<horarios>(?:-|\d{1,2}:\d{2})(?:\s+(?:-|\d{1,2}:\d{2})){2,})\s*$
```
Ignora linhas que contenham `|` (normalmente cabeçalhos/separadores de tabela) ou comecem por
`[PÁGINA`/`[P`. Só aceita nomes com pelo menos 3 caracteres.

**`build_stop_index()`** — apaga completamente `cache_paragens_linha` (`DELETE FROM ...`) e
reconstrói-a do zero a partir de `cache_horarios`, chamando `_extract_stops_from_text` para cada linha e
inserindo cada par (linha, paragem) com `INSERT OR IGNORE` (a chave primária composta `(linha, paragem)`
evita duplicados).

**`_normalize_stop_name(texto)`** — uma normalização **mais rica** do que `normalize_search_name`,
específica para nomes de paragens: substitui "são" por "s.", "santa" por "sta.", "santo" por "sto." (com
`\b` para não afetar substrings), depois remove todos os pontos, remove acentos, colapsa espaços. Isto
existe porque os PDFs oficiais escrevem estes prefixos de forma inconsistente (às vezes "São Torcato",
às vezes "S. Torcato").

**`_search_lines_by_title(termo_norm)`** — *fallback* usado quando uma paragem não é encontrada
diretamente: procura o termo pesquisado dentro do **título** de cada linha (`cache_titulo_linha`), útil
quando o utilizador escreve o nome de uma zona/freguesia que aparece no título da linha mas não como
nome exato de paragem (ex: "Linha Guimarães-Gonça via S. Torcato").

**`enrich_stops_with_parish(progresso_callback=None)`** — para cada paragem em `cache_paragens_linha`
que ainda não tenha entrada em `cache_paragem_freguesia`, faz um pedido a
`https://nominatim.openstreetmap.org/search` (com `countrycodes=pt`, `addressdetails=1`), extraindo a
freguesia do primeiro resultado a partir dos campos `suburb`, `city_district`, `village`, `town` ou
`municipality` (por esta ordem de preferência). Grava o resultado mesmo quando não encontra nada
(`fonte = "sem_resultado"`), para não voltar a tentar essa paragem em execuções futuras. Respeita o
*rate limit* do Nominatim com `time.sleep(1.1)` entre pedidos — para ~200 paragens, isto demora
~4 minutos, daí o `progresso_callback` opcional para mostrar uma barra de progresso na sidebar.

**`get_parish_of_stop` / `search_stops_by_parish`** — consultas de leitura simples sobre
`cache_paragem_freguesia`, usando `_normalize_stop_name` e correspondência por `\b...\b` em ambas as
direções (o termo pesquisado dentro do nome guardado, ou o nome guardado dentro do termo pesquisado).

### 14. Planeamento de viagens — o motor de transbordos

**`plan_trip_with_transfer(origem, destino)`** é a função mais complexa da app. Passo a passo:

1. Lê **toda** a tabela `cache_paragens_linha` para memória (`todas = [(linha, paragem), ...]`) — não há
   filtragem por SQL, o cruzamento todo é feito em Python.
2. Constrói `mapa_linha_paragens` (dicionário `linha → set de paragens`) e, ao mesmo tempo, procura por
   correspondência direta de `origem`/`destino` nos nomes de paragem normalizados (com `\b...\b`),
   populando `linhas_origem`/`linhas_destino` e os conjuntos das paragens exatas encontradas.
3. **Fallback 1 — título da linha:** se não encontrou nenhuma linha diretamente, tenta
   `_search_lines_by_title`.
4. **Fallback 2 — freguesia:** se ainda assim não encontrou, assume que `origem`/`destino` pode ser o
   nome de uma freguesia, chama `search_stops_by_parish`, e para cada paragem dessa freguesia procura a
   correspondência exata no índice `todas`.
5. Se, depois de todos os *fallbacks*, `linhas_origem` ou `linhas_destino` continuarem vazios, devolve
   `"I could not find the origin/destination '...'"` (mensagem usada por `plan_trip_from_place` para
   decidir se deve tentar geocodificação — ver secção seguinte).
6. **Linha direta:** se `linhas_origem & linhas_destino` (interseção) não for vazia, essas são as linhas
   diretas — devolve-as imediatamente, sem procurar transbordo.
7. **Transbordo:** caso contrário, calcula `stops_o` (todas as paragens de todas as linhas de origem) e
   `stops_d` (idem para destino); o conjunto de possíveis pontos de transbordo é
   `(stops_o & stops_d) - paragens_origem_encontradas - paragens_destino_encontradas` (exclui as
   próprias paragens de origem/destino da lista de transbordos possíveis, para não sugerir "transborda
   onde já estás"). Se não houver nenhum ponto comum, devolve mensagem de falha. Caso contrário, para
   cada ponto de transbordo, lista as linhas que lá passam vindas da origem e as que lá passam a
   caminho do destino.
8. Ao longo de todo o processo, acumula notas de precisão (`aviso_precisao`) sempre que um *fallback*
   foi usado (título de linha ou freguesia), para o modelo poder comunicar essa incerteza.

**`_resolve_place_to_stop(nome_local)`** — a ponte entre "local qualquer" e "paragem": tenta
`_search_local_map`, depois `_geocode_nominatim_place`; se encontrar coordenadas, percorre todo o
`LOCAL_MAP` à procura da paragem (`tipo` `bus_stop`/`public_transport`) mais próxima via
`calculate_distance`, devolvendo `(nome_paragem, distancia, fonte)`.

**`plan_trip_from_place(origem, destino)`** — primeiro tenta `plan_trip_with_transfer` diretamente (caso
`origem`/`destino` já sejam nomes conhecidos de paragem/freguesia — caminho rápido, sem geocoding). Só se
essa tentativa falhar (mensagem a começar por "I could not find the origin/destination") é que resolve
cada local via `_resolve_place_to_stop` e volta a chamar `plan_trip_with_transfer`, desta vez com os
nomes das paragens encontradas. Anexa sempre notas explicando a que paragem cada local foi associado e
qual foi a distância/fonte, com um aviso extra se alguma das fontes tiver sido geocoding em tempo real.

### 15. Passes, tarifário e verificação de documentos

**`get_pass_types_cache()`** — lê `cache_titulos` ordenado por `tipologia`; se estiver vazia, devolve
`TIPOLOGIAS_PASSE_FALLBACK`. Cada `documentos_json` é desserializado com `json.loads`.

**`recommend_pass_types(respostas, tipologias_disponiveis)`** — motor de regras determinístico (sem IA)
baseado nas respostas do pequeno questionário em `render_pass_request`. A função auxiliar `_has(n)`
procura, entre as tipologias disponíveis nesse momento, a primeira cujo nome contenha `n` (case
insensitive) — isto porque os nomes exatos das tipologias podem variar consoante o *scrape*. As regras,
por ordem: veterano com "Antigo Combatente" disponível; incapacidade ≥60% com "Mobilidade Condicionada";
idade ≥65 e residente com tipologia "65+"; reforma antecipada entre 60–64 anos com "Reformado";
estudante (nível superior → universitário residente/não-residente; até 18 → "18+TP"; até 23 →
"23+TP"); utilizador de passe CP com "Mensal CP". **Se nenhuma regra específica se aplicar**, cai num
segundo nível de regras genéricas: residente com "CIM AVE 50% + 10% CMG" ou "CIM AVE 50%"; ou, em último
caso, a tipologia genérica "Mensal" (só se não existir nenhuma tipologia "CIM" disponível). O resultado
final remove duplicados preservando a ordem (`dict.fromkeys`).

**`verify_pass_documents(tipologia, ficheiros_carregados)`** — monta uma lista de "partes" para o Gemini:
uma instrução de texto a listar os documentos exigidos para a tipologia escolhida, seguida, para cada
ficheiro carregado, de um marcador de texto com o nome do documento e um dicionário
`{"mime_type": ..., "data": fich.getvalue()}` (o Gemini aceita imagens/PDFs diretamente como *bytes*
nesta estrutura). Chama `genai.GenerativeModel("gemini-3.5-flash").generate_content(partes, timeout=40)`.

**`render_pass_request(ui)`** — desenha o formulário completo: um "assistente de recomendação" opcional
(idade, residência, se é estudante e o nível, incapacidade, veterano, reforma antecipada, uso de passe
CP) que chama `recommend_pass_types` e mostra sugestões; depois um `selectbox` para escolher a tipologia
final; mostra descrição/preço/custo do cartão/prazo; gera dinamicamente um `st.file_uploader` por cada
documento exigido dessa tipologia; e um botão que chama `verify_pass_documents` e mostra o resultado.

### 16. Jogo escondido

`render_game(ui)` monta um bloco HTML/JS com um `<canvas>` de 650×360, injetado via `components.html`.
É um pequeno jogo de arcade (o *system prompt* interno chama-lhe "cabine de condução") com pontuação;
quando o jogo termina, usa a técnica descrita na secção 6 (parâmetros de URL) para comunicar a pontuação
de volta ao Python, que a grava via `save_score_db`. A tabela de recordes (`get_top_10`) é passada para o
JavaScript já como JSON no momento em que a função é chamada.

### 17. Sidebar administrativa

A sidebar tem sempre visíveis: botão para limpar o histórico da sessão atual; botão para abrir/fechar o
jogo; botão para abrir/fechar o formulário de pedido de passe; informação do programador (nome, contacto)
e estado do sistema (modelo Gemini ativo). A área de administrador fica atrás de um `st.text_input` do
tipo password, comparada com `hmac.compare_digest(password_input, admin_pass_real)` — uma comparação em
**tempo constante**, que evita que um atacante consiga inferir informação sobre a password a partir do
tempo de resposta (ao contrário de uma comparação direta com `==`). Além disso, ao fim de **5 tentativas
falhadas**, o login fica bloqueado durante **5 minutos** (`st.session_state.admin_bloqueado_ate`). Ainda
não há *hashing* da password em si (ela vive em texto simples nos secrets/`.env`), o que é razoável para
um projeto pessoal com um único administrador, mas não seria adequado para um sistema multi-utilizador
sensível. Uma vez autenticado
(`st.session_state.admin_autenticado = True`, guardado apenas na sessão, não persistido), o administrador
tem acesso a: botões para forçar `sync_all_guimabus_schedules` + `build_stop_index`, só
`build_stop_index`, `enrich_stops_with_parish` (com barra de progresso ao vivo), e
`sync_pass_types_and_fares`; um botão de logout; um botão para descarregar o ficheiro `.db` inteiro
(`st.download_button` a ler o ficheiro em modo binário); um leitor das últimas 10 linhas do ficheiro de
log; e um visualizador das últimas 30 mensagens de `historico_global` de todas as sessões.

### 18. Loop principal do chat e rede anti-alucinação

Fluxo completo desde o *input* do utilizador até à resposta final:

1. **Captura do input**: `prompt_texto = st.chat_input(...)` ou `audio_file = st.audio_input(...)`. Se
   for áudio, evita reprocessar o mesmo ficheiro duas vezes comparando
   `audio_file.file_id != st.session_state.ultimo_audio_processado_id`; transcreve com
   `genai.GenerativeModel("gemini-3.5-flash").generate_content([instrução, {"mime_type": "audio/wav", ...}])`.
2. Grava a mensagem do utilizador (`save_message_db` + `st.session_state.messages.append`) e mostra-a.
3. Monta `contexto_base = load_knowledge_base()`.
4. Define `LANGUAGE_INSTRUCTION` (força resposta em PT ou EN consoante `st.session_state.language`) e
   `SCHEDULE_INSTRUCTION` (obriga a consultar sempre `query_line_schedule_cache` antes de apresentar
   horários, também bilingue).
5. Constrói os 4 *system prompts* possíveis (`PROMPT_GUIMABUS`, `PROMPT_INTERVIEW`, `PROMPT_RECRUITER`,
   `PROMPT_PROJECT`) — ver conteúdo completo na secção seguinte.
6. Deteta o modo ativo por palavras-chave: primeiro `project_triggers`, depois "entrevista"/"interview",
   depois `recruiter_triggers`; senão, `PROMPT_GUIMABUS` por defeito.
7. Tenta chamar o Gemini com até 3 modelos candidatos em cascata
   (`["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]`) — se um falhar (ex: limite de
   *rate*), tenta o seguinte. `chat = model.start_chat(history=historico_api, enable_automatic_function_calling=True)`;
   é o SDK que gere automaticamente o ciclo de chamar ferramentas, receber o resultado, e devolver a
   resposta final de texto.
8. **Rede de segurança anti-alucinação** (`_called_real_tool`): se `looks_like_route_request(prompt)` for
   verdadeiro e o modo ativo for `PROMPT_GUIMABUS`, inspeciona o `chat.history` desde antes da chamada à
   procura de algum `part.function_call.name` que esteja em `ROUTE_TOOL_NAMES`. Se não encontrar
   nenhum, isso significa que o modelo respondeu "de cabeça" — e o sistema envia uma nova mensagem ao
   mesmo `chat`, desta vez com `tool_config={"function_calling_config": {"mode": "ANY", "allowed_function_names": ROUTE_TOOL_NAMES}}`,
   que **obriga tecnicamente** o modelo a chamar uma das ferramentas de trajeto antes de poder devolver
   texto. Regista sempre no log quando isto acontece (para poderes monitorizar quantas vezes o modelo
   "quase" alucinou).
9. Mostra `response.text`, grava-a (`save_message_db` + histórico da sessão), e oferece um botão de
   download da resposta em `.txt`.
10. Qualquer exceção não apanhada nos passos anteriores é capturada no `except` mais exterior e mostrada
    como `"Erro detetado no pipeline do agente: {e}"`.

### 19. Notas técnicas e possíveis extensões futuras

- O login de administrador usa `hmac.compare_digest` (comparação em tempo constante) e bloqueia o acesso
  por 5 minutos ao fim de 5 tentativas falhadas. A password em si é guardada em texto simples nos
  secrets, o que é adequado para um projeto pessoal com um único administrador.
- O índice paragem↔linha (`cache_paragens_linha`) inclui uma verificação de consistência: qualquer linha
  associada a menos de 2 paragens distintas é automaticamente descartada, uma vez que uma linha de
  autocarro real liga sempre pelo menos duas paragens.
- O geocoding em tempo real (Nominatim) só aceita um resultado se este partilhar pelo menos uma palavra
  significativa com o termo pesquisado, e fica em cache por 24h para reduzir pedidos repetidos ao serviço
  público (que tem um *rate limit* de 1 pedido/segundo).
- Possíveis extensões futuras: testes automatizados (`pytest`) para o motor de recomendação de passes
  (`recommend_pass_types`), que é lógica pura sem dependência de rede; e um indicador na UI mostrando há
  quanto tempo a cache de horários/tarifário foi sincronizada pela última vez.

---
---

## 🇬🇧 English Version

This document explains, **in as much detail as possible**, what every function and block of `app.py`
does, including exact algorithms, SQL queries, edge cases and design decisions — not just a high-level
summary. The order follows the order of the file itself.

### Table of contents
1. Imports
2. `UI_TEXT` — language dictionary
3. Log configuration
4. SQLite database — full schema
5. Search and geolocation system
6. Page configuration, languages and Gemini
7. Facebook RSS notices footer
8. Real-time fleet tools
9. Schedule PDF scraping + cache (includes Knowledge Base and cache diagnostics)
10. Geographic functions (Overpass, Folium, Google Maps)
11. Startup sync lock
12. Pass type and fare table scraping
13. Stop ↔ line index
14. Trip planning (transfer engine)
15. Passes, fares and document verification
16. Hidden game
17. Admin sidebar
18. Main chat loop and anti-hallucination safety net
19. Technical notes and possible future extensions

---

### 1. Imports

`streamlit` draws the whole interface. `google.generativeai` is Gemini's official SDK. `requests` makes
every external HTTP call (RSS, Nominatim geocoding, Overpass, official PDFs, the Guimabus tracking API).
`sqlite3` manages the local `agente_memoria.db` database (no ORM — every query is hand-written raw SQL).
`pdfplumber` extracts text from PDFs while preserving layout (`extract_text(layout=True)`), which is
essential for "reading" schedule tables with aligned columns. `folium` generates pure-HTML Leaflet maps.
`bs4.BeautifulSoup` parses both HTML (Guimabus pages) and XML (the RSS feed). The remaining modules
(`re`, `json`, `math`, `unicodedata`, `datetime`, `zoneinfo`, `email.utils`, `time`, `io`, `os`, `glob`,
`logging`) are all Python standard library — they don't go into `requirements.txt`.

### 2. `UI_TEXT` — language dictionary

A dictionary with two top-level keys, `"PT"` and `"EN"`, each with dozens of key→string pairs, covering
**every** visible piece of text in the interface: page title, welcome text (`initial_msg`), sidebar
button labels, error messages (wrong password, audio error), game texts, pass-request wizard texts, etc.
When the user clicks a language button, `st.session_state.language` changes and the app calls
`st.rerun()`; on reload, `ui = UI_TEXT[st.session_state.language]` selects the right dictionary and the
rest of the script uses `ui[...]` instead of loose strings. This means **adding any new UI text always
requires adding the matching key to both the `"PT"` and `"EN"` blocks**, or it raises a `KeyError` in
whichever language is missing it.

### 3. Log configuration

```python
logging.basicConfig(filename="auditoria_agente.log", level=logging.INFO, ...)
```
(exact configuration in section 1 of the file). Every `except Exception as e: logging.error(...)`
scattered through the code writes here. Since many functions return a friendly error message to the
user/model *and* log the full technical error, this file is the only way to see the actual `Exception`
(full message/stack trace) when something fails silently. It's read directly by the admin panel
(section 18), which shows the last 10 lines.

### 4. SQLite database — full schema

`initialize_db()` runs once at startup (called unconditionally right after its definition, line 340) and
creates these tables, all with `CREATE TABLE IF NOT EXISTS` (safe to always run):

| Table | Columns | Purpose |
|---|---|---|
| `historico_global` | `id, timestamp, session_id, role, content` | Permanent history of all chat messages across all sessions |
| `high_scores` | `id, timestamp, nome, pontor` | Hidden game's leaderboard |
| `cache_horarios` | `linha (PK), url, conteudo_txt, ultima_atualizacao` | Text extracted from official schedule PDFs, per line |
| `cache_titulos` | `tipologia (PK), descricao, preco, custo_cartao, prazo, documentos_json, ultima_atualizacao` | Pass types (scraped from the official page) |
| `cache_tarifario` | `id (PK, always 1), url_pdf, conteudo_txt, ultima_atualizacao` | Text of the fare table PDF (single table, single record) |
| `cache_paragens_linha` | `linha, paragem, PK(linha, paragem)` | Line↔stop index, built from `cache_horarios` |
| `cache_titulo_linha` | `linha (PK), titulo, ultima_atualizacao` | Textual title/description of each line (extracted from the link on the main page) |
| `cache_paragem_freguesia` | `paragem (PK), freguesia, fonte, ultima_atualizacao` | Stop→parish mapping (via geocoding) |
| `nos_geograficos` | `id, tipo, nome, freguesia, latitude, longitude, linhas_associadas, ultima_atualizacao` | General geographic index: POIs and streets imported via Overpass |

An index is also created: `CREATE INDEX idx_nome_nos ON nos_geograficos(nome)`.

`save_message_db(session_id, role, content)` inserts a row into `historico_global` with the current
timestamp (`%Y-%m-%d %H:%M:%S`). `get_top_10()` reads `high_scores` ordered by `pontor DESC, id ASC`,
limited to 10. `save_score_db(nome, pontor)` inserts a new score. All three wrap their logic in
`try/except`, returning an empty list (on read) or simply not writing (on write) on error, always
logging the exception.

**Critical compatibility note:** every table/column name above (`linha`, `paragem`, `tipo`, `nome`,
`freguesia`, `preco`, etc.) is **always kept in Portuguese**, even after the rest of the code was
translated into English. The `agente_memoria.db` already running in production has these columns
physically written into the `.db` file; translating the names in the code would make every query stop
matching the real schema, silently breaking the whole application (`sqlite3.OperationalError: no such
column`).

### 5. Fast search and geolocation system

The app's "geographic brain" — the most refined block across our development sessions.

- **`normalize_search_name(texto)`** — general normalisation pipeline: lowercase → strip accents via
  `unicodedata.normalize('NFKD', ...)` followed by filtering out combining characters → replace any
  non-alphanumeric character with `_` (`re.sub(r'[^a-z0-9]', '_', t)`) → collapse repeated `_` → trim `_`
  from both ends. E.g. `"Café Rio!"` → `"cafe_rio"`.
- **`looks_like_route_request(texto)`** — normalises the text and wraps it as `" word1 word2 ... "` (with
  surrounding spaces, to allow `in` without partial-substring false positives), then checks whether any
  word from the `_ROUTE_KEYWORDS_PT` list (see section 19) appears inside it. This list deliberately
  includes broad terms like "linha", "horario", "paragem", "onde fica", "como vou", "café" — to catch both
  explicit route requests and location questions like "where is café rio", which also need to go through
  a real tool.
- **`load_static_map()` / `LOCAL_MAP`** — reads `geo_guimaraes.json` once (decorated with
  `@st.cache_data`, no `ttl`, so it stays cached until the Streamlit session restarts) into an in-memory
  Python dictionary: `LOCAL_MAP = load_static_map()`. Each entry looks like
  `{"lat": ..., "lon": ..., "nome_real": ..., "tipo": ...}`. If the file doesn't exist or is invalid, it
  returns `{}` and logs the error — the app doesn't crash, but every static-map lookup silently fails
  from that point on.
- **`calculate_distance(lat1, lon1, lat2, lon2)`** — full Haversine formula (Earth's radius
  `R = 6371.0` km), returns the distance in **metres** (multiplies the km result by 1000).
- **`_search_local_map(local_nome)`** — a word-overlap scoring algorithm: normalises the searched term,
  turns it into a set of tokens (`set(chave_pesquisa.split("_"))`); for each `LOCAL_MAP` entry, computes
  `score = len(common_tokens) / len(searched_tokens)`; keeps the entry with the highest score; only
  accepts the result if `score >= 0.5` (at least half of the searched words found). This is what lets
  "café rio" find "Café do Rio" even without an exact match.
- **`_geocode_nominatim_place(local_nome)`** — a `GET` call to
  `https://nominatim.openstreetmap.org/search` with `q=f"{local_nome}, Guimarães, Portugal"`,
  `format=json`, `limit=1`, an 8-second timeout, and a custom `User-Agent` (Nominatim requires an
  identifiable User-Agent, otherwise it blocks the request). Returns `{"nome_real", "lat", "lon"}` from
  the first result, or `None` if there are no results or the call fails.
- **`find_nearest_stop(local_nome)`** — orchestrates everything: tries `_search_local_map`; if that
  fails, tries `_geocode_nominatim_place`; if both fail, returns a `"⚠️ NOT CONFIRMED: ..."` message (the
  exact marker the system prompt instructs the model to repeat to the user). If the place is found, it
  walks through **every** `LOCAL_MAP` entry whose `tipo` is `"bus_stop"` or `"public_transport"`,
  computes the distance to each with `calculate_distance`, and keeps the nearest one. If the distance is
  over 1500 metres, it explicitly warns that the distance is large and may be unreliable. The final
  message includes an extra note if the location's source was live Nominatim geocoding (less reliable
  than the official map).
- **`search_places_by_type(tipo_local, limite=20)`** — normalises the searched type, scans the whole
  `LOCAL_MAP` comparing against each entry's `tipo` field (bidirectional substring match:
  `type_norm in stored_type_norm or stored_type_norm in type_norm`), returns up to `limite`
  alphabetically-sorted names, with a note if there are more results than shown.

### 6. Page setup, languages, CSS and Gemini

`st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="wide")` must always be the
first Streamlit command. The language buttons are drawn as two `st.empty()` placeholders (`lang_pt_slot`,
`lang_en_slot`) inside `st.columns([12, 1, 1])`, next to the title — the actual clickable buttons are only
inserted into those slots later (section 18), once the startup lock releases execution. Next comes
capturing high scores via URL parameters (`st.query_params`), CSS injection for the chat box and the
audio recording button, and finally `genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])` inside a
`try/except` that, on failure (missing key), shows an error and calls `st.stop()` immediately — no
further line of the script runs in that case.

### 7. Facebook RSS notices footer

**`extract_future_date(texto)`** — uses a `PT_MONTHS` dictionary (Portuguese month names, including
abbreviations like "jan", "fev") to recognise dates written out in words, plus a regex pattern for
numeric dates (`dd/mm` or `dd-mm`, optionally with a year). It scans every date found in the text and
returns the **latest** one, already as a `datetime`. Returns `None` if none is found.

**`get_facebook_notices()`** — decorated with `@st.cache_data(ttl=3600)` (the real HTTP request only
happens once per hour). Calls `requests.get` on the RSS feed (`FetchRSS`, the service that turns the
Guimabus Facebook page into an RSS feed), uses
`BeautifulSoup(response.content, "xml")` to walk up to 30 `<item>` elements. For each item:
1. Extracts `title`, `description`/`content:encoded`, strips HTML tags and joins title+description into
   `texto_minusculas` (all lowercase, for comparison).
2. Extracts the image, if there's an `<enclosure>`.
3. Keeps a copy in `todos_avisos` (fallback plan, no filtering at all).
4. If it contains "resolvido" ("resolved"), "terminado" ("finished"), "já passou" ("already passed") or
   "reaberto" ("reopened") → `continue` (skip entirely).
5. Calls `extract_future_date`. If a confirmed future date is found and hasn't passed yet: **Tier 1** —
   priority = `1000 - days_until_end` (+50 for a critical keyword: "obra"/roadworks, "greve"/strike,
   "corte"/closure, "condicionamento"/traffic restriction, "interrupção"/interruption, "aviso"/notice,
   "urgente"/urgent); stays active until that date passes.
6. If no date is found: **Tier 2** — computes `dias_passados` from the RSS `<pubDate>`; if
   `dias_passados > 7`, `continue` (skip); otherwise priority = `7 - dias_passados` (+20 if critical).
7. At the end: sorts `avisos_ativos` by descending priority; if it ends up empty but `todos_avisos`
   isn't, returns the 2 most recent from that (fallback plan); otherwise returns **the entire**
   `avisos_ativos` list, with no size limit.

**`render_notices_footer(anuncios_ativos, ui)`** — if the list is empty, it `return`s immediately
(nothing is drawn, no visible error). Otherwise, it assembles an HTML/CSS/JS block injected via
`components.html(html_rodape, height=170)` — it runs **inside an isolated iframe**. The notices are
serialised as JSON (`json.dumps`) directly into a JavaScript `anuncios` variable; the `correrAviso()`
function uses `setTimeout` to walk through the array and update the DOM (text, image), all on the client
side, with no extra API cost. Because it runs inside an iframe, `position: fixed` in the CSS is relative
to the iframe, not the browser window — the footer sits wherever this component is called in the page's
flow.

### 8. Real-time fleet tools

**`_extract_vehicle_list(dados)`** — normalises the API response, which can come as a direct list or
nested inside a dictionary under several possible keys (`"vehicles"`, `"data"`, `"results"`, `"items"`,
`"veiculos"`); if none match, it looks for any dictionary value that is itself a list.

**`_first_value(dicionario, chaves, default=None)`** — returns the first non-`None` value among a list
of candidate keys (useful because the API may name the same field differently depending on the endpoint
version, e.g. `"id"`, `"vehicleId"`, `"vehicle_id"`, `"code"`).

**`DICIONARIO_PARAGENS_CONHECIDAS`** — a small fixed dictionary of shortcuts (`"vaca negra": "1103"`,
`"central": "1001"`, `"hospital": "1045"`, `"universidade": "1022"`, `"estacao": "1005"`) mapping
colloquial names to real numeric stop IDs in the Guimabus API.

**`get_guimabus_data(route_id=None)`** — decorated with `@st.cache_data(ttl=60)`. Calls
`GET https://gmr.elevensystems.pt/api/locations` with `passengerInfo=true` (and `routeId` if specified),
an 8-second timeout. For every vehicle returned, it builds a summary line with ID, line, status and
delay (using `_first_value` to tolerate different formats), and computes the fleet's average delay
across vehicles that report that data.

**`get_stop_schedule(stop_id)`** — decorated with `@st.cache_data(ttl=30)`. It first tries to map the
input text via `DICIONARIO_PARAGENS_CONHECIDAS`; if the result is a numeric ID (or the input itself is
already digits), it calls `GET https://gmr.elevensystems.pt/api/stops/{id}/routes` for live forecasts.
**If that fails or doesn't apply**, it falls back to a direct text search against the SQLite cache: it
strips common Portuguese stopwords from the input text (a regex with a word list like "estou", "na",
"no", "em", "paragem", etc.), uses the remaining terms to build a query
`SELECT linha, conteudo_txt FROM cache_horarios WHERE conteudo_txt LIKE ? AND conteudo_txt LIKE ? ...`
(one `LIKE` condition per term, all combined with `AND`), and for each matched line extracts only the
text lines that contain one of the terms or the words "página"/"tabela", capped at 25 context lines.

### 9. Schedule PDF scraping + cache

**`sync_all_guimabus_schedules()`** — the app's heaviest process. It sends a `GET` to
`https://guimabus.pt/horarios-linhas/`, parses it with `BeautifulSoup(response.text, 'html.parser')`,
walks every `<a href>` that contains both `.pdf` and `horario` in the link, extracts the line ID via the
regex `r'linha-([a-z0-9]+)'` applied to the lowercased *href*, and also keeps the link's visible text as
the line's "title" (`titulos_linha`). For each line found:
1. Up to 2 attempts (`for tentativa in range(2)`), with a 1-second wait between them on failure.
2. Downloads the PDF (`timeout=20`), checks `status_code == 200`.
3. Extracts text **from every page** with `pagina.extract_text(layout=True)` (preserves column
   alignment — essential for reading schedule tables), prefixing each page with `[PÁGINA N]`.
4. If no text at all can be extracted, it saves
   `"PDF em formato de imagem ou protegido contra leitura."` ("PDF is an image or protected against
   reading") as the content, instead of failing.
5. Saves into `cache_horarios` via `INSERT OR REPLACE` (the primary key is `linha`, so every re-sync
   fully replaces the previous record) and, if there is a title, also into `cache_titulo_linha`.
6. Between each processed line, `time.sleep(0.4)` — a manual rate limit so as not to hammer the Guimabus
   server with a burst of requests.

Returns a final message with the success/failure count.

**`query_line_schedule_cache(linha_id)`** — normalises the input ID to uppercase; if it's digits only, it
generates alternative candidates (without leading zeros, and zero-padded to 3 digits —
`entrada.zfill(3)`), to tolerate the user typing "5" when the line is stored as "005" or vice versa.
Tries each candidate against the table until it finds a result.

**`load_knowledge_base()`** — `glob.glob("knowledge/*.md")`, reads every file and concatenates all the
content, prefixed with `--- CONTEÚDO DE {filename} ---`. This text is injected into the context of
**every** call to Gemini, regardless of the active mode.

**`get_schedule_cache_age_days` / `get_pass_cache_age_days`** — run `SELECT MAX(ultima_atualizacao)` on
the respective table and compute `(datetime.now() - ultima).days`. **`get_stop_index_count`** runs
`SELECT COUNT(*) FROM cache_paragens_linha`. These three feed directly into `check_sync_needed`
(section 12).

### 10. Geographic functions: Overpass, Folium, Google Maps

**`import_guimaraes_pois()`** — sends an Overpass QL query (`[out:json][timeout:25]`) to
`https://overpass-api.de/api/interpreter`, requesting nodes inside the "Guimarães" area with `amenity`
tags (hospital, clinic, doctors, pharmacy, cafe, restaurant, school, university), `tourism` tags
(museum, attraction, monument) or `shop` tags (supermarket, mall, bakery). For every returned element
with a name and coordinates, it inserts into `nos_geograficos` with `tipo = f"poi_{tipo_poi}"` (e.g.
`"poi_cafe"`), using `INSERT OR IGNORE` (doesn't duplicate on the same key — though note this table has
no explicit `UNIQUE` constraint beyond the autoincrement `id`, so `INSERT OR IGNORE` here doesn't
actually prevent real data duplication; it's more of a safeguard against repeated primary keys than
against duplicate data).

**`import_parish_streets(nome_freguesia)`** — a similar Overpass query, but for `way["highway"]`
(streets) within the intersection of two areas (Guimarães + the specific parish), using a `set()` to
avoid saving the same street name twice within the same run.

**`generate_line_map_html(linha_id)`** — runs a SQL `JOIN` between `cache_paragens_linha` and
`nos_geograficos`, comparing the **normalised** names on both sides:
```sql
SELECT p.paragem, g.latitude, g.longitude, g.freguesia 
FROM cache_paragens_linha p
JOIN nos_geograficos g ON _normalize_stop_name(p.paragem) = _normalize_stop_name(g.nome)
WHERE p.linha = ? AND g.latitude IS NOT NULL
```
Draws a `folium.Map` centred on the first stop, with one marker per stop (bus icon) and a `PolyLine`
connecting all coordinates in order, saving the result as `maps/linha_{linha_id}.html`.

> **Implementation note:** this SQL query calls `_normalize_stop_name(...)` directly inside the SQL text,
> as if it were a native SQLite function. For this to work, the Python function `_normalize_stop_name`
> is explicitly registered with SQLite via `conn.create_function("_normalize_stop_name", 1,
> _normalize_stop_name)` right after every `sqlite3.connect(...)` that uses it, before running the query
> — in both `generate_line_map_html` and `generate_google_maps_link`.

**`generate_google_maps_link(local_nome)`** — a 3-level fallback chain: (1) `_search_local_map` (static
map); (2) a SQL query against `nos_geograficos` with the same `_normalize_stop_name(...)`-inside-SQL
pattern (same technique referenced above); (3) `_geocode_nominatim_place` (live). Always returns a link in the
format `https://www.google.com/maps/search/?api=1&query={lat},{lon}`, with a note indicating which
source was used — and an explicit "not confirmed" warning when the source was live Nominatim geocoding.

### 11. Startup sync lock

**`check_sync_needed(limite_dias=7)`** — uses `st.session_state.get("sync_checked")` as a flag so this
check only runs once per session (avoids recomputing on every user interaction). It independently
computes:
- `needs_sch` — whether the schedule cache doesn't exist or is `>= limite_dias` days old.
- `needs_idx` — whether `get_stop_index_count() == 0`.
- `needs_tkt` — whether the pass-type cache doesn't exist or is `>= limite_dias` days old.
- `needs_geo` — whether `SELECT COUNT(*) FROM nos_geograficos WHERE tipo LIKE 'poi_%'` is zero.

If any of these is true, it sets `st.session_state.is_updating = True` and stores an `update_tasks`
dictionary with the individual flags — this lets the startup block (section 18) run **only** the needed
syncs, not everything at once.

### 12. Pass type and fare table scraping

**`sync_guimabus_pass_types()`** — sends a `GET` to `https://guimabus.pt/titulos/`, strips irrelevant tags
(`nav`, `footer`, `form`, `script`, `style`) from the HTML before extracting text, then splits the full
text into blocks using the literal string `"\nPASSE\n"` as a separator (it assumes the page has the word
"PASSE" marking the start of each pass type). For each block, it runs a small line-by-line **state
machine** (`parsing_mode` cycles through `"desc"`, `"prazo"`, `"preco"`, `"cartao"`, `"docs"`, `"done"`),
detecting key phrases such as `"preço:"`, `"custo do cartão:"`, `"documentos necessários:"`,
`"só podem ser"`/`"até ao dia"` (for the deadline), and accumulating the rest as the description. It
saves everything into `cache_titulos` via `INSERT OR REPLACE`, with required documents serialised as JSON
(`json.dumps(documentos, ensure_ascii=False)`).

**`sync_guimabus_fare_table()`** — sends a `GET` to `https://guimabus.pt/tarifarios/`, looks for a PDF
link whose *href* contains "tarifa" or "tabela"; if none is found specifically, it uses the first PDF
found on the page as a fallback. It extracts the PDF's text the same way as
`sync_all_guimabus_schedules`, and saves it into a single record (`id = 1`) of the `cache_tarifario`
table.

**`sync_pass_types_and_fares()`** — calls the previous two in sequence and concatenates their result
messages.

`TIPOLOGIAS_PASSE_FALLBACK` is a fixed dictionary with a single pass type ("Mensal") used as an emergency
response in `get_pass_types_cache()` if the `cache_titulos` table is completely empty — so the app never
ends up with zero pass options to show.

### 13. Stop ↔ line index

**`_extract_stops_from_text(texto)`** — the heart of extracting stops from the scraped PDF text. It uses
a regex that looks for lines ending in at least 3 "schedule fields" (each field is either a literal `-`
or a time in `HH:MM` format), treating everything before that as the stop name:
```
^(?P<nome>.+?)\s+(?P<horarios>(?:-|\d{1,2}:\d{2})(?:\s+(?:-|\d{1,2}:\d{2})){2,})\s*$
```
It ignores lines containing `|` (usually table headers/separators) or starting with `[PÁGINA`/`[P`. It
only accepts names with at least 3 characters.

**`build_stop_index()`** — completely wipes `cache_paragens_linha` (`DELETE FROM ...`) and rebuilds it
from scratch from `cache_horarios`, calling `_extract_stops_from_text` for each line and inserting every
(line, stop) pair with `INSERT OR IGNORE` (the composite primary key `(linha, paragem)` avoids
duplicates).

**`_normalize_stop_name(texto)`** — a **richer** normalisation than `normalize_search_name`, specific to
stop names: replaces "são" with "s.", "santa" with "sta.", "santo" with "sto." (with `\b` so it doesn't
affect substrings), then strips all periods, strips accents, collapses whitespace. This exists because
the official PDFs write these prefixes inconsistently (sometimes "São Torcato", sometimes "S. Torcato").

**`_search_lines_by_title(termo_norm)`** — a fallback used when a stop isn't found directly: it searches
for the term inside each line's **title** (`cache_titulo_linha`), useful when the user types the name of
an area/parish that appears in the line's title but not as an exact stop name (e.g. "Guimarães-Gonça via
S. Torcato line").

**`enrich_stops_with_parish(progresso_callback=None)`** — for every stop in `cache_paragens_linha` that
doesn't yet have an entry in `cache_paragem_freguesia`, it makes a request to
`https://nominatim.openstreetmap.org/search` (with `countrycodes=pt`, `addressdetails=1`), extracting the
parish from the first result's `suburb`, `city_district`, `village`, `town` or `municipality` fields
(in that preference order). It saves the result even when nothing is found
(`fonte = "sem_resultado"`), so as not to retry that stop on future runs. It respects Nominatim's rate
limit with `time.sleep(1.1)` between requests — for ~200 stops, this takes ~4 minutes, hence the optional
`progresso_callback` to show a progress bar in the sidebar.

**`get_parish_of_stop` / `search_stops_by_parish`** — simple read queries against
`cache_paragem_freguesia`, using `_normalize_stop_name` and `\b...\b` matching in both directions (the
searched term inside the stored name, or the stored name inside the searched term).

### 14. Trip planning — the transfer engine

**`plan_trip_with_transfer(origem, destino)`** is the app's most complex function. Step by step:

1. Reads the **entire** `cache_paragens_linha` table into memory (`todas = [(linha, paragem), ...]`) —
   there is no SQL-level filtering, all the cross-referencing happens in Python.
2. Builds `mapa_linha_paragens` (a `line → set of stops` dictionary) and, at the same time, looks for a
   direct match of `origem`/`destino` in the normalised stop names (with `\b...\b`), populating
   `linhas_origem`/`linhas_destino` and the sets of exact stops found.
3. **Fallback 1 — line title:** if no line was found directly, it tries `_search_lines_by_title`.
4. **Fallback 2 — parish:** if still nothing was found, it assumes `origem`/`destino` might be a parish
   name, calls `search_stops_by_parish`, and for each stop in that parish looks for the exact match in
   the `todas` index.
5. If, after every fallback, `linhas_origem` or `linhas_destino` are still empty, it returns
   `"I could not find the origin/destination '...'"` (the message `plan_trip_from_place` uses to decide
   whether to try geocoding — see the next section).
6. **Direct line:** if `linhas_origem & linhas_destino` (intersection) is non-empty, those are the direct
   lines — returned immediately, without looking for a transfer.
7. **Transfer:** otherwise, it computes `stops_o` (every stop of every origin line) and `stops_d` (same
   for destination); the set of possible transfer points is
   `(stops_o & stops_d) - paragens_origem_encontradas - paragens_destino_encontradas` (excludes the
   origin/destination's own stops from the list of possible transfers, so it doesn't suggest "transfer
   where you already are"). If there's no common point, it returns a failure message. Otherwise, for
   each transfer point, it lists the lines arriving there from the origin and the ones leaving from
   there towards the destination.
8. Throughout the process, it accumulates precision notes (`aviso_precisao`) whenever a fallback was
   used (line title or parish), so the model can communicate that uncertainty.

**`_resolve_place_to_stop(nome_local)`** — the bridge between "any place" and "a stop": tries
`_search_local_map`, then `_geocode_nominatim_place`; if coordinates are found, it scans the entire
`LOCAL_MAP` looking for the nearest stop (`tipo` `bus_stop`/`public_transport`) via `calculate_distance`,
returning `(stop_name, distance, source)`.

**`plan_trip_from_place(origem, destino)`** — first tries `plan_trip_with_transfer` directly (in case
`origem`/`destino` are already known stop/parish names — a fast path, no geocoding). Only if that attempt
fails (a message starting with "I could not find the origin/destination") does it resolve each place via
`_resolve_place_to_stop` and call `plan_trip_with_transfer` again, this time with the stop names found.
It always appends notes explaining which stop each place was matched to and what the distance/source
was, with an extra warning if any of the sources was live geocoding.

### 15. Passes, fares and document verification

**`get_pass_types_cache()`** — reads `cache_titulos` ordered by `tipologia`; if it's empty, returns
`TIPOLOGIAS_PASSE_FALLBACK`. Each `documentos_json` is deserialised with `json.loads`.

**`recommend_pass_types(respostas, tipologias_disponiveis)`** — a deterministic rule engine (no AI)
based on the answers from the short questionnaire in `render_pass_request`. The helper `_has(n)` looks,
among the currently available pass types, for the first one whose name contains `n` (case insensitive) —
this is because the exact pass-type names can vary depending on the scrape. The rules, in order: veteran
with "Antigo Combatente" available; disability ≥60% with "Mobilidade Condicionada"; age ≥65 and resident
with "65+"; early retirement between ages 60–64 with "Reformado"; student (higher-education level →
resident/non-resident university pass; up to 18 → "18+TP"; up to 23 → "23+TP"); CP pass user with
"Mensal CP". **If no specific rule applies**, it falls back to a second, more generic tier: resident with
"CIM AVE 50% + 10% CMG" or "CIM AVE 50%"; or, as a last resort, the generic "Mensal" type (only if no
"CIM" type is available). The final result removes duplicates while preserving order
(`dict.fromkeys`).

**`verify_pass_documents(tipologia, ficheiros_carregados)`** — builds a list of "parts" for Gemini: a
text instruction listing the required documents for the chosen pass type, followed, for each uploaded
file, by a text marker with the document's name and a dictionary
`{"mime_type": ..., "data": fich.getvalue()}` (Gemini accepts images/PDFs directly as raw bytes in this
structure). Calls
`genai.GenerativeModel("gemini-3.5-flash").generate_content(partes, timeout=40)`.

**`render_pass_request(ui)`** — draws the full form: an optional "recommendation wizard" (age, residency,
whether a student and at what level, disability, veteran status, early retirement, CP pass usage) that
calls `recommend_pass_types` and shows suggestions; then a `selectbox` to choose the final pass type;
shows description/price/card cost/deadline; dynamically generates one `st.file_uploader` per required
document for that pass type; and a button that calls `verify_pass_documents` and shows the result.

### 16. Hidden game

`render_game(ui)` assembles an HTML/JS block with a 650×360 `<canvas>`, injected via
`components.html`. It's a small arcade game (the internal system prompt calls it a "driving cabin") with
scoring; when the game ends, it uses the technique described in section 6 (URL parameters) to send the
score back to Python, which saves it via `save_score_db`. The leaderboard (`get_top_10`) is passed into
the JavaScript as JSON at the moment the function is called.

### 17. Admin sidebar

The sidebar always shows: a button to clear the current session's history; a button to open/close the
game; a button to open/close the pass-request form; developer info (name, contact) and system status
(active Gemini model). The admin area sits behind a password-type `st.text_input`, compared with
`hmac.compare_digest(password_input, admin_pass_real)` — a **constant-time** comparison that prevents an
attacker from inferring anything about the password from response timing (unlike a direct `==`
comparison). On top of that, after **5 failed attempts**, the login is locked for **5 minutes**
(`st.session_state.admin_bloqueado_ate`). The password itself still isn't hashed (it lives in plain text
in secrets/`.env`), which is reasonable for a personal project with a single administrator, but wouldn't
be appropriate for a sensitive multi-user system. Once authenticated (`st.session_state.admin_autenticado = True`, stored only in the session, not persisted),
the admin has access to: buttons to force `sync_all_guimabus_schedules` + `build_stop_index`, just
`build_stop_index`, `enrich_stops_with_parish` (with a live progress bar), and
`sync_pass_types_and_fares`; a logout button; a button to download the entire `.db` file
(`st.download_button` reading the file in binary mode); a viewer for the last 10 lines of the log file;
and a viewer for the last 30 messages from `historico_global` across all sessions.

### 18. Main chat loop and anti-hallucination safety net

Full flow from user input to the final answer:

1. **Input capture**: `prompt_texto = st.chat_input(...)` or `audio_file = st.audio_input(...)`. For
   audio, it avoids reprocessing the same file twice by comparing
   `audio_file.file_id != st.session_state.ultimo_audio_processado_id`; transcribes with
   `genai.GenerativeModel("gemini-3.5-flash").generate_content([instruction, {"mime_type": "audio/wav", ...}])`.
2. Saves the user's message (`save_message_db` + `st.session_state.messages.append`) and displays it.
3. Builds `contexto_base = load_knowledge_base()`.
4. Defines `LANGUAGE_INSTRUCTION` (forces the reply in PT or EN based on `st.session_state.language`) and
   `SCHEDULE_INSTRUCTION` (requires always querying `query_line_schedule_cache` before presenting
   schedules, also bilingual).
5. Builds the 4 possible system prompts (`PROMPT_GUIMABUS`, `PROMPT_INTERVIEW`, `PROMPT_RECRUITER`,
   `PROMPT_PROJECT`) — see full content in the previous section.
6. Detects the active mode by keywords: first `project_triggers`, then "entrevista"/"interview", then
   `recruiter_triggers`; otherwise `PROMPT_GUIMABUS` by default.
7. Tries calling Gemini with up to 3 candidate models in a cascade
   (`["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]`) — if one fails (e.g. rate
   limit), it tries the next. `chat = model.start_chat(history=historico_api, enable_automatic_function_calling=True)`;
   it's the SDK that automatically manages the cycle of calling tools, receiving their results, and
   returning the final text answer.
8. **Anti-hallucination safety net** (`_called_real_tool`): if `looks_like_route_request(prompt)` is true
   and the active mode is `PROMPT_GUIMABUS`, it inspects `chat.history` from before the call, looking for
   any `part.function_call.name` that is in `ROUTE_TOOL_NAMES`. If none is found, that means the model
   answered "off the top of its head" — and the system sends a new message to the same `chat`, this time
   with `tool_config={"function_calling_config": {"mode": "ANY", "allowed_function_names": ROUTE_TOOL_NAMES}}`,
   which **technically forces** the model to call one of the route tools before it can return text. It
   always logs when this happens (so you can monitor how often the model "almost" hallucinated).
9. Displays `response.text`, saves it (`save_message_db` + session history), and offers a `.txt` download
   button for the answer.
10. Any exception not caught in the previous steps is captured by the outermost `except` and shown as
    `"Erro detetado no pipeline do agente: {e}"`.

### 19. Technical notes and possible future extensions

- Admin login uses `hmac.compare_digest` (constant-time comparison) and locks access for 5 minutes after
  5 failed attempts. The password itself is stored in plain text in secrets, which is appropriate for a
  personal project with a single administrator.
- The stop↔line index (`cache_paragens_linha`) includes a consistency check: any line associated with
  fewer than 2 distinct stops is automatically discarded, since a real bus line always connects at least
  two stops.
- Live geocoding (Nominatim) only accepts a result if it shares at least one meaningful word with the
  search term, and is cached for 24h to reduce repeated calls to the public service (which has a 1
  request/second rate limit).
- Possible future extensions: automated tests (`pytest`) for the pass-recommendation engine
  (`recommend_pass_types`), which is pure logic with no network dependency; and a UI indicator showing
  how long ago the schedule/fare cache was last synced.
