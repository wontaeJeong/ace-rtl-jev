# ACE-RTL 실측 비교

기준 실행 상태: `completed`; 평가 범위 292/292.
개선 실행 상태: **미실행**.

| 지표 | 기준 실행 | JEV-like | 변화 (JEV − 기준 실행) |
|---|---:|---:|---:|
| 평가 케이스 수 | 292 | 미실행 | 자료 없음 |
| 성공 케이스 수 | 240 | 미실행 | 자료 없음 |
| 성공률 (0–1) | 0.822 | 미실행 | 자료 없음 |
| 총 토큰 (보고된 사용량 + 공개된 추정치) | 자료 없음 | 미실행 | 자료 없음 |
| 평균 토큰/케이스 | 자료 없음 | 미실행 | 자료 없음 |
| 총 실행 시간 (배치 경과 시간, 초) | 자료 없음 | 미실행 | 자료 없음 |
| 평균 실행 시간/케이스 (s) | 자료 없음 | 미실행 | 자료 없음 |
| 주력 LLM 호출 수 | 1294 | 미실행 | 자료 없음 |
| JEV-like 호출 수 | 0 | 미실행 | 자료 없음 |
| 평균 호출 지연 시간 (s) | 17.399 | 미실행 | 자료 없음 |
| 실패 및 오류 건수 | 52 | 미실행 | 자료 없음 |

실측 토큰 절감률 (%): 자료 없음.
실측 배치 경과 시간 절감률 (%): 자료 없음.

## 조건과 측정

```json
{
  "attempts": 1,
  "iterations": 5,
  "workers": 4,
  "llm_timeout": 90,
  "evaluator_timeout": 300,
  "case_timeout": 1800
}
```

준비 실행은 실제 추론이며 평가 지표에서 제외한다. 총 경과 시간은 동시 실행 배치의 실제 경과 시간이며, 평균 케이스 시간에는 하위 프로세스·평가기·수정 처리의 부가 시간이 포함된다. 재시도 호출, JEV 호출, 주력 모델 대체 호출을 모두 합산한다.
사용량이 없는 진행 중·오류 호출에는 비용이 없다고 임의로 가정하지 않는다. 과금이 미확인이면 토큰 절감률을 제시하지 않는다. 문자 수/4 추정치는 별도로 표시하며 실측 토큰 절감을 입증하지 못한다. 제공자의 캐시·적재 시간은 불투명할 수 있으며 별도 캐시는 추가하지 않았다.

## 제공자 사용량 집계

| 실행 방식/제공자 | 호출 수 | 보고된 입력 토큰 | 보고된 출력 토큰 | 보고된 총 토큰 | 추정 총 토큰 | 사용량 미확인 호출 | 대체 호출 | 평균 지연 (초) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 기준 실행/주력 모델 | 1294 | 14162840 | 2308144 | 16470984 | 0 | 26 | 0 | 17.399 |
| 기준 실행/JEV | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 자료 없음 |

## 케이스별 결과

