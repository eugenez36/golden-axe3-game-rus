/***************************************************************************************
 *  headless_gpgx -- windowless Genesis Plus GX driver for ROM hacking.
 *
 *  No SDL, no libretro: it runs a ROM for a scripted number of frames, presses
 *  buttons, saves PNG screenshots, dumps VRAM/CRAM/VSRAM/Work RAM and sets
 *  write watchpoints that report the PC of the code doing the write.
 *
 *  Build:  make emu                       (from the project root)
 *  Run:    ga3 emu emu/scenes/title.txt   or
 *          build/emu/headless_gpgx --rom build/ga3.bin --script emu/scenes/title.txt
 *
 *  Script files are line oriented; see usage() for the command list and
 *  docs/emulator.md for the three Genesis Plus GX pitfalls that matter here.
 ***************************************************************************************/

#include "shared.h"
#include "state.h"
#include "cpuhook.h"
#include "m68k.h"

#include <errno.h>
#include <sys/stat.h>
#include <zlib.h>

#define SOUND_FREQUENCY 44100
#define MAX_WATCHES     16
#define MAX_INCLUDE     8

/* ------------------------------------------------------------------ core globals */

t_config config;

char GG_ROM[256]    = "";
char AR_ROM[256]    = "";
char SK_ROM[256]    = "";
char SK_UPMEM[256]  = "";
char GG_BIOS[256]   = "";
char MD_BIOS[256]   = "";
char CD_BIOS_EU[256] = "";
char CD_BIOS_US[256] = "";
char CD_BIOS_JP[256] = "";
char MS_BIOS_US[256] = "";
char MS_BIOS_EU[256] = "";
char MS_BIOS_JP[256] = "";

static uint16 bitmap_data_[720 * 576 * 2]; /* generous: a 32bpp pixel is 4 bytes */
static int16  soundbuffer[2048 * 2];

/* ------------------------------------------------------------------ driver state */

static uint16 pad_state[2];      /* INPUT_* masks for port A and port B */
static long   frame_counter;
static int    verbose = 1;

struct watch {
  unsigned int lo, hi;
  const char  *name;
};
static struct watch watches[MAX_WATCHES];
static int    watch_count;
static struct watch vwatches[MAX_WATCHES];   /* VRAM write watchpoints */
static int    vwatch_count;
static int    dma_log_on;                    /* log every DMA transfer */
static unsigned int breakpoints[MAX_WATCHES]; /* PCs at which registers are dumped */
static int    bp_count;

extern void (*dma_hook)(unsigned int src, unsigned int dst, unsigned int len,
                        unsigned int code, unsigned int type);
static FILE  *watch_fp;
static long   watch_hits;
static unsigned int last_pc;     /* updated by the HOOK_M68K_E hook */

/* ------------------------------------------------------------------ mandatory OSD layer */

void osd_input_update(void)
{
  input.pad[0] = pad_state[0];
  input.pad[4] = pad_state[1];   /* port B is index 4 in GPGX: each port keeps 4 multitap slots */
}

void ROMCheatUpdate(void) { }

int load_archive(char *filename, unsigned char *buffer, int maxsize, char *extension)
{
  FILE *fp;
  int size;

  fp = fopen(filename, "rb");
  if (!fp)
    return 0;

  fseek(fp, 0, SEEK_END);
  size = (int)ftell(fp);
  fseek(fp, 0, SEEK_SET);

  if (size > maxsize)
    size = maxsize;

  if (fread(buffer, 1, size, fp) != (size_t)size)
    size = 0;
  fclose(fp);

  if (extension)
  {
    char *ext = strrchr(filename, '.');
    if (ext)
    {
      strncpy(extension, ext + 1, 3);
      extension[3] = 0;
    }
  }

  if (verbose)
    fprintf(stderr, "[load] %s -- %d bytes\n", filename, size);
  return size;
}

/* ------------------------------------------------------------------ paths */

/* Create every directory on the way to `path` (the file name itself is not created).
 * Scripts write into build/shots and build/dumps, which do not exist on a fresh
 * checkout; silently failing fopen()s cost real debugging time before this existed. */
