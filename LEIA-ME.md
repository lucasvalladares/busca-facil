# Monitor de preços de iPhones no Paraguai

## O que tem nesta pasta

| Arquivo | Para que serve |
|---|---|
| `coletor.py` | Visita as lojas, salva os preços no banco e atualiza a página. **É o único que você precisa rodar.** |
| `normalizar.py` | Transforma nomes como `CEL IPHONE 16 6.1" 8GB+128GB` em `iPhone 16 128GB` e identifica a condição (Novo / Recondicionado / Sem lacre). |
| `pagina.py` | Prepara os dados, baixa as fotos e monta as páginas `relatorio-minimalista.html` e `relatorio-vibrante.html`. |
| `template-minimalista.html` / `template-vibrante.html` | O visual de cada versão. As cores ficam no topo de cada arquivo. |
| `fontes/` | Fontes Inter e Anton (para funcionar sem internet). |
| `cores_principais.py` | A cor principal de cada modelo, usada para escolher a foto. Edite aqui para trocar. |
| `fotos/` | Fotos dos modelos, baixadas uma vez das lojas (para a página funcionar sem internet). |
| `precos.db` | O banco de dados (SQLite). Criado na primeira coleta. Guarda todo o histórico. |
| `relatorio-minimalista.html` / `relatorio-vibrante.html` / `relatorio-vibrante-es.html` (espanhol) | As versões visuais da página. Abra com dois cliques. |
| `traducao_es.py` | Tabela de tradução da versão vibrante para o espanhol (a versão em espanhol é gerada a partir da vibrante). |
| `com.monitorprecos.coleta.plist` | Configuração do agendamento diário no Mac. |

## Rodar uma coleta manualmente

**Coleta de verdade** (acessa as lojas, guarda as cópias em `fixtures/` e publica o site):

```
cd ~/monitor-precos && python3 coletor.py --real
```

**Teste** (não acessa nenhuma loja: usa só as cópias de `fixtures/`, grava em `dev/` e não publica):

```
cd ~/monitor-precos && python3 coletor.py && open dev/relatorio-vibrante.html
```

### Testes (sem internet)

```
cd ~/monitor-precos && python3 testes.py
```

Confere: reconhecimento de nomes (636 nomes reais em `tests/nomes.json`), robots.txt de cada endereço usado,
os leitores de cada loja contra as cópias de `fixtures/` (precisam de uma coleta real antes), as regras de
educação (numa loja falsa local) e a trava contra queda. Depois de mudar o reconhecimento de nomes de propósito,
regrave a referência com `python3 testes.py --atualizar-nomes`.

### Trava contra quebra silenciosa e aviso
- Se uma loja trouxer **menos da metade** dos produtos da última coleta dela, os dados do dia são descartados
  (ficam os anteriores) e ela aparece como **SUSPEITA** no resumo — normalmente é o site que mudou.
- Na coleta real, se qualquer loja tiver problema (parada, erro ou suspeita), o Mac mostra uma **notificação**
  e os detalhes ficam em `coleta.log`.

### Regras de educação com as lojas (arquivo `educado.py`)
- No máximo 1 pedido a cada 3–5 segundos por loja (ou o intervalo pedido no robots.txt, se maior).
- O robots.txt de cada loja é lido e respeitado; endereços proibidos não são acessados.
- User-agent: `BuscaFacilBot/1.0 (+site do projeto; e-mail de contato)`.
- Erro 403, 429, 5xx, falha de conexão ou resposta com mais de 20 s: a loja para na hora, o motivo
  vai para o log (`coleta.log`) e ela não é acessada de novo no mesmo dia (tabela `pausas`).
- Por causa do robots.txt: na Visuar usamos as categorias (a busca é proibida) e na Bristol as
  categorias com filtro de marca (`?marca=`).

No fim aparece um resumo: produtos por loja, pedidos feitos, endereços pulados pelo robots.txt, tempo e problemas.
Para coletar sem publicar o site: `python3 coletor.py --real --sem-publicar`.

## Ligar a coleta automática (1x por dia, às 19h — horário do Paraguai)

Cole no Terminal (uma linha de cada vez):

```
cp ~/monitor-precos/com.monitorprecos.coleta.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.monitorprecos.coleta.plist
```

- **Testar agora, sem esperar as 19h:** `launchctl start com.monitorprecos.coleta` (é uma coleta real)
- **Ver o que aconteceu:** `cat ~/Library/Logs/monitor-precos.log`
- **Desligar:** `launchctl unload ~/Library/LaunchAgents/com.monitorprecos.coleta.plist`
- **Mudar o horário:** edite `Hour`/`Minute` no arquivo `.plist`, depois rode o `unload`, o `cp` e o `load` de novo.

