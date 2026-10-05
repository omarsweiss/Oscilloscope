# Scope

## MCU Configuration (CubeMX)

- **ADC1 + ADC2** run in dual interleaved mode with ADC1 as the master.
- **ADC clock** is 48 MHz (synchronous, from AHB) and sample time is 6.5 cycles.
- **Conversion time** is `t_sample + 12.5 = 19 cycles`.
- **ADC2 is offset from ADC1 by 9 cycles**, interleaving the two conversions.
- **TIM3 triggers the master ADC**: no prescaler, ARR = 18 (a 19-tick period).
  Since TIM3 also runs at 48 MHz, one timer tick equals one ADC cycle, so the
  trigger period is exactly one conversion time.
- **DMA** is circular with word-sized transfers, carrying both packed results
  per transfer.

This comes out to 5.05 MSPS

Data is being sent through USB CDC Fullspeed, around 500kb/s 