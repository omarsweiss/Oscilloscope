#include "myapp.h"
#define ADC_BUF_LEN 50
uint16_t snapshot[2*ADC_BUF_LEN];
uint16_t adcBuf[2*ADC_BUF_LEN]; // Multiplied by two because the DMA is configured as 1 Word and this is a uint16_t array.
TaskHandle_t initTaskH = NULL;
TaskHandle_t TxTaskH = NULL;
void initTask(void* pvParameters);
void TxTask(void* pvParameters);

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc){
    HAL_TIM_Base_Stop(&htim3);
    memcpy(snapshot, adcBuf, sizeof(adcBuf));
    vTaskNotifyGiveFromISR(TxTaskH, pdFALSE);
    HAL_TIM_Base_Start(&htim3);
}
void initTask(void *pvParameters){
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
    HAL_ADCEx_Calibration_Start(&hadc2, ADC_SINGLE_ENDED);
    HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
    HAL_ADCEx_MultiModeStart_DMA(&hadc1, (uint32_t*)adcBuf, 50);
    HAL_TIM_Base_Start(&htim3);


    vTaskDelete(NULL);
}

void TxTask(void* pvParameters){
    for(;;){
    ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
    CDC_Transmit_FS((uint8_t*)snapshot, 2*sizeof(snapshot));
    
    }
}
void myapp(void){
if(xTaskCreate(initTask,
            NULL,
            100,
            NULL,
            2,
            &initTaskH) != pdPASS){
                printf("Here");
            }
if(xTaskCreate(TxTask,
            NULL,
            200,
            NULL,
            1,
            &TxTaskH)!= pdPASS){
                printf("Here");
            }
vTaskStartScheduler();
}