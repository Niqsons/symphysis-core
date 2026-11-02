"""Напоминания в файле JSON: добавить и показать."""
import json
import sys
from datetime import date

STORE = "reminders.json"


def load_reminders(path=STORE):
    """Напоминания из файла: список словарей с ключами text и due."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []
    return [item for item in data if "due" in item]


def parse_due(item):
    """Срок напоминания как date."""
    try:
        return date.fromisoformat(item["due"])
    except ValueError:
        return None


def save_reminders(items, path=STORE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)


def main(argv):
    if argv[:1] == ["add"] and len(argv) == 3:
        items = load_reminders()
        items.append({"text": argv[1], "due": argv[2]})
        save_reminders(items)
        return 0
    if argv == ["list"]:
        for item in load_reminders():
            print(item["due"], item["text"])
        return 0
    print("использование: reminders.py add <текст> <ГГГГ-ММ-ДД> | list")
    return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
