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
SKILLS_COUNT = 5
# references/*.md без шапки GSD: с D4b таких нет — переложение гриля store из атаки убрано,
# все копии несут шапку MIT/Open GSD (исключение было бы явным, не по маске).
OWN_REFERENCES = ()
# Скиллы без источника GSD (F-26: просмотрщик — свой скилл, Playground — образец): references/ нет
# или без копий GSD — шапка MIT/Open GSD у них не проверяется, её быть не должно.
OWN_SKILLS = ("symphysis-viewer",)
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
    if skill.name in OWN_SKILLS:
        for ref in refs:
            assert not read(ref).startswith(GSD_HEADER), f"references/{ref.name}: копия GSD в своём скилле"
    else:
        assert refs, "нет references/*.md"
    for ref in refs if skill.name not in OWN_SKILLS else ():
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
ATTACK_LENS_SLUGS = ("requirement-coverage", "task-completeness", "dependency-correctness", "key-links",
                     "scope-sanity", "verification-derivation", "context-compliance", "scope-reduction",
                     "data-contracts", "research-resolution", "claim-authority", "claim-extraction",
                     "honest-verifier", "coverage")
# Воздержание honest-verifier: строка, которая не «есть» и не «нет» (`honest-verifier.md:43`).
ABSTENTION_ROW = "по спеке не выводится"
# Одно правило вердикта — то же, что в шаблонах (`tests/test_schema.py::VERDICT_RULE`), дословно в §5 и в приёмке.
VERDICT_RULE = ("`status: passed` ставится, только когда в таблице нет ни одной строки с тяжестью "
                "`блокер` или `предупреждение`; строки `справка` не блокируют")
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
    # правило переносится через строку в §5 — сравнение по схлопнутым пробелам, как `check` сверяет цитаты
    assert " ".join(text.split()).count(VERDICT_RULE) == 2, "правило вердикта — дословно в §5 и в строке приёмки"
    assert "инварианта не несут" in text, "в SKILL.md нет исключения для строк покрытия"
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


# --- просмотрщик: линзы атаки и перспективы интервью не смешиваются (слово владельца 2026-10-30) ---

TEMPLATE = ROOT / "tools" / "playground-template.html"
# Русские имена перспектив — таблица `symphysis-brainstorm/SKILL.md`, шаг 2 (взяты оттуда, не придуманы).
PERSPECTIVES_RU = ("Исследователь", "Упрощатель", "Хранитель границ", "Аналитик отказов", "Закрывающий")


def skill_lens_slugs():
    """Слуги таблицы линз SKILL.md атаки в порядке строк: от заголовка `| Линза |` до конца таблицы."""
    text = read(SKILLS / "symphysis-attack" / "SKILL.md")
    rows = []
    for line in text[text.index("| Линза |"):].splitlines()[2:]:
        if not line.startswith("|"):
            break
        rows.append(re.match(r"\| `([^`]+)`", line).group(1))
    return rows


def template_lens_lists():
    """Закрытые списки линз шаблона по файлам атаки: `ATTACK_LENSES = { journal: [...], artifacts: [...] }`."""
    text = read(TEMPLATE)
    m = re.search(r"const ATTACK_LENSES = \{(.*?)\n\};", text, re.S)
    assert m, "в шаблоне просмотрщика нет константы ATTACK_LENSES"
    lists = dict(re.findall(r"(journal|artifacts):\s*\[(.*?)\n\s*\],", m.group(1), re.S))
    return {name: re.findall(r"slug:\s*'([^']+)'", body) for name, body in lists.items()}


def template_lens_slugs():
    return [slug for slugs in template_lens_lists().values() for slug in slugs]


def test_template_lenses_match_the_closed_list():
    assert skill_lens_slugs() == list(ATTACK_LENS_SLUGS), "константа теста разошлась с таблицей SKILL.md"
    # F-07.A: журнал и артефакты — свои закрытые списки, порядок — порядок списка
    assert template_lens_lists() == {
        "journal": ["context-compliance", "claim-authority", "claim-extraction", "coverage"],
        "artifacts": ["scenario-run", "claim-extraction"]}, f"ATTACK_LENSES шаблона: {template_lens_lists()}"


def test_template_keeps_perspectives_out_of_attack_mode():
    brainstorm = read(SKILLS / "symphysis-brainstorm" / "SKILL.md")
    for name in PERSPECTIVES_RU:
        assert name in brainstorm, f"имя перспективы «{name}» не из таблицы брейншторма"
    text = read(TEMPLATE)
    for name in PERSPECTIVES + PERSPECTIVES_RU:
        assert name not in text, f"перспектива интервью «{name}» в шаблоне — перспективы живут в брейншторме"
    assert not set(template_lens_slugs()) & set(PERSPECTIVES)


