Explicação Completa do Projeto — app.py
Read this in English: jump to the English version below.

🇵🇹 Versão em Português
Este documento explica, com o máximo de detalhe possível, o que cada função e bloco de app.py faz, incluindo algoritmos exatos, queries SQL, casos-limite e decisões de desenho — não só um resumo de alto nível. A ordem segue a ordem do próprio ficheiro.

Índice
Imports
UI_TEXT — dicionário de idiomas
Configuração de logs
Base de dados SQLite — esquema completo
Sistema de pesquisa e geolocalização
Configuração da página, idiomas e Gemini
Rodapé de avisos via RSS do Facebook
Ferramentas de frota em tempo real
Scraping de PDFs de horários + cache (inclui Knowledge Base e diagnósticos de cache)
Funções geográficas (Overpass, Folium, Google Maps)
Bloqueio de sincronização no arranque
Scraping de tipologias de passe e tarifário
Índice paragem ↔ linha
Planeamento de viagens (motor de transbordos)
Passes, tarifário e verificação de documentos
Jogo escondido
Sidebar administrativa
Loop principal do chat e rede anti-alucinação
Notas técnicas e possíveis extensões futuras
1. Imports
streamlit desenha toda a interface. google.generativeai é o SDK oficial do Gemini. requests faz todos os pedidos HTTP externos (RSS, geocoding Nominatim, Overpass, PDFs oficiais, API de tracking da Guimabus). sqlite3 gere a base de dados local agente_memoria.db (sem ORM — todas as queries são SQL puro escrito à mão). pdfplumber extrai texto de PDFs preservando o layout (extract_text(layout=True)), o que é essencial para conseguir "ler" tabelas de horários com colunas alinhadas. folium gera mapas Leaflet em HTML puro. bs4.BeautifulSoup faz parsing tanto de HTML (páginas da Guimabus) como de XML (feed RSS). Os restantes módulos (re, json, math, unicodedata, datetime, zoneinfo, email.utils, time, io, os, glob, logging) são da biblioteca padrão do Python — não entram no requirements.txt.

2. UI_TEXT — dicionário de idiomas
Um dicionário com duas chaves de topo, "PT" e "EN", cada uma com dezenas de pares chave→string, cobrindo cada texto visível na interface: título da página, texto de boas-vindas (initial_msg), rótulos de botões da sidebar, mensagens de erro (password incorreta, erro de áudio), textos do jogo, textos do assistente de pedido de passe, etc. Quando o utilizador clica num botão de idioma, st.session_state.language muda e a app faz st.rerun(); no recarregamento, ui = UI_TEXT[st.session_state.language] seleciona o dicionário certo e todo o resto do script usa ui[...] em vez de strings soltas. Isto significa que acrescentar um novo texto à interface obriga sempre a adicionar a chave correspondente em ambos os blocos "PT" e "EN", ou a chave falha com KeyError num dos dois idiomas.

3. Configuração de logs
logging.basicConfig(filename="auditoria_agente.log", level=logging.INFO, ...)
(configuração exata na secção 1 do ficheiro). Todos os except Exception as e: logging.error(...) espalhados pelo código escrevem aqui. Como muitas funções devolvem uma mensagem de erro amigável ao utilizador/modelo e registam o erro técnico completo no log, este ficheiro é a única forma de ver a Exception real (stack trace/mensagem completa) quando algo falha silenciosamente. É lido diretamente pelo painel de administrador (secção 18), que mostra as últimas 10 linhas.

4. Base de dados SQLite — esquema completo
initialize_db() corre uma vez no arranque (chamada incondicional logo a seguir à sua definição, linha 340) e cria estas tabelas, todas com CREATE TABLE IF NOT EXISTS (seguro para correr sempre):

Tabela	Colunas	Propósito
historico_global	id, timestamp, session_id, role, content	Histórico permanente de todas as mensagens de chat de todas as sessões
high_scores	id, timestamp, nome, pontor	Tabela de recordes do jogo escondido
cache_horarios	linha (PK), url, conteudo_txt, ultima_atualizacao	Texto extraído dos PDFs oficiais de horários, por linha
cache_titulos	tipologia (PK), descricao, preco, custo_cartao, prazo, documentos_json, ultima_atualizacao	Tipologias de passe (scraped da página oficial)
cache_tarifario	id (PK, sempre 1), url_pdf, conteudo_txt, ultima_atualizacao	Texto do PDF de tarifário (tabela única, um único registo)
cache_paragens_linha	linha, paragem, PK(linha, paragem)	Índice linha↔paragem, construído a partir de cache_horarios
cache_titulo_linha	linha (PK), titulo, ultima_atualizacao	Título/descrição textual de cada linha (extraído do link na página principal)
cache_paragem_freguesia	paragem (PK), freguesia, fonte, ultima_atualizacao	Associação paragem→freguesia (via geocoding)
nos_geograficos	id, tipo, nome, freguesia, latitude, longitude, linhas_associadas, ultima_atualizacao	Índice geográfico geral: POIs e ruas importados via Overpass
Também é criado um índice: CREATE INDEX idx_nome_nos ON nos_geograficos(nome).

