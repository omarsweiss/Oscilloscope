#ifndef MYAPP_H
#define MYAPP_H
#include "main.h"
#include "FreeRTOS.h"
#include "task.h"
#include "usbd_cdc_if.h"
#include "string.h"
#include <math.h>
#include "stream_buffer.h"
void myapp(void);
void txcplt(void);
void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef *hadc);
extern StreamBufferHandle_t commands;     // was: extern uint8_t commands[64];
extern USBD_HandleTypeDef hUsbDeviceFS;
extern TaskHandle_t TxTaskH;
extern ADC_HandleTypeDef hadc1;
extern ADC_HandleTypeDef hadc2;
extern DMA_HandleTypeDef hdma_adc1;
extern TIM_HandleTypeDef htim3;
extern TIM_HandleTypeDef htim1;
extern DAC_HandleTypeDef hdac1;
extern TIM_HandleTypeDef htim6;
typedef struct __attribute__((packed)) {
    uint8_t  id;        // 1 = PWM, 2 = DAC
    uint32_t freq_hz;
    uint16_t dutyx100;         
} Cmd;                  
#endif