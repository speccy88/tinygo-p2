/* SPDX-License-Identifier: MIT
 * C startup/serial harness. The GO image MUST resolve p2_add/p2_mix from go.o.
 * BASELINE is a separate, explicitly marked C-only transport control.
 */
#include <stdint.h>
#include <stdio.h>

#ifndef HOST_TEST
#include <propeller.h>
/* P2 Edge EC32MB Rev B previously identified: external 20 MHz TCXO.
 * Do not include p2es_clock.h: it hardcodes a crystal/capacitor configuration.
 * Verify this profile against the connected board before hardware execution.
 */
#ifndef P2_XTAL_HZ
#error P2_XTAL_HZ must be supplied by the build profile
#endif
#ifndef P2_XOSC
#error P2_XOSC must be supplied by the build profile
#endif
#define _XTALFREQ P2_XTAL_HZ
#define _XOSC P2_XOSC
#include <sys/p2_clock.h>
#endif

#ifdef BASELINE
#define IMAGE_MODE 'C'
static uint32_t payload_add(uint32_t a, uint32_t b) { return a + b; }
static uint32_t payload_mix(uint32_t a, uint32_t b) {
    uint32_t x = a ^ b;
    return ((x << 5) | (x >> 27)) + (a - b);
}
#else
#define IMAGE_MODE 'G'
extern uint32_t p2_add(uint32_t a, uint32_t b);
extern uint32_t p2_mix(uint32_t a, uint32_t b);
#define payload_add p2_add
#define payload_mix p2_mix
#endif

static void output_char(int c) { (void)putchar(c); }
static void output_text(const char *s) { while (*s) output_char(*s++); }
static void output_hex(uint32_t n) {
    static const char digits[] = "0123456789abcdef";
    int shift;
    for (shift = 28; shift >= 0; shift -= 4)
        output_char(digits[(n >> shift) & 15u]);
}
static void flush_output(void) {
#ifdef HOST_TEST
    (void)fflush(stdout);
#endif
}
static void ready(void) {
    output_text("READY "); output_char(IMAGE_MODE); output_text(" 1\r\n");
    flush_output();
}
static int parse_hex(const char *s, uint32_t *value) {
    unsigned i;
    uint32_t v = 0;
    for (i = 0; i < 8; ++i) {
        unsigned char c = (unsigned char)s[i];
        unsigned digit;
        if (c >= '0' && c <= '9') digit = c - '0';
        else if (c >= 'a' && c <= 'f') digit = c - 'a' + 10u;
        else if (c >= 'A' && c <= 'F') digit = c - 'A' + 10u;
        else return 0;
        v = (v << 4) | digit;
    }
    *value = v;
    return 1;
}
static void process_line(const char *line, unsigned length) {
    uint32_t id, a, b, sum, mix;
    if (length == 1 && line[0] == '?') { ready(); return; }
    if (length != 28 || line[0] != 'Q' || line[1] != ' ' ||
        line[10] != ' ' || line[19] != ' ' ||
        !parse_hex(line + 2, &id) || !parse_hex(line + 11, &a) ||
        !parse_hex(line + 20, &b)) {
        output_text("ERR INPUT\r\n"); flush_output(); return;
    }
    /* Inputs arrive AFTER boot. Neither function call is constant-foldable. */
    sum = payload_add(a, b);
    mix = payload_mix(a, b);
    output_text("R "); output_char(IMAGE_MODE); output_char(' ');
    output_hex(id); output_char(' '); output_hex(sum); output_char(' ');
    output_hex(mix); output_text("\r\n"); flush_output();
}
int main(void) {
    char line[64];
    unsigned length = 0;
    int overflow = 0;
#ifndef HOST_TEST
    _clkset(_SETFREQ, _CLOCKFREQ);
    _uart_init(DBG_UART_RX_PIN, DBG_UART_TX_PIN, 115200, 0);
#endif
    /* libc initializes stdin in cooked, echoing terminal mode. This binary
       protocol must receive each serial byte without echo or CR translation. */
#ifndef HOST_TEST
    stdin->_flag &= ~_IOCOOKED;
#endif
    ready();
    for (;;) {
        int c = getchar();
        if (c < 0) {
#ifdef HOST_TEST
            return 0;
#else
            continue;
#endif
        }
        if (c == '\r' || c == '\n') {
            if (overflow) { output_text("ERR OVERFLOW\r\n"); flush_output(); }
            else if (length) process_line(line, length);
            length = 0; overflow = 0;
        } else if (length < sizeof(line)) {
            line[length++] = (char)c;
        } else {
            overflow = 1;
        }
    }
}
