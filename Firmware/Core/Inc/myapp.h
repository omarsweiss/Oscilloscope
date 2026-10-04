#include "main.h"
#include "FreeRTOS.h"
#include "task.h"
void myapp(void);
void HAL_ADC_ConvHalfCpltCallback(ADC_HandleTypeDef *hadc);
extern ADC_HandleTypeDef hadc1;
extern DMA_HandleTypeDef hdma_adc1;
extern TIM_HandleTypeDef htim3;