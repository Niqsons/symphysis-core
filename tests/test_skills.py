"""Форма скиллов symphysis: frontmatter, копии GSD с шапкой MIT/Open GSD, перечень отличий перевода (F-14).

Чистый Python, без форка и без node. Task 20 сводит сюда проверки всех четырёх скиллов.
"""
import hashlib
import json
import re
import subprocess
import sys

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
# Ориентир владельца. Порога у скиллов нет (бриф 7.1 calibration-fixes, решение контроллера 12; прежний
# потолок 1800 снят): число слов печатается, превышение ориентира несётся владельцу, текст ради числа не ужимается.
WORDS_TARGET = 1500


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


PROVENANCE = re.compile(r"^[ \t]*<!--[ \t]*(?:src|dev)\b.*?-->[ \t]*\r?\n?", re.M | re.S)


def stripped(text):
    """Тело без комментариев провенанса `<!-- src: -->` и `<!-- dev: -->` — то, что уходит в payload."""
    return PROVENANCE.sub("", text)


def table_rows(text):
    return [line for line in text.splitlines() if line.startswith("|")]


SKILL_DIRS = sorted(p for p in SKILLS.glob("symphysis-*/") if p.is_dir())
SKILLS_COUNT = 6
# sources/*.md без шапки GSD: с D4b таких нет — переложение гриля store из атаки убрано,
# все копии несут шапку MIT/Open GSD (исключение было бы явным, не по маске).
OWN_REFERENCES = ()
# Скиллы без источника GSD (F-26: просмотрщик — свой скилл, Playground — образец): sources/ нет
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

    refs = sorted(r for r in (skill / "sources").glob("*.md") if r.name != "TRANSLATION-NOTES.md")
    if skill.name in OWN_SKILLS:
        for ref in refs:
            assert not read(ref).startswith(GSD_HEADER), f"sources/{ref.name}: копия GSD в своём скилле"
    else:
        assert refs, "нет sources/*.md"
    for ref in refs if skill.name not in OWN_SKILLS else ():
        first = read(ref).splitlines()[0]
        if (skill.name, ref.name) in OWN_REFERENCES:
            assert not first.startswith(GSD_HEADER), \
                f"sources/{ref.name} — своё: шапки MIT/Open GSD быть не должно"
            continue
        assert first.startswith(GSD_HEADER), f"sources/{ref.name}: первая строка не шапка MIT/Open GSD: {first!r}"
        assert GSD_PIN in first, f"sources/{ref.name}: в шапке нет пина {GSD_PIN}"

    notes = read(skill / "sources" / "TRANSLATION-NOTES.md")
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
        print(f"ориентир {WORDS_TARGET} превышен на {n - WORDS_TARGET} — к владельцу, не ужимать")


def test_brainstorm_skill_shape():
    skill = SKILLS / "symphysis-brainstorm"
    text = read(skill / "SKILL.md")

    for name in PERSPECTIVES:
        assert name in text, f"в SKILL.md нет перспективы {name}"
    assert "брейншторм закончен по решению человека" in text, "нет строки отказа от нового круга (F-07)"

    notes = read(skill / "sources" / "TRANSLATION-NOTES.md")
    rows = table_rows(notes)
    assert any("числов" in row.lower() or "ambiguity" in row.lower() for row in rows), \
        "в TRANSLATION-NOTES.md нет строки про снятый числовой гейт (ambiguity)"


EDGE_CATEGORIES = ("boundary", "adjacency", "empty", "encoding", "ordering", "precision",
                   "idempotency", "concurrency")
