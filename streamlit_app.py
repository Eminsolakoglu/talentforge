"""
TalentForge — Streamlit Frontend
CV yükleme, aday arama (form + doğal dil), bilgi grafiği görselleştirme
"""

import streamlit as st
import requests
import json
import os
import tempfile
from pyvis.network import Network
import tempfile as tmp_module
from dotenv import load_dotenv

load_dotenv()

DEMO_LOCAL_NEO4J = os.getenv("STREAMLIT_DEMO_LOCAL_NEO4J", "true").lower() in {"1", "true", "yes"}
if DEMO_LOCAL_NEO4J:
    os.environ["NEO4J_URI"] = os.getenv("LOCAL_NEO4J_URI", "bolt://localhost:7687")
    os.environ["NEO4J_USERNAME"] = os.getenv("LOCAL_NEO4J_USERNAME", "neo4j")
    os.environ["NEO4J_PASSWORD"] = os.getenv(
        "LOCAL_NEO4J_PASSWORD",
        os.getenv("NEO4J_LOCAL_PASSWORD", "password123"),
    )
    os.environ["NEO4J_DATABASE"] = os.getenv("LOCAL_NEO4J_DATABASE", "neo4j")
    os.environ.setdefault("LLM_BACKEND", "huggingface")
    os.environ.setdefault("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="TalentForge",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────

st.sidebar.title("🔍 TalentForge")
st.sidebar.caption("LLM + Knowledge Graph ile Akıllı Aday Eşleştirme")
st.sidebar.divider()

page = st.sidebar.radio(
    "Sayfa",
    ["📄 CV Yükle", "🔎 Aday Ara", "💬 Doğal Dil Ara", "🕸️ Bilgi Grafiği", "🔗 Entity Resolution"],
    label_visibility="collapsed",
)

st.sidebar.divider()
st.sidebar.info(
    "**Bitirme Projesi**\n\n"
    "Marmara Üniversitesi\n"
    "Bilgisayar Mühendisliği\n\n"
    "Gizem Özdemir\n"
    "M. Emin Solakoğlu\n"
    "Emre Kılıç\n\n"
    "Danışman: Doç. Dr. Buket Doğan"
)


# ── Yardımcı: Aday kartı ─────────────────────────────────────────────

def render_candidate_card(candidate: dict, rank: int, expanded: bool = False):
    """Tek bir aday kartını render eder (arama sonuçları için)"""
    score = candidate.get("total_score", 0)
    score_color = "🟢" if score >= 70 else ("🟡" if score >= 40 else "🔴")

    with st.expander(
        f"{score_color} **#{rank} {candidate.get('name', '-')}** — "
        f"Skor: {score}/100 — "
        f"{candidate.get('experience_count', 0)} deneyim",
        expanded=expanded,
    ):
        # Skor kırılımı
        st.write("**Skor Kırılımı:**")
        breakdown = candidate.get("score_breakdown", {})
        labels = {
            "must_skills": "Zorunlu Skill",
            "nice_skills": "Bonus Skill",
            "seniority": "Kıdem",
            "title": "Pozisyon",
            "experience": "Deneyim",
            "education": "Eğitim",
            "location": "Lokasyon",
            "languages": "Diller",
            "certifications": "Sertifika",
        }
        cols = st.columns(5)
        for j, (key, label) in enumerate(labels.items()):
            cols[j % 5].metric(label, breakdown.get(key, 0))

        # Açıklamalar
        reasons = candidate.get("reasons", [])
        if reasons:
            st.write("**Eşleşme Açıklaması:**")
            for reason in reasons:
                icon = "✅" if "✓" in reason else ("❌" if "✗" in reason else "ℹ️")
                st.write(f"  {icon} {reason}")

        # Yetenekler
        skills = candidate.get("skills", [])
        if skills:
            st.write("**Yetenekler:**")
            st.markdown(" · ".join([f"`{s}`" for s in skills[:20]]))
            if len(skills) > 20:
                st.caption(f"... ve {len(skills) - 20} yetenek daha")

        # İletişim + CV İndirme
        st.write("**İletişim:**")
        contact_col, dl_col = st.columns([3, 1])
        with contact_col:
            st.write(
                f"📧 {candidate.get('email', '-')} · "
                f"📍 {candidate.get('location', '-')}"
            )
        with dl_col:
            candidate_id = candidate.get("candidate_id") or candidate.get("id")
            if candidate_id:
                try:
                    dl_response = requests.get(
                        f"{API_URL}/download-cv/{candidate_id}",
                        timeout=15,
                    )
                    if dl_response.status_code == 200:
                        # Dosya adını header'dan al
                        content_disp = dl_response.headers.get(
                            "Content-Disposition", ""
                        )
                        filename = f"{candidate.get('name', 'aday').replace(' ', '_')}_CV"
                        if "filename=" in content_disp:
                            filename = content_disp.split("filename=")[-1].strip('"')

                        st.download_button(
                            label="📥 CV İndir",
                            data=dl_response.content,
                            file_name=filename,
                            mime="application/octet-stream",
                            key=f"dl_{candidate_id}_{rank}",
                        )
                    else:
                        st.caption("CV yok")
                except Exception:
                    st.caption("CV erişilemiyor")


# ── Sayfa 1: CV Yükle ────────────────────────────────────────────────

@st.cache_resource
def _demo_matcher():
    from app.core.database import get_neo4j_driver
    from app.query.matcher import CandidateMatcher

    return CandidateMatcher(get_neo4j_driver())


@st.cache_resource
def _demo_nl_parser():
    from app.query.nl_parser import NLQueryParser

    return NLQueryParser()


@st.cache_resource
def _demo_pipeline():
    from app.extraction.pipeline import CVProcessingPipeline

    return CVProcessingPipeline()


def _search_local_neo4j(query: dict) -> list[dict]:
    from app.schemas.query import QuerySpec

    return _demo_matcher().search(QuerySpec(**query), limit=10)


def _nl_search_local_neo4j(nl_query: str) -> dict:
    query_spec = _demo_nl_parser().parse(nl_query)
    results = _demo_matcher().search(query_spec, limit=10)
    return {"parsed_query": query_spec.model_dump(), "results": results}


def _process_cv_local_hf(uploaded_file) -> dict | None:
    suffix = os.path.splitext(uploaded_file.name)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = temp_file.name
        temp_file.write(uploaded_file.getvalue())

    try:
        return _demo_pipeline().process(temp_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def page_upload():
    st.title("📄 CV Yükle")
    st.markdown(
        "CV dosyasını yükleyin. Sistem otomatik olarak bilgi çıkaracak, "
        "Knowledge Graph'e yazacak ve R2'ye yedekleyecektir."
    )

    uploaded_file = st.file_uploader(
        "PDF veya DOCX dosyası seçin",
        type=["pdf", "docx"],
        help="Maksimum 10 MB",
    )

    if uploaded_file and st.button("🚀 İşle", type="primary", use_container_width=True):
        with st.spinner("CV işleniyor... (LLM çıkarımı + KG yazma + Entity Resolution + Embedding)"):
            try:
                data = _process_cv_local_hf(uploaded_file)
                if data is None:
                    st.info("CV zaten sistemde kayitli veya islenemedi.")
                    return

                if data is not None:

                    # Duplicate kontrolü
                    if data is None:
                        st.info("⏭️ Bu CV zaten sistemde kayıtlı.")
                        return

                    st.success(f"✅ {data.get('candidate_name', 'Aday')} başarıyla işlendi!")

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Yetenekler", len(data.get("skills", [])))
                    col2.metric("Deneyimler", len(data.get("experiences", [])))
                    col3.metric("Eğitimler", len(data.get("educations", [])))
                    col4.metric("Sertifikalar", len(data.get("certifications", [])))

                    st.subheader("👤 Kişisel Bilgiler")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**İsim:** {data.get('candidate_name', '-')}")
                        st.write(f"**E-posta:** {data.get('email', '-')}")
                        st.write(f"**Telefon:** {data.get('phone', '-')}")
                    with c2:
                        st.write(f"**Konum:** {data.get('location', '-')}")
                        if data.get("languages"):
                            st.write(f"**Diller:** {', '.join(data['languages'])}")

                    if data.get("summary"):
                        st.info(data["summary"])

                    if data.get("experiences"):
                        st.subheader("💼 Deneyimler")
                        for exp in data["experiences"]:
                            current = " 🟢" if exp.get("is_current") else ""
                            with st.expander(
                                f"**{exp.get('role_title', '-')}** @ {exp.get('company_name', '-')} "
                                f"({exp.get('start_date', '?')} — {exp.get('end_date', 'Halen')}){current}"
                            ):
                                if exp.get("description"):
                                    st.write(exp["description"])
                                if exp.get("achievements"):
                                    st.write("**Başarılar:**")
                                    for a in exp["achievements"]:
                                        st.write(f"  • {a}")
                                if exp.get("skills_used"):
                                    st.markdown(
                                        " · ".join(f"`{s}`" for s in exp["skills_used"])
                                    )

                    if data.get("skills"):
                        st.subheader("🛠️ Yetenekler")
                        categories = {}
                        for s in data["skills"]:
                            cat = s.get("category", "Other")
                            years = f" ({s['years_experience']}y)" if s.get("years_experience") else ""
                            level = f" L{s['level']}" if s.get("level") else ""
                            categories.setdefault(cat, []).append(f"{s['name']}{years}{level}")

                        cols = st.columns(3)
                        for i, (cat, skills) in enumerate(sorted(categories.items())):
                            with cols[i % 3]:
                                st.write(f"**{cat}**")
                                for s in skills:
                                    st.write(f"  • {s}")

                    if data.get("educations"):
                        st.subheader("🎓 Eğitim")
                        for edu in data["educations"]:
                            gpa = f" — GPA: {edu['gpa']}" if edu.get("gpa") else ""
                            st.write(
                                f"• **{edu.get('degree', '-')}** — {edu.get('field', '-')} "
                                f"@ {edu.get('institution', '-')} "
                                f"({edu.get('start_year', '?')}-{edu.get('end_year', '?')}){gpa}"
                            )

                    if data.get("certifications"):
                        st.subheader("📜 Sertifikalar")
                        for cert in data["certifications"]:
                            st.write(f"  • {cert}")

                    with st.expander("📋 Ham JSON"):
                        st.json(data)

                else:
                    st.error(f"❌ Hata ({response.status_code}): {response.text}")

            except requests.exceptions.Timeout:
                st.error("⏱️ Zaman aşımı. Lütfen tekrar deneyin.")
            except requests.exceptions.ConnectionError:
                st.error("🔌 API'ye bağlanılamadı.")
            except Exception as e:
                st.error(f"❌ Hata: {e}")


# ── Sayfa 2: Form ile Aday Ara ────────────────────────────────────────

def page_search_legacy_old():
    st.title("🔎 Aday Ara")
    st.markdown("Kriterleri form ile girin, sistem en uygun adayları sıralayacaktır.")

    with st.form("search_form"):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Pozisyon", placeholder="Backend Developer")
            seniority = st.selectbox("Kıdem", [None, "junior", "mid", "senior", "lead"])
            must_skills = st.text_input("Zorunlu Yetenekler (virgülle ayır)", placeholder="Python, FastAPI, PostgreSQL")
            nice_skills = st.text_input("Tercih Edilen Yetenekler", placeholder="Docker, Kubernetes")
            min_exp = st.number_input("Minimum Deneyim (yıl)", 0, 30, 0)
        with col2:
            location = st.text_input("Lokasyon", placeholder="Istanbul")
            education = st.selectbox("Eğitim Seviyesi", [None, "bsc", "msc", "phd"])
            lang_code = st.text_input("Dil Gereksinimi", placeholder="English")
            lang_level = st.text_input("Minimum Dil Seviyesi", placeholder="B1")
            certifications = st.text_input("Sertifikalar", placeholder="AWS, CKA")

        free_text = st.text_area("Serbest Metin", placeholder="Fintech deneyimi olan, mikroservis mimarisi bilen...")
        submitted = st.form_submit_button("🔍 Ara", type="primary", use_container_width=True)

    if submitted:
        query = {
            "title": title or None,
            "seniority": seniority,
            "must_have_skills": [s.strip() for s in must_skills.split(",") if s.strip()] if must_skills else [],
            "nice_to_have_skills": [s.strip() for s in nice_skills.split(",") if s.strip()] if nice_skills else [],
            "min_experience_years": min_exp,
            "preferred_industries": [],
            "locations": [location] if location else [],
            "languages": [{"code": lang_code, "min_level": lang_level or "B1"}] if lang_code else [],
            "education_level": education,
            "must_have_certifications": [c.strip() for c in certifications.split(",") if c.strip()] if certifications else [],
            "free_text": free_text or None,
        }

        with st.spinner("Aday aranıyor..."):
            try:
                response = requests.post(
                    f"{API_URL}/search-candidates", json=query, timeout=30
                )
                if response.status_code == 200:
                    results = response.json()
                    if not results:
                        st.warning("Kriterlere uygun aday bulunamadı.")
                        return
                    st.success(f"✅ {len(results)} aday bulundu")
                    for i, candidate in enumerate(results, 1):
                        render_candidate_card(candidate, i, expanded=(i == 1))
                else:
                    st.error(f"❌ API hatası: {response.text}")
            except Exception as e:
                st.error(f"❌ Hata: {e}")


# ── Sayfa 3: Doğal Dil ile Aday Ara ─────────────────────────────────

def page_nl_search_legacy_old():
    st.title("💬 Doğal Dil ile Aday Ara")
    st.markdown(
        "İş ilanınızı veya arama kriterlerinizi **doğal dille** yazın. "
        "Sistem LLM kullanarak otomatik olarak yapısal kriterlere dönüştürür."
    )

    nl_query = st.text_area(
        "Arama metni",
        placeholder=(
            "Örnek: 5 yıl Python ve AWS deneyimi olan, "
            "Kubernetes bilen, İstanbul'da yaşayan senior backend mühendisi arıyoruz. "
            "Fintech sektöründe çalışmış olması tercih edilir."
        ),
        height=150,
    )

    if st.button("🔍 Ara", type="primary", use_container_width=True, key="nl_search_btn"):
        if not nl_query.strip():
            st.warning("Lütfen bir arama metni girin.")
            return

        with st.spinner("Sorgu analiz ediliyor ve adaylar aranıyor..."):
            try:
                response = requests.post(
                    f"{API_URL}/nl-search",
                    json={"query": nl_query},
                    timeout=60,
                )

                if response.status_code == 200:
                    data = response.json()
                    parsed = data.get("parsed_query", {})
                    results = data.get("results", [])

                    # Çözümlenen QuerySpec'i göster
                    with st.expander("🔧 Sistem Sorguyu Şöyle Anladı", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Pozisyon:** {parsed.get('title', '-')}")
                            st.write(f"**Kıdem:** {parsed.get('seniority', '-')}")
                            st.write(f"**Min. Deneyim:** {parsed.get('min_experience_years', 0)} yıl")
                            st.write(f"**Eğitim:** {parsed.get('education_level', '-')}")
                        with col2:
                            st.write(f"**Zorunlu Yetenekler:** {', '.join(parsed.get('must_have_skills', []))}")
                            st.write(f"**Tercih Edilen:** {', '.join(parsed.get('nice_to_have_skills', []))}")
                            st.write(f"**Lokasyon:** {', '.join(parsed.get('locations', []))}")
                            langs = parsed.get("languages", [])
                            if langs:
                                st.write(f"**Diller:** {', '.join(l.get('code', '') for l in langs)}")

                    # Sonuçlar
                    if not results:
                        st.warning("Kriterlere uygun aday bulunamadı.")
                        return

                    st.success(f"✅ {len(results)} aday bulundu")
                    for i, candidate in enumerate(results, 1):
                        render_candidate_card(candidate, i, expanded=(i == 1))

                else:
                    st.error(f"❌ API hatası: {response.text}")

            except requests.exceptions.Timeout:
                st.error("⏱️ Zaman aşımı. LLM analizi biraz uzun sürebilir, tekrar deneyin.")
            except requests.exceptions.ConnectionError:
                st.error("🔌 API'ye bağlanılamadı.")
            except Exception as e:
                st.error(f"❌ Hata: {e}")


# ── Sayfa 4: Bilgi Grafiği ───────────────────────────────────────────

def _render_search_results_state(state_key: str, has_run_key: str):
    if not st.session_state.get(has_run_key):
        return

    results = st.session_state.get(state_key, [])
    if not results:
        st.warning("Kriterlere uygun aday bulunamadi.")
        return

    st.success(f"{len(results)} aday bulundu")
    for i, candidate in enumerate(results, 1):
        render_candidate_card(candidate, i, expanded=(i == 1))


def page_search():
    st.title("Aday Ara")
    st.markdown("Kriterleri form ile girin, sistem en uygun adaylari siralayacaktir.")

    with st.form("search_form"):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Pozisyon", placeholder="Backend Developer")
            seniority = st.selectbox("Kidem", [None, "junior", "mid", "senior", "lead"])
            must_skills = st.text_input("Zorunlu Yetenekler (virgulle ayir)", placeholder="Python, FastAPI, PostgreSQL")
            nice_skills = st.text_input("Tercih Edilen Yetenekler", placeholder="Docker, Kubernetes")
            min_exp = st.number_input("Minimum Deneyim (yil)", 0, 30, 0)
        with col2:
            location = st.text_input("Lokasyon", placeholder="Istanbul")
            education = st.selectbox("Egitim Seviyesi", [None, "bsc", "msc", "phd"])
            lang_code = st.text_input("Dil Gereksinimi", placeholder="English")
            lang_level = st.text_input("Minimum Dil Seviyesi", placeholder="B1")
            certifications = st.text_input("Sertifikalar", placeholder="AWS, CKA")

        free_text = st.text_area("Serbest Metin", placeholder="Fintech deneyimi olan, mikroservis mimarisi bilen...")
        submitted = st.form_submit_button("Ara", type="primary", use_container_width=True)

    if submitted:
        query = {
            "title": title or None,
            "seniority": seniority,
            "must_have_skills": [s.strip() for s in must_skills.split(",") if s.strip()] if must_skills else [],
            "nice_to_have_skills": [s.strip() for s in nice_skills.split(",") if s.strip()] if nice_skills else [],
            "min_experience_years": min_exp,
            "preferred_industries": [],
            "locations": [location] if location else [],
            "languages": [{"code": lang_code, "min_level": lang_level or "B1"}] if lang_code else [],
            "education_level": education,
            "must_have_certifications": [c.strip() for c in certifications.split(",") if c.strip()] if certifications else [],
            "free_text": free_text or None,
        }

        with st.spinner("Aday araniyor..."):
            try:
                st.session_state["search_results"] = _search_local_neo4j(query)
                st.session_state["search_has_run"] = True
            except Exception as e:
                st.error(f"Hata: {e}")

    _render_search_results_state("search_results", "search_has_run")


def _render_nl_parsed_query(parsed: dict):
    with st.expander("Sistem Sorguyu Boyle Anladi", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Pozisyon:** {parsed.get('title', '-')}")
            st.write(f"**Kidem:** {parsed.get('seniority', '-')}")
            st.write(f"**Min. Deneyim:** {parsed.get('min_experience_years', 0)} yil")
            st.write(f"**Egitim:** {parsed.get('education_level', '-')}")
        with col2:
            st.write(f"**Zorunlu Yetenekler:** {', '.join(parsed.get('must_have_skills', []))}")
            st.write(f"**Tercih Edilen:** {', '.join(parsed.get('nice_to_have_skills', []))}")
            st.write(f"**Lokasyon:** {', '.join(parsed.get('locations', []))}")
            langs = parsed.get("languages", [])
            if langs:
                st.write(f"**Diller:** {', '.join(l.get('code', '') for l in langs)}")


def page_nl_search():
    st.title("Dogal Dil ile Aday Ara")
    st.markdown(
        "Is ilanini veya arama kriterlerini dogal dille yazin. "
        "Sistem LLM kullanarak yapisal kriterlere donusturur."
    )

    nl_query = st.text_area(
        "Arama metni",
        placeholder=(
            "Ornek: 5 yil Python ve AWS deneyimi olan, Kubernetes bilen, "
            "Istanbul'da yasayan senior backend muhendisi ariyoruz."
        ),
        height=150,
    )

    if st.button("Ara", type="primary", use_container_width=True, key="nl_search_btn"):
        if not nl_query.strip():
            st.warning("Lutfen bir arama metni girin.")
            return

        with st.spinner("Sorgu analiz ediliyor ve adaylar araniyor..."):
            try:
                data = _nl_search_local_neo4j(nl_query)
                st.session_state["nl_parsed"] = data.get("parsed_query", {})
                st.session_state["nl_results"] = data.get("results", [])
                st.session_state["nl_has_run"] = True

            except requests.exceptions.Timeout:
                st.error("Zaman asimi. LLM analizi biraz uzun surebilir, tekrar deneyin.")
            except requests.exceptions.ConnectionError:
                st.error("API'ye baglanilamadi.")
            except Exception as e:
                st.error(f"Hata: {e}")

    if st.session_state.get("nl_has_run"):
        _render_nl_parsed_query(st.session_state.get("nl_parsed", {}))
        _render_search_results_state("nl_results", "nl_has_run")


def page_graph():
    st.title("🕸️ Bilgi Grafiği")
    st.markdown("Neo4j'deki Knowledge Graph'in interaktif görselleştirmesi.")

    try:
        from neo4j import GraphDatabase

        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password123")
        driver = GraphDatabase.driver(uri, auth=(user, password))

        with driver.session() as session:
            stats = session.run(
                "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC"
            )
            stat_data = [r.data() for r in stats]

        st.subheader("📊 Graf İstatistikleri")
        cols = st.columns(min(len(stat_data), 6))
        for i, s in enumerate(stat_data[:6]):
            cols[i].metric(s["label"], s["count"])

        view = st.selectbox("Görünüm", [
            "Tüm adaylar ve yetenekleri",
            "Tek aday detayı",
            "Şirket bağlantıları",
        ])

        if view == "Tüm adaylar ve yetenekleri":
            query = """
                MATCH (c:Candidate)-[r:HAS_SKILL]->(s:Skill)
                RETURN c.name AS source, 'HAS_SKILL' AS rel, s.name AS target,
                       'Candidate' AS source_type, 'Skill' AS target_type
                LIMIT 100
            """
        elif view == "Tek aday detayı":
            with driver.session() as session:
                names = [r["name"] for r in session.run("MATCH (c:Candidate) RETURN c.name AS name")]
            if not names:
                st.warning("Henüz aday yok.")
                driver.close()
                return
            selected = st.selectbox("Aday seçin", names)
            query = f"""
                MATCH (c:Candidate {{name: '{selected}'}})-[r]->(n)
                RETURN c.name AS source, type(r) AS rel,
                       coalesce(n.name, n.role_title, n.degree) AS target,
                       'Candidate' AS source_type, labels(n)[0] AS target_type
            """
        else:
            query = """
                MATCH (c:Candidate)-[:HAS_EXPERIENCE]->(e:Experience)-[:AT_COMPANY]->(co:Company)
                RETURN c.name AS source, 'WORKED_AT' AS rel, co.name AS target,
                       'Candidate' AS source_type, 'Company' AS target_type
                LIMIT 100
            """

        with driver.session() as session:
            edges = [r.data() for r in session.run(query)]
        driver.close()

        if not edges:
            st.warning("Gösterilecek veri yok.")
            return

        color_map = {
            "Candidate": "#9b59b6", "Skill": "#e67e22",
            "Experience": "#3498db", "Company": "#95a5a6",
            "Education": "#e74c3c", "Institution": "#2ecc71",
            "Language": "#f39c12", "Certification": "#1abc9c",
        }

        net = Network(height="600px", width="100%", bgcolor="#0E1117", font_color="white")
        net.barnes_hut(gravity=-5000, central_gravity=0.3, spring_length=100)

        added = set()
        for edge in edges:
            for node, ntype in [(edge["source"], edge["source_type"]),
                                (edge["target"], edge["target_type"])]:
                if node and node not in added:
                    net.add_node(
                        node, label=node,
                        color=color_map.get(ntype, "#888"),
                        size=25 if ntype == "Candidate" else 15,
                        title=f"{ntype}: {node}",
                    )
                    added.add(node)
            if edge["source"] and edge["target"]:
                net.add_edge(edge["source"], edge["target"], title=edge.get("rel", ""))

        with tmp_module.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            net.save_graph(f.name)
            with open(f.name) as rf:
                html = rf.read()
            st.components.v1.html(html, height=620)
            os.unlink(f.name)

        cols = st.columns(len(color_map))
        for i, (label, color) in enumerate(color_map.items()):
            cols[i].markdown(f"<span style='color:{color}'>●</span> {label}", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Bağlantı hatası: {e}")


# ── Sayfa 5: Entity Resolution ────────────────────────────────────────

def page_er():
    st.title("🔗 Entity Resolution")
    st.markdown("Knowledge Graph'teki duplicate düğümleri birleştirir.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Sinonim Sözlüğü")
        st.markdown("- K8s → Kubernetes\n- JS → JavaScript\n- ML → Machine Learning\n- Agile/Scrum → Agile")
    with col2:
        st.subheader("Fuzzy Matching")
        st.markdown("- React.js ≈ React\n- PostgreSQL ≈ Postgres\n- Kısa isimler (< 4 kar.) atlanır")

    st.divider()

    if st.button("🔗 Çalıştır", type="primary", use_container_width=True):
        with st.spinner("Duplicate düğümler taranıyor..."):
            try:
                response = requests.post(f"{API_URL}/resolve-entities", timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    total = sum(data.get("merged", {}).values())
                    if total > 0:
                        st.success(f"✅ {total} düğüm birleştirildi!")
                        for key, count in data["merged"].items():
                            if count > 0:
                                st.write(f"  • **{key}**: {count}")
                    else:
                        st.info("ℹ️ Duplicate bulunamadı, graf temiz.")
                else:
                    st.error(f"❌ Hata: {response.text}")
            except Exception as e:
                st.error(f"❌ Hata: {e}")


# ── Router ────────────────────────────────────────────────────────────

if page == "📄 CV Yükle":
    page_upload()
elif page == "🔎 Aday Ara":
    page_search()
elif page == "💬 Doğal Dil Ara":
    page_nl_search()
elif page == "🕸️ Bilgi Grafiği":
    page_graph()
elif page == "🔗 Entity Resolution":
    page_er()
