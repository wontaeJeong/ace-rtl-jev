# ACE-RTL 실측 비교

기준 실행 상태: `completed`; 평가 범위 292/292.
개선 실행 상태: **미실행**.

| 지표 | 기준 실행 | JEV-like | 변화 (JEV − 기준 실행) |
|---|---:|---:|---:|
| 평가 케이스 수 | 292 | 미실행 | 자료 없음 |
| 성공 케이스 수 | 239 | 미실행 | 자료 없음 |
| 성공률 (0–1) | 0.818 | 미실행 | 자료 없음 |
| 총 토큰 (보고된 사용량 + 공개된 추정치) | 자료 없음 | 미실행 | 자료 없음 |
| 평균 토큰/케이스 | 자료 없음 | 미실행 | 자료 없음 |
| 총 실행 시간 (배치 경과 시간, 초) | 4367.250 | 미실행 | 자료 없음 |
| 평균 실행 시간/케이스 (s) | 109.631 | 미실행 | 자료 없음 |
| 주력 LLM 호출 수 | 1311 | 미실행 | 자료 없음 |
| JEV-like 호출 수 | 0 | 미실행 | 자료 없음 |
| 평균 호출 지연 시간 (s) | 17.161 | 미실행 | 자료 없음 |
| 실패 및 오류 건수 | 53 | 미실행 | 자료 없음 |

실측 토큰 절감률 (%): 자료 없음.
실측 배치 경과 시간 절감률 (%): 자료 없음.

## 조건과 측정

