"""
BL-2: Few-shot Prompt (CoT yok, Semantic Inference yok)
Sadece örnek girdi-çıktı çifti var. Adım adım düşünme ve
dolaylı anlam çıkarımı kuralları yok.
"""

SYSTEM_PROMPT_BL2 = """\
Sen bir CV analiz asistanısın.
Verilen CV metninden yapılandırılmış bilgi çıkar ve JSON formatında döndür.

Sadece CV'de yazılan bilgileri çıkar. Metinde olmayan bilgi ekleme.
"""

FEW_SHOT_BL2 = """\
## ÖRNEK

### CV Metni:
\"\"\"
Elif Kara
elif.kara@gmail.com | 0533 987 6543 | Ankara

HAKKIMDA
7 yıllık deneyime sahip kıdemli veri bilimci.

DENEYİM
Senior Data Scientist — Getir (Şub 2022 – Halen)
- Python, PySpark, MLflow ile pipeline kurdum
- 5 kişilik ML takımını yönetiyorum

Veri Bilimci — QNB Finansbank (Oca 2019 – Oca 2022)
- XGBoost, LightGBM ile kredi skorlama
- SQL veri analizi

EĞİTİM
İstatistik Yüksek Lisans — ODTÜ (2017-2019)
Endüstri Mühendisliği Lisans — Bilkent (2013-2017)

DİLLER
Türkçe (Ana dil), İngilizce (C1)

SERTİFİKA
AWS Machine Learning Specialty (2023)
\"\"\"

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
      "description": "Python, PySpark, MLflow ile pipeline kurma. ML takım yönetimi.",
      "achievements": ["5 kişilik ML takımını yönetiyor"],
      "skills_used": ["Python", "PySpark", "MLflow"],
      "evidence_text": "Python, PySpark, MLflow ile pipeline kurdum",
      "confidence": 0.95
    },
    {
      "company_name": "QNB Finansbank",
      "role_title": "Veri Bilimci",
      "start_date": "Oca 2019",
      "end_date": "Oca 2022",
      "is_current": false,
      "location": null,
      "description": "Kredi skorlama modeli geliştirme ve SQL veri analizi.",
      "achievements": [],
      "skills_used": ["XGBoost", "LightGBM", "SQL"],
      "evidence_text": "XGBoost, LightGBM ile kredi skorlama. SQL veri analizi.",
      "confidence": 0.95
    }
  ],
  "skills": [
    {"name": "Python", "category": "Programming", "years_experience": 7, "level": 5,
     "evidence_text": "Python, PySpark, MLflow ile pipeline kurdum", "confidence": 0.95},
    {"name": "PySpark", "category": "Data Science", "years_experience": null, "level": 4,
     "evidence_text": "Python, PySpark, MLflow ile pipeline kurdum", "confidence": 0.9},
    {"name": "MLflow", "category": "Tool", "years_experience": null, "level": null,
     "evidence_text": "Python, PySpark, MLflow ile pipeline kurdum", "confidence": 0.9},
    {"name": "XGBoost", "category": "Data Science", "years_experience": null, "level": null,
     "evidence_text": "XGBoost, LightGBM ile kredi skorlama", "confidence": 0.9},
    {"name": "LightGBM", "category": "Data Science", "years_experience": null, "level": null,
     "evidence_text": "XGBoost, LightGBM ile kredi skorlama", "confidence": 0.9},
    {"name": "SQL", "category": "Database", "years_experience": null, "level": 4,
     "evidence_text": "SQL veri analizi", "confidence": 0.9}
  ],
  "educations": [
    {"degree": "Yüksek Lisans", "field": "İstatistik", "institution": "ODTÜ",
     "start_year": 2017, "end_year": 2019, "gpa": null},
    {"degree": "Lisans", "field": "Endüstri Mühendisliği", "institution": "Bilkent",
     "start_year": 2013, "end_year": 2017, "gpa": null}
  ],
  "languages": ["Türkçe (Ana dil)", "İngilizce (C1)"],
  "certifications": ["AWS Machine Learning Specialty (2023)"]
}
"""

def build_user_prompt_bl2(cv_text: str, max_chars: int = 6000) -> str:
    return f"""\
{FEW_SHOT_BL2}

---

Şimdi aşağıdaki CV'yi aynı formatta analiz et.
Sadece CV'de yazılan bilgileri çıkar.

### CV Metni:
\"\"\"
{cv_text[:max_chars]}
\"\"\"
"""