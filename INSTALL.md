# Installing

Everything runs on Linux, macOS and Windows via WSL. You need Python 3.12+, a C
compiler with zlib headers, GNU make and git. No emulator or graphics toolkit
has to be installed: the headless emulator is built from the submodule.

## 1. Dependencies

### Ubuntu / Debian / WSL

```bash
sudo apt install build-essential zlib1g-dev python3.12 python3.12-venv git
```

### macOS (Homebrew)

```bash
brew install python@3.12 git           # clang, zlib and make come with the Xcode tools
```

**Windows**: install WSL (Ubuntu) and follow the Ubuntu steps inside it. Keep
the checkout on the Linux side of the file system; `core.autocrlf` on the
Windows side once turned a 14-line emulator patch into a 6600-line diff.

## 2. Clone

```bash
git clone --recurse-submodules https://github.com/eugenez36/golden-axe3-game-rus.git
cd golden-axe3-game-rus
# if you cloned without --recurse-submodules:
git submodule update --init
```

The submodule `emu/gpgx` is Genesis Plus GX on the `ga3/dma-hook` branch of a
fork: upstream plus one 14-line commit (`emu/patches/0001-dma-hook.patch`).

## 3. Python environment

```bash
make venv          # $(PYTHON) -m venv .venv && pip install -e ".[dev,disasm]"
source .venv/bin/activate
ga3 --version
```

If `python3` is older than 3.12 (Ubuntu 22.04, the macOS system Python), name
the interpreter: `make venv PYTHON=python3.12`.

`make` targets use `.venv/bin/…` directly, so activating is optional. Every
`ga3` command finds the project in `$GA3_ROOT` when it is set, otherwise by
walking up to `rom_map.yml`; `--root PATH` overrides both.

## 4. The base ROM

Place your own dump of *Golden Axe III* (Russian translation by NEWGAME, 2003)
at `baserom/ga3.bin`. The exact expected image is listed in
[baserom/README.md](baserom/README.md) (SHA-1 `e9538c05…`). The repository does
not contain and will never contain the ROM; every tool refuses an image with a
different hash unless told otherwise.

## 5. Build and check

```bash
make               # build/ga3.bin + build/ga3.ips from assets/
make verify        # sha1sum -c roms.sha1 and an IPS self-check
make test          # pytest, including the ROM-gated tests now that the ROM is present
make emu           # build/emu/headless_gpgx
make regress       # run every scene in emu/scenes/ against build/ga3.bin, in parallel (JOBS=N)
```

A successful `make verify` on a fresh clone with unchanged assets means the
toolchain reproduces the committed build byte for byte.

## Optional

- `pre-commit install` — ruff, YAML checks, large-file and ROM guards on every commit.
- `ga3 extract --png` — decoded previews of the Nemesis blocks in `build/preview/`.
- `make asm` — regenerate the Capstone listings in `assets/code/asm/`.

## Troubleshooting

| Symptom                                                | Cause / fix                                                                                      |
|--------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| `error: baserom/ga3.bin is missing`                    | step 4                                                                                           |
| `sha1 … does not match rom_map.yml`                    | a different dump or a patched image; use `ga3 extract --rom PATH` only if you know why           |
| `emu/gpgx/core not found`                              | `git submodule update --init`                                                                    |
| `vdp_ctrl.c lacks the dma_hook`                        | the submodule is on upstream instead of `ga3/dma-hook`; `git -C emu/gpgx checkout ga3/dma-hook`  |
| `Pillow is required`                                   | Pillow is a core dependency, so the venv is stale: `make venv` (or `pip install -e .` inside it) |
| `sha1 differs from rom_map.yml` (a note, not an error) | you passed `--rom PATH`; the image is used as is, only the default `baserom/ga3.bin` is verified |
