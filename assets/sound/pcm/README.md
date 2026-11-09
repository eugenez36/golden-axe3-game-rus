# assets/sound/pcm

`samples.pcm` is the raw byte range `0FAEB8–0FFA10` of the ROM (19 288 bytes):
the DAC samples of the sound bank `0F0000–0FFA10` (issue #53, segments
`snd_*`, `z80_driver`, `dac_table`, `pcm` in `rom_map.yml`).
It is committed verbatim and written back verbatim by `ga3 build`.

What is known:

- **Player.** The Z80 program `0FACC8–0FAE5E` (406 bytes) is copied to Z80 RAM
  `0000` by the 68k routine `0F0858` at boot. It plays two sample streams
  mixed into the YM2612 DAC; the 68000 runs music and SFX itself (SMPS 68k).
- **Table.** `dac_table` (`0FAE5E–0FAEB8`): 18 entries of 5 bytes — length
  (little-endian word), rate byte, offset (little-endian word) from the entry
  itself. The Z80 sees the ROM through the bank window `0F8000–0FFFFF`.
- **Format.** 8-bit unsigned, centred on `0x80`. The rate byte is the step
  of a fractional accumulator, not a frequency in Hz.
- **Sounds.** 8 distinct sounds behind the 18 entries (entries 3–7 play one
  sound at five rates). The last byte, `0FFA0F`, is word padding.

Not known yet: which entry is which drum, and the playback rate in Hz. Until
there is an editable form, edit this file only with a hex editor and keep the
size unchanged.
