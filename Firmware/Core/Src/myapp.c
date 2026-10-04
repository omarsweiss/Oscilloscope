#include "myapp.h"
#define ADC_BUF_LEN 50
uint16_t adcBuf[ADC_BUF_LEN];
TaskHandle_t initTaskH = NULL;
void HAL_ADC_ConvHalfCpltCallback(&hadc1){

}
void initTask(void *pvParameters){
    HAL_ADC_Start_DMA(&hadc1, (uint32_t*)adcBuf, 50);
    HAL_TIM_Base_Start_IT(&htim3);

    vTaskDelete(NULL);
}
void myapp(void){
xTaskCreate(initTask,
     NULL,
      100,
       NULL,
        2,
         &initTaskH);
    vTaskStartScheduler();
}