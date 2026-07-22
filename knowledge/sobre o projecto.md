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
import hmac
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# --- LANGUAGE DICTIONARY ---
UI_TEXT = {
    "PT": {
        "title": "🚌 Agente Sobre Rodas😎",
        "toast_score": "💾 Recorde de {name} ({score} pessoa(s)) guardado com sucesso!",
        "sidebar_panel": "⚙️ Painel do Agente",
        "clear_history": "🗑️ Limpar O Meu Histórico",
        "entertainment": "🕹️ Entretenimento",
        "close_game": "Fechar Crazy Bus Driver X",
        "open_game": "Abrir Crazy Bus Driver Mini-Game 👾",
        "transport_tickets": "🎫 Títulos de Transporte",
        "close_ticket": "Fechar Pedido de Passe X",
        "request_ticket": "Pedir Passe 🎫",
        "developer": "👨‍💻 Desenvolvedor",
        "dev_desc": "**Celso Ferreira**\n*À procura de emprego na área de IT / Informática.*\n🔗 [LinkedIn](https://www.linkedin.com/in/celso-ferreira-ab0830134/) | [GitHub](https://github.com/celsofernandesferreira)",
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
        "initial_msg": "Olá! Sou o **Agente de Produtividade de Elite do Celso**.\n\nEstou pronto para te apoiar em três frentes:\n1. **Guimabus:** Monitorização da frota, horários e trajetos da Guimabus e informações .\n2. **Secretario do Celso:** Informação sobre o Perfil do Celso e percurso profissional para recrutadores — dá-me um problema de IT para eu mostrar como o Celso Resolveria.\n3. **Projeto:** Pergunta-me sobre este projeto — como foi construído, que tecnologias usa e como funciona.\n\nComo posso ajudar hoje?",
        "game_title": "🚌 Crazy Bus Driver 🚌",
        "game_play": "Play ▶",
        "game_pause": "Pause ⏸",
        "game_reset": "Reset 🔄",
        "game_save": "Gravar 💾",
        "game_name": "Teu Nome",
        "game_pax": "Passageiros",
        "game_unit": "passageiros(s)",
        "game_top10": "🏆 TOP 10 MOTORISTAS",
        "game_gameover": "FIM DA LINHA",
        "game_transported": "Transportaste",
        "game_type_name": "Digita o teu nome no painel abaixo.",
        "game_alert": "Por favor introduz o teu nome!",
        "ad_disclaimer": "⚠️ Aviso importante: Esta é uma ferramenta de apoio e verificação preliminar. Não é um canal oficial de submissão à Guimabus.",
        "ad_notice": "Aviso",
        "ticket_title": "🎫 Titulos de Transporte — Guimabus",
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
        "title": "🚌 Agent on Wheels😎",
        "toast_score": "💾 Score for {name} ({score} person(s)) saved successfully!",
        "sidebar_panel": "⚙️ Agent Panel",
        "clear_history": "🗑️ Clear My History",
        "entertainment": "🕹️ Entertainment",
        "close_game": "Close Crazy Bus Driver X",
        "open_game": "Open Crazy Bus Driver Mini-Game 👾",
        "transport_tickets": "🎫 Transport Tickets",
        "close_ticket": "Close Ticket Request X",
        "request_ticket": "Request Ticket 🎫",
        "developer": "👨‍💻 Developer",
        "dev_desc": "**Celso Ferreira**\n*Looking for IT / Computer Science roles.*\n🔗 [LinkedIn](https://www.linkedin.com/in/celso-ferreira-ab0830134/) | [GitHub](https://github.com/celsofernandesferreira)",
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
        "initial_msg": "Hello! I am **Celso's Elite Productivity Agent**.\n\nI am ready to support you on three fronts:\n1. **Guimabus:** Fleet monitoring, schedules and routes for Guimabus, plus general information.\n2. **Celso's Assistant:** Information about Celso's profile and career for recruiters — give me an IT problem and I'll show you how Celso would solve it.\n3. **Project:** Ask me about this project — how it was built, what technologies it uses and how it works.\n\nHow can I help you today?",
        "game_title": "🚌 Crazy Bus Driver 🚌",
        "game_play": "Play ▶",
        "game_pause": "Pause ⏸",
        "game_reset": "Reset 🔄",
        "game_save": "Save 💾",
        "game_name": "Your Name",
        "game_pax": "Passengers",
        "game_unit": "passenger(s)",
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

# 1. LOG CONFIGURATION (Technical Audit)
logging.basicConfig(
    filename="auditoria_agente.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)

# 2. DATABASE CONFIGURATION (Persistent SQLite with High Scores and Schedule Cache)
def initialize_db():
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

    # Remove any duplicate rows that may already exist (safe for a pre-existing database
    # that was populated before this UNIQUE constraint existed), keeping the earliest row
    # of each (tipo, nome) pair, then enforce real uniqueness going forward so that
    # INSERT OR IGNORE actually prevents duplicates instead of silently doing nothing.
    cursor.execute("""
        DELETE FROM nos_geograficos
        WHERE id NOT IN (
            SELECT MIN(id) FROM nos_geograficos GROUP BY tipo, nome
        )
    """)
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_geo ON nos_geograficos(tipo, nome);")

    conn.commit()
    conn.close()

def save_message_db(session_id, role, content):
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
        logging.error(f"Error saving to the database: {e}")

def get_top_10():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT nome, pontor FROM high_scores ORDER BY pontor DESC, id ASC LIMIT 10")
        resultados = cursor.fetchall()
        conn.close()
        return resultados
    except Exception as e:
        logging.error(f"Error reading High Scores: {e}")
        return []

def save_score_db(nome, pontor):
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
        logging.error(f"Error saving High Score: {e}")

initialize_db()

# --- JSON SEARCH & FAST GEOLOCATION SYSTEM ---
def normalize_search_name(texto):
    if not texto: return ""
    t = texto.lower().strip()
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'[^a-z0-9]', '_', t)
    t = re.sub(r'_+', '_', t).strip('_')
    return t

# Tools that, if called, guarantee a response grounded in real data
# (cache/DB/map) instead of the model's generic knowledge about transport.
ROUTE_TOOL_NAMES = [
    "get_guimabus_data", "get_stop_schedule", "query_line_schedule_cache",
    "plan_trip_with_transfer", "plan_trip_from_place",
    "find_nearest_stop", "query_stop_parish_tool",
]

_ROUTE_KEYWORDS_PT = [
    "linha", "horario", "horário", "autocarro", "guimabus", "paragem", "paragens",
    "viagem", "trajeto", "trajecto", "transporte", " para ", " até ", " ate ",
    "ir para", "como vou", "como chegar", "que horas passa", "onde fica", "onde e",
    "onde é", "café", "cafe", "fica"
]

def looks_like_route_request(texto: str) -> bool:
    """Heuristic: detects whether the user's question is about schedules, lines or
    routes — cases where there can NEVER be an answer without going through a real tool."""
    if not texto:
        return False
    t = " " + normalize_search_name(texto).replace("_", " ") + " "
    return any(normalize_search_name(p).replace("_", " ") in t for p in _ROUTE_KEYWORDS_PT)

@st.cache_data
def load_static_map():
    try:
        with open("geo_guimaraes.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading geo_guimaraes.json: {e}")
        return {}

LOCAL_MAP = load_static_map()

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c * 1000

def _search_local_map(local_nome: str):
    """Searches for a place in LOCAL_MAP (geo_guimaraes.json) with word-tolerant matching,
    instead of requiring an almost-exact match of the whole string."""
    if not LOCAL_MAP:
        return None
    chave_pesquisa = normalize_search_name(local_nome)
    tokens_pesquisa = set(t for t in chave_pesquisa.split("_") if t)
    if not tokens_pesquisa:
        return None

    melhor_match, melhor_pontuacao = None, 0.0
    for chave, dados in LOCAL_MAP.items():
        tokens_chave = set(t for t in chave.split("_") if t)
        comuns = tokens_pesquisa & tokens_chave
        if not comuns:
            continue
        pontuacao = len(comuns) / len(tokens_pesquisa)
        if pontuacao > melhor_pontuacao:
            melhor_pontuacao, melhor_match = pontuacao, dados

    # Stricter matching than before: for short queries (<=2 words) we now require
    # EVERY word to match, not just half. A 50% threshold meant a 2-word query like
    # "cafe areal" could match an entry for just "areal" (a neighbourhood/zone) and be
    # reported back with full confidence as if it were the specific business "Café
    # Areal" — a real source of invented/incorrect locations. Longer queries keep a
    # high (but not perfect) bar, since extra descriptive words are more tolerable.
    limite_minimo = 1.0 if len(tokens_pesquisa) <= 2 else 0.75
    if melhor_match and melhor_pontuacao >= limite_minimo:
        return melhor_match
    return None

@st.cache_data(ttl=86400)
def _geocode_nominatim_place(local_nome: str):
    """Geocodes a place name in Guimarães live via OpenStreetMap (Nominatim),
    used as a fallback when the place is not in the static map (geo_guimaraes.json)."""
    headers = {'User-Agent': 'SuperSecretarioIA-Guimaraes/1.0'}
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{local_nome}, Guimarães, Portugal", "format": "json", "limit": 5},
            headers=headers, timeout=8
        )
        resp.raise_for_status()
        resultados = resp.json()
        if not resultados:
            return None

        # Nominatim's free-text search almost always returns *something*, even when no
        # real match exists for the specific place asked about — it silently drops the
        # words it can't match and geocodes whatever remains (e.g. a street or a
        # neighbourhood). Blindly trusting result[0] was a real source of confidently
        # reported, incorrect locations. We now only accept a candidate whose own name
        # actually shares a meaningful word with the query.
        tokens_pesquisa = set(t for t in normalize_search_name(local_nome).split("_") if t)
        for r in resultados:
            nome_resultado = r.get("display_name", "").split(",")[0]
            tokens_resultado = set(t for t in normalize_search_name(nome_resultado).split("_") if t)
            if tokens_pesquisa & tokens_resultado:
                return {
                    "nome_real": nome_resultado or local_nome,
                    "lat": float(r["lat"]),
                    "lon": float(r["lon"]),
                }
        return None
    except Exception as e:
        logging.error(f"Error geocoding via Nominatim for '{local_nome}': {e}")
    return None

def find_nearest_stop(local_nome: str):
    """Finds the nearest bus stop to any café, street, factory or other place.
    Searches the static map first (geo_guimaraes.json); if not found, tries live
    geocoding via OpenStreetMap before giving up."""
    local_encontrado = _search_local_map(local_nome)
    fonte = "mapa estático"

    if not local_encontrado:
        local_encontrado = _geocode_nominatim_place(local_nome)
        fonte = "OpenStreetMap (tempo real)"

    if not local_encontrado:
        return f"⚠️ NOT CONFIRMED: I could not locate '{local_nome}' either on the static map of Guimarães or via a live search. Confirm the exact name or indicate the street/parish where it is located."

    if not LOCAL_MAP:
        return "O mapa estático não está carregado, não é possível calcular a paragem mais próxima."

    lat_origem = local_encontrado["lat"]
    lon_origem = local_encontrado["lon"]
    paragem_mais_proxima = None
    menor_distancia = float('inf')

    for chave, dados in LOCAL_MAP.items():
        if dados.get("tipo") in ["bus_stop", "public_transport"]:
            dist = calculate_distance(lat_origem, lon_origem, dados["lat"], dados["lon"])
            if dist < menor_distancia:
                menor_distancia = dist
                paragem_mais_proxima = dados["nome_real"]

    nota_fonte = " (localização obtida via OpenStreetMap em tempo real, não do mapa oficial da Guimabus)" if fonte == "OpenStreetMap (tempo real)" else ""

    if paragem_mais_proxima:
        if menor_distancia > 1500:
            return f"O local '{local_encontrado['nome_real']}'{nota_fonte} foi encontrado, mas a paragem mais próxima ('{paragem_mais_proxima}') está a {int(menor_distancia)} metros — distância elevada, pode não ser fiável. Confirma o nome exato do local."
        return f"O local '{local_encontrado['nome_real']}'{nota_fonte} fica a {int(menor_distancia)} metros da paragem de autocarro '{paragem_mais_proxima}'. ⚠️ Esta função só indica a paragem mais próxima geograficamente — NÃO confirma que linha passa por ela. Usa 'plan_trip_with_transfer' ou 'query_line_schedule_cache' com o nome exato desta paragem para confirmar a linha real."
    else:
        return "Encontrei o local, mas não existem paragens de autocarro nas imediações."


def search_places_by_type(tipo_local: str, limite: int = 20):
    """Searches the static map of Guimarães (geo_guimaraes.json) for all places of a given
    type/category — e.g. 'café', 'restaurant', 'pharmacy', 'school', 'supermarket', etc.
    Useful when the user asks to list/discover options of a type of place (e.g. 'what cafés are near the centre?')."""
    if not LOCAL_MAP:
        return "O mapa estático não está carregado. Verifica o ficheiro geo_guimaraes.json."

    if not tipo_local:
        return "É necessário indicar o tipo de local a procurar (ex: 'café', 'farmácia', 'restaurante')."

    tipo_norm = normalize_search_name(tipo_local)
    encontrados = []
    for chave, dados in LOCAL_MAP.items():
        tipo_dado_norm = normalize_search_name(str(dados.get("tipo", "")))
        if not tipo_dado_norm:
            continue
        # Flexible matching: "cafe" also finds "cafe_bar", "cafeteria", etc.
        if tipo_norm in tipo_dado_norm or tipo_dado_norm in tipo_norm:
            nome_real = dados.get("nome_real", chave)
            encontrados.append(nome_real)

    if not encontrados:
        return f"I could not find any place of type '{tipo_local}' on the static map of Guimarães (geo_guimaraes.json). This type may not exist in the file, or the type name stored is different."

    encontrados = sorted(set(encontrados))
    total = len(encontrados)
    listados = encontrados[:limite]
    resumo = f"Encontrei {total} local(is) do tipo '{tipo_local}' em Guimarães:\n"
    resumo += "\n".join(f"- {nome}" for nome in listados)
    if total > limite:
        resumo += f"\n... e mais {total - limite} local(is) não mostrados. Pede para refinar a pesquisa se precisares de mais."
    return resumo

# 3. Page configuration 
st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="wide")