save_message_db(session_id, role, content) insere uma linha em historico_global com o timestamp atual (%Y-%m-%d %H:%M:%S). get_top_10() lê high_scores ordenado por pontor DESC, id ASC, limitado a 10. save_score_db(nome, pontor) insere um novo recorde. As três funções envolvem toda a lógica em try/except, devolvendo uma lista vazia (no caso de leitura) ou simplesmente não gravando (no caso de escrita) em caso de erro, sempre registando no log.

Nota de compatibilidade crítica: todos os nomes de tabelas e colunas acima (linha, paragem, tipo, nome, freguesia, preco, etc.) ficam sempre em português, mesmo depois de o resto do código ter sido traduzido para inglês. A agente_memoria.db que já existe em produção tem estas colunas gravadas fisicamente no ficheiro .db; traduzir os nomes no código faria com que todas as queries deixassem de bater certo com o esquema real, partindo a aplicação inteira sem aviso prévio (erro sqlite3.OperationalError: no such column).

5. Sistema de pesquisa e geolocalização rápida
O "cérebro geográfico" da app — o bloco mais afinado ao longo do desenvolvimento.

normalize_search_name(texto) — pipeline de normalização geral: minúsculas → remove acentos via unicodedata.normalize('NFKD', ...) seguido de filtragem de caracteres combinantes → substitui qualquer caractere não-alfanumérico por _ (re.sub(r'[^a-z0-9]', '_', t)) → colapsa _ repetidos → remove _ nas pontas. Ex: "Café Rio!" → "cafe_rio".
looks_like_route_request(texto) — normaliza o texto e o transforma em " palavra1 palavra2 ... " (com espaços a rodear, para permitir in sem falsos positivos de substring parcial), depois verifica se alguma palavra da lista _ROUTE_KEYWORDS_PT (ver secção 19) aparece lá dentro. Esta lista inclui termos como "linha", "horario", "paragem", "onde fica", "como vou", "café" — propositadamente ampla, para capturar tanto pedidos de trajeto explícitos como perguntas de localização como "onde fica o café rio", que também precisam de passar por uma ferramenta real.
load_static_map() / LOCAL_MAP — lê geo_guimaraes.json uma única vez (decorado com @st.cache_data, sem ttl, ou seja, fica em cache até a sessão do Streamlit reiniciar) para um dicionário Python em memória: LOCAL_MAP = load_static_map(). Cada entrada tem a forma {"lat": ..., "lon": ..., "nome_real": ..., "tipo": ...}. Se o ficheiro não existir ou for inválido, devolve {} e regista o erro — a app não crasha, mas todas as pesquisas no mapa estático falham silenciosamente a partir daí.
calculate_distance(lat1, lon1, lat2, lon2) — fórmula de Haversine completa (raio da Terra R = 6371.0 km), devolve a distância em metros (multiplica o resultado em km por 1000).
_search_local_map(local_nome) — algoritmo de pontuação por sobreposição de palavras: normaliza o termo pesquisado, transforma em conjunto de tokens (set(chave_pesquisa.split("_"))); para cada entrada do LOCAL_MAP, calcula pontuacao = len(tokens_comuns) / len(tokens_pesquisa); guarda a entrada com maior pontuação; só aceita o resultado se pontuacao >= 0.5 (pelo menos metade das palavras pesquisadas encontradas). Isto é o que permite que "café rio" encontre "Café do Rio" mesmo sem correspondência exata.
_geocode_nominatim_place(local_nome) — chamada GET a https://nominatim.openstreetmap.org/search com q=f"{local_nome}, Guimarães, Portugal", format=json, limit=1, timeout de 8s, com um User-Agent customizado (Nominatim exige um User-Agent identificável, caso contrário bloqueia o pedido). Devolve {"nome_real", "lat", "lon"} a partir do primeiro resultado, ou None se não houver resultados ou a chamada falhar.
find_nearest_stop(local_nome) — orquestra tudo: tenta _search_local_map; se falhar, tenta _geocode_nominatim_place; se ambos falharem, devolve uma mensagem "⚠️ NOT CONFIRMED: ..." (o marcador exato que o prompt de sistema instrui o modelo a repetir ao utilizador). Se encontrar o local, percorre todas as entradas do LOCAL_MAP cujo tipo seja "bus_stop" ou "public_transport", calcula a distância a cada uma com calculate_distance, e guarda a mais próxima. Se a distância for superior a 1500 metros, avisa explicitamente que a distância é elevada e pode não ser fiável. A mensagem final inclui uma nota extra se a fonte da localização tiver sido o Nominatim em tempo real (menos fiável do que o mapa oficial).
search_places_by_type(tipo_local, limite=20) — normaliza o tipo pesquisado, percorre todo o LOCAL_MAP comparando com o campo tipo de cada entrada (correspondência bidirecional por substring: tipo_norm in tipo_dado_norm or tipo_dado_norm in tipo_norm), devolve até limite nomes ordenados alfabeticamente, com uma nota se houver mais resultados do que os mostrados.
6. Configuração da página, idiomas, CSS e Gemini
st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="wide") tem de ser sempre o primeiro comando Streamlit. Os botões de idioma são desenhados como dois st.empty() (lang_pt_slot, lang_en_slot) dentro de st.columns([12, 1, 1]), ao lado do título — os botões clicáveis reais só são inseridos nesses slots mais tarde (secção 18), depois de o bloqueio de arranque libertar a execução. Segue-se a captura de recordes via parâmetros de URL (st.query_params), a injeção de CSS para a caixa de chat e o botão de gravação de áudio, e por fim genai.configure(api_key=st.secrets["GOOGLE_API_KEY"]) dentro de um try/except que, em caso de falha (chave em falta), mostra erro e chama st.stop() imediatamente — nenhuma linha seguinte do script corre nesse caso.