static void ensure_parent_dir(const char *path)
{
  char buf[1024];
  char *p;
  size_t n = strlen(path);

  if (n == 0 || n >= sizeof(buf))
    return;
  memcpy(buf, path, n + 1);
  for (p = buf + 1; *p; p++)
  {
    if (*p == '/')
    {
      *p = 0;
      if (mkdir(buf, 0777) && errno != EEXIST)
        fprintf(stderr, "[path] cannot create %s: %s\n", buf, strerror(errno));
      *p = '/';
    }
  }
}

/* ------------------------------------------------------------------ PNG without external libraries */

static void png_chunk(FILE *fp, const char *tag, const unsigned char *data, unsigned len)
{
  unsigned char be[4];
  unsigned long crc;

  be[0] = len >> 24; be[1] = len >> 16; be[2] = len >> 8; be[3] = len;
  fwrite(be, 1, 4, fp);
  fwrite(tag, 1, 4, fp);
  if (len)
    fwrite(data, 1, len, fp);

  crc = crc32(0, (const Bytef *)tag, 4);
  if (len)
    crc = crc32(crc, (const Bytef *)data, len);
  be[0] = crc >> 24; be[1] = crc >> 16; be[2] = crc >> 8; be[3] = crc;
  fwrite(be, 1, 4, fp);
}

/* rgb is a packed w*h*3 array */
static int png_write(const char *path, const unsigned char *rgb, int w, int h)
{
  FILE *fp;
  unsigned char ihdr[13];
  unsigned char *raw, *comp;
  unsigned long rawlen, complen;
  int y;
  static const unsigned char sig[8] = { 137, 'P', 'N', 'G', 13, 10, 26, 10 };

  /* every PNG scanline starts with a filter byte */
  rawlen = (unsigned long)h * (1 + (unsigned long)w * 3);
  raw = (unsigned char *)malloc(rawlen);
  if (!raw)
    return 0;
  for (y = 0; y < h; y++)
  {
    raw[y * (1 + w * 3)] = 0;
    memcpy(raw + y * (1 + w * 3) + 1, rgb + (size_t)y * w * 3, (size_t)w * 3);
  }

  complen = compressBound(rawlen);
  comp = (unsigned char *)malloc(complen);
  if (!comp) { free(raw); return 0; }
  if (compress2(comp, &complen, raw, rawlen, 6) != Z_OK)
  {
    free(raw); free(comp);
    return 0;
  }
  free(raw);

  ensure_parent_dir(path);
  fp = fopen(path, "wb");
  if (!fp)
  {
    fprintf(stderr, "[png ] cannot open %s: %s\n", path, strerror(errno));
    free(comp);
    return 0;
  }

  fwrite(sig, 1, 8, fp);
  ihdr[0] = w >> 24; ihdr[1] = w >> 16; ihdr[2] = w >> 8; ihdr[3] = w;
  ihdr[4] = h >> 24; ihdr[5] = h >> 16; ihdr[6] = h >> 8; ihdr[7] = h;
  ihdr[8] = 8;   /* 8 bits per channel */
  ihdr[9] = 2;   /* truecolor RGB     */
  ihdr[10] = ihdr[11] = ihdr[12] = 0;
  png_chunk(fp, "IHDR", ihdr, 13);
  png_chunk(fp, "IDAT", comp, (unsigned)complen);
  png_chunk(fp, "IEND", NULL, 0);
  fclose(fp);
  free(comp);
  return 1;
}

