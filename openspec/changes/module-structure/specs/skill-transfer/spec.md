# Spec Delta

## MODIFIED Requirements

### Requirement: Скилл несёт копию источника с copyright notice и перечень смысловых отличий
Каждый скилл `symphysis-*`, переносящий механику GSD, SHALL быть русским текстом с цитатами источника в оригинале там, где цитирует, SHALL держать копию источника в `references/` с его copyright notice (MIT) и SHALL нести `TRANSLATION-NOTES.md` с перечнем мест, где смысл инструкции изменён против источника, с причиной (F-14.A, слово человека «указать, где при переводе произошло изменение смысла»).

#### Scenario: Состав каталога скилла
- **GIVEN** каталог скилла `symphysis-edge-probe` (F-26)
- **WHEN** читается каталог
- **THEN** есть `SKILL.md`, `TRANSLATION-NOTES.md` и `references/edge-probe.md`, в котором есть строка с «Copyright»

#### Scenario: Скилл без источника GSD
- **GIVEN** каталог скилла `symphysis-viewer` (образец — плагин Playground, не GSD)
- **WHEN** читается каталог
- **THEN** `references/` отсутствует, `TRANSLATION-NOTES.md` называет, что взято как образец и что сделано иначе — предположение: правило «копия с notice» распространяется только на скиллы с источником GSD/BMAD (CLAUDE.md «Копии файлов GSD и BMAD»); решить: нужен ли у viewer перечень отличий от Playground в той же форме
<!-- проба краёв: форма=collection, исходы: нет -->
<!-- проба запретов: исходы: нет -->