7. Rodapé de avisos via RSS do Facebook
extract_future_date(texto) — usa um dicionário PT_MONTHS (nomes de meses em português, incluindo abreviações como "jan", "fev") para reconhecer datas escritas por extenso, mais um padrão regex para datas numéricas (dd/mm ou dd-mm, opcionalmente com ano). Percorre todas as datas encontradas no texto e devolve a mais tardia, já como datetime. Devolve None se não encontrar nenhuma.

get_facebook_notices() — decorada com @st.cache_data(ttl=3600) (só faz o pedido HTTP real uma vez por hora). Faz requests.get ao feed RSS (FetchRSS, o serviço que transforma a página de Facebook da Guimabus num feed RSS), usa BeautifulSoup(response.content, "xml") para percorrer até 30 <item>. Para cada item:

Extrai title, description/content:encoded, limpa tags HTML e junta título+descrição em texto_minusculas (tudo em minúsculas, para comparação).
Extrai a imagem, se houver <enclosure>.
Guarda uma cópia em todos_avisos (plano B, sem qualquer filtro).
Se contiver "resolvido", "terminado", "já passou" ou "reaberto" → continue (ignora completamente).
Chama extract_future_date. Se encontrar data futura confirmada e ainda não passada: Tier 1 — prioridade = 1000 - dias_ate_fim (+50 se tiver palavra crítica: "obra", "greve", "corte", "condicionamento", "interrupção", "aviso", "urgente"); mantém-se ativo até essa data passar.
Se não encontrar data: Tier 2 — calcula dias_passados a partir do <pubDate> do RSS; se dias_passados > 7, continue (ignora); caso contrário prioridade = 7 - dias_passados (+20 se crítico).
No final: ordena avisos_ativos por prioridade decrescente; se ficar vazio mas todos_avisos não, devolve os 2 mais recentes deste último (plano B); caso contrário devolve toda a lista avisos_ativos, sem limite de tamanho.
render_notices_footer(anuncios_ativos, ui) — se a lista vier vazia, return imediato (nada é desenhado, sem erro visível). Caso contrário, monta um bloco HTML/CSS/JS injetado via components.html(html_rodape, height=170) — corre dentro de um iframe isolado. Os avisos são serializados como JSON (json.dumps) diretamente para uma variável JavaScript anuncios; a função correrAviso() usa setTimeout para percorrer o array e atualizar o DOM (texto, imagem), tudo no lado do cliente, sem custo de API adicional. Por correr num iframe, position: fixed no CSS é relativo ao iframe, não à janela do browser — o rodapé fica onde este componente é chamado no fluxo da página.

8. Ferramentas de frota em tempo real
_extract_vehicle_list(dados) — normaliza a resposta da API, que pode vir como lista direta ou dentro de um dicionário sob várias chaves possíveis ("vehicles", "data", "results", "items", "veiculos"); se nenhuma bater, procura qualquer valor do dicionário que seja uma lista.

_first_value(dicionario, chaves, default=None) — devolve o primeiro valor não-None entre uma lista de chaves candidatas (útil porque a API pode nomear o mesmo campo de formas diferentes consoante a versão do endpoint, ex: "id", "vehicleId", "vehicle_id", "code").

