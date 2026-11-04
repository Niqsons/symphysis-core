// Собирает выдержки исходников opencode v2.2.5 в один файл следа. Строка: "<номер в исходнике>: <текст>".
import fs from "node:fs";
import path from "node:path";

const [, , srcRoot, out] = process.argv;
const spec = [
  ["packages/core/src/session/session.ts", [[155, 191], [286, 327]]],
  ["packages/core/src/session/prompt.ts", [[40, 53], [79, 90]]],
  ["packages/core/src/session/inbox.ts", [[52, 57]]],
  ["packages/core/src/session/run-coordinator.ts", [[14, 15], [131, 140]]],
  ["packages/core/src/session/execution.ts", [[18, 25], [53, 53], [73, 80]]],
  ["packages/core/src/session/execution/restart.ts", [[56, 62]]],
  ["packages/core/src/session/runner/to-llm-message.ts", [[258, 281]]],
  ["packages/core/src/session/title.ts", [[78, 78]]],
  ["packages/schema/src/session-inbox.ts", [[11, 11], [14, 18], [27, 32]]],
  ["packages/schema/src/session-message.ts", [[76, 84], [93, 99]]],
  ["packages/plugin/src/promise/session.ts", [[14, 20], [168, 183], [185, 199], [201, 221]]],
  ["packages/plugin/src/promise/event.ts", [[1, 10]]],
  ["packages/plugin/src/promise/plugin.ts", [[27, 30], [35, 35], [52, 52], [62, 67]]],
  ["packages/plugin/src/promise/adapter.ts", [[331, 342], [627, 627], [633, 633], [637, 637]]],
  ["packages/plugin/src/README.md", [[29, 38]]],
  ["packages/protocol/src/groups/session.ts", [[337, 356], [398, 410], [814, 825]]],
  ["packages/schema/src/session-event.ts", [[39, 57], [122, 130], [244, 249]]],
  ["packages/schema/src/session.ts", [[44, 55], [104, 109]]],
  ["packages/core/src/session/store.ts", [[149, 151], [156, 161], [179, 182], [221, 222]]],
  ["packages/core/src/bus.ts", [[127, 133], [188, 188]]],
  ["packages/core/src/plugin/host.ts", [[266, 282], [594, 594], [615, 615], [628, 628]]],
  ["packages/core/src/location-activity.ts", [[29, 29], [38, 49], [76, 76], [88, 105]]],
  ["packages/core/src/location-services.ts", [[54, 56]]],
  ["packages/schema/src/config/experimental.ts", [[46, 51]]],
  ["packages/cli/src/session-target.ts", [[141, 161]]],
  ["packages/cli/src/run/run.ts", [[74, 76]]],
  ["packages/cli/src/services/server-connection.ts", [[47, 56]]],
  ["packages/cli/src/server-process.ts", [[63, 66], [79, 84], [127, 131]]],
  ["packages/core/src/config/plugin/instruction.ts", [[41, 41], [51, 58]]],
  ["packages/core/src/config/plugin/compatibility.ts", [[44, 45]]],
  ["packages/core/src/config/discovery.ts", [[70, 71], [140, 147]]],
  ["packages/core/src/skill/instructions.ts", [[15, 22]]],
  ["packages/tui/src/component/prompt/index.tsx", [[1234, 1242], [1350, 1356], [1366, 1374], [1398, 1401]]],
  ["packages/tui/src/routes/session/index.tsx", [[1937, 1941], [2102, 2105], [2121, 2128]]],
  ["packages/tui/src/app.tsx", [[227, 228]]],
  ["packages/tui/src/context/session-tabs.tsx", [[236, 245]]],
  ["packages/app/src/session/timeline/message-timeline.tsx", [[214, 220]]],
  ["packages/app/src/composer/comment-note.ts", [[31, 37]]],
];

const lines = [
  "Выдержки исходников opencode, тег v2.2.5, репозиторий anomalyco/opencode (адрес github.com/sst/opencode переводит туда же).",
  "Основа адреса файла: https://raw.githubusercontent.com/anomalyco/opencode/v2.2.5/<путь>",
  "Список файлов смотрел через GitHub API (git/trees этого тега, recursive=1).",
  "Формат: «== путь», затем «<номер строки в исходнике>: <строка>». В цитатах F-49.md номер — строка этого файла. Участки, не весь файл.",
];
for (const [file, ranges] of spec) {
  const text = fs.readFileSync(path.join(srcRoot, file), "utf8").split(/\r?\n/);
  lines.push("", `== ${file}`);
  for (const [from, to] of ranges) {
    for (let n = from; n <= to; n++) lines.push(`${n}: ${text[n - 1]}`);
    lines.push("...");
  }
}
fs.writeFileSync(out, `${lines.join("\n")}\n`, "utf8");
console.log("строк", lines.length);