/* Frame (XRGB8888) -> PNG, cropped to the viewport, integer-scaled */
static int save_screenshot(const char *path, int scale)
{
  int vx = bitmap.viewport.x, vy = bitmap.viewport.y;
  int vw = bitmap.viewport.w, vh = bitmap.viewport.h;
  unsigned char *rgb;
  int x, y, sx, sy, ok;
  int ow, oh;

  if (vw <= 0 || vh <= 0)
  {
    fprintf(stderr, "[png ] empty viewport (%dx%d) -- no frame yet\n", vw, vh);
    return 0;
  }
  if (scale < 1) scale = 1;
  ow = vw * scale;
  oh = vh * scale;

  rgb = (unsigned char *)malloc((size_t)ow * oh * 3);
  if (!rgb)
    return 0;

  for (y = 0; y < vh; y++)
  {
    uint32 *src = (uint32 *)bitmap.data + (size_t)(vy + y) * bitmap.width + vx;
    for (x = 0; x < vw; x++)
    {
      unsigned int p = src[x];
      unsigned char r = (p >> 16) & 0xFF, g = (p >> 8) & 0xFF, b = p & 0xFF;
      for (sy = 0; sy < scale; sy++)
      {
        unsigned char *dst = rgb + (((size_t)y * scale + sy) * ow + (size_t)x * scale) * 3;
        for (sx = 0; sx < scale; sx++)
        {
          dst[sx * 3 + 0] = r;
          dst[sx * 3 + 1] = g;
          dst[sx * 3 + 2] = b;
        }
      }
    }
  }

  ok = png_write(path, rgb, ow, oh);
  free(rgb);
  if (ok && verbose)
    fprintf(stderr, "[png ] frame %ld -> %s (%dx%d%s)\n", frame_counter, path, ow, oh,
            scale > 1 ? ", scaled" : "");
  return ok;
}

/* ------------------------------------------------------------------ memory dumps */

static int dump_blob(const char *path, const void *data, size_t len, const char *what)
{
  FILE *fp;
  ensure_parent_dir(path);
  fp = fopen(path, "wb");
  if (!fp)
  {
    fprintf(stderr, "[dump] cannot open %s: %s\n", path, strerror(errno));
    return 0;
  }
  fwrite(data, 1, len, fp);
  fclose(fp);
  if (verbose)
    fprintf(stderr, "[dump] %s (%zu bytes) -> %s\n", what, len, path);
  return 1;
}

/* GPGX keeps VRAM and the sprite table as host-endian uint16, so on a little-endian
 * host the two bytes of every word are swapped relative to Mega Drive order. Dumps
 * are written in honest big-endian so they compare byte for byte with the ROM. */
static int dump_swapped(const char *path, const void *data, size_t len, const char *what)
{
  const unsigned char *src = (const unsigned char *)data;
  unsigned char *tmp = (unsigned char *)malloc(len);
  size_t i;
  int ok;

  if (!tmp)
    return 0;
  for (i = 0; i + 1 < len; i += 2)
  {
    tmp[i]     = src[i + 1];
    tmp[i + 1] = src[i];
  }
  if (len & 1)
    tmp[len - 1] = src[len - 1];

  ok = dump_blob(path, tmp, len, what);
  free(tmp);
  return ok;
}

static int dump_named(const char *what, const char *path)
{
  if (!strcmp(what, "vram"))  return dump_swapped(path, vram, 0x10000, "VRAM");
  /* CRAM is GPGX's packed 9-bit form, little-endian; ga3.palette.gpgx_cram_to_words() unpacks it */
  if (!strcmp(what, "cram"))  return dump_blob(path, cram,  0x80,    "CRAM (GPGX packed)");
  if (!strcmp(what, "vsram")) return dump_blob(path, vsram, 0x80,    "VSRAM");
  /* Work RAM is byte-swapped too (READ_BYTE = BASE[ADDR ^ 1]); see ga3.ramsearch */
  if (!strcmp(what, "wram"))  return dump_blob(path, work_ram, 0x10000, "Work RAM (68k, byte-swapped)");
  if (!strcmp(what, "zram"))  return dump_blob(path, zram, 0x2000,   "Z80 RAM");
  /* sprites are drawn from the VDP's internal sat[] copy, not from VRAM directly */
  if (!strcmp(what, "sat"))   return dump_swapped(path, sat, 0x400, "Sprite table (VDP copy)");
  if (!strcmp(what, "satvram")) return dump_swapped(path, &vram[satb & 0xFFFF], 0x400, "Sprite table (VRAM)");
  if (!strcmp(what, "regs"))  return dump_blob(path, reg, 0x20,      "VDP registers");
  fprintf(stderr, "[dump] unknown area '%s'\n", what);
  return 0;
}

/* ------------------------------------------------------------------ watchpoints */

