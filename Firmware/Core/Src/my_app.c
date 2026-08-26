#include "my_app.h"
#include "usbd_cdc_if.h"
#include <stdint.h>

void my_app(void);
void vTask1(void* pvParameters);
void vTask2(void* pvParameters);
uint16_t adcValue=0;
void vTask1(void* pvParameters){
    char* msg = (char*) pvParameters;
    for(;;){
    taskENTER_CRITICAL();
    CDC_Transmit_FS((uint8_t*) adcValue , 2);
    taskEXIT_CRITICAL();
    }
}
void vTask2(void* pvParameters){
    char* msg = (char*) pvParameters;
    for(;;){
        taskENTER_CRITICAL();
    CDC_Transmit_FS((uint8_t*) msg , strlen(msg));
    taskEXIT_CRITICAL();
    }
}


void my_app(void){
    char* msgUSB1 = "USB1 ADC Value";
    char* msgUSB2 = "USB2\n";
    xTaskCreate(vTask1,
"Task1",
100,
(void*) msgUSB1,
1,
NULL);

xTaskCreate(vTask2,
"Task2",
100,
(void*) msgUSB2,
2,
NULL);
vTaskStartScheduler();
    for(;;);
}