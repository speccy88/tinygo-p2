ENTRY(__entry)

/* P2 Hub RAM image with the proven loadp2/P2LLVM cog bootstrap. */
STACK_SIZE = 0xc000;
HEAP_SIZE = 0xc000;

SECTIONS {
    . = 0x00000;
    .text : {
        /* Reset starts in cog-local instruction memory at word 0. */
        KEEP(*(.text.__entry));
        /* The entry jumps to cog word 0x10 (byte address 0x40). */
        . = 0x40;
        KEEP(__start0())
        KEEP(__start())
        KEEP(*(cog))
        /* Keep established P2LLVM cog/LUT reservation semantics. */
        . = 0x00200;
        KEEP(*(lut))
        /* Hub-resident ordinary Go code begins beyond cog/LUT space. */
        . = 0x00a00;
        *(.text*);
    }
    .rodata : { *(.rodata*); }
    .data : {
        _data_start = .;
        *(.data*);
        _data_end = .;
        PROVIDE(__enable_p2db = .);
        LONG(0)
        _init_array_start = .; KEEP(*(.init_array)) _init_array_end = .;
        _fini_array_start = .; KEEP(*(.fini_array)) _fini_array_end = .;
    }
    .bss (NOLOAD) : {
        _bss_start = .;
        *(.bss*);
        *(COMMON);
        _bss_end = .;
    }
    _globals_start = _data_start;
    _globals_end = _bss_end;
    .heap (NOLOAD) : {
        . = ALIGN(4);
        _heap_start = .;
        __heap_start = .;
        . = . + HEAP_SIZE;
        _heap_end = .;
    }
    .stack 0x7c000 - STACK_SIZE (NOLOAD) : {
        _stack_bottom = .;
        . = ALIGN(4);
        . = . + STACK_SIZE;
        _stack_top = .;
        __stack = _stack_bottom;
    }
    ASSERT(_heap_end <= _stack_bottom, "P2 Hub RAM heap/stack overlap")
    _end = _stack_top;
}
