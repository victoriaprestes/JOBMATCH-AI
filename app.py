import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

from src.database import init_db, save_automatic_job, get_jobs, update_job, delete_job, STATUSES
from src.matcher import score_job, explain_match

st.set_page_config(page_title="JobMatch AI", page_icon="🎯", layout="wide")
init_db()

st.title("🎯 JobMatch AI")
st.caption("Vagas de entrada no Brasil · Curitiba e região metropolitana ou remoto Brasil.")

PROFILE_GROUP = "Perfil atual"
TRANSITION_GROUP = "Trilha de transição"
CURITIBA_TZ = ZoneInfo("America/Sao_Paulo")
TODAY = datetime.now(CURITIBA_TZ).date()

@st.cache_data(ttl=300)
def load_feed():
    url = "https://raw.githubusercontent.com/victoriaprestes/JOBMATCH-AI/main/data/jobs_feed.json"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.json()

def published_date(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
        return parsed.astimezone(CURITIBA_TZ).date()
    except (TypeError, ValueError):
        return None

def age_label(posted):
    if posted is None:
        return "Data de publicação não informada"
    days = (TODAY - posted).days
    if days <= 0:
        return "Publicada hoje"
    if days == 1:
        return "Publicada ontem"
    return f"Publicada há {days} dias"

tab_auto, tab_saved = st.tabs(["🔎 Vagas automáticas", "⭐ Vagas salvas / candidaturas"])

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

        # Filtros avançados ficam na área principal, sem sidebar.
        with st.expander("⚙️ Filtros avançados", expanded=False):
            f1, f2 = st.columns(2)
            with f1:
                role_groups = st.multiselect(
                    "Trilha profissional", [PROFILE_GROUP, TRANSITION_GROUP],
                    default=[PROFILE_GROUP, TRANSITION_GROUP], key="role_groups"
                )
                work_modes = st.multiselect(
                    "Modalidade", ["Presencial", "Híbrido", "Remoto"],
                    default=["Presencial", "Híbrido", "Remoto"], key="work_modes"
                )
                min_salary = st.number_input(
                    "Piso salarial bruto mensal (R$)", min_value=0, value=3000,
                    step=250, key="min_salary"
                )
            with f2:
                include_older = st.checkbox(
                    "Incluir vagas com mais de 7 dias (até 45 dias), se ainda listadas pela fonte",
                    value=False, key="include_older"
                )
                hide_below = st.checkbox(
                    "Ocultar vagas com salário informado abaixo do piso",
                    value=True, key="hide_below"
                )
                show_unknown_salary = st.checkbox(
                    "Mostrar vagas sem salário divulgado", value=True, key="show_unknown_salary"
                )
                show_unknown_benefits = st.checkbox(
                    "Mostrar vagas sem benefícios identificados", value=True, key="show_unknown_benefits"
                )

        role_groups = st.session_state.get("role_groups", [PROFILE_GROUP, TRANSITION_GROUP])
        work_modes = st.session_state.get("work_modes", ["Presencial", "Híbrido", "Remoto"])
        min_salary = st.session_state.get("min_salary", 3000)
        include_older = st.session_state.get("include_older", False)
        hide_below = st.session_state.get("hide_below", True)
        show_unknown_salary = st.session_state.get("show_unknown_salary", True)
        show_unknown_benefits = st.session_state.get("show_unknown_benefits", True)

        query = st.text_input("Pesquisar cargo, empresa ou competência", key="auto_search").strip().lower()
        saved_ids = {(j.get("source"), j.get("external_id")) for j in get_jobs()}
        candidates = []
        for job in feed.get("jobs", []):
            if job.get("eligibility_status") != "Brasil confirmado":
                continue
            posted = published_date(job.get("published_at"))
            if posted is None:
                continue
            age_days = (TODAY - posted).days
            # Padrão: hoje até 7 dias. Expansão opcional: até 45 dias,
            # desde que o anúncio continue sendo retornado pela fonte consultada.
            if age_days < 0 or (age_days >= 7 and not include_older) or (age_days > 45 and include_older):
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
            item.update(_score=score, _matched=matched, _missing=missing, _learning=learning,
                        _posted_date=posted, _age_days=age_days)
            candidates.append(item)

        # Primeiro hoje, depois ontem; demais dias em ordem decrescente de publicação.
        candidates.sort(key=lambda j: (
            j["_age_days"], j.get("role_group") != PROFILE_GROUP,
            -j.get("_score", 0)
        ))
        quick_filter = st.session_state.get("quick_filter", "all")
        visible = candidates
        if quick_filter == "profile":
            visible = [j for j in visible if j.get("role_group") == PROFILE_GROUP]
        elif quick_filter == "transition":
            visible = [j for j in visible if j.get("role_group") == TRANSITION_GROUP]
        elif quick_filter == "salary":
            visible = [j for j in visible if j.get("salary_min_brl_monthly") is not None
                       and j.get("salary_min_brl_monthly") >= min_salary]

        today_count = sum(j["_age_days"] == 0 for j in candidates)
        yesterday_count = sum(j["_age_days"] == 1 for j in candidates)
        profile_count = sum(j.get("role_group") == PROFILE_GROUP for j in candidates)
        transition_count = sum(j.get("role_group") == TRANSITION_GROUP for j in candidates)
        salary_count = sum(j.get("salary_min_brl_monthly") is not None and
                           j.get("salary_min_brl_monthly") >= min_salary for j in candidates)

        st.caption(
            f"Período exibido: {'últimos 45 dias' if include_older else 'menos de 7 dias'} · "
            f"{today_count} publicada(s) hoje · {yesterday_count} ontem. "
            "As mais recentes aparecem primeiro."
        )
        m1, m2, m3, m4 = st.columns(4)
        if m1.button(f"📋 Vagas no filtro\n{len(candidates)}", use_container_width=True,
                     type="primary" if quick_filter == "all" else "secondary"):
            st.session_state["quick_filter"] = "all"
            st.rerun()
        if m2.button(f"👤 Perfil atual\n{profile_count}", use_container_width=True,
                     type="primary" if quick_filter == "profile" else "secondary"):
            st.session_state["quick_filter"] = "profile"
            st.rerun()
        if m3.button(f"🔄 Trilha de transição\n{transition_count}", use_container_width=True,
                     type="primary" if quick_filter == "transition" else "secondary"):
            st.session_state["quick_filter"] = "transition"
            st.rerun()
        if m4.button(f"💰 Piso confirmado\n{salary_count}", use_container_width=True,
                     type="primary" if quick_filter == "salary" else "secondary"):
            st.session_state["quick_filter"] = "salary"
            st.rerun()

        if quick_filter != "all":
            st.caption("Atalho ativo: clique em “Vagas no filtro” para voltar à lista completa.")
        unknown = sum(j.get("salary_min_brl_monthly") is None for j in visible)
        if unknown:
            st.caption(f"{unknown} vaga(s) sem salário divulgado; não é possível confirmar que atendam ao piso de R$ {min_salary:,.0f}/mês.".replace(",", "."))

        if not visible:
            st.info("Nenhuma vaga encontrada com os filtros atuais. Experimente incluir vagas com mais de 7 dias ou ajustar os filtros avançados.")
        for i, job in enumerate(visible):
            key = (job.get("source"), job.get("external_id"))
            is_saved = key in saved_ids
            with st.container(border=True):
                left, right = st.columns([5,1])
                left.markdown(f"**{job.get('title','Cargo')} — {job.get('company','Empresa')}**")
                left.caption(f"{age_label(job['_posted_date'])} · {job.get('role_group')} · {job.get('location','Local não informado')} · {job.get('work_mode','Modalidade não informada')}")
                left.caption(f"Fonte: {job.get('source','')} · Vínculo: {job.get('employment_type','Não informado')}")
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
