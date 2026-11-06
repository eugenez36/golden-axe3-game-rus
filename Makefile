# Golden Axe III (RUS) — ROM-hacking toolkit
#
#   make            build build/ga3.bin + build/ga3.ips from assets/ (needs baserom/ga3.bin)
#   make extract    take the base ROM apart into assets/
#   make verify     sha1sum -c roms.sha1 + IPS self-check
#   make test       pytest (ROM-gated tests skip when the base ROM is absent)
#   make lint       ruff
#   make assets     refresh derived-but-committed files (encoding.tbl, font.nem, docs/rom_map.md)
#   make asm        Capstone listings for every code segment -> assets/code/asm/
#   make emu        build the headless Genesis Plus GX frontend -> build/emu/headless_gpgx
#   make regress    run every emu/scenes/*.txt against build/ga3.bin, JOBS at a time
#   make banner     capture the title and menu in the emulator -> docs/branding/banner.png
#   make dist       the release files: build/dist/ga3-VERSION.bin, .ips and their sha256
#   make clean      rm -rf build/
#   make distclean  clean + virtualenv + caches
#   make venv       create .venv and install ga3 with the [dev,disasm] extras
#   make help       print this list
#
# Variables: PYTHON (interpreter used to create .venv), GPGX (emulator core dir),
#            JOBS (parallel scenes and emulator compiles; default: CPU count).

PYTHON   ?= python3
JOBS     ?= $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 1)
VENV     ?= .venv
GA3      ?= $(VENV)/bin/ga3
PYTEST   ?= $(VENV)/bin/pytest
RUFF     ?= $(VENV)/bin/ruff
GPGX     ?= $(CURDIR)/emu/gpgx
BASEROM  := baserom/ga3.bin
BUILDROM := build/ga3.bin
EMU      := build/emu/headless_gpgx
SCENES   := $(filter-out emu/scenes/banner.txt,$(wildcard emu/scenes/*.txt))

.DEFAULT_GOAL := build
.PHONY: build extract verify test lint assets asm emu regress banner dist clean distclean venv help

build: $(GA3) $(BASEROM) rom_map.yml
	$(GA3) build

extract: $(GA3) $(BASEROM)
	$(GA3) extract

verify: build
	$(GA3) verify
	@if command -v sha1sum >/dev/null; then sha1sum -c roms.sha1; else shasum -c roms.sha1; fi

test: $(PYTEST)
	$(PYTEST) -q

lint: $(RUFF)
	$(RUFF) check src tests
	$(RUFF) format --check src tests

assets: $(GA3)
	$(GA3) assets refresh

asm: $(GA3) $(BASEROM)
	$(GA3) asm

emu:
	$(MAKE) -C emu/headless check-core GPGX=$(GPGX)
	$(MAKE) -C emu/headless -j$(JOBS) GPGX=$(GPGX) BUILD=$(CURDIR)/build/emu

regress: build emu
	@# scenes write disjoint files, so they run in parallel; xargs fails if any scene does
	@printf '%s\n' $(SCENES) | xargs -P $(JOBS) -I{} \
	  sh -c 'echo "== {}"; $(EMU) --rom $(BUILDROM) --script {} --quiet || { echo "FAILED {}"; exit 1; }'

banner: build emu
	rm -rf build/shots/banner
	$(EMU) --rom $(BUILDROM) --script emu/scenes/banner.txt --quiet
	$(GA3) banner-anim

dist: verify
	@# the files a GitHub release carries: the image for players, the patch for a base dump
	@ver=$$($(GA3) --version | cut -d' ' -f2) && mkdir -p build/dist && \
	  cp $(BUILDROM) build/dist/ga3-$$ver.bin && cp build/ga3.ips build/dist/ga3-$$ver.ips && \
	  (cd build/dist && sha256sum ga3-$$ver.bin ga3-$$ver.ips > ga3-$$ver.sha256) && \
	  ls -l build/dist/ga3-$$ver.*

clean:
	rm -rf build/

distclean: clean
	rm -rf $(VENV) .ruff_cache .pytest_cache src/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

# -- tooling --------------------------------------------------------------

# One install per change of pyproject.toml: the stamp keeps `make build test lint`
# from running pip three times on a cold tree.
STAMP := $(VENV)/.installed

venv: $(STAMP)

$(GA3) $(PYTEST) $(RUFF): $(STAMP)

$(STAMP): pyproject.toml
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -q --upgrade pip
	$(VENV)/bin/pip install -q -e ".[dev,disasm]"
	@touch $@

$(BASEROM):
	@echo "error: $(BASEROM) is missing."
	@echo "       Put your own dump there (sha1 e9538c0542b4a05050f5b68d279cddb06559ae20)."
	@echo "       See baserom/README.md."
	@exit 1

help:
	@sed -n '2,17p' $(MAKEFILE_LIST)
