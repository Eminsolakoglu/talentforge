"""
Entity Resolution — KG'deki duplicate düğümleri birleştirir.

Üç aşamalı çözümleme:
  1. Sinonim Sözlüğü: Bilinen eşdeğerleri birleştirir (K8s → Kubernetes)
  2. Fuzzy Matching: Benzer isimleri rapidfuzz ile tespit eder (React.js ≈ React)
  3. Neo4j MERGE: Duplicate düğümleri ve ilişkilerini birleştirir

APOC bağımlılığı YOK — saf Cypher ile çalışır.

Kullanım:
  resolver = EntityResolver(neo4j_driver)
  stats = resolver.resolve_all()
"""

import logging
from typing import Dict, List, Tuple, Set
from neo4j import Driver

logger = logging.getLogger(__name__)


# ── Sinonim Sözlükleri ────────────────────────────────────────────────

SKILL_SYNONYMS: Dict[str, List[str]] = {
    # Programlama dilleri
    "JavaScript":       ["JS", "Javascript", "javascript", "Java Script"],
    "TypeScript":       ["TS", "Typescript", "typescript"],
    "Python":           ["python", "Python3", "python3"],
    "C#":               ["CSharp", "C Sharp", "c#", "csharp"],

    # Frameworks
    "React":            ["React.js", "ReactJS", "Reactjs", "react.js"],
    "Next.js":          ["NextJS", "Nextjs", "next.js"],
    "Vue":              ["Vue.js", "VueJS", "Vuejs", "vue.js"],
    "Angular":          ["AngularJS", "Angular.js", "angular"],
    "Node.js":          ["NodeJS", "Nodejs", "node.js"],
    "Express":          ["Express.js", "ExpressJS", "express.js"],
    ".NET Core":        ["dotnet", "DotNet", ".Net Core", "ASP.NET"],
    "Spring Boot":      ["SpringBoot", "spring boot"],
    "FastAPI":          ["fastapi", "Fast API"],

    # Veritabanı
    "PostgreSQL":       ["Postgres", "postgres", "PSQL", "psql"],
    "MongoDB":          ["Mongo", "mongo", "MongoDb"],
    "MySQL":            ["mysql", "MySql"],
    "Oracle DB":        ["Oracle", "OracleDB", "Oracle Database"],
    "Elasticsearch":    ["ElasticSearch", "Elastic Search", "elastic"],
    "Redis":            ["redis"],

    # DevOps & Cloud
    "Kubernetes":       ["K8s", "k8s", "Kubernetes (K8s)", "kubernetes"],
    "Docker":           ["docker"],
    "AWS":              ["Amazon Web Services", "aws", "AWS (EKS, RDS, SQS, Lambda)"],
    "Google Cloud":     ["GCP", "Google Cloud Platform", "gcp"],
    "Azure":            ["Microsoft Azure", "azure"],
    "Jenkins":          ["jenkins"],
    "GitHub Actions":   ["Github Actions", "GH Actions", "github actions"],
    "Terraform":        ["terraform"],
    "ArgoCD":           ["Argo CD", "argocd"],
    "CI/CD":            ["CICD", "CI CD", "ci/cd"],

    # Data Science
    "Machine Learning": ["ML", "ml", "Makine Öğrenmesi", "makine öğrenmesi"],
    "Deep Learning":    ["DL", "dl", "Derin Öğrenme", "derin öğrenme"],
    "Pandas":           ["pandas"],
    "NumPy":            ["Numpy", "numpy"],

    # Araçlar
    "Git":              ["git"],
    "Jira":             ["jira", "JIRA"],
    "DataDog":          ["Datadog", "datadog"],
    "Kafka":            ["Apache Kafka", "apache kafka", "kafka"],
    "RabbitMQ":         ["Rabbit MQ", "rabbitmq"],

    # Soft Skills
    "Leadership":       ["Team Leadership", "Takım Liderliği", "Teknik Liderlik", "liderlik"],
    "Mentoring":        ["Mentorluk", "mentorluk", "Mentorship"],
    "Agile":            ["Agile/Scrum", "agile"],
    "Scrum":            ["scrum", "Scrum Master"],
    "Project Management": ["Proje Yönetimi", "proje yönetimi"],

    # Domain / Mimari
    "Microservices":    ["Mikroservis", "Mikroservis Mimarisi", "mikroservis", "Microservice"],
    "Event-Driven Architecture": ["Event-Driven", "Event Driven Architecture", "event-driven"],
}

