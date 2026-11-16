#include "myapp.h"
#define ADC_BUF_LEN 16000
//removed snapshot cause I changed from continuous to one shot mode
uint16_t adcBuf[2*ADC_BUF_LEN]; // Multiplied by two because the DMA is configured as 1 Word and this is a uint16_t array.
TaskHandle_t initTaskH = NULL;
TaskHandle_t TxTaskH = NULL;
StreamBufferHandle_t commands = NULL;
static const uint16_t sinewave[64] = {
    2048, 2244, 2438, 2629, 2813, 2991, 3159, 3317,
    3462, 3594, 3711, 3812, 3896, 3962, 4010, 4038,
    4048, 4038, 4010, 3962, 3896, 3812, 3711, 3594,
    3462, 3317, 3159, 2991, 2813, 2629, 2438, 2244,
    2048, 1852, 1658, 1467, 1283, 1105,  937,  779,
     634,  502,  385,  284,  200,  134,   86,   58,
      48,   58,   86,  134,  200,  284,  385,  502,
     634,  779,  937, 1105, 1283, 1467, 1658, 1852,
};   // dac codes for 12bits


void initTask(void* pvParameters);
void TxTask(void* pvParameters);
void pwm_set(uint32_t hz, uint32_t duty){
    uint32_t ticks = 48000000 / hz;
    uint32_t psc = ticks / 65536u; 
    uint32_t arr = ticks / (psc + 1) - 1;
    __HAL_TIM_SET_PRESCALER(&htim1, psc);
    __HAL_TIM_SET_AUTORELOAD(&htim1, arr);
    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, (arr + 1) * duty / 10000);
    HAL_TIM_GenerateEvent(&htim1, TIM_EVENTSOURCE_UPDATE);
}
// DAC sine frequency on PA4: only TIM6's speed changes, the table and DMA keep running
static void dac_set(uint32_t hz){
    if (hz == 0 || hz > 15000u) return;            // ~1 MSPS DAC limit / 64 points
    uint32_t ticks = 48000000u / (hz * 64u);       // timer ticks per table step
    uint32_t psc = ticks / 65536u;
    uint32_t arr = ticks / (psc + 1) - 1;
    HAL_TIM_Base_Stop(&htim6);
    __HAL_TIM_SET_PRESCALER(&htim6, psc);
    __HAL_TIM_SET_AUTORELOAD(&htim6, arr);
    __HAL_TIM_SET_COUNTER(&htim6, 0);
    HAL_TIM_GenerateEvent(&htim6, TIM_EVENTSOURCE_UPDATE);
    HAL_TIM_Base_Start(&htim6);
}

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc){
    HAL_TIM_Base_Stop(&htim3);
    BaseType_t woken = pdFALSE;
    vTaskNotifyGiveFromISR(TxTaskH, &woken);
    portYIELD_FROM_ISR(woken);
}
void initTask(void *pvParameters){
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
    HAL_ADCEx_Calibration_Start(&hadc2, ADC_SINGLE_ENDED);
    HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
    HAL_DAC_Start_DMA(&hdac1, DAC_CHANNEL_1, (const uint32_t*)sinewave, 64, DAC_ALIGN_12B_R);
    HAL_TIM_Base_Start(&htim6);

    vTaskDelete(NULL); //self deleting task to init PWM and dual interleaved ADC's triggered by a timer
}
void cmdTask(void* pvParameters){
    Cmd cmd;
    for(;;){
    xStreamBufferReceive(commands, &cmd, sizeof(cmd),portMAX_DELAY);
    switch (cmd.id){
        case 1: pwm_set(cmd.freq_hz,cmd.dutyx100); break;
        case 2: dac_set(cmd.freq_hz); break;
        default: break;
    }
    }
}

void TxTask(void* pvParameters){
    for(;;){
    HAL_ADCEx_MultiModeStart_DMA(&hadc1, (uint32_t*)adcBuf, ADC_BUF_LEN);
    HAL_TIM_Base_Start(&htim3);
    ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
    HAL_ADCEx_MultiModeStop_DMA(&hadc1);
        if (hUsbDeviceFS.dev_state != USBD_STATE_CONFIGURED){
            vTaskDelay(pdMS_TO_TICKS(100));                // PC not connected yet
            continue;
        }

    CDC_Transmit_FS((uint8_t*)adcBuf, sizeof(adcBuf));
    ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
    }
}
void myapp(void){
    commands = xStreamBufferCreate(64, sizeof(Cmd));

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
               if(xTaskCreate(cmdTask,
                 NULL,
                  256,
                   NULL, 
                   1,
                    NULL) != pdPASS){
        printf("Here");
    }
vTaskStartScheduler();
}