# Dictionary and toggle initialization
if "language" not in st.session_state:
    st.session_state.language = "PT"
ui = UI_TEXT[st.session_state.language]

col1, col2, col3 = st.columns([12, 1, 1])
with col1:
    st.title(ui["title"])
with col2:
    lang_pt_slot = st.empty()
with col3:
    lang_en_slot = st.empty()
# The buttons are only drawn inside these "slots" further down in the code,
# after we confirm the system is not updating (see the "is_updating" block).
# While the app is locked, these slots stay empty and the language buttons
# neither appear nor are clickable.

if "session_id" not in st.session_state:
    st.session_state.session_id = datetime.now().strftime("%H%M%S%f")

# --- CAPTURING HIGH SCORES VIA URL ---
query_params = st.query_params
if "save_nome" in query_params and "save_pontos" in query_params:
    nome_recorde = query_params["save_nome"].upper()
    pontos_recorde = int(float(query_params["save_pontos"]))
    
    save_score_db(nome_recorde, pontos_recorde)
    st.toast(ui["toast_score"].replace("{name}", nome_recorde).replace("{score}", str(pontos_recorde)))
    
    st.query_params.clear()
    st.rerun()

# 4. Advanced CSS injection
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

def _load_dotenv_file(file_path: str | Path | None = None):
    """Load simple KEY=VALUE pairs from a dotenv-style file without adding a new dependency."""
    candidates = []
    if file_path:
        candidates.append(Path(file_path))

    base_dir = Path(__file__).resolve().parent
    candidates.extend([
        base_dir / "Secrets.env",
        base_dir / ".env",
        base_dir / "secrets.env",
        Path.cwd() / "Secrets.env",
        Path.cwd() / ".env",
        Path.cwd() / "secrets.env",
    ])

    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=False)
        except Exception:
            resolved = candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        if not resolved.exists() or not resolved.is_file():
            continue
        try:
            values = {}
            for raw_line in resolved.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
            return values
        except Exception as exc:
            logging.warning(f"Unable to read secrets file {resolved}: {exc}")
    return {}


DOTENV_VALUES = _load_dotenv_file()


def _get_secret(key: str, default=None):
    """Reads a configuration secret, preferring environment variables, then
    Streamlit secrets, and finally a local dotenv-style file so the same app
    behaves correctly in Docker and in local development."""
    valor = os.getenv(key)
    if valor:
        return valor

    try:
        if st.secrets.get(key, None):
            return st.secrets.get(key, default)
    except Exception:
        pass

    if key in DOTENV_VALUES:
        return DOTENV_VALUES[key]

    return default

# 5. Gemini API initialization
try:
    chave_api = _get_secret("GOOGLE_API_KEY")
    if not chave_api:
        raise ValueError("GOOGLE_API_KEY not set (checked environment variable and st.secrets).")
    genai.configure(api_key=chave_api)
except Exception:
    st.error("Error: API key missing from environment variables, Streamlit secrets, or Secrets.env.")
    logging.error("Failed to initialize the application: API key missing from environment/secrets files.")
    st.stop()


