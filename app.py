import streamlit as st
import pandas as pd
from src.database import init_db, add_job, get_jobs, update_status, delete_job, export_jobs, import_jobs
from src.matcher import score_job, explain_match

st.set_page_config(page_title="JobMatch AI", page_icon="🎯", layout="wide")
init_db()

st.title("🎯 JobMatch AI")
st.caption("Seu painel pessoal para organizar oportunidades e priorizar candidaturas.")

PROFILE_SKILLS = [
    "Excel", "SAP", "contas a pagar", "contas a receber", "fornecedores",
    "contratos", "processos", "indicadores", "KPI", "Power BI", "SQL",
    "Python", "Pandas", "gestão de projetos", "governança", "controles internos",
    "compliance", "BPMN", "melhoria contínua", "inglês", "operações"
]
PROFILE_CONTEXT = (
    "Experiência administrativa e financeira, contas a pagar e receber, "
    "fornecedores, contratos, suporte à diretoria, SAP, operações, indicadores "
    "e acompanhamento de processos. Conhecimentos em Excel, Power BI, SQL e Python. "
    "Graduação em Estatística e Ciência de Dados em andamento. Inglês fluente."
)

with st.sidebar:
    st.header("Filtros")
    status_filter = st.multiselect(
        "Status",
        ["Nova", "Salva", "Candidatura enviada", "Entrevista", "Teste", "Recusada", "Encerrada"],
        default=["Nova", "Salva", "Candidatura enviada", "Entrevista", "Teste"]
    )
    min_salary = st.number_input("Salário mínimo (R$)", min_value=0, value=3000, step=250)
    work_modes = st.multiselect("Modalidade", ["Híbrido", "Presencial", "Remoto"], default=["Híbrido", "Presencial", "Remoto"])

tab0, tab1, tab2, tab3 = st.tabs(["🔎 Vagas automáticas", "📋 Minhas vagas", "➕ Cadastrar vaga", "📦 Importar / exportar"])

with tab2:
    st.subheader("Adicionar oportunidade")
    with st.form("new_job", clear_on_submit=True):
        c1, c2 = st.columns(2)
        company = c1.text_input("Empresa *")
        title = c2.text_input("Cargo *")
        c3, c4, c5 = st.columns(3)
        location = c3.text_input("Localização", "Curitiba / PR")
        mode = c4.selectbox("Modalidade", ["Híbrido", "Presencial", "Remoto", "Não informado"])
        salary = c5.number_input("Salário bruto mensal (R$)", min_value=0, value=0, step=250)
        link = st.text_input("Link da vaga")
        description = st.text_area("Descrição e requisitos *", height=180)
        notes = st.text_area("Observações pessoais", height=80)
        submitted = st.form_submit_button("Salvar vaga", type="primary")
        if submitted:
            if not company.strip() or not title.strip() or not description.strip():
                st.error("Preencha empresa, cargo e descrição.")
            else:
                add_job(company, title, location, mode, int(salary), link, description, notes)
                st.success("Vaga cadastrada.")
                st.rerun()

with tab1:
    jobs = get_jobs()
    if not jobs:
        st.info("Você ainda não cadastrou vagas. Use a aba **Cadastrar vaga** para começar.")
    else:
        df = pd.DataFrame(jobs)
        filtered = df.copy()
        if status_filter:
            filtered = filtered[filtered["status"].isin(status_filter)]
        if work_modes:
            filtered = filtered[filtered["work_mode"].isin(work_modes + ["Não informado"])]
        filtered = filtered[(filtered["salary"].fillna(0) == 0) | (filtered["salary"].fillna(0) >= min_salary)]
        if filtered.empty:
            st.warning("Nenhuma vaga corresponde aos filtros atuais.")
        else:
            scored = []
            for _, row in filtered.iterrows():
                score, matched, missing = score_job(str(row["description"]))
                scored.append((score, matched, missing))
            filtered["compatibilidade"] = [x[0] for x in scored]
            filtered["competencias"] = [", ".join(x[1][:5]) for x in scored]
            filtered = filtered.sort_values(["compatibilidade", "created_at"], ascending=[False, False])

            m1, m2, m3 = st.columns(3)
            m1.metric("Vagas exibidas", len(filtered))
            m2.metric("Compatibilidade média", f"{filtered['compatibilidade'].mean():.0f}%")
            m3.metric("Candidaturas enviadas", int((df["status"] == "Candidatura enviada").sum()))

            for _, job in filtered.iterrows():
                with st.container(border=True):
                    left, right = st.columns([5, 1])
                    left.subheader(f"{job['title']} — {job['company']}")
                    left.caption(f"{job['location']} · {job['work_mode']} · {job['status']}")
                    if job["salary"]:
                        left.write(f"Salário informado: R$ {job['salary']:,.0f}".replace(",", "."))
                    else:
                        left.write("Salário: não informado")
                    right.metric("Match", f"{job['compatibilidade']}%")
                    if job["competencias"]:
                        st.caption("Competências identificadas no seu perfil: " + job["competencias"])
                    with st.expander("Ver descrição, análise e atualizar"):
                        st.write(job["description"])
                        score, matched, missing = score_job(str(job["description"]))
                        st.markdown("**Pontos de aderência**")
                        st.write(", ".join(matched) if matched else "Nenhuma competência identificada automaticamente.")
                        st.markdown("**Possíveis lacunas**")
                        st.write(", ".join(missing) if missing else "Nenhuma lacuna identificada pela análise por palavras-chave.")
                        st.caption(explain_match(score))
                        if job["url"]:
                            st.markdown(f"[Abrir anúncio]({job['url']})")
                        new_status = st.selectbox(
                            "Atualizar status",
                            ["Nova", "Salva", "Candidatura enviada", "Entrevista", "Teste", "Recusada", "Encerrada"],
                            index=["Nova", "Salva", "Candidatura enviada", "Entrevista", "Teste", "Recusada", "Encerrada"].index(job["status"]),
                            key=f"status_{job['id']}"
                        )
                        note = st.text_area("Observações", value=job["notes"] or "", key=f"note_{job['id']}")
                        b1, b2 = st.columns(2)
                        if b1.button("Salvar alterações", key=f"save_{job['id']}"):
                            update_status(int(job["id"]), new_status, note)
                            st.success("Atualizado.")
                            st.rerun()
                        if b2.button("Excluir vaga", key=f"del_{job['id']}"):
                            delete_job(int(job["id"]))
                            st.rerun()

with tab3:
    st.subheader("Backup e migração")
    st.write("Exporte suas vagas para CSV ou importe um arquivo CSV com as colunas do modelo.")
    data = export_jobs()
    if data:
        csv = pd.DataFrame(data).to_csv(index=False).encode("utf-8-sig")
        st.download_button("Baixar backup CSV", csv, "jobmatch-vagas.csv", "text/csv")
    upload = st.file_uploader("Importar CSV", type=["csv"])
    if upload and st.button("Importar vagas"):
        try:
            count = import_jobs(pd.read_csv(upload))
            st.success(f"{count} vaga(s) importada(s).")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível importar: {exc}")

st.divider()
st.caption("MVP 0.1 · A pontuação atual usa correspondência de competências por palavras-chave. Não é uma decisão automatizada nem substitui a leitura da descrição.")
