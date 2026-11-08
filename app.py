import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from src.database import init_db, save_automatic_job, get_jobs, update_job, delete_job, STATUSES
from src.matcher import score_job, explain_match

st.set_page_config(page_title="JobMatch AI", page_icon="🎯", layout="wide")
init_db()

st.title("🎯 JobMatch AI")
st.caption("Vagas automáticas de entrada no Brasil · Curitiba e região metropolitana ou remoto Brasil.")

PROFILE_GROUP = "Perfil atual"
TRANSITION_GROUP = "Trilha de transição"

with st.sidebar:
    st.header("Filtros")
    role_groups = st.multiselect("Trilha profissional", [PROFILE_GROUP, TRANSITION_GROUP],
                                 default=[PROFILE_GROUP, TRANSITION_GROUP])
    work_modes = st.multiselect("Modalidade", ["Presencial", "Híbrido", "Remoto"],
                                default=["Presencial", "Híbrido", "Remoto"])
    min_salary = st.number_input("Piso salarial bruto mensal (R$)", min_value=0, value=3000, step=250)
    hide_below = st.checkbox("Ocultar vagas com salário informado abaixo do piso", value=True)
    show_unknown_salary = st.checkbox("Mostrar vagas sem salário divulgado", value=True)
    show_unknown_benefits = st.checkbox("Mostrar vagas sem benefícios identificados", value=True)

tab_auto, tab_saved = st.tabs(["🔎 Vagas automáticas", "⭐ Vagas salvas / candidaturas"])

@st.cache_data(ttl=300)
def load_feed():
    url = "https://raw.githubusercontent.com/victoriaprestes/JOBMATCH-AI/main/data/jobs_feed.json"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.json()