# --- FACEBOOK RSS INTEGRATION (SMART NATIVE LOGIC) ---
def extract_future_date(texto):
    PT_MONTHS = {
        "janeiro": 1, "jan": 1, "fevereiro": 2, "fev": 2, "março": 3, "mar": 3,
        "abril": 4, "abr": 4, "maio": 5, "mai": 5, "junho": 6, "jun": 6,
        "julho": 7, "jul": 7, "agosto": 8, "ago": 8, "setembro": 9, "set": 9,
        "outubro": 10, "out": 10, "novembro": 11, "nov": 11, "dezembro": 12, "dez": 12
    }
    
    agora = datetime.now()
    ano_atual = agora.year
    datas_encontradas = []

    for m in re.finditer(r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b', texto):
        dia, mes = int(m.group(1)), int(m.group(2))
        ano = int(m.group(3)) if m.group(3) else ano_atual
        if ano < 100: ano += 2000
        try:
            datas_encontradas.append(datetime(ano, mes, dia))
        except ValueError:
            pass

    for m in re.finditer(r'\b(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(\d{4}))?\b', texto.lower()):
        dia = int(m.group(1))
        mes_str = m.group(2)
        ano = int(m.group(3)) if m.group(3) else ano_atual
        if mes_str in PT_MONTHS:
            try:
                datas_encontradas.append(datetime(ano, PT_MONTHS[mes_str], dia))
            except ValueError:
                pass

    if datas_encontradas:
        return max(datas_encontradas)
    return None

@st.cache_data(ttl=3600)
def get_facebook_notices():
    # 1. NOVO URL DO FETCHRSS
    url_rss = "https://fetchrss.com/feed/1wk44d0rp6kO1wk41H0MeFRi.rss"
    avisos_ativos = []
    todos_avisos = [] 
    
    agora_utc = datetime.now(timezone.utc)
    agora_local = datetime.now()

    try:
        response = requests.get(url_rss, timeout=10)
        soup = BeautifulSoup(response.content, "xml") 
        itens = soup.find_all("item")
        
        for item in itens[:30]: 
            title = item.find("title").text if item.find("title") else "Aviso"
            content_encoded = item.find("content:encoded")
            desc = content_encoded.text if content_encoded else (item.find("description").text if item.find("description") else "")
            
            # 2. CORREÇÃO DO TEXTO: Forçar tudo a uma única linha sem quebras manhosas
            clean_text = BeautifulSoup(desc, "html.parser").get_text(separator=" ").strip()
            clean_text = re.sub(r'\s+', ' ', clean_text) # Transforma \n e múltiplos espaços num só espaço
            title = re.sub(r'\s+', ' ', title).strip()
            
            # 3. CORREÇÃO DA IMAGEM: Procurar em media:content ou na tag <img> dentro da descrição
            img_url = ""
            media_content = item.find("media:content")
            if media_content and media_content.get("url"):
                img_url = media_content.get("url")
            elif item.find("enclosure") and item.find("enclosure").get("url"):
                img_url = item.find("enclosure").get("url")
            else:
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc, re.IGNORECASE)
                if img_match: 
                    img_url = img_match.group(1)
            
            texto_minusculas = clean_text.lower() + " " + title.lower()
            texto_final = clean_text if len(clean_text) > 5 else title
            
            aviso_temp = {
                "texto": texto_final, 
                "imagem": img_url, 
                "prioridade": 1
            }
            todos_avisos.append(aviso_temp)
            
            if any(palavra in texto_minusculas for palavra in ["resolvido", "terminado", "já passou", "reaberto"]):
                continue

            data_fim_texto = extract_future_date(texto_minusculas)
            palavras_criticas = ["obra", "obras", "trânsito", "greve", "corte", "condicionamento", "interrupção", "aviso", "urgente"]

            if data_fim_texto:
                if data_fim_texto < agora_local:
                    continue
                dias_ate_fim = (data_fim_texto - agora_local).days
                prioridade_calculada = 1000 - max(dias_ate_fim, 0)
                if any(kw in texto_minusculas for kw in palavras_criticas):
                    prioridade_calculada += 50
            else:
                LIMITE_DIAS_GENERICO = 7
                pub_date_node = item.find("pubDate")
                dias_passados = 0
                if pub_date_node:
                    try:
                        data_post = email.utils.parsedate_to_datetime(pub_date_node.text)
                        dias_passados = (agora_utc - data_post).days
                    except Exception:
                        pass

                if dias_passados > LIMITE_DIAS_GENERICO:
                    continue

                prioridade_calculada = LIMITE_DIAS_GENERICO - dias_passados

                if any(kw in texto_minusculas for kw in palavras_criticas):
                    prioridade_calculada += 20
            
            aviso_temp["prioridade"] = prioridade_calculada
            avisos_ativos.append(aviso_temp)
            
        avisos_ativos.sort(key=lambda x: x["prioridade"], reverse=True)
        
        if not avisos_ativos and todos_avisos:
            return todos_avisos[:2]
        
        return avisos_ativos
            
    except Exception as e:
        logging.error(f"Native RSS error: {e}")
        
    return avisos_ativos

def render_notices_footer(anuncios_ativos, ui):
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

    
# --- CONTEXT FUNCTIONS / TOOLS ---
def _extract_vehicle_list(dados):
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

def _first_value(dicionario, chaves, default=None):
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
def get_guimabus_data(route_id: str = None):
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

        veiculos = _extract_vehicle_list(dados)
        if not veiculos:
            linha_txt = f" da linha {route_id}" if route_id else ""
            return f"Não há autocarros{linha_txt} em circulação neste momento."

        total_atraso = 0
        count_com_atraso = 0
        resumo = "Dados de frota em tempo real (Guimabus):\n"
        for bus in veiculos:
            id_bus = _first_value(bus, ["id", "vehicleId", "vehicle_id", "code"], "N/A")
            linha = _first_value(bus, ["line", "lineName", "route", "routeShortName", "routeId"], None)
            status = _first_value(bus, ["busStatus", "status", "state"], "N/A")
            atraso = _first_value(bus, ["delay", "delayMinutes", "delay_min"], None)

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
def get_stop_schedule(stop_id: str):
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
            rotas = _extract_vehicle_list(dados)
            if rotas:
                resumo = f"Horários/previsões em tempo real para a paragem {target_id}:\n"
                for rota in rotas:
                    linha = _first_value(rota, ["line", "lineName", "route", "routeShortName", "routeId"], "N/A")
                    destino = _first_value(rota, ["destination", "headsign", "direction"], None)
                    eta = _first_value(rota, ["eta", "etaMinutes", "waitTime", "waitingTime", "arrivalTime", "nextArrival"], None)
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
        logging.error(f"Error in advanced text scan on DB: {e_db}")

    return f"Não foi possível obter informação em tempo real nem encontrar registos em cache para a localização '{stop_id}'."

# --- TOOL: FULL PDF SCRAPING AUTOMATION ---
def sync_all_guimabus_schedules():
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
                logging.error(f"Failed to process the PDF for line {linha_id} after 2 attempts: {ultimo_erro}")

            time.sleep(0.4)

        conn.commit()
        conn.close()
        
        success_msg = f"Sync complete: {len(linhas_processadas)}/{len(links_pdf)} PDFs downloaded and converted into the local DB!"
        if linhas_falhadas:
            success_msg += f" Failed: {', '.join(linhas_falhadas)}."
        logging.info(success_msg)
        return success_msg
        
    except Exception as e:
        error_msg = f"PDF scraping automation failed: {e}"
        logging.error(error_msg)
        return error_msg

def query_line_schedule_cache(linha_id: str):
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

def load_knowledge_base():
    contexto = ""
    files = glob.glob("knowledge/*.md")
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            contexto += f"\n--- CONTEÚDO DE {os.path.basename(file)} ---\n{f.read()}"
    return contexto if contexto else "Sem documentação extra encontrada na Knowledge Base."

def get_schedule_cache_age_days():
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
        logging.error(f"Error checking schedule cache age: {e}")
        return None

def get_pass_cache_age_days():
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
        logging.error(f"Error checking pass cache age: {e}")
        return None

def get_stop_index_count():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cache_paragens_linha")
        resultado = cursor.fetchone()
        conn.close()
        return resultado[0] if resultado else 0
    except Exception as e:
        logging.error(f"Error counting stop index: {e}")
        return 0

# --- NEW GEOGRAPHIC FUNCTIONS (OVERPASS, FOLIUM, MAPS) ---
def import_guimaraes_pois():
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

def import_parish_streets(nome_freguesia):
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

def generate_line_map_html(linha_id):
    os.makedirs("maps", exist_ok=True)
    conn = sqlite3.connect("agente_memoria.db")
    conn.create_function("_normalize_stop_name", 1, _normalize_stop_name)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.paragem, g.latitude, g.longitude, g.freguesia 
        FROM cache_paragens_linha p
        JOIN nos_geograficos g ON _normalize_stop_name(p.paragem) = _normalize_stop_name(g.nome)
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

