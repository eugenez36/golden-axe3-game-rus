/* Minimal OSD layer for the headless Genesis Plus GX build.
 * No SDL, no libretro-common -- only libc and zlib.
 * t_config mirrors the libretro port: the core reads these fields directly.
 */
#ifndef _OSD_H
#define _OSD_H

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define MAX_INPUTS  8
#define MAX_KEYS    8
#define MAXPATHLEN  1024

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif
#ifndef M_PI
#define M_PI 3.1415926535897932385
#endif

#define CHEATS_UPDATE() ROMCheatUpdate()

#define HAVE_NO_SPRITE_LIMIT
#define MAX_SPRITES_PER_LINE 80
#define TMS_MAX_SPRITES_PER_LINE   (config.no_sprite_limit ? MAX_SPRITES_PER_LINE : 4)
#define MODE4_MAX_SPRITES_PER_LINE (config.no_sprite_limit ? MAX_SPRITES_PER_LINE : 8)
#define MODE5_MAX_SPRITES_PER_LINE (config.no_sprite_limit ? MAX_SPRITES_PER_LINE : (bitmap.viewport.w >> 4))
#define MODE5_MAX_SPRITE_PIXELS    (config.no_sprite_limit ? MAX_SPRITES_PER_LINE * 32 : max_sprite_pixels)

typedef struct
{
  int8 device;
  uint8 port;
  uint8 padtype;
} t_input_config;

typedef struct
{
  char version[16];
  uint8 hq_fm;
  uint8 filter;
  uint8 hq_psg;
  uint8 ym2612;
  uint8 ym2413;
  uint8 mono;
  int16 psg_preamp;
  int16 fm_preamp;
  int16 cdda_volume;
  int16 pcm_volume;
  uint16 lp_range;
  int16 low_freq;
  int16 high_freq;
  int16 lg;
  int16 mg;
  int16 hg;
  uint8 system;
  uint8 region_detect;
  uint8 master_clock;
  uint8 vdp_mode;
  uint8 force_dtack;
  uint8 addr_error;
  uint8 bios;
  uint8 lock_on;
  uint8 add_on;
  uint8 overscan;
  uint8 aspect_ratio;
  uint8 ntsc;
  uint8 lcd;
  uint8 gg_extra;
  uint8 left_border;
  uint8 render;
  t_input_config input[MAX_INPUTS];
  uint8 invert_mouse;
  uint8 gun_cursor;
  uint32 overclock;
  uint8 no_sprite_limit;
  uint8 enhanced_vscroll;
  uint8 enhanced_vscroll_limit;
  uint8 cd_latency;
} t_config;

extern t_config config;

extern char GG_ROM[256];
extern char AR_ROM[256];
extern char SK_ROM[256];
extern char SK_UPMEM[256];
extern char GG_BIOS[256];
extern char MD_BIOS[256];
extern char CD_BIOS_EU[256];
extern char CD_BIOS_US[256];
extern char CD_BIOS_JP[256];
extern char MS_BIOS_US[256];
extern char MS_BIOS_EU[256];
extern char MS_BIOS_JP[256];

extern void osd_input_update(void);
extern int  load_archive(char *filename, unsigned char *buffer, int maxsize, char *extension);
extern void ROMCheatUpdate(void);

/* CD images are not needed, but cd_hw references this layer -- plain FILE will do */
#ifndef cdStream
#define cdStream            FILE
#define cdStreamOpen(fname) fopen(fname, "rb")
#define cdStreamClose       fclose
#define cdStreamRead        fread
#define cdStreamSeek        fseek
#define cdStreamTell        ftell
#define cdStreamGets        fgets
#endif

#endif /* _OSD_H */
