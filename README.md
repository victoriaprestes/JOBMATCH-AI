# JobMatch AI

Aplicação pessoal para encontrar vagas de entrada no Brasil, avaliar aderência ao perfil profissional e acompanhar candidaturas.

## Critérios do coletor

- **Localização obrigatória:** Brasil explicitamente indicado no anúncio. Para vagas presenciais/híbridas, foco em Curitiba e região metropolitana; para remotas, contratação explicitamente permitida no Brasil.
- **Localizações excluídas:** Worldwide, Global, Americas, LATAM e anúncios sem país elegível confirmado.
- **Senioridade:** assistente/auxiliar/trainee ou vagas júnior/analista I com evidência de nível inicial. Títulos e requisitos sêniores são excluídos.
- **Trilha de perfil atual:** administrativo, suporte executivo, operações, processos, projetos/PMO, compras, facilities, back office e financeiro corporativo.
- **Trilha de transição:** governança, governança de TI, IT Operations, IT Service Management, gestão de serviços, controles internos, riscos, compliance, auditoria e PMO/gestão de projetos em nível inicial.
- **Vínculo e salário:** a busca da Empregare solicita regime CLT; nas demais fontes, o vínculo pode não estar informado e é exibido como não confirmado. O piso desejado é R$ 3.000 brutos mensais. Vagas com remuneração em reais abaixo do piso podem ser ocultadas na interface. Vagas sem salário divulgado são identificadas como não confirmadas, nunca tratadas como se atendessem ao piso.
- **Compatibilidade:** pontuação heurística baseada em competências conhecidas. A trilha de transição tem indicador de aderência transferível, sem presumir domínio de ITIL, COBIT, governança ou ferramentas ainda não estudadas.

## Fontes e limitações

A coleta usa a API pública de vagas da Empregare (com busca por cidades, modalidade e país) e os feeds públicos de Remotive, RemoteOK e Arbeitnow. O filtro geográfico é deliberadamente conservador: anúncios sem confirmação explícita de Brasil não entram no feed.

A cobertura é parcial. Esta versão **não** integra LinkedIn, Gupy, Indeed nem todas as páginas de carreira das empresas. A API da Empregare permite buscar oportunidades presenciais/híbridas na região metropolitana de Curitiba e remotas no Brasil; as outras fontes conectadas têm predominância de vagas remotas. A quantidade de resultados depende da cobertura de cada fonte. Não se deve interpretar ausência de resultados como ausência de vagas no mercado.

O sistema não confirma por conta própria se a contratação é CLT, se benefícios estão disponíveis ou se a empresa aceita todos os estados brasileiros. Esses itens devem ser conferidos no anúncio original. Salário em moeda estrangeira não é convertido para simular remuneração brasileira.

## Automação

O workflow .github/workflows/collect-jobs.yml executa diariamente às 08:00 no horário de Curitiba (11:00 UTC) e pode ser acionado manualmente em Actions → Atualizar vagas automaticamente → Run workflow.

O GitHub Actions baixa o repositório, instala dependências, consulta os feeds, aplica filtros de país/cargo/senioridade, remove duplicatas e atualiza data/jobs_feed.json. O Streamlit lê o feed atualizado. O banco de candidaturas pessoais permanece local e não é publicado.

## Executar localmente

~~~bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
~~~

## Privacidade

Não adicione currículo, telefone, endereço ou dados pessoais ao repositório público. O feed contém apenas dados públicos dos anúncios.