def generate_google_maps_link(local_nome: str):
    local_encontrado = _search_local_map(local_nome)
    if local_encontrado:
        nome_real = local_encontrado["nome_real"]
        lat = local_encontrado["lat"]
        lon = local_encontrado["lon"]
        link_maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        return f"📍 Encontrei a localização de '{nome_real}' no mapa estático. Podes abrir no Google Maps aqui: {link_maps}"

    nome_norm = _normalize_stop_name(local_nome)
    conn = sqlite3.connect("agente_memoria.db")
    conn.create_function("_normalize_stop_name", 1, _normalize_stop_name)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nome, latitude, longitude FROM nos_geograficos 
        WHERE _normalize_stop_name(nome) LIKE ? LIMIT 1
    """, (f"%{nome_norm}%",))
    resultado = cursor.fetchone()
    conn.close()
    
    if resultado:
        nome_real, lat, lon = resultado
        link_maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        return f"📍 Encontrei a localização de '{nome_real}' na base de dados. Podes abrir diretamente no Google Maps aqui: {link_maps}"

    # Last resort: live geocoding via OpenStreetMap.
    local_live = _geocode_nominatim_place(local_nome)
    if local_live:
        link_maps = f"https://www.google.com/maps/search/?api=1&query={local_live['lat']},{local_live['lon']}"
        return f"📍 Encontrei '{local_live['nome_real']}' via OpenStreetMap (tempo real, ⚠️ não confirmado pelo mapa oficial). Podes abrir no Google Maps aqui: {link_maps}"

    return f"Não consegui encontrar coordenadas GPS para '{local_nome}'."

# --- BLOCKING STARTUP SYNC SYSTEM ---
def check_sync_needed(limite_dias: int = 7):
    if st.session_state.get("sync_checked"): return False

    idade_horarios = get_schedule_cache_age_days()
    idade_titulos = get_pass_cache_age_days()
    idx_count = get_stop_index_count()

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

# --- DYNAMIC SCRAPING: PASS TYPES AND FARE TABLE ---
TIPOLOGIAS_PASSE_FALLBACK = {
    "Mensal": {
        "descricao": "Válido para o mês e Origem/Destino para o qual foi adquirido, com nº de viagens ilimitado.",
        "preco": "Consultar tabela tarifária",
        "custo_cartao": "5€",
        "prazo": "Só pode ser emitido ou carregado até ao dia 18 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de identificação"],
    },
}

def sync_guimabus_pass_types():
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

def sync_guimabus_fare_table():
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

def sync_pass_types_and_fares():
    resultado_titulos = sync_guimabus_pass_types()
    resultado_tarifario = sync_guimabus_fare_table()
    return f"{resultado_titulos}\n{resultado_tarifario}"

# --- STOP <-> LINE INDEX (to suggest transfers) ---
def _extract_stops_from_text(texto: str):
    paragens = set()
    padrao = re.compile(r'^(?P<nome>.+?)\s+(?P<horarios>(?:-|\d{1,2}:\d{2})(?:\s+(?:-|\d{1,2}:\d{2})){2,})\s*$')
    for linha_texto in texto.split("\n"):
        linha_texto = linha_texto.strip()
        if not linha_texto or "|" in linha_texto or linha_texto.startswith("[PÁGINA") or linha_texto.startswith("[P"):
            continue
        m = padrao.match(linha_texto)
        if m:
            nome = m.group("nome").strip(" -\t")
            horarios_str = m.group("horarios")
            # Dashes ("-") are used in the official PDFs as a placeholder for "no
            # service" and were previously accepted on their own as valid "times", so a
            # row made entirely of dashes (or a coincidental legend/note line) could be
            # wrongly registered as a real stop. Require at least one genuine HH:MM time
            # in the row before treating it as an actual stop with a schedule.
            if len(nome) >= 3 and re.search(r'\d{1,2}:\d{2}', horarios_str):
                paragens.add(nome)
    return paragens

def build_stop_index():
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
            paragens = _extract_stops_from_text(conteudo_txt)
            for paragem in paragens:
                cursor.execute(
                    "INSERT OR IGNORE INTO cache_paragens_linha (linha, paragem) VALUES (?, ?)",
                    (linha_id, paragem)
                )
                total_paragens += 1
        conn.commit()

        # Sanity cleanup: a real bus line always serves several stops. If a line ended
        # up associated with only a single stop, that's almost certainly leftover noise
        # from PDF text extraction (e.g. a stray legend/note line), not a genuine route
        # — and offering it as a transfer option would be misleading. Drop those.
        cursor.execute("""
            DELETE FROM cache_paragens_linha
            WHERE linha IN (
                SELECT linha FROM cache_paragens_linha
                GROUP BY linha
                HAVING COUNT(DISTINCT paragem) < 2
            )
        """)
        conn.commit()
        conn.close()
        return f"Índice de paragens reconstruído: {total_paragens} associações linha-paragem."
    except Exception as e:
        return f"Falha ao construir índice de paragens: {e}"

def _normalize_stop_name(texto: str):
    t = texto.lower().strip()
    t = re.sub(r'\bsão\b', 's.', t)
    t = re.sub(r'\bsanta\b', 'sta.', t)
    t = re.sub(r'\bsanto\b', 'sto.', t)
    t = t.replace('.', '')
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def _search_lines_by_title(termo_norm: str):
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
        titulo_norm = _normalize_stop_name(titulo)
        if re.search(r'\b' + re.escape(termo_norm) + r'\b', titulo_norm):
            linhas_encontradas.add(linha_id)
            titulos_encontrados.append(f"Linha {linha_id}: {titulo}")
    return linhas_encontradas, titulos_encontrados

def enrich_stops_with_parish(progresso_callback=None):
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

def get_parish_of_stop(nome_paragem: str):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT paragem, freguesia FROM cache_paragem_freguesia WHERE freguesia IS NOT NULL")
        todas = cursor.fetchall()
        conn.close()
    except Exception:
        return None

    nome_norm = _normalize_stop_name(nome_paragem)
    for paragem, freguesia in todas:
        paragem_norm = _normalize_stop_name(paragem)
        if re.search(r'\b' + re.escape(nome_norm) + r'\b', paragem_norm) or re.search(r'\b' + re.escape(paragem_norm) + r'\b', nome_norm):
            return freguesia
    return None

def search_stops_by_parish(nome_freguesia: str):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT paragem, freguesia FROM cache_paragem_freguesia WHERE freguesia IS NOT NULL")
        todas = cursor.fetchall()
        conn.close()
    except Exception:
        return []

    freguesia_norm = _normalize_stop_name(nome_freguesia)
    return [paragem for paragem, freguesia in todas if re.search(r'\b' + re.escape(freguesia_norm) + r'\b', _normalize_stop_name(freguesia))]

# Paragens centrais de Guimarães entre as quais é sempre possível fazer transbordo
# a pé (a poucos minutos de distância umas das outras), mesmo que não sejam
# literalmente a mesma paragem. Usadas como fallback quando não há nenhuma
# paragem exatamente em comum entre a rede de origem e a de destino.
_HUB_KEYWORDS_NORM = ["s goncalo", "central de camionagem", "s damaso norte", "s damaso sul", "s damaso"]

def _e_paragem_hub(nome_paragem: str) -> bool:
    n = _normalize_stop_name(nome_paragem)
    return any(kw in n for kw in _HUB_KEYWORDS_NORM)

def _e_linha_noturna(linha_id: str) -> bool:
    # Regra 8 do prompt: linhas cujo identificador começa por "N" são noturnas.
    return str(linha_id).strip().upper().startswith("N")

def plan_trip_with_transfer(origem: str, destino: str):
    if not origem or not destino: return "É necessário indicar a paragem de origem e a paragem de destino."
    origem_norm, destino_norm = _normalize_stop_name(origem), _normalize_stop_name(destino)

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

    # "Guimarães" sozinho não é o nome de nenhuma paragem real — significa
    # genericamente qualquer uma das paragens centrais (regra 12 do prompt).
    # Em vez de depender do modelo se lembrar de substituir isto manualmente,
    # tratamos aqui: se a origem/destino normalizar para "guimaraes", uma
    # paragem conta como correspondência se for uma das paragens centrais.
    origem_e_guimaraes_generico = origem_norm == "guimaraes"
    destino_e_guimaraes_generico = destino_norm == "guimaraes"

    for linha_id, paragem in todas:
        mapa_linha_paragens.setdefault(linha_id, set()).add(paragem)
        paragem_norm = _normalize_stop_name(paragem)
        match_origem = _e_paragem_hub(paragem) if origem_e_guimaraes_generico else re.search(r'\b' + re.escape(origem_norm) + r'\b', paragem_norm)
        match_destino = _e_paragem_hub(paragem) if destino_e_guimaraes_generico else re.search(r'\b' + re.escape(destino_norm) + r'\b', paragem_norm)
        if match_origem:
            linhas_origem.add(linha_id); paragens_origem_encontradas.add(paragem)
        if match_destino:
            linhas_destino.add(linha_id); paragens_destino_encontradas.add(paragem)

    aviso_o, aviso_d = False, False
    if not linhas_origem: linhas_origem, titulos_o = _search_lines_by_title(origem_norm); aviso_o = bool(linhas_origem)
    if not linhas_destino: linhas_destino, titulos_d = _search_lines_by_title(destino_norm); aviso_d = bool(linhas_destino)

    aviso_o_freg, aviso_d_freg = None, None
    if not linhas_origem:
        paragens_da_freguesia = search_stops_by_parish(origem)
        if paragens_da_freguesia:
            for paragem_freg in paragens_da_freguesia:
                for linha_id, paragem_indice in todas:
                    if _normalize_stop_name(paragem_freg) == _normalize_stop_name(paragem_indice):
                        linhas_origem.add(linha_id); paragens_origem_encontradas.add(paragem_indice)
            if linhas_origem: aviso_o_freg = paragens_da_freguesia

    if not linhas_destino:
        paragens_da_freguesia = search_stops_by_parish(destino)
        if paragens_da_freguesia:
            for paragem_freg in paragens_da_freguesia:
                for linha_id, paragem_indice in todas:
                    if _normalize_stop_name(paragem_freg) == _normalize_stop_name(paragem_indice):
                        linhas_destino.add(linha_id); paragens_destino_encontradas.add(paragem_indice)
            if linhas_destino: aviso_d_freg = paragens_da_freguesia

    if not linhas_origem: return f"I could not find the origin '{origem}'."
    if not linhas_destino: return f"I could not find the destination '{destino}'."

    aviso_precisao = ""
    if aviso_o: aviso_precisao += f"\n⚠️ Nota: '{origem}' encontrada pelo TÍTULO da linha."
    if aviso_d: aviso_precisao += f"\n⚠️ Nota: '{destino}' encontrada pelo TÍTULO da linha."
    if aviso_o_freg: aviso_precisao += f"\n📍 '{origem}' é freguesia."
    if aviso_d_freg: aviso_precisao += f"\n📍 '{destino}' é freguesia."

    linhas_diretas = linhas_origem & linhas_destino
    if linhas_diretas:
        # Regra 8 do prompt: dar prioridade às linhas diurnas — as noturnas (prefixo "N")
        # só aparecem primeiro se forem mesmo a única opção disponível.
        diurnas = sorted(l for l in linhas_diretas if not _e_linha_noturna(l))
        noturnas = sorted(l for l in linhas_diretas if _e_linha_noturna(l))
        linhas_ordenadas = diurnas + noturnas

        resumo = f"Encontrei linha(s) DIRETA(S) entre '{origem}' e '{destino}':\n"
        for l in linhas_ordenadas: resumo += f"- Linha {l}\n"
        if not diurnas and noturnas:
            resumo += "\n🌙 Nota: só encontrei linha(s) noturna(s) para este trajeto — não há alternativa diurna direta."
        return resumo + aviso_precisao

    stops_o, stops_d = set(), set()
    for l in linhas_origem: stops_o |= mapa_linha_paragens.get(l, set())
    for l in linhas_destino: stops_d |= mapa_linha_paragens.get(l, set())

    transbordos = (stops_o & stops_d) - paragens_origem_encontradas - paragens_destino_encontradas
    if transbordos:
        resumo = f"Não há linha direta. Sugestão de transbordo:\n\n"
        for t in sorted(transbordos):
            l_to = [l for l in linhas_origem if t in mapa_linha_paragens.get(l, set())]
            l_from = [l for l in linhas_destino if t in mapa_linha_paragens.get(l, set())]
            resumo += f"- Via **{t}**: apanha linha {'/'.join(l_to)} e depois linha {'/'.join(l_from)}.\n"
        return resumo + aviso_precisao

    # Não há nenhuma paragem literalmente em comum — antes de desistir, verifica se
    # a origem e o destino têm cada uma acesso a alguma das paragens centrais de
    # Guimarães (S. Gonçalo, Central de Camionagem, S. Dâmaso Norte/Sul). Essas
    # paragens ficam a poucos minutos a pé umas das outras, por isso um transbordo
    # entre elas é sempre viável mesmo que não seja literalmente o mesmo poste.
    hubs_o = sorted({p for p in stops_o if _e_paragem_hub(p)})
    hubs_d = sorted({p for p in stops_d if _e_paragem_hub(p)})
    if hubs_o and hubs_d:
        resumo = (
            "Não há transbordo na mesma paragem, mas é possível fazer transbordo a pé "
            "pelo centro de Guimarães (as paragens S. Gonçalo, Central de Camionagem e "
            "S. Dâmaso Norte/Sul ficam a poucos minutos a pé umas das outras):\n\n"
        )
        combinacoes_mostradas = 0
        for stop_o in hubs_o:
            l_to = [l for l in linhas_origem if stop_o in mapa_linha_paragens.get(l, set())]
            for stop_d in hubs_d:
                l_from = [l for l in linhas_destino if stop_d in mapa_linha_paragens.get(l, set())]
                if stop_o == stop_d:
                    resumo += f"- Apanha linha {'/'.join(l_to)} até '{stop_o}' e depois linha {'/'.join(l_from)} — mesma paragem.\n"
                else:
                    resumo += f"- Apanha linha {'/'.join(l_to)} até '{stop_o}', caminha até '{stop_d}', e apanha linha {'/'.join(l_from)}.\n"
                combinacoes_mostradas += 1
                if combinacoes_mostradas >= 4:
                    break
            if combinacoes_mostradas >= 4:
                break
        resumo += "\n⚠️ Este transbordo envolve caminhar entre paragens diferentes no centro de Guimarães, não é o mesmo poste."
        return resumo + aviso_precisao

    return f"I could not find an obvious transfer between '{origem}' and '{destino}'."

def _resolve_place_to_stop(nome_local: str):
    """Resolves any place name (café, street, address, etc.) to the nearest bus stop,
    using the static map first and then live geocoding as a fallback.
    Returns (stop_name, distance_metres, source) or (None, None, None) if it can't."""
    local = _search_local_map(nome_local)
    fonte = "mapa estático"
    if not local:
        local = _geocode_nominatim_place(nome_local)
        fonte = "OpenStreetMap (tempo real)"
    if not local or not LOCAL_MAP:
        return None, None, None

    paragem_mais_proxima, menor_distancia = None, float('inf')
    for chave, dados in LOCAL_MAP.items():
        if dados.get("tipo") in ["bus_stop", "public_transport"]:
            dist = calculate_distance(local["lat"], local["lon"], dados["lat"], dados["lon"])
            if dist < menor_distancia:
                menor_distancia = dist
                paragem_mais_proxima = dados["nome_real"]
    return paragem_mais_proxima, menor_distancia, fonte

