"""
Tradução da versão vibrante para o espanhol.

A página em espanhol (relatorio-vibrante-es.html) é gerada a partir do
template-vibrante.html, trocando os textos pela lista abaixo. Assim, toda
mudança de visual feita na versão vibrante vale também para a espanhola.

Se um texto novo for adicionado à versão vibrante, acrescente o par aqui.
O pagina.py avisa quando um texto da lista não é encontrado no template.
"""

# Textos entre aspas simples no código da página: ('português', 'espanhol')
TEXTOS = [
    ("Atualizado ", "Actualizado "),
    ("iPhone Air e Duo", "iPhone Air y Duo"),
    ("Mais", "Más"),
    ("Preço", "Precio"),
    ("Desconto", "Descuento"),
    ("Busca Fácil · Desconto de verdade ou maquiagem?", "Busca Fácil · ¿Descuento de verdad o maquillaje?"),
    ("Desconto de verdade ou maquiagem?", "¿Descuento de verdad o maquillaje?"),
    ("Todo dia comparamos o preço de celulares, notebooks e TVs em ", "Todos los días comparamos el precio de celulares, notebooks y TVs en "),
    (" lojas do Paraguai e mostramos se a oferta é boa de verdade — ou se o preço subiu antes da promoção.",
     " tiendas de Paraguay y te mostramos si la oferta es buena de verdad — o si el precio subió antes de la promoción."),
    ("Ver categorias", "Ver categorías"),
    ("Escolha uma categoria", "Elige una categoría"),
    (" abaixo do normal hoje", " por debajo de lo normal hoy"),
    ("← Todas as categorias", "← Todas las categorías"),
    ("O menor preço de hoje em cada modelo, entre ", "El precio más bajo de hoy en cada modelo, entre "),
    ("Maior desconto de hoje", "Mayor descuento de hoy"),
    ("Condição", "Condición"),
    ("Série", "Serie"),
    ("Nenhum modelo com esses filtros.", "Ningún modelo con estos filtros."),
    ("A partir de", "Desde"),
    (" · exclusivo para estrangeiros", " · exclusivo para extranjeros"),
    ("Ver histórico ", "Ver historial "),
    ("iPhone novo mais barato hoje", "iPhone nuevo más barato hoy"),
    ("Como funciona", "Cómo funciona"),
    ("1. Coletamos", "1. Recolectamos"),
    ("Uma vez por dia, lemos o preço de cada produto em ", "Una vez por día, leemos el precio de cada producto en "),
    (" lojas do Paraguai.", " tiendas de Paraguay."),
    ("Juntamos o mesmo modelo entre as lojas e guardamos o menor preço de cada dia.",
     "Unimos el mismo modelo entre las tiendas y guardamos el precio más bajo de cada día."),
    ("3. Julgamos", "3. Evaluamos"),
    ("Preço mais de 10% abaixo da média dos últimos 40 dias é desconto real; mais de 10% acima, preço inflado.",
     "Más de 10% por debajo del promedio de los últimos 40 días es descuento real; más de 10% por encima, precio inflado."),
    ("Cotação usada: 1 US$ = ", "Cotización usada: 1 US$ = "),
    (" · coletada em ", " · recolectada el "),
    (" às ", " a las "),
    ("Publicado em US$ ", "Publicado en US$ "),
    ("Publicado em ", "Publicado en "),
    ("Coletando histórico", "Recolectando historial"),
    ("Mais barato hoje", "Más barato hoy"),
    ("Ver lojas ", "Ver tiendas "),
    ("Mais baixo que o normal", "Más bajo que lo normal"),
    ("Mais caro que o normal", "Más caro que lo normal"),
    ("↓ Abaixo do normal", "↓ Por debajo de lo normal"),
    ("↑ Acima do normal", "↑ Por encima de lo normal"),
    ("Todos", "Todos"),
    ("Preço normal", "Precio normal"),
    ("A comparação com o preço normal começa depois de ", "La comparación con el precio normal empieza después de "),
    (" dias de coleta", " días de recolección"),
    (" a ", " al "),
    ("← Todos os modelos", "← Todos los modelos"),
    ("todas as cores", "todos los colores"),
    ("Cor", "Color"),
    ("Todas", "Todos"),
    ("Sem ofertas hoje.", "Sin ofertas hoy."),
    ("Foto em outra cor: ", "Foto en otro color: "),
    (" não está à venda hoje.", " no está a la venta hoy."),
    ("Onde comprar hoje", "Dónde comprar hoy"),
    ("Preço subiu antes da Black Friday", "El precio subió antes del Black Friday"),
    ("Hoje está ", "Hoy está "),
    (" acima da média de ", " por encima del promedio del "),
    ("Ver na loja →", "Ver en la tienda →"),
    ("Preço exclusivo para estrangeiros", "Precio exclusivo para extranjeros"),
    (" · sem IVA (10%). Com IVA: ", " · sin IVA (10%). Con IVA: "),
    ("Sem oferta hoje · último preço em ", "Sin oferta hoy · último precio el "),
    ("O preço está bom?", "¿El precio está bien?"),
    (" em relação à média dos últimos 40 dias", " respecto al promedio de los últimos 40 días"),
    (" acima da média dos últimos 40 dias", " por encima del promedio de los últimos 40 días"),
    ("Variação de ", "Variación de "),
    (" em relação à média", " respecto al promedio"),
    ("hoje", "hoy"),
    ("Menor preço hoje", "Precio más bajo hoy"),
    ("Média dos últimos 40 dias", "Promedio de los últimos 40 días"),
    ("Dias com dados (de 40)", "Días con datos (de 40)"),
    ("Só ", "Solo "),
    (" dia", " día"),
    (" dias", " días"),
    (" de histórico: o indicador fica confiável depois de algumas semanas.",
     " de historial: el indicador será confiable después de algunas semanas."),
    ("Barato: mais de 10% abaixo da média. Normal: até 10% para mais ou para menos. Caro: mais de 10% acima. A média considera o menor preço de cada dia nos últimos 40 dias.",
     "Barato: más de 10% por debajo del promedio. Normal: hasta 10% arriba o abajo. Caro: más de 10% por encima. El promedio considera el precio más bajo de cada día en los últimos 40 días."),
    ("Histórico de preços", "Historial de precios"),
    ("Preço médio", "Precio promedio"),
    ("Maior preço", "Precio más alto"),
    ("30 dias", "30 días"),
    ("Dados de teste: ", "Datos de prueba: del "),
    (" são inventados.", " son inventados."),
    ("A coleta começou em ", "La recolección empezó el "),
    ("Menor preço de cada dia nos últimos 12 meses. Use as setas para percorrer os dias.",
     "Precio más bajo de cada día en los últimos 12 meses. Use las flechas para recorrer los días."),
    ("Média 12 meses ", "Promedio 12 meses "),
    ("Faixa ±10% da média", "Rango ±10% del promedio"),
    ("Ver tabela", "Ver tabla"),
    ("Mês", "Mes"),
    ("Menor preço", "Precio más bajo"),
    ("Dia", "Día"),
    ("Loja", "Tienda"),
    ("pt-BR", "es-PY"),
]