```json
{
  "attempts": 1,
  "iterations": 5,
  "workers": 8,
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
| 기준 실행/주력 모델 | 1311 | 14235838 | 2302443 | 16538281 | 0 | 33 | 0 | 17.161 |
| 기준 실행/JEV | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 자료 없음 |

## 케이스별 결과

| 케이스 | 기준 실행 | JEV-like | 기준 실행 시간 (초) | JEV 시간 (초) |
|---|---|---|---:|---:|
| `cvdp_copilot_16qam_mapper_0001` | 성공 | 미실행 | 35.501 | 자료 없음 |
| `cvdp_copilot_16qam_mapper_0006` | 성공 | 미실행 | 95.382 | 자료 없음 |
| `cvdp_copilot_32_bit_Brent_Kung_PP_adder_0001` | 성공 | 미실행 | 31.575 | 자료 없음 |
| `cvdp_copilot_64b66b_decoder_0001` | 성공 | 미실행 | 8.265 | 자료 없음 |
| `cvdp_copilot_64b66b_decoder_0011` | 성공 | 미실행 | 326.109 | 자료 없음 |
| `cvdp_copilot_64b66b_encoder_0001` | 성공 | 미실행 | 9.018 | 자료 없음 |
| `cvdp_copilot_64b66b_encoder_0005` | 성공 | 미실행 | 11.392 | 자료 없음 |
| `cvdp_copilot_64b66b_encoder_0009` | 실패 | 미실행 | 277.939 | 자료 없음 |
| `cvdp_copilot_64b66b_encoder_0022` | 성공 | 미실행 | 29.705 | 자료 없음 |
| `cvdp_copilot_8x3_priority_encoder_0001` | 성공 | 미실행 | 9.759 | 자료 없음 |
| `cvdp_copilot_8x3_priority_encoder_0013` | 성공 | 미실행 | 18.952 | 자료 없음 |
| `cvdp_copilot_Attenuator_0001` | 성공 | 미실행 | 27.714 | 자료 없음 |
| `cvdp_copilot_Carry_Lookahead_Adder_0001` | 성공 | 미실행 | 5.238 | 자료 없음 |
| `cvdp_copilot_Carry_Lookahead_Adder_0005` | 성공 | 미실행 | 57.079 | 자료 없음 |
| `cvdp_copilot_FIR_0001` | 성공 | 미실행 | 25.441 | 자료 없음 |
| `cvdp_copilot_FIR_0003` | 성공 | 미실행 | 16.615 | 자료 없음 |
| `cvdp_copilot_GFCM_0001` | 성공 | 미실행 | 51.759 | 자료 없음 |
| `cvdp_copilot_GFCM_0003` | 성공 | 미실행 | 81.588 | 자료 없음 |
| `cvdp_copilot_IIR_filter_0019` | 성공 | 미실행 | 140.332 | 자료 없음 |
| `cvdp_copilot_MSHR_0001` | 실패 | 미실행 | 326.406 | 자료 없음 |
| `cvdp_copilot_MSHR_0008` | 성공 | 미실행 | 49.528 | 자료 없음 |
| `cvdp_copilot_Serial_Line_Converter_0001` | 성공 | 미실행 | 66.562 | 자료 없음 |
| `cvdp_copilot_Serial_Line_Converter_0011` | 실패 | 미실행 | 251.145 | 자료 없음 |
| `cvdp_copilot_String_to_ASCII_0001` | 성공 | 미실행 | 23.014 | 자료 없음 |
| `cvdp_copilot_Synchronous_Muller_C_Element_0001` | 성공 | 미실행 | 16.086 | 자료 없음 |
| `cvdp_copilot_adc_data_rotate_0001` | 성공 | 미실행 | 15.457 | 자료 없음 |
| `cvdp_copilot_aes_key_expansion_0001` | 성공 | 미실행 | 336.318 | 자료 없음 |
| `cvdp_copilot_ahb_clk_counter_0001` | 성공 | 미실행 | 23.527 | 자료 없음 |
| `cvdp_copilot_alphablending_0003` | 성공 | 미실행 | 116.164 | 자료 없음 |
| `cvdp_copilot_apb_dsp_op_0002` | 실패 | 미실행 | 250.076 | 자료 없음 |
| `cvdp_copilot_apb_dsp_unit_0001` | 실패 | 미실행 | 233.048 | 자료 없음 |
| `cvdp_copilot_apb_gpio_0001` | 성공 | 미실행 | 220.891 | 자료 없음 |
| `cvdp_copilot_apb_gpio_0005` | 성공 | 미실행 | 173.785 | 자료 없음 |
| `cvdp_copilot_apb_history_shift_register_0001` | 실패 | 미실행 | 132.480 | 자료 없음 |
| `cvdp_copilot_arithmetic_progression_generator_0003` | 성공 | 미실행 | 21.857 | 자료 없음 |
| `cvdp_copilot_arithmetic_progression_generator_0015` | 성공 | 미실행 | 47.240 | 자료 없음 |
| `cvdp_copilot_async_filo_0001` | 성공 | 미실행 | 189.412 | 자료 없음 |
| `cvdp_copilot_async_filo_0025` | 성공 | 미실행 | 25.939 | 자료 없음 |
| `cvdp_copilot_axi_alu_0001` | 시간 초과 | 미실행 | 1800.047 | 자료 없음 |
| `cvdp_copilot_axi_register_0001` | 실패 | 미실행 | 224.035 | 자료 없음 |
| `cvdp_copilot_axi_stream_downscale_0001` | 실패 | 미실행 | 112.447 | 자료 없음 |
| `cvdp_copilot_axi_stream_upscale_0001` | 실패 | 미실행 | 109.094 | 자료 없음 |
| `cvdp_copilot_axi_tap_0001` | 실패 | 미실행 | 383.419 | 자료 없음 |
| `cvdp_copilot_axi_tap_0009` | 성공 | 미실행 | 157.844 | 자료 없음 |
| `cvdp_copilot_axil_precision_counter_0001` | 성공 | 미실행 | 368.422 | 자료 없음 |
| `cvdp_copilot_axis_border_gen_0001` | 실패 | 미실행 | 307.614 | 자료 없음 |
| `cvdp_copilot_axis_border_gen_0014` | 실패 | 미실행 | 1798.796 | 자료 없음 |
| `cvdp_copilot_axis_joiner_0001` | 실패 | 미실행 | 209.086 | 자료 없음 |
| `cvdp_copilot_axis_mux_0001` | 성공 | 미실행 | 37.520 | 자료 없음 |
| `cvdp_copilot_barrel_shifter_0001` | 성공 | 미실행 | 5.921 | 자료 없음 |
| `cvdp_copilot_barrel_shifter_0037` | 성공 | 미실행 | 18.757 | 자료 없음 |
| `cvdp_copilot_barrel_shifter_0054` | 성공 | 미실행 | 12.451 | 자료 없음 |
| `cvdp_copilot_barrel_shifter_0058` | 성공 | 미실행 | 38.921 | 자료 없음 |
| `cvdp_copilot_barrel_shifter_0064` | 성공 | 미실행 | 18.681 | 자료 없음 |
| `cvdp_copilot_bcd_adder_0001` | 성공 | 미실행 | 12.720 | 자료 없음 |
| `cvdp_copilot_bcd_counter_0001` | 성공 | 미실행 | 11.043 | 자료 없음 |
| `cvdp_copilot_bcd_to_excess_3_0001` | 성공 | 미실행 | 5.529 | 자료 없음 |
| `cvdp_copilot_bcd_to_excess_3_0008` | 성공 | 미실행 | 6.899 | 자료 없음 |
| `cvdp_copilot_binary_multiplier_0012` | 성공 | 미실행 | 28.200 | 자료 없음 |
| `cvdp_copilot_binary_search_tree_sorting_0001` | 성공 | 미실행 | 95.308 | 자료 없음 |
| `cvdp_copilot_binary_search_tree_sorting_0014` | 실패 | 미실행 | 318.290 | 자료 없음 |
| `cvdp_copilot_binary_to_BCD_0001` | 성공 | 미실행 | 11.950 | 자료 없음 |
| `cvdp_copilot_binary_to_BCD_0010` | 성공 | 미실행 | 26.428 | 자료 없음 |
| `cvdp_copilot_binary_to_BCD_0036` | 성공 | 미실행 | 9.801 | 자료 없음 |
| `cvdp_copilot_binary_to_gray_0001` | 성공 | 미실행 | 4.594 | 자료 없음 |
| `cvdp_copilot_binary_to_gray_0013` | 성공 | 미실행 | 3.868 | 자료 없음 |
| `cvdp_copilot_binary_to_one_hot_decoder_0001` | 성공 | 미실행 | 28.206 | 자료 없음 |
| `cvdp_copilot_bit_synchronizer_0001` | 성공 | 미실행 | 10.598 | 자료 없음 |
| `cvdp_copilot_bus_arbiter_0001` | 성공 | 미실행 | 43.794 | 자료 없음 |
| `cvdp_copilot_bus_arbiter_0004` | 성공 | 미실행 | 12.853 | 자료 없음 |
| `cvdp_copilot_cache_lru_0001` | 성공 | 미실행 | 26.864 | 자료 없음 |
| `cvdp_copilot_cache_lru_0008` | 성공 | 미실행 | 23.955 | 자료 없음 |
| `cvdp_copilot_cache_lru_0011` | 성공 | 미실행 | 15.571 | 자료 없음 |
| `cvdp_copilot_cache_lru_0016` | 성공 | 미실행 | 25.618 | 자료 없음 |
| `cvdp_copilot_cache_lru_0019` | 성공 | 미실행 | 92.625 | 자료 없음 |
| `cvdp_copilot_cache_lru_0022` | 성공 | 미실행 | 9.606 | 자료 없음 |
| `cvdp_copilot_caesar_cipher_0001` | 성공 | 미실행 | 13.281 | 자료 없음 |
| `cvdp_copilot_caesar_cipher_0024` | 성공 | 미실행 | 21.405 | 자료 없음 |
| `cvdp_copilot_caesar_cipher_0038` | 성공 | 미실행 | 15.029 | 자료 없음 |
| `cvdp_copilot_car_parking_management_0001` | 성공 | 미실행 | 41.581 | 자료 없음 |
| `cvdp_copilot_car_parking_management_0015` | 성공 | 미실행 | 33.392 | 자료 없음 |
| `cvdp_copilot_car_parking_management_0018` | 성공 | 미실행 | 188.536 | 자료 없음 |
| `cvdp_copilot_car_parking_management_0031` | 성공 | 미실행 | 29.524 | 자료 없음 |
| `cvdp_copilot_cascaded_adder_0001` | 성공 | 미실행 | 49.628 | 자료 없음 |
| `cvdp_copilot_cascaded_adder_0025` | 성공 | 미실행 | 191.162 | 자료 없음 |
| `cvdp_copilot_cdc_pulse_synchronizer_0004` | 성공 | 미실행 | 4.169 | 자료 없음 |
| `cvdp_copilot_cdc_pulse_synchronizer_0013` | 성공 | 미실행 | 14.970 | 자료 없음 |
| `cvdp_copilot_cellular_automata_0001` | 성공 | 미실행 | 19.692 | 자료 없음 |
| `cvdp_copilot_cellular_automata_0017` | 성공 | 미실행 | 13.817 | 자료 없음 |
| `cvdp_copilot_clock_divider_0003` | 성공 | 미실행 | 10.508 | 자료 없음 |
| `cvdp_copilot_clock_jitter_detection_module_0003` | 성공 | 미실행 | 158.920 | 자료 없음 |
| `cvdp_copilot_coffee_machine_0001` | 성공 | 미실행 | 112.770 | 자료 없음 |
| `cvdp_copilot_comparator_0001` | 성공 | 미실행 | 8.459 | 자료 없음 |
| `cvdp_copilot_complex_multiplier_0001` | 성공 | 미실행 | 12.296 | 자료 없음 |
| `cvdp_copilot_compression_engine_0001` | 성공 | 미실행 | 57.389 | 자료 없음 |
| `cvdp_copilot_concatenate_0001` | 실패 | 미실행 | 167.085 | 자료 없음 |
| `cvdp_copilot_configurable_digital_low_pass_filter_0001` | 성공 | 미실행 | 36.081 | 자료 없음 |
| `cvdp_copilot_configurable_digital_low_pass_filter_0004` | 성공 | 미실행 | 60.321 | 자료 없음 |
| `cvdp_copilot_configurable_digital_low_pass_filter_0011` | 성공 | 미실행 | 78.003 | 자료 없음 |
| `cvdp_copilot_configurable_digital_low_pass_filter_0014` | 성공 | 미실행 | 19.939 | 자료 없음 |
| `cvdp_copilot_cont_adder_0006` | 성공 | 미실행 | 22.021 | 자료 없음 |
| `cvdp_copilot_cont_adder_0023` | 성공 | 미실행 | 34.496 | 자료 없음 |
| `cvdp_copilot_cont_adder_0042` | 성공 | 미실행 | 84.079 | 자료 없음 |
| `cvdp_copilot_convolutional_encoder_0001` | 성공 | 미실행 | 6.152 | 자료 없음 |
| `cvdp_copilot_convolutional_encoder_0010` | 성공 | 미실행 | 5.071 | 자료 없음 |
| `cvdp_copilot_crossbar_switch_0001` | 성공 | 미실행 | 8.530 | 자료 없음 |
| `cvdp_copilot_data_bus_controller_0001` | 성공 | 미실행 | 68.212 | 자료 없음 |
| `cvdp_copilot_data_serializer_0001` | 성공 | 미실행 | 19.692 | 자료 없음 |
| `cvdp_copilot_data_width_converter_0003` | 성공 | 미실행 | 6.210 | 자료 없음 |
| `cvdp_copilot_dbi_0001` | 성공 | 미실행 | 12.224 | 자료 없음 |
| `cvdp_copilot_dbi_0008` | 성공 | 미실행 | 8.039 | 자료 없음 |
| `cvdp_copilot_dbi_dec_0001` | 성공 | 미실행 | 4.500 | 자료 없음 |
| `cvdp_copilot_decode_firstbit_0001` | 성공 | 미실행 | 67.042 | 자료 없음 |
| `cvdp_copilot_decoder_8b10b_0001` | 성공 | 미실행 | 7.696 | 자료 없음 |
| `cvdp_copilot_digital_dice_roller_0001` | 실패 | 미실행 | 156.058 | 자료 없음 |
| `cvdp_copilot_digital_dice_roller_0004` | 성공 | 미실행 | 20.622 | 자료 없음 |
| `cvdp_copilot_digital_stopwatch_0001` | 실패 | 미실행 | 1322.071 | 자료 없음 |
| `cvdp_copilot_digital_stopwatch_0012` | 성공 | 미실행 | 53.287 | 자료 없음 |
| `cvdp_copilot_dot_product_0002` | 성공 | 미실행 | 13.239 | 자료 없음 |
| `cvdp_copilot_dot_product_0005` | 성공 | 미실행 | 76.783 | 자료 없음 |
| `cvdp_copilot_dot_product_0012` | 성공 | 미실행 | 10.953 | 자료 없음 |
| `cvdp_copilot_edge_detector_0001` | 성공 | 미실행 | 4.600 | 자료 없음 |
| `cvdp_copilot_elastic_buffer_0001` | 성공 | 미실행 | 21.224 | 자료 없음 |
| `cvdp_copilot_elevator_control_0006` | 실패 | 미실행 | 1753.394 | 자료 없음 |
| `cvdp_copilot_elevator_control_0009` | 성공 | 미실행 | 78.723 | 자료 없음 |
| `cvdp_copilot_elevator_control_0026` | 성공 | 미실행 | 221.175 | 자료 없음 |
| `cvdp_copilot_elevator_control_0033` | 성공 | 미실행 | 38.102 | 자료 없음 |
| `cvdp_copilot_elevator_control_0036` | 성공 | 미실행 | 101.849 | 자료 없음 |
| `cvdp_copilot_ethernet_packet_parser_0001` | 성공 | 미실행 | 47.860 | 자료 없음 |
| `cvdp_copilot_events_to_apb_0001` | 성공 | 미실행 | 42.992 | 자료 없음 |
| `cvdp_copilot_factorial_0001` | 성공 | 미실행 | 19.465 | 자료 없음 |
| `cvdp_copilot_fan_controller_0001` | 성공 | 미실행 | 21.156 | 자료 없음 |
| `cvdp_copilot_fan_controller_0005` | 성공 | 미실행 | 15.735 | 자료 없음 |
| `cvdp_copilot_fan_controller_0008` | 실패 | 미실행 | 225.728 | 자료 없음 |
| `cvdp_copilot_fibonacci_series_0001` | 성공 | 미실행 | 81.728 | 자료 없음 |
| `cvdp_copilot_fifo_async_0001` | 성공 | 미실행 | 71.101 | 자료 없음 |
| `cvdp_copilot_fifo_to_axis_0001` | 실패 | 미실행 | 201.515 | 자료 없음 |
| `cvdp_copilot_fifo_to_axis_0005` | 성공 | 미실행 | 41.659 | 자료 없음 |
| `cvdp_copilot_filo_0005` | 성공 | 미실행 | 16.297 | 자료 없음 |
| `cvdp_copilot_filo_0033` | 성공 | 미실행 | 26.772 | 자료 없음 |
| `cvdp_copilot_findfasterclock_0001` | 성공 | 미실행 | 44.741 | 자료 없음 |
| `cvdp_copilot_flop_0001` | 성공 | 미실행 | 5.815 | 자료 없음 |
| `cvdp_copilot_flop_0002` | 성공 | 미실행 | 5.970 | 자료 없음 |
| `cvdp_copilot_fsm_seq_detector_0001` | 성공 | 미실행 | 12.161 | 자료 없음 |
| `cvdp_copilot_fsm_seq_detector_0023` | 성공 | 미실행 | 24.581 | 자료 없음 |
| `cvdp_copilot_galois_encryption_0001` | 실패 | 미실행 | 327.891 | 자료 없음 |
| `cvdp_copilot_gaussian_rounding_div_0003` | 성공 | 미실행 | 58.575 | 자료 없음 |
| `cvdp_copilot_gaussian_rounding_div_0005` | 실패 | 미실행 | 310.373 | 자료 없음 |
| `cvdp_copilot_gcd_0001` | 성공 | 미실행 | 248.342 | 자료 없음 |
| `cvdp_copilot_gcd_0009` | 성공 | 미실행 | 50.894 | 자료 없음 |
| `cvdp_copilot_gcd_0015` | 성공 | 미실행 | 40.543 | 자료 없음 |
| `cvdp_copilot_gcd_0023` | 성공 | 미실행 | 105.260 | 자료 없음 |
| `cvdp_copilot_generic_nbit_counter_0036` | 성공 | 미실행 | 19.452 | 자료 없음 |
| `cvdp_copilot_generic_nbit_counter_0039` | 성공 | 미실행 | 17.207 | 자료 없음 |
| `cvdp_copilot_gf_multiplier_0001` | 성공 | 미실행 | 10.776 | 자료 없음 |
| `cvdp_copilot_gf_multiplier_0005` | 성공 | 미실행 | 7.421 | 자료 없음 |
| `cvdp_copilot_gf_multiplier_0013` | 성공 | 미실행 | 33.247 | 자료 없음 |
| `cvdp_copilot_gf_multiplier_0021` | 성공 | 미실행 | 88.235 | 자료 없음 |
| `cvdp_copilot_gmii_axis_0001` | 성공 | 미실행 | 26.718 | 자료 없음 |
| `cvdp_copilot_gray_to_binary_0001` | 성공 | 미실행 | 11.933 | 자료 없음 |
| `cvdp_copilot_grayscale_image_0014` | 성공 | 미실행 | 16.983 | 자료 없음 |
| `cvdp_copilot_halfband_fir_0005` | 성공 | 미실행 | 21.181 | 자료 없음 |
| `cvdp_copilot_hamming_code_tx_and_rx_0001` | 성공 | 미실행 | 5.026 | 자료 없음 |
| `cvdp_copilot_hamming_code_tx_and_rx_0003` | 성공 | 미실행 | 10.609 | 자료 없음 |
| `cvdp_copilot_hamming_code_tx_and_rx_0009` | 성공 | 미실행 | 42.438 | 자료 없음 |
| `cvdp_copilot_hamming_code_tx_and_rx_0011` | 성공 | 미실행 | 26.414 | 자료 없음 |
| `cvdp_copilot_hamming_code_tx_and_rx_0013` | 성공 | 미실행 | 68.778 | 자료 없음 |
| `cvdp_copilot_hebbian_rule_0012` | 실패 | 미실행 | 337.618 | 자료 없음 |
| `cvdp_copilot_hebbian_rule_0017` | 실패 | 미실행 | 213.385 | 자료 없음 |
| `cvdp_copilot_hill_cipher_0001` | 성공 | 미실행 | 42.302 | 자료 없음 |
| `cvdp_copilot_hill_cipher_0015` | 성공 | 미실행 | 53.535 | 자료 없음 |
| `cvdp_copilot_hmac_register_0001` | 실패 | 미실행 | 245.643 | 자료 없음 |
| `cvdp_copilot_huffman_0001` | 성공 | 미실행 | 53.177 | 자료 없음 |
| `cvdp_copilot_icache_controller_0001` | 성공 | 미실행 | 48.644 | 자료 없음 |
| `cvdp_copilot_image_rotate_0001` | 성공 | 미실행 | 136.129 | 자료 없음 |
| `cvdp_copilot_image_rotate_0014` | 성공 | 미실행 | 43.747 | 자료 없음 |
| `cvdp_copilot_image_rotate_0015` | 성공 | 미실행 | 32.285 | 자료 없음 |
| `cvdp_copilot_image_stego_0004` | 성공 | 미실행 | 10.512 | 자료 없음 |
| `cvdp_copilot_interrupt_controller_0014` | 실패 | 미실행 | 185.813 | 자료 없음 |
| `cvdp_copilot_interrupt_controller_0017` | 실패 | 미실행 | 243.677 | 자료 없음 |
| `cvdp_copilot_interrupt_controller_0019` | 실패 | 미실행 | 200.298 | 자료 없음 |
| `cvdp_copilot_ir_receiver_0001` | 실패 | 미실행 | 1678.030 | 자료 없음 |
| `cvdp_copilot_ir_receiver_0005` | 실패 | 미실행 | 351.059 | 자료 없음 |
| `cvdp_copilot_kogge_stone_adder_0007` | 성공 | 미실행 | 29.042 | 자료 없음 |
| `cvdp_copilot_lfsr_0007` | 성공 | 미실행 | 5.530 | 자료 없음 |
| `cvdp_copilot_line_buffer_0003` | 성공 | 미실행 | 54.052 | 자료 없음 |
| `cvdp_copilot_load_store_unit_0001` | 성공 | 미실행 | 63.214 | 자료 없음 |
| `cvdp_copilot_load_store_unit_0003` | 성공 | 미실행 | 28.623 | 자료 없음 |
| `cvdp_copilot_load_store_unit_0009` | 성공 | 미실행 | 52.221 | 자료 없음 |
| `cvdp_copilot_manchester_enc_0005` | 성공 | 미실행 | 11.820 | 자료 없음 |
| `cvdp_copilot_manchester_enc_0013` | 성공 | 미실행 | 8.881 | 자료 없음 |
| `cvdp_copilot_matrix_multiplier_0001` | 성공 | 미실행 | 33.128 | 자료 없음 |
| `cvdp_copilot_matrix_multiplier_0007` | 성공 | 미실행 | 64.892 | 자료 없음 |
| `cvdp_copilot_matrix_multiplier_0010` | 성공 | 미실행 | 99.185 | 자료 없음 |
| `cvdp_copilot_mem_allocator_0001` | 성공 | 미실행 | 31.215 | 자료 없음 |
| `cvdp_copilot_microcode_sequencer_0001` | 실패 | 미실행 | 197.478 | 자료 없음 |
| `cvdp_copilot_modified_booth_mul_0002` | 성공 | 미실행 | 33.767 | 자료 없음 |
| `cvdp_copilot_modified_booth_mul_0005` | 성공 | 미실행 | 32.524 | 자료 없음 |
| `cvdp_copilot_montgomery_0001` | 성공 | 미실행 | 38.115 | 자료 없음 |
| `cvdp_copilot_montgomery_0002` | 실패 | 미실행 | 338.825 | 자료 없음 |
| `cvdp_copilot_morse_code_0001` | 성공 | 미실행 | 9.751 | 자료 없음 |
| `cvdp_copilot_morse_code_0014` | 성공 | 미실행 | 10.024 | 자료 없음 |
| `cvdp_copilot_moving_average_0001` | 성공 | 미실행 | 8.857 | 자료 없음 |
| `cvdp_copilot_moving_average_0005` | 성공 | 미실행 | 8.000 | 자료 없음 |
| `cvdp_copilot_mux_synch_0001` | 성공 | 미실행 | 14.473 | 자료 없음 |
| `cvdp_copilot_mux_synch_0011` | 성공 | 미실행 | 54.237 | 자료 없음 |
| `cvdp_copilot_nbit_swizzling_0001` | 성공 | 미실행 | 19.226 | 자료 없음 |
| `cvdp_copilot_nbit_swizzling_0014` | 성공 | 미실행 | 13.793 | 자료 없음 |
| `cvdp_copilot_nbit_swizzling_0020` | 성공 | 미실행 | 36.971 | 자료 없음 |
| `cvdp_copilot_neuromorphic_array_0001` | 성공 | 미실행 | 36.506 | 자료 없음 |
| `cvdp_copilot_one_hot_address_0001` | 성공 | 미실행 | 25.244 | 자료 없음 |
| `cvdp_copilot_packet_controller_0001` | 성공 | 미실행 | 55.465 | 자료 없음 |
| `cvdp_copilot_palindrome_3b_0002` | 성공 | 미실행 | 18.581 | 자료 없음 |
| `cvdp_copilot_password_generator_0001` | 성공 | 미실행 | 58.187 | 자료 없음 |
| `cvdp_copilot_perceptron_0001` | 성공 | 미실행 | 45.602 | 자료 없음 |
| `cvdp_copilot_perceptron_0006` | 실패 | 미실행 | 308.152 | 자료 없음 |
| `cvdp_copilot_perceptron_0013` | 실패 | 미실행 | 304.109 | 자료 없음 |
| `cvdp_copilot_perf_counters_0001` | 실패 | 미실행 | 1623.169 | 자료 없음 |
| `cvdp_copilot_perfect_squares_0001` | 성공 | 미실행 | 13.372 | 자료 없음 |
| `cvdp_copilot_ping_pong_buffer_0001` | 실패 | 미실행 | 199.187 | 자료 없음 |
| `cvdp_copilot_pipeline_mac_0017` | 성공 | 미실행 | 50.555 | 자료 없음 |
| `cvdp_copilot_piso_0001` | 성공 | 미실행 | 11.702 | 자료 없음 |
| `cvdp_copilot_pkt_detector_0001` | 성공 | 미실행 | 36.236 | 자료 없음 |
| `cvdp_copilot_prbs_gen_0003` | 실패 | 미실행 | 225.253 | 자료 없음 |
| `cvdp_copilot_prim_max_0001` | 성공 | 미실행 | 27.883 | 자료 없음 |
| `cvdp_copilot_radix2_div_0001` | 성공 | 미실행 | 9.887 | 자료 없음 |
| `cvdp_copilot_reed_solomon_encoder_and_decoder_0005` | 실패 | 미실행 | 243.259 | 자료 없음 |
| `cvdp_copilot_register_file_2R1W_0006` | 실패 | 미실행 | 214.343 | 자료 없음 |
| `cvdp_copilot_register_file_2R1W_0013` | 성공 | 미실행 | 11.276 | 자료 없음 |
| `cvdp_copilot_restoring_division_0001` | 성공 | 미실행 | 27.723 | 자료 없음 |
| `cvdp_copilot_reverse_bits_0001` | 성공 | 미실행 | 4.476 | 자료 없음 |
| `cvdp_copilot_rgb2ycbcr_0001` | 성공 | 미실행 | 29.540 | 자료 없음 |
| `cvdp_copilot_round_robin_arbiter_0005` | 성공 | 미실행 | 30.315 | 자료 없음 |
| `cvdp_copilot_rounding_0001` | 실패 | 미실행 | 132.736 | 자료 없음 |
| `cvdp_copilot_rs_232_0001` | 성공 | 미실행 | 51.926 | 자료 없음 |
| `cvdp_copilot_run_length_0001` | 실패 | 미실행 | 213.294 | 자료 없음 |
| `cvdp_copilot_run_length_0007` | 실패 | 미실행 | 287.105 | 자료 없음 |
| `cvdp_copilot_scrambler_0001` | 실패 | 미실행 | 302.381 | 자료 없음 |
| `cvdp_copilot_scrambler_0009` | 실패 | 미실행 | 507.694 | 자료 없음 |
| `cvdp_copilot_scrambler_0018` | 실패 | 미실행 | 236.567 | 자료 없음 |
| `cvdp_copilot_scrambler_0024` | 성공 | 미실행 | 16.091 | 자료 없음 |
| `cvdp_copilot_sdram_controller_0001` | 성공 | 미실행 | 97.426 | 자료 없음 |
| `cvdp_copilot_secure_ALU_0001` | 성공 | 미실행 | 8.118 | 자료 없음 |
| `cvdp_copilot_secure_read_write_bus_0001` | 성공 | 미실행 | 11.954 | 자료 없음 |
| `cvdp_copilot_secure_read_write_register_bank_0001` | 성공 | 미실행 | 53.046 | 자료 없음 |
| `cvdp_copilot_secure_variable_timer_0001` | 성공 | 미실행 | 16.709 | 자료 없음 |
| `cvdp_copilot_sequencial_binary_to_one_hot_decoder_0001` | 성공 | 미실행 | 20.992 | 자료 없음 |
| `cvdp_copilot_serial_in_parallel_out_0004` | 성공 | 미실행 | 3.620 | 자료 없음 |
| `cvdp_copilot_serial_in_parallel_out_0011` | 성공 | 미실행 | 104.959 | 자료 없음 |
| `cvdp_copilot_serial_in_parallel_out_0014` | 실패 | 미실행 | 245.501 | 자료 없음 |
| `cvdp_copilot_set_bit_calculator_0001` | 성공 | 미실행 | 7.852 | 자료 없음 |
| `cvdp_copilot_sigma_delta_audio_0007` | 성공 | 미실행 | 28.881 | 자료 없음 |
| `cvdp_copilot_signal_correlator_0015` | 성공 | 미실행 | 10.253 | 자료 없음 |
| `cvdp_copilot_signed_adder_0001` | 성공 | 미실행 | 22.398 | 자료 없음 |
| `cvdp_copilot_simple_spi_0001` | 실패 | 미실행 | 166.110 | 자료 없음 |
| `cvdp_copilot_single_number_0001` | 성공 | 미실행 | 4.425 | 자료 없음 |
| `cvdp_copilot_skid_buffer_0001` | 실패 | 미실행 | 130.876 | 자료 없음 |
| `cvdp_copilot_sobel_filter_0011` | 성공 | 미실행 | 59.069 | 자료 없음 |
| `cvdp_copilot_sorter_0001` | 성공 | 미실행 | 34.466 | 자료 없음 |
| `cvdp_copilot_sorter_0003` | 성공 | 미실행 | 76.812 | 자료 없음 |
| `cvdp_copilot_sorter_0009` | 성공 | 미실행 | 39.669 | 자료 없음 |
| `cvdp_copilot_sorter_0031` | 성공 | 미실행 | 54.618 | 자료 없음 |
| `cvdp_copilot_sound_generator_0001` | 성공 | 미실행 | 31.273 | 자료 없음 |
| `cvdp_copilot_sprite_0004` | 실패 | 미실행 | 236.454 | 자료 없음 |
| `cvdp_copilot_sprite_0010` | 성공 | 미실행 | 77.430 | 자료 없음 |
| `cvdp_copilot_square_root_0003` | 성공 | 미실행 | 14.991 | 자료 없음 |
| `cvdp_copilot_static_branch_predict_0001` | 성공 | 미실행 | 98.242 | 자료 없음 |
| `cvdp_copilot_static_branch_predict_0009` | 성공 | 미실행 | 19.388 | 자료 없음 |
| `cvdp_copilot_static_branch_predict_0013` | 성공 | 미실행 | 22.078 | 자료 없음 |
| `cvdp_copilot_static_branch_predict_0014` | 성공 | 미실행 | 20.728 | 자료 없음 |
| `cvdp_copilot_strobe_divider_0001` | 성공 | 미실행 | 30.029 | 자료 없음 |
| `cvdp_copilot_swizzler_0009` | 성공 | 미실행 | 30.673 | 자료 없음 |
| `cvdp_copilot_swizzler_0014` | 성공 | 미실행 | 25.194 | 자료 없음 |
| `cvdp_copilot_sync_lifo_0001` | 성공 | 미실행 | 19.581 | 자료 없음 |
| `cvdp_copilot_sync_lifo_0010` | 성공 | 미실행 | 27.441 | 자료 없음 |
| `cvdp_copilot_sync_serial_communication_0001` | 성공 | 미실행 | 92.409 | 자료 없음 |
| `cvdp_copilot_sync_serial_communication_0014` | 성공 | 미실행 | 82.092 | 자료 없음 |
| `cvdp_copilot_sync_serial_communication_0052` | 성공 | 미실행 | 56.793 | 자료 없음 |
| `cvdp_copilot_thermostat_0001` | 성공 | 미실행 | 16.112 | 자료 없음 |
| `cvdp_copilot_ttc_lite_0001` | 성공 | 미실행 | 49.237 | 자료 없음 |
| `cvdp_copilot_unpacker_one_hot_0001` | 성공 | 미실행 | 20.937 | 자료 없음 |
| `cvdp_copilot_vending_machine_0001` | 실패 | 미실행 | 241.990 | 자료 없음 |
| `cvdp_copilot_vga_controller_0001` | 성공 | 미실행 | 29.049 | 자료 없음 |
| `cvdp_copilot_vga_controller_0006` | 성공 | 미실행 | 32.019 | 자료 없음 |
| `cvdp_copilot_vga_controller_0026` | 성공 | 미실행 | 68.451 | 자료 없음 |
| `cvdp_copilot_virtual2physical_tlb_0001` | 실패 | 미실행 | 299.898 | 자료 없음 |
| `cvdp_copilot_wb2ahb_0001` | 실패 | 미실행 | 242.726 | 자료 없음 |
| `cvdp_copilot_word_change_detector_0001` | 성공 | 미실행 | 25.036 | 자료 없음 |
| `cvdp_copilot_word_reducer_0001` | 성공 | 미실행 | 26.336 | 자료 없음 |
| `cvdp_copilot_word_reducer_0008` | 성공 | 미실행 | 18.884 | 자료 없음 |
| `cvdp_copilot_write_buffer_merge_0001` | 성공 | 미실행 | 72.064 | 자료 없음 |
| `cvdp_copilot_write_through_data_direct_mapped_cache_0012` | 성공 | 미실행 | 12.167 | 자료 없음 |

## 한계

비에이전트 방식·비상용 도구의 제한된 네이티브 평가군 한 묶음으로, 모든 CVDP 작업 흐름이나 원래 기본 예산을 포괄하지 않는다. 실제 도구 요구에 따라 상용 도구가 필요한 항목을 명시적으로 제외했다. API의 확률적 변동과 원격 지연은 통제하지 못했으며, 단일 실행 차이는 관찰 결과일 뿐 통계적으로 입증된 효과가 아니다. 반복·요소 제거 실험은 실제 실행한 경우에만 보고해야 한다. 출처·무결성 규칙·남은 작업은 환경 및 개선 기회 문서를 참고한다.
