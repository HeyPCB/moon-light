/*
 * Luna, the night-light moon - firmware for the CH32V003F4P6 (heypcb.ai merch 06), on ch32fun.
 *
 * What it does
 *   - Reads the room's light from an APDS-9306 once a second.
 *   - AUTO: when the room has been dark for 20 s, the eight orange LEDs fade up over 3 s to a candle-like
 *     glow; after the sleep timer (45 min by default) they fade out over 2 minutes. Then it waits for
 *     daylight before it can switch itself on again, so it never relights in the middle of the night.
 *   - Pat the gold cheek: on or off by hand (a manual "on" runs the same sleep timer).
 *   - Hold the cheek 1.5 s: next sleep timer, 15 / 45 / 90 min, shown as 1 / 2 / 3 blinks.
 *   While its own LEDs are on, the sensor sees their glow on the walls, so the dark threshold is ignored
 *   and only real daylight (a much higher reading) counts.
 *
 * Light sensor: Broadcom APDS-9306-065 at I2C 0x52 (AV02-4755EN): MAIN_CTRL 0x00 (bit 1 ALS_EN),
 * ALS_MEAS_RATE 0x04, ALS_GAIN 0x05, MAIN_STATUS 0x07 (bit 3 = new data), ALS_DATA 0x0D-0x0F (20 bits,
 * least significant byte first). Defaults kept: 18-bit resolution, 100 ms, gain 3. Bit-banged I2C
 * (ch32fun's static_i2c.h) with 10k pull-ups to 3.3 V.
 *
 * Pins (from the board's netlist; KiCad symbol MCU_WCH_RiscV:CH32V003FxPx), all at 3.3 V
 *   PC4 (pin 14) LED_PWM  TIM1 CH4, the AO3400A gate that switches all eight LEDs
 *   PD3 (pin 20) SDA, PD2 (pin 19) SCL
 *   PA2 (pin 6)  TOUCH, ADC channel 0, the gold cheek through 1k
 *   PD1 SWIO; the rest unconnected (pulled up)
 */
#include "ch32fun.h"
#include "ch32v00x_touch.h"

#define PIN_SDA PD3
#define PIN_SCL PD2
#define DELAY1 Delay_Us(2);
#define DELAY2 Delay_Us(4);
#define DSCL_IHIGH  { funPinMode(PIN_SCL, GPIO_CFGLR_IN_PUPD); funDigitalWrite(PIN_SCL, 1); }
#define DSDA_IHIGH  { funPinMode(PIN_SDA, GPIO_CFGLR_IN_PUPD); funDigitalWrite(PIN_SDA, 1); }
#define DSDA_INPUT  { funPinMode(PIN_SDA, GPIO_CFGLR_IN_PUPD); funDigitalWrite(PIN_SDA, 1); }
#define DSCL_OUTPUT { funDigitalWrite(PIN_SCL, 0); funPinMode(PIN_SCL, GPIO_CFGLR_OUT_2Mhz_PP); }
#define DSDA_OUTPUT { funDigitalWrite(PIN_SDA, 0); funPinMode(PIN_SDA, GPIO_CFGLR_OUT_2Mhz_PP); }
#define READ_DSDA funDigitalRead(PIN_SDA)
#define I2CNEEDGETBYTE 1
#include "static_i2c.h"

#define APDS_ADDR 0x52
#define DARK 40u            /* ALS counts (18-bit, gain 3): a dim bedroom at night; tune on hardware */
#define DAYLIGHT 4000u      /* morning: a hundred times the dark threshold, far above the moon's own glow */
#define DARK_FOR_S 20u
#define PWM_TOP 1000u
#define GLOW 600u           /* of PWM_TOP: a soft glow, about 60 mA of the 105 mA full string */

volatile uint32_t ms;
void SysTick_Handler(void) __attribute__((interrupt));
void SysTick_Handler(void)
{
    SysTick->CMP += DELAY_MS_TIME;
    SysTick->SR = 0;
    ms++;
}

/* ---- the light sensor ---- */
static int apds_write(uint8_t reg, uint8_t val)
{
    SendStart();
    int nak = SendByte(APDS_ADDR << 1) | SendByte(reg) | SendByte(val);
    SendStop();
    return nak ? -1 : 0;
}

static int apds_read(uint8_t reg, uint8_t *buf, int n)
{
    SendStart();
    if (SendByte(APDS_ADDR << 1) | SendByte(reg)) {
        SendStop();
        return -1;
    }
    SendStart();                                  /* repeated start */
    if (SendByte((APDS_ADDR << 1) | 1)) {
        SendStop();
        return -1;
    }
    for (int i = 0; i < n; i++)
        buf[i] = GetByte(i == n - 1);
    SendStop();
    return 0;
}

static int32_t room_light(void)                   /* ALS counts, or -1 when nothing new or no answer */
{
    uint8_t st, d[3];
    if (apds_read(0x07, &st, 1) || !(st & 0x08))
        return -1;
    if (apds_read(0x0D, d, 3))
        return -1;
    return (int32_t)(d[0] | (d[1] << 8) | ((uint32_t)(d[2] & 0x0F) << 16));
}

