# TalentForge Thesis Evaluation Outputs

## Ablation / Model Results
| run | config | model | n | success_rate | ner_f1 | skill_f1 | re_f1 | kg_f1 | hallucination_rate | unsupported_triple_rate | avg_elapsed_sec |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BL-1_Qwen2.5-7B-Instruct | BL-1 | Qwen/Qwen2.5-7B-Instruct | 98 | 0.98 | 0.969 | 0.938 | 0.944 | 0.88 | 0.032 | 0.045 | 13.4 |
| BL-2_Qwen2.5-7B-Instruct | BL-2 | Qwen/Qwen2.5-7B-Instruct | 99 | 0.99 | 0.963 | 0.939 | 0.947 | 0.893 | 0.006 | 0.036 | 14.93 |
| SYS-A_Qwen2.5-7B-Instruct | SYS-A | Qwen/Qwen2.5-7B-Instruct | 98 | 0.98 | 0.898 | 0.889 | 0.929 | 0.773 | 0.059 | 0.071 | 18.87 |
| SYS-B_Qwen2.5-7B-Instruct | SYS-B | Qwen/Qwen2.5-7B-Instruct | 100 | 1.0 | 0.919 | 0.884 | 0.881 | 0.854 | 0.017 | 0.074 | 15.96 |

## Matching Metrics
| metric | value |
| --- | --- |
| n_queries | 10 |
| attempted_queries | 10 |
| success_rate | 1.0 |
| hit_strong_at_1 | 0.0 |
| hit_strong_at_3 | 0.0 |
| hit_strong_at_5 | 0.0 |
| hit_any_relevant_at_1 | 0.0 |
| hit_any_relevant_at_3 | 0.0 |
| hit_any_relevant_at_5 | 0.0 |
| strong_recall_at_10 | 0.0 |
| relevant_recall_at_10 | 0.0 |
| ndcg_at_10 | 0.0 |
| avg_elapsed_sec | 3.27 |

## Entity Resolution Metrics


## Generated Figures
- `ablation_model_metrics.jpeg`
- `ablation_summary_table.jpeg`
- `difficulty_distribution.jpeg`
- `hallucination_rates.jpeg`
- `kg_relation_f1.jpeg`
- `matching_metrics.jpeg`
- `role_family_distribution.jpeg`
- `template_distribution.jpeg`