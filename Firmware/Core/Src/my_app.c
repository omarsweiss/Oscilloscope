#include "my_app.h"
#include "projdefs.h"
#include "usbd_def.h"


void my_app(void);
void vTask1(void* pvParameters);


void vTask1(void* pvParameters){
    
    for(;;){
        CDC_Transmit_FS((uint8_t*) adcVal, sizeof(adcVal));
        
    }
}



void my_app(void){
    
    
    xTaskCreate(vTask1,
"Task1",
100,
NULL,
2,
NULL);

vTaskStartScheduler();
    }
