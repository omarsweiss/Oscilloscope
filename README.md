# Scope

## MCU Configuration (CubeMX)

- **ADC1 + ADC2** run in dual interleaved mode with ADC1 as the master.
- **ADC clock** - 48 MHz with 6.5 sec sample time.
- **Conversion time** is `t_conv = t_sample + 12.5 = 19 cycles`.
- **ADC2** interleaving offset is 9 cycles
- **TIM3 triggers ADC1**: no prescaler, ARR = 18 (a 19-tick period equal to t_conv).
- **DMA** is circular with word-sized transfers, carrying both packed results
  per transfer.
- **PWM** As a quick test signal
This comes out to 5.05 MSPS

Data is being sent through USB CDC Fullspeed, around 500kb/s 
