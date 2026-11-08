import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from src.database import init_db, add_job, get_jobs, update_status, delete_job, export_jobs, import_jobs
from src.matcher import score_job, explain_match

st.set_page_config(page_title="JobMatch AI", page_icon="🎯", layout="wide")
init_db()

st.title("🎯 JobMatch AI")
st.caption("Vagas de entrada no Brasil, filtradas por localização, senioridade e aderência ao seu perfil.")

PROFILE_GROUP = "Perfil atual"
TRANSITION_GROUP = "Trilha de transição"

with st.sidebar:
    st.header("Filtros das vagas automáticas")
    role_groups = st.multiselect(
        "Trilha profissional",
        [PROFILE_GROUP, TRANSITION_GROUP],
        default=[PROFILE_GROUP, TRANSITION_GROUP],
    )
    work_modes = st.multiselect(
        "Modalidade",
        ["Presencial", "Híbrido", "Remoto"],
        default=["Presencial", "Híbrido", "Remoto"],
    )
    min_salary = st.number_input("Piso salarial bruto mensal (R$)", min_value=0, value=3000, step=250)
    hide_below = st.checkbox("Ocultar vagas com salário informado abaixo do piso", value=True)
    show_unknown_salary = st.checkbox("Mostrar vagas sem salário divulgado", value=True)

tab0, tab1, tab2, tab3 = st.tabs(["🔎 Vagas automáticas", "📋 Minhas vagas", "➕ Cadastrar vaga", "📦 Importar / exportar"])

with tab0:
    st.subheader("Oportunidades encontradas automaticamente")
    feed_path = Path("data/jobs_feed.json")
    try:
        # O feed é atualizado pelo GitHub Actions. Busca sempre a versão pública
        # mais recente para que o Codespace não dependa de um git pull diário.
        response = requests.get(
            "https://raw.githubusercontent.com/victoriaprestes/JOBMATCH-AI/main/data/jobs_feed.json",
            timeout=8,
        )
        response.raise_for_status()
        feed = response.json()
    except Exception:
        try:
            feed = json.loads(feed_path.read_text(encoding="utf-8")) if feed_path.exists() else {}
        except Exception as exc:
            feed = {}
            st.error(f"Não foi possível ler o feed local ou remoto: {exc}")

    if not feed:
        st.info("A coleta ainda não foi executada. O GitHub Actions fará a busca diária; também é possível iniciá-la manualmente na aba Actions do repositório.")
    else:
        st.caption(
            f"Última atualização: {feed.get('updated_at', 'não informada')} · "
            f"{feed.get('count', 0)} vaga(s) elegíveis no feed"
        )
        st.success("Todas as vagas deste feed passaram pelo filtro de contratação explicitamente confirmada no Brasil.")
        if feed.get("errors"):
            st.warning("Algumas fontes não responderam nesta execução: " + " | ".join(feed["errors"]))
        if feed.get("coverage_note"):
            st.caption(feed["coverage_note"])

        automatic = feed.get("jobs", [])
        query = st.text_input("Pesquisar cargo, empresa ou competência", key="auto_search").strip().lower()
        visible = []
        for job in automatic:
            if job.get("eligibility_status") != "Brasil confirmado":
                continue
            if job.get("role_group") not in role_groups:
                continue
            if job.get("work_mode") not in work_modes:
                continue
            salary_min = job.get("salary_min_brl_monthly")
            if salary_min is None:
                if not show_unknown_salary:
                    continue
            elif hide_below and salary_min < min_salary:
                continue
            hay = " ".join([
                job.get("title", ""), job.get("company", ""),
                job.get("description", ""), job.get("role_group", "")
            ]).lower()
            if query and query not in hay:
                continue
            score, matched, missing, learning = score_job(
                job.get("description", ""), job.get("title", ""), job.get("role_group", PROFILE_GROUP)
            )
            job_view = dict(job)
            job_view["_score"] = score
            job_view["_matched"] = matched
            job_view["_missing"] = missing
            job_view["_learning"] = learning
            visible.append(job_view)

        visible.sort(key=lambda j: (
            j.get("role_group") != PROFILE_GROUP,
            -j.get("_score", 0),
            j.get("published_at") or "",
        ))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Vagas no filtro", len(visible))
        c2.metric("Perfil atual", sum(j.get("role_group") == PROFILE_GROUP for j in visible))
        c3.metric("Trilha de transição", sum(j.get("role_group") == TRANSITION_GROUP for j in visible))
        c4.metric(
            "Piso confirmado",
            sum(
                j.get("salary_min_brl_monthly") is not None
                and j.get("salary_min_brl_monthly") >= min_salary
                for j in visible
            ),
        )
        unknown_salary_count = sum(j.get("salary_min_brl_monthly") is None for j in visible)
        if unknown_salary_count:
            st.caption(
                f"{unknown_salary_count} vaga(s) sem salário divulgado: não é possível confirmar "
                f"que atendam ao piso de R$ {min_salary:,.0f}/mês.".replace(",", ".")
            )

        if not visible:
            st.info(
                "Nenhuma vaga encontrada com os filtros atuais. Isso não significa que não existam oportunidades: "
                "as fontes conectadas têm cobertura parcial e o filtro não aceita anúncios sem confirmação de Brasil "
                "ou sem evidência de nível de entrada."
            )

        for job in visible:
            with st.container(border=True):
                left, right = st.columns([5, 1])
                left.markdown(f"**{job.get('title', 'Cargo')} — {job.get('company', 'Empresa')}**")
                group = job.get("role_group", PROFILE_GROUP)
                left.caption(f"{group} · {job.get('location', 'Local não informado')} · {job.get('work_mode', 'Modalidade não informada')}")
                left.caption(f"Brasil confirmado · Fonte: {job.get('source', '')} · Vínculo: {job.get('employment_type', 'Não informado')}")
                if job.get("published_at"):
                    try:
                        published = datetime.fromisoformat(str(job["published_at"]).replace("Z", "+00:00"))
                        left.caption("Publicada em " + published.strftime("%d/%m/%Y"))
                    except ValueError:
                        pass
                if re.search(r"\b(pcd|pessoa com deficiencia|pessoas com deficiencia)\b", (job.get("title", "") + " " + job.get("description", "")).lower()):
                    left.caption("O anúncio menciona vaga afirmativa/exclusiva para PCD; confira os critérios de elegibilidade.")
                salary_label = job.get("salary_label") or "Não informado"
                low = job.get("salary_min_brl_monthly")
                if low is None:
                    salary_label += " — piso salarial não confirmado"
                high = job.get("salary_max_brl_monthly")
                if low is not None:
                    salary_label += f" · faixa estimada: R$ {low:,.0f}".replace(",", ".")
                    if high is not None and high != low:
                        salary_label += f" a R$ {high:,.0f}".replace(",", ".")
                    salary_label += "/mês"
                left.write("Remuneração: " + salary_label)
                left.caption(job.get("salary_note", "Conferir remuneração no anúncio original"))
                right.metric("Aderência", f"{job['_score']}%")
                if job.get("url"):
                    left.markdown(f"[Ver anúncio original]({job['url']})")
                with st.expander("Descrição e análise de compatibilidade"):
                    st.write(job.get("description") or "Descrição não disponível")
                    st.write("**Competências do seu perfil encontradas:** " + (", ".join(job["_matched"]) if job["_matched"] else "Não identificadas automaticamente"))
                    if group == TRANSITION_GROUP:
                        st.write("**Conhecimentos da trilha para estudar/conferir:** " + (", ".join(job["_learning"]) if job["_learning"] else "Confira os requisitos específicos no anúncio"))
                    st.caption(explain_match(job["_score"], group))

        st.caption(
            "O piso salarial é aplicado somente quando o anúncio informa remuneração em reais. "
            "Vagas sem salário divulgado ficam identificadas separadamente; o sistema não presume que atendam ao piso."
        )

