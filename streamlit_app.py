"""
TalentForge — Streamlit Frontend MVP
CV yükleme, aday arama, bilgi grafiği görselleştirme
"""

import streamlit as st
import requests
import json
from pyvis.network import Network
import tempfile
import os

# ── Ayarlar ───────────────────────────────────────────────────────────

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
    ["📄 CV Yükle", "🔎 Aday Ara", "🕸️ Bilgi Grafiği", "🔗 Entity Resolution"],
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


# ── Sayfa 1: CV Yükle ────────────────────────────────────────────────

def page_upload():
    st.title("📄 CV Yükle")
    st.markdown("CV dosyasını yükleyin, sistem otomatik olarak bilgi çıkaracak ve Knowledge Graph'e yazacaktır.")

    uploaded_file = st.file_uploader(
        "PDF veya DOCX dosyası seçin",
        type=["pdf", "docx"],
        help="Maksimum 10 MB"
    )

    if uploaded_file and st.button("🚀 İşle", type="primary", use_container_width=True):
        with st.spinner("CV işleniyor... (LLM çıkarımı + KG yazma + Entity Resolution)"):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                response = requests.post(f"{API_URL}/upload-cv", files=files, timeout=300)

                if response.status_code == 200:
                    data = response.json()
                    st.success(f"✅ {data.get('candidate_name', 'Aday')} başarıyla işlendi!")

                    # Özet kartlar
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Yetenekler", len(data.get("skills", [])))
                    col2.metric("Deneyimler", len(data.get("experiences", [])))
                    col3.metric("Eğitimler", len(data.get("educations", [])))
                    col4.metric("Sertifikalar", len(data.get("certifications", [])))

                    # Kişisel bilgiler
                    st.subheader("👤 Kişisel Bilgiler")
                    info_col1, info_col2 = st.columns(2)
                    with info_col1:
                        st.write(f"**İsim:** {data.get('candidate_name', '-')}")
                        st.write(f"**E-posta:** {data.get('email', '-')}")
                        st.write(f"**Telefon:** {data.get('phone', '-')}")
                    with info_col2:
                        st.write(f"**Konum:** {data.get('location', '-')}")
                        if data.get("languages"):
                            st.write(f"**Diller:** {', '.join(data['languages'])}")

                    if data.get("summary"):
                        st.info(data["summary"])

                    # Deneyimler
                    if data.get("experiences"):
                        st.subheader("💼 Deneyimler")
                        for exp in data["experiences"]:
                            current = " 🟢 Devam ediyor" if exp.get("is_current") else ""
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
                                    st.write("**Kullanılan Yetenekler:**")
                                    skill_text = " · ".join(
                                        [f"`{s}`" for s in exp["skills_used"]]
                                    )
                                    st.markdown(skill_text)

                    # Yetenekler
                    if data.get("skills"):
                        st.subheader("🛠️ Yetenekler")
                        skill_cols = st.columns(3)
                        categories = {}
                        for s in data["skills"]:
                            cat = s.get("category", "Other")
                            if cat not in categories:
                                categories[cat] = []
                            years = f" ({s['years_experience']}y)" if s.get("years_experience") else ""
                            level = f" L{s['level']}" if s.get("level") else ""
                            categories[cat].append(f"{s['name']}{years}{level}")

                        for i, (cat, skills) in enumerate(sorted(categories.items())):
                            with skill_cols[i % 3]:
                                st.write(f"**{cat}**")
                                for s in skills:
                                    st.write(f"  • {s}")

                    # Eğitim
                    if data.get("educations"):
                        st.subheader("🎓 Eğitim")
                        for edu in data["educations"]:
                            gpa = f" — GPA: {edu['gpa']}" if edu.get("gpa") else ""
                            st.write(
                                f"• **{edu.get('degree', '-')}** — {edu.get('field', '-')} "
                                f"@ {edu.get('institution', '-')} "
                                f"({edu.get('start_year', '?')}-{edu.get('end_year', '?')}){gpa}"
                            )

                    # Sertifikalar
                    if data.get("certifications"):
                        st.subheader("📜 Sertifikalar")
                        for cert in data["certifications"]:
                            st.write(f"  • {cert}")

                    # Ham JSON
                    with st.expander("📋 Ham JSON Çıktısı"):
                        st.json(data)

                else:
                    st.error(f"❌ Hata: {response.text}")

            except requests.exceptions.Timeout:
                st.error("⏱️ İstek zaman aşımına uğradı. Lütfen tekrar deneyin.")
            except requests.exceptions.ConnectionError:
                st.error("🔌 API'ye bağlanılamadı. FastAPI sunucusunun çalıştığından emin olun.")
            except Exception as e:
                st.error(f"❌ Beklenmeyen hata: {e}")