COMPANY_SYNONYMS: Dict[str, List[str]] = {
    "Garanti BBVA":     ["Garanti BBVA Teknoloji", "Garanti Bankası", "Garanti"],
    "Trendyol":         ["Trendyol Teknoloji", "Trendyol Group"],
    "Turkcell":         ["Turkcell Teknoloji", "Turkcell İletişim"],
    "İş Bankası":       ["Türkiye İş Bankası", "İşbank"],
    "Akbank":           ["Akbank T.A.Ş.", "Akbank Teknoloji"],
    "Yapı Kredi":       ["Yapı ve Kredi Bankası", "Yapı Kredi Teknoloji"],
    "Hepsiburada":      ["Hepsiburada Teknoloji", "D-Market"],
    "Getir":            ["Getir Teknoloji"],
    "Papara":           ["Papara Teknoloji", "Papara Elektronik Para"],
}


def _normalize(text: str) -> str:
    """Karşılaştırma için normalize"""
    for k, v in {"İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s",
                 "Ğ": "g", "ğ": "g", "Ü": "u", "ü": "u", "Ö": "o",
                 "ö": "o", "Ç": "c", "ç": "c"}.items():
        text = text.replace(k, v)
    return text.lower().strip()


# ── Ana sınıf ─────────────────────────────────────────────────────────