| 케이스 | 기준 실행 | JEV-like | 기준 실행 시간 (초) | JEV 시간 (초) |
|---|---|---|---:|---:|
| `cvdp_copilot_16qam_mapper_0001` | 성공 | 미실행 | 17.325 | 자료 없음 |
| `cvdp_copilot_16qam_mapper_0006` | 성공 | 미실행 | 39.382 | 자료 없음 |
| `cvdp_copilot_32_bit_Brent_Kung_PP_adder_0001` | 성공 | 미실행 | 23.836 | 자료 없음 |
| `cvdp_copilot_64b66b_decoder_0001` | 성공 | 미실행 | 4.554 | 자료 없음 |
| `cvdp_copilot_64b66b_decoder_0011` | 실패 | 미실행 | 189.255 | 자료 없음 |
| `cvdp_copilot_64b66b_encoder_0001` | 성공 | 미실행 | 4.107 | 자료 없음 |
| `cvdp_copilot_64b66b_encoder_0005` | 성공 | 미실행 | 7.754 | 자료 없음 |
| `cvdp_copilot_64b66b_encoder_0009` | 성공 | 미실행 | 142.659 | 자료 없음 |
| `cvdp_copilot_64b66b_encoder_0022` | 성공 | 미실행 | 23.478 | 자료 없음 |
| `cvdp_copilot_8x3_priority_encoder_0001` | 성공 | 미실행 | 5.410 | 자료 없음 |
| `cvdp_copilot_8x3_priority_encoder_0013` | 성공 | 미실행 | 18.239 | 자료 없음 |
| `cvdp_copilot_Attenuator_0001` | 성공 | 미실행 | 19.520 | 자료 없음 |
| `cvdp_copilot_Carry_Lookahead_Adder_0001` | 성공 | 미실행 | 3.606 | 자료 없음 |
| `cvdp_copilot_Carry_Lookahead_Adder_0005` | 성공 | 미실행 | 51.138 | 자료 없음 |
| `cvdp_copilot_FIR_0001` | 성공 | 미실행 | 22.000 | 자료 없음 |
| `cvdp_copilot_FIR_0003` | 성공 | 미실행 | 20.309 | 자료 없음 |
| `cvdp_copilot_GFCM_0001` | 성공 | 미실행 | 65.647 | 자료 없음 |
| `cvdp_copilot_GFCM_0003` | 성공 | 미실행 | 40.419 | 자료 없음 |
| `cvdp_copilot_IIR_filter_0019` | 성공 | 미실행 | 77.811 | 자료 없음 |
| `cvdp_copilot_MSHR_0001` | 성공 | 미실행 | 170.827 | 자료 없음 |
| `cvdp_copilot_MSHR_0008` | 성공 | 미실행 | 93.476 | 자료 없음 |
| `cvdp_copilot_Serial_Line_Converter_0001` | 성공 | 미실행 | 80.484 | 자료 없음 |
| `cvdp_copilot_Serial_Line_Converter_0011` | 실패 | 미실행 | 175.224 | 자료 없음 |
| `cvdp_copilot_String_to_ASCII_0001` | 성공 | 미실행 | 19.572 | 자료 없음 |
| `cvdp_copilot_Synchronous_Muller_C_Element_0001` | 성공 | 미실행 | 11.558 | 자료 없음 |
| `cvdp_copilot_adc_data_rotate_0001` | 성공 | 미실행 | 15.004 | 자료 없음 |
| `cvdp_copilot_aes_key_expansion_0001` | 성공 | 미실행 | 45.740 | 자료 없음 |
| `cvdp_copilot_ahb_clk_counter_0001` | 성공 | 미실행 | 25.712 | 자료 없음 |
| `cvdp_copilot_alphablending_0003` | 성공 | 미실행 | 122.547 | 자료 없음 |
| `cvdp_copilot_apb_dsp_op_0002` | 실패 | 미실행 | 247.179 | 자료 없음 |
| `cvdp_copilot_apb_dsp_unit_0001` | 실패 | 미실행 | 206.017 | 자료 없음 |
| `cvdp_copilot_apb_gpio_0001` | 실패 | 미실행 | 178.146 | 자료 없음 |
| `cvdp_copilot_apb_gpio_0005` | 성공 | 미실행 | 125.261 | 자료 없음 |
| `cvdp_copilot_apb_history_shift_register_0001` | 실패 | 미실행 | 132.352 | 자료 없음 |
| `cvdp_copilot_arithmetic_progression_generator_0003` | 성공 | 미실행 | 22.555 | 자료 없음 |
| `cvdp_copilot_arithmetic_progression_generator_0015` | 성공 | 미실행 | 49.697 | 자료 없음 |
| `cvdp_copilot_async_filo_0001` | 성공 | 미실행 | 38.790 | 자료 없음 |
| `cvdp_copilot_async_filo_0025` | 성공 | 미실행 | 18.633 | 자료 없음 |
| `cvdp_copilot_axi_alu_0001` | 실패 | 미실행 | 331.361 | 자료 없음 |
| `cvdp_copilot_axi_register_0001` | 성공 | 미실행 | 29.046 | 자료 없음 |
| `cvdp_copilot_axi_stream_downscale_0001` | 실패 | 미실행 | 83.910 | 자료 없음 |
| `cvdp_copilot_axi_stream_upscale_0001` | 실패 | 미실행 | 98.996 | 자료 없음 |
| `cvdp_copilot_axi_tap_0001` | 성공 | 미실행 | 245.826 | 자료 없음 |
| `cvdp_copilot_axi_tap_0009` | 성공 | 미실행 | 120.077 | 자료 없음 |
| `cvdp_copilot_axil_precision_counter_0001` | 성공 | 미실행 | 105.620 | 자료 없음 |
| `cvdp_copilot_axis_border_gen_0001` | 실패 | 미실행 | 304.150 | 자료 없음 |
| `cvdp_copilot_axis_border_gen_0014` | 시간 초과 | 미실행 | 1330.764 | 자료 없음 |
| `cvdp_copilot_axis_joiner_0001` | 실패 | 미실행 | 206.083 | 자료 없음 |
| `cvdp_copilot_axis_mux_0001` | 성공 | 미실행 | 26.729 | 자료 없음 |
| `cvdp_copilot_barrel_shifter_0001` | 성공 | 미실행 | 4.030 | 자료 없음 |
| `cvdp_copilot_barrel_shifter_0037` | 성공 | 미실행 | 30.132 | 자료 없음 |
| `cvdp_copilot_barrel_shifter_0054` | 성공 | 미실행 | 16.673 | 자료 없음 |
| `cvdp_copilot_barrel_shifter_0058` | 성공 | 미실행 | 23.118 | 자료 없음 |
| `cvdp_copilot_barrel_shifter_0064` | 성공 | 미실행 | 21.778 | 자료 없음 |
| `cvdp_copilot_bcd_adder_0001` | 성공 | 미실행 | 14.880 | 자료 없음 |
| `cvdp_copilot_bcd_counter_0001` | 성공 | 미실행 | 11.658 | 자료 없음 |
| `cvdp_copilot_bcd_to_excess_3_0001` | 성공 | 미실행 | 4.134 | 자료 없음 |
| `cvdp_copilot_bcd_to_excess_3_0008` | 성공 | 미실행 | 5.668 | 자료 없음 |
| `cvdp_copilot_binary_multiplier_0012` | 성공 | 미실행 | 57.901 | 자료 없음 |
| `cvdp_copilot_binary_search_tree_sorting_0001` | 실패 | 미실행 | 372.752 | 자료 없음 |
| `cvdp_copilot_binary_search_tree_sorting_0014` | 시간 초과 | 미실행 | 604.659 | 자료 없음 |
| `cvdp_copilot_binary_to_BCD_0001` | 성공 | 미실행 | 6.185 | 자료 없음 |
| `cvdp_copilot_binary_to_BCD_0010` | 성공 | 미실행 | 21.595 | 자료 없음 |
| `cvdp_copilot_binary_to_BCD_0036` | 성공 | 미실행 | 8.329 | 자료 없음 |
| `cvdp_copilot_binary_to_gray_0001` | 성공 | 미실행 | 5.413 | 자료 없음 |
| `cvdp_copilot_binary_to_gray_0013` | 성공 | 미실행 | 4.819 | 자료 없음 |
| `cvdp_copilot_binary_to_one_hot_decoder_0001` | 성공 | 미실행 | 11.827 | 자료 없음 |
| `cvdp_copilot_bit_synchronizer_0001` | 성공 | 미실행 | 12.230 | 자료 없음 |
| `cvdp_copilot_bus_arbiter_0001` | 성공 | 미실행 | 50.777 | 자료 없음 |
| `cvdp_copilot_bus_arbiter_0004` | 성공 | 미실행 | 12.545 | 자료 없음 |
| `cvdp_copilot_cache_lru_0001` | 성공 | 미실행 | 69.721 | 자료 없음 |
| `cvdp_copilot_cache_lru_0008` | 성공 | 미실행 | 27.498 | 자료 없음 |
| `cvdp_copilot_cache_lru_0011` | 성공 | 미실행 | 26.292 | 자료 없음 |
| `cvdp_copilot_cache_lru_0016` | 성공 | 미실행 | 58.551 | 자료 없음 |
| `cvdp_copilot_cache_lru_0019` | 성공 | 미실행 | 150.293 | 자료 없음 |
| `cvdp_copilot_cache_lru_0022` | 성공 | 미실행 | 10.635 | 자료 없음 |
| `cvdp_copilot_caesar_cipher_0001` | 성공 | 미실행 | 13.294 | 자료 없음 |
| `cvdp_copilot_caesar_cipher_0024` | 성공 | 미실행 | 28.948 | 자료 없음 |
| `cvdp_copilot_caesar_cipher_0038` | 성공 | 미실행 | 12.097 | 자료 없음 |
| `cvdp_copilot_car_parking_management_0001` | 성공 | 미실행 | 38.217 | 자료 없음 |
| `cvdp_copilot_car_parking_management_0015` | 성공 | 미실행 | 38.475 | 자료 없음 |
| `cvdp_copilot_car_parking_management_0018` | 성공 | 미실행 | 180.095 | 자료 없음 |
| `cvdp_copilot_car_parking_management_0031` | 성공 | 미실행 | 73.350 | 자료 없음 |
| `cvdp_copilot_cascaded_adder_0001` | 성공 | 미실행 | 64.639 | 자료 없음 |
| `cvdp_copilot_cascaded_adder_0025` | 성공 | 미실행 | 89.524 | 자료 없음 |
| `cvdp_copilot_cdc_pulse_synchronizer_0004` | 성공 | 미실행 | 8.292 | 자료 없음 |
| `cvdp_copilot_cdc_pulse_synchronizer_0013` | 성공 | 미실행 | 13.939 | 자료 없음 |
| `cvdp_copilot_cellular_automata_0001` | 성공 | 미실행 | 35.267 | 자료 없음 |
| `cvdp_copilot_cellular_automata_0017` | 성공 | 미실행 | 19.511 | 자료 없음 |
| `cvdp_copilot_clock_divider_0003` | 성공 | 미실행 | 19.696 | 자료 없음 |
| `cvdp_copilot_clock_jitter_detection_module_0003` | 실패 | 미실행 | 237.221 | 자료 없음 |
| `cvdp_copilot_coffee_machine_0001` | 성공 | 미실행 | 122.116 | 자료 없음 |
| `cvdp_copilot_comparator_0001` | 성공 | 미실행 | 12.226 | 자료 없음 |
| `cvdp_copilot_complex_multiplier_0001` | 성공 | 미실행 | 17.553 | 자료 없음 |
| `cvdp_copilot_compression_engine_0001` | 성공 | 미실행 | 96.250 | 자료 없음 |
| `cvdp_copilot_concatenate_0001` | 실패 | 미실행 | 169.924 | 자료 없음 |
| `cvdp_copilot_configurable_digital_low_pass_filter_0001` | 성공 | 미실행 | 50.165 | 자료 없음 |
| `cvdp_copilot_configurable_digital_low_pass_filter_0004` | 성공 | 미실행 | 77.675 | 자료 없음 |
| `cvdp_copilot_configurable_digital_low_pass_filter_0011` | 실패 | 미실행 | 291.437 | 자료 없음 |
| `cvdp_copilot_configurable_digital_low_pass_filter_0014` | 성공 | 미실행 | 38.305 | 자료 없음 |
| `cvdp_copilot_cont_adder_0006` | 성공 | 미실행 | 29.389 | 자료 없음 |
| `cvdp_copilot_cont_adder_0023` | 성공 | 미실행 | 52.358 | 자료 없음 |
| `cvdp_copilot_cont_adder_0042` | 성공 | 미실행 | 101.147 | 자료 없음 |
| `cvdp_copilot_convolutional_encoder_0001` | 성공 | 미실행 | 6.414 | 자료 없음 |
| `cvdp_copilot_convolutional_encoder_0010` | 성공 | 미실행 | 5.699 | 자료 없음 |
| `cvdp_copilot_crossbar_switch_0001` | 성공 | 미실행 | 12.666 | 자료 없음 |
| `cvdp_copilot_data_bus_controller_0001` | 성공 | 미실행 | 48.551 | 자료 없음 |
| `cvdp_copilot_data_serializer_0001` | 성공 | 미실행 | 20.355 | 자료 없음 |
| `cvdp_copilot_data_width_converter_0003` | 성공 | 미실행 | 10.821 | 자료 없음 |
| `cvdp_copilot_dbi_0001` | 성공 | 미실행 | 16.909 | 자료 없음 |
| `cvdp_copilot_dbi_0008` | 성공 | 미실행 | 12.441 | 자료 없음 |
| `cvdp_copilot_dbi_dec_0001` | 성공 | 미실행 | 5.916 | 자료 없음 |
| `cvdp_copilot_decode_firstbit_0001` | 성공 | 미실행 | 34.053 | 자료 없음 |
| `cvdp_copilot_decoder_8b10b_0001` | 성공 | 미실행 | 9.487 | 자료 없음 |
| `cvdp_copilot_digital_dice_roller_0001` | 성공 | 미실행 | 95.465 | 자료 없음 |
| `cvdp_copilot_digital_dice_roller_0004` | 성공 | 미실행 | 34.152 | 자료 없음 |
| `cvdp_copilot_digital_stopwatch_0001` | 시간 초과 | 미실행 | 1374.366 | 자료 없음 |
| `cvdp_copilot_digital_stopwatch_0012` | 성공 | 미실행 | 77.681 | 자료 없음 |
| `cvdp_copilot_dot_product_0002` | 성공 | 미실행 | 23.619 | 자료 없음 |
| `cvdp_copilot_dot_product_0005` | 성공 | 미실행 | 119.108 | 자료 없음 |
| `cvdp_copilot_dot_product_0012` | 성공 | 미실행 | 19.338 | 자료 없음 |
| `cvdp_copilot_edge_detector_0001` | 성공 | 미실행 | 5.691 | 자료 없음 |
| `cvdp_copilot_elastic_buffer_0001` | 성공 | 미실행 | 20.356 | 자료 없음 |
| `cvdp_copilot_elevator_control_0006` | 성공 | 미실행 | 54.210 | 자료 없음 |
| `cvdp_copilot_elevator_control_0009` | 성공 | 미실행 | 85.455 | 자료 없음 |
| `cvdp_copilot_elevator_control_0026` | 성공 | 미실행 | 159.582 | 자료 없음 |
| `cvdp_copilot_elevator_control_0033` | 성공 | 미실행 | 44.057 | 자료 없음 |
| `cvdp_copilot_elevator_control_0036` | 성공 | 미실행 | 73.668 | 자료 없음 |
| `cvdp_copilot_ethernet_packet_parser_0001` | 성공 | 미실행 | 45.716 | 자료 없음 |
| `cvdp_copilot_events_to_apb_0001` | 성공 | 미실행 | 42.915 | 자료 없음 |
| `cvdp_copilot_factorial_0001` | 성공 | 미실행 | 17.441 | 자료 없음 |
| `cvdp_copilot_fan_controller_0001` | 성공 | 미실행 | 62.392 | 자료 없음 |
| `cvdp_copilot_fan_controller_0005` | 성공 | 미실행 | 17.447 | 자료 없음 |
| `cvdp_copilot_fan_controller_0008` | 실패 | 미실행 | 209.870 | 자료 없음 |
| `cvdp_copilot_fibonacci_series_0001` | 성공 | 미실행 | 44.082 | 자료 없음 |
| `cvdp_copilot_fifo_async_0001` | 성공 | 미실행 | 60.704 | 자료 없음 |
| `cvdp_copilot_fifo_to_axis_0001` | 실패 | 미실행 | 155.122 | 자료 없음 |
| `cvdp_copilot_fifo_to_axis_0005` | 성공 | 미실행 | 30.425 | 자료 없음 |
| `cvdp_copilot_filo_0005` | 성공 | 미실행 | 18.780 | 자료 없음 |
| `cvdp_copilot_filo_0033` | 성공 | 미실행 | 14.392 | 자료 없음 |
| `cvdp_copilot_findfasterclock_0001` | 성공 | 미실행 | 39.453 | 자료 없음 |
| `cvdp_copilot_flop_0001` | 성공 | 미실행 | 4.909 | 자료 없음 |
| `cvdp_copilot_flop_0002` | 성공 | 미실행 | 6.957 | 자료 없음 |
| `cvdp_copilot_fsm_seq_detector_0001` | 성공 | 미실행 | 14.458 | 자료 없음 |
| `cvdp_copilot_fsm_seq_detector_0023` | 성공 | 미실행 | 16.601 | 자료 없음 |
| `cvdp_copilot_galois_encryption_0001` | 실패 | 미실행 | 292.848 | 자료 없음 |
| `cvdp_copilot_gaussian_rounding_div_0003` | 성공 | 미실행 | 31.630 | 자료 없음 |
| `cvdp_copilot_gaussian_rounding_div_0005` | 실패 | 미실행 | 276.832 | 자료 없음 |
| `cvdp_copilot_gcd_0001` | 성공 | 미실행 | 28.823 | 자료 없음 |
| `cvdp_copilot_gcd_0009` | 성공 | 미실행 | 60.781 | 자료 없음 |
| `cvdp_copilot_gcd_0015` | 성공 | 미실행 | 34.730 | 자료 없음 |
| `cvdp_copilot_gcd_0023` | 성공 | 미실행 | 61.493 | 자료 없음 |
| `cvdp_copilot_generic_nbit_counter_0036` | 성공 | 미실행 | 16.461 | 자료 없음 |
| `cvdp_copilot_generic_nbit_counter_0039` | 성공 | 미실행 | 21.922 | 자료 없음 |
| `cvdp_copilot_gf_multiplier_0001` | 성공 | 미실행 | 8.101 | 자료 없음 |
| `cvdp_copilot_gf_multiplier_0005` | 성공 | 미실행 | 7.190 | 자료 없음 |
| `cvdp_copilot_gf_multiplier_0013` | 성공 | 미실행 | 33.952 | 자료 없음 |
| `cvdp_copilot_gf_multiplier_0021` | 성공 | 미실행 | 21.035 | 자료 없음 |
| `cvdp_copilot_gmii_axis_0001` | 성공 | 미실행 | 27.063 | 자료 없음 |
| `cvdp_copilot_gray_to_binary_0001` | 성공 | 미실행 | 13.260 | 자료 없음 |
| `cvdp_copilot_grayscale_image_0014` | 성공 | 미실행 | 30.642 | 자료 없음 |
| `cvdp_copilot_halfband_fir_0005` | 성공 | 미실행 | 22.956 | 자료 없음 |
| `cvdp_copilot_hamming_code_tx_and_rx_0001` | 성공 | 미실행 | 5.820 | 자료 없음 |
| `cvdp_copilot_hamming_code_tx_and_rx_0003` | 성공 | 미실행 | 19.253 | 자료 없음 |
| `cvdp_copilot_hamming_code_tx_and_rx_0009` | 성공 | 미실행 | 24.533 | 자료 없음 |
| `cvdp_copilot_hamming_code_tx_and_rx_0011` | 성공 | 미실행 | 24.540 | 자료 없음 |
| `cvdp_copilot_hamming_code_tx_and_rx_0013` | 성공 | 미실행 | 29.595 | 자료 없음 |
| `cvdp_copilot_hebbian_rule_0012` | 실패 | 미실행 | 419.858 | 자료 없음 |
| `cvdp_copilot_hebbian_rule_0017` | 실패 | 미실행 | 232.882 | 자료 없음 |
| `cvdp_copilot_hill_cipher_0001` | 성공 | 미실행 | 27.140 | 자료 없음 |
| `cvdp_copilot_hill_cipher_0015` | 성공 | 미실행 | 53.558 | 자료 없음 |
| `cvdp_copilot_hmac_register_0001` | 실패 | 미실행 | 242.428 | 자료 없음 |
| `cvdp_copilot_huffman_0001` | 성공 | 미실행 | 679.066 | 자료 없음 |
| `cvdp_copilot_icache_controller_0001` | 실패 | 미실행 | 301.767 | 자료 없음 |
| `cvdp_copilot_image_rotate_0001` | 실패 | 미실행 | 239.948 | 자료 없음 |
| `cvdp_copilot_image_rotate_0014` | 성공 | 미실행 | 95.552 | 자료 없음 |
| `cvdp_copilot_image_rotate_0015` | 성공 | 미실행 | 35.579 | 자료 없음 |
| `cvdp_copilot_image_stego_0004` | 성공 | 미실행 | 11.487 | 자료 없음 |
| `cvdp_copilot_interrupt_controller_0014` | 실패 | 미실행 | 259.656 | 자료 없음 |
| `cvdp_copilot_interrupt_controller_0017` | 실패 | 미실행 | 405.179 | 자료 없음 |
| `cvdp_copilot_interrupt_controller_0019` | 실패 | 미실행 | 228.309 | 자료 없음 |
| `cvdp_copilot_ir_receiver_0001` | 시간 초과 | 미실행 | 1767.215 | 자료 없음 |
| `cvdp_copilot_ir_receiver_0005` | 실패 | 미실행 | 388.079 | 자료 없음 |
| `cvdp_copilot_kogge_stone_adder_0007` | 성공 | 미실행 | 22.558 | 자료 없음 |
| `cvdp_copilot_lfsr_0007` | 성공 | 미실행 | 8.255 | 자료 없음 |
| `cvdp_copilot_line_buffer_0003` | 성공 | 미실행 | 59.898 | 자료 없음 |
| `cvdp_copilot_load_store_unit_0001` | 성공 | 미실행 | 83.695 | 자료 없음 |
| `cvdp_copilot_load_store_unit_0003` | 성공 | 미실행 | 33.385 | 자료 없음 |
| `cvdp_copilot_load_store_unit_0009` | 성공 | 미실행 | 249.361 | 자료 없음 |
| `cvdp_copilot_manchester_enc_0005` | 성공 | 미실행 | 1013.480 | 자료 없음 |
| `cvdp_copilot_manchester_enc_0013` | 성공 | 미실행 | 9.112 | 자료 없음 |
| `cvdp_copilot_matrix_multiplier_0001` | 성공 | 미실행 | 34.255 | 자료 없음 |
| `cvdp_copilot_matrix_multiplier_0007` | 성공 | 미실행 | 64.847 | 자료 없음 |
| `cvdp_copilot_matrix_multiplier_0010` | 성공 | 미실행 | 312.295 | 자료 없음 |
| `cvdp_copilot_mem_allocator_0001` | 성공 | 미실행 | 24.756 | 자료 없음 |
| `cvdp_copilot_microcode_sequencer_0001` | 실패 | 미실행 | 225.787 | 자료 없음 |
| `cvdp_copilot_modified_booth_mul_0002` | 성공 | 미실행 | 37.467 | 자료 없음 |
| `cvdp_copilot_modified_booth_mul_0005` | 성공 | 미실행 | 28.572 | 자료 없음 |
| `cvdp_copilot_montgomery_0001` | 실패 | 미실행 | 222.101 | 자료 없음 |
| `cvdp_copilot_montgomery_0002` | 실패 | 미실행 | 362.383 | 자료 없음 |
| `cvdp_copilot_morse_code_0001` | 성공 | 미실행 | 11.245 | 자료 없음 |
| `cvdp_copilot_morse_code_0014` | 성공 | 미실행 | 11.377 | 자료 없음 |
| `cvdp_copilot_moving_average_0001` | 성공 | 미실행 | 11.494 | 자료 없음 |
| `cvdp_copilot_moving_average_0005` | 성공 | 미실행 | 7.476 | 자료 없음 |
| `cvdp_copilot_mux_synch_0001` | 성공 | 미실행 | 59.838 | 자료 없음 |
| `cvdp_copilot_mux_synch_0011` | 성공 | 미실행 | 74.799 | 자료 없음 |
| `cvdp_copilot_nbit_swizzling_0001` | 성공 | 미실행 | 11.375 | 자료 없음 |
| `cvdp_copilot_nbit_swizzling_0014` | 성공 | 미실행 | 12.102 | 자료 없음 |
| `cvdp_copilot_nbit_swizzling_0020` | 성공 | 미실행 | 26.339 | 자료 없음 |
| `cvdp_copilot_neuromorphic_array_0001` | 성공 | 미실행 | 63.558 | 자료 없음 |
| `cvdp_copilot_one_hot_address_0001` | 성공 | 미실행 | 29.285 | 자료 없음 |
| `cvdp_copilot_packet_controller_0001` | 성공 | 미실행 | 32.572 | 자료 없음 |
| `cvdp_copilot_palindrome_3b_0002` | 성공 | 미실행 | 24.655 | 자료 없음 |
| `cvdp_copilot_password_generator_0001` | 성공 | 미실행 | 66.376 | 자료 없음 |
| `cvdp_copilot_perceptron_0001` | 성공 | 미실행 | 37.036 | 자료 없음 |
| `cvdp_copilot_perceptron_0006` | 실패 | 미실행 | 450.321 | 자료 없음 |
| `cvdp_copilot_perceptron_0013` | 실패 | 미실행 | 250.194 | 자료 없음 |
| `cvdp_copilot_perf_counters_0001` | 시간 초과 | 미실행 | 1608.700 | 자료 없음 |
| `cvdp_copilot_perfect_squares_0001` | 성공 | 미실행 | 14.648 | 자료 없음 |
| `cvdp_copilot_ping_pong_buffer_0001` | 실패 | 미실행 | 225.074 | 자료 없음 |
| `cvdp_copilot_pipeline_mac_0017` | 성공 | 미실행 | 86.283 | 자료 없음 |
| `cvdp_copilot_piso_0001` | 성공 | 미실행 | 8.853 | 자료 없음 |
| `cvdp_copilot_pkt_detector_0001` | 성공 | 미실행 | 44.553 | 자료 없음 |
| `cvdp_copilot_prbs_gen_0003` | 실패 | 미실행 | 206.828 | 자료 없음 |
| `cvdp_copilot_prim_max_0001` | 성공 | 미실행 | 22.608 | 자료 없음 |
| `cvdp_copilot_radix2_div_0001` | 성공 | 미실행 | 8.182 | 자료 없음 |
| `cvdp_copilot_reed_solomon_encoder_and_decoder_0005` | 실패 | 미실행 | 225.715 | 자료 없음 |
| `cvdp_copilot_register_file_2R1W_0006` | 실패 | 미실행 | 228.575 | 자료 없음 |
| `cvdp_copilot_register_file_2R1W_0013` | 성공 | 미실행 | 13.252 | 자료 없음 |
| `cvdp_copilot_restoring_division_0001` | 성공 | 미실행 | 24.737 | 자료 없음 |
| `cvdp_copilot_reverse_bits_0001` | 성공 | 미실행 | 3.650 | 자료 없음 |
| `cvdp_copilot_rgb2ycbcr_0001` | 성공 | 미실행 | 50.576 | 자료 없음 |
| `cvdp_copilot_round_robin_arbiter_0005` | 성공 | 미실행 | 24.133 | 자료 없음 |
| `cvdp_copilot_rounding_0001` | 실패 | 미실행 | 133.831 | 자료 없음 |
| `cvdp_copilot_rs_232_0001` | 성공 | 미실행 | 42.353 | 자료 없음 |
| `cvdp_copilot_run_length_0001` | 성공 | 미실행 | 28.025 | 자료 없음 |
| `cvdp_copilot_run_length_0007` | 성공 | 미실행 | 101.580 | 자료 없음 |
| `cvdp_copilot_scrambler_0001` | 성공 | 미실행 | 42.562 | 자료 없음 |
| `cvdp_copilot_scrambler_0009` | 실패 | 미실행 | 752.644 | 자료 없음 |
| `cvdp_copilot_scrambler_0018` | 성공 | 미실행 | 174.611 | 자료 없음 |
| `cvdp_copilot_scrambler_0024` | 성공 | 미실행 | 16.654 | 자료 없음 |
| `cvdp_copilot_sdram_controller_0001` | 성공 | 미실행 | 93.056 | 자료 없음 |
| `cvdp_copilot_secure_ALU_0001` | 성공 | 미실행 | 7.982 | 자료 없음 |
| `cvdp_copilot_secure_read_write_bus_0001` | 성공 | 미실행 | 10.356 | 자료 없음 |
| `cvdp_copilot_secure_read_write_register_bank_0001` | 성공 | 미실행 | 22.907 | 자료 없음 |
| `cvdp_copilot_secure_variable_timer_0001` | 성공 | 미실행 | 20.368 | 자료 없음 |
| `cvdp_copilot_sequencial_binary_to_one_hot_decoder_0001` | 성공 | 미실행 | 21.456 | 자료 없음 |
| `cvdp_copilot_serial_in_parallel_out_0004` | 성공 | 미실행 | 3.117 | 자료 없음 |
| `cvdp_copilot_serial_in_parallel_out_0011` | 성공 | 미실행 | 104.138 | 자료 없음 |
| `cvdp_copilot_serial_in_parallel_out_0014` | 실패 | 미실행 | 259.026 | 자료 없음 |
| `cvdp_copilot_set_bit_calculator_0001` | 성공 | 미실행 | 9.214 | 자료 없음 |
| `cvdp_copilot_sigma_delta_audio_0007` | 성공 | 미실행 | 28.635 | 자료 없음 |
| `cvdp_copilot_signal_correlator_0015` | 성공 | 미실행 | 10.958 | 자료 없음 |
| `cvdp_copilot_signed_adder_0001` | 성공 | 미실행 | 21.749 | 자료 없음 |
| `cvdp_copilot_simple_spi_0001` | 실패 | 미실행 | 205.847 | 자료 없음 |
| `cvdp_copilot_single_number_0001` | 성공 | 미실행 | 5.610 | 자료 없음 |
| `cvdp_copilot_skid_buffer_0001` | 실패 | 미실행 | 157.032 | 자료 없음 |
| `cvdp_copilot_sobel_filter_0011` | 성공 | 미실행 | 28.392 | 자료 없음 |
| `cvdp_copilot_sorter_0001` | 성공 | 미실행 | 61.834 | 자료 없음 |
| `cvdp_copilot_sorter_0003` | 성공 | 미실행 | 46.383 | 자료 없음 |
| `cvdp_copilot_sorter_0009` | 성공 | 미실행 | 62.438 | 자료 없음 |
| `cvdp_copilot_sorter_0031` | 성공 | 미실행 | 59.958 | 자료 없음 |
| `cvdp_copilot_sound_generator_0001` | 성공 | 미실행 | 34.424 | 자료 없음 |
| `cvdp_copilot_sprite_0004` | 실패 | 미실행 | 248.929 | 자료 없음 |
| `cvdp_copilot_sprite_0010` | 성공 | 미실행 | 95.779 | 자료 없음 |
| `cvdp_copilot_square_root_0003` | 성공 | 미실행 | 17.578 | 자료 없음 |
| `cvdp_copilot_static_branch_predict_0001` | 성공 | 미실행 | 90.525 | 자료 없음 |
| `cvdp_copilot_static_branch_predict_0009` | 성공 | 미실행 | 17.759 | 자료 없음 |
| `cvdp_copilot_static_branch_predict_0013` | 성공 | 미실행 | 97.624 | 자료 없음 |
| `cvdp_copilot_static_branch_predict_0014` | 성공 | 미실행 | 48.118 | 자료 없음 |
| `cvdp_copilot_strobe_divider_0001` | 성공 | 미실행 | 38.897 | 자료 없음 |
| `cvdp_copilot_swizzler_0009` | 성공 | 미실행 | 30.097 | 자료 없음 |
| `cvdp_copilot_swizzler_0014` | 성공 | 미실행 | 39.320 | 자료 없음 |
| `cvdp_copilot_sync_lifo_0001` | 성공 | 미실행 | 17.714 | 자료 없음 |
| `cvdp_copilot_sync_lifo_0010` | 성공 | 미실행 | 25.951 | 자료 없음 |
| `cvdp_copilot_sync_serial_communication_0001` | 시간 초과 | 미실행 | 자료 없음 | 자료 없음 |
| `cvdp_copilot_sync_serial_communication_0014` | 성공 | 미실행 | 220.571 | 자료 없음 |
| `cvdp_copilot_sync_serial_communication_0052` | 성공 | 미실행 | 38.694 | 자료 없음 |
| `cvdp_copilot_thermostat_0001` | 성공 | 미실행 | 16.381 | 자료 없음 |
| `cvdp_copilot_ttc_lite_0001` | 성공 | 미실행 | 40.208 | 자료 없음 |
| `cvdp_copilot_unpacker_one_hot_0001` | 성공 | 미실행 | 22.030 | 자료 없음 |
| `cvdp_copilot_vending_machine_0001` | 실패 | 미실행 | 264.748 | 자료 없음 |
| `cvdp_copilot_vga_controller_0001` | 성공 | 미실행 | 30.333 | 자료 없음 |
| `cvdp_copilot_vga_controller_0006` | 성공 | 미실행 | 38.457 | 자료 없음 |
| `cvdp_copilot_vga_controller_0026` | 성공 | 미실행 | 63.566 | 자료 없음 |
| `cvdp_copilot_virtual2physical_tlb_0001` | 실패 | 미실행 | 295.502 | 자료 없음 |
| `cvdp_copilot_wb2ahb_0001` | 실패 | 미실행 | 231.094 | 자료 없음 |
| `cvdp_copilot_word_change_detector_0001` | 성공 | 미실행 | 29.318 | 자료 없음 |
| `cvdp_copilot_word_reducer_0001` | 성공 | 미실행 | 21.559 | 자료 없음 |
| `cvdp_copilot_word_reducer_0008` | 성공 | 미실행 | 20.264 | 자료 없음 |
| `cvdp_copilot_write_buffer_merge_0001` | 성공 | 미실행 | 63.996 | 자료 없음 |
| `cvdp_copilot_write_through_data_direct_mapped_cache_0012` | 성공 | 미실행 | 10.548 | 자료 없음 |

## 한계

비에이전트 방식·비상용 도구의 제한된 네이티브 평가군 한 묶음으로, 모든 CVDP 작업 흐름이나 원래 기본 예산을 포괄하지 않는다. 실제 도구 요구에 따라 상용 도구가 필요한 항목을 명시적으로 제외했다. API의 확률적 변동과 원격 지연은 통제하지 못했으며, 단일 실행 차이는 관찰 결과일 뿐 통계적으로 입증된 효과가 아니다. 반복·요소 제거 실험은 실제 실행한 경우에만 보고해야 한다. 출처·무결성 규칙·남은 작업은 환경 및 개선 기회 문서를 참고한다.
