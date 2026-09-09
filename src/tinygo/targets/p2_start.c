/* TinyGo P2 Phase 2 startup and primitives.
 *
 * P2 reset begins in cog-local instruction memory.  __entry and the cogmain
 * trampoline preserve the proven P2LLVM boot layout: entry at cog address 0,
 * a branch to cog word 0x10, and a cog restart before Hub-resident Go code is
 * called.  No generated-C prologue may touch PTRA before __start sets it.
 */
typedef unsigned char u8;
typedef unsigned int u32;

extern u8 _bss_start[], _bss_end[];
extern u8 _stack_bottom[];
extern void main(void);
extern void __start(void);

static u32 p2_lock;

static void p2_clock_160mhz(void) {
    /* _SETFREQ for 20MHz XOSC /1 *8 = 160MHz: 0x010007f4.
     * HUBSET immediate encoding is only nine bits: use registers for the
     * complete clock words, otherwise the upper configuration bits vanish. */
    const u32 setfreq = 0x010007f4u;
    const u32 enable = 0x010007f7u;
    __asm__ volatile ("hubset #0xf0\n\twaitx #200000\n\thubset %0\n\twaitx #200000\n\thubset %1"
                      :: "r"(setfreq), "r"(enable) : "memory");
}

static void p2_uart_init(void) {
    /* Smart-pin async console: TX pin 62, RX pin 63, 8N1 at 115200.
     * RX is deliberately only a thin hardware primitive; Go owns line framing,
     * parsing, command dispatch, state, and response formatting. */
    const u32 tx = 62;
    const u32 rx = 63;
    const u32 txmode = 0x7c; /* P_ASYNC_TX|P_TT_01 */
    const u32 rxmode = 0x3e; /* P_ASYNC_RX */
    const u32 bitperiod = ((160000000u / 115200u) << 16) | 7u;
    __asm__ volatile ("dirl %0\n\twrpin %1, %0\n\twxpin %2, %0\n\tdirh %0"
                      :: "r"(tx), "r"(txmode), "r"(bitperiod) : "memory");
    __asm__ volatile ("dirl %0\n\twrpin %1, %0\n\twxpin %2, %0\n\tdirh %0"
                      :: "r"(rx), "r"(rxmode), "r"(bitperiod) : "memory");
}

void raw_p2_uart_putc(u8 c) {
    const u32 tx = 62;
    __asm__ volatile ("wypin %0, %1\n\twaitx #20" :: "r"((u32)c), "r"(tx) : "memory");
    for (;;) {
        u32 done;
        __asm__ volatile ("testp %1 wc\n\twrc %0" : "=r"(done) : "r"(tx));
        if (done) break;
    }
}

/* Blocking one-byte RX only. No line buffering or protocol interpretation is
 * present in C: Go invokes this primitive and owns every higher-level action. */
u8 raw_p2_uart_getc(void) {
    const u32 rx = 63;
    for (;;) {
        u32 ready;
        __asm__ volatile ("testp %1 wc\n\twrc %0" : "=r"(ready) : "r"(rx));
        if (ready) {
            u32 value;
            __asm__ volatile ("rdpin %1, %0" : "=r"(value) : "r"(rx));
            return (u8)(value >> 24);
        }
    }
}

void p2_lock_acquire(void) {
    for (;;) {
        u32 acquired;
        __asm__ volatile ("locktry %1 wc\n\twrc %0" : "=r"(acquired) : "r"(p2_lock) : "memory");
        if (acquired) return;
    }
}
void p2_lock_release(void) { __asm__ volatile ("lockrel %0" :: "r"(p2_lock) : "memory"); }

/* The first cog-resident code.  cogmain suppresses a normal stack prologue;
 * the fixed word-address jump is the established P2LLVM loadp2 convention. */
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Winvalid-noreturn"
__attribute__((cogmain, noreturn, section(".text.__entry")))
void __entry(void) {
    __asm__ volatile ("jmp #\\0x10");
}

/* Restart cog 0 from the linker-placed cog image. */
__attribute__((cogmain, noreturn, section("cog")))
void __start0(void) {
    __asm__ volatile ("coginit #0, %0" : : "r"(__start));
    __builtin_unreachable();
}

/* This remains cog-resident only through startup.  After PTRA and BSS are
 * valid it calls Hub-resident clock/UART code and then ordinary TinyGo main. */
__attribute__((cogmain, noreturn, section("cog")))
void __start(void) {
    u8 *p;
    /* P2LLVM's established cog image copy: load cog words 0..511 from the
     * linker-arranged Hub image before executing the rest of startup. */
    __asm__ volatile ("setq2 #0x1ff\n\taugs #1\n\trdlong $0, #0" ::: "memory");
    __asm__ volatile ("mov ptra, %0" :: "r"(_stack_bottom) : "memory");
    for (p = _bss_start; p != _bss_end; ++p) *p = 0;
    p2_clock_160mhz();
    p2_uart_init();
    __asm__ volatile ("locknew %0" : "=r"(p2_lock) :: "memory");
    main();
    for (;;) __asm__ volatile ("waitx #1");
}
#pragma clang diagnostic pop

__attribute__((noreturn)) void p2_halt(void) {
    for (;;) __asm__ volatile ("waitx #1");
}
