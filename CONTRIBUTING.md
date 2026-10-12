# Contributing · Как участвовать

Thanks for stopping by the camp. A few rules keep this project honest — and keep
SEGA's lawyers asleep. Conventions live in [STYLE.md](STYLE.md); setup in
[INSTALL.md](INSTALL.md). Russian version follows below · Русская версия ниже.

---

## English

### Ground rules

1. **The ROM never enters git.** Not the reference, not a build, not a "demo".
   `.gitignore` blocks `*.bin`; the pre-commit hook and CI fail on any ROM-shaped
   file. Changes are made to the files in `assets/` and reviewed as diffs; the
   build produces the IPS.
2. **The base ROM is read-only.** Tools read `baserom/ga3.bin` and write to
   `build/`. If a command wants to modify the base ROM, it is a bug.
3. **Nothing is guessed.** An address enters `rom_map.yml` only with an
   `evidence:` field: a watchpoint / breakpoint hit, a disassembly listing, a
   tilemap / VRAM dump, or an in-game screenshot after a poke.

### The four checks

Every change that alters the built image must pass all of these before a PR:

| # | Check | How |
|---|---|---|
| 1 | **Structural** | `make && ga3 diff baserom/ga3.bin build/ga3.bin` shows exactly the expected bytes; `ga3 verify --update` recorded the new hash |
| 2 | **Round-trip** | `ga3 text verify` (text) · `make assets` leaves no diff (font / tables) · `make test` |
| 3 | **In-game** | a scene under `emu/scenes/` run with `ga3 emu`, screenshot attached to the PR |
| 4 | **VRAM parity** | graphics only: repacking unchanged tiles reproduces the same VRAM (covered by `tests/`; extend the fixture if you touch the codec) |

A PR that changes the codec, the character table or the font without check 4
will be sent back — it catches packer bugs no eye can.

### Workflow

```bash
git checkout -b quest/short-name          # features
git checkout -b glitch/short-name         # bug fixes
# edit assets/… or src/ga3/…
make && ga3 verify --update && make test && make lint
ga3 emu emu/scenes/menu_verify.txt        # or the scene that shows your change
```

- Commits: imperative, ≤ 72 chars, English. Asset edits and code changes in
  separate commits when possible, so `git log -- assets/` reads as the
  translation's history.
- PRs are **squash-merged**; the PR title becomes the commit subject.
- Every PR into `main` needs **at least one approving review** from someone
  other than its author; a new push dismisses earlier approvals. The owner may
  merge without one in an emergency, through the PR, never by a direct push.
  GitHub enforces this with a ruleset created by
  `.github/scripts/protect-main.sh` (needs GitHub Pro for a private repository;
  until then the rule is ours to keep).
- Fill in the PR template. The checklist is not decorative.
- New offsets go in `rom_map.yml`, never in code.
- `ruff` is pinned twice, in `pyproject.toml` (`[dev]`) and in
  `.pre-commit-config.yaml` (`rev:`); bump both in the same commit, or the hook
  and `make lint` will disagree.

### Reporting a finding

Found an address, table or routine? Open an issue with the **ROM finding**
template even without code. A verified address with a reproduction scene is
worth more than an unverified patch.

---

## Русский

### Правила лагеря

1. **ROM в git не попадает никогда.** Ни эталон, ни сборка, ни «демо».
   `.gitignore` режет `*.bin`; pre-commit и CI падают на любом файле, похожем на
   ROM. Правки вносятся в файлы `assets/` и читаются как diff; IPS порождает сборка.
2. **Эталон только для чтения.** Инструменты читают `baserom/ga3.bin` и пишут в
   `build/`. Если команда хочет изменить эталон — это баг.
3. **Ничего не угадываем.** Адрес попадает в `rom_map.yml` только с полем
   `evidence:`: срабатывание watchpoint'а / брейкпоинта, листинг дизассемблера,
   дамп тайлмапа / VRAM или скриншот из игры после poke.

### Четыре проверки

Любая правка, меняющая собранный образ, до открытия PR проходит все четыре:

| # | Проверка | Как |
|---|---|---|
| 1 | **Структурная** | `make && ga3 diff baserom/ga3.bin build/ga3.bin` показывает ровно ожидаемые байты; `ga3 verify --update` записал новый хеш |
| 2 | **Round-trip** | `ga3 text verify` (текст) · `make assets` не даёт diff (шрифт / таблицы) · `make test` |
| 3 | **В игре** | сцена из `emu/scenes/`, запущенная через `ga3 emu`; скриншот приложен к PR |
| 4 | **Паритет VRAM** | только графика: перепаковка неизменённых тайлов даёт ту же VRAM (покрыто `tests/`; расширьте фикстуру, если трогали кодек) |

PR, меняющий кодек, таблицу символов или шрифт без проверки 4, будет возвращён —
она ловит ошибки упаковщика лучше любых глаз.

### Порядок работы

```bash
git checkout -b quest/short-name          # новые возможности
git checkout -b glitch/short-name         # исправления
# правки в assets/… или src/ga3/…
make && ga3 verify --update && make test && make lint
ga3 emu emu/scenes/menu_verify.txt        # или сцена, показывающая вашу правку
```

- Коммиты: повелительное наклонение, до 72 знаков, английский. Правки ресурсов и
  кода — по возможности отдельными коммитами, чтобы `git log -- assets/` читался
  как история перевода.
- PR вливаются **squash'ем**; заголовок PR становится заголовком коммита.
- Любой PR в `main` требует **хотя бы одного одобряющего ревью** не от автора;
  новый push сбрасывает прежние одобрения. Владелец в крайнем случае может
  влить PR без ревью, но только через PR, а не прямым push. На стороне GitHub
  это обеспечивает набор правил (ruleset), который создаёт
  `.github/scripts/protect-main.sh` (для приватного репозитория нужен
  GitHub Pro; пока его нет, правило держится на нас).
- Заполняйте шаблон PR. Чеклист там не для красоты.
- Новые смещения — в `rom_map.yml`, никогда в код.
- `ruff` закреплён дважды: в `pyproject.toml` (`[dev]`) и в
  `.pre-commit-config.yaml` (`rev:`); поднимайте обе версии одним коммитом,
  иначе хук и `make lint` разойдутся.

### Сообщить о находке

Нашли адрес, таблицу или подпрограмму? Откройте issue по шаблону **ROM finding**,
даже без кода. Подтверждённый адрес со сценой воспроизведения ценнее непроверенного патча.
