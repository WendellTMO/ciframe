# Plano — Sequências de Acordes Customizadas

## Passos

1. [x] Colocar `data/db/` no `.gitignore` e no `.dockerignore`. Isso vem primeiro porque, a partir do passo 4, todo import do `main.py` cria o arquivo do banco.

2. [x] Criar o `sequencias_db.py`. Cada função dele abre e fecha a própria conexão. O módulo tem:
   - A lista `SEQUENCIAS_INICIAIS`, com as 6 sequências atuais já normalizadas (`Bm G D A`, `C G Am F`, `Em G`, `C A7 Dm G7`, `Gm F` e `C C7 F Fm`), na ordem de `scripts/generate_data_set.py:8`. Lá elas estão em minúsculo. A posição de cada uma na lista (de 0 a 5) é o número que a coluna `SEQ_FAMOSA` usa para ela. O `id` do banco começa em 1 e não entra nessa comparação.
   - A função `normaliza_acorde`, que deixa a primeira letra maiúscula e mantém o resto.
   - A função `init_db`, que cria a pasta e a tabela `sequencias`, com `id` e `acordes`, se ainda não existirem. A coluna `acordes` guarda os acordes já normalizados e separados por `;` (como `C;G;Am;F`) e não pode se repetir. A função insere as 6 sequências com `ON CONFLICT DO NOTHING`, para não duplicar a cada reinício.
   - A função `listar`, que devolve as sequências ordenadas por `id`, cada uma com `id` e a lista de acordes.
   - As funções `buscar` e `criar`. As duas recebem uma lista de acordes e passam cada um por `normaliza_acorde` antes de procurar ou gravar. O `buscar` devolve `id` e acordes da sequência, ou nada se ela não existir. O `criar` recusa lista vazia.

3. [x] Escrever a `casa_com_sequencia(cifra, acordes)` no `main.py`. Ela recebe os acordes da sequência já normalizados, passa cada acorde da cifra por `normaliza_acorde` e compara acorde por acorde:
   - Primeiro confere se todos os acordes da música pertencem à sequência e para no primeiro que não pertence. Quase toda música tem algum acorde de fora, então a maioria sai logo no começo. Essa parada é o que deixa a busca rápida: cerca de 55 ms nos testes locais. Normalizando a cifra inteira antes de conferir, a busca leva cerca de 290 ms.
   - Depois procura a sequência inteira na cifra, como lista, em ordem e com os acordes seguidos.

   O `get_famosas` procurava o texto da sequência dentro do texto da cifra. Nas 6 sequências isso dá o mesmo resultado. Em sequências novas dá falso positivo sempre que o texto da sequência começa ou termina no meio de um acorde: `Am;A` casaria com `oasis_the-swamp-song`, que só tem Am, porque o texto `Am;A` aparece dentro de `Am;Am`.

   No mesmo passo, reescrever o `research/seq_famosa_rule.py` como `scripts/regressao_sequencias.py`, para o teste entrar no git. O script roda a função nova nas 6 sequências de `SEQUENCIAS_INICIAIS` e compara com a coluna `SEQ_FAMOSA` pela posição na lista. Ele precisa dar 199, 296, 4, 5, 7 e 3 músicas, com 0 diferenças, antes de seguir. Esses números saem iguais com as duas normalizações testadas (tudo em minúsculo e só a primeira letra maiúscula) e com as duas formas de comparar (texto e lista). Por isso o script também confere que `bm` vira `Bm`, que `C7M` e `C7m` continuam diferentes (o mesmo para `Gm` e `GM`) e que `Am;A` não casa com a música do Oasis. O teste roda dentro do Docker, onde o Flask está instalado:

   ```
   docker build -t ciframe . && docker run --rm ciframe python scripts/regressao_sequencias.py
   ```

4. [x] Ligar o `/similares` ao banco. O dicionário de `main.py:40-45` sai e o `init_db` passa a rodar no import, depois da carga do CSV. O parâmetro `sequencia` é separado por vírgula, cada acorde perde os espaços e os vazios saem. O handler procura a sequência com `buscar`. Se ela não existir, a resposta continua sendo `[]`. Se existir, o `get_similares_por_sequencia` recebe a lista de acordes no lugar do `id_seq` e usa a `casa_com_sequencia` no lugar da coluna `seqs_famosas`. Rodar o teste de regressão de novo. A partir daqui, o script também chama o `/similares` das 6 sequências pelo `test_client` do Flask, junta todas as páginas e compara as músicas com a coluna `SEQ_FAMOSA`. Assim o teste cobre o caminho inteiro da busca, incluindo o banco. O script também roda o `init_db` uma segunda vez e confere que o `listar` continua com 6 sequências, o que simula um reinício com o banco já criado.