# ── Sayfa 2: Aday Ara ────────────────────────────────────────────────

def page_search():
    st.title("🔎 Aday Ara")
    st.markdown("Pozisyon kriterlerinizi girin, sistem en uygun adayları sıralayacaktır.")

    with st.form("search_form"):
        col1, col2 = st.columns(2)

        with col1:
            title = st.text_input("Pozisyon", placeholder="Backend Developer")
            seniority = st.selectbox("Kıdem", [None, "junior", "mid", "senior", "lead"])
            must_skills = st.text_input(
                "Zorunlu Yetenekler (virgülle ayır)",
                placeholder="Python, FastAPI, PostgreSQL"
            )
            nice_skills = st.text_input(
                "Tercih Edilen Yetenekler",
                placeholder="Docker, Kubernetes"
            )
            min_exp = st.number_input("Minimum Deneyim (yıl)", 0, 30, 0)

        with col2:
            location = st.text_input("Lokasyon", placeholder="Istanbul")
            education = st.selectbox("Eğitim Seviyesi", [None, "bsc", "msc", "phd"])
            lang_code = st.text_input("Dil Gereksinimi", placeholder="English")
            lang_level = st.text_input("Minimum Dil Seviyesi", placeholder="B1")
            certifications = st.text_input(
                "Sertifikalar",
                placeholder="AWS, CKA"
            )

        free_text = st.text_area(
            "Serbest Metin (ek açıklama)",
            placeholder="Fintech deneyimi olan, mikroservis mimarisi bilen..."
        )

        submitted = st.form_submit_button("🔍 Ara", type="primary", use_container_width=True)

    if submitted:
        # QuerySpec oluştur
        query = {
            "title": title or None,
            "seniority": seniority,
            "must_have_skills": [s.strip() for s in must_skills.split(",") if s.strip()] if must_skills else [],
            "nice_to_have_skills": [s.strip() for s in nice_skills.split(",") if s.strip()] if nice_skills else [],
            "min_experience_years": min_exp if min_exp > 0 else 0,
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
                    f"{API_URL}/search-candidates",
                    json=query,
                    timeout=30
                )

                if response.status_code == 200:
                    results = response.json()

                    if not results:
                        st.warning("🔍 Kriterlere uygun aday bulunamadı.")
                        return

                    st.success(f"✅ {len(results)} aday bulundu")

                    for i, candidate in enumerate(results, 1):
                        score = candidate.get("total_score", 0)

                        # Skor rengini belirle
                        if score >= 70:
                            score_color = "🟢"
                        elif score >= 40:
                            score_color = "🟡"
                        else:
                            score_color = "🔴"

                        with st.expander(
                            f"{score_color} **#{i} {candidate.get('name', '-')}** — "
                            f"Skor: {score}/100 — "
                            f"{candidate.get('experience_count', 0)} deneyim",
                            expanded=(i == 1)
                        ):
                            # Skor kırılımı
                            st.write("**Skor Kırılımı:**")
                            breakdown = candidate.get("score_breakdown", {})
                            score_cols = st.columns(5)
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
                            for j, (key, label) in enumerate(labels.items()):
                                val = breakdown.get(key, 0)
                                score_cols[j % 5].metric(label, f"{val}")

                            # Açıklamalar
                            reasons = candidate.get("reasons", [])
                            if reasons:
                                st.write("**Eşleşme Açıklaması:**")
                                for reason in reasons:
                                    if "✓" in reason:
                                        st.write(f"  ✅ {reason}")
                                    elif "✗" in reason:
                                        st.write(f"  ❌ {reason}")
                                    else:
                                        st.write(f"  ℹ️ {reason}")

                            # Yetenekler
                            skills = candidate.get("skills", [])
                            if skills:
                                st.write("**Yetenekler:**")
                                st.markdown(" · ".join([f"`{s}`" for s in skills[:20]]))
                                if len(skills) > 20:
                                    st.caption(f"... ve {len(skills) - 20} yetenek daha")

                            # İletişim
                            st.write("**İletişim:**")
                            st.write(
                                f"📧 {candidate.get('email', '-')} · "
                                f"📍 {candidate.get('location', '-')}"
                            )

                else:
                    st.error(f"❌ API hatası: {response.text}")

            except requests.exceptions.ConnectionError:
                st.error("🔌 API'ye bağlanılamadı.")
            except Exception as e:
                st.error(f"❌ Hata: {e}")


