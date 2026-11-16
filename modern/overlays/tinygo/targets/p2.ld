ENTRY(__entry)

STACK_SIZE = 0x4000;
HUB_LIMIT = 0x7c000;
PROVIDE(__p2_secondary_stack_bytes = 7 * 8192);

SECTIONS {
    . = 0;
    .text : {
        KEEP(*(.text.__entry))
        . = 0x14;
        _clkfreq = .; LONG(160000000)
        _clkmode = .; LONG(0x010007f7)
        _dbgbaud = .; LONG(115200)
        . = 0x40;
        KEEP(*(.p2.boot))
        ASSERT(__start0 == 0x40, "P2 reset jump requires boot at hub address 0x40")
        KEEP(*(cog))
        ASSERT(. <= 0x200, "P2 cog startup exceeds reserved image")
        . = 0x200;
        __p2_lut_load_start = .;
        KEEP(*(lut))
        KEEP(*(.lut .lut.*))
        __p2_lut_load_end = .;
        ASSERT(__p2_lut_load_end - __p2_lut_load_start <= 0x800,
               "P2 LUT image exceeds 512 longs")
        . = 0xa00;
        *(.text*)
    }
    .rodata : { *(.rodata*) }
    .data : {
        . = ALIGN(8);
        _data_start = .;
        *(.data*)
        _data_end = .;
    }
    .bss (NOLOAD) : {
        . = ALIGN(8);
        _bss_start = .;
        *(.bss*) *(COMMON)
        . = ALIGN(8);
        _bss_end = .;
    }
    _globals_start = _data_start;
    _globals_end = _bss_end;
    .stack.secondary (NOLOAD) : {
        . = ALIGN(8);
        _p2_secondary_stacks = .;
        . += __p2_secondary_stack_bytes;
    }
    _heap_start = ALIGN(8);
    __heap_start = _heap_start;
    _heap_end = HUB_LIMIT - STACK_SIZE;
    .stack HUB_LIMIT - STACK_SIZE (NOLOAD) : {
        _stack_bottom = .;
        __stack = .;
        . += STACK_SIZE;
        _stack_top = .;
    }
    ASSERT(_heap_start + 0x10000 <= _heap_end, "P2 requires at least 64 KiB heap")
    _end = _stack_top;
}