DICIONARIO_PARAGENS_CONHECIDAS — um pequeno dicionário fixo de atalhos ("vaca negra": "1103", "central": "1001", "hospital": "1045", "universidade": "1022", "estacao": "1005") para mapear nomes coloquiais a IDs numéricos reais de paragem na API da Guimabus.

get_guimabus_data(route_id=None) — decorada com @st.cache_data(ttl=60). Chama GET https://gmr.elevensystems.pt/api/locations com passengerInfo=true (e routeId se especificado), timeout de 8s. Para cada veículo devolvido, monta uma linha de resumo com ID, linha, estado e atraso (usando _first_value para tolerar formatos diferentes), e calcula a média de atraso da frota entre os veículos que reportam esse dado.

get_stop_schedule(stop_id) — decorada com @st.cache_data(ttl=30). Primeiro tenta mapear o texto de entrada via DICIONARIO_PARAGENS_CONHECIDAS; se o resultado for um ID numérico (ou o próprio input já for dígitos), chama GET https://gmr.elevensystems.pt/api/stops/{id}/routes para obter previsões em tempo real. Se isso falhar ou não se aplicar, cai num fallback que faz uma pesquisa textual direta na cache SQLite: remove stopwords portuguesas comuns do texto de entrada (regex com uma lista de palavras como "estou", "na", "no", "em", "paragem", etc.), usa os termos restantes para construir uma query SELECT linha, conteudo_txt FROM cache_horarios WHERE conteudo_txt LIKE ? AND conteudo_txt LIKE ? ... (uma condição LIKE por termo, todas com AND), e para cada linha encontrada extrai só as linhas de texto que contêm algum dos termos ou as palavras "página"/"tabela", limitando a 25 linhas de contexto.

9. Scraping de PDFs de horários + cache
sync_all_guimabus_schedules() — o processo mais pesado da app. Faz GET a https://guimabus.pt/horarios-linhas/, faz parsing com BeautifulSoup(response.text, 'html.parser'), percorre todos os <a href> que contenham .pdf e horario no link, extrai o ID da linha via regex r'linha-([a-z0-9]+)' aplicada ao href em minúsculas, e guarda também o texto visível do link como "título" da linha (titulos_linha). Para cada linha encontrada:

Até 2 tentativas (for tentativa in range(2)), com 1 segundo de espera entre elas em caso de falha.
Descarrega o PDF (timeout=20), verifica status_code == 200.
Extrai texto de cada página com pagina.extract_text(layout=True) (preserva alinhamento de colunas — essencial para as tabelas de horas), prefixando cada página com [PÁGINA N].
Se não conseguir extrair texto nenhum, grava "PDF em formato de imagem ou protegido contra leitura." como conteúdo (em vez de falhar).
Grava em cache_horarios via INSERT OR REPLACE (chave primária é linha, por isso cada re-sincronização substitui o registo anterior por completo) e, se houver título, também em cache_titulo_linha.
Entre cada linha processada, time.sleep(0.4) — um rate limit manual para não sobrecarregar o servidor da Guimabus com pedidos em rajada.
Devolve uma mensagem final com a contagem de sucessos/falhas.

query_line_schedule_cache(linha_id) — normaliza o ID de entrada para maiúsculas; se for só dígitos, gera candidatos alternativos (sem zeros à esquerda, e com 3 dígitos com zeros à esquerda — entrada.zfill(3)), para tolerar o utilizador escrever "5" quando a linha está gravada como "005" ou vice-versa. Testa cada candidato na tabela até encontrar um resultado.

load_knowledge_base() — glob.glob("knowledge/*.md"), lê cada ficheiro e concatena todo o conteúdo, prefixado com --- CONTEÚDO DE {nome_do_ficheiro} ---. Este texto é injetado no contexto de todas as chamadas ao Gemini, independentemente do modo ativo.

get_schedule_cache_age_days / get_pass_cache_age_days — fazem SELECT MAX(ultima_atualizacao) na respetiva tabela e calculam (datetime.now() - ultima).days. get_stop_index_count faz SELECT COUNT(*) FROM cache_paragens_linha. Estas três alimentam diretamente check_sync_needed (secção 12).

10. Funções geográficas: Overpass, Folium, Google Maps
import_guimaraes_pois() — envia uma query em linguagem Overpass QL ([out:json][timeout:25]) para https://overpass-api.de/api/interpreter, pedindo nós dentro da área "Guimarães" com tags amenity (hospital, clínica, médico, farmácia, café, restaurante, escola, universidade), tourism (museu, atração, monumento) ou shop (supermercado, centro comercial, padaria). Para cada elemento devolvido com nome e coordenadas, insere em nos_geograficos com tipo = f"poi_{tipo_poi}" (ex: "poi_cafe"), usando INSERT OR IGNORE (não duplica se já existir com a mesma chave — embora repare-se que esta tabela não tem uma constraint UNIQUE explícita além do id autoincrement, por isso INSERT OR IGNORE aqui não impede duplicados reais; é mais uma proteção contra chaves primárias repetidas do que contra dados duplicados).

