"""Форма скиллов symphysis: frontmatter, копии GSD с шапкой MIT/Open GSD, перечень отличий перевода (F-14).

Чистый Python, без форка и без node. Task 20 сводит сюда проверки всех четырёх скиллов.
"""
import re

from conftest import ROOT

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


def test_brainstorm_skill_shape():
    skill = SKILLS / "symphysis-brainstorm"
    text = read(skill / "SKILL.md")

    fm = frontmatter(text)
    assert fm.get("name") == "symphysis-brainstorm"
    assert fm.get("description"), "frontmatter без description"
    assert "Применяй, когда" in fm["description"], "description без «Применяй, когда …»"
    assert "Не применяй" in fm["description"], "description без «Не применяй …»"

    for name in PERSPECTIVES:
        assert name in text, f"в SKILL.md нет перспективы {name}"
    assert "брейншторм закончен по решению человека" in text, "нет строки отказа от нового круга (F-07)"

    for ref in ("spec-phase.md", "discuss-phase-gray-areas.md"):
        first = read(skill / "references" / ref).splitlines()[0]
        assert first.startswith(GSD_HEADER), f"references/{ref}: первая строка не шапка MIT/Open GSD: {first!r}"
        assert GSD_PIN in first, f"references/{ref}: в шапке нет пина {GSD_PIN}"

    notes = read(skill / "TRANSLATION-NOTES.md")
    assert notes.strip(), "TRANSLATION-NOTES.md пуст"
    rows = table_rows(notes)
    assert any(all(word in row.lower() for word in NOTES_HEADER) for row in rows), \
        "в TRANSLATION-NOTES.md нет заголовка таблицы «место · в источнике · у нас · почему смысл изменён»"
    assert any("числов" in row.lower() or "ambiguity" in row.lower() for row in rows), \
        "в TRANSLATION-NOTES.md нет строки про снятый числовой гейт (ambiguity)"

    n = word_count(text)
    print(f"SKILL.md symphysis-brainstorm: {n} слов (ориентир {WORDS_TARGET}, потолок {WORDS_CEILING})")
    assert n <= WORDS_CEILING, f"SKILL.md: {n} слов, потолок {WORDS_CEILING}"


EDGE_CATEGORIES = ("boundary", "adjacency", "empty", "encoding", "ordering", "precision",
                   "idempotency", "concurrency")
PROBE_OUTCOMES = ("Specify", "Dismiss", "Backstop", "Defer")


def test_edge_probe_has_eight_categories():
    skill = SKILLS / "symphysis-edge-probe"
    text = read(skill / "SKILL.md")

    fm = frontmatter(text)
    assert fm.get("name") == "symphysis-edge-probe"
    assert fm.get("description"), "frontmatter без description"
    assert "Применяй, когда" in fm["description"], "description без «Применяй, когда …»"
    assert "Не применяй" in fm["description"], "description без «Не применяй …»"

    for cat in EDGE_CATEGORIES:
        assert f"| {cat} |" in text, f"в таблице SKILL.md нет категории {cat}"
    for token in PROBE_OUTCOMES:
        assert token in text, f"в SKILL.md нет исхода {token}"
    assert "Dismissal requires a reason string" in text, "нет цитаты edge-probe.md:89 об отказе без причины"

    first = read(skill / "references" / "edge-probe.md").splitlines()[0]
    assert first.startswith(GSD_HEADER), f"references/edge-probe.md: первая строка не шапка MIT/Open GSD: {first!r}"
    assert GSD_PIN in first, f"references/edge-probe.md: в шапке нет пина {GSD_PIN}"

    notes = read(skill / "TRANSLATION-NOTES.md")
    rows = table_rows(notes)
    assert any(all(word in row.lower() for word in NOTES_HEADER) for row in rows), \
        "в TRANSLATION-NOTES.md нет заголовка таблицы «место · в источнике · у нас · почему смысл изменён»"
    assert any("unclassified" in row for row in rows), \
        "в TRANSLATION-NOTES.md нет строки про снятый кандидат `unclassified` (#1110)"

    n = word_count(text)
    print(f"SKILL.md symphysis-edge-probe: {n} слов (ориентир {WORDS_TARGET}, потолок {WORDS_CEILING})")
    assert n <= WORDS_CEILING, f"SKILL.md: {n} слов, потолок {WORDS_CEILING}"


# Вопрос пробы запретов — дословно (`prohibition-probe.md:53-54`); варианты кандидата — по ярусам проверки.
PROHIBITION_QUESTION = ("What could this feature silently become that the author would NOT want, "
                        "but the spec does not forbid?")
PROHIBITION_OPTIONS = ("Specify/test", "Specify/judgment", "Dismiss", "Defer")


