# Monitor de preços de iPhones no Paraguai

## O que tem nesta pasta

| Arquivo | Para que serve |
|---|---|
| `coletor.py` | Visita as lojas, salva os preços no banco e atualiza a página. **É o único que você precisa rodar.** |
| `normalizar.py` | Transforma nomes como `CEL IPHONE 16 6.1" 8GB+128GB` em `iPhone 16 128GB` e identifica a condição (Novo / Recondicionado / Sem lacre). |
| `pagina.py` | Prepara os dados, baixa as fotos e monta as páginas `relatorio-minimalista.html` e `relatorio-vibrante.html`. |
| `template-vibrante.html` | As telas do site (categorias, filtros, detalhe, gráfico). Vale para todas as versões. |
| `estilo-minimalista.css` | O visual da versão minimalista (clean): mesma página, só outro estilo. Mudanças nas telas valem para as duas. |
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

## Coleta automática: roda no GitHub (o Mac pode ficar desligado)

Desde 12/11/2026 a coleta **não roda mais no Mac**. Quem roda é o **GitHub Actions**, de graça
(o repositório é público), todo dia às **19h do Paraguai** (o GitHub às vezes atrasa alguns minutos).

A cada execução o GitHub: roda os testes → faz a coleta real (mesmas regras de educação) →
guarda o `precos.db` atualizado no repositório → monta e publica o site.

- **Ver as execuções e o resumo de cada coleta:** https://github.com/lucasvalladares/busca-facil/actions
  (clique numa execução: o "Resumo da coleta" mostra a tabela por loja e avisos de problema)
- **Rodar agora, na mão:** na página acima → "Coleta diária" → **Run workflow** → escolha:
  - `coleta` — coleta real + publica;
  - `so-publicar` — só gera e publica o site com os dados que já existem (ex.: depois de mudar o visual);
  - `checar-conexao` — 1–2 pedidos por loja, para ver se alguma está bloqueando o GitHub.
- **Aviso por e-mail:** o GitHub manda e-mail se uma execução falhar por completo.
- **Mudar o horário:** linha `cron` em `.github/workflows/coleta.yml` (está em UTC: 22h UTC = 19h PY).
- **Desligar:** Actions → "Coleta diária" → botão "…" → Disable workflow.
- **Atenção:** o GitHub desliga agendamentos de repositórios sem atividade por 60 dias; como a
  coleta grava um commit por dia, isso não deve acontecer.

**Antes de mexer no código neste Mac:** rode `git pull` (o GitHub grava o banco novo todo dia).
Depois de mudar, `git add -A && git commit -m "..." && git push`.

**Rodar no Mac (só se precisar):** `python3 coletor.py --real --sem-publicar`. Não publica nada e
deixa o banco local diferente do GitHub — evite. O agendamento antigo do Mac (launchd) foi desligado;
o arquivo `com.monitorprecos.coleta.plist` ficou só como referência.

## Painel interno e avisos no celular

- **Painel interno:** https://lucasvalladares.github.io/busca-facil/painel.html — pede senha.
  Mostra quantos produtos subiram/baixaram de preço em relação à coleta anterior (com loja e %),
  e quanto tempo levou cada coleta. Os dados vão **criptografados** (AES-256); sem a senha não dá para ler.
  A senha fica no segredo `PAINEL_SENHA` do GitHub (Settings → Secrets and variables → Actions).
  Sem esse segredo, o painel simplesmente não é publicado. Para ver localmente sem senha: `python3 painel.py`.
- **Avisos no celular:** ao fim de cada coleta (✅ ok, ⚠️ problema em alguma loja, ❌ falhou), pelo app gratuito
  **ntfy** (iPhone/Android), assinando o tópico guardado no segredo `NTFY_TOPICO`. Tocar no aviso abre o painel.

## Site público (GitHub Pages)

- **Endereço:** https://lucasvalladares.github.io/busca-facil/
  (espanhol: `.../busca-facil/es.html` · minimalista: `.../busca-facil/minimalista.html` · minimalista em espanhol: `.../busca-facil/minimalista-es.html`)
- **Repositório:** https://github.com/lucasvalladares/busca-facil (público: código + banco de preços).
  O site publicado contém só as páginas, fotos e fontes (o banco não fica acessível pelo site).
- **Publicação:** feita pelo GitHub Actions ao fim de cada coleta (ou com `so-publicar`).

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
- A versão minimalista mostra tudo o que a vibrante mostra (todas as categorias); só o visual muda.

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
