#include "my_app.h"
#include "stm32g4xx_hal_adc.h"
#include "usbd_cdc_if.h"
#include <stdint.h>

void my_app(void);
void vTask1(void* pvParameters);


void vTask1(void* pvParameters){
    
    
    for(;;){
    
    
    }
}



void my_app(void){
    char* msgUSB1 = "USB1 ADC Value";
    
    xTaskCreate(vTask1,
"Task1",
100,
(void*) msgUSB1,
2,
NULL);
    }