static void hook(hook_type_t type, int width, unsigned int address, unsigned int value)
{
  int i;

  /* The 68000 drives only 24 address bits: the game addresses RAM as FFFFxxxx,
   * physically that is FFxxxx. Without the mask no watchpoint ever fires. */
  if (type == HOOK_M68K_W || type == HOOK_M68K_R || type == HOOK_M68K_E)
    address &= 0xFFFFFF;

  if (type == HOOK_M68K_E)
  {
    last_pc = address;

    for (i = 0; i < bp_count; i++)
    {
      if (address == breakpoints[i])
      {
        watch_hits++;
        if (watch_fp)
        {
          fprintf(watch_fp, "BP frame=%ld pc=%06X", frame_counter, address);
          fprintf(watch_fp, " a0=%08X a1=%08X a2=%08X a3=%08X a4=%08X a5=%08X a6=%08X",
                  m68k_get_reg(M68K_REG_A0), m68k_get_reg(M68K_REG_A1),
                  m68k_get_reg(M68K_REG_A2), m68k_get_reg(M68K_REG_A3),
                  m68k_get_reg(M68K_REG_A4), m68k_get_reg(M68K_REG_A5),
                  m68k_get_reg(M68K_REG_A6));
          fprintf(watch_fp, " d0=%08X d1=%08X d2=%08X d3=%08X\n",
                  m68k_get_reg(M68K_REG_D0), m68k_get_reg(M68K_REG_D1),
                  m68k_get_reg(M68K_REG_D2), m68k_get_reg(M68K_REG_D3));
        }
        break;
      }
    }
    return;
  }

  if (type == HOOK_VRAM_W && vwatch_count)
  {
    for (i = 0; i < vwatch_count; i++)
    {
      if (address >= vwatches[i].lo && address <= vwatches[i].hi)
      {
        /* DMA source: registers 21..23 hold the word address */
        unsigned int dma_src = ((reg[23] & 0x7F) << 17) | (reg[22] << 9) | (reg[21] << 1);
        unsigned int dma_len = (reg[20] << 8) | reg[19];
        watch_hits++;
        if (watch_fp)
          fprintf(watch_fp, "VRAM_W frame=%ld pc=%06X vram=%04X value=%04X "
                            "dma_src=%06X dma_len=%04X name=%s\n",
                  frame_counter, last_pc & 0xFFFFFF, address, value,
                  dma_src, dma_len, vwatches[i].name ? vwatches[i].name : "-");
        break;
      }
    }
    return;
  }

  if (type != HOOK_M68K_W || !watch_count)
    return;

  for (i = 0; i < watch_count; i++)
  {
    /* an access of `width` bytes covers address..address+width-1, otherwise a
     * long write to an even address would miss a narrow watchpoint */
    unsigned int last = address + (width > 0 ? (unsigned)width - 1 : 0);
    if (last >= watches[i].lo && address <= watches[i].hi)
    {
      watch_hits++;
      if (watch_fp)
        fprintf(watch_fp, "frame=%ld pc=%06X addr=%06X width=%d value=%X name=%s\n",
                frame_counter, last_pc & 0xFFFFFF, address, width, value,
                watches[i].name ? watches[i].name : "-");
      break;
    }
  }
}

/* Where a DMA goes: the VDP destination code selects the memory */
static const char *dma_dest(unsigned int code)
{
  switch (code & 0x07)
  {
    case 1: return "VRAM";
    case 3: return "CRAM";
    case 5: return "VSRAM";
    default: return "?";
  }
}

static void on_dma(unsigned int src, unsigned int dst, unsigned int len,
                   unsigned int code, unsigned int type)
{
  if (!dma_log_on || !watch_fp)
    return;
  fprintf(watch_fp, "DMA frame=%ld pc=%06X src=%06X dst=%04X len=%04X dest=%s type=%u\n",
          frame_counter, last_pc & 0xFFFFFF, src, dst, len, dma_dest(code), type);
}

static void watch_add(unsigned int lo, unsigned int len, const char *name)
{
  if (watch_count >= MAX_WATCHES)
  {
    fprintf(stderr, "[watch] too many watchpoints (max %d)\n", MAX_WATCHES);
    return;
  }
  watches[watch_count].lo = lo;
  watches[watch_count].hi = lo + (len ? len - 1 : 0);
  watches[watch_count].name = name ? strdup(name) : NULL;
  watch_count++;
  if (verbose)
    fprintf(stderr, "[watch] writes to %06X..%06X%s%s\n", lo, lo + (len ? len - 1 : 0),
            name ? " -- " : "", name ? name : "");
}