def test_template_scheme_names_attack_not_grill():
    text = read(TEMPLATE)
    assert "Гриль" not in text and "гриль" not in text, "гриля после D4b нет"
    assert "4 Атака журнала" in text and "attack/decisions.md" in text and "attack/artifacts.md" in text
    assert "'attack.md'" not in text, "общего attack.md после D4b нет: два файла атаки"


# --- symphysis-viewer: свой скилл, Playground — образец (F-26, слово владельца 2026-10-30) ---

VIEWER_MAIN_RULE = "вывод модели — развилка"


def test_viewer_skill_shape():
    """D7: главное правило «вывод модели — развилка, а не строка поставки», три режима и что человек делает
    в каждом, порядок команд, правило разделения линз и перспектив одной фразой в «Главном правиле»;
    references/ нет или без копий GSD; TRANSLATION-NOTES — по `playground/SKILL.md`: что взято как образец
    и что сделано иначе."""
    skill = SKILLS / "symphysis-viewer"
    text = read(skill / "SKILL.md")
    assert VIEWER_MAIN_RULE in text, f"в SKILL.md нет «{VIEWER_MAIN_RULE}»"
    for token in ("render-html", "apply", "маловероятно", "--attack", "check", "render-md", "answers/",
                  "сначала запись", "не считается вердиктом"):
        assert token in text, f"в SKILL.md нет «{token}»"
    for mode in ("«решения»", "«проверка»", "«атака»"):
        assert mode in text, f"в SKILL.md нет режима {mode}"
    main = text.split("## Главное правило")[1].split("\n## ")[0]
    assert "линз" in main and "перспектив" in main, "правило разделения линз и перспектив — в «Главном правиле»"
    assert "Playground" in text, "в SKILL.md не назван образец — Playground"
    refs = sorted((skill / "references").glob("*.md")) if (skill / "references").is_dir() else []
    assert not any(read(r).startswith(GSD_HEADER) for r in refs), "своё: копий GSD нет"
    notes = read(skill / "TRANSLATION-NOTES.md")
    assert any("playground/SKILL.md" in row for row in table_rows(notes)), \
        "в TRANSLATION-NOTES.md нет строки по playground/SKILL.md"
    for token in ("Single HTML file", "presets", "browser storage", "apply"):
        assert token in notes, f"в TRANSLATION-NOTES.md нет «{token}»"


def test_viewer_skill_describes_the_attack_mode():
    """6.6: раздел «Атака» несёт фильтр по линзе и счётчики вне фильтра, блок записи, слуги по файлам, понижение,
    промпт из состояния (внесённое уходит, спор «вопрос человеку» → слово к решению, конфликт, выбор без слова)
    и правило ячейки таблицы атаки."""
    text = read(SKILLS / "symphysis-viewer" / "SKILL.md")
    attack = " ".join(text.split("### «Атака»")[1].split("\n## ")[0].split())   # переносы строк не в счёт
    points = {
        "фильтр по линзе": ("Фильтр по линзе", "«все»", "прячет группы строк, но не счётчики"),
        "счётчики вне фильтра": ("блокеров N · предупреждений N · справок N", "вне фильтра", "по всему файлу"),
        "блок записи": ("Блок записи", "`<details>`", "текст вопроса записи", "выбранный вариант", "переход к карточке"),
        "списки линз": ("`context-compliance`, `claim-authority`", "`scenario-run`", "группа «вне списка»", "в счётчике линз её нет"),
        "понижение": ("понижение без причины", "в скобках", "по спеке не выводится"),
        "промпт из состояния": ("Промпт пересобирается из состояния", "внесённое уходит", "очистка поля замечаний"),
        "спор — слово к решению": ("«вопрос человеку»", "`F-NN, decision`", "словом к решению", "`- F-NN: <буква> — «ответ»`"),
        "конфликт ответов": ("конфликт", "оставьте один", "строки слова на запись"),
        "выбор без слова": ("слово к выбору необязательно", "(без слова)"),
        "правило ячейки": ("Правило ячейки", "`\\|`", "`\\\\`", "внутри пары backticks", "`\\\\|`", "код 2"),
    }
    for point, tokens in points.items():
        for token in tokens:
            assert token in attack, f"в разделе «Атака» ({point}) нет «{token}»"
    assert "Researcher" not in attack and "Исследователь" not in attack
