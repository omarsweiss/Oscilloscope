/**
 * @file my_app.h
 * @author Omar Sweiss
 * @brief 
 * @version 0.1
 * @date 2026-08-23
 * 
 * @copyright Copyright (c) 2026
 * 
 */
#ifndef H_MY_APP
#define H_MY_APP
#include "stm32g4xx_hal.h"
#include <stdio.h>
#include "FreeRTOS.h"
#include "task.h"
#include "usbd_cdc_if.h"
#include <stdint.h>
#include <string.h>
extern ADC_HandleTypeDef hadc1;
void vTask1(void* pvParameters);
void vTask1(void* pvParameters);
void my_app(void);

#endif