/* ------------------------------------------------------------------ buttons */

static uint16 parse_buttons(const char *s)
{
  uint16 mask = 0;
  char buf[128], *tok;

  if (!s || !*s || !strcmp(s, "-") || !strcmp(s, "none"))
    return 0;
  strncpy(buf, s, sizeof(buf) - 1);
  buf[sizeof(buf) - 1] = 0;

  for (tok = strtok(buf, "+,"); tok; tok = strtok(NULL, "+,"))
  {
    if      (!strcasecmp(tok, "up"))    mask |= INPUT_UP;
    else if (!strcasecmp(tok, "down"))  mask |= INPUT_DOWN;
    else if (!strcasecmp(tok, "left"))  mask |= INPUT_LEFT;
    else if (!strcasecmp(tok, "right")) mask |= INPUT_RIGHT;
    else if (!strcasecmp(tok, "a"))     mask |= INPUT_A;
    else if (!strcasecmp(tok, "b"))     mask |= INPUT_B;
    else if (!strcasecmp(tok, "c"))     mask |= INPUT_C;
    else if (!strcasecmp(tok, "x"))     mask |= INPUT_X;
    else if (!strcasecmp(tok, "y"))     mask |= INPUT_Y;
    else if (!strcasecmp(tok, "z"))     mask |= INPUT_Z;
    else if (!strcasecmp(tok, "start")) mask |= INPUT_START;
    else if (!strcasecmp(tok, "mode"))  mask |= INPUT_MODE;
    else fprintf(stderr, "[input] unknown button '%s'\n", tok);
  }
  return mask;
}

/* ------------------------------------------------------------------ frame loop */

static void run_frames(int n)
{
  int i;
  for (i = 0; i < n; i++)
  {
    system_frame_gen(0);
    audio_update(soundbuffer);
    frame_counter++;
  }
}

/* ------------------------------------------------------------------ script */

static unsigned int parse_addr(const char *s)
{
  return (unsigned int)strtoul(s, NULL, 16);
}

/* "dir/of/including/file" + "name" -> "dir/of/including/file/name"; absolute paths pass through */
static void resolve_relative(char *out, size_t outlen, const char *base_file, const char *name)
{
  const char *slash = base_file ? strrchr(base_file, '/') : NULL;
  if (name[0] == '/' || !slash || !strcmp(base_file, "-"))
  {
    snprintf(out, outlen, "%s", name);
    return;
  }
  snprintf(out, outlen, "%.*s/%s", (int)(slash - base_file), base_file, name);
}

