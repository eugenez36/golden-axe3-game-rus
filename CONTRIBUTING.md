# Contributing · Как участвовать

Thanks for stopping by the camp. A few rules keep this project honest — and keep SEGA's
lawyers asleep. Russian version follows below · Русская версия ниже.

---

## English

### Ground rules

1. **The ROM never enters git.** Not the reference, not a working copy, not a "demo build".
   `.gitignore` blocks `*.bin`, and CI fails on any `.bin` in the tree. Share changes as
   **IPS patches** (`romlib.py ips`) or as edits to `text/*.txt`.
2. **The reference image is read-only.** All work happens on `work/ga3.bin`. If you find
   yourself wanting to `chmod +w` the reference, stop.
3. **Nothing is guessed.** An address goes into the docs only when it is backed by one of:
   a watchpoint / breakpoint hit, the disassembly, or a tilemap/VRAM dump. Say which.

### The four checks

Every change to ROM contents must pass all of these before a PR is opened:

| # | Check | How |
|---|---|---|
| 1 | **Structural** | `romlib.py diff` shows exactly the expected bytes; checksum recomputed |
| 2 | **Round-trip** | `text_tool.py verify` (text) or re-pack → decode == original (graphics) |
| 3 | **In-game** | headless run with a script under `scripts/`, screenshot attached to the PR |
| 4 | **VRAM parity** | for graphics: re-packing unchanged data yields byte-identical VRAM (all 65 536 bytes) |

A PR that changes a codec, the character table or the font without check 4 will be
sent back — that check catches packer bugs no eye can.

### Workflow

```bash
git checkout -b quest/short-name          # features
git checkout -b glitch/short-name         # bug fixes
# ... work on work/ga3.bin ...
python3 tools/romlib.py ips "Golden Axe 3 (RUS).bin" work/ga3.bin -o out/your-change.ips
./emu/headless/headless_gpgx --rom work/ga3.bin --script scripts/your-check.txt
```

- Commits: imperative mood, ≤ 72 chars, English or Russian — pick one per commit.
- PRs are **squash-merged**; the PR title becomes the commit title, so make it good.
- Fill in the PR template. The checklist is not decorative.
- Code style: Python — `ruff` defaults, 4 spaces; C — 2 spaces, C99, no new warnings.
- Docstrings and journal entries may be in Russian. Public README stays bilingual.

### Reporting a finding

Found a new address, table or routine? Open an issue with the **ROM finding** template
even if you have no code yet. A verified address with a reproduction script is worth more
than an unverified patch.

---

## Русский

### Правила лагеря

1. **ROM в git не попадает никогда.** Ни эталон, ни рабочая копия, ни «демо-сборка».
   `.gitignore` режет `*.bin`, CI падает на любом `.bin` в дереве. Правки передаются
   **IPS-патчами** (`romlib.py ips`) или изменениями в `text/*.txt`.
2. **Эталон только для чтения.** Вся работа идёт на `work/ga3.bin`. Захотелось
   `chmod +w` на эталон — остановись.
3. **Ничего не угадываем.** Адрес попадает в документацию только с подтверждением:
   срабатывание watchpoint'а / брейкпоинта, дизассемблер или дамп тайлмапа/VRAM. Укажи, каким.

### Четыре проверки

Любая правка содержимого ROM до открытия PR проходит все четыре:

| # | Проверка | Как |
|---|---|---|
| 1 | **Структурная** | `romlib.py diff` показывает ровно ожидаемые байты; checksum пересчитана |
| 2 | **Round-trip** | `text_tool.py verify` (текст) или перепаковка → распаковка == оригинал (графика) |
| 3 | **В игре** | прогон headless-эмулятора сценарием из `scripts/`, скриншот приложен к PR |
| 4 | **Паритет VRAM** | для графики: перепаковка без изменений даёт байт-в-байт ту же VRAM (все 65 536 байт) |

PR, меняющий кодек, таблицу символов или шрифт без проверки 4, будет возвращён —
она ловит ошибки упаковщика лучше любых глаз.

### Порядок работы

```bash
git checkout -b quest/короткое-имя        # новые возможности
git checkout -b glitch/короткое-имя       # исправления
# ... работа на work/ga3.bin ...
python3 tools/romlib.py ips "Golden Axe 3 (RUS).bin" work/ga3.bin -o out/your-change.ips
./emu/headless/headless_gpgx --rom work/ga3.bin --script scripts/your-check.txt
```

- Коммиты: повелительное наклонение, до 72 знаков, русский или английский — один язык на коммит.
- PR вливаются **squash'ем**; заголовок PR становится заголовком коммита — формулируй как следует.
- Заполняй шаблон PR. Чеклист там не для красоты.
- Стиль: Python — `ruff` по умолчанию, 4 пробела; C — 2 пробела, C99, без новых предупреждений.
- Докстринги и журнал можно писать по-русски. Публичный README остаётся двуязычным.

### Сообщить о находке

Нашёл новый адрес, таблицу или подпрограмму? Открой issue по шаблону **ROM finding**,
даже без кода. Подтверждённый адрес со сценарием воспроизведения ценнее непроверенного патча.