# ── Sayfa 3: Bilgi Grafiği ───────────────────────────────────────────

def page_graph():
    st.title("🕸️ Bilgi Grafiği")
    st.markdown("Neo4j'deki Knowledge Graph'in interaktif görselleştirmesi.")

    # Neo4j'den veri çek
    try:
        from neo4j import GraphDatabase

        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password123")

        driver = GraphDatabase.driver(uri, auth=(user, password))

        with driver.session() as session:
            # İstatistikler
            stats = session.run("""
                MATCH (n)
                RETURN labels(n)[0] AS label, count(n) AS count
                ORDER BY count DESC
            """)
            stat_data = [r.data() for r in stats]

        # Metrik kartlar
        st.subheader("📊 Graf İstatistikleri")
        cols = st.columns(min(len(stat_data), 6))
        for i, s in enumerate(stat_data[:6]):
            cols[i].metric(s["label"], s["count"])

        # Görselleştirme seçenekleri
        st.subheader("🎯 Görselleştirme")
        view = st.selectbox(
            "Görünüm",
            [
                "Tüm adaylar ve yetenekleri",
                "Tek aday detayı",
                "Skill ağı (ortak yetenekler)",
            ]
        )

        if view == "Tüm adaylar ve yetenekleri":
            query = """
                MATCH (c:Candidate)-[r:HAS_SKILL]->(s:Skill)
                RETURN c.name AS source, 'HAS_SKILL' AS rel, s.name AS target,
                       'Candidate' AS source_type, 'Skill' AS target_type
                LIMIT 100
            """
        elif view == "Tek aday detayı":
            with driver.session() as session:
                candidates = session.run("MATCH (c:Candidate) RETURN c.name AS name")
                names = [r["name"] for r in candidates]

            if not names:
                st.warning("Henüz aday yok.")
                driver.close()
                return

            selected = st.selectbox("Aday seçin", names)
            query = f"""
                MATCH (c:Candidate {{name: '{selected}'}})-[r]->(n)
                OPTIONAL MATCH (n)-[r2]->(m)
                WITH c.name AS source, type(r) AS rel, 
                     coalesce(n.name, n.role_title, n.degree) AS target,
                     labels(c)[0] AS source_type, labels(n)[0] AS target_type,
                     m, r2
                WHERE target IS NOT NULL
                RETURN source, rel, target, source_type, target_type
                UNION
                MATCH (c:Candidate {{name: '{selected}'}})-[]->(n)-[r2]->(m)
                WHERE m IS NOT NULL
                RETURN coalesce(n.name, n.role_title, n.degree) AS source, 
                       type(r2) AS rel,
                       m.name AS target,
                       labels(n)[0] AS source_type, labels(m)[0] AS target_type
            """
        else:
            query = """
                MATCH (c1:Candidate)-[:HAS_SKILL]->(s:Skill)<-[:HAS_SKILL]-(c2:Candidate)
                WHERE id(c1) < id(c2)
                RETURN c1.name AS source, s.name AS rel, c2.name AS target,
                       'Candidate' AS source_type, 'Candidate' AS target_type
                LIMIT 50
            """

        with driver.session() as session:
            result = session.run(query)
            edges = [r.data() for r in result]

        driver.close()

        if not edges:
            st.warning("Gösterilecek veri yok.")
            return

        # PyVis graf oluştur
        net = Network(height="600px", width="100%", bgcolor="#0E1117", font_color="white")
        net.barnes_hut(gravity=-5000, central_gravity=0.3, spring_length=100)

        # Renk haritası
        color_map = {
            "Candidate": "#9b59b6",
            "Skill": "#e67e22",
            "Experience": "#3498db",
            "Company": "#95a5a6",
            "Education": "#e74c3c",
            "Institution": "#2ecc71",
            "Language": "#f39c12",
            "Certification": "#1abc9c",
        }

        added_nodes = set()
        for edge in edges:
            src = edge["source"]
            tgt = edge["target"]
            src_type = edge.get("source_type", "Other")
            tgt_type = edge.get("target_type", "Other")

            if src and src not in added_nodes:
                net.add_node(
                    src, label=src,
                    color=color_map.get(src_type, "#888"),
                    size=25 if src_type == "Candidate" else 15,
                    title=f"{src_type}: {src}"
                )
                added_nodes.add(src)

            if tgt and tgt not in added_nodes:
                net.add_node(
                    tgt, label=tgt,
                    color=color_map.get(tgt_type, "#888"),
                    size=25 if tgt_type == "Candidate" else 15,
                    title=f"{tgt_type}: {tgt}"
                )
                added_nodes.add(tgt)

            if src and tgt:
                net.add_edge(src, tgt, title=edge.get("rel", ""))

        # HTML olarak render et
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            net.save_graph(f.name)
            f.seek(0)
            with open(f.name, "r") as rf:
                html = rf.read()
            st.components.v1.html(html, height=620, scrolling=False)
            os.unlink(f.name)

        # Renk açıklaması
        legend_cols = st.columns(len(color_map))
        for i, (label, color) in enumerate(color_map.items()):
            legend_cols[i].markdown(
                f"<span style='color:{color}'>●</span> {label}",
                unsafe_allow_html=True
            )

    except ImportError:
        st.error("neo4j ve pyvis kütüphaneleri gerekli: `pip install neo4j pyvis`")
    except Exception as e:
        st.error(f"❌ Neo4j bağlantı hatası: {e}")


