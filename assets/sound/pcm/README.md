# assets/sound/pcm

`samples.pcm` is the raw byte range `0FC000–0FFA20` of the ROM (14 880 bytes).
It is committed verbatim and written back verbatim by `ga3 build`.

What is *not* known yet, and would turn this into real audio assets:

- the sample table (offsets and lengths of individual samples),
- the encoding and playback rate (8-bit unsigned at a fixed Z80-timed rate is the
  usual Mega Drive arrangement, but it is unverified here),
- which Z80 driver routine reads it (the Z80 program itself has not been located;
  `0D9000–0E9000` is high-entropy and is the first place to look).

Open a **ROM finding** issue when any of these is confirmed. Until then, edit
this file only with a hex editor and keep the size unchanged.
