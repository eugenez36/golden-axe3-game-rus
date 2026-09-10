# Third-party notices

This repository is a toolkit. It contains original code under the MIT license (see
[LICENSE](LICENSE)) and depends on, or refers to, the following works that are **not**
covered by that license.

## Golden Axe III (game ROM) — © SEGA

The game, its code, graphics, music, text and the `Golden Axe 3 (RUS).bin` image are the
property of SEGA Corporation. **The ROM is not included in this repository** and must never
be committed (see `.gitignore` and the CI guard step). Users must supply their own dump.

"SEGA", "Mega Drive", "Genesis" and "Golden Axe" are trademarks of SEGA Corporation.
This project is not affiliated with, endorsed by, or sponsored by SEGA.

Addresses, tables and structural descriptions of the ROM found in this repository are
the result of independent analysis for interoperability and preservation purposes.

## Russian translation — NEWGAME, 2003

The Cyrillic font, character table layout and translated strings this toolkit operates
on were created by the translation group **NEWGAME** in 2003. The toolkit reads and
edits that work; it does not claim authorship of it.

## Genesis Plus GX — Charles MacDonald, Eke-Eke and contributors

`emu/gpgx/` is the Genesis Plus GX emulator core (upstream:
<https://github.com/ekeeke/Genesis-Plus-GX>), used unchanged except for a small
`dma_hook` callback added to `core/vdp_ctrl.c` (see `emu/patches/`). `emu/headless/`
is an original frontend that links against it.

Genesis Plus GX is distributed under the following license, which applies to the core
and to any binary built from it, including `headless_gpgx`:

```
Copyright (c) 1998-2003 Charles MacDonald
Copyright (c) 2007-2026 Eke-Eke
Some portions copyright Nicola Salmoria and the MAME team
All rights reserved.

Redistribution and use of this code or any derivative works are permitted
provided that the following conditions are met:

* Redistributions may not be sold, nor may they be used in a commercial
product or activity.

* Redistributions that are modified from the original source must include the
complete source code, including the source code for all components used by a
binary built from the modified sources. However, as a special exception, the
source code distributed need not include anything that is normally distributed
(in either source or binary form) with the major components (compiler, kernel,
and so on) of the operating system on which the executable runs, unless that
component itself accompanies the executable.

* Redistributions must reproduce the above copyright notice, this list of
conditions and the following disclaimer in the documentation and/or other
materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
```

Consequence for this repository: the **toolkit binaries that embed the emulator core
are non-commercial**, even though the Python tools themselves are MIT.

## Capstone — BSD-3-Clause

`tools/disasm.py` uses the [Capstone](https://www.capstone-engine.org/) disassembly
framework (Python bindings, `capstone==5.0.9`), © Nguyen Anh Quynh and contributors,
BSD-3-Clause.

## Nemesis compression format

Nemesis is SEGA's in-house tile compression scheme. The implementation in
`tools/nemesis.py` was written from the disassembly of this game's own decoder
(`NemDec` at `0x0122FC`). Public documentation of the format by the Sonic Retro
community was used as a cross-reference.