class EntityResolver:
    """
    KG'deki duplicate düğümleri tespit edip birleştirir.

    Kullanım:
        resolver = EntityResolver(driver)
        stats = resolver.resolve_all()
    """

    def __init__(self, driver: Driver, fuzzy_threshold: int = 85):
        self.driver = driver
        self.fuzzy_threshold = fuzzy_threshold

    def resolve_all(self) -> Dict[str, int]:
        """Tüm entity tiplerini çözümler"""
        logger.info("🔍 Entity Resolution başlatılıyor...")

        stats = {
            "skills_synonym": self._resolve_synonyms("Skill", SKILL_SYNONYMS),
            "companies_synonym": self._resolve_synonyms("Company", COMPANY_SYNONYMS),
            "skills_fuzzy": self._resolve_fuzzy("Skill"),
            "companies_fuzzy": self._resolve_fuzzy("Company"),
        }

        total = sum(stats.values())
        logger.info(f"✅ Entity Resolution tamamlandı — {total} birleştirme: {stats}")
        return stats

    # ── Sinonim çözümleme ─────────────────────────────────────────────

    def _resolve_synonyms(self, label: str, synonyms: Dict[str, List[str]]) -> int:
        """Sinonim sözlüğüne göre düğümleri birleştirir"""
        merged_count = 0

        with self.driver.session() as session:
            for canonical, aliases in synonyms.items():
                for alias in aliases:
                    if alias == canonical:
                        continue

                    # Alias düğümü var mı kontrol et
                    check = session.run(f"""
                        MATCH (a:{label} {{name: $alias}})
                        RETURN count(a) AS cnt
                    """, alias=alias)

                    if check.single()["cnt"] > 0:
                        # Canonical düğümü yoksa oluştur
                        session.run(f"""
                            MERGE (:{label} {{name: $canonical}})
                        """, canonical=canonical)

                        # Birleştir
                        self._merge_nodes(session, label, alias, canonical)
                        merged_count += 1
                        logger.info(f"  🔗 {label}: '{alias}' → '{canonical}'")

        return merged_count

    # ── Fuzzy çözümleme ───────────────────────────────────────────────

    def _resolve_fuzzy(self, label: str) -> int:
        """rapidfuzz ile benzer isimleri tespit edip birleştirir"""
        try:
            from rapidfuzz import fuzz
        except ImportError:
            logger.warning("⚠️ rapidfuzz yüklü değil, fuzzy matching atlanıyor")
            return 0

        # Tüm düğüm isimlerini çek
        with self.driver.session() as session:
            result = session.run(f"MATCH (n:{label}) RETURN n.name AS name")
            names = [r["name"] for r in result if r["name"]]

        if len(names) < 2:
            return 0

        # Benzer çiftleri bul
        resolved: Set[str] = set()
        merge_pairs: List[Tuple[str, str]] = []

        for i, name1 in enumerate(names):
            if name1 in resolved:
                continue
            for name2 in names[i + 1:]:
                if name2 in resolved:
                    continue

                n1 = _normalize(name1)
                n2 = _normalize(name2)

                # Tam eşleşme (sadece case/Türkçe karakter farkı)
                if n1 == n2:
                    shorter = name1 if len(name1) <= len(name2) else name2
                    longer = name2 if shorter == name1 else name1
                    merge_pairs.append((longer, shorter))
                    resolved.add(longer)
                    continue

                # Çok kısa isimlerde fuzzy match tehlikeli (JS ≈ C# gibi)
                if len(n1) < 4 or len(n2) < 4:
                    continue

                # Fuzzy eşleşme
                score = fuzz.ratio(n1, n2)
                if score >= self.fuzzy_threshold:
                    shorter = name1 if len(name1) <= len(name2) else name2
                    longer = name2 if shorter == name1 else name1
                    merge_pairs.append((longer, shorter))
                    resolved.add(longer)

        # Birleştir
        merged_count = 0
        with self.driver.session() as session:
            for from_name, to_name in merge_pairs:
                self._merge_nodes(session, label, from_name, to_name)
                merged_count += 1
                logger.info(f"  🔗 {label} (fuzzy): '{from_name}' → '{to_name}'")

        return merged_count

    # ── Düğüm birleştirme ─────────────────────────────────────────────

    def _merge_nodes(self, session, label: str, from_name: str, to_name: str):
        """
        from_name düğümünün tüm ilişkilerini to_name'e taşır,
        sonra from_name düğümünü siler. APOC gerektirmez.
        """
        if label == "Skill":
            self._merge_skill(session, from_name, to_name)
        elif label == "Company":
            self._merge_company(session, from_name, to_name)
        else:
            self._merge_generic(session, label, from_name, to_name)

    def _merge_skill(self, session, from_name: str, to_name: str):
        """Skill düğümlerini birleştirir — HAS_SKILL ve USED_SKILL ilişkilerini taşır"""
        # HAS_SKILL ilişkilerini taşı (Candidate → Skill)
        session.run("""
            MATCH (c:Candidate)-[old:HAS_SKILL]->(from:Skill {name: $from_name})
            MERGE (to:Skill {name: $to_name})
            MERGE (c)-[new:HAS_SKILL]->(to)
            SET new.years_experience = coalesce(new.years_experience, old.years_experience),
                new.level = coalesce(new.level, old.level),
                new.confidence = coalesce(new.confidence, old.confidence),
                new.category = coalesce(new.category, old.category)
            DELETE old
        """, from_name=from_name, to_name=to_name)

        # USED_SKILL ilişkilerini taşı (Experience → Skill)
        session.run("""
            MATCH (e:Experience)-[old:USED_SKILL]->(from:Skill {name: $from_name})
            MERGE (to:Skill {name: $to_name})
            MERGE (e)-[:USED_SKILL]->(to)
            DELETE old
        """, from_name=from_name, to_name=to_name)

        # Eski düğümü sil
        session.run("""
            MATCH (from:Skill {name: $from_name})
            WHERE NOT exists((from)--())
            DELETE from
        """, from_name=from_name)

    def _merge_company(self, session, from_name: str, to_name: str):
        """Company düğümlerini birleştirir — AT_COMPANY ilişkilerini taşır"""
        session.run("""
            MATCH (e:Experience)-[old:AT_COMPANY]->(from:Company {name: $from_name})
            MERGE (to:Company {name: $to_name})
            MERGE (e)-[:AT_COMPANY]->(to)
            DELETE old
        """, from_name=from_name, to_name=to_name)

        session.run("""
            MATCH (from:Company {name: $from_name})
            WHERE NOT exists((from)--())
            DELETE from
        """, from_name=from_name)

    def _merge_generic(self, session, label: str, from_name: str, to_name: str):
        """Genel düğüm birleştirme — düğümü siler, ilişkileri taşımaz"""
        session.run(f"""
            MATCH (from:{label} {{name: $from_name}})
            DETACH DELETE from
        """, from_name=from_name)