/* ---- the glow: TIM1 CH4 on PC4, 48 MHz / 48 / 1000 = 1 kHz ---- */
static void pwm_init(void)
{
    RCC->APB2PCENR |= RCC_APB2Periph_TIM1;
    funPinMode(PC4, GPIO_Speed_10MHz | GPIO_CNF_OUT_PP_AF);
    RCC->APB2PRSTR |= RCC_APB2Periph_TIM1;
    RCC->APB2PRSTR &= ~RCC_APB2Periph_TIM1;
    TIM1->PSC = 48 - 1;
    TIM1->ATRLR = PWM_TOP - 1;
    TIM1->CHCTLR2 |= TIM_OC4M_2 | TIM_OC4M_1;     /* PWM mode 1: high while the count is below CH4CVR */
    TIM1->CCER |= TIM_CC4E;
    TIM1->CH4CVR = 0;
    TIM1->SWEVGR |= TIM_UG;
    TIM1->BDTR |= TIM_MOE;
    TIM1->CTLR1 |= TIM_CEN;
}

static uint16_t level;                            /* 0..PWM_TOP, perceived brightness */
static void set_level(uint16_t l)
{
    level = l;
    TIM1->CH4CVR = (uint32_t)l * l / PWM_TOP;     /* square-law gamma: fades look even to the eye */
}

static void fade_to(uint16_t target, uint32_t over_ms)
{
    uint16_t from = level;
    uint32_t t0 = ms;
    while (ms - t0 < over_ms) {
        set_level((uint16_t)(from + ((int32_t)target - from) * (int32_t)(ms - t0) / (int32_t)over_ms));
        Delay_Ms(10);
    }
    set_level(target);
}

static void blinks(int n)
{
    for (int i = 0; i < n; i++) {
        set_level(GLOW);
        Delay_Ms(180);
        set_level(0);
        Delay_Ms(220);
    }
}

/* ---- the cheek ---- */
static uint32_t baseline;
static int touched(void)
{
    uint32_t v = ReadTouchPin(GPIOA, 2, 0, 3);
    if (v > baseline + baseline / 16 + 20)        /* tune on hardware */
        return 1;
    baseline = (baseline * 15 + v) / 16;
    return 0;
}

int main(void)
{
    SystemInit();
    funGpioInitAll();
    RCC->APB2PCENR |= RCC_APB2Periph_ADC1;
    static const uint8_t unused[] = { PD4, PD5, PD6, PA1, PD0, PC0, PC1, PC2, PC3, PC5, PC6, PC7 };
    for (unsigned i = 0; i < sizeof unused; i++) {
        funPinMode(unused[i], GPIO_CNF_IN_PUPD);
        funDigitalWrite(unused[i], FUN_HIGH);
    }
    SysTick->CTLR = 0;
    SysTick->CMP = DELAY_MS_TIME - 1;
    SysTick->CNT = 0;
    SysTick->CTLR = SYSTICK_CTLR_STE | SYSTICK_CTLR_STIE | SYSTICK_CTLR_STCLK;
    NVIC_EnableIRQ(SysTick_IRQn);
    pwm_init();
    InitTouchADC();
    funPinMode(PIN_SDA, GPIO_CFGLR_IN_PUPD);
    funPinMode(PIN_SCL, GPIO_CFGLR_IN_PUPD);
    ConfigI2C();
    Delay_Ms(10);
    apds_write(0x00, 0x02);                       /* MAIN_CTRL: ALS on */
    for (int i = 0; i < 16; i++)
        baseline += ReadTouchPin(GPIOA, 2, 0, 3);
    baseline /= 16;
    blinks(1);                                    /* hello */

    static const uint32_t timers_min[3] = { 15, 45, 90 };
    int timer_idx = 1;
    int lit = 0, armed = 1;
    uint32_t dark_s = 0, lit_since = 0, last_read = 0, held = 0;
    int was = 0;
    for (;;) {
        uint32_t now = ms;
        if (now - last_read >= 1000) {
            last_read = now;
            int32_t lux = room_light();
            if (lux >= 0) {
                if (lux >= (int32_t)DAYLIGHT) {   /* morning: re-arm, and stop glowing in daylight */
                    armed = 1;
                    if (lit) {
                        fade_to(0, 5000);
                        lit = 0;
                    }
                }
                dark_s = (!lit && lux < (int32_t)DARK) ? dark_s + 1 : 0;
                if (!lit && armed && dark_s >= DARK_FOR_S) {
                    fade_to(GLOW, 3000);
                    lit = 1;
                    lit_since = ms;
                }
            }
            if (lit && ms - lit_since >= timers_min[timer_idx] * 60000UL) {
                fade_to(0, 120000);               /* two minutes to dark */
                lit = 0;
                armed = 0;                        /* not again until daylight */
            }
        }

        int t = touched();
        if (t) {
            held += 20;
            if (held == 1500) {                   /* a long hold: the next sleep timer */
                timer_idx = (timer_idx + 1) % 3;
                uint16_t keep = level;
                blinks(timer_idx + 1);
                set_level(keep);
            }
        } else {
            if (was && held < 1500) {             /* a pat: on or off */
                if (lit) {
                    fade_to(0, 1500);
                    lit = 0;
                    armed = 0;
                } else {
                    fade_to(GLOW, 1500);
                    lit = 1;
                    lit_since = ms;
                }
            }
            held = 0;
        }
        was = t;
        Delay_Ms(20);
    }
}