import_parish_streets(nome_freguesia) — query Overpass semelhante, mas para way["highway"] (ruas) dentro da interseção de duas áreas (Guimarães + a freguesia específica), usando um set() para não gravar o mesmo nome de rua duas vezes na mesma execução.

generate_line_map_html(linha_id) — faz uma query SQL com JOIN entre cache_paragens_linha e nos_geograficos, comparando os nomes normalizados de ambos os lados:

SELECT p.paragem, g.latitude, g.longitude, g.freguesia 
FROM cache_paragens_linha p
JOIN nos_geograficos g ON _normalize_stop_name(p.paragem) = _normalize_stop_name(g.nome)
WHERE p.linha = ? AND g.latitude IS NOT NULL
Desenha um folium.Map centrado na primeira paragem, com um marcador por paragem (ícone de autocarro) e uma PolyLine a ligar todas as coordenadas por ordem, gravando o resultado como maps/linha_{linha_id}.html.

Nota de implementação: esta query SQL chama _normalize_stop_name(...) diretamente dentro do texto SQL, como se fosse uma função nativa do SQLite. Para isso funcionar, a função Python _normalize_stop_name é registada explicitamente no SQLite via conn.create_function("_normalize_stop_name", 1, _normalize_stop_name) logo a seguir a cada sqlite3.connect(...) que a usa, antes de executar a query — tanto em generate_line_map_html como em generate_google_maps_link.

generate_google_maps_link(local_nome) — cadeia de fallback em 3 níveis: (1) _search_local_map (mapa estático); (2) query SQL a nos_geograficos com o mesmo padrão _normalize_stop_name(...) dentro do SQL (mesma técnica referida acima); (3) _geocode_nominatim_place (tempo real). Devolve sempre um link no formato https://www.google.com/maps/search/?api=1&query={lat},{lon}, com uma nota indicando a fonte usada — e um aviso explícito de "não confirmado" quando a fonte é o Nominatim em tempo real.

11. Bloqueio de sincronização no arranque
check_sync_needed(limite_dias=7) — usa st.session_state.get("sync_checked") como flag para só correr esta verificação uma vez por sessão (evita recalcular em cada interação do utilizador). Calcula independentemente:

needs_sch — se a cache de horários não existe ou tem >= limite_dias dias.
needs_idx — se get_stop_index_count() == 0.
needs_tkt — se a cache de tipologias não existe ou tem >= limite_dias dias.
needs_geo — se SELECT COUNT(*) FROM nos_geograficos WHERE tipo LIKE 'poi_%' for zero.
Se qualquer uma for verdadeira, marca st.session_state.is_updating = True e guarda um dicionário update_tasks com as flags individuais — isto permite ao bloco de arranque (secção 18) correr só as sincronizações necessárias, não todas de cada vez.

12. Scraping de tipologias de passe e tarifário
sync_guimabus_pass_types() — faz GET a https://guimabus.pt/titulos/, remove tags irrelevantes (nav, footer, form, script, style) do HTML antes de extrair texto, e depois divide o texto completo em blocos usando a string literal "\nPASSE\n" como separador (assume que a página tem a palavra "PASSE" a marcar o início de cada tipologia). Para cada bloco, corre uma pequena máquina de estados linha a linha (parsing_mode alterna entre "desc", "prazo", "preco", "cartao", "docs", "done"), detetando frases-chave como "preço:", "custo do cartão:", "documentos necessários:", "só podem ser"/"até ao dia" (para o prazo), e acumulando o resto como descrição. Grava tudo em cache_titulos via INSERT OR REPLACE, com os documentos necessários serializados como JSON (json.dumps(documentos, ensure_ascii=False)).

sync_guimabus_fare_table() — faz GET a https://guimabus.pt/tarifarios/, procura um link PDF cujo href contenha "tarifa" ou "tabela"; se não encontrar nenhum específico, usa o primeiro PDF que encontrar na página como fallback. Extrai o texto do PDF da mesma forma que sync_all_guimabus_schedules, e grava num único registo (id = 1) da tabela cache_tarifario.

sync_pass_types_and_fares() — chama as duas anteriores em sequência e concatena as mensagens de resultado.

TIPOLOGIAS_PASSE_FALLBACK é um dicionário fixo com uma única tipologia ("Mensal") usado como resposta de emergência em get_pass_types_cache() se a tabela cache_titulos estiver completamente vazia — para a app nunca ficar sem nenhuma opção de passe para mostrar.