with tab_auto:
    st.subheader("Oportunidades encontradas automaticamente")
    try:
        feed = load_feed()
    except Exception as exc:
        feed = {}
        st.error(f"Não foi possível carregar o feed: {exc}")

    if not feed:
        st.info("Aguardando a próxima coleta automática do GitHub Actions.")
    else:
        st.caption(f"Última atualização: {feed.get('updated_at', 'não informada')} · {feed.get('count', 0)} vaga(s) no feed")
        st.caption("Contratação no Brasil confirmada pelo local/escopo informado na fonte. Cobertura parcial das fontes conectadas.")
        if feed.get("errors"):
            st.warning("Fontes com falha nesta coleta: " + " | ".join(feed["errors"]))
        if feed.get("coverage_note"):
            st.caption(feed["coverage_note"])

        query = st.text_input("Pesquisar cargo, empresa ou competência", key="auto_search").strip().lower()
        saved_ids = {(j.get("source"), j.get("external_id")) for j in get_jobs()}
        visible = []
        for job in feed.get("jobs", []):
            if job.get("eligibility_status") != "Brasil confirmado":
                continue
            if job.get("role_group") not in role_groups or job.get("work_mode") not in work_modes:
                continue
            salary = job.get("salary_min_brl_monthly")
            if salary is None and not show_unknown_salary:
                continue
            if salary is not None and hide_below and salary < min_salary:
                continue
            if not show_unknown_benefits and not job.get("benefits"):
                continue
            hay = " ".join([job.get("title", ""), job.get("company", ""),
                            job.get("description", ""), job.get("role_group", "")]).lower()
            if query and query not in hay:
                continue
            score, matched, missing, learning = score_job(
                job.get("description", ""), job.get("title", ""), job.get("role_group", PROFILE_GROUP))
            item = dict(job)
            item.update(_score=score, _matched=matched, _missing=missing, _learning=learning)
            visible.append(item)

        visible.sort(key=lambda j: (j.get("role_group") != PROFILE_GROUP,
                                    -j.get("_score", 0), j.get("published_at") or ""), reverse=False)
        a,b,c,d = st.columns(4)
        a.metric("Vagas no filtro", len(visible))
        b.metric("Perfil atual", sum(j.get("role_group") == PROFILE_GROUP for j in visible))
        c.metric("Trilha de transição", sum(j.get("role_group") == TRANSITION_GROUP for j in visible))
        d.metric("Piso confirmado", sum(j.get("salary_min_brl_monthly") is not None and
                                        j.get("salary_min_brl_monthly") >= min_salary for j in visible))
        unknown = sum(j.get("salary_min_brl_monthly") is None for j in visible)
        if unknown:
            st.caption(f"{unknown} vaga(s) sem salário divulgado; não é possível confirmar que atendam ao piso de R$ {min_salary:,.0f}/mês.".replace(",", "."))

        for i, job in enumerate(visible):
            key = (job.get("source"), job.get("external_id"))
            is_saved = key in saved_ids
            with st.container(border=True):
                left, right = st.columns([5,1])
                left.markdown(f"**{job.get('title','Cargo')} — {job.get('company','Empresa')}**")
                left.caption(f"{job.get('role_group')} · {job.get('location','Local não informado')} · {job.get('work_mode','Modalidade não informada')}")
                left.caption(f"Fonte: {job.get('source','')} · Vínculo: {job.get('employment_type','Não informado')}")
                if job.get("published_at"):
                    try:
                        dt = datetime.fromisoformat(str(job["published_at"]).replace("Z","+00:00"))
                        left.caption("Publicada em " + dt.strftime("%d/%m/%Y"))
                    except ValueError:
                        pass
                salary_label = job.get("salary_label") or "Não informado"
                low, high = job.get("salary_min_brl_monthly"), job.get("salary_max_brl_monthly")
                if low is None:
                    salary_label += " — piso não confirmado"
                else:
                    salary_label += f" · faixa mensal estimada: R$ {low:,.0f}".replace(",", ".")
                    if high is not None and high != low:
                        salary_label += f" a R$ {high:,.0f}".replace(",", ".")
                left.write("**Remuneração:** " + salary_label)
                benefits = job.get("benefits") or ""
                left.write("**Benefícios:** " + (benefits if benefits else "Não identificados no anúncio coletado"))
                right.metric("Aderência lexical", f"{job['_score']}%")
                if is_saved:
                    right.success("Já salva")
                elif right.button("⭐ Salvar vaga", key=f"save_{i}"):
                    save_automatic_job(job)
                    st.success("Vaga salva para acompanhar.")
                    st.rerun()
                if job.get("url"):
                    left.markdown(f"[Ver anúncio original]({job['url']})")
                with st.expander("Descrição e análise de compatibilidade"):
                    st.write(job.get("description") or "Descrição não disponível")
                    st.write("**Competências do seu perfil encontradas no texto:** " +
                             (", ".join(job["_matched"]) if job["_matched"] else "Nenhuma identificada"))
                    if job.get("role_group") == TRANSITION_GROUP:
                        st.write("**Conhecimentos da trilha citados no anúncio:** " +
                                 (", ".join(job["_learning"]) if job["_learning"] else "Não identificados automaticamente"))
                    st.caption(explain_match(job["_score"], job.get("role_group", PROFILE_GROUP)))
        st.caption("A aderência é uma correspondência lexical aproximada, não uma avaliação semântica nem probabilidade de contratação. Benefícios só são exibidos quando identificados na fonte ou em seção explícita do anúncio.")

with tab_saved:
    st.subheader("Vagas que você salvou")
    saved = get_jobs()
    if not saved:
        st.info("Use o botão ⭐ Salvar vaga na lista automática. Não há cadastro manual.")
    else:
        st.caption(f"{len(saved)} vaga(s) salvas. Atualize o status conforme avançar no processo.")
        for job in saved:
            with st.container(border=True):
                left, right = st.columns([4,2])
                left.markdown(f"**{job['title']} — {job['company']}**")
                left.caption(f"{job.get('location','')} · {job.get('work_mode','')} · Origem: {job.get('source','')}")
                if job.get("url"):
                    left.markdown(f"[Ver anúncio original]({job['url']})")
                left.write("**Benefícios:** " + (job.get("benefits") or "Não identificados"))
                current = job.get("status") if job.get("status") in STATUSES else "Salva"
                new_status = right.selectbox("Etapa", STATUSES, index=STATUSES.index(current), key=f"status_{job['id']}")
                if right.button("Atualizar etapa", key=f"update_{job['id']}"):
                    update_job(int(job["id"]), new_status, job.get("notes") or "")
                    st.success("Etapa atualizada.")
                    st.rerun()
                if right.button("Remover da lista", key=f"remove_{job['id']}"):
                    delete_job(int(job["id"]))
                    st.rerun()