def test_prohibition_probe_question_verbatim():
    skill = SKILLS / "symphysis-prohibition-probe"
    text = read(skill / "SKILL.md")

    fm = frontmatter(text)
    assert fm.get("name") == "symphysis-prohibition-probe"
    assert fm.get("description"), "frontmatter без description"
    assert "Применяй, когда" in fm["description"], "description без «Применяй, когда …»"
    assert "Не применяй" in fm["description"], "description без «Не применяй …»"

    assert PROHIBITION_QUESTION in text, "в SKILL.md нет вопроса GSD дословно (prohibition-probe.md:53-54)"
    assert "security.md" in text, "в SKILL.md нет отсылки канона к `security.md`"
    for token in PROHIBITION_OPTIONS:
        assert token in text, f"в SKILL.md нет варианта {token}"

    first = read(skill / "references" / "prohibition-probe.md").splitlines()[0]
    assert first.startswith(GSD_HEADER), f"references/prohibition-probe.md: первая строка не шапка MIT/Open GSD: {first!r}"
    assert GSD_PIN in first, f"references/prohibition-probe.md: в шапке нет пина {GSD_PIN}"

    notes = read(skill / "TRANSLATION-NOTES.md")
    rows = table_rows(notes)
    assert any(all(word in row.lower() for word in NOTES_HEADER) for row in rows), \
        "в TRANSLATION-NOTES.md нет заголовка таблицы «место · в источнике · у нас · почему смысл изменён»"
    assert any("PROB-06" in row or "гейт" in row.lower() for row in rows), \
        "в TRANSLATION-NOTES.md нет строки про снятый мягкий гейт PROB-06"

    n = word_count(text)
    print(f"SKILL.md symphysis-prohibition-probe: {n} слов (ориентир {WORDS_TARGET}, потолок {WORDS_CEILING})")
    assert n <= WORDS_CEILING, f"SKILL.md: {n} слов, потолок {WORDS_CEILING}"


# Пять линз гриля — имена дословно (`store/change-intake/references/grill-form.md:24-25`).
GRILL_LENSES = ("эхо требования", "ветви без сценария", "переход состояния",
                "термин без определения", "реализация в постановке")
# Установка проверяющих GSD — начала трёх строк «FORCE stance» дословно
# (`agents/gsd-plan-checker.md:30`, `gsd-code-reviewer.md:22`, `gsd-doc-verifier.md:29`).
FORCE_LINES = ("Assume every plan set is flawed until evidence proves otherwise",
               "Assume every submitted implementation contains defects",
               "Assume every factual claim in the doc is wrong until filesystem evidence proves it correct")


def test_attack_skill_writes_verdict_contract():
    skill = SKILLS / "symphysis-attack"
    text = read(skill / "SKILL.md")

    fm = frontmatter(text)
    assert fm.get("name") == "symphysis-attack"
    assert fm.get("description"), "frontmatter без description"
    assert "Применяй, когда" in fm["description"], "description без «Применяй, когда …»"
    assert "Не применяй" in fm["description"], "description без «Не применяй …»"

    assert "status: passed" in text, "в SKILL.md нет вердикта `status: passed`"
    assert "target_sha256" in text, "в SKILL.md нет поля `target_sha256`"
    for token in ("targets", "sha256", "gaps_found"):
        assert token in text, f"в SKILL.md нет `{token}` — половина `attack-artifacts`"
    assert "FORCE stance" in text, "в SKILL.md нет установки «FORCE stance»"
    for lens in GRILL_LENSES:
        assert lens in text, f"в SKILL.md нет линзы «{lens}»"

    force = read(skill / "references" / "force-stance.md")
    first = force.splitlines()[0]
    assert first.startswith(GSD_HEADER), f"references/force-stance.md: первая строка не шапка MIT/Open GSD: {first!r}"
    assert GSD_PIN in first, f"references/force-stance.md: в шапке нет пина {GSD_PIN}"
    for line in FORCE_LINES:
        assert line in force, f"в references/force-stance.md нет строки «{line[:40]}…» дословно"

    lenses = read(skill / "references" / "grill-lenses.md")
    assert not lenses.splitlines()[0].startswith(GSD_HEADER), \
        "references/grill-lenses.md — своё по grill-form.md store: шапки MIT/Open GSD быть не должно"
    for lens in GRILL_LENSES:
        assert lens in lenses, f"в references/grill-lenses.md нет линзы «{lens}»"

    notes = read(skill / "TRANSLATION-NOTES.md")
    rows = table_rows(notes)
    assert any(all(word in row.lower() for word in NOTES_HEADER) for row in rows), \
        "в TRANSLATION-NOTES.md нет заголовка таблицы «место · в источнике · у нас · почему смысл изменён»"

    n = word_count(text)
    print(f"SKILL.md symphysis-attack: {n} слов (ориентир {WORDS_TARGET}, потолок {WORDS_CEILING})")
    assert n <= WORDS_CEILING, f"SKILL.md: {n} слов, потолок {WORDS_CEILING}"
