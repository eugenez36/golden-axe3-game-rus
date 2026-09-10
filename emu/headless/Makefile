# Headless build of Genesis Plus GX for ROM hacking.
# No SDL, no libretro -- only libc and zlib.
#
#   make                 build  -> $(BUILD)/headless_gpgx
#   make clean           remove objects and the binary
#
# Variables
#   GPGX   emulator core checkout (git submodule emu/gpgx with the dma_hook branch)
#   BUILD  where objects and the binary go; nothing is written into the core tree
#
# HOOK_CPU=1 enables the core's CPU hooks: without them watchpoints do not work.

GPGX     ?= $(abspath ../gpgx)
BUILD    ?= $(abspath ../../build/emu)
CORE     := $(GPGX)/core

SRC_DIRS := $(CORE) \
            $(CORE)/z80 \
            $(CORE)/m68k \
            $(CORE)/ntsc \
            $(CORE)/sound \
            $(CORE)/sound/minimp3 \
            $(CORE)/input_hw \
            $(CORE)/cd_hw \
            $(CORE)/cart_hw \
            $(CORE)/cart_hw/svp \
            $(CORE)/debug

CORE_SRCS := $(foreach d,$(SRC_DIRS),$(wildcard $(d)/*.c))
CORE_OBJS := $(patsubst $(GPGX)/%.c,$(BUILD)/obj/gpgx/%.o,$(CORE_SRCS))
MAIN_OBJ  := $(BUILD)/obj/headless/main.o
OBJECTS   := $(CORE_OBJS) $(MAIN_OBJ)

INCFLAGS := $(foreach d,$(SRC_DIRS),-I$(d)) -I$(CURDIR)

# USE_32BPP_RENDERING -- frames as XRGB8888, the easiest thing to turn into PNG
# HOOK_CPU            -- read/write/execute hooks (watchpoints, breakpoints, dma_hook)
DEFINES  := -DLSB_FIRST -DBYTE_ORDER=LITTLE_ENDIAN \
            -DUSE_32BPP_RENDERING \
            -DHOOK_CPU \
            -DHAVE_ZLIB \
            -DMAXROMSIZE=33554432 \
            -DHAVE_OVERCLOCK

# -fcommon:        cpuhook.h declares cpu_hook without extern -- gcc >= 10 would see duplicate definitions
# -include zlib.h: sram.c / sms_cart.c call crc32 without a declaration, truncating uLong to int
CFLAGS   ?= -O2 -fomit-frame-pointer
CFLAGS   += -std=gnu99 -fcommon -include zlib.h -MMD -MP \
            -Wno-unused-variable -Wno-unused-but-set-variable \
            -Wno-sign-compare -Wno-format-truncation \
            $(INCFLAGS) $(DEFINES)

LDLIBS   := -lz -lm

TARGET   := $(BUILD)/headless_gpgx

all: $(TARGET)

$(TARGET): $(OBJECTS)
	@mkdir -p $(@D)
	$(CC) -o $@ $^ $(LDLIBS)
	@echo "done: $@"

$(BUILD)/obj/gpgx/%.o: $(GPGX)/%.c
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/obj/headless/%.o: %.c
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) -c $< -o $@

-include $(OBJECTS:.o=.d)

check-core:
	@test -d $(CORE) || { echo "error: $(CORE) not found -- run: git submodule update --init"; exit 1; }
	@grep -q dma_hook $(CORE)/vdp_ctrl.c || { echo "error: $(CORE)/vdp_ctrl.c lacks the dma_hook (wrong branch?)"; exit 1; }
	@echo "core ok: $(GPGX)"

clean:
	rm -rf $(BUILD)/obj $(TARGET)

.PHONY: all clean check-core