# Trechos fora das aspas (HTML, listas)
TRECHOS = [
    ('<html lang="pt-BR">', '<html lang="es">'),
    ("<title>Busca Fácil · Desconto de verdade ou maquiagem?</title>",
     "<title>Busca Fácil · ¿Descuento de verdad o maquillaje?</title>"),
    (">Como funciona<", ">Cómo funciona<"),
    ('aria-label="Moeda"', 'aria-label="Moneda"'),
    ("const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];",
     "const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];"),
    ("const ROTULO = {};",
     "const ROTULO = {'Novo': 'Nuevo', 'Recondicionado (CPO)': 'Reacondicionado (CPO)', 'Sem lacre': 'Sin lacre', "
     "'Cor não informada': 'Color no informado', 'Armazenamento': 'Almacenamiento', 'Configuração': 'Configuración', "
     "'Placa de vídeo': 'Tarjeta de video', 'Tamanho': 'Tamaño', 'Placa não informada': 'Tarjeta no informada'};"),
]

def traduzir(html):
    """Aplica a tradução e devolve (html_traduzido, avisos)."""
    avisos = []
    for pt, es in TRECHOS:
        if pt not in html:
            avisos.append("trecho não encontrado: %r" % pt[:60])
        html = html.replace(pt, es)
    for pt, es in TEXTOS:
        alvo = "'%s'" % pt
        if alvo not in html:
            avisos.append("texto não encontrado: %r" % pt[:60])
        html = html.replace(alvo, "'%s'" % es)
    return html, avisos