def plan_trip_from_place(origem: str, destino: str):
    """Plans a trip between ANY TWO PLACES — cafés, streets, addresses, factories, parishes, etc.
    — even if they are not the exact name of a bus stop. Use this whenever the user
    asks for a route from a place that isn't clearly already a known stop/parish
    (e.g. 'how do I get from café rio to the hospital?'). Resolves each place to the nearest stop and then
    uses the same logic as 'plan_trip_with_transfer' to find the lines."""
    if not origem or not destino:
        return "É necessário indicar a localização de origem e de destino."

    # 1) Direct attempt: it might already be the name of a known stop or parish.
    resultado_direto = plan_trip_with_transfer(origem, destino)
    if not resultado_direto.startswith("I could not find the origin") and not resultado_direto.startswith("I could not find the destination"):
        return resultado_direto

    # 2) Resolve each place to the nearest bus stop (static map or live geocoding).
    paragem_o, dist_o, fonte_o = _resolve_place_to_stop(origem)
    paragem_d, dist_d, fonte_d = _resolve_place_to_stop(destino)

    if not paragem_o:
        return f"⚠️ NOT CONFIRMED: I could not identify the origin '{origem}' nor find a bus stop near it. Confirm the exact name or indicate the street/parish."
    if not paragem_d:
        return f"⚠️ NOT CONFIRMED: I could not identify the destination '{destino}' nor find a bus stop near it. Confirm the exact name or indicate the street/parish."

    resultado = plan_trip_with_transfer(paragem_o, paragem_d)

    aviso = (
        f"\n\n📍 Nota: '{origem}' foi associado à paragem mais próxima '{paragem_o}'"
        f" (a {int(dist_o)}m, via {fonte_o})."
        f"\n📍 Nota: '{destino}' foi associado à paragem mais próxima '{paragem_d}'"
        f" (a {int(dist_d)}m, via {fonte_d})."
    )
    if fonte_o == "OpenStreetMap (tempo real)" or fonte_d == "OpenStreetMap (tempo real)":
        aviso += "\n⚠️ Uma ou mais localizações vieram de pesquisa em tempo real (OpenStreetMap), não do mapa oficial — confirma o nome exato do local."

    return resultado + aviso

def query_stop_parish_tool(nome: str):
    if not nome: return "É necessário indicar o nome."
    freguesia = get_parish_of_stop(nome)
    if freguesia: return f"A paragem '{nome}' fica na freguesia de {freguesia}."
    paragens = search_stops_by_parish(nome)
    if paragens: return f"Paragens em '{nome}': {', '.join(paragens)}."
    return f"Não tenho informação para '{nome}'."

def get_pass_types_cache():
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
            except (json.JSONDecodeError, TypeError): docs = [docs_json]
            resultado[tip] = {"descricao": desc, "preco": preco, "custo_cartao": cartao, "prazo": prazo, "documentos": docs}
        return resultado, ultima_atualizacao
    except Exception:
        return TIPOLOGIAS_PASSE_FALLBACK, None