static int run_script(const char *path, int depth)
{
  FILE *fp = strcmp(path, "-") ? fopen(path, "r") : stdin;
  char line[512];
  int lineno = 0;

  if (!fp)
  {
    fprintf(stderr, "[script] cannot open %s: %s\n", path, strerror(errno));
    return 0;
  }

  while (fgets(line, sizeof(line), fp))
  {
    char *cmd, *a1, *a2, *a3, *hash;
    lineno++;

    hash = strchr(line, '#');
    if (hash) *hash = 0;

    /* at most three arguments are parsed; arguments cannot contain spaces */
    cmd = strtok(line, " \t\r\n");
    if (!cmd)
      continue;
    a1 = strtok(NULL, " \t\r\n");
    a2 = strtok(NULL, " \t\r\n");
    a3 = strtok(NULL, " \t\r\n");

    if (!strcmp(cmd, "include"))
    {
      /* include PATH -- run another script here; PATH is relative to this file */
      char inc[1024];
      if (!a1)
      {
        fprintf(stderr, "[script] %s:%d: include needs a path\n", path, lineno);
        continue;
      }
      if (depth >= MAX_INCLUDE)
      {
        fprintf(stderr, "[script] %s:%d: include nesting deeper than %d\n", path, lineno, MAX_INCLUDE);
        continue;
      }
      resolve_relative(inc, sizeof(inc), path, a1);
      if (!run_script(inc, depth + 1))
      {
        if (fp != stdin) fclose(fp);
        return 0;
      }
    }
    else if (!strcmp(cmd, "wait"))
    {
      run_frames(a1 ? atoi(a1) : 1);
    }
    else if (!strcmp(cmd, "hold"))
    {
      /* hold BUTTONS FRAMES -- hold buttons for that many frames */
      pad_state[0] = parse_buttons(a1);
      run_frames(a2 ? atoi(a2) : 1);
      pad_state[0] = 0;
    }
    else if (!strcmp(cmd, "press"))
    {
      /* press BUTTONS [FRAMES] -- press, hold, release (default 6 frames each) */
      int n = a2 ? atoi(a2) : 6;
      pad_state[0] = parse_buttons(a1);
      run_frames(n);
      pad_state[0] = 0;
      run_frames(n);
    }
    else if (!strcmp(cmd, "pad2"))
    {
      /* pad2 BUTTONS [FRAMES] -- hold buttons on the second pad */
      pad_state[1] = parse_buttons(a1);
      run_frames(a2 ? atoi(a2) : 1);
      pad_state[1] = 0;
    }
    else if (!strcmp(cmd, "screenshot"))
    {
      if (a1) save_screenshot(a1, a2 ? atoi(a2) : 1);
    }
    else if (!strcmp(cmd, "dump"))
    {
      if (a1 && a2) dump_named(a1, a2);
    }
    else if (!strcmp(cmd, "watch"))
    {
      if (a1) watch_add(parse_addr(a1), a2 ? parse_addr(a2) : 1, a3);
    }
    else if (!strcmp(cmd, "watchlog"))
    {
      if (watch_fp) fclose(watch_fp);
      watch_fp = NULL;
      if (a1)
      {
        ensure_parent_dir(a1);
        watch_fp = fopen(a1, "w");
        if (!watch_fp)
          fprintf(stderr, "[watch] cannot open log %s: %s\n", a1, strerror(errno));
      }
    }
    else if (!strcmp(cmd, "bp"))
    {
      /* bp ADDR -- dump registers into the watchlog whenever ADDR executes */
      if (a1 && bp_count < MAX_WATCHES)
      {
        breakpoints[bp_count++] = parse_addr(a1);
        if (verbose)
          fprintf(stderr, "[bp   ] breakpoint at %06X\n", parse_addr(a1));
      }
    }
    else if (!strcmp(cmd, "dmalog"))
    {
      /* dmalog on|off -- log every DMA transfer with its source address into the watchlog */
      dma_log_on = (!a1 || strcmp(a1, "off")) ? 1 : 0;
      if (verbose)
        fprintf(stderr, "[dma  ] DMA log %s\n", dma_log_on ? "on" : "off");
    }
    else if (!strcmp(cmd, "vwatch"))
    {
      /* vwatch ADDR LEN [NAME] -- watch VRAM writes (including DMA) */
      if (a1 && vwatch_count < MAX_WATCHES)
      {
        unsigned int lo = parse_addr(a1);
        unsigned int len = a2 ? parse_addr(a2) : 1;
        vwatches[vwatch_count].lo = lo;
        vwatches[vwatch_count].hi = lo + (len ? len - 1 : 0);
        vwatches[vwatch_count].name = a3 ? strdup(a3) : NULL;
        vwatch_count++;
        if (verbose)
          fprintf(stderr, "[vwatch] VRAM %04X..%04X\n", lo, lo + (len ? len - 1 : 0));
      }
    }
    else if (!strcmp(cmd, "clearwatch"))
    {
      /* clears RAM and VRAM watchpoints; breakpoints and the DMA log stay */
      watch_count = 0;
      vwatch_count = 0;
    }
    else if (!strcmp(cmd, "poke8"))
    {
      if (a1 && a2) { unsigned int ad = parse_addr(a1);
        work_ram[ad & 0xFFFF] = (uint8)strtoul(a2, NULL, 16); }
    }
    else if (!strcmp(cmd, "poke16"))
    {
      if (a1 && a2) { unsigned int ad = parse_addr(a1), v = (unsigned)strtoul(a2, NULL, 16);
        work_ram[ad & 0xFFFF] = v >> 8; work_ram[(ad + 1) & 0xFFFF] = v & 0xFF; }
    }
    else if (!strcmp(cmd, "state"))
    {
      static unsigned char *sbuf;
      if (!sbuf) sbuf = (unsigned char *)malloc(STATE_SIZE);
      if (a1 && a2 && !strcmp(a1, "save"))
      {
        int n = state_save(sbuf);
        dump_blob(a2, sbuf, n, "savestate");
      }
      else if (a1 && a2 && !strcmp(a1, "load"))
      {
        FILE *sf = fopen(a2, "rb");
        if (sf) { size_t got = fread(sbuf, 1, STATE_SIZE, sf); fclose(sf);
                  fprintf(stderr, "[state] load %s (%zu bytes) -> %s\n", a2, got,
                          (got && state_load(sbuf)) ? "ok" : "FAILED"); }
        else fprintf(stderr, "[state] cannot open %s: %s\n", a2, strerror(errno));
      }
    }
    else if (!strcmp(cmd, "reset"))
    {
      system_reset();
      if (verbose) fprintf(stderr, "[sys ] reset at frame %ld\n", frame_counter);
    }
    else if (!strcmp(cmd, "echo"))
    {
      printf("%s%s%s%s%s\n", a1 ? a1 : "", a2 ? " " : "", a2 ? a2 : "",
             a3 ? " " : "", a3 ? a3 : "");
      fflush(stdout);
    }
    else if (!strcmp(cmd, "status"))
    {
      printf("frame=%ld viewport=%dx%d watch_hits=%ld\n",
             frame_counter, bitmap.viewport.w, bitmap.viewport.h, watch_hits);
      fflush(stdout);
    }
    else if (!strcmp(cmd, "quiet"))
    {
      verbose = 0;
    }
    else
    {
      fprintf(stderr, "[script] %s:%d: unknown command '%s'\n", path, lineno, cmd);
    }
  }

  if (fp != stdin)
    fclose(fp);
  return 1;
}