5. [x] Criar `GET /sequencias` e `POST /sequencias` no `main.py`, sempre respondendo com `json.dumps`, inclusive nos erros. Regras do `POST`:
   - O corpo é lido com `request.get_json(silent=True)` e precisa ser um objeto JSON. Corpo inválido ou uma lista no lugar do objeto responde 400.
   - O campo `acordes` precisa ser uma lista de textos.
   - Cada acorde perde os espaços das pontas e os vazios saem.
   - Acorde com `;` ou `,` é recusado, porque quebraria a separação dos acordes no banco e na URL.
   - Se não sobrar nenhum acorde, a resposta é 400.
   - Sequência nova responde 201, com o `id` e os acordes normalizados.
   - Sequência repetida faz a restrição de unicidade do banco falhar. O handler então procura a existente com `buscar` e responde 409 com o `id` dela.

6. [x] Mudar a página `#/porsequencia`:
   - No `sequencia.js`, as 4 sequências escritas no código saem e a lista passa a vir de `GET /sequencias`.
   - Cada sequência da API é convertida para `{id: 3, acordes: [{acorde: 'C', cor: '#2E1C74'}, ...]}`. É o formato que o template e o `createChordsString` usam, com o `id` preservado. A sequência recém-criada passa pela mesma conversão.
   - O campo de texto e o botão de cadastro saem. No lugar, um botão "Nova sequência" abaixo da lista abre um card no meio da tela (modal) com a sequência em construção no topo e, abaixo, os acordes para escolher.
   - A lista de acordes e a paleta de cores saem do `acordes.js` para a constante `ACORDES` no `app.js`, usada pelos dois controllers. A página `#/poracordes` continua com o mesmo comportamento e o modal não duplica as cores.
   - Cada clique num acorde da lista acrescenta ele no fim da sequência em construção, que aparece no topo do modal com o `df-hex` e a cor da paleta.
   - Ao passar o mouse em qualquer acorde do topo, ele fica vermelho e mostra o ícone de lixeira no centro do hexágono. Clicar na lixeira remove aquele acorde.
   - "Salvar" faz o `POST /sequencias`. O 201 acrescenta a sequência nova à lista e fecha o modal. O 409 usa o `id` da resposta para selecionar a existente, avisa e fecha o modal. O 400 mostra a mensagem de erro dentro do modal, que continua aberto para o usuário corrigir.
   - O modal tem um botão de fechar que descarta a sequência em construção.
   - A paleta só tem acorde maior, menor e com sétima (sem `+`, `7M`, `sus` e afins), então pelo modal só dá para montar sequências com esses acordes.
   - A busca passa a montar a URL com `params` do `$http`, que codifica os acordes. Hoje a URL é montada juntando texto (`sequencia.js:73-77`). Com isso o `#` de `F#m` corta a URL e o navegador manda só `sequencia=F`. O `+` de `A7+` chega no servidor como espaço. As 6 sequências atuais não têm esses símbolos, por isso o problema nunca apareceu. Nos dados, 31.701 músicas têm acorde com `#` e 6.142 têm acorde com `+`.
   - A exibição dos resultados continua igual.

7. [x] Trocar o comando de execução no `AGENTS.md` por `docker run -p 8080:8080 -v ciframe-seq:/app/data/db ciframe`.

8. [x] Testar tudo no Docker: montar pela página a sequência `A E F#m D` (que tem sustenido), buscar por ela, reiniciar e recriar o container com o volume e conferir se ela continua lá. Conferir também por `curl` que o `POST` de `D7+,G7+` é aceito e sobrevive ao restart, já que o modal só oferece os acordes da paleta.

## Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `main.py` | Sai o dicionário das 6 sequências. Entram a `casa_com_sequencia`, o `GET /sequencias` e o `POST /sequencias`. O `/similares` passa a buscar no banco e o `get_similares_por_sequencia` passa a receber a lista de acordes |
| `musica.py` | Sem mudança. O `seqs_famosas` continua sendo lido do CSV, mas deixa de ser usado |
| `static/assets/js/controllers/sequencia.js` | A lista vem da API e é convertida para o formato do template, com o `id` preservado. Entra o modal que monta a sequência clicando nos acordes. A busca passa a codificar a URL |
| `static/templates/sequencia.html` | Botão "Nova sequência", modal com a sequência em construção e os acordes para escolher. Mensagens de erro e aviso |
| `static/assets/js/app.js` | Constante `ACORDES` com a lista e a paleta, tiradas do `acordes.js` |
| `static/assets/js/controllers/acordes.js` | Passa a usar a constante `ACORDES`, sem mudança de comportamento |
| `static/assets/css/app.css` | Estilos do modal e do acorde vermelho com a lixeira |
| (novo) `sequencias_db.py` | Tabela, 6 sequências iniciais, normalização, funções de acesso ao banco |
| (novo) `scripts/regressao_sequencias.py` | Teste de regressão das 6 sequências, reescrito a partir do `research/seq_famosa_rule.py` |
| `.gitignore`, `.dockerignore` | Passam a ignorar `data/db/` |
| `AGENTS.md` | Comando com volume |
| `Dockerfile`, `requirements.txt` | Sem mudança, porque o `sqlite3` já vem com o Python |

## Riscos e mitigação

