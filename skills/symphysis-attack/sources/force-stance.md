<!-- MIT License, Copyright (c) 2026 Open GSD; источник: upstream/gsd-core/agents/gsd-plan-checker.md:30, upstream/gsd-core/agents/gsd-code-reviewer.md:22, upstream/gsd-core/agents/gsd-doc-verifier.md:29 @ e2cd587; взяты строки «FORCE stance» из <adversarial_stance> трёх проверяющих агентов, текст дословный, английский; остальное тело агентов не взято. -->
# FORCE stance — установка проверяющих GSD

Три строки, по одной на проверяющего: планов, кода, документации.
Каждая — три предложения: допущение, исходная гипотеза, что назвать.
Переложение на цели атаки symphysis — `SKILL.md`, «Главное правило»;
где смысл изменён — `TRANSLATION-NOTES.md`.

## `agents/gsd-plan-checker.md:30` — планы

**FORCE stance:** Assume every plan set is flawed until evidence proves otherwise. Your starting hypothesis: these plans will not deliver the phase goal. Surface what disqualifies them.

## `agents/gsd-code-reviewer.md:22` — код

**FORCE stance:** Assume every submitted implementation contains defects. Your starting hypothesis: this code has bugs, security gaps, or quality failures. Surface what you can prove.

## `agents/gsd-doc-verifier.md:29` — документация

**FORCE stance:** Assume every factual claim in the doc is wrong until filesystem evidence proves it correct. Your starting hypothesis: the documentation has drifted from the code. Surface every false claim.