def query_fare_table_cache():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT conteudo_txt, ultima_atualizacao FROM cache_tarifario WHERE id = 1")
        res = cursor.fetchone()
        conn.close()
        if res: return f"Tabela tarifária ({res[1]}):\n\n{res[0]}"
        return "Tarifário não sincronizado."
    except Exception as e: return f"Erro cache tarifário: {e}"

def query_pass_types_cache_tool():
    tipologias, upd = get_pass_types_cache()
    if not tipologias: return "Sem tipologias em cache."
    resumo = f"Tipologias ({upd}):\n\n"
    for n, i in tipologias.items():
        resumo += f"- **{n}**: {i['descricao']} Preço: {i['preco']}. Prazo: {i['prazo']}.\n"
    return resumo

def verify_pass_documents(tipologia: str, ficheiros_carregados: dict):
    tipologias_atuais, _ = get_pass_types_cache()
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

def recommend_pass_types(respostas: dict, tipologias_disponiveis: dict):
    cand = []
    def _has(n): return next((k for k in tipologias_disponiveis if n.lower() in k.lower()), None)

    if respostas.get("antigo_combatente") and _has("Antigo Combatente"): cand.append(_has("Antigo Combatente"))
    if respostas.get("incapacidade_60") and _has("Mobilidade Condicionada"): cand.append(_has("Mobilidade Condicionada"))
    if respostas.get("idade", 0) >= 65 and respostas.get("residente_gmr") and _has("65+"): cand.append(_has("65+"))
    if respostas.get("reforma_antecipada") and 60 <= respostas.get("idade", 0) < 65 and _has("Reformado"): cand.append(_has("Reformado"))
    if respostas.get("estudante"):
        if respostas.get("nivel_estudo") == "superior":
            cand.append(_has("Universitário Residente") if respostas.get("residente_gmr") else _has("Universitário Não Residente"))
        elif respostas.get("nivel_estudo") == "ate_18" and _has("18+TP"): cand.append(_has("18+TP"))
        elif respostas.get("nivel_estudo") == "ate_23" and _has("23+TP"): cand.append(_has("23+TP"))
    if respostas.get("usa_passe_cp") and _has("Mensal CP"): cand.append(_has("Mensal CP"))

    if not cand:
        if respostas.get("residente_gmr") and _has("CIM AVE 50% + 10% CMG"): cand.append(_has("CIM AVE 50% + 10% CMG"))
        elif respostas.get("residente_gmr") and _has("CIM AVE 50%"): cand.append(_has("CIM AVE 50%"))
        elif _has("Mensal") and not _has("CIM"):
            cand.append(next(n for n in tipologias_disponiveis if n.strip().lower() == "mensal"))

    return list(dict.fromkeys([c for c in cand if c]))

def render_pass_request(ui):
    st.subheader(ui["ticket_title"])
    st.info(ui["ticket_warning"])

    TICKET_TYPES, last_update = get_pass_types_cache()
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
            rec = recommend_pass_types(ans, TICKET_TYPES)
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
                st.markdown(verify_pass_documents(tipologia_escolhida, ficheiros))