| Risco | Como perceber | O que fazer |
|---|---|---|
| A regra nova muda os resultados das 6 sequências | O teste de regressão mostra diferença | Parar e corrigir a função antes de ligar no `/similares` |
| O teste de regressão compara a sequência errada | As contagens saem trocadas entre as 6 | Comparar pela posição na lista (0 a 5), nunca pelo `id` do banco |
| O teste de regressão passa com as duas normalizações | O script não acusa nada mesmo com a normalização errada | O script também confere os pares `bm`/`Bm`, `C7M`/`C7m` e `Gm`/`GM` |
| Comparar a sequência como texto gera falso positivo | `Am;A` casa com uma música que só tem Am | Comparar acorde por acorde e conferir esse caso no teste |
| A busca fica lenta | O `/similares?sequencia=` passa de 100 ms | Conferir primeiro se os acordes da música estão na sequência, parando no primeiro de fora |
| O `#` e o `+` dos acordes quebram a URL da busca | Uma sequência com `F#m` volta vazia pela página e funciona no `curl` com `%23` | Montar a URL com `params` do `$http` |
| A página recebe a lista da API num formato que o template não entende | Os hexágonos aparecem vazios ou o 409 não acha a sequência existente | Converter cada sequência para `{id, acordes: [{acorde, cor}]}` no controller |
| A extração da paleta quebra a página `#/poracordes` | Faltam acordes ou as cores saem trocadas | Mover a lista inteira sem alterar os valores e conferir a página depois |
| O vermelho e a lixeira do hover não aparecem em qualquer acorde | O hexágono continua com a cor da paleta ou a lixeira só aparece no último | O `df-hex` pinta o hexágono com `ng-style`, então aplicar a cor vermelha no wrapper de cada acorde com `!important` |
| O modal só oferece os acordes da paleta | Não dá para montar `D7+` nem `G7+` clicando | Limitação aceita nesta entrega. A paleta atual só tem maior, menor e sétima |
| Um acorde com `;` ou `,` quebra a separação dos acordes | O `GET /sequencias` mostra um acorde que não existe | Recusar esses acordes no `POST` |
| Alguém grava HTML como acorde direto pela API e o `/sequencias`, que responde como `text/html`, executa esse HTML se for aberto no navegador | Um `POST` com `<img src=x onerror=alert(1)>` responde 201 | Aceito nesta entrega. A página só envia acordes escolhidos numa lista e mostra o texto escapado pelo Angular |
| Quem digita `c7m` querendo dó com sétima maior recebe `C7m`, que é dó menor com sétima | A sequência não acha as músicas esperadas | Aceito. Só a primeira letra é normalizada e o resto vale como foi digitado |
| Quem digita `d/f#` recebe `D/f#`, que não casa com `D/F#` | A sequência não acha as músicas esperadas | Aceito. Nos dados, a letra minúscula depois da barra é extensão em 817 casos (`b5`, `b9`, `b13`, `sus4`) e baixo em só 35. Deixar essa letra maiúscula estragaria as extensões |
| O segundo start falha ou duplica as 6 sequências | O teste roda o `init_db` duas vezes e dá erro ou o `listar` passa de 6 | Criar a tabela só se ela não existir e inserir com `ON CONFLICT DO NOTHING` |
| O volume montado no lugar errado esconde o CSV | O `/generos` não responde | Montar só em `/app/data/db` |

## Definição de pronto

- [x] As 6 sequências originais dão 199, 296, 4, 5, 7 e 3 músicas, com 0 diferenças em relação à coluna `SEQ_FAMOSA`, tanto na função quanto no `/similares`.
- [x] O `GET /sequencias` devolve as 6 sequências no primeiro uso, ordenadas por `id`.
- [x] O `POST /sequencias` com uma sequência nova responde 201 e ela aparece no `GET /sequencias`.
- [x] O `POST /sequencias` responde 400 para lista vazia, corpo inválido ou corpo que é uma lista. Para sequência repetida, inclusive `c,g,am,f`, responde 409 com o `id` da existente.
- [x] As sequências `GM;F` e `Gm;F` são aceitas como diferentes. O mesmo vale para `C7M` e `C7m`.
- [x] A sequência `Am;A` não casa com música que só tem Am.
- [x] A busca por `bm,g,d,a` encontra as mesmas músicas que `Bm,G,D,A`. Antes ela retornava `[]`. Essa mudança é esperada.
- [x] Montar `A E F#m D` pelo modal cria a sequência `A E F#m D`, que encontra 159 músicas. A página mostra as 100 primeiras, como hoje.
- [x] O `POST /sequencias` de `D7+,G7+`, fora do modal, cria uma sequência que encontra 3 músicas.
- [x] A página `#/porsequencia` mostra as 6 sequências, monta uma nova clicando nos acordes, mostra os erros e busca pela nova.
- [x] Uma sequência cadastrada continua lá depois de recriar o container com o volume.
- [x] Todos os endpoints continuam respondendo com `json.dumps`.
