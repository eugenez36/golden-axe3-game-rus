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
#   make regress    run every emu/scenes/*.txt against build/ga3.bin
#   make clean      rm -rf build/
#   make distclean  clean + virtualenv + caches
#   make venv       create .venv and install ga3 with the [dev,disasm] extras
#   make help       print this list
#
# Variables: PYTHON (interpreter used to create .venv), GPGX (emulator core dir).

PYTHON   ?= python3
VENV     ?= .venv
GA3      ?= $(VENV)/bin/ga3
PYTEST   ?= $(VENV)/bin/pytest
RUFF     ?= $(VENV)/bin/ruff
GPGX     ?= $(CURDIR)/emu/gpgx
BASEROM  := baserom/ga3.bin
BUILDROM := build/ga3.bin
EMU      := build/emu/headless_gpgx
SCENES   := $(wildcard emu/scenes/*.txt)

.DEFAULT_GOAL := build
.PHONY: build extract verify test lint assets asm emu regress clean distclean venv help

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
	$(MAKE) -C emu/headless GPGX=$(GPGX) BUILD=$(CURDIR)/build/emu

regress: build emu
	@for s in $(SCENES); do \
	  echo "== $$s"; $(EMU) --rom $(BUILDROM) --script $$s --quiet || exit 1; \
	done

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
