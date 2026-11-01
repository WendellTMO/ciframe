# Pesquisa — Sequências de Acordes Customizadas

## Perguntas que você precisa responder

1. **Algoritmo de matching**: hoje, as 6 sequências hardcoded em `main.py` (linhas
   40-45) são comparadas contra músicas via uma tag pré-computada
   (`SEQ_FAMOSA`/`seqs_famosas`, vinda do CSV). Sequências cadastradas pelo usuário
   não têm essa tag — o matching precisa ser calculado em tempo real a partir da
   lista de acordes de cada música (`musica.acordes`/`musica.cifra`). O que vai
   definir "a sequência X aparece na música Y"? A ordem dos acordes importa?
   Repetições de acorde dentro da música importam? É preciso normalizar (ex.:
   maiúsculas/minúsculas, variações de escrita do mesmo acorde)?
2. **Validação da hipótese**: rode o algoritmo que você está considerando contra os
   dados reais em `data/top/dataset_final.csv`, para as 6 sequências hoje
   hardcoded, e confirme (ou refute) que ele reproduz os mesmos matches que o
   código atual produz via `seqs_famosas`. Esse é o bar mínimo de correção que
   você vai usar na fase de testes.
3. **Banco de dados**: quais bancos embarcados (sem serviço externo adicional) são
   viáveis dentro do container Docker único e local-only já documentado em
   `docs/adr/0001-local-only-docker-deploy.md`? O que cada opção implica para o
   `Dockerfile` atual e para a persistência dos dados entre reinícios do
   container?
4. **Frontend existente**: o que a página `#/porsequencia`
   (`static/templates/sequencia.html` +
   `static/assets/js/controllers/sequencia.js`) já faz? Repare que ela tem hoje uma
   lista *hardcoded no JavaScript* de 4 sequências (`sequencia1`..`sequencia4`),
   diferente das 6 que existem no backend — um detalhe real e pré-existente do
   código, não um erro seu, que vale entender antes de decidir o que precisa
   mudar.

## Registro das descobertas

1. Da maneira que está o backend não olha os acordes para buscar por sequência. Em `main.py:209` ele só confere se o id da sequência está na coluna 7 do CSV (`seqs_famosas`). Essa coluna foi gerada pela função `get_famosas` em `generate_data_set.py`.

A coluna 7 guarda um número de 0 a 5 que diz qual das 6 sequências a música tem: 0 = Bm G D A, 1 = C G Am F, 2 = Em G, 3 = C A7 Dm G7, 4 = Gm F, 5 = C C7 F Fm. Quando o usuário busca por C G Am F, o backend junta os acordes em `CGAmF` e acha no dicionário de `main.py` que isso corresponde ao número 1. Depois devolve as músicas que têm 1 na coluna 7.

A ordem importa, já que C G Am F e F Am G C são progressões diferentes.

Além disso, todos os acordes da música precisam pertencer à sequência. Uma música com C, G, Am, F e Dm não entra em C G Am F.

Repetição de acorde não atrapalha, desde que a sequência apareça seguida pelo menos uma vez. Em C C G Am F, a sequência C G Am F aparece a partir do segundo acorde.

A única normalização que o script faz é passar tudo para minúsculo.

2. A regra da resposta 1 foi implementada em `research/seq_famosa_rule.py`. O script carrega as músicas pelo próprio `main.py` (67.585 músicas, cifra já limpa por `limpa_cifra`), aplica a regra nas 6 sequências que estão em um dicionário no `main.py:` e compara com `seqs_famosas`.

A hipótese está confirmada, tivemos 0 diferenças nas 67.585 músicas. Nenhuma música tem mais de uma sequência.

3. O SQLite já vem com o Python, então não precisa mudar nada no Dockerfile. Outros bancos embarcados, como TinyDB e LMDB, precisam de uma linha no `requirements.txt`. PostgreSQL e MySQL ficam de fora porque rodam como um serviço separado.

O Dockerfile atual não usa volume, então o banco fica salvo dentro do container. Os dados continuam lá depois de um `docker restart`, mas se perdem quando o container é recriado. Para não perder, é preciso rodar com um volume.

4. Da maneira que está a página `#/porsequencia` não busca as sequências no backend. Ela mostra 4 sequências escritas direto no `sequencia.js`: Bm G D A, C G Am F, Gm F e C C7 F Fm. Faltam Em G e C A7 Dm G7.

Quando o usuário clica numa sequência, a página chama `/similares?sequencia=Bm,G,D,A` e lista as músicas por popularidade. Só aparecem as 100 primeiras, porque a página não tem paginação. Também não existe campo para cadastrar uma sequência nova.

Pelo histórico do git, o frontend foi criado com essas 4 sequências antes de o backend ter as 6 e nunca foi atualizado.

## Trade-offs identificados

Algoritmo de matching: usar a mesma regra do `get_famosas` garante que as 6 sequências continuam com os mesmos resultados, já que deu 0 diferenças. O lado ruim é que ela é bem restrita, porque a música precisa usar só os acordes da sequência. Uma regra mais solta acharia mais músicas, mas mudaria os resultados das 6 sequências.

Banco de dados: o SQLite já vem com o Python e não muda nada no Dockerfile. TinyDB e LMDB também funcionam, mas adicionam uma dependência. Qualquer opção perde os dados quando o container é recriado, a menos que o `docker run` use um volume.

Frontend: dá para alterar a página `#/porsequencia` atual, trocando a lista do JS por uma lista vinda do backend e adicionando um formulário de cadastro. A outra opção é criar uma página nova só para cadastro, o que mexe menos no código antigo, mas separa o cadastro da busca.