/* ------------------------------------------------------------------ core setup */

static void init_bitmap(void)
{
  memset(&bitmap, 0, sizeof(bitmap));
  bitmap.width  = 720;
  bitmap.height = 576;
  bitmap.pitch  = 720 * 4;           /* USE_32BPP_RENDERING */
  bitmap.data   = (uint8 *)bitmap_data_;
}

static void config_default(void)
{
  int i;

  memset(&config, 0, sizeof(config));

  /* sound: unused, but the core will not run without it initialised */
  config.psg_preamp  = 150;
  config.fm_preamp   = 100;
  config.cdda_volume = 100;
  config.pcm_volume  = 100;
  config.hq_fm       = 1;
  config.hq_psg      = 1;
  config.filter      = 0;            /* no filter -- slightly faster */
  config.lp_range    = 0x9999;
  config.low_freq    = 880;
  config.high_freq   = 5000;
  config.lg = config.mg = config.hg = 100;
  config.ym2612      = YM2612_DISCRETE;
  config.ym2413      = 2;            /* AUTO */
  config.mono        = 0;

  /* system */
  config.system        = 0;          /* AUTO */
  config.region_detect = 0;          /* AUTO */
  config.vdp_mode      = 0;          /* AUTO */
  config.master_clock  = 0;          /* AUTO */
  config.force_dtack   = 0;
  config.addr_error    = 1;
  config.bios          = 0;
  config.lock_on       = 0;
  config.add_on        = 0;
  config.overclock     = 100;
  config.no_sprite_limit = 0;        /* like real hardware: matters for an honest frame */
  config.enhanced_vscroll = 0;
  config.enhanced_vscroll_limit = 8;
  config.cd_latency    = 1;

  /* video */
  config.overscan    = 0;            /* no border -- exactly the active picture */
  config.aspect_ratio = 0;
  config.gg_extra    = 0;
  config.ntsc        = 0;            /* no NTSC filter: we need exact pixels */
  config.lcd         = 0;
  config.render      = 0;
  config.left_border = 0;

  /* input: two plain three-button pads */
  input.system[0] = SYSTEM_GAMEPAD;
  input.system[1] = SYSTEM_GAMEPAD;
  for (i = 0; i < MAX_INPUTS; i++)
    config.input[i].padtype = DEVICE_PAD3B;
}