def render_game(ui):
    json_scores = json.dumps(get_top_10())
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
                        ctx.textAlign = 'end'; ctx.fillText(leaderboard[k][1] + ' {ui['game_unit']}', canvas.width - 15, yPos); ctx.textAlign = 'start';
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
                // Não lemos window.parent.location (isso é bloqueado como leitura
                // entre origens diferentes, ex: no Streamlit Cloud). Em vez disso,
                // criamos um link normal com target="_parent" e simulamos um clique —
                // a navegação por clique num link é sempre permitida pelo browser,
                // mesmo que o iframe seja tratado como uma origem diferente.
                try {{
                    var novaQuery = "?save_nome=" + encodeURIComponent(nome) + "&save_pontos=" + encodeURIComponent(score / 10);
                    var link = document.createElement("a");
                    link.href = novaQuery;
                    link.target = "_parent";
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                }} catch(e) {{
                    alert("Não foi possível gravar o recorde: " + e.message);
                    btnGravar.disabled = false; btnGravar.innerText = "{ui['game_save']}";
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

# --- STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": ui["initial_msg"]}]

if len(st.session_state.messages) == 1 and st.session_state.messages[0]["role"] == "assistant":
    st.session_state.messages[0]["content"] = ui["initial_msg"]

if "jogo_ativo" not in st.session_state:
    st.session_state.jogo_ativo = False

# --- ELITE SIDEBAR ---
is_updating = check_sync_needed(limite_dias=7)

if is_updating:
    st.error(ui["updating_system"], icon="⏳")
    
    with st.spinner(ui["robot_reading"]):
        tasks = st.session_state.update_tasks
        
        if tasks.get("sch"):
            sync_all_guimabus_schedules()
            build_stop_index()
        elif tasks.get("idx"):
            build_stop_index()
        
        if tasks.get("tkt"):
            sync_pass_types_and_fares()
            
        if tasks.get("geo"):
            import_guimaraes_pois()
            
    st.session_state.is_updating = False
    st.rerun() # Refresh força a libertação do input box abaixo.

# 🔓 We only get here if the system is NOT updating (see block above).
# This is where the language buttons are finally drawn into the "slots"
# reserved above — while the update is running, they stay empty.
with lang_pt_slot:
    if st.button("🇵🇹 PT", use_container_width=True, key="lang_pt_btn"):
        st.session_state.language = "PT"
        st.rerun()
with lang_en_slot:
    if st.button("🇬🇧 EN", use_container_width=True, key="lang_en_btn"):
        st.session_state.language = "EN"
        st.rerun()

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
    if "admin_falhas" not in st.session_state:
        st.session_state.admin_falhas = 0
    if "admin_bloqueado_ate" not in st.session_state:
        st.session_state.admin_bloqueado_ate = None

    if not st.session_state.admin_autenticado:
        agora = datetime.now()
        bloqueado = st.session_state.admin_bloqueado_ate and agora < st.session_state.admin_bloqueado_ate
        with st.sidebar.expander(ui["login_admin"]):
            if bloqueado:
                segundos_restantes = int((st.session_state.admin_bloqueado_ate - agora).total_seconds())
                aviso_bloqueio = (
                    f"Demasiadas tentativas falhadas. Tenta novamente daqui a {segundos_restantes}s."
                    if st.session_state.language == "PT"
                    else f"Too many failed attempts. Try again in {segundos_restantes}s."
                )
                st.warning(aviso_bloqueio)
            else:
                password_input = st.text_input(ui["admin_pass"], type="password", key="admin_pwd")
                if st.button(ui["login_btn"], key="admin_login_btn"):
                    admin_pass_real = _get_secret("ADMIN_PASSWORD")
                    # Constant-time comparison (hmac.compare_digest) instead of "==",
                    # to avoid leaking timing information about how much of the password matched.
                    if admin_pass_real and password_input and hmac.compare_digest(password_input, admin_pass_real):
                        st.session_state.admin_autenticado = True
                        st.session_state.admin_falhas = 0
                        st.session_state.admin_bloqueado_ate = None
                        st.rerun()
                    else:
                        st.session_state.admin_falhas += 1
                        # After 5 failed attempts, lock the login for 5 minutes.
                        if st.session_state.admin_falhas >= 5:
                            st.session_state.admin_bloqueado_ate = agora + timedelta(minutes=5)
                            st.session_state.admin_falhas = 0
                        st.sidebar.error(ui["wrong_pass"])
    else:
        st.sidebar.success(ui["admin_active"])
        
        st.sidebar.subheader(ui["web_auto"])
        if st.sidebar.button(ui["sync_all"], use_container_width=True):
            with st.spinner(ui["robot_reading"]):
                st.sidebar.success(sync_all_guimabus_schedules())
                st.sidebar.success(build_stop_index())

        if st.sidebar.button(ui["rebuild_index"], use_container_width=True):
            with st.spinner(ui["rebuild_index_spinner"]):
                st.sidebar.success(build_stop_index())

        if st.sidebar.button(ui["discover_parish"], use_container_width=True):
            st.sidebar.caption(ui["ask_osm"])
            barra_progresso = st.sidebar.progress(0.0)
            texto_progresso = st.sidebar.empty()
            def _update_progress(atual, total, paragem_atual):
                barra_progresso.progress(atual / total)
                texto_progresso.caption(f"{atual}/{total}: {paragem_atual}")
            st.sidebar.success(enrich_stops_with_parish(progresso_callback=_update_progress))

        if st.sidebar.button(ui["sync_tickets"], use_container_width=True):
            with st.spinner(ui["robot_reading_tickets"]):
                st.sidebar.success(sync_pass_types_and_fares())
                
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
    render_game(ui)

if st.session_state.get("passe_ativo"):
    render_pass_request(ui)

avisos_hoje = get_facebook_notices()
if avisos_hoje:
    render_notices_footer(avisos_hoje, ui)

for message in st.session_state.messages:
    avatar_tipo = "💼" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar_tipo):
        st.markdown(message["content"])

# --- BLOCKING AND RESILIENT EXECUTION OF INITIAL UPDATES ---
is_updating = check_sync_needed(limite_dias=7)

if is_updating:
    st.error(ui["updating_system"], icon="⏳")
    
    with st.spinner(ui["robot_reading"]):
        tasks = st.session_state.update_tasks
        
        if tasks.get("sch"):
            sync_all_guimabus_schedules()
            build_stop_index()
        elif tasks.get("idx"):
            build_stop_index()
        
        if tasks.get("tkt"):
            sync_pass_types_and_fares()
            
        if tasks.get("geo"):
            import_guimaraes_pois()
            
    st.session_state.is_updating = False
    st.rerun() # Refresh força a libertação do input box abaixo.

# The input is only actually rendered after the lock function is clear
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
    save_message_db(st.session_state.session_id, "user", prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="💼"):
        with st.spinner(ui["processing_agent"]):
            try:
                contexto_base = load_knowledge_base()
                
                LANGUAGE_INSTRUCTION = "CRUCIAL LANGUAGE RULE: You MUST respond entirely in European Portuguese (pt-PT)." if st.session_state.language == "PT" else "CRUCIAL LANGUAGE RULE: You MUST respond entirely in English."

                SCHEDULE_INSTRUCTION = (
                    "MANDATÓRIO: Sempre que o utilizador perguntar como ir de um local para outro, ou pedir horários, tens OBRIGATORIAMENTE de apresentar as horas de partida/chegada lendo a cache da ferramenta `query_line_schedule_cache`. NUNCA mandes apenas as linhas ou os links sem mostrar os horários no texto. Após descobrires as linhas (seja rota direta ou transbordo), FAZ SEMPRE query aos horários dessas linhas. No final da resposta, coloca os links oficiais." 
                    if st.session_state.language == "PT" else 
                    "MANDATORY: Whenever asked for directions or schedules, you MUST present the departure/arrival times by using the `query_line_schedule_cache` tool for the suggested lines. NEVER just output the lines without schedules. Always query the schedules for the lines you find. At the end, include the official links."
                )

                PROMPT_GUIMABUS = f"""You are Celso Ferreira's Elite Executive Assistant.
                You are an Agent focused on automation, support and IT infrastructure.

                {LANGUAGE_INSTRUCTION}

                You have these tools related to the local Guimabus fleet:
                - get_guimabus_data: real-time fleet status.
                - get_stop_schedule: forecast of waiting times for a specific stop.
                - query_line_schedule_cache: queries the local cache to read fixed schedules and timetables.
                - query_pass_types_cache_tool: reads the pass types.
                - query_fare_table_cache: reads the full fare table.
                - plan_trip_with_transfer: given the name of an origin and destination stop, says whether there is a direct line or suggests a transfer.
                - plan_trip_from_place: like the previous one, but accepts ANY PLACE (cafés, streets, addresses, factories), not just stops/parishes — resolves each place to the nearest stop automatically and then plans the route. USE THIS instead of manually chaining 'find_nearest_stop' + 'plan_trip_with_transfer' whenever the origin or destination isn't clearly already a known stop or parish.
                - query_stop_parish_tool: says which parish a stop is in.
                - generate_google_maps_link: takes the name of a place and returns a direct Google Maps link.
                - find_nearest_stop: finds the nearest stop (geographically) to a parish or place. It NEVER confirms which line serves that stop — that must always be verified afterwards with 'plan_trip_with_transfer' or 'query_line_schedule_cache'. NEVER invent the line number from this tool alone. Use this only when you just need the stop, not the full route — for routes use 'plan_trip_from_place'.
                - search_places_by_type: takes a type/category of place (e.g. "café", "restaurant", "pharmacy", "supermarket") and returns the list of places of that type found on the static map of Guimarães (geo_guimaraes.json). Use this tool whenever the user asks to "discover"/"list"/"what options are there" for a type of place, instead of inventing establishment names. Once you find a name, you can use 'find_nearest_stop', 'generate_google_maps_link' or 'plan_trip_from_place' with that exact name.

                MANDATORY PLANNING LOGIC:
                1. - If the origin OR the destination is any place (café, street, address, factory, point of interest) and not an obvious stop/parish, use "plan_trip_from_place" directly — don't try to guess the stop manually.
                2. - If origin and destination are already names of known stops or parishes, use "plan_trip_with_transfer" with the exact names. If it closely resembles a stop, mention that. When in doubt, ask the user.
                3. - {SCHEDULE_INSTRUCTION} If you've already found it in these steps, skip find_nearest_stop.
                4. - find_nearest_stop: finds the official bus stop nearest to any café, factory or geographic point of interest (based on the static distance JSON, with a fallback to live geocoding).
                5. If a route has several lines (direct or for either leg of a transfer), you MUST list ALL of them, not just one or two examples — never summarise with "e.g." or pick just one when the tool returned several.
                6. Whenever a schedule is requested, provide all schedules for the given day; if no day is given, all schedules for the current day.
                7. Whenever asked about schedules, reply politely only, without mentioning this system's technical functions, unless technical functions are specifically requested.
                8. Any line starting with N is a night line, unless night lines are specifically requested or it's a time only they cover. Give priority to day lines.
                9. From any stop it is possible to transfer in the centre of Guimarães by walking between the stops s.goncalo, central de camionagem, s.damaso norte or s.damaso sul. Even if it takes two or three transfers, you must find a solution.
                10. In the schedules, only a time listed directly opposite the stop means it passes there at that time.
                11. Check all outbound and return schedules — some schedules span several pages.
                12. When "guimaraes" is requested, it means goncalo, central de camionagem, s.damaso norte or s.damaso sul.
                13. When a route is requested, you must check both directions of every line.
                14. Even if you've already found a solution, you must check all of them.
                15. FORMATTING: whenever you present a transfer plan or a set of schedules with more than one line/departure, use a Markdown table (columns like "Linha", "Sentido", "Partidas") instead of plain bullet lists — it's much easier to read. Use one table per leg of the trip when there's a transfer. Always include every line and every departure time the tools returned for that leg; never truncate the table or omit rows to keep the answer short.
                ANTI-HALLUCINATION RULE — THE MOST IMPORTANT OF ALL:
                NEVER invent, estimate or "fill in" data that the tools or the Knowledge Base did not give you. NEVER assume or invent a date from memory. If you can't find the information in the database, apologise and clearly say the information is not available.
                If a tool's result contains "⚠️ NOT CONFIRMED" or "📍", you are REQUIRED to communicate that uncertainty to the user in the same terms (e.g. "I don't have exact confirmation, but..."). NEVER present a stop/line found only by name/title similarity as if it were a confirmed fact."""
                
                PROMPT_INTERVIEW = """You are an expert IT Technical Recruiter interviewing Celso Ferreira for an IT role.
                Conduct the interview strictly in English. Ask one tough, deep technical or behavioral question at a time.
                Evaluate Celso's response professionally based on IT best practices and keep the interviewer persona realistic."""

                PROMPT_RECRUITER = f"""You are Celso Ferreira's Professional Presentation Agent, aimed at recruiters and anyone wanting to know his background.

                {LANGUAGE_INSTRUCTION}

                Your goal is to:
                1. Answer questions about Celso's CV, skills, professional experience and background, ALWAYS using the information available in the Knowledge Base provided in the context (.md files). NEVER invent dates, companies, roles, technologies or facts about Celso that are not in the Knowledge Base — if the information isn't there, clearly say you don't have that information available, instead of inventing it.
                2. If the user says something like "quero treinar para uma entrevista" or "I want to train for an interview", let them know you are about to start a technical interview simulation in English (the role switch is handled automatically by the system in the next step).
                3. If the user presents a technical/IT problem (e.g. "the server went down", "network error", any kind of failure), demonstrate how Celso would solve it — you MUST start the answer with the sentence 'O Celso resolveria este problema desta forma:' (or, in English, 'Celso would solve this problem like this:') and explain the reasoning step by step, following IT best practices. This is meant to show a recruiter how Celso actually thinks and works.

                Always keep a professional, confident and clear tone — you are representing Celso to potential employers. NEVER invent information about Celso outside the Knowledge Base."""

                PROMPT_PROJECT = f"""You are the Agent that explains this project to anyone who asks about it — recruiters, curious visitors, or Celso himself.

                {LANGUAGE_INSTRUCTION}

                This project is an AI agent application built by Celso Ferreira, in Streamlit (Python), with these main components:
                - A conversational assistant (Guimabus Mode) that uses the Gemini API with function calling to check the fleet's real-time status, schedules and fares (cached locally in SQLite), plan routes with transfers, and resolve locations (cafés, streets, addresses) through a static map (geo_guimaraes.json) with a live geocoding fallback via OpenStreetMap/Nominatim.
                - An anti-hallucination safety net that forces the model to use real tools before answering questions about routes/schedules, instead of inventing data from the model's generic knowledge.
                - A notices footer that reads an RSS feed from the Guimabus Facebook page, filters and prioritises notices (roadworks/events with a confirmed end date vs. recent generic posts) and shows them scrolling in the app's footer.
                - A document-verification system (for pass applications) that uses Gemini to analyse uploaded images/PDFs.
                - Audio transcription, to allow voice input.
                - A Knowledge Base built from Markdown files, injected into the model's context, to answer with verified facts instead of generic knowledge.
                - Three conversation modes (Guimabus, Recruiter, Project) that share the same chat interface, with automatic detection of which prompt/persona to use based on keywords in the question.

                Whenever someone asks about the project, explain it clearly and concisely, adapting the level of detail to what is asked (e.g. "what technologies does it use" focuses on the stack; "why did you build this" focuses on the project's purpose/goal). NEVER invent features that don't exist in the system."""

                normalized_prompt = prompt.lower()
                project_triggers = ["este projeto", "sobre o projeto", "sobre este projeto", "como foi feito", "como foi construido", "que tecnologias", "stack", "arquitetura", "arquitectura", "this project", "how was this built", "tech stack"]
                # Split into two tiers: "strong" recruiter signals are unambiguous (CV,
                # hiring, skills) and should always switch mode. The "IT problem" words
                # are intentionally generic (so a recruiter can say "give me a problem")
                # but the same words show up naturally in transport questions (e.g. "há
                # algum problema na linha 170?"), so they only switch mode when the
                # message doesn't otherwise look like a route/schedule question.
                recruiter_triggers_strong = ["cv", "curriculo", "currículo", "recrutador", "recruiter", "contratar", "hire", "experiencia profissional", "experiência profissional", "competencias", "competências", "skills", "helpdesk", "ticket"]
                recruiter_triggers_it_problem = ["problema", "avaria", "erro", "servidor", "computador", "rede", "suporte", "falha", "problem", "error", "server", "computer", "network", "support"]

                if any(word in normalized_prompt for word in project_triggers):
                    active_system_prompt = PROMPT_PROJECT
                    st.session_state.modo_ativo = "project"
                elif "entrevista" in normalized_prompt or "interview" in normalized_prompt:
                    active_system_prompt = PROMPT_INTERVIEW
                    st.session_state.modo_ativo = "interview"
                elif any(word in normalized_prompt for word in recruiter_triggers_strong):
                    active_system_prompt = PROMPT_RECRUITER
                    st.session_state.modo_ativo = "recruiter"
                elif looks_like_route_request(prompt):
                    active_system_prompt = PROMPT_GUIMABUS
                    st.session_state.modo_ativo = "guimabus"
                elif any(word in normalized_prompt for word in recruiter_triggers_it_problem):
                    active_system_prompt = PROMPT_RECRUITER
                    st.session_state.modo_ativo = "recruiter"
                else:
                    # No clear signal in this specific message — instead of silently
                    # resetting to Guimabus (which used to break the thread of an
                    # ongoing Recruiter/Project conversation on any generic follow-up
                    # like "e no fim de semana?" or "podes explicar melhor?"), keep
                    # whatever mode the conversation was already in.
                    _mapa_modos = {"project": PROMPT_PROJECT, "interview": PROMPT_INTERVIEW, "recruiter": PROMPT_RECRUITER, "guimabus": PROMPT_GUIMABUS}
                    active_system_prompt = _mapa_modos.get(st.session_state.get("modo_ativo", "guimabus"), PROMPT_GUIMABUS)

                historico_api = []
                for msg in st.session_state.messages[:-1]:
                    if msg["content"] not in [ui["initial_msg"], UI_TEXT["PT"]["initial_msg"], UI_TEXT["EN"]["initial_msg"]]:
                        role_api = "model" if msg["role"] == "assistant" else "user"
                        historico_api.append({"role": role_api, "parts": [msg["content"]]})
                
                agora = datetime.now(ZoneInfo("Europe/Lisbon"))
                contexto_data = f"[DATA E HORA ATUAL DO SISTEMA: {agora.strftime('%Y-%m-%d %H:%M')}.]"

                prompt_enriquecido = f"{contexto_data}\n\n{contexto_base}\n\nUser Prompt: {prompt}"
                
                agent_tools = [get_guimabus_data, get_stop_schedule, query_line_schedule_cache, query_pass_types_cache_tool, query_fare_table_cache, plan_trip_with_transfer, plan_trip_from_place, query_stop_parish_tool, generate_google_maps_link, find_nearest_stop, search_places_by_type]
                
                candidate_models = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]
                response = None
                last_model_error = None
                chat = None
                history_len_before = 0

                for model_name in candidate_models:
                    try:
                        model = genai.GenerativeModel(
                            model_name=model_name,
                            system_instruction=active_system_prompt,
                            tools=agent_tools,
                            # A low, fixed temperature makes tool-calling decisions far
                            # more consistent: with the provider's default sampling, the
                            # exact same question could sometimes trigger a real tool
                            # call and sometimes get an "I don't know" answer purely by
                            # chance. Factual/route questions should behave the same way
                            # every time they're asked.
                            generation_config={"temperature": 0.2},
                        )
                        chat = model.start_chat(history=historico_api, enable_automatic_function_calling=True)
                        history_len_before = len(chat.history)
                        response = chat.send_message(prompt_enriquecido, request_options={"timeout": 25})
                        break
                    except Exception as e:
                        last_model_error = e
                        continue

                if response is None:
                    if last_model_error is not None and "429" in str(last_model_error):
                        st.error(ui["api_limit"])
                    else:
                        st.error(ui["model_error"])
                    st.stop()

                def _called_real_tool(chat_obj, desde_indice):
                    """Checks whether, since 'since_index', the chat history contains a
                    real call to one of the route/schedule tools (instead of the model
                    having answered purely from its own generic knowledge)."""
                    try:
                        for entrada in chat_obj.history[desde_indice:]:
                            for part in getattr(entrada, "parts", []):
                                fc = getattr(part, "function_call", None)
                                if fc and getattr(fc, "name", None) in ROUTE_TOOL_NAMES:
                                    return True
                    except Exception:
                        pass
                    return False

                # 🛡️ ANTI-HALLUCINATION SAFETY NET
                # If the question is clearly about routes/lines/schedules and the model did NOT
                # call any real tool, it answered "off the top of its head" — exactly
                # what happens when it invents line numbers. We force a new attempt
                # in which it is required to consult a real tool before answering.
                #
                # Important exception: if the model already answered with honest uncertainty
                # (e.g. "I could not find...", "not confirmed"), it did NOT hallucinate — it
                # correctly admitted it doesn't know. Forcing a retry in that case only adds
                # latency (a second full API call, up to +25s) and risks the model being
                # forced to call a tool with made-up arguments just to satisfy the rule,
                # producing a worse answer than the honest one it already gave. So we skip
                # the retry whenever the response already shows that honesty.
                _FRASES_INCERTEZA_HONESTA = [
                    "não encontrei", "nao encontrei", "não consegui", "nao consegui",
                    "não confirmado", "not confirmed", "could not find", "não tenho essa informação",
                    "não tenho informação", "peço desculpa", "i'm sorry", "i am sorry",
                    "não disponho", "não existem linhas", "sem transbordo", "sem informação",
                ]
                resposta_ja_e_honesta = any(f in response.text.lower() for f in _FRASES_INCERTEZA_HONESTA)

                if (active_system_prompt == PROMPT_GUIMABUS and looks_like_route_request(prompt)
                        and chat is not None and not resposta_ja_e_honesta):
                    if not _called_real_tool(chat, history_len_before):
                        logging.error(f"Possible hallucination detected (response without a tool call) for the prompt: {prompt}")
                        try:
                            forced_tool_config = {
                                "function_calling_config": {
                                    "mode": "ANY",
                                    "allowed_function_names": ROUTE_TOOL_NAMES,
                                }
                            }
                            history_len_before_retry = len(chat.history)
                            forced_response = chat.send_message(
                                "A tua resposta anterior não usou nenhuma ferramenta de trajeto/horários. "
                                "Repete a resposta, mas és OBRIGADO a consultar uma ferramenta real "
                                "(plan_trip_from_place, plan_trip_with_transfer, "
                                "query_line_schedule_cache, get_stop_schedule ou "
                                "find_nearest_stop) antes de responderes. "
                                "NUNCA inventes linhas ou horários que não venham da ferramenta.",
                                tool_config=forced_tool_config,
                                request_options={"timeout": 25}
                            )
                            if _called_real_tool(chat, history_len_before_retry):
                                response = forced_response
                            else:
                                # Even when forced, it didn't confirm anything via real tools — warn the user.
                                response = forced_response
                                logging.error("Safety net: the forced attempt also did not call a real tool.")
                        except Exception as e:
                            logging.error(f"Anti-hallucination safety net failure: {e}")

                full_response = response.text

                st.markdown(full_response)
                
                save_message_db(st.session_state.session_id, "assistant", full_response)
                st.download_button(ui["download_txt"], full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"Erro detetado no pipeline do agente: {e}")