# ── Sayfa 4: Entity Resolution ────────────────────────────────────────

def page_er():
    st.title("🔗 Entity Resolution")
    st.markdown(
        "Knowledge Graph'teki duplicate düğümleri birleştirir. "
        "Örneğin 'Kubernetes' ve 'K8s' aynı skill düğümüne dönüştürülür."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Sinonim Sözlüğü")
        st.markdown(
            "Bilinen eşdeğerler otomatik birleştirilir:\n"
            "- K8s → Kubernetes\n"
            "- JS → JavaScript\n"
            "- ML → Machine Learning\n"
            "- Agile/Scrum → Agile\n"
            "- Garanti BBVA Teknoloji → Garanti BBVA"
        )

    with col2:
        st.subheader("Fuzzy Matching")
        st.markdown(
            "Benzer isimler rapidfuzz ile tespit edilir:\n"
            "- React.js ≈ React (skor > 85)\n"
            "- PostgreSQL ≈ Postgres\n"
            "- Kısa isimler (< 4 karakter) atlanır"
        )

    st.divider()

    if st.button("🔗 Entity Resolution Çalıştır", type="primary", use_container_width=True):
        with st.spinner("Duplicate düğümler taranıyor..."):
            try:
                response = requests.post(f"{API_URL}/resolve-entities", timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    merged = data.get("merged", {})
                    total = sum(merged.values())

                    if total > 0:
                        st.success(f"✅ {total} düğüm birleştirildi!")
                        for key, count in merged.items():
                            if count > 0:
                                st.write(f"  • **{key}**: {count} birleştirme")
                    else:
                        st.info("ℹ️ Duplicate düğüm bulunamadı, graf temiz.")
                else:
                    st.error(f"❌ Hata: {response.text}")

            except requests.exceptions.ConnectionError:
                st.error("🔌 API'ye bağlanılamadı.")
            except Exception as e:
                st.error(f"❌ Hata: {e}")


# ── Router ────────────────────────────────────────────────────────────

if page == "📄 CV Yükle":
    page_upload()
elif page == "🔎 Aday Ara":
    page_search()
elif page == "🕸️ Bilgi Grafiği":
    page_graph()
elif page == "🔗 Entity Resolution":
    page_er()