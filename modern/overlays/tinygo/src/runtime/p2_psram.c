//go:build ignore

// P2-EC32MB SPI initialization follows APS6404L rev 2.3 sections 10 and 12.
// https://www.pjrc.com/store/APS6404L_3SQR.pdf
typedef unsigned int u32;
#define DATA_MASK 0x00ffff00u
#define MOSI_MASK 0x00111100u

static void pins(u32 value) {
    __asm__ volatile ("andn outb, %0\n\tor outb, %1" :: "r"(DATA_MASK), "r"(value) : "memory");
}
static void pulse(void) {
    __asm__ volatile ("outh #56\n\toutl #56" ::: "memory");
}
static void select_ram(void) { __asm__ volatile ("outl #57" ::: "memory"); }
static void release_ram(void) { __asm__ volatile ("outh #57" ::: "memory"); }
static void spi_byte(u32 value) {
    for (u32 bit = 0x80; bit; bit >>= 1) {
        pins(value & bit ? MOSI_MASK : 0);
        pulse();
    }
}
static void spi_command(u32 command) {
    select_ram(); spi_byte(command); release_ram();
}
static u32 spi_read_parallel(void) {
    u32 result = 0;
    for (u32 bit = 8; bit; --bit) {
        u32 sample;
        __asm__ volatile ("outh #56\n\tmov %0, inb\n\toutl #56" : "=r"(sample) :: "memory");
        result <<= 1;
        result |= ((sample >> 9) & 1) | (((sample >> 13) & 1) << 8)
               | (((sample >> 17) & 1) << 16) | (((sample >> 21) & 1) << 24);
    }
    return result;
}

// IDs are stored as eight parallel words (byte bank0..bank3 per word).
void p2_psram_init(u32 *ids) {
    for (u32 pin = 40; pin <= 57; ++pin) {
        __asm__ volatile ("dirl %0\n\twrpin #0, %0" :: "r"(pin) : "memory");
    }
    __asm__ volatile ("outl #56\n\touth #57\n\tdirh #56\n\tdirh #57" ::: "memory");
    __asm__ volatile ("or dirb, %0" :: "r"(DATA_MASK) : "memory");
    pins(0);
    __asm__ volatile ("waitx %0" :: "r"(32000) : "memory");
    // Exit QPI after a warm reset. SPI mode discards this incomplete command.
    select_ram(); pins(0x00ffff00); pulse(); pins(0x00555500); pulse(); release_ram();
    __asm__ volatile ("andn dirb, %0\n\tor dirb, %1" :: "r"(DATA_MASK), "r"(MOSI_MASK) : "memory");
    spi_command(0x66); spi_command(0x99);
    __asm__ volatile ("waitx #32" ::: "memory");
    select_ram(); spi_byte(0x9f); spi_byte(0); spi_byte(0); spi_byte(0);
    for (u32 i = 0; i < 8; ++i) ids[i] = spi_read_parallel();
    release_ram();
    spi_command(0x35);
    __asm__ volatile ("andn dirb, %0" :: "r"(DATA_MASK) : "memory");
}
