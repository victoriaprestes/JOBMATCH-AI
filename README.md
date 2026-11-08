# JobMatch AI

Aplicação pessoal para organizar vagas, acompanhar candidaturas e explorar aderência entre requisitos e competências.

## Funcionalidades do MVP

- Cadastro de vagas e descrições.
- Filtros por status, modalidade e salário.
- Acompanhamento de candidaturas.
- Indicador exploratório de aderência por palavras-chave.
- Importação e exportação CSV.
- Persistência local em SQLite.

## Tecnologias

- Python
- Streamlit
- SQLite
- Pandas

## Executar localmente

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Executar no GitHub Codespaces

1. Crie um repositório público chamado `jobmatch-ai`.
2. Envie os arquivos deste projeto para o repositório.
3. Abra **Code > Codespaces > Create codespace on main**.
4. Aguarde a instalação automática das dependências.
5. No terminal do Codespace, execute:

```bash
python -m streamlit run app.py
```

6. Abra a porta 8501 quando o Codespaces oferecer o link.

## Privacidade

O banco `data/jobs.db` é local e está excluído do Git. Não adicione currículo, telefone, endereço ou dados pessoais ao repositório público. Para uma demonstração pública, use apenas dados fictícios.

## Sobre a pontuação

A pontuação atual é uma heurística lexical: procura termos associados ao perfil dentro da descrição da vaga. Não é um modelo de IA, não é uma probabilidade de contratação e não avalia contexto ou senioridade. A próxima evolução planejada é adicionar análise semântica gratuita e explicações mais completas.

## Roadmap

- [ ] Melhorar o matching com TF-IDF e similaridade semântica.
- [ ] Criar perfil editável de competências.
- [ ] Adicionar análise de lacunas por vaga.
- [ ] Adicionar dados demonstrativos fictícios.
- [ ] Avaliar integração com fontes de vagas que permitam acesso automatizado.
- [ ] Preparar deploy público separado dos dados pessoais.


## Coleta automática de vagas

O workflow `.github/workflows/collect-jobs.yml` executa a coleta diariamente às 11:00 UTC (08:00 em Curitiba no horário UTC-3) e também pode ser executado manualmente em **Actions → Atualizar vagas automaticamente → Run workflow**.

Fontes da primeira versão:
- **Remotive**: vagas remotas com localização explicitamente compatível com Brasil, América Latina ou mundial. A API pública atrasa as listagens em 24 horas e exige atribuição/link para o anúncio original; por isso a aplicação mantém a fonte e o link de cada vaga.
- **Arbeitnow**: feed público, predominantemente europeu; nesta versão só entram vagas cuja localização indica Brasil, América Latina ou Curitiba/Paraná. É provável que a cobertura local seja limitada.

O coletor grava `data/jobs_feed.json`. O GitHub Actions faz commit do arquivo e a aplicação o lê na aba **Vagas automáticas**. O feed contém apenas dados públicos dos anúncios; dados pessoais e candidaturas permanecem no banco local excluído do Git.

**Limitações:** esta primeira versão não cobre todas as empresas de Curitiba nem plataformas fechadas como LinkedIn/Indeed. Não há garantia de salário: anúncios sem remuneração informada são exibidos como “não informado”, não presumidos como abaixo do piso. A elegibilidade geográfica, o salário e se a vaga continua aberta devem ser confirmados no anúncio original.
