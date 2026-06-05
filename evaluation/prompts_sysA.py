"""
SYS-A: Few-shot + CoT Prompt (Semantic Inference yok)
BL-2'ye ek olarak adım adım düşünme talimatı var.
Dolaylı anlam çıkarımı kuralları (sektör çıkarımı, sinonim normalizasyonu
gibi) henüz yok — bunlar SYS-B/C'de mevcut prompts.py'de ekleniyor.
"""

SYSTEM_PROMPT_SYSA = """\
Sen deneyimli bir İnsan Kaynakları ve NLP uzmanısın.
Görevin, verilen CV metninden yapılandırılmış bilgi çıkarmaktır.

ADIM ADIM DÜŞÜNME (Chain of Thought):
Her CV için şu sırayla ilerle:
  1. Kişisel bilgileri bul (isim, e-posta, telefon, konum).
  2. Özet/profil cümlesini çıkar.
  3. Deneyimleri kronolojik sırayla listele.
  4. Her deneyimde kullanılan yetenekleri çıkar.
  5. Yetenekleri kategorize et.
  6. Eğitim bilgilerini çıkar.
  7. Dil ve sertifikaları çıkar.

KURALLAR:
- CV'de açıkça YAZILMAYAN bilgiyi EKLEME.
- Tarihler: "Oca 2023" formatında yaz. Devam eden → is_current=true.
- evidence_text: Maksimum 15 kelime.
- confidence: 0.90+ açık bilgi, 0.75-0.89 güçlü ipucu.
"""

FEW_SHOT_SYSA = """\
## ÖRNEK — Adım adım düşünme ile

### CV Metni:
\"\"\"
Elif Kara
elif.kara@gmail.com | 0533 987 6543 | Ankara

HAKKIMDA
7 yıllık deneyime sahip kıdemli veri bilimci. Finans ve e-ticaret
sektörlerinde büyük ölçekli ML projeleri yönettim.

DENEYİM
Senior Data Scientist — Getir (Şub 2022 – Halen)
- Talep tahmin modeli geliştirdim, MAPE %12'den %7'ye düştü
- 5 kişilik ML takımını yönetiyorum
- Python, PySpark, MLflow ile end-to-end pipeline kurdum
- A/B testleri ile model performansını ölçtüm

Veri Bilimci — QNB Finansbank (Oca 2019 – Oca 2022)
- Kredi skorlama modeli geliştirdim (XGBoost, LightGBM)
- SQL ile büyük ölçekli veri analizi

EĞİTİM
İstatistik Yüksek Lisans — ODTÜ (2017-2019)
Endüstri Mühendisliği Lisans — Bilkent Üniversitesi (2013-2017)

DİLLER
Türkçe (Ana dil), İngilizce (C1)

SERTİFİKA
AWS Machine Learning Specialty (2023)
\"\"\"

### Adım adım düşünme:
1. Kişisel bilgiler: Elif Kara, elif.kara@gmail.com, Ankara
2. Özet: 7 yıl deneyim, kıdemli veri bilimci
3. Deneyimler: Getir (Şub 2022-halen), QNB Finansbank (Oca 2019-Oca 2022)
4. Getir'deki yetenekler: Python, PySpark, MLflow, A/B Testing
   QNB'deki yetenekler: XGBoost, LightGBM, SQL
5. Kategoriler: Python→Programming, MLflow→Tool, XGBoost→Data Science
6. Eğitim: ODTÜ YL İstatistik, Bilkent Lisans Endüstri
7. Diller: Türkçe, İngilizce. Sertifika: AWS ML Specialty

### Çıktı:
{
  "candidate_name": "Elif Kara",
  "email": "elif.kara@gmail.com",
  "phone": "0533 987 6543",
  "location": "Ankara",
  "summary": "7 yıllık deneyime sahip kıdemli veri bilimci.",
  "experiences": [
    {
      "company_name": "Getir",
      "role_title": "Senior Data Scientist",
      "start_date": "Şub 2022",
      "end_date": null,
      "is_current": true,
      "location": null,
      "description": "Talep tahmin modeli, ML takım yönetimi, end-to-end pipeline.",
      "achievements": ["MAPE %12'den %7'ye düşürüldü"],
      "skills_used": ["Python", "PySpark", "MLflow", "A/B Testing"],
      "evidence_text": "Python, PySpark, MLflow ile end-to-end pipeline kurdum",
      "confidence": 0.95
    },
    {
      "company_name": "QNB Finansbank",
      "role_title": "Veri Bilimci",
      "start_date": "Oca 2019",
      "end_date": "Oca 2022",
      "is_current": false,
      "location": null,
      "description": "Kredi skorlama ve SQL veri analizi.",
      "achievements": [],
      "skills_used": ["XGBoost", "LightGBM", "SQL"],
      "evidence_text": "Kredi skorlama modeli geliştirdim (XGBoost, LightGBM)",
      "confidence": 0.95
    }
  ],
  "skills": [
    {"name": "Python", "category": "Programming", "years_experience": 7, "level": 5,
     "evidence_text": "Python, PySpark, MLflow ile end-to-end pipeline kurdum", "confidence": 0.95},
    {"name": "PySpark", "category": "Data Science", "years_experience": null, "level": 4,
     "evidence_text": "Python, PySpark, MLflow ile end-to-end pipeline kurdum", "confidence": 0.9},
    {"name": "MLflow", "category": "Tool", "years_experience": null, "level": null,
     "evidence_text": "Python, PySpark, MLflow ile end-to-end pipeline kurdum", "confidence": 0.9},
    {"name": "XGBoost", "category": "Data Science", "years_experience": null, "level": null,
     "evidence_text": "Kredi skorlama modeli geliştirdim (XGBoost, LightGBM)", "confidence": 0.9},
    {"name": "LightGBM", "category": "Data Science", "years_experience": null, "level": null,
     "evidence_text": "Kredi skorlama modeli geliştirdim (XGBoost, LightGBM)", "confidence": 0.9},
    {"name": "SQL", "category": "Database", "years_experience": null, "level": 4,
     "evidence_text": "SQL ile büyük ölçekli veri analizi", "confidence": 0.9},
    {"name": "A/B Testing", "category": "Data Science", "years_experience": null, "level": null,
     "evidence_text": "A/B testleri ile model performansını ölçtüm", "confidence": 0.85}
  ],
  "educations": [
    {"degree": "Yüksek Lisans", "field": "İstatistik", "institution": "ODTÜ",
     "start_year": 2017, "end_year": 2019, "gpa": null},
    {"degree": "Lisans", "field": "Endüstri Mühendisliği", "institution": "Bilkent Üniversitesi",
     "start_year": 2013, "end_year": 2017, "gpa": null}
  ],
  "languages": ["Türkçe (Ana dil)", "İngilizce (C1)"],
  "certifications": ["AWS Machine Learning Specialty (2023)"]
}
"""

def build_user_prompt_sysA(cv_text: str, max_chars: int = 6000) -> str:
    return f"""\
{FEW_SHOT_SYSA}

---

Şimdi aşağıdaki CV'yi adım adım düşünerek analiz et.

Kurallar:
1. Adım adım düşün (önce kişisel bilgi, sonra deneyim, sonra skill…).
2. Sadece CV'de yazılan bilgileri çıkar, uydurma.
3. evidence_text maksimum 15 kelime.

### CV Metni:
\"\"\"
{cv_text[:max_chars]}
\"\"\"
"""