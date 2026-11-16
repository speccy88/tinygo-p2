typedef unsigned char u8;
typedef unsigned int u32;

extern u8 _bss_start[], _bss_end[];
extern void main(void);
extern void __start(void);

__attribute__((noinline)) static void p2_clock_init(void) {
    const u32 setfreq = 0x010007f4u;
    const u32 enable = 0x010007f7u;
    __asm__ volatile (
        "hubset #0xf0\n\twaitx ##200000\n\thubset %0\n"
        "\twaitx ##200000\n\thubset %1"
        :: "r"(setfreq), "r"(enable) : "memory");
}

__attribute__((noinline)) static void p2_uart_init(void) {
    const u32 tx = 62, rx = 63;
    const u32 txmode = 0x7c, rxmode = 0x3e;
    const u32 period = ((160000000u / 115200u) << 16) | 7u;
    __asm__ volatile (
        "dirl %0\n\twrpin %1, %0\n\twxpin %2, %0\n\tdirh %0"
        :: "r"(tx), "r"(txmode), "r"(period) : "memory");
    __asm__ volatile (
        "dirl %0\n\twrpin %1, %0\n\twxpin %2, %0\n\tdirh %0"
        :: "r"(rx), "r"(rxmode), "r"(period) : "memory");
}

void raw_p2_uart_putc(u8 c) {
    const u32 tx = 62;
    __asm__ volatile ("wypin %0, %1\n\twaitx #20"
                      :: "r"((u32)c), "r"(tx) : "memory");
    for (;;) {
        u32 done;
        __asm__ volatile ("testp %1 wc\n\twrc %0"
                          : "=r"(done) : "r"(tx) : "memory");
        if (done) return;
    }
}

u32 raw_p2_uart_buffered(void) {
    u32 ready;
    const u32 rx = 63;
    __asm__ volatile ("testp %1 wc\n\twrc %0"
                      : "=r"(ready) : "r"(rx) : "memory");
    return ready;
}

u8 raw_p2_uart_getc(void) {
    while (!raw_p2_uart_buffered()) {}
    u32 value;
    const u32 rx = 63;
    __asm__ volatile ("rdpin %0, %1"
                      : "=r"(value) : "r"(rx) : "memory");
    return (u8)(value >> 24);
}

// Fixed cog IDs use the ready handshake; WC reports free-cog allocation status.
// P2 silicon doc, Starting and Stopping Cogs: https://p2docs.github.io/mirror/p2silicon.html
void p2_start_core(u32 cog, void *stack) {
    __asm__ volatile ("setq %1\n\tcoginit %0, %2"
                      :: "r"(cog), "r"(stack), "r"(__start) : "memory");
}

__attribute__((noreturn)) void p2_primary_entry(void) {
    for (u8 *p = _bss_start; p != _bss_end; ++p) *p = 0;
    p2_clock_init();
    p2_uart_init();
    main();
    for (;;) __asm__ volatile ("waitx #1");
}

__attribute__((noreturn)) void p2_halt(void) {
    for (;;) __asm__ volatile ("waitx #511");
}
