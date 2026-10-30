"""Форма скиллов symphysis: frontmatter, копии GSD с шапкой MIT/Open GSD, перечень отличий перевода (F-14).

Чистый Python, без форка и без node. Task 20 сводит сюда проверки всех четырёх скиллов.
"""
import re

import pytest
from conftest import ROOT
from journal_model import PROBE_OUTCOMES

SKILLS = ROOT / "skills"
# Шапка копии файла GSD: первая строка файла, с пином коммита источника.
GSD_HEADER = "<!-- MIT License, Copyright (c) 2026 Open GSD; источник: upstream/gsd-core/"
GSD_PIN = "@ e2cd587"
# Заголовок таблицы отличий перевода — «место · в источнике · у нас · почему смысл изменён».
NOTES_HEADER = ("место", "в источнике", "у нас", "почему смысл изменён")
PERSPECTIVES = ("Researcher", "Simplifier", "Boundary Keeper", "Failure Analyst", "Seed Closer")
WORDS_TARGET = 1500   # ориентир владельца
WORDS_CEILING = 1800  # потолок: больше — красное


def read(path):
    return path.read_text(encoding="utf-8")


BLOCK_SCALARS = ("|", "|-", ">", ">-")


def frontmatter(text):
    """Поля frontmatter SKILL.md словарём `ключ -> значение`. Значение — простой скаляр
    в той же строке или блочный (`>-`, `>`, `|`, `|-`): строки с отступом ниже, свёрнутые
    пробелом. Простой скаляр с `: ` внутри строгий YAML не разберёт — AssertionError;
    нет frontmatter — AssertionError."""
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "нет frontmatter `---` в начале SKILL.md"
    fields, key = {}, None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if line.startswith((" ", "\t")):
            assert key is not None, f"строка с отступом без ключа: {line!r}"
            fields[key] = (fields[key] + " " + line.strip()).strip()
            continue
        key, sep, value = line.partition(":")
        assert sep, f"строка frontmatter без ключа: {line!r}"
        key, value = key.strip(), value.strip()
        if value in BLOCK_SCALARS:
            fields[key] = ""
        else:
            assert ": " not in value, f"{key}: простой скаляр с «: » внутри — строгий YAML его не разберёт"
            fields[key] = value
    return fields


def word_count(text):
    return len(text.split())


def table_rows(text):
    return [line for line in text.splitlines() if line.startswith("|")]


SKILL_DIRS = sorted(p for p in SKILLS.glob("symphysis-*/") if p.is_dir())
SKILLS_COUNT = 4
# references/*.md без шапки GSD: с D4b таких нет — переложение гриля store из атаки убрано,
# все копии несут шапку MIT/Open GSD (исключение было бы явным, не по маске).
OWN_REFERENCES = ()
# Вторая персона: целые слова. Кириллица — \w в Unicode-режиме re, границы слов работают.
SECOND_PERSON = re.compile(
    r"(?<!\w)(?:ты|тебе|тебя|тобой|твой|твоя|твоё|твои|вы|вас|вам|вами|ваш|ваша|ваше|ваши)(?!\w)"
    r"|(?<!\w)your(?!\w)", re.I)


def test_four_skills_present():
    assert len(SKILL_DIRS) == SKILLS_COUNT, \
        f"скиллов symphysis-*: {len(SKILL_DIRS)}, ожидалось {SKILLS_COUNT}: {[d.name for d in SKILL_DIRS]}"


