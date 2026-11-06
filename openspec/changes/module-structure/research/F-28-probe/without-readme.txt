### openspec schemas
Available schemas:

  spec-driven
    Default OpenSpec workflow - proposal → specs → design → tasks
    Artifacts: proposal → specs → design → tasks

  symphysis (project)
    Проектирование на сильной модели — намерение → решения (журнал) → исследование и второй круг → proposal → specs → опись последствий → design → security → tasks; атаки решений и артефактов вызываются по имени
    Artifacts: intent → decisions → research → attack-decisions → proposal → specs → consequences → design → security → tasks → attack-artifacts

### openspec status --change module-structure
Change: module-structure
Schema: symphysis
Change root: C:\Users\User\AppData\Local\Temp\tmp.7nKSnnEWXk\proj\openspec\changes\module-structure
Progress: 2/9 artifacts complete (2 optional, not invoked)

[x] intent
[x] decisions
[ ] research
[-] attack-decisions (blocked by: research) (optional, not invoked)
[-] proposal (blocked by: research)
[-] specs (blocked by: proposal)
[-] consequences (blocked by: specs)
[-] design (blocked by: proposal, consequences)
[-] security (blocked by: specs)
[-] tasks (blocked by: specs, design)
[-] attack-artifacts (blocked by: specs, design, security, tasks) (optional, not invoked)

Next: openspec instructions research --change "module-structure" --json
### openspec instructions decisions --change module-structure
<artifact id="decisions" change="module-structure" schema="symphysis">

<task>
Create the decisions artifact for change "module-structure".
Журнал решений — развилки и факты с уликами, решает человек
</task>

<rules>
<!-- These are constraints for you to follow. Do NOT include this in your output. -->
</rules>

<dependencies>
Read the current contents of these files before creating this artifact (re-read them from disk even if you saw them earlier - they may have been edited):

<dependency id="intent" status="done">
  <path>C:\Users\User\AppData\Local\Temp\tmp.7nKSnnEWXk\proj\openspec\changes\module-structure\intent.md</path>
  <description>Намерение человека — его слова дословно и критерии готовности</description>
</dependency>
</dependencies>

<output>
Write to: C:\Users\User\AppData\Local\Temp\tmp.7nKSnnEWXk\proj\openspec\changes\module-structure\decisions.json
</output>

<instruction>
Начни интервью с `intent.md`.
`intent.md` пуст (0 байт или одна строка заголовка) — сначала спроси намерение и сохрани ответ дословно по шаблону, затем круг.
Загрузи скилл `symphysis-brainstorm` и проведи интервью по задаче: развилки и факты записывай в журнал `decisions.json` по шаблону.
Решает человек, не ты: пока его слова нет, запись остаётся открытой.
Улики сверяет `python .symphysis/tools/journal.py check <каталог изменения>/decisions.json` — это сигнал, не стоп.
</instruction>

<template>
<!-- Use this as the structure for your output file. Fill in the sections. -->
{
 "title": "",
 "source": "decisions.json",
 "intro": "",
 "records": []
}
</template>

<success_criteria>
<!-- To be defined in schema validation rules -->
</success_criteria>

<unlocks>
Completing this artifact enables: research
</unlocks>

</artifact>