13. Índice paragem ↔ linha
_extract_stops_from_text(texto) — o coração da extração de paragens a partir do texto scraped dos PDFs. Usa uma regex que procura linhas terminadas em pelo menos 3 "campos de horário" (cada campo é um - literal ou uma hora no formato HH:MM), interpretando tudo antes disso como o nome da paragem:

^(?P<nome>.+?)\s+(?P<horarios>(?:-|\d{1,2}:\d{2})(?:\s+(?:-|\d{1,2}:\d{2})){2,})\s*$
Ignora linhas que contenham | (normalmente cabeçalhos/separadores de tabela) ou comecem por [PÁGINA/[P. Só aceita nomes com pelo menos 3 caracteres.

build_stop_index() — apaga completamente cache_paragens_linha (DELETE FROM ...) e reconstrói-a do zero a partir de cache_horarios, chamando _extract_stops_from_text para cada linha e inserindo cada par (linha, paragem) com INSERT OR IGNORE (a chave primária composta (linha, paragem) evita duplicados).

_normalize_stop_name(texto) — uma normalização mais rica do que normalize_search_name, específica para nomes de paragens: substitui "são" por "s.", "santa" por "sta.", "santo" por "sto." (com \b para não afetar substrings), depois remove todos os pontos, remove acentos, colapsa espaços. Isto existe porque os PDFs oficiais escrevem estes prefixos de forma inconsistente (às vezes "São Torcato", às vezes "S. Torcato").

_search_lines_by_title(termo_norm) — fallback usado quando uma paragem não é encontrada diretamente: procura o termo pesquisado dentro do título de cada linha (cache_titulo_linha), útil quando o utilizador escreve o nome de uma zona/freguesia que aparece no título da linha mas não como nome exato de paragem (ex: "Linha Guimarães-Gonça via S. Torcato").

enrich_stops_with_parish(progresso_callback=None) — para cada paragem em cache_paragens_linha que ainda não tenha entrada em cache_paragem_freguesia, faz um pedido a https://nominatim.openstreetmap.org/search (com countrycodes=pt, addressdetails=1), extraindo a freguesia do primeiro resultado a partir dos campos suburb, city_district, village, town ou municipality (por esta ordem de preferência). Grava o resultado mesmo quando não encontra nada (fonte = "sem_resultado"), para não voltar a tentar essa paragem em execuções futuras. Respeita o rate limit do Nominatim com time.sleep(1.1) entre pedidos — para ~200 paragens, isto demora ~4 minutos, daí o progresso_callback opcional para mostrar uma barra de progresso na sidebar.

get_parish_of_stop / search_stops_by_parish — consultas de leitura simples sobre cache_paragem_freguesia, usando _normalize_stop_name e correspondência por \b...\b em ambas as direções (o termo pesquisado dentro do nome guardado, ou o nome guardado dentro do termo pesquisado).

14. Planeamento de viagens — o motor de transbordos
plan_trip_with_transfer(origem, destino) é a função mais complexa da app. Passo a passo:

Lê toda a tabela cache_paragens_linha para memória (todas = [(linha, paragem), ...]) — não há filtragem por SQL, o cruzamento todo é feito em Python.
Constrói mapa_linha_paragens (dicionário linha → set de paragens) e, ao mesmo tempo, procura por correspondência direta de origem/destino nos nomes de paragem normalizados (com \b...\b), populando linhas_origem/linhas_destino e os conjuntos das paragens exatas encontradas.
Fallback 1 — título da linha: se não encontrou nenhuma linha diretamente, tenta _search_lines_by_title.
Fallback 2 — freguesia: se ainda assim não encontrou, assume que origem/destino pode ser o nome de uma freguesia, chama search_stops_by_parish, e para cada paragem dessa freguesia procura a correspondência exata no índice todas.
Se, depois de todos os fallbacks, linhas_origem ou linhas_destino continuarem vazios, devolve "I could not find the origin/destination '...'" (mensagem usada por plan_trip_from_place para decidir se deve tentar geocodificação — ver secção seguinte).
Linha direta: se linhas_origem & linhas_destino (interseção) não for vazia, essas são as linhas diretas — devolve-as imediatamente, sem procurar transbordo.
Transbordo: caso contrário, calcula stops_o (todas as paragens de todas as linhas de origem) e stops_d (idem para destino); o conjunto de possíveis pontos de transbordo é (stops_o & stops_d) - paragens_origem_encontradas - paragens_destino_encontradas (exclui as próprias paragens de origem/destino da lista de transbordos possíveis, para não sugerir "transborda onde já estás"). Se não houver nenhum ponto comum, devolve mensagem de falha. Caso contrário, para cada ponto de transbordo, lista as linhas que lá passam vindas da origem e as que lá passam a caminho do destino.
Ao longo de todo o processo, acumula notas de precisão (aviso_precisao) sempre que um fallback foi usado (título de linha ou freguesia), para o modelo poder comunicar essa incerteza.
_resolve_place_to_stop(nome_local) — a ponte entre "local qualquer" e "paragem": tenta _search_local_map, depois _geocode_nominatim_place; se encontrar coordenadas, percorre todo o LOCAL_MAP à procura da paragem (tipo bus_stop/public_transport) mais próxima via calculate_distance, devolvendo (nome_paragem, distancia, fonte).

plan_trip_from_place(origem, destino) — primeiro tenta plan_trip_with_transfer diretamente (caso origem/destino já sejam nomes conhecidos de paragem/freguesia — caminho rápido, sem geocoding). Só se essa tentativa falhar (mensagem a começar por "I could not find the origin/destination") é que resolve cada local via _resolve_place_to_stop e volta a chamar plan_trip_with_transfer, desta vez com os nomes das paragens encontradas. Anexa sempre notas explicando a que paragem cada local foi associado e qual foi a distância/fonte, com um aviso extra se alguma das fontes tiver sido geocoding em tempo real.

15. Passes, tarifário e verificação de documentos
get_pass_types_cache() — lê cache_titulos ordenado por tipologia; se estiver vazia, devolve TIPOLOGIAS_PASSE_FALLBACK. Cada documentos_json é desserializado com json.loads.

recommend_pass_types(respostas, tipologias_disponiveis) — motor de regras determinístico (sem IA) baseado nas respostas do pequeno questionário em render_pass_request. A função auxiliar _has(n) procura, entre as tipologias disponíveis nesse momento, a primeira cujo nome contenha n (case insensitive) — isto porque os nomes exatos das tipologias podem variar consoante o scrape. As regras, por ordem: veterano com "Antigo Combatente" disponível; incapacidade ≥60% com "Mobilidade Condicionada"; idade ≥65 e residente com tipologia "65+"; reforma antecipada entre 60–64 anos com "Reformado"; estudante (nível superior → universitário residente/não-residente; até 18 → "18+TP"; até 23 → "23+TP"); utilizador de passe CP com "Mensal CP". Se nenhuma regra específica se aplicar, cai num segundo nível de regras genéricas: residente com "CIM AVE 50% + 10% CMG" ou "CIM AVE 50%"; ou, em último caso, a tipologia genérica "Mensal" (só se não existir nenhuma tipologia "CIM" disponível). O resultado final remove duplicados preservando a ordem (dict.fromkeys).

verify_pass_documents(tipologia, ficheiros_carregados) — monta uma lista de "partes" para o Gemini: uma instrução de texto a listar os documentos exigidos para a tipologia escolhida, seguida, para cada ficheiro carregado, de um marcador de texto com o nome do documento e um dicionário {"mime_type": ..., "data": fich.getvalue()} (o Gemini aceita imagens/PDFs diretamente como bytes nesta estrutura). Chama genai.GenerativeModel("gemini-3.5-flash").generate_content(partes, timeout=40).

render_pass_request(ui) — desenha o formulário completo: um "assistente de recomendação" opcional (idade, residência, se é estudante e o nível, incapacidade, veterano, reforma antecipada, uso de passe CP) que chama recommend_pass_types e mostra sugestões; depois um selectbox para escolher a tipologia final; mostra descrição/preço/custo do cartão/prazo; gera dinamicamente um st.file_uploader por cada documento exigido dessa tipologia; e um botão que chama verify_pass_documents e mostra o resultado.

16. Jogo escondido
render_game(ui) monta um bloco HTML/JS com um <canvas> de 650×360, injetado via components.html. É um pequeno jogo de arcade (o system prompt interno chama-lhe "cabine de condução") com pontuação; quando o jogo termina, usa a técnica descrita na secção 6 (parâmetros de URL) para comunicar a pontuação de volta ao Python, que a grava via save_score_db. A tabela de recordes (get_top_10) é passada para o JavaScript já como JSON no momento em que a função é chamada.

17. Sidebar administrativa
A sidebar tem sempre visíveis: botão para limpar o histórico da sessão atual; botão para abrir/fechar o jogo; botão para abrir/fechar o formulário de pedido de passe; informação do programador (nome, contacto) e estado do sistema (modelo Gemini ativo). A área de administrador fica atrás de um st.text_input do tipo password, comparada com hmac.compare_digest(password_input, admin_pass_real) — uma comparação em tempo constante, que evita que um atacante consiga inferir informação sobre a password a partir do tempo de resposta (ao contrário de uma comparação direta com ==). Além disso, ao fim de 5 tentativas falhadas, o login fica bloqueado durante 5 minutos (st.session_state.admin_bloqueado_ate). Ainda não há hashing da password em si (ela vive em texto simples nos secrets/.env), o que é razoável para um projeto pessoal com um único administrador, mas não seria adequado para um sistema multi-utilizador sensível. Uma vez autenticado (st.session_state.admin_autenticado = True, guardado apenas na sessão, não persistido), o administrador tem acesso a: botões para forçar sync_all_guimabus_schedules + build_stop_index, só build_stop_index, enrich_stops_with_parish (com barra de progresso ao vivo), e sync_pass_types_and_fares; um botão de logout; um botão para descarregar o ficheiro .db inteiro (st.download_button a ler o ficheiro em modo binário); um leitor das últimas 10 linhas do ficheiro de log; e um visualizador das últimas 30 mensagens de historico_global de todas as sessões.

18. Loop principal do chat e rede anti-alucinação
Fluxo completo desde o input do utilizador até à resposta final:

Captura do input: prompt_texto = st.chat_input(...) ou audio_file = st.audio_input(...). Se for áudio, evita reprocessar o mesmo ficheiro duas vezes comparando audio_file.file_id != st.session_state.ultimo_audio_processado_id; transcreve com genai.GenerativeModel("gemini-3.5-flash").generate_content([instrução, {"mime_type": "audio/wav", ...}]).
Grava a mensagem do utilizador (save_message_db + st.session_state.messages.append) e mostra-a.
Monta contexto_base = load_knowledge_base().
Define LANGUAGE_INSTRUCTION (força resposta em PT ou EN consoante st.session_state.language) e SCHEDULE_INSTRUCTION (obriga a consultar sempre query_line_schedule_cache antes de apresentar horários, também bilingue).
Constrói os 4 system prompts possíveis (PROMPT_GUIMABUS, PROMPT_INTERVIEW, PROMPT_RECRUITER, PROMPT_PROJECT) — ver conteúdo completo na secção seguinte.
Deteta o modo ativo por palavras-chave: primeiro project_triggers, depois "entrevista"/"interview", depois recruiter_triggers; senão, PROMPT_GUIMABUS por defeito.
Tenta chamar o Gemini com até 3 modelos candidatos em cascata (["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]) — se um falhar (ex: limite de rate), tenta o seguinte. chat = model.start_chat(history=historico_api, enable_automatic_function_calling=True); é o SDK que gere automaticamente o ciclo de chamar ferramentas, receber o resultado, e devolver a resposta final de texto.
Rede de segurança anti-alucinação (_called_real_tool): se looks_like_route_request(prompt) for verdadeiro e o modo ativo for PROMPT_GUIMABUS, inspeciona o chat.history desde antes da chamada à procura de algum part.function_call.name que esteja em ROUTE_TOOL_NAMES. Se não encontrar nenhum, isso significa que o modelo respondeu "de cabeça" — e o sistema envia uma nova mensagem ao mesmo chat, desta vez com tool_config={"function_calling_config": {"mode": "ANY", "allowed_function_names": ROUTE_TOOL_NAMES}}, que obriga tecnicamente o modelo a chamar uma das ferramentas de trajeto antes de poder devolver texto. Regista sempre no log quando isto acontece (para poderes monitorizar quantas vezes o modelo "quase" alucinou).
Mostra response.text, grava-a (save_message_db + histórico da sessão), e oferece um botão de download da resposta em .txt.
Qualquer exceção não apanhada nos passos anteriores é capturada no except mais exterior e mostrada como "Erro detetado no pipeline do agente: {e}".
19. Notas técnicas e possíveis extensões futuras
O login de administrador usa hmac.compare_digest (comparação em tempo constante) e bloqueia o acesso por 5 minutos ao fim de 5 tentativas falhadas. A password em si é guardada em texto simples nos secrets, o que é adequado para um projeto pessoal com um único administrador.
O índice paragem↔linha (cache_paragens_linha) inclui uma verificação de consistência: qualquer linha associada a menos de 2 paragens distintas é automaticamente descartada, uma vez que uma linha de autocarro real liga sempre pelo menos duas paragens.
O geocoding em tempo real (Nominatim) só aceita um resultado se este partilhar pelo menos uma palavra significativa com o termo pesquisado, e fica em cache por 24h para reduzir pedidos repetidos ao serviço público (que tem um rate limit de 1 pedido/segundo).
Possíveis extensões futuras: testes automatizados (pytest) para o motor de recomendação de passes (recommend_pass_types), que é lógica pura sem dependência de rede; e um indicador na UI mostrando há quanto tempo a cache de horários/tarifário foi sincronizada pela última vez.

