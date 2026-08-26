#include "callbacks.h"
#include "stm32g4xx_hal_adc.h"

HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc);

HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc){
    adcValue = HAL_ADC_GetValue(&hadc1);
}