@pytest.mark.parametrize("skill", SKILL_DIRS, ids=lambda d: d.name)
def test_skill_shape(skill):
    """Общий контракт формы: единственное место для frontmatter, шапок, перечня отличий, объёма."""
    text = read(skill / "SKILL.md")

    fm = frontmatter(text)
    assert fm.get("name") == skill.name, f"name {fm.get('name')!r} != имя каталога {skill.name!r}"
    assert fm.get("description"), "frontmatter без description"
    assert "Применяй, когда" in fm["description"], "description без «Применяй, когда …»"
    assert "Не применяй" in fm["description"], "description без «Не применяй …»"

    refs = sorted((skill / "references").glob("*.md"))
    assert refs, "нет references/*.md"
    for ref in refs:
        first = read(ref).splitlines()[0]
        if (skill.name, ref.name) in OWN_REFERENCES:
            assert not first.startswith(GSD_HEADER), \
                f"references/{ref.name} — своё: шапки MIT/Open GSD быть не должно"
            continue
        assert first.startswith(GSD_HEADER), f"references/{ref.name}: первая строка не шапка MIT/Open GSD: {first!r}"
        assert GSD_PIN in first, f"references/{ref.name}: в шапке нет пина {GSD_PIN}"

    notes = read(skill / "TRANSLATION-NOTES.md")
    assert notes.strip(), "TRANSLATION-NOTES.md пуст"
    rows = table_rows(notes)
    assert rows, "в TRANSLATION-NOTES.md нет таблицы"
    header = tuple(c.strip().lower() for c in rows[0].strip().strip("|").split("|"))
    assert header == NOTES_HEADER, f"заголовок таблицы отличий: {header}"
    assert len(rows) >= 3, "в таблице отличий нет строк данных (заголовок + разделитель + данные)"

    hits = SECOND_PERSON.findall(text)
    assert not hits, f"во втором лице в SKILL.md: {hits}"

    n = word_count(text)
    print(f"SKILL.md {skill.name}: {n} слов")
    if n > WORDS_TARGET:
        print(f"ориентир {WORDS_TARGET} превышен на {n - WORDS_TARGET}")
    assert n <= WORDS_CEILING, f"SKILL.md: {n} слов, потолок {WORDS_CEILING}"


def test_brainstorm_skill_shape():
    skill = SKILLS / "symphysis-brainstorm"
    text = read(skill / "SKILL.md")

    for name in PERSPECTIVES:
        assert name in text, f"в SKILL.md нет перспективы {name}"
    assert "брейншторм закончен по решению человека" in text, "нет строки отказа от нового круга (F-07)"

    notes = read(skill / "TRANSLATION-NOTES.md")
    rows = table_rows(notes)
    assert any("числов" in row.lower() or "ambiguity" in row.lower() for row in rows), \
        "в TRANSLATION-NOTES.md нет строки про снятый числовой гейт (ambiguity)"


EDGE_CATEGORIES = ("boundary", "adjacency", "empty", "encoding", "ordering", "precision",
                   "idempotency", "concurrency")
EDGE_OPTION_LINES = (
    "A. Specify — уточнить: строка «проходит/не проходит» в критерии приёмки spec.md",
    "B. Dismiss — не относится; причина обязательна",
    "C. Backstop — тест-страховка на крае; строки в spec.md нет",
    "D. Defer — отложено; остаётся открытым",
)


def test_edge_probe_has_eight_categories():
    skill = SKILLS / "symphysis-edge-probe"
    text = read(skill / "SKILL.md")

    for cat in EDGE_CATEGORIES:
        assert f"| {cat} |" in text, f"в таблице SKILL.md нет категории {cat}"
    for token in PROBE_OUTCOMES:  # из journal_model: токены модели журнала = токены скилла
        assert token in text, f"в SKILL.md нет исхода {token}"
    for line in EDGE_OPTION_LINES:
        assert line in text, f"в SKILL.md нет строки варианта дословно: {line!r}"
    assert "Dismissal requires a reason string" in text, "нет цитаты edge-probe.md:89 об отказе без причины"

    notes = read(skill / "TRANSLATION-NOTES.md")
    rows = table_rows(notes)
    assert any("unclassified" in row for row in rows), \
        "в TRANSLATION-NOTES.md нет строки про снятый кандидат `unclassified` (#1110)"


# Вопрос пробы запретов — дословно (`prohibition-probe.md:53-54`); варианты кандидата — по ярусам проверки.
PROHIBITION_QUESTION = ("What could this feature silently become that the author would NOT want, "
                        "but the spec does not forbid?")
PROHIBITION_OPTIONS = ("Specify/test", "Specify/judgment", "Dismiss", "Defer")
PROHIBITION_OPTION_LINES = (
    "A. Specify/test — запрет становится требованием spec.md; проверка — тест",
    "B. Specify/judgment — запрет становится требованием spec.md; проверка — суждение, не тест",
    "C. Dismiss — не относится; причина обязательна",
    "D. Defer — отложено; остаётся открытым",
)


def test_prohibition_probe_question_verbatim():
    skill = SKILLS / "symphysis-prohibition-probe"
    text = read(skill / "SKILL.md")

    assert PROHIBITION_QUESTION in text, "в SKILL.md нет вопроса GSD дословно (prohibition-probe.md:53-54)"
    assert "security.md" in text, "в SKILL.md нет отсылки канона к `security.md`"
    for token in PROHIBITION_OPTIONS:
        assert token in text, f"в SKILL.md нет варианта {token}"
    for line in PROHIBITION_OPTION_LINES:
        assert line in text, f"в SKILL.md нет строки варианта дословно: {line!r}"

    notes = read(skill / "TRANSLATION-NOTES.md")
    rows = table_rows(notes)
    assert any("PROB-06" in row or "гейт" in row.lower() for row in rows), \
        "в TRANSLATION-NOTES.md нет строки про снятый мягкий гейт PROB-06"


# Установка проверяющих GSD — начала трёх строк «FORCE stance» дословно
# (`agents/gsd-plan-checker.md:30`, `gsd-code-reviewer.md:22`, `gsd-doc-verifier.md:29`).
FORCE_LINES = ("Assume every plan set is flawed until evidence proves otherwise",
               "Assume every submitted implementation contains defects",
               "Assume every factual claim in the doc is wrong until filesystem evidence proves it correct")
# Тяжесть строки атаки — переложение BLOCKER / WARNING / INFO (`agents/gsd-plan-checker.md:39-42`).
ATTACK_SEVERITIES = ("блокер", "предупреждение", "справка")
# Линзы атаки — измерения plan-checker по имени (`gsd-plan-checker.md:126`, `:705`) и слуги колонки
# «Линза» (закрытый список SKILL.md; просмотрщик группирует строки по слугу — слово владельца 2026-10-30).
ATTACK_LENSES = ("Requirement Coverage", "Numeric/Factual Claim Authority")
ATTACK_LENS_SLUGS = ("requirement-coverage", "claim-authority", "honest-verifier", "coverage")
# Воздержание honest-verifier: строка, которая не «есть» и не «нет» (`honest-verifier.md:43`).
ABSTENTION_ROW = "по спеке не выводится"
# Копии слоя проверки GSD в references/ атаки: файл -> строка источника дословно.
ATTACK_REFERENCES = {
    "plan-checker-dimensions.md": "Issues without a severity classification are not valid output",
    "claim-extraction.md": "Do NOT execute any commands. Existence check only.",
    "honest-verifier.md": "## The problem it solves",
    "gap-output.md": "confirm that status is not `passed` when human verification items exist",
}


def test_attack_skill_writes_verdict_contract():
    skill = SKILLS / "symphysis-attack"
    text = read(skill / "SKILL.md")

    assert "status: passed" in text, "в SKILL.md нет вердикта `status: passed`"
    assert "target_sha256" in text, "в SKILL.md нет поля `target_sha256`"
    for token in ("targets", "sha256", "gaps_found"):
        assert token in text, f"в SKILL.md нет `{token}` — половина `attack-artifacts`"
    assert "FORCE stance" in text, "в SKILL.md нет установки «FORCE stance»"
    for severity in ATTACK_SEVERITIES:
        assert severity in text, f"в SKILL.md нет тяжести «{severity}»"
    for lens in ATTACK_LENSES:
        assert lens in text, f"в SKILL.md нет линзы plan-checker «{lens}»"
    assert "| Линза |" in text, "в SKILL.md нет таблицы закрытого списка линз с колонкой «Линза»"
    for slug in ATTACK_LENS_SLUGS:
        assert f"`{slug}`" in text, f"в SKILL.md нет слуга линзы `{slug}`"
    assert ABSTENTION_ROW in text, f"в SKILL.md нет строки воздержания «{ABSTENTION_ROW}»"
    # журнал — опора артефактов: его правка обесценивает и вердикт `attack-artifacts` (ruling Task 19)
    artifacts_row = next(row for row in table_rows(text) if row.startswith("| `attack-artifacts`"))
    assert "decisions.json" in artifacts_row, "в строке `attack-artifacts` таблицы вызовов нет `decisions.json`"

    force = read(skill / "references" / "force-stance.md")
    for line in FORCE_LINES:
        assert line in force, f"в references/force-stance.md нет строки «{line[:40]}…» дословно"
    for name, quote in ATTACK_REFERENCES.items():
        assert quote in read(skill / "references" / name), f"в references/{name} нет строки «{quote[:40]}…» дословно"
    assert not (skill / "references" / "grill-lenses.md").exists(), "гриль store — не источник атаки (D4b)"

    notes = read(skill / "TRANSLATION-NOTES.md")
    assert any("store" in row for row in table_rows(notes)), \
        "в TRANSLATION-NOTES.md нет строки про заимствование из store"