**O Mac precisa estar acordado às 19h.** Dormindo (tampa fechada, na bateria), a coleta falha.
- A coleta roda com `caffeinate`, que impede o Mac de dormir até ela terminar.
- Para o Mac acordar sozinho às 18:58, rode uma vez (pede a senha): `sudo pmset repeat wakeorpoweron MTWRFSU 18:58:00`
- O mais seguro é deixar o Mac **na tomada** nesse horário.
- Se mesmo assim ele dormir no meio da coleta, o coletor percebe: não culpa as lojas, **não publica** o dia incompleto e mostra um aviso. Aí, com o Mac acordado, rode: `python3 coletor.py --real`

**Por que a pasta fica em `~/monitor-precos` (e não em Documentos):** o macOS bloqueia
programas agendados de acessar a pasta Documentos ("Operation not permitted"). Fora dela,
a coleta automática funciona sem precisar dar permissões extras.

## Site público (GitHub Pages)

- **Endereço:** https://lucasvalladares.github.io/busca-facil/
  (espanhol: `.../busca-facil/es.html` · minimalista: `.../busca-facil/minimalista.html`)
- **Repositório:** https://github.com/lucasvalladares/busca-facil (público; contém só a pasta `site/`)
- **Atualização automática:** a coleta das 19h gera as páginas e envia a pasta `site/` para o GitHub.
  O site novo aparece 1–2 minutos depois.
- **Publicar na mão** (por exemplo, depois de mudar o visual):
  ```
  cd ~/monitor-precos && python3 pagina.py && python3 publicar.py
  ```
- **Ferramenta do GitHub:** instalada em `~/.local/bin/gh` (login feito com `gh auth login`).
- **Parar de publicar automaticamente:** apague a pasta `site/.git` (o site no ar fica congelado na última versão).

## Dados de teste (simulados)

Para ver gráficos e etiquetas com histórico, crie uma **cópia de teste** com 6 meses inventados.
Os dados inventados **nunca** entram no banco real (`precos.db`) nem no site publicado: ficam só na pasta `teste/`.

```
cd ~/monitor-precos && python3 simular.py && open teste/relatorio-vibrante.html
```

Para apagar a cópia de teste: `python3 simular.py --apagar`

## Ver os dados "crus"

```
sqlite3 -header -column ~/monitor-precos/precos.db "SELECT data, loja, modelo, preco_gs, em_estoque FROM ofertas ORDER BY data DESC LIMIT 30;"
```

## Produtos e categorias

- **Celulares:** iPhone (todos os modelos) e Xiaomi (Redmi Note 15 Pro 5G, Redmi Note 15 4G e 5G, Redmi 15 5G).
- **Notebooks:** MacBook (Air 13" M5, Air 15" M4, Air 13" M4, Pro 14" M5, Pro 16" M5) e notebooks gamer
  (Lenovo LOQ, ASUS TUF Gaming F16, Acer Nitro V 15, Dell G15, Lenovo Legion Pro 5i).
- O que entra em cada um é decidido pelo nome do anúncio, em `normalizar.py` (listas `MACBOOKS` e `GAMERS`).
  As buscas feitas em cada loja ficam em `coletor.py` (lista `TERMOS`).
- Variação comparada entre lojas: armazenamento (celulares), chip + SSD (MacBook) e placa de vídeo (gamer).
- A versão minimalista continua mostrando só iPhones.

## Limitações conhecidas

- **Lojas monitoradas (9):** Nissei, Mega Eletrônicos, Shopping China, Alemania Cell, Tecnostore, Visuar,
  Tienda Yankee (tiendayankee.com), Bristol e Tienda Móvil.
- **Não monitoradas:** Cellshop e Compulandia (bloqueiam acesso automático); Gonzalez Gimenez e Compumarket
  (os produtos vêm de um serviço de busca separado, que exige uma chave de acesso do site); Tupi (a busca só
  mostra produtos quando o navegador monta a página; exigiria navegador automatizado).
- **Tienda Yankee:** anúncios sem o armazenamento no nome (a capacidade fica numa opção dentro da página do
  produto) ficam de fora, para não abrir produto por produto.
- **Como os preços são guardados e mostrados:** tudo em guaranis (tabela `ofertas`, coluna `preco_gs`).
  O site mostra em Gs. por padrão; o botão **US$** converte no navegador, usando uma única cotação:
  a do momento da coleta (tabela `cambio`, publicada pela Nissei).
  - Nissei: preço **exclusivo para estrangeiros** (o preço do site sem o IVA de 10%).
  - Mega e Shopping China: anunciam em US$ ("tax free"); convertido pela cotação da coleta.
  - Alemania Cell, Tecnostore e Visuar: valor original em guaranis (com IVA).
- **Condição:** "seminuevo" (Tecnostore) e "SWAP" (Visuar) entram como Recondicionado (CPO).
- Se uma loja mudar o site, a coleta dela falha (as outras continuam) e a página mostra "erro" no rodapé.
- Itens fora de estoque são ignorados; a Mega lista alguns por "US$ 1" (sem preço) — também ignorados.
