---
status: gaps_found
target: decisions.json
target_sha256: 69fa58491eae0eb751fc3f1fbeb21260db0c8cfcb163b0ad6339bdb55a2f5f37
---

# Атака журнала решений

| Утверждение | Раздел | Линза | Инвариант | Тяжесть | Опора есть / нет | Чем закрыть |
| --- | --- | --- | --- | --- | --- | --- |
| улики записи не резолвятся: `store/change-intake/references/fork-form.md`, `playground/SKILL.md`, `md4h/readme.md` (×2), `store/.md4h/feedback/…/feedback.md` (×2), `store/research/variant-B-2026-10-28.md` | F-01, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (7 улик) | правка записи |
| улика записи не резолвится: `store/flow-step/SKILL.md` | F-02, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (1 улика) | правка записи |
| улика записи не резолвится: `store/change-intake/SKILL.md` | F-04, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (1 улика) | правка записи |
| улики записи не резолвятся: `store/research/variant-B-2026-10-28.md` (×3) | F-05, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (3 улики) | правка записи |
| улика записи не резолвится: `store/config/openspec/schemas/store-flow/schema.yaml` | F-06, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (1 улика) | правка записи |
| улика записи не резолвится: `store/change-intake/SKILL.md` | F-07, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (1 улика) | правка записи |
| улика записи не резолвится: `store/change-intake/references/approve-form.md` | F-09, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (1 улика) | правка записи |
| `recommendation` без `why` | F-10, recommendation | research-resolution | рекомендация несёт `why` | блокер | нет: `why` пуст | правка записи |
| улика записи не резолвится: `store/change-intake/SKILL.md` | F-11, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (1 улика) | правка записи |
| улики записи не резолвятся: `store/change-intake/references/fork-form.md`, `store/change-intake/references/grill-form.md` | F-12, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (2 улики) | правка записи |
| `recommendation` без `why` | F-14, recommendation | research-resolution | рекомендация несёт `why` | блокер | нет: `why` пуст | правка записи |
| улика записи не резолвится: `store/tools/openspec_setup.py` | F-15, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (1 улика) | правка записи |
| улика записи не резолвится: `store/tools/openspec_setup.py` | F-16, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (1 улика) | правка записи |
| улика записи не резолвится: `playground/templates/document-critique.md` | F-17, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (1 улика) | правка записи |
| улики записи не резолвятся: `playground/SKILL.md` (×2) | F-18, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (2 улики) | правка записи |
| улики записи не резолвятся: `store/change-intake/references/grill-form.md` (×2) | F-25, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (2 улики) | правка записи |
| улики записи не резолвятся: `playground/SKILL.md` (×2) | F-26, evidence | claim-extraction | улики записи резолвятся в корнях журнала | блокер | нет: файла нет (2 улики) | правка записи |
| чисто | F-03 | coverage | — | справка | есть | — |
| чисто | F-08 | coverage | — | справка | есть | — |
| чисто | F-13 | coverage | — | справка | есть | — |
| чисто | F-19 | coverage | — | справка | есть | — |
| чисто | F-20 | coverage | — | справка | есть | — |
| чисто | F-21 | coverage | — | справка | есть | — |
| чисто | F-22 | coverage | — | справка | есть | — |
| чисто | F-23 | coverage | — | справка | есть | — |
| чисто | F-24 | coverage | — | справка | есть | — |
| чисто | F-27 | coverage | — | справка | есть | — |

Вердикт: `status: gaps_found` — 17 блокеров (15 `claim-extraction`, 2 `research-resolution`), 0 предупреждений, 10 справок.
