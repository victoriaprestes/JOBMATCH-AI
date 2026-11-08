# JobMatch AI

Aplicação web para identificar oportunidades de nível inicial no Brasil, organizar a busca por trilhas profissionais e acompanhar candidaturas. O projeto nasceu de um problema prático: encontrar vagas compatíveis com a experiência atual e, ao mesmo tempo, mapear posições de transição para áreas de governança, operações de TI e gestão de serviços.

**Aplicação:** https://jobmatch-victoria.streamlit.app/  
**Tecnologias:** Python · Streamlit · pandas · Requests · SQLite · GitHub Actions · Git/GitHub

## O que a aplicação faz

- Coleta vagas de fontes públicas e consolida os resultados em um feed JSON.
- Filtra oportunidades por localização, modalidade, senioridade e família de cargos.
- Organiza os resultados em duas trilhas:
  - **Perfil atual:** administrativo, suporte executivo, operações, processos, projetos/PMO, compras, facilities, back office e financeiro corporativo.
  - **Trilha de transição:** governança, governança de TI, IT Operations, IT Service Management, controles internos, riscos, compliance, auditoria e gestão de projetos.
- Permite pesquisar por cargo, empresa e competências.
- Apresenta informações de remuneração e benefícios quando identificadas na fonte, sem presumir dados ausentes.
- Calcula uma pontuação heurística de compatibilidade com base em palavras-chave e competências do perfil. Essa pontuação é indicativa, não uma previsão de contratação.
- Permite salvar vagas e acompanhar etapas de candidatura.

## Uso de IA no desenvolvimento

O projeto foi desenvolvido com **apoio de IA generativa como ferramenta de programação e resolução de problemas**, em um fluxo iterativo. A IA foi utilizada como copiloto para transformar requisitos escritos em linguagem natural em tarefas técnicas, propor e revisar trechos de código, investigar erros e estruturar testes.

O trabalho foi conduzido por etapas:

1. **Definição do problema e dos requisitos:** descrevi o objetivo da ferramenta, o perfil profissional considerado, as regiões de interesse, o piso salarial desejado e os tipos de vaga que deveriam entrar ou ser excluídos.
2. **Tradução de requisitos em lógica:** usei prompts para solicitar regras de classificação de cargos, senioridade, localização, modalidade de trabalho e elegibilidade das oportunidades.
3. **Construção e integração:** solicitei apoio para implementar o coletor em Python, a interface em Streamlit, a persistência local de vagas salvas e a automação de atualização com GitHub Actions.
4. **Refinamento orientado a exemplos:** apresentei casos reais em que o resultado não correspondia ao esperado — por exemplo, vagas afirmativas exclusivas para determinados públicos e benefícios descritos em formatos diferentes — e pedi análise da causa e ajustes específicos.
5. **Depuração e validação:** compartilhei mensagens de erro, trechos de código e resultados do workflow para investigar falhas. Também solicitei testes automatizados para verificar os comportamentos esperados antes de considerar uma alteração concluída.

### Exemplo de prompt utilizado

> Estou desenvolvendo uma aplicação em Python e Streamlit para coletar vagas de nível inicial no Brasil. Quero separar oportunidades compatíveis com minha experiência atual de vagas que representam uma possível transição para governança e operações de TI. Implemente filtros explícitos para localização, senioridade e tipo de cargo. Não inclua vagas sêniores, oportunidades sem confirmação de contratação no Brasil ou posições fora dos grupos definidos. Preserve as informações da fonte, não invente salário ou benefícios e escreva testes para os critérios de inclusão e exclusão. Explique as alterações e indique como validar o resultado.

Os prompts foram refinados conforme os testes e os casos encontrados. O uso de IA não substituiu a validação: requisitos, critérios de negócio, exemplos de erro e resultados esperados foram definidos e revisados durante o desenvolvimento.

**Importante:** a IA foi utilizada no processo de desenvolvimento; o produto não depende de um modelo de linguagem para classificar ou recomendar vagas em tempo de execução. A pontuação de compatibilidade atual é baseada em regras e palavras-chave, não em inferência por LLM.

## Arquitetura e automação

```text
Fontes públicas de vagas
        |
        v
collect_jobs.py
(coleta, normalização, filtros e deduplicação)
        |
        v
data/jobs_feed.json
        |
        v
app.py (Streamlit)
(interface, filtros e compatibilidade)
        |
        v
src/database.py
(vagas salvas e etapas de candidatura)
```

O workflow `.github/workflows/collect-jobs.yml` executa a coleta diariamente às 08:00 no horário de Curitiba (11:00 UTC), além de poder ser iniciado manualmente pelo GitHub Actions. Antes da coleta, o workflow instala as dependências, executa os testes com pytest e verifica a sintaxe dos módulos Python. Ao final, atualiza o feed no repositório.

## Critérios de coleta

- **Localização:** Brasil explicitamente indicado no anúncio. Para vagas presenciais/híbridas, foco em Curitiba e região metropolitana; para remotas, contratação explicitamente permitida no Brasil.
- **Localizações excluídas:** Worldwide, Global, Americas, LATAM e anúncios sem país elegível confirmado.
- **Senioridade:** assistente, auxiliar, trainee e vagas júnior/analista I com evidência de nível inicial. Anúncios sem data ou com mais de 45 dias são descartados; títulos e requisitos sêniores são excluídos.
- **Tipos de vaga excluídos:** posições predominantemente operacionais fora do escopo, como caixa, loja, estoque e atendimento ao cliente, além de contratos temporários identificados no título.
- **Ações afirmativas exclusivas:** vagas exclusivas ou reservadas a grupos específicos são filtradas; anúncios gerais que apenas informam aceitar pessoas com deficiência são mantidos.
- **Remuneração:** o piso desejado é R$ 3.000 brutos mensais. Vagas com remuneração em reais abaixo do piso podem ser ocultadas na interface. Vagas sem salário divulgado permanecem identificadas como não confirmadas.
- **Benefícios:** são exibidos quando encontrados em campos estruturados ou em seções identificáveis da descrição. A ausência de informação não é interpretada como ausência do benefício.

## Fontes e limitações

A coleta utiliza a busca pública do portal Gupy (endpoint não documentado, usado pela busca do próprio portal) e feeds públicos de Remotive, RemoteOK e Arbeitnow. A cobertura é parcial: esta versão não integra LinkedIn, Indeed nem todas as páginas de carreira das empresas. O endpoint da Gupy pode mudar, e a quantidade de resultados depende da cobertura de cada fonte. A ausência de resultados não significa ausência de vagas no mercado.

O sistema não confirma por conta própria se a contratação é CLT ou se todos os benefícios estão disponíveis. Na Gupy, o tipo “Efetivo” é exibido como regime CLT a confirmar; nas demais fontes, o vínculo pode não estar informado. Esses itens devem ser conferidos no anúncio original. Salários em moeda estrangeira não são convertidos para simular remuneração brasileira.

## Executar localmente

```bash
python -m venv .venv

# Windows PowerShell
.venv\\Scripts\\Activate.ps1

# macOS/Linux
source .venv/bin/activate

python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Para executar os testes:

```bash
python -m pip install pytest
python -m pytest -q
```

## Privacidade

O repositório público não deve conter currículo, telefone, endereço ou outros dados pessoais. O feed reúne dados públicos dos anúncios. A base de vagas salvas e candidaturas é local ao ambiente da aplicação e não deve ser considerada armazenamento permanente.