# Заголовки вариантов пробы краёв: «<буква>. <токен> — » и шаблон текста; сам текст конкретен у кандидата (F-61.A).
EDGE_OPTION_HEADS = ("A. Specify — ", "B. Dismiss — ", "C. Backstop — ", "D. Defer — ")
EDGE_FIXED_LINES = (  # прежние фиксированные строки: после F-61.A их в скилле нет
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
    for head in EDGE_OPTION_HEADS:
        assert f"`{head}<" in text, f"в SKILL.md нет заголовка варианта с шаблоном текста: {head!r}"
    assert "Слово нужно у выбора мимо рекомендации, не у отказа" in text, "нет инварианта о слове мимо рекомендации"

    notes = read(skill / "sources" / "TRANSLATION-NOTES.md")
    rows = table_rows(notes)
    assert any("unclassified" in row for row in rows), \
        "в TRANSLATION-NOTES.md нет строки про снятый кандидат `unclassified` (#1110)"


# Значения строки покрытия: как названы в определении и чем начинается хвост строки разобранного примера.
COVERAGE_VALUES = {"`кандидат F-NN`": r"· кандидат F-\d+$",
                   "`не выбран: <край>; <причина>`": r"· не выбран: [^;\n]+; .+$",
                   "`не найдено: <что проверялось>`": r"· не найдено: .+$",
                   "`неприменимо: <причина>`": r"· неприменимо: .+$"}


def test_edge_probe_names_each_coverage_value_with_an_example():
    """Backstop F-69, сценарий «Чтение текста скилла»: каждое значение названо определением
    и встречается в файле покрытия примера; все строки примера — об одном требовании, их восемь."""
    text = read(SKILLS / "symphysis-edge-probe" / "SKILL.md")
    step = text.split("### 5. ")[1].split("\n### ")[0]
    sample = text.split("### 7. ")[1].split("```")[1]
    rows = [line for line in sample.splitlines() if line.startswith("- ")]
    assert [row.split(" · ")[1] for row in rows] == list(EDGE_CATEGORIES), "восемь строк в порядке таблицы категорий"
    assert len({row.split(" · ")[0] for row in rows}) == 1, "примеры значений — на данных одного требования"
    for value, pattern in COVERAGE_VALUES.items():
        assert f"**{value}**" in step, f"в такте 5 нет определения значения {value}"
        assert any(re.search(pattern, row) for row in rows), f"в файле покрытия примера нет значения {value}"


def test_edge_probe_summary_counts_not_selected_rows():
    """F-99: итог пробы не идёт без счёта строк `не выбран`: строка `notes[]` несёт их число и имена требований."""
    summary = flat(read(SKILLS / "symphysis-edge-probe" / "SKILL.md").split("### 10. ")[1].split("\n### ")[0])
    assert "не выбран k: <ключи требований через запятую>" in summary
    assert "число строк `не выбран`" in summary


# Вопрос пробы запретов — дословно (`prohibition-probe.md:53-54`); варианты кандидата — по ярусам проверки.
PROHIBITION_QUESTION = ("What could this feature silently become that the author would NOT want, "
                        "but the spec does not forbid?")
PROHIBITION_QUESTION_RU = "Чем эта возможность может тихо стать"
PROHIBITION_OPTIONS = ("Specify/test", "Specify/judgment", "Dismiss", "Defer")
PROHIBITION_OPTION_HEADS = ("A. Specify/test — ", "B. Specify/judgment — ", "C. Dismiss — ", "D. Defer — ")
PROHIBITION_FIXED_LINES = (  # прежние фиксированные строки: после F-61.A их в скилле нет
    "A. Specify/test — запрет становится требованием spec.md; проверка — тест",
    "B. Specify/judgment — запрет становится требованием spec.md; проверка — суждение, не тест",
    "C. Dismiss — не относится; причина обязательна",
    "D. Defer — отложено; остаётся открытым",
)


def test_prohibition_probe_question_verbatim():
    skill = SKILLS / "symphysis-prohibition-probe"
    text = read(skill / "SKILL.md")

    assert PROHIBITION_QUESTION_RU in text, "в SKILL.md нет вопроса пробы по-русски"
    source = flat(read(skill / "sources" / "prohibition-probe.md").replace("\n> ", "\n"))  # цитата `>` переносится
    assert PROHIBITION_QUESTION in source, "в sources/ нет вопроса GSD дословно"
    assert "security.md" in text, "в SKILL.md нет отсылки канона к `security.md`"
    for token in PROHIBITION_OPTIONS:
        assert token in text, f"в SKILL.md нет варианта {token}"
    for head in PROHIBITION_OPTION_HEADS:
        assert f"`{head}<" in text, f"в SKILL.md нет заголовка варианта с шаблоном текста: {head!r}"

    notes = read(skill / "sources" / "TRANSLATION-NOTES.md")
    rows = table_rows(notes)
    assert any("PROB-06" in row or "гейт" in row.lower() for row in rows), \
        "в TRANSLATION-NOTES.md нет строки про снятый мягкий гейт PROB-06"


# --- конкретные тексты исходов у проб (F-61.A) -------------------------------

PROBE_CASES = (("symphysis-edge-probe", EDGE_OPTION_HEADS, EDGE_FIXED_LINES),
               ("symphysis-prohibition-probe", PROHIBITION_OPTION_HEADS, PROHIBITION_FIXED_LINES))


def example_option_texts(text, heads):
    """Четыре строки варианта из примера кандидата в SKILL.md: начинаются с заголовка без обратных кавычек."""
    lines = [line for line in text.splitlines() if line.startswith(tuple(heads))]
    return lines


@pytest.mark.parametrize("name,heads,fixed", PROBE_CASES)
def test_probe_skill_texts_are_concrete_not_template(name, heads, fixed):
    text = read(SKILLS / name / "SKILL.md")
    shared = read(SHARED / "candidate.md")

    assert "Текст, одинаковый у двух кандидатов" in shared, "нет правила о шаблонном тексте варианта (F-61.A) в candidate.md"
    assert "дефект кандидата" in shared
    assert "`.symphysis/docs/candidate.md`" in text, "тело не называет общий файл candidate.md"
    for line in fixed:
        assert line not in text, f"в SKILL.md остался прежний фиксированный текст: {line!r}"
    example = example_option_texts(text, heads)
    assert len(example) == 4, f"в SKILL.md нужен один пример кандидата с четырьмя вариантами, найдено {len(example)}"
    bodies = [line.split(" — ", 1)[1] for line in example]
    assert len(set(bodies)) == 4, "тексты четырёх вариантов в примере совпадают"
    assert all(len(body) > 40 for body in bodies), "текст варианта в примере слишком короток для конкретики"


PROBE_FIXTURE = ROOT / "tests" / "fixtures" / "probe-candidates"


def test_probe_fixture_candidates_carry_distinct_texts(tmp_path):
    """Кандидаты пробы на fixture: `check` годен, четыре текста каждого попарно различны,
    каждый начинается своим токеном, тексты двух кандидатов не совпадают."""
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"": str(PROBE_FIXTURE)}), encoding="utf-8")
    run = subprocess.run([sys.executable, str(ROOT / "tools" / "journal.py"), "check",
                          str(PROBE_FIXTURE / "decisions.json"), "--roots", str(roots)],
                         capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "[!!]" not in run.stdout

    records = json.loads((PROBE_FIXTURE / "decisions.json").read_text(encoding="utf-8"))["records"]
    edge, prohibition = records
    assert edge["question"].startswith("[encoding") and prohibition["question"].startswith("[запрет]")
    per_candidate = []
    for record, tokens in ((edge, ("Specify", "Dismiss", "Backstop", "Defer")),
                           (prohibition, ("Specify/test", "Specify/judgment", "Dismiss", "Defer"))):
        options = record["options"]
        assert [o["letter"] for o in options] == ["A", "B", "C", "D"]
        bodies = []
        for option, token in zip(options, tokens):
            assert option["text"].startswith(f"{token} — "), f"{record['id']}: текст не начинается с {token}"
            bodies.append(option["text"].split(" — ", 1)[1])
        assert len(set(bodies)) == 4, f"{record['id']}: тексты четырёх вариантов совпадают"
        per_candidate.append(set(bodies))
    assert not per_candidate[0] & per_candidate[1], "тексты двух кандидатов совпадают"


# Установка проверяющих GSD — начала трёх строк «FORCE stance» дословно
# (`agents/gsd-plan-checker.md:30`, `gsd-code-reviewer.md:22`, `gsd-doc-verifier.md:29`).
FORCE_LINES = ("Assume every plan set is flawed until evidence proves otherwise",
               "Assume every submitted implementation contains defects",
               "Assume every factual claim in the doc is wrong until filesystem evidence proves it correct")
# Тяжесть строки атаки — переложение BLOCKER / WARNING / INFO (`agents/gsd-plan-checker.md:39-42`).
ATTACK_SEVERITIES = ("блокер", "предупреждение", "справка")
# Линзы атаки — измерения plan-checker по имени (`gsd-plan-checker.md:376`, `:705`) и слуги колонки
# «Линза»: закрытый список на каждый файл атаки (F-07.A), просмотрщик группирует строки по слугу —
# слово владельца 2026-10-30. Порядок — порядок таблицы SKILL.md и константы ATTACK_LENSES шаблона.
ATTACK_LENSES = ("Context Compliance", "Numeric/Factual Claim Authority")
ATTACK_LENS_LISTS = {
    "journal": ["context-compliance", "claim-authority", "claim-extraction", "coverage"],
    "artifacts": ["scenario-run", "claim-extraction"],
}
# Метки таблиц линз в SKILL.md, шаг 3: таблица файла — первая после метки.
LENS_TABLES = {"journal": "**Линзы журнала**", "artifacts": "**Линзы артефактов**"}
# Линзы присутствия, снятые решением F-07.A: детерминируемое — в `journal.py check` и `openspec validate --strict`.
REMOVED_LENS_SLUGS = ("requirement-coverage", "task-completeness", "dependency-correctness", "key-links",
                      "scope-sanity", "verification-derivation", "scope-reduction", "data-contracts",
                      "research-resolution", "honest-verifier")
# Воздержание honest-verifier: строка, которая не «есть» и не «нет» (`honest-verifier.md:43`).
ABSTENTION_ROW = "по спеке не выводится"
# Одно правило вердикта — то же, что в шаблонах (`tests/test_schema.py::VERDICT_RULE`), дословно в §5 и в приёмке.
VERDICT_RULE = ("`status: passed` ставится, только когда в таблице нет ни одной строки с тяжестью `блокер`; "
                "строки `предупреждение` идут человеку списком и `apply` не держат, строки `справка` не блокируют")
# Копии слоя проверки GSD в sources/ атаки: файл -> строка источника дословно.
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
    assert "| Линза |" in text, "в SKILL.md нет таблицы закрытого списка линз с колонкой «Линза»"
    for slug in {s for lenses in ATTACK_LENS_LISTS.values() for s in lenses}:
        assert f"`{slug}`" in text, f"в SKILL.md нет слуга линзы `{slug}`"
    assert ABSTENTION_ROW in text, f"в SKILL.md нет строки воздержания «{ABSTENTION_ROW}»"
    # правило переносится через строку в §5 — сравнение по схлопнутым пробелам, как `check` сверяет цитаты
    assert " ".join(text.split()).count(VERDICT_RULE) == 2, "правило вердикта — дословно в §5 и в строке приёмки"
    assert "инварианта не несут" in text, "в SKILL.md нет исключения для строк покрытия"
    # журнал — опора артефактов: его правка обесценивает и вердикт `attack-artifacts` (ruling Task 19)
    artifacts_call = block(text, "- Вызов `attack-artifacts`:", "\n- ")
    assert "decisions.json" in artifacts_call, "во «Входе» у вызова `attack-artifacts` нет `decisions.json`"

    force = read(skill / "sources" / "force-stance.md")
    for line in FORCE_LINES:
        assert line in force, f"в sources/force-stance.md нет строки «{line[:40]}…» дословно"
    for name, quote in ATTACK_REFERENCES.items():
        assert quote in read(skill / "sources" / name), f"в sources/{name} нет строки «{quote[:40]}…» дословно"
    assert not (skill / "sources" / "grill-lenses.md").exists(), "гриль store — не источник атаки (D4b)"

    notes = read(skill / "sources" / "TRANSLATION-NOTES.md")
    assert any("store" in row for row in table_rows(notes)), \
        "в TRANSLATION-NOTES.md нет строки про заимствование из store"


# --- атака: линзы следования вместо линз присутствия (7.1: F-07.A, F-12.A, F-08.A, F-09.A, F-23.A,
# F-32.E, F-33.E, F-34.E, F-53.E, F-54.E) ---

ATTACK_SKILL = SKILLS / "symphysis-attack"


def flat(text):
    """Текст в одну строку: переносы markdown не в счёт, как `check` сверяет цитаты."""
    return " ".join(text.split())


def block(text, start, stop):
    """Кусок текста от метки `start` до первой метки `stop` после неё (или до конца), в одну строку."""
    assert start in text, f"в SKILL.md нет «{start}»"
    tail = text[text.index(start):]
    end = tail.find(stop, len(start))
    return flat(tail if end < 0 else tail[:end])


def lens_table(text, marker):
    """Строки данных таблицы линз, первой после метки: от заголовка `| Линза |` до конца таблицы."""
    assert marker in text, f"в SKILL.md нет метки таблицы «{marker}»"
    tail = text[text.index(marker):]
    rows = []
    for line in tail[tail.index("| Линза |"):].splitlines()[2:]:
        if not line.startswith("|"):
            break
        rows.append(line)
    return rows


def lens_row(text, file, slug):
    return next(row for row in lens_table(text, LENS_TABLES[file]) if row.startswith(f"| `{slug}`"))


def test_attack_skill_drops_presence_lenses():
    """F-07.A: линзы присутствия сняты целиком — ни строки таблицы, ни слуга; одна фраза-ссылка
    на `journal.py check` и `openspec validate --strict`."""
    text = read(ATTACK_SKILL / "SKILL.md")
    for slug in REMOVED_LENS_SLUGS:
        assert f"`{slug}`" not in text, f"в SKILL.md остался слуг снятой линзы `{slug}`"
    step4 = block(text, "### 4. Назови линзу", "\n### 5.")
    for token in ("`journal.py check`", "`openspec validate --strict`"):
        assert token in step4, f"в шаге 4 нет фразы-ссылки о снятых линзах: «{token}»"


def test_attack_skill_scenario_run_row_form():
    """F-07.A, F-32.E, F-33.E: строка `scenario-run` — сценарий, механизм, код, исход, THEN; строка на пару;
    механизм не назван — блокер без воздержания; воздержание — только край Defer; покрытие — каждым сценарием."""
    text = read(ATTACK_SKILL / "SKILL.md")
    notes = flat(read(ATTACK_SKILL / "sources" / "TRANSLATION-NOTES.md"))
    assert "`scenario-run`" in notes and "SELF" in notes, "источник `scenario-run` — SELF, в заметках перевода"
    artifacts = block(text, "#### scenario-run", "\n#### claim-extraction")
    for token in ("`<файл>, <требование> / <сценарий>`", "механизм design", "THEN сценария",
                  "`есть: <путь:строка> «код» → исход совпал`",
                  "`нет: <путь:строка> «код» → исход <какой>, THEN <какой>`",
                  "`нет: design не называет механизм`",
                  "Одна строка на пару «сценарий × механизм»", "инвариант каждой — исход по своему коду",
                  "воздержания нет: ответ выводится из design", "исходом `Defer`",
                  "каждый сценарий каждой спеки цели", "нет: не пройдено", "повторить атаку по разделу",
                  "чтением кода и рассуждением"):
        assert token in artifacts, f"в описании строки `scenario-run` нет «{token}»"


def test_attack_skill_reads_does_not_execute():
    """F-53.E: «читает, не исполняет» — отдельный абзац; разрешены чтение и греп; проверка — ревью транскрипта."""
    text = read(ATTACK_SKILL / "SKILL.md")
    rule = block(text, "**Читает, не исполняет.**", "\n\n")
    for token in ("запускать код образца, тесты, сборку или команды цели", "чтение файлов и греп",
                  "`claim-extraction`", "`claim-authority`", "`wc`", "`grep -c`", "`sha256sum`",
                  "ревью транскрипта", "суждение"):
        assert token in rule, f"в правиле «читает, не исполняет» нет «{token}»"


def test_attack_skill_demotion_needs_a_reason():
    """F-54.E, F-136.B: тяжесть «нет» — тяжесть линзы (у всех — блокер); иная — только по слову человека, с записью журнала в скобках той же ячейки."""
    text = read(ATTACK_SKILL / "SKILL.md")
    rule = block(text, "**Понижение тяжести.**", "\n\n")
    for token in ("тяжесть линзы", "`блокер`", "`предупреждение (решено человеком в F-NN)`", "в той же ячейке",
                  "нарушение правила", "«понижение без причины»"):
        assert token in rule, f"в правиле понижения тяжести нет «{token}»"
    for file, slugs in ATTACK_LENS_LISTS.items():
        for slug in slugs:
            assert "блокер" in lens_row(text, file, slug), f"у линзы `{slug}` ({file}) тяжесть «нет» — не блокер"


def test_attack_skill_leaves_journal_hygiene_to_check():
    """F-12.A: гигиену журнала ловит `check` (код 1 / `[!!]`), атака её не репортит."""
    text = read(ATTACK_SKILL / "SKILL.md")
    skip = block(text, "Не репортится", "\n\n")
    for token in ("`факт` без улики", "`recommendation` с пустым `why`", "без `finding`",
                  "буква решения вне вариантов", "`journal.py check`", "код 1", "`[!!]`"):
        assert token in skip, f"в «Не репортится» нет гигиены журнала: «{token}»"
    for file in LENS_TABLES:
        for row in lens_table(text, LENS_TABLES[file]):
            assert "без улики" not in row and "`finding`" not in row and "`why`" not in row, \
                f"гигиена журнала в таблице линз: {row[:60]}"


RECOMMENDATION_WITH_TEXT = re.compile(r"recommendation[^{}\n]*\{[^}\n]*\btext\b")


def test_no_skill_teaches_the_text_of_a_recommendation():
    """F-05, F-11, F-32: у рекомендации только `option` и `why`, образцы не учат писать `text`."""
    found = [f"{path.relative_to(ROOT)}:{number}"
             for path in sorted(SKILLS.rglob("*.md"))
             for number, line in enumerate(read(path).splitlines(), 1)
             if RECOMMENDATION_WITH_TEXT.search(line)]
    assert found == []


@pytest.mark.parametrize("skill", ["symphysis-brainstorm", "symphysis-edge-probe", "symphysis-prohibition-probe",
                                   "symphysis-consequences"])
def test_skill_describes_why_as_the_reason_against_other_options(skill):
    """F-05, F-21: `why` — причина выбора этого варианта против других, а не пересказ варианта.
    У тел, вынесших форму кандидата в общий файл `candidate.md`, норма стоит там (канон, раздел 8)."""
    text = flat(read(SKILLS / skill / "SKILL.md"))
    if "`.symphysis/docs/candidate.md`" in text:
        text = flat(read(SHARED / "candidate.md"))
    assert "{option, why}`" in text
    assert "`why` — причина выбора этого варианта против других, а не пересказ варианта" in text


def test_attack_skill_finds_a_why_that_retells_the_option():
    """F-21: находка под линзой `context-compliance`, закрытый список линз не растёт."""
    row = block(read(ATTACK_SKILL / "SKILL.md"), "#### context-compliance", "\n#### claim-authority")
    assert "`recommendation.why` пересказывает вариант и не называет причины выбора против других" in row


def test_attack_skill_context_compliance_sees_the_setting():
    """F-08.A, F-09.A, F-55.E: решение против факта постановки без пометки — находка; выбранный вариант
    с полем `deviation` — справка без слова человека (видимость без замка); опора решения design на факт
    или на запись без решения — блокер."""
    row = block(read(ATTACK_SKILL / "SKILL.md"), "#### context-compliance", "\n#### claim-authority")
    for token in ("`addressee: постановка`", "выбранный вариант", "пометки «отступление от постановки»",
                  "поле `deviation: F-NN` варианта",
                  "выбранный вариант с полем `deviation` — `справка`, опора «есть: deviation F-NN у выбранного "
                  "варианта»; слово человека не требуется",
                  "опора решения design на факт или на запись без решения", "блокер"):
        assert token in row, f"в строке `context-compliance` нет «{token}»"
    assert "словом человека" not in row, "справка при отступлении не требует слова человека (F-55.E)"
    notes = flat(read(ATTACK_SKILL / "sources" / "TRANSLATION-NOTES.md"))
    assert "с пометкой и словом человека" not in notes
    assert "с полем `deviation` у выбранного варианта — `справка`, слово человека не требуется" in notes


def test_attack_skill_cell_rule():
    r"""F-23.A, F-34.E: черта — `\|` или внутри backticks; `\\|` — косая и черта в цитате кода; пустых ячеек нет.
    Хозяин нормы — общий файл `attack-table.md` (Р9-A, канон раздел 8): пишет атака, читает просмотрщик."""
    rule = block(read(SHARED / "attack-table.md"), "## Правило ячейки", "\n## ")
    for token in (r"`\|`", "внутри backticks", "Цитата кода — в backticks", r"`\\|`", r"`\\`",
                  "следующая черта — разделитель", "Пустых ячеек нет", "`—`", "код 2",
                  "файлом, строкой и столбцом",
                  r"Литеральная обратная косая в цитате кода пишется `\\`", r"внутри backticks `\\|` читается как `\|`"):
        assert token in rule, f"в правиле ячейки нет «{token}»"


def test_attack_skill_target_paths_relative_to_change_dir():
    """Дополнение контроллера 13: форк считает `path` и `target` от каталога изменения — хеш печатается
    из каталога изменения, путь с префиксом `openspec/changes/<имя>/` даёт вечный `stale`."""
    text = read(ATTACK_SKILL / "SKILL.md")
    assert "sha256sum <каталог изменения>/" not in text, "хеш с префиксом каталога: такой путь в `path:` — вечный stale"
    assert "cd <каталог изменения> && sha256sum decisions.json" in text
    # Git Bash печатает `<хеш> *<путь>`: путь с `*` в `path:` дал бы вечный stale (финальное ревью, minor 8)
    assert "но без `*`" in text and "`<хеш> *<путь>`" in text
    assert "cd <каталог изменения> && find specs -name '*.md'" in text
    files = block(text, "### 1. Войди", "\n### 2.")
    for token in ("относительно каталога изменения", "`specs/<cap>/spec.md`", "`openspec/changes/<имя>/`",
                  "`stale`"):
        assert token in files, f"в «Файлы и команды» нет правила пути цели: «{token}»"


def test_attack_translation_notes_name_self_and_removed_dimensions():
    """`scenario-run` — измерение SELF; снятые измерения plan-checker — с причиной (F-07.A); выписки GSD помечены."""
    notes = table_rows(read(ATTACK_SKILL / "sources" / "TRANSLATION-NOTES.md"))
    assert any("`scenario-run`" in row and "SELF" in row and "F-03" in row for row in notes), \
        "в TRANSLATION-NOTES.md нет строки о `scenario-run` как измерении SELF"
    removed = [row for row in notes if "F-07.A" in row and all(f"`{s}`" in row for s in REMOVED_LENS_SLUGS)]
    assert removed, "в TRANSLATION-NOTES.md нет строки о снятых измерениях с причиной F-07.A"
    assert "`journal.py check`" in removed[0] and "`openspec validate --strict`" in removed[0]
    for name in ("plan-checker-dimensions.md", "honest-verifier.md"):
        mark = read(ATTACK_SKILL / "sources" / name).splitlines()[1]
        assert "F-07.A" in mark and "не линз" in mark, f"sources/{name}: нет пометки «не линза после F-07.A»"
    assert "Requirement Coverage" in read(ATTACK_SKILL / "sources" / "plan-checker-dimensions.md").splitlines()[1]


# --- просмотрщик: линзы атаки и перспективы интервью не смешиваются (слово владельца 2026-10-30) ---

TEMPLATE = ROOT / "tools" / "playground-template.html"
# Русские имена перспектив — таблица `symphysis-brainstorm/SKILL.md`, шаг 2 (взяты оттуда, не придуманы).
PERSPECTIVES_RU = ("Исследователь", "Упрощатель", "Хранитель границ", "Аналитик отказов", "Закрывающий")


def skill_lens_lists():
    """Закрытые списки линз SKILL.md атаки по файлам: слуги таблицы после метки файла в порядке строк."""
    text = read(SKILLS / "symphysis-attack" / "SKILL.md")
    return {file: [re.match(r"\| `([^`]+)`", row).group(1) for row in lens_table(text, marker)]
            for file, marker in LENS_TABLES.items()}


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
    # F-07.A: журнал и артефакты — свои закрытые списки, порядок — порядок списка; скилл и шаблон — буква в букву
    assert skill_lens_lists() == ATTACK_LENS_LISTS, f"таблицы линз SKILL.md: {skill_lens_lists()}"
    assert template_lens_lists() == ATTACK_LENS_LISTS, f"ATTACK_LENSES шаблона: {template_lens_lists()}"


def test_template_lenses_equal_the_skill_tables():
    # финальное ревью, minor 12: шаблон сверяется с таблицами скилла напрямую, а не только через константу теста
    skill, template = skill_lens_lists(), template_lens_lists()
    assert set(template) == {"journal", "artifacts"}
    assert template == skill, f"ATTACK_LENSES шаблона {template} ≠ таблицы SKILL.md {skill}"


def test_template_keeps_perspectives_out_of_attack_mode():
    brainstorm = read(SKILLS / "symphysis-brainstorm" / "SKILL.md")
    for name in PERSPECTIVES_RU:
        assert name in brainstorm, f"имя перспективы «{name}» не из таблицы брейншторма"
    text = read(TEMPLATE)
    for name in PERSPECTIVES + PERSPECTIVES_RU:
        assert name not in text, f"перспектива интервью «{name}» в шаблоне — перспективы живут в брейншторме"
    assert not set(template_lens_slugs()) & set(PERSPECTIVES)


def test_template_names_attack_not_grill():
    text = read(TEMPLATE)
    assert "Гриль" not in text and "гриль" not in text, "гриля после D4b нет"
    assert "attack/decisions.md" in text and "attack/artifacts.md" in text
    assert "'attack.md'" not in text, "общего attack.md после D4b нет: два файла атаки"


# --- symphysis-viewer: свой скилл, Playground — образец (F-26, слово владельца 2026-10-30) ---

VIEWER_MAIN_RULE = "вывод модели — развилка"


CANON_SECTIONS = ("## Вход", "## Выход", "## Инварианты", "## Порядок", "## Коды и сигналы", "## Границы", "## Приёмка")


def canon_sections(text):
    """Разделы `##` тела в порядке появления — скелет канона (docs/skills-canon.md, раздел 2)."""
    return [line for line in text.splitlines() if line.startswith("## ")]


def test_viewer_skill_shape():
    """Канон: тело по скелету — инварианты (решает человек, всё показано, рендер не правится, запись и строка
    атаки не смешиваются), три режима в шаге 1, команды в шаге 2, правило развилки — в «Границах» с хозяином;
    sources/ без копий GSD; TRANSLATION-NOTES — по `playground/SKILL.md`: что взято как образец и что сделано
    иначе; Playground в теле продукта не назван — провенанс."""
    skill = SKILLS / "symphysis-viewer"
    text = read(skill / "SKILL.md")
    assert canon_sections(text) == list(CANON_SECTIONS), canon_sections(text)
    for token in ("render-html", "apply", "маловероятно", "--attack", "check", "render-md", "answers/",
                  "вердиктом не считается", "`.symphysis/docs/terms.md`", "`.symphysis/docs/journal-cli.md`",
                  "`.symphysis/docs/attack-table.md`"):
        assert token in text, f"в SKILL.md нет «{token}»"
    for mode in ("«решения»", "«проверка»", "«атака»"):
        assert mode in block(text, "### 1.", "### 2."), f"в шаге 1 нет режима {mode}"
    invariants = block(text, "## Инварианты", "\n## ")
    assert "линз" in invariants and "строка атаки" in invariants, "разделение записи и строки атаки — инвариант"
    assert "MUST" in invariants, "инварианты без уровня RFC 2119"
    assert VIEWER_MAIN_RULE in block(text, "## Границы", "\n## "), "правило развилки — в «Границах», хозяин — rules конфигурации"
    assert "Playground" not in stripped(text), "образец Playground — провенанс, в теле продукта его нет"
    refs = sorted(r for r in (skill / "sources").glob("*.md") if r.name != "TRANSLATION-NOTES.md") if (skill / "sources").is_dir() else []
    assert not any(read(r).startswith(GSD_HEADER) for r in refs), "своё: копий GSD нет"
    notes = read(skill / "sources" / "TRANSLATION-NOTES.md")
    assert any("playground/SKILL.md" in row for row in table_rows(notes)), \
        "в TRANSLATION-NOTES.md нет строки по playground/SKILL.md"
    for token in ("Single HTML file", "presets", "browser storage", "apply"):
        assert token in notes, f"в TRANSLATION-NOTES.md нет «{token}»"


SHARED = ROOT / "skills" / "shared"


def test_viewer_skill_describes_the_attack_mode():
    """Р9-A: в теле — когда режим «атака» и куда уходит спор; поведение страницы и правило ячейки — общий
    файл `attack-table.md` (хозяин нормы — атака, страница только показывает)."""
    text = read(SKILLS / "symphysis-viewer" / "SKILL.md")
    mode = block(text, "режим «атака»", "\n- ")
    for token in ("`attack/decisions.md`", "`attack/artifacts.md`", "по линзам и тяжести", "`notes[]`",
                  "`.symphysis/docs/attack-table.md`"):
        assert token in flat(text), f"в теле нет «{token}»"
    assert "Researcher" not in text and "Исследователь" not in text
    table = " ".join(read(SHARED / "attack-table.md").split())
    points = {
        "счётчики вне фильтра": ("блокеров N · предупреждений N · справок N", "вне фильтра", "по всему файлу"),
        "фильтр по линзе": ("прячет группы, но не счётчики",),
        "блок записи": ("`F-NN, поле`", "переход, не слияние"),
        "списки линз": ("`context-compliance`", "`claim-authority`", "`scenario-run`", "группа «вне списка»", "в счётчике линз её нет"),
        "понижение": ("понижение без причины", "в скобках", "по спеке не выводится"),
        "правило ячейки": ("`\\|`", "внутри backticks", "`\\\\|`", "Пустых ячеек нет", "код 2", "файлом, строкой и столбцом"),
        "строки атаки и apply": ("Строки атаки `apply` не меняет",),
    }
    for point, tokens in points.items():
        for token in tokens:
            assert token in table, f"в attack-table.md ({point}) нет «{token}»"


# --- брейншторм: намерение первым, факты постановки, отступление, предписание (7.2: F-13.A, F-08.A, F-09.A,
# F-17.A, F-28.E, F-43.E, F-44.E, F-55.E) ---

BRAINSTORM = SKILLS / "symphysis-brainstorm"
VIEWER = SKILLS / "symphysis-viewer"


def brainstorm():
    return read(BRAINSTORM / "SKILL.md")


def test_brainstorm_reads_intent_first():
    """(а) Круг 1 начинается с `intent.md`: каждый критерий — факт `addressee: постановка` с дословной цитатой
    и путём от корня проекта; факты постановки — первые записи; `intent.md` не правится."""
    text = brainstorm()
    step = block(text, "### 1.", "### 2.")
    for token in ("Первым — `<каталог изменения>/intent.md`", "Каждый критерий готовности", "`addressee: постановка`",
                  "дословно", "`openspec/changes/<имя>/intent.md`", "первые записи журнала",
                  "`intent.md` не правится"):
        assert token in step, f"в шаге 1 нет «{token}»"
    assert "живёт записями журнала" in block(text, "## Инварианты", "\n## ")
    assert text.index("### 1. Прочитай намерение") < text.index("### 3. Прочитай материалы"), "материалы читаются после intent.md"
    assert "дальше файл не правится" in block(text, "## Границы", "\n## ")


def test_brainstorm_fills_an_empty_intent_first():
    """F-24.E, финальное ревью П.3: форк засчитывает `intent` по существованию файла, в том числе пустого;
    пустой `intent.md` (0 байт или одна строка заголовка) — сначала намерение дословно по шаблону, затем круг."""
    step = " ".join(block(brainstorm(), "### 1.", "### 2.").split())
    for token in ("**`intent.md` пуст** (0 байт или одна строка заголовка)", "по существованию файла",
                  "сначала спроси намерение и сохрани ответ дословно по шаблону `intent.md`", "затем круг"):
        assert token in step, f"в шаге 1 нет «{token}»"
    assert step.index("`intent.md` пуст") < step.index("Критериев ноль")
    assert "пустой файл заполняется его ответом дословно" in block(brainstorm(), "## Границы", "\n## ")


def test_brainstorm_asks_for_criteria_when_there_are_none():
    """(б) F-43.E: нуль критериев — первый вопрос «назови критерии готовности» и строка `notes[]`; ответ
    «Без критериев готовности» — факт постановки, критерии заполнены."""
    step = block(brainstorm(), "### 1.", "### 2.")
    for token in ("Критериев ноль", "первый вопрос человеку", "«назови критерии готовности»",
                  "«намерение без критериев»", "`notes[]`", "«Без критериев готовности»",
                  "критерии заполнены", "`<каталог изменения>/answers/<дата>-criteria.md`"):
        assert token in step, f"в шаге 1 нет «{token}»"


def test_brainstorm_second_round_does_not_duplicate_setting_facts():
    """(в) F-44.E: факт с той же цитатой второй раз не заводится; изменённый текст — новый факт по слову человека."""
    step = block(brainstorm(), "### 1.", "### 2.")
    for token in ("Второй круг", "с той же цитатой второй раз не заводится", "изменился",
                  "только по слову человека"):
        assert token in step, f"в шаге 1 нет «{token}»"


def test_brainstorm_marks_a_deviation_from_the_setting():
    """(г) F-08.A, F-28.E, F-55.E: вариант против сценария факта постановки несёт поле `deviation: F-NN` —
    пометка у варианта, не у записи; уточнение без противоречия — без поля; пометка не замок."""
    rule = block(brainstorm(), "#### Отступление от постановки", "\n#### ")
    for token in ("`options[].deviation: F-NN`", "противоречит сценарию факта", "`addressee: постановка`",
                  "у варианта, не у записи", "Уточнение без противоречия", "без поля", "видимость, не замок",
                  "Решает человек", "выбранный вариант", "«Отступления от постановки»"):
        assert token in rule, f"в правиле отступления нет «{token}»"


def test_brainstorm_turns_a_prescription_into_a_fork():
    """(д) F-09.A: находка, из которой напрашивается конструкция, — факт-наблюдение и развилка с вариантами
    и рекомендацией; предписания в `consequences` факта нет."""
    rule = block(brainstorm(), "**Находка с конструкцией — развилка, не предписание.**", "\n<!--")
    for token in ("«по образцу X»", "«требует новой …»", "факт-наблюдение", "развилку с вариантами",
                  "образец X", "иной путь", "маловероятные с причиной", "рекомендацией",
                  "не предписание в `consequences`"):
        assert token in rule, f"в правиле предписания нет «{token}»"


def test_brainstorm_names_the_keep_as_is_option_by_the_render_prefix():
    """(е) Вариант «ничего не менять» начинается словами «Оставить как есть» — тем префиксом, по которому
    `render-design` ставит пометку «конструкция не меняется»."""
    import journal_render
    text = flat(brainstorm())
    for token in ("«Оставить как есть»", "«конструкция не меняется»"):
        assert token in text, f"в SKILL.md нет «{token}»"
    assert "оставить как есть" in journal_render.UNCHANGED_PREFIXES
    assert journal_render._is_unchanged("Оставить как есть: цена выше пользы")


def test_brainstorm_word_to_a_choice_is_optional():
    """(ж) F-55.E: слово к выбору необязательно — строка `- F-NN: X — (без слова)` законна."""
    viewer = block(read(VIEWER / "SKILL.md"), "### 5.", "### 6.")
    for token in ("`- F-NN: X — (без слова)` законна", "просит слово"):
        assert token in viewer, f"в шаге 5 просмотрщика нет «{token}»"
    assert "скилл `symphysis-viewer`" in block(brainstorm(), "### 8.", "### 9."), "брейншторм называет хозяина круга"


def test_second_round_lives_at_the_end_of_research():
    """(з) Второй круг брейншторма — в конце шага `research`, после отчётов, не в `attack-decisions`
    (схема: instruction `research`); то же в описании и тексте просмотрщика."""
    text = brainstorm()
    description = frontmatter(text)["description"]
    assert "instruction артефакта `decisions` или `research`" in description
    assert "`attack-decisions`" not in description
    body = flat(text)
    for stale in ("instruction `attack-decisions`", "(спросит `attack-decisions`)", "второго круга перед атакой"):
        assert stale not in body, f"в SKILL.md брейншторма осталось «{stale}»"
    assert "в конце шага `research`" in body
    notes = flat(read(BRAINSTORM / "sources" / "TRANSLATION-NOTES.md"))
    for stale in ("второй круг из `attack-decisions`", "instruction артефакта `attack-decisions`",
                  "второй круг по схеме идёт из `attack-decisions`"):
        assert stale not in notes, f"в TRANSLATION-NOTES.md брейншторма осталось «{stale}»"
    assert "в конце шага `research`" in notes
    schema = read(ROOT / "openspec" / "schemas" / "symphysis" / "schema.yaml")
    research = schema.split("  - id: research")[1].split("  - id: ")[0]
    assert "Второй круг брейншторма — после отчётов" in research and "symphysis-brainstorm" in research

    viewer = read(VIEWER / "SKILL.md")
    for part in (frontmatter(viewer)["description"], flat(viewer)):
        assert "второй круг перед `attack-decisions`" not in part
        assert "второго круга перед `attack-decisions`" not in part
    assert "второй круг в конце `research`" in frontmatter(viewer)["description"]
    assert "второй круг в конце шага `research`" in flat(viewer)


def test_viewer_card_names_the_deviation_badge():
    """Вариант с `deviation` — бейдж «отступление от F-NN» у этого варианта; слово к выбору и тогда необязательно."""
    card = block(read(VIEWER / "SKILL.md"), "режим «решения»", "режим «проверка»")
    for token in ("`deviation`", "бейдж «отступление от F-NN»", "У варианта", "необязательно"):
        assert token in card, f"в разделе «Решения» нет «{token}»"


# Fixture-изменение после круга 1: `intent.md` с критерием из сценария «Намерение прочитано первым» и журнал,
# каким его оставляет круг 1 по правилу скилла. Модель в тесте не запускается — проверяется форма результата.
INTENT_FIXTURE = ROOT / "tests" / "fixtures" / "intent-demo"
INTENT_PATH = "openspec/changes/intent-demo/intent.md"
SCENARIO_CRITERION = '`businessId=""` → дочерний экземпляр без бизнес-идентификатора'
# Эталон `intent.md` fixture — SHA-256 его байтов (`*.md` в рабочей копии — CRLF по `.gitattributes`):
# круг 1 файл не правит (F-13.A).
INTENT_SHA256 = "86d4a88c859a64013664a255fa63075d499c7de2ec4860701c23a8097ad44693"


def test_round_one_on_an_intent_starts_with_a_setting_fact(tmp_path):
    """7.2: `check` годен; первая запись — факт `addressee: постановка` с цитатой критерия из сценария спеки,
    цитата дословно в `intent.md`; каждый критерий — один факт постановки, они идут первыми; `intent.md`
    побайтно равен эталону; развилка против сценария факта несёт `deviation`."""
    roots = tmp_path / "roots.json"
    roots.write_text(json.dumps({"openspec/changes/intent-demo/": str(INTENT_FIXTURE)}), encoding="utf-8")
    run = subprocess.run([sys.executable, str(ROOT / "tools" / "journal.py"), "check",
                          str(INTENT_FIXTURE / "decisions.json"), "--roots", str(roots), "--strict"],
                         capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stdout + run.stderr
    assert "[!!]" not in run.stdout + run.stderr

    intent = INTENT_FIXTURE / "intent.md"
    assert hashlib.sha256(intent.read_bytes()).hexdigest() == INTENT_SHA256, "intent.md изменён"
    lines = intent.read_text(encoding="utf-8").splitlines()
    criteria = [line[2:] for line in lines[lines.index("## Критерии готовности"):] if line.startswith("- ")]

    records = json.loads((INTENT_FIXTURE / "decisions.json").read_text(encoding="utf-8"))["records"]
    first = records[0]
    assert (first["kind"], first["addressee"], first["status"]) == ("факт", "постановка", "решён")
    assert first["evidence"] == [{"path": INTENT_PATH, "quote": SCENARIO_CRITERION}]
    assert any(SCENARIO_CRITERION in line for line in lines), "цитата не дословно из intent.md"

    setting = [r for r in records if r["addressee"] == "постановка"]
    assert records[:len(setting)] == setting, "факты постановки — первые записи"
    quotes = [r["evidence"][0]["quote"] for r in setting]
    assert sorted(quotes) == sorted(criteria) and len(set(quotes)) == len(quotes), "по одному факту на критерий"

    fork = next(r for r in records if r["kind"] == "развилка")
    marks = {o["letter"]: o.get("deviation") for o in fork["options"]}
    assert marks == {"A": None, "B": first["id"]}, "отступает вариант B, уточняющий A пометки не несёт"
    assert "deviation" not in fork and fork["decision"] is None, "пометка у варианта; решает человек"


def test_brainstorm_asks_for_criteria_only_while_there_are_no_setting_facts():
    """Ревью: `intent.md` не правится, поэтому условие вопроса смотрит и в журнал — критериев ноль в `intent.md`
    и фактов постановки нет; названные в `answers/<дата>-criteria.md` критерии уже дали факты — во втором круге
    вопрос не задаётся, второй строки `notes[]` нет."""
    step = block(brainstorm(), "### 1.", "### 2.")
    for token in ("в `intent.md` их нет", "и фактов `addressee: постановка` в журнале нет",
                  "Факты постановки в журнале уже есть", "вопрос не задаётся", "второй строки `notes[]` нет"):
        assert token in step, f"в шаге 1 нет «{token}»"
    branch = step.split("Критериев ноль")[1].split("«назови критерии готовности»")[0]
    assert "фактов `addressee: постановка` в журнале нет" in branch, "условие ветки — и по intent.md, и по журналу"


# --- decision-scheme: схема, круги без потолка, антиподы (F-22, F-44, F-50, F-56, F-102, F-110, F-114) ---

def test_brainstorm_creates_the_scheme_on_the_first_round():
    """Сценарии «Сценарий есть», «Сценария нет», «Файл уже есть», «Повтор после обрыва», «Файл появился перед записью»."""
    step = block(brainstorm(), "### 2.", "### 3.")
    for token in ("`<каталог изменения>/scheme.md`", "первом круге", "Файла нет, сценарий в `intent.md` есть", "Файла нет и сценария нет",
                  "предложи своё видение", "Файл есть", "не меняй его и дай на него ссылку", "не различаются",
                  "Перед записью проверь ещё раз", "не перезаписывай", "покажи свой вариант в чате"):
        assert token in step, f"в шаге 1 нет «{token}»"


def test_brainstorm_changes_the_scheme_only_by_the_word():
    """Сценарии «Новый круг с новыми решениями» и «Человек попросил правку», F-22."""
    step = block(brainstorm(), "### 2.", "### 3.")
    for token in ("только по слову человека", "Просит поправить", "правишь файл и даёшь ссылку"):
        assert token in step, f"в шаге 2 нет «{token}»"
    assert "`nodes`" in block(brainstorm(), "### 6.", "### 7."), "модель ставит `nodes` при записи"


def test_brainstorm_does_not_supervise_the_scheme():
    """Запрет F-102: при закрытии круга о схеме не спрашивает и утверждения не ждёт."""
    closing = block(brainstorm(), "### 10.", "## Коды и сигналы")
    assert "scheme.md" not in closing and "схем" not in closing
    assert "При закрытии круга о схеме не спрашивай и утверждения файла не жди" in block(brainstorm(), "### 2.", "### 3.")
    assert "не надзирает за схемой" in block(brainstorm(), "## Границы", "## Приёмка")


def test_brainstorm_has_no_ceiling_of_rounds():
    """F-44: потолка нет, конец — отказ человека или круг без нового; при парковках спрашивает `research` (F-95)."""
    text = brainstorm()
    assert "два круга" not in text and "N = 2" not in text and "третьего круга нет" not in text
    closing = block(text, "### 10.", "## Коды и сигналы")
    assert "K = 0 и M = 0" in closing and "только если и D = 0" in closing
    assert closing.index("P > 0") < closing.index("K = 0 и M = 0"), "парковки проверяются раньше конца брейншторма"
    assert "Начать новый круг?" in closing


def test_brainstorm_round_after_the_end_line():
    """F-96: строка о конце брейншторма новому кругу не мешает."""
    closing = block(brainstorm(), "### 10.", "## Коды и сигналы")
    assert "Строка о конце брейншторма новому кругу не мешает" in closing
    assert "прежняя строка остаётся" in closing


def test_brainstorm_reconciles_antipodes_before_showing_and_after_choice():
    """Сценарии «Пара до показа», «Вариант отвергнут раньше», «Вариант человека», «Антиподов нет», «Пара уже заведена»; F-50, F-51."""
    step = block(brainstorm(), "### 8.", "### 9.")
    for token in ("До показа", "новые варианты между собой и с уже выбранными", "отвергнутые не смотри", "у обоих вариантов",
                  "После выбора", "выбранные за круг решения между собой и с прежними решениями", "Находка — новая развилка",
                  "уже заведена", "новой записи не даёт", "в этом же контексте", "субагента для неё не заводи"):
        assert token in step, f"в шаге 8 нет «{token}»"
    closing = block(brainstorm(), "### 10.", "## Коды и сигналы")
    assert "антиподов A" in closing and "ноль значит «смотрел, таких нет»" in closing


def test_brainstorm_reconciling_does_not_decide_for_the_human():
    """Запрет F-110: судят атака и человек; в тексте скилла запрет назван."""
    step = block(brainstorm(), "### 8.", "### 9.")
    assert "Тексты вариантов, рекомендации и `decision` прежних записей сверка не меняет" in step


def test_attack_both_antipodes_is_a_warning_and_missing_nodes_is_not_a_finding():
    """F-56: оговорка в линзе, как у `deviation`; F-114: отсутствие `nodes` не находка."""
    text = read(SKILLS / "symphysis-attack" / "SKILL.md")
    assert "оба антипода выбраны — `предупреждение (оба антипода выбраны)`" in text
    assert "отсутствие поля `nodes` у записи" in block(text, "Не репортится", "### 5.")


def test_viewer_skill_names_the_fallback_of_the_scheme_panel():
    """F-39: страница больше не всегда один файл; без файла mermaid рядом виден текст."""
    text = read(VIEWER / "SKILL.md")
    assert "`scheme.md` рисунком" in text and "текст вместо рисунка — не ошибка" in text


def test_viewer_skill_text_names_hook_files():
    """Сценарий «Текст скилла»: скилл называет `events.jsonl`, `.symphysis/viewer/` и `answers/` (F-34)."""
    text = read(VIEWER / "SKILL.md")
    for name in ("events.jsonl", ".symphysis/viewer/", "answers/"):
        assert name in text, f"в SKILL.md не названо {name}"