with tab1:
    st.subheader("Minhas vagas")
    jobs = get_jobs()
    if not jobs:
        st.info("Você ainda não cadastrou vagas. Use a aba **Cadastrar vaga** para começar.")
    else:
        df = pd.DataFrame(jobs)
        filtered = df.copy()
        status_filter = st.multiselect(
            "Status",
            ["Nova", "Salva", "Candidatura enviada", "Entrevista", "Teste", "Recusada", "Encerrada"],
            default=["Nova", "Salva", "Candidatura enviada", "Entrevista", "Teste"],
        )
        work_modes_saved = st.multiselect(
            "Modalidade das vagas salvas",
            ["Híbrido", "Presencial", "Remoto", "Não informado"],
            default=["Híbrido", "Presencial", "Remoto", "Não informado"],
        )
        min_saved_salary = st.number_input("Salário mínimo das vagas salvas (R$)", min_value=0, value=3000, step=250)
        if status_filter:
            filtered = filtered[filtered["status"].isin(status_filter)]
        if work_modes_saved:
            filtered = filtered[filtered["work_mode"].isin(work_modes_saved)]
        filtered = filtered[(filtered["salary"].fillna(0) == 0) | (filtered["salary"].fillna(0) >= min_saved_salary)]
        if filtered.empty:
            st.warning("Nenhuma vaga corresponde aos filtros atuais.")
        else:
            scored = []
            for _, row in filtered.iterrows():
                score, matched, missing, learning = score_job(str(row["description"]), str(row["title"]))
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
                    left.write(f"Salário informado: R$ {job['salary']:,.0f}".replace(",", ".") if job["salary"] else "Salário: não informado")
                    right.metric("Aderência", f"{job['compatibilidade']}%")
                    if job["competencias"]:
                        st.caption("Competências identificadas: " + job["competencias"])
                    with st.expander("Ver descrição, análise e atualizar"):
                        st.write(job["description"])
                        score, matched, missing, learning = score_job(str(job["description"]), str(job["title"]))
                        st.markdown("**Pontos de aderência**")
                        st.write(", ".join(matched) if matched else "Nenhuma competência identificada automaticamente.")
                        st.markdown("**Possíveis lacunas**")
                        st.write(", ".join(missing) if missing else "Nenhuma lacuna identificada automaticamente.")
                        st.caption(explain_match(score))
                        if job["url"]:
                            st.markdown(f"[Abrir anúncio]({job['url']})")
                        statuses = ["Nova", "Salva", "Candidatura enviada", "Entrevista", "Teste", "Recusada", "Encerrada"]
                        new_status = st.selectbox("Atualizar status", statuses, index=statuses.index(job["status"]), key=f"status_{job['id']}")
                        note = st.text_area("Observações", value=job["notes"] or "", key=f"note_{job['id']}")
                        b1, b2 = st.columns(2)
                        if b1.button("Salvar alterações", key=f"save_{job['id']}"):
                            update_status(int(job["id"]), new_status, note)
                            st.success("Atualizado.")
                            st.rerun()
                        if b2.button("Excluir vaga", key=f"del_{job['id']}"):
                            delete_job(int(job["id"]))
                            st.rerun()

with tab2:
    st.subheader("Adicionar oportunidade manualmente")
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
st.caption("JobMatch AI · coleta automática diária · filtros determinísticos de país, senioridade e trilha profissional.")
