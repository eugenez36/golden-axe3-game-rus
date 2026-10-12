# emu/ — the headless emulator

| Path                          | What                                                                                                                                            |
|-------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| `gpgx/`                       | Genesis Plus GX core, a git submodule on the `ga3/dma-hook` branch of [eugenez36/Genesis-Plus-GX](https://github.com/eugenez36/Genesis-Plus-GX) |
| `patches/0001-dma-hook.patch` | the one commit that branch adds to upstream (14 lines, `#ifdef HOOK_CPU`)                                                                       |
| `headless/`                   | the frontend: `main.c`, `osd.h`, `Makefile`; builds into `build/emu/headless_gpgx`                                                              |
| `scenes/`                     | regression scripts run by `make regress`; shared preambles in `_*.inc`                                                                          |
| `explore/`                    | one-off scripts that produced the findings in `rom_map.yml` ([README](explore/README.md))                                                       |

```bash
make emu                                  # build (needs zlib headers and a C compiler)
ga3 emu emu/scenes/menu_verify.txt        # run one scene against build/ga3.bin
make regress                              # run them all; output in build/shots and build/dumps
```

Command reference and the three Genesis Plus GX pitfalls (byte-swapped VRAM and
Work RAM, DMA invisible to `cpu_hook`): [docs/emulator.md](../docs/emulator.md).
