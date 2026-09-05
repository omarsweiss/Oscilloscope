#include "my_app.h"
#include "projdefs.h"
#include "stm32g474xx.h"
#include "usbd_def.h"
#include <stdint.h>
#include <string.h>


void my_app(void);
void vTask1(void* pvParameters);
void vTask1(void* pvParameters){

    for(;;){
        
        taskENTER_CRITICAL();
        while(CDC_Transmit_FS((uint8_t*) adcVal, sizeof(adcVal)) == USBD_BUSY){
            flag++;
        }
 
        taskEXIT_CRITICAL();
        
    }
}



void my_app(void){
    
    
    xTaskCreate(vTask1,
"Task1",
400,
NULL,
2,
NULL);

vTaskStartScheduler();
    }
