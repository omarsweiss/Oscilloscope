# Scope

## MCU Configuration (CubeMX)

- **ADC1 + ADC2** run in dual interleaved mode with ADC1 as the master.
- **ADC clock** - 48 MHz with 6.5 sec sample time.
- **Conversion time** is `t_conv = t_sample + 12.5 = 19 cycles`.
- **ADC2** interleaving offset is 9 cycles
- **TIM3 triggers ADC1**: no prescaler, ARR = 18 (a 19-tick period equal to t_conv).
- **DMA** is in normal mode (used to be circular) with word-sized transfers, carrying both packed results
  per transfer.
- **PWM** As a quick test signal
- Now working on implementing commands sent from pc -> mcu this is done by sending 7 bytes, for id(1byte),frequency(4bytes), duty cycle(2bytes) (packed struct)
This comes out to 5.05 MSPS

Data is being sent through USB CDC Fullspeed, around 500kb/s 
