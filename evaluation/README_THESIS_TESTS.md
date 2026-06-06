# TalentForge Thesis Test Pipeline

Bu klasor, 100 CV dataset ile tezde kullanilacak deney sonuclarini uretmek icin
duzenlendi. Ana gold dosya `golden_extractions_pretty.json`, dataset dagilimlari
`dataset_summary.json`, aday eslestirme beklentileri `matching_ground_truth.json`
ve entity resolution hedefleri `entity_resolution_targets.json` dosyalarindan okunur.

## 1. Ablation / Prompt Karsilastirmasi

Tek model ile prompt varyantlarini olcmek icin:

```powershell
$env:UV_CACHE_DIR="$env:TEMP\talentforge-uv-cache"
$env:UV_PYTHON="C:\Users\gizem\AppData\Local\Programs\Python\Python313\python.exe"
uv run --no-dev --no-python-downloads python evaluation/ablation_runner.py `
  --cv_dir data/cvs `
  --gold evaluation/golden_extractions_pretty.json `
  --n_cvs 100 `
  --configs BL-1 BL-2 SYS-A SYS-B `
  --models Qwen/Qwen2.5-7B-Instruct `
  --output evaluation/ablation_results_thesis_100.json `
  --no_resume
```

## 2. Model Karsilastirmasi

BL-2 prompt sabitlenerek farkli HF modellerini karsilastirmak icin:

```powershell
$env:UV_CACHE_DIR="$env:TEMP\talentforge-uv-cache"
$env:UV_PYTHON="C:\Users\gizem\AppData\Local\Programs\Python\Python313\python.exe"
uv run --no-dev --no-python-downloads python evaluation/ablation_runner.py `
  --cv_dir data/cvs `
  --gold evaluation/golden_extractions_pretty.json `
  --n_cvs 100 `
  --configs BL-2 `
  --models Qwen/Qwen2.5-7B-Instruct meta-llama/Llama-3.1-8B-Instruct mistralai/Mistral-7B-Instruct-v0.3 `
  --output evaluation/model_comparison_bl2_thesis_100.json `
  --no_resume
```

Model erisimi HF Router tarafinda degisebilir. Bir model hata verirse ayni komuta
erisilebilir baska bir instruct model eklenebilir.

## 3. Triple-level KG Metrikleri

Ablation sonucu icin:

```powershell
uv run --no-dev --no-python-downloads python evaluation/evaluate_ablation_triples.py `
  --ablation evaluation/ablation_results_thesis_100.json `
  --gold evaluation/golden_extractions_pretty.json `
  --output evaluation/ablation_triple_results_thesis_100.json
```

Model karsilastirmasi sonucu icin:

```powershell
uv run --no-dev --no-python-downloads python evaluation/evaluate_ablation_triples.py `
  --ablation evaluation/model_comparison_bl2_thesis_100.json `
  --gold evaluation/golden_extractions_pretty.json `
  --output evaluation/model_comparison_bl2_triple_results_thesis_100.json
```

Bu metriklere `HAS_PROJECT` ve `PROJECT_USED_SKILL` iliskileri de dahildir.

## 4. Matching Ground Truth Testi

Bu test icin once FastAPI calisiyor olmali:

```powershell
uv run --no-dev --no-python-downloads uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Sonra ayri terminalde:

```powershell
uv run --no-dev --no-python-downloads python evaluation/evaluate_matching_ground_truth.py `
  --ground-truth evaluation/matching_ground_truth.json `
  --api-base http://127.0.0.1:8000 `
  --output evaluation/thesis_outputs/matching_results.json
```

## 5. Entity Resolution Testi

Aura/local Neo4j hangi ortamda test edilecekse `.env` o ortami gostermeli.
Once entity resolution calistirilir:

```powershell
uv run --no-dev --no-python-downloads python -c "import requests; print(requests.post('http://127.0.0.1:8000/resolve-entities', timeout=120).json())"
```

Sonra hedef varyantlar olculur:

```powershell
uv run --no-dev --no-python-downloads python evaluation/evaluate_entity_resolution.py `
  --targets evaluation/entity_resolution_targets.json `
  --output evaluation/thesis_outputs/entity_resolution_results.json
```

## 6. Tez Cikti Dosyalari ve JPEG Grafikler

Ablation ciktilari uretildikten sonra:

```powershell
uv run --no-dev --no-python-downloads python evaluation/thesis_report.py `
  --ablation evaluation/ablation_results_thesis_100.json `
  --triple evaluation/ablation_triple_results_thesis_100.json `
  --dataset-summary evaluation/dataset_summary.json `
  --matching evaluation/thesis_outputs/matching_results.json `
  --output-dir evaluation/thesis_outputs
```

Uretilen temel dosyalar:

- `ablation_aggregate_metrics.csv`
- `kg_relation_metrics.csv`
- `kg_metadata_breakdowns.csv`
- `dataset_distributions.csv`
- `matching_metrics.csv`
- `thesis_report_summary.md`
- `*.jpeg` grafik ve tablo gorselleri

## Teze Konulabilecek Metrikler

- NER F1: skill, company, education ve ortalama entity F1
- RE F1: experience-company-skill baglanti kalitesi
- KG triple precision / recall / F1
- Relation bazli F1: `HAS_SKILL`, `HAS_EXPERIENCE`, `USED_SKILL`, `HAS_PROJECT`, vb.
- Metadata kirilimi: difficulty, file format, CV dili, template tipi, role family, seniority
- Hallucination / unsupported extraction rate
- Unsupported triple rate
- Success rate
- Ortalama sure
- Matching: Hit@K, Recall@10, NDCG@10
