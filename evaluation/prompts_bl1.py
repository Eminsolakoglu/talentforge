"""
BL-1: Sıfır-Örnekli Prompt (Zero-shot)
Few-shot örnek yok, CoT yok, Semantic Inference yok.
Sadece temel talimat + JSON şeması.
"""

SYSTEM_PROMPT_BL1 = """\
Sen bir CV analiz asistanısın.
Verilen CV metninden aşağıdaki bilgileri JSON formatında çıkar.

Sadece CV'de açıkça yazılan bilgileri çıkar.
Metinde olmayan bilgi ekleme.
"""

def build_user_prompt_bl1(cv_text: str, max_chars: int = 6000) -> str:
    return f"""\
Aşağıdaki CV'yi analiz et ve JSON formatında yapılandırılmış bilgi çıkar.

CV metni:
\"\"\"
{cv_text[:max_chars]}
\"\"\"

Şu alanları içeren JSON döndür:
{{
  "candidate_name": "string",
  "email": "string",
  "phone": "string",
  "location": "string",
  "summary": "string",
  "experiences": [
    {{
      "company_name": "string",
      "role_title": "string",
      "start_date": "string",
      "end_date": "string or null",
      "is_current": "boolean",
      "location": "string or null",
      "description": "string",
      "achievements": ["string"],
      "skills_used": ["string"],
      "evidence_text": "string",
      "confidence": 0.9
    }}
  ],
  "skills": [
    {{
      "name": "string",
      "category": "Programming|Framework|Database|Cloud|DevOps|Soft Skill|Tool|Data Science|Domain|Other",
      "years_experience": "number or null",
      "level": "1-5 or null",
      "evidence_text": "string",
      "confidence": 0.9
    }}
  ],
  "educations": [
    {{
      "degree": "string",
      "field": "string",
      "institution": "string",
      "start_year": "number",
      "end_year": "number or null",
      "gpa": "number or null"
    }}
  ],
  "languages": ["string"],
  "certifications": ["string"]
}}
"""