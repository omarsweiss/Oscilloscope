#include "my_app.h"

void my_app(void);
void vTask1(void* pvParameters);
void vTask2(void* pvParameters);

void vTask1(void* pvParameters){
    for(;;){
    taskENTER_CRITICAL();
    printf("Hi from Task1\r\n");
    taskEXIT_CRITICAL();
    }
}
void vTask2(void* pvParameters){
    for(;;){
    taskENTER_CRITICAL();
    printf("Hi from Task2\r\n");
    taskEXIT_CRITICAL();
    }
}


void my_app(void){
    xTaskCreate(vTask1,
"Task1",
100,
NULL,
1,
NULL);

xTaskCreate(vTask2,
"Task2",
100,
NULL,
1,
NULL);
vTaskStartScheduler();
    for(;;);
}