/* ------------------------------------------------------------------ main */

static void usage(const char *argv0)
{
  fprintf(stderr,
    "headless Genesis Plus GX -- run a ROM without a window\n"
    "\n"
    "  %s --rom FILE [--script FILE] [--frames N] [--png FILE] [--scale N] [--quiet]\n"
    "\n"
    "Script commands (# starts a comment; --script - reads stdin):\n"
    "  include PATH           run another script (relative to the including file, depth <= %d)\n"
    "  wait N                 advance N frames\n"
    "  press BTNS [N]         press for N frames, then release for N (default 6)\n"
    "  hold BTNS N            hold buttons for N frames\n"
    "  pad2 BTNS [N]          the same on the second pad (default 1 frame)\n"
    "  screenshot PATH [S]    save a PNG, S = integer scale; directories are created\n"
    "  dump WHAT PATH         WHAT: vram|cram|vsram|wram|zram|sat|satvram|regs\n"
    "  watchlog PATH          where watchpoint, breakpoint and DMA lines are written\n"
    "  watch ADDR LEN [NAME]  watchpoint on 68000 writes (address AND length in hex)\n"
    "  vwatch ADDR LEN [NAME] watchpoint on VRAM writes, including DMA\n"
    "  bp ADDR                dump registers whenever ADDR executes\n"
    "  dmalog on|off          log every DMA transfer with its source address\n"
    "  clearwatch             remove RAM and VRAM watchpoints (breakpoints stay)\n"
    "  poke8/poke16 ADDR VAL  patch Work RAM on the fly (hex)\n"
    "  state save|load PATH   save / load a savestate\n"
    "  reset                  reset the system\n"
    "  status                 print frame / viewport / watch hits\n"
    "  echo TEXT              print up to three words\n"
    "  quiet                  silence progress messages\n"
    "\n"
    "Buttons: up down left right a b c x y z start mode, joined with '+'\n"
    "Arguments cannot contain spaces; anything past the third argument is ignored.\n",
    argv0, MAX_INCLUDE);
}

int main(int argc, char **argv)
{
  const char *rom = NULL, *script = NULL, *png = NULL;
  int frames = 0, scale = 1, i;

  for (i = 1; i < argc; i++)
  {
    if (!strcmp(argv[i], "--rom") && i + 1 < argc)         rom = argv[++i];
    else if (!strcmp(argv[i], "--script") && i + 1 < argc) script = argv[++i];
    else if (!strcmp(argv[i], "--frames") && i + 1 < argc) frames = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--png") && i + 1 < argc)    png = argv[++i];
    else if (!strcmp(argv[i], "--scale") && i + 1 < argc)  scale = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--quiet"))                  verbose = 0;
    else if (!strcmp(argv[i], "--help") || !strcmp(argv[i], "-h")) { usage(argv[0]); return 0; }
    else { fprintf(stderr, "unknown argument: %s\n", argv[i]); usage(argv[0]); return 2; }
  }

  if (!rom)
  {
    usage(argv[0]);
    return 2;
  }

  init_bitmap();
  config_default();
  set_cpu_hook(hook);
  dma_hook = on_dma;

  if (load_rom((char *)rom) <= 0)
  {
    fprintf(stderr, "cannot load ROM: %s\n", rom);
    return 1;
  }

  audio_init(SOUND_FREQUENCY, 0);
  system_init();
  system_reset();

  if (verbose)
    fprintf(stderr, "[sys ] %s, region %d, %s\n",
            (system_hw == SYSTEM_MD) ? "Mega Drive" : "non-MD system",
            region_code, vdp_pal ? "PAL" : "NTSC");

  if (script)
  {
    if (!run_script(script, 0))
      return 1;
  }
  else
  {
    run_frames(frames > 0 ? frames : 600);
  }

  if (png)
    save_screenshot(png, scale);

  if (watch_count && verbose)
    fprintf(stderr, "[watch] hits: %ld\n", watch_hits);
  if (watch_fp)
    fclose(watch_fp);

  audio_shutdown();
  return 0;
}
