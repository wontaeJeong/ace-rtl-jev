# ACE-RTL measured comparison

Baseline state: `completed`; coverage 292/292.
Improved state: **Not run**.

| 지표 | Baseline | JEV-like | 변화 (JEV − baseline) |
|---|---:|---:|---:|
| 평가 케이스 수 | 292 | Not run | Unavailable |
| 성공 케이스 수 | 240 | Not run | Unavailable |
| 성공률 (0–1) | 0.822 | Not run | Unavailable |
| 총 토큰 (reported + disclosed estimates) | Unavailable | Not run | Unavailable |
| 평균 토큰/케이스 | Unavailable | Not run | Unavailable |
| 총 실행 시간 (batch wall s) | Unavailable | Not run | Unavailable |
| 평균 실행 시간/케이스 (s) | Unavailable | Not run | Unavailable |
| 주력 LLM 호출 수 | 1294 | Not run | Unavailable |
| JEV-like 호출 수 | 0 | Not run | Unavailable |
| 평균 호출 지연 시간 (s) | 17.399 | Not run | Unavailable |
| 실패 및 오류 건수 | 52 | Not run | Unavailable |

Measured token savings (%): Unavailable.
Measured batch wall-time savings (%): Unavailable.

## Conditions and measurement

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

Warmup is actual inference, excluded from evaluation metrics. Total wall time is concurrent batch wall time; average case time includes subprocess/evaluator/repair overhead. Retry calls, JEV calls and primary fallback calls count toward totals.
An inflight/error call with unavailable usage is not assigned fictional zero cost. Unknown billing suppresses token savings. Char/4 estimates are labeled and cannot establish measured token savings. Provider caches/load time may be opaque; no custom cache was added.

## Provider accounting

| Mode/provider | Calls | Reported input | Reported output | Reported total | Estimated total | Unknown usage calls | Fallback calls | Mean latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline/primary | 1294 | 14162840 | 2308144 | 16470984 | 0 | 26 | 0 | 17.399 |
| baseline/jev | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Unavailable |

## Case outcomes

| Case | Baseline | JEV-like | Baseline s | JEV s |
|---|---|---|---:|---:|
| `cvdp_copilot_16qam_mapper_0001` | success | Not run | 17.325 | Unavailable |
| `cvdp_copilot_16qam_mapper_0006` | success | Not run | 39.382 | Unavailable |
| `cvdp_copilot_32_bit_Brent_Kung_PP_adder_0001` | success | Not run | 23.836 | Unavailable |
| `cvdp_copilot_64b66b_decoder_0001` | success | Not run | 4.554 | Unavailable |
| `cvdp_copilot_64b66b_decoder_0011` | failure | Not run | 189.255 | Unavailable |
| `cvdp_copilot_64b66b_encoder_0001` | success | Not run | 4.107 | Unavailable |
| `cvdp_copilot_64b66b_encoder_0005` | success | Not run | 7.754 | Unavailable |
| `cvdp_copilot_64b66b_encoder_0009` | success | Not run | 142.659 | Unavailable |
| `cvdp_copilot_64b66b_encoder_0022` | success | Not run | 23.478 | Unavailable |
| `cvdp_copilot_8x3_priority_encoder_0001` | success | Not run | 5.410 | Unavailable |
| `cvdp_copilot_8x3_priority_encoder_0013` | success | Not run | 18.239 | Unavailable |
| `cvdp_copilot_Attenuator_0001` | success | Not run | 19.520 | Unavailable |
| `cvdp_copilot_Carry_Lookahead_Adder_0001` | success | Not run | 3.606 | Unavailable |
| `cvdp_copilot_Carry_Lookahead_Adder_0005` | success | Not run | 51.138 | Unavailable |
| `cvdp_copilot_FIR_0001` | success | Not run | 22.000 | Unavailable |
| `cvdp_copilot_FIR_0003` | success | Not run | 20.309 | Unavailable |
| `cvdp_copilot_GFCM_0001` | success | Not run | 65.647 | Unavailable |
| `cvdp_copilot_GFCM_0003` | success | Not run | 40.419 | Unavailable |
| `cvdp_copilot_IIR_filter_0019` | success | Not run | 77.811 | Unavailable |
| `cvdp_copilot_MSHR_0001` | success | Not run | 170.827 | Unavailable |
| `cvdp_copilot_MSHR_0008` | success | Not run | 93.476 | Unavailable |
| `cvdp_copilot_Serial_Line_Converter_0001` | success | Not run | 80.484 | Unavailable |
| `cvdp_copilot_Serial_Line_Converter_0011` | failure | Not run | 175.224 | Unavailable |
| `cvdp_copilot_String_to_ASCII_0001` | success | Not run | 19.572 | Unavailable |
| `cvdp_copilot_Synchronous_Muller_C_Element_0001` | success | Not run | 11.558 | Unavailable |
| `cvdp_copilot_adc_data_rotate_0001` | success | Not run | 15.004 | Unavailable |
| `cvdp_copilot_aes_key_expansion_0001` | success | Not run | 45.740 | Unavailable |
| `cvdp_copilot_ahb_clk_counter_0001` | success | Not run | 25.712 | Unavailable |
| `cvdp_copilot_alphablending_0003` | success | Not run | 122.547 | Unavailable |
| `cvdp_copilot_apb_dsp_op_0002` | failure | Not run | 247.179 | Unavailable |
| `cvdp_copilot_apb_dsp_unit_0001` | failure | Not run | 206.017 | Unavailable |
| `cvdp_copilot_apb_gpio_0001` | failure | Not run | 178.146 | Unavailable |
| `cvdp_copilot_apb_gpio_0005` | success | Not run | 125.261 | Unavailable |
| `cvdp_copilot_apb_history_shift_register_0001` | failure | Not run | 132.352 | Unavailable |
| `cvdp_copilot_arithmetic_progression_generator_0003` | success | Not run | 22.555 | Unavailable |
| `cvdp_copilot_arithmetic_progression_generator_0015` | success | Not run | 49.697 | Unavailable |
| `cvdp_copilot_async_filo_0001` | success | Not run | 38.790 | Unavailable |
| `cvdp_copilot_async_filo_0025` | success | Not run | 18.633 | Unavailable |
| `cvdp_copilot_axi_alu_0001` | failure | Not run | 331.361 | Unavailable |
| `cvdp_copilot_axi_register_0001` | success | Not run | 29.046 | Unavailable |
| `cvdp_copilot_axi_stream_downscale_0001` | failure | Not run | 83.910 | Unavailable |
| `cvdp_copilot_axi_stream_upscale_0001` | failure | Not run | 98.996 | Unavailable |
| `cvdp_copilot_axi_tap_0001` | success | Not run | 245.826 | Unavailable |
| `cvdp_copilot_axi_tap_0009` | success | Not run | 120.077 | Unavailable |
| `cvdp_copilot_axil_precision_counter_0001` | success | Not run | 105.620 | Unavailable |
| `cvdp_copilot_axis_border_gen_0001` | failure | Not run | 304.150 | Unavailable |
| `cvdp_copilot_axis_border_gen_0014` | timeout | Not run | 1330.764 | Unavailable |
| `cvdp_copilot_axis_joiner_0001` | failure | Not run | 206.083 | Unavailable |
| `cvdp_copilot_axis_mux_0001` | success | Not run | 26.729 | Unavailable |
| `cvdp_copilot_barrel_shifter_0001` | success | Not run | 4.030 | Unavailable |
| `cvdp_copilot_barrel_shifter_0037` | success | Not run | 30.132 | Unavailable |
| `cvdp_copilot_barrel_shifter_0054` | success | Not run | 16.673 | Unavailable |
| `cvdp_copilot_barrel_shifter_0058` | success | Not run | 23.118 | Unavailable |
| `cvdp_copilot_barrel_shifter_0064` | success | Not run | 21.778 | Unavailable |
| `cvdp_copilot_bcd_adder_0001` | success | Not run | 14.880 | Unavailable |
| `cvdp_copilot_bcd_counter_0001` | success | Not run | 11.658 | Unavailable |
| `cvdp_copilot_bcd_to_excess_3_0001` | success | Not run | 4.134 | Unavailable |
| `cvdp_copilot_bcd_to_excess_3_0008` | success | Not run | 5.668 | Unavailable |
| `cvdp_copilot_binary_multiplier_0012` | success | Not run | 57.901 | Unavailable |
| `cvdp_copilot_binary_search_tree_sorting_0001` | failure | Not run | 372.752 | Unavailable |
| `cvdp_copilot_binary_search_tree_sorting_0014` | timeout | Not run | 604.659 | Unavailable |
| `cvdp_copilot_binary_to_BCD_0001` | success | Not run | 6.185 | Unavailable |
| `cvdp_copilot_binary_to_BCD_0010` | success | Not run | 21.595 | Unavailable |
| `cvdp_copilot_binary_to_BCD_0036` | success | Not run | 8.329 | Unavailable |
| `cvdp_copilot_binary_to_gray_0001` | success | Not run | 5.413 | Unavailable |
| `cvdp_copilot_binary_to_gray_0013` | success | Not run | 4.819 | Unavailable |
| `cvdp_copilot_binary_to_one_hot_decoder_0001` | success | Not run | 11.827 | Unavailable |
| `cvdp_copilot_bit_synchronizer_0001` | success | Not run | 12.230 | Unavailable |
| `cvdp_copilot_bus_arbiter_0001` | success | Not run | 50.777 | Unavailable |
| `cvdp_copilot_bus_arbiter_0004` | success | Not run | 12.545 | Unavailable |
| `cvdp_copilot_cache_lru_0001` | success | Not run | 69.721 | Unavailable |
| `cvdp_copilot_cache_lru_0008` | success | Not run | 27.498 | Unavailable |
| `cvdp_copilot_cache_lru_0011` | success | Not run | 26.292 | Unavailable |
| `cvdp_copilot_cache_lru_0016` | success | Not run | 58.551 | Unavailable |
| `cvdp_copilot_cache_lru_0019` | success | Not run | 150.293 | Unavailable |
| `cvdp_copilot_cache_lru_0022` | success | Not run | 10.635 | Unavailable |
| `cvdp_copilot_caesar_cipher_0001` | success | Not run | 13.294 | Unavailable |
| `cvdp_copilot_caesar_cipher_0024` | success | Not run | 28.948 | Unavailable |
| `cvdp_copilot_caesar_cipher_0038` | success | Not run | 12.097 | Unavailable |
| `cvdp_copilot_car_parking_management_0001` | success | Not run | 38.217 | Unavailable |
| `cvdp_copilot_car_parking_management_0015` | success | Not run | 38.475 | Unavailable |
| `cvdp_copilot_car_parking_management_0018` | success | Not run | 180.095 | Unavailable |
| `cvdp_copilot_car_parking_management_0031` | success | Not run | 73.350 | Unavailable |
| `cvdp_copilot_cascaded_adder_0001` | success | Not run | 64.639 | Unavailable |
| `cvdp_copilot_cascaded_adder_0025` | success | Not run | 89.524 | Unavailable |
| `cvdp_copilot_cdc_pulse_synchronizer_0004` | success | Not run | 8.292 | Unavailable |
| `cvdp_copilot_cdc_pulse_synchronizer_0013` | success | Not run | 13.939 | Unavailable |
| `cvdp_copilot_cellular_automata_0001` | success | Not run | 35.267 | Unavailable |
| `cvdp_copilot_cellular_automata_0017` | success | Not run | 19.511 | Unavailable |
| `cvdp_copilot_clock_divider_0003` | success | Not run | 19.696 | Unavailable |
| `cvdp_copilot_clock_jitter_detection_module_0003` | failure | Not run | 237.221 | Unavailable |
| `cvdp_copilot_coffee_machine_0001` | success | Not run | 122.116 | Unavailable |
| `cvdp_copilot_comparator_0001` | success | Not run | 12.226 | Unavailable |
| `cvdp_copilot_complex_multiplier_0001` | success | Not run | 17.553 | Unavailable |
| `cvdp_copilot_compression_engine_0001` | success | Not run | 96.250 | Unavailable |
| `cvdp_copilot_concatenate_0001` | failure | Not run | 169.924 | Unavailable |
| `cvdp_copilot_configurable_digital_low_pass_filter_0001` | success | Not run | 50.165 | Unavailable |
| `cvdp_copilot_configurable_digital_low_pass_filter_0004` | success | Not run | 77.675 | Unavailable |
| `cvdp_copilot_configurable_digital_low_pass_filter_0011` | failure | Not run | 291.437 | Unavailable |
| `cvdp_copilot_configurable_digital_low_pass_filter_0014` | success | Not run | 38.305 | Unavailable |
| `cvdp_copilot_cont_adder_0006` | success | Not run | 29.389 | Unavailable |
| `cvdp_copilot_cont_adder_0023` | success | Not run | 52.358 | Unavailable |
| `cvdp_copilot_cont_adder_0042` | success | Not run | 101.147 | Unavailable |
| `cvdp_copilot_convolutional_encoder_0001` | success | Not run | 6.414 | Unavailable |
| `cvdp_copilot_convolutional_encoder_0010` | success | Not run | 5.699 | Unavailable |
| `cvdp_copilot_crossbar_switch_0001` | success | Not run | 12.666 | Unavailable |
| `cvdp_copilot_data_bus_controller_0001` | success | Not run | 48.551 | Unavailable |
| `cvdp_copilot_data_serializer_0001` | success | Not run | 20.355 | Unavailable |
| `cvdp_copilot_data_width_converter_0003` | success | Not run | 10.821 | Unavailable |
| `cvdp_copilot_dbi_0001` | success | Not run | 16.909 | Unavailable |
| `cvdp_copilot_dbi_0008` | success | Not run | 12.441 | Unavailable |
| `cvdp_copilot_dbi_dec_0001` | success | Not run | 5.916 | Unavailable |
| `cvdp_copilot_decode_firstbit_0001` | success | Not run | 34.053 | Unavailable |
| `cvdp_copilot_decoder_8b10b_0001` | success | Not run | 9.487 | Unavailable |
| `cvdp_copilot_digital_dice_roller_0001` | success | Not run | 95.465 | Unavailable |
| `cvdp_copilot_digital_dice_roller_0004` | success | Not run | 34.152 | Unavailable |
| `cvdp_copilot_digital_stopwatch_0001` | timeout | Not run | 1374.366 | Unavailable |
| `cvdp_copilot_digital_stopwatch_0012` | success | Not run | 77.681 | Unavailable |
| `cvdp_copilot_dot_product_0002` | success | Not run | 23.619 | Unavailable |
| `cvdp_copilot_dot_product_0005` | success | Not run | 119.108 | Unavailable |
| `cvdp_copilot_dot_product_0012` | success | Not run | 19.338 | Unavailable |
| `cvdp_copilot_edge_detector_0001` | success | Not run | 5.691 | Unavailable |
| `cvdp_copilot_elastic_buffer_0001` | success | Not run | 20.356 | Unavailable |
| `cvdp_copilot_elevator_control_0006` | success | Not run | 54.210 | Unavailable |
| `cvdp_copilot_elevator_control_0009` | success | Not run | 85.455 | Unavailable |
| `cvdp_copilot_elevator_control_0026` | success | Not run | 159.582 | Unavailable |
| `cvdp_copilot_elevator_control_0033` | success | Not run | 44.057 | Unavailable |
| `cvdp_copilot_elevator_control_0036` | success | Not run | 73.668 | Unavailable |
| `cvdp_copilot_ethernet_packet_parser_0001` | success | Not run | 45.716 | Unavailable |
| `cvdp_copilot_events_to_apb_0001` | success | Not run | 42.915 | Unavailable |
| `cvdp_copilot_factorial_0001` | success | Not run | 17.441 | Unavailable |
| `cvdp_copilot_fan_controller_0001` | success | Not run | 62.392 | Unavailable |
| `cvdp_copilot_fan_controller_0005` | success | Not run | 17.447 | Unavailable |
| `cvdp_copilot_fan_controller_0008` | failure | Not run | 209.870 | Unavailable |
| `cvdp_copilot_fibonacci_series_0001` | success | Not run | 44.082 | Unavailable |
| `cvdp_copilot_fifo_async_0001` | success | Not run | 60.704 | Unavailable |
| `cvdp_copilot_fifo_to_axis_0001` | failure | Not run | 155.122 | Unavailable |
| `cvdp_copilot_fifo_to_axis_0005` | success | Not run | 30.425 | Unavailable |
| `cvdp_copilot_filo_0005` | success | Not run | 18.780 | Unavailable |
| `cvdp_copilot_filo_0033` | success | Not run | 14.392 | Unavailable |
| `cvdp_copilot_findfasterclock_0001` | success | Not run | 39.453 | Unavailable |
| `cvdp_copilot_flop_0001` | success | Not run | 4.909 | Unavailable |
| `cvdp_copilot_flop_0002` | success | Not run | 6.957 | Unavailable |
| `cvdp_copilot_fsm_seq_detector_0001` | success | Not run | 14.458 | Unavailable |
| `cvdp_copilot_fsm_seq_detector_0023` | success | Not run | 16.601 | Unavailable |
| `cvdp_copilot_galois_encryption_0001` | failure | Not run | 292.848 | Unavailable |
| `cvdp_copilot_gaussian_rounding_div_0003` | success | Not run | 31.630 | Unavailable |
| `cvdp_copilot_gaussian_rounding_div_0005` | failure | Not run | 276.832 | Unavailable |
| `cvdp_copilot_gcd_0001` | success | Not run | 28.823 | Unavailable |
| `cvdp_copilot_gcd_0009` | success | Not run | 60.781 | Unavailable |
| `cvdp_copilot_gcd_0015` | success | Not run | 34.730 | Unavailable |
| `cvdp_copilot_gcd_0023` | success | Not run | 61.493 | Unavailable |
| `cvdp_copilot_generic_nbit_counter_0036` | success | Not run | 16.461 | Unavailable |
| `cvdp_copilot_generic_nbit_counter_0039` | success | Not run | 21.922 | Unavailable |
| `cvdp_copilot_gf_multiplier_0001` | success | Not run | 8.101 | Unavailable |
| `cvdp_copilot_gf_multiplier_0005` | success | Not run | 7.190 | Unavailable |
| `cvdp_copilot_gf_multiplier_0013` | success | Not run | 33.952 | Unavailable |
| `cvdp_copilot_gf_multiplier_0021` | success | Not run | 21.035 | Unavailable |
| `cvdp_copilot_gmii_axis_0001` | success | Not run | 27.063 | Unavailable |
| `cvdp_copilot_gray_to_binary_0001` | success | Not run | 13.260 | Unavailable |
| `cvdp_copilot_grayscale_image_0014` | success | Not run | 30.642 | Unavailable |
| `cvdp_copilot_halfband_fir_0005` | success | Not run | 22.956 | Unavailable |
| `cvdp_copilot_hamming_code_tx_and_rx_0001` | success | Not run | 5.820 | Unavailable |
| `cvdp_copilot_hamming_code_tx_and_rx_0003` | success | Not run | 19.253 | Unavailable |
| `cvdp_copilot_hamming_code_tx_and_rx_0009` | success | Not run | 24.533 | Unavailable |
| `cvdp_copilot_hamming_code_tx_and_rx_0011` | success | Not run | 24.540 | Unavailable |
| `cvdp_copilot_hamming_code_tx_and_rx_0013` | success | Not run | 29.595 | Unavailable |
| `cvdp_copilot_hebbian_rule_0012` | failure | Not run | 419.858 | Unavailable |
| `cvdp_copilot_hebbian_rule_0017` | failure | Not run | 232.882 | Unavailable |
| `cvdp_copilot_hill_cipher_0001` | success | Not run | 27.140 | Unavailable |
| `cvdp_copilot_hill_cipher_0015` | success | Not run | 53.558 | Unavailable |
| `cvdp_copilot_hmac_register_0001` | failure | Not run | 242.428 | Unavailable |
| `cvdp_copilot_huffman_0001` | success | Not run | 679.066 | Unavailable |
| `cvdp_copilot_icache_controller_0001` | failure | Not run | 301.767 | Unavailable |
| `cvdp_copilot_image_rotate_0001` | failure | Not run | 239.948 | Unavailable |
| `cvdp_copilot_image_rotate_0014` | success | Not run | 95.552 | Unavailable |
| `cvdp_copilot_image_rotate_0015` | success | Not run | 35.579 | Unavailable |
| `cvdp_copilot_image_stego_0004` | success | Not run | 11.487 | Unavailable |
| `cvdp_copilot_interrupt_controller_0014` | failure | Not run | 259.656 | Unavailable |
| `cvdp_copilot_interrupt_controller_0017` | failure | Not run | 405.179 | Unavailable |
| `cvdp_copilot_interrupt_controller_0019` | failure | Not run | 228.309 | Unavailable |
| `cvdp_copilot_ir_receiver_0001` | timeout | Not run | 1767.215 | Unavailable |
| `cvdp_copilot_ir_receiver_0005` | failure | Not run | 388.079 | Unavailable |
| `cvdp_copilot_kogge_stone_adder_0007` | success | Not run | 22.558 | Unavailable |
| `cvdp_copilot_lfsr_0007` | success | Not run | 8.255 | Unavailable |
| `cvdp_copilot_line_buffer_0003` | success | Not run | 59.898 | Unavailable |
| `cvdp_copilot_load_store_unit_0001` | success | Not run | 83.695 | Unavailable |
| `cvdp_copilot_load_store_unit_0003` | success | Not run | 33.385 | Unavailable |
| `cvdp_copilot_load_store_unit_0009` | success | Not run | 249.361 | Unavailable |
| `cvdp_copilot_manchester_enc_0005` | success | Not run | 1013.480 | Unavailable |
| `cvdp_copilot_manchester_enc_0013` | success | Not run | 9.112 | Unavailable |
| `cvdp_copilot_matrix_multiplier_0001` | success | Not run | 34.255 | Unavailable |
| `cvdp_copilot_matrix_multiplier_0007` | success | Not run | 64.847 | Unavailable |
| `cvdp_copilot_matrix_multiplier_0010` | success | Not run | 312.295 | Unavailable |
| `cvdp_copilot_mem_allocator_0001` | success | Not run | 24.756 | Unavailable |
| `cvdp_copilot_microcode_sequencer_0001` | failure | Not run | 225.787 | Unavailable |
| `cvdp_copilot_modified_booth_mul_0002` | success | Not run | 37.467 | Unavailable |
| `cvdp_copilot_modified_booth_mul_0005` | success | Not run | 28.572 | Unavailable |
| `cvdp_copilot_montgomery_0001` | failure | Not run | 222.101 | Unavailable |
| `cvdp_copilot_montgomery_0002` | failure | Not run | 362.383 | Unavailable |
| `cvdp_copilot_morse_code_0001` | success | Not run | 11.245 | Unavailable |
| `cvdp_copilot_morse_code_0014` | success | Not run | 11.377 | Unavailable |
| `cvdp_copilot_moving_average_0001` | success | Not run | 11.494 | Unavailable |
| `cvdp_copilot_moving_average_0005` | success | Not run | 7.476 | Unavailable |
| `cvdp_copilot_mux_synch_0001` | success | Not run | 59.838 | Unavailable |
| `cvdp_copilot_mux_synch_0011` | success | Not run | 74.799 | Unavailable |
| `cvdp_copilot_nbit_swizzling_0001` | success | Not run | 11.375 | Unavailable |
| `cvdp_copilot_nbit_swizzling_0014` | success | Not run | 12.102 | Unavailable |
| `cvdp_copilot_nbit_swizzling_0020` | success | Not run | 26.339 | Unavailable |
| `cvdp_copilot_neuromorphic_array_0001` | success | Not run | 63.558 | Unavailable |
| `cvdp_copilot_one_hot_address_0001` | success | Not run | 29.285 | Unavailable |
| `cvdp_copilot_packet_controller_0001` | success | Not run | 32.572 | Unavailable |
| `cvdp_copilot_palindrome_3b_0002` | success | Not run | 24.655 | Unavailable |
| `cvdp_copilot_password_generator_0001` | success | Not run | 66.376 | Unavailable |
| `cvdp_copilot_perceptron_0001` | success | Not run | 37.036 | Unavailable |
| `cvdp_copilot_perceptron_0006` | failure | Not run | 450.321 | Unavailable |
| `cvdp_copilot_perceptron_0013` | failure | Not run | 250.194 | Unavailable |
| `cvdp_copilot_perf_counters_0001` | timeout | Not run | 1608.700 | Unavailable |
| `cvdp_copilot_perfect_squares_0001` | success | Not run | 14.648 | Unavailable |
| `cvdp_copilot_ping_pong_buffer_0001` | failure | Not run | 225.074 | Unavailable |
| `cvdp_copilot_pipeline_mac_0017` | success | Not run | 86.283 | Unavailable |
| `cvdp_copilot_piso_0001` | success | Not run | 8.853 | Unavailable |
| `cvdp_copilot_pkt_detector_0001` | success | Not run | 44.553 | Unavailable |
| `cvdp_copilot_prbs_gen_0003` | failure | Not run | 206.828 | Unavailable |
| `cvdp_copilot_prim_max_0001` | success | Not run | 22.608 | Unavailable |
| `cvdp_copilot_radix2_div_0001` | success | Not run | 8.182 | Unavailable |
| `cvdp_copilot_reed_solomon_encoder_and_decoder_0005` | failure | Not run | 225.715 | Unavailable |
| `cvdp_copilot_register_file_2R1W_0006` | failure | Not run | 228.575 | Unavailable |
| `cvdp_copilot_register_file_2R1W_0013` | success | Not run | 13.252 | Unavailable |
| `cvdp_copilot_restoring_division_0001` | success | Not run | 24.737 | Unavailable |
| `cvdp_copilot_reverse_bits_0001` | success | Not run | 3.650 | Unavailable |
| `cvdp_copilot_rgb2ycbcr_0001` | success | Not run | 50.576 | Unavailable |
| `cvdp_copilot_round_robin_arbiter_0005` | success | Not run | 24.133 | Unavailable |
| `cvdp_copilot_rounding_0001` | failure | Not run | 133.831 | Unavailable |
| `cvdp_copilot_rs_232_0001` | success | Not run | 42.353 | Unavailable |
| `cvdp_copilot_run_length_0001` | success | Not run | 28.025 | Unavailable |
| `cvdp_copilot_run_length_0007` | success | Not run | 101.580 | Unavailable |
| `cvdp_copilot_scrambler_0001` | success | Not run | 42.562 | Unavailable |
| `cvdp_copilot_scrambler_0009` | failure | Not run | 752.644 | Unavailable |
| `cvdp_copilot_scrambler_0018` | success | Not run | 174.611 | Unavailable |
| `cvdp_copilot_scrambler_0024` | success | Not run | 16.654 | Unavailable |
| `cvdp_copilot_sdram_controller_0001` | success | Not run | 93.056 | Unavailable |
| `cvdp_copilot_secure_ALU_0001` | success | Not run | 7.982 | Unavailable |
| `cvdp_copilot_secure_read_write_bus_0001` | success | Not run | 10.356 | Unavailable |
| `cvdp_copilot_secure_read_write_register_bank_0001` | success | Not run | 22.907 | Unavailable |
| `cvdp_copilot_secure_variable_timer_0001` | success | Not run | 20.368 | Unavailable |
| `cvdp_copilot_sequencial_binary_to_one_hot_decoder_0001` | success | Not run | 21.456 | Unavailable |
| `cvdp_copilot_serial_in_parallel_out_0004` | success | Not run | 3.117 | Unavailable |
| `cvdp_copilot_serial_in_parallel_out_0011` | success | Not run | 104.138 | Unavailable |
| `cvdp_copilot_serial_in_parallel_out_0014` | failure | Not run | 259.026 | Unavailable |
| `cvdp_copilot_set_bit_calculator_0001` | success | Not run | 9.214 | Unavailable |
| `cvdp_copilot_sigma_delta_audio_0007` | success | Not run | 28.635 | Unavailable |
| `cvdp_copilot_signal_correlator_0015` | success | Not run | 10.958 | Unavailable |
| `cvdp_copilot_signed_adder_0001` | success | Not run | 21.749 | Unavailable |
| `cvdp_copilot_simple_spi_0001` | failure | Not run | 205.847 | Unavailable |
| `cvdp_copilot_single_number_0001` | success | Not run | 5.610 | Unavailable |
| `cvdp_copilot_skid_buffer_0001` | failure | Not run | 157.032 | Unavailable |
| `cvdp_copilot_sobel_filter_0011` | success | Not run | 28.392 | Unavailable |
| `cvdp_copilot_sorter_0001` | success | Not run | 61.834 | Unavailable |
| `cvdp_copilot_sorter_0003` | success | Not run | 46.383 | Unavailable |
| `cvdp_copilot_sorter_0009` | success | Not run | 62.438 | Unavailable |
| `cvdp_copilot_sorter_0031` | success | Not run | 59.958 | Unavailable |
| `cvdp_copilot_sound_generator_0001` | success | Not run | 34.424 | Unavailable |
| `cvdp_copilot_sprite_0004` | failure | Not run | 248.929 | Unavailable |
| `cvdp_copilot_sprite_0010` | success | Not run | 95.779 | Unavailable |
| `cvdp_copilot_square_root_0003` | success | Not run | 17.578 | Unavailable |
| `cvdp_copilot_static_branch_predict_0001` | success | Not run | 90.525 | Unavailable |
| `cvdp_copilot_static_branch_predict_0009` | success | Not run | 17.759 | Unavailable |
| `cvdp_copilot_static_branch_predict_0013` | success | Not run | 97.624 | Unavailable |
| `cvdp_copilot_static_branch_predict_0014` | success | Not run | 48.118 | Unavailable |
| `cvdp_copilot_strobe_divider_0001` | success | Not run | 38.897 | Unavailable |
| `cvdp_copilot_swizzler_0009` | success | Not run | 30.097 | Unavailable |
| `cvdp_copilot_swizzler_0014` | success | Not run | 39.320 | Unavailable |
| `cvdp_copilot_sync_lifo_0001` | success | Not run | 17.714 | Unavailable |
| `cvdp_copilot_sync_lifo_0010` | success | Not run | 25.951 | Unavailable |
| `cvdp_copilot_sync_serial_communication_0001` | timeout | Not run | Unavailable | Unavailable |
| `cvdp_copilot_sync_serial_communication_0014` | success | Not run | 220.571 | Unavailable |
| `cvdp_copilot_sync_serial_communication_0052` | success | Not run | 38.694 | Unavailable |
| `cvdp_copilot_thermostat_0001` | success | Not run | 16.381 | Unavailable |
| `cvdp_copilot_ttc_lite_0001` | success | Not run | 40.208 | Unavailable |
| `cvdp_copilot_unpacker_one_hot_0001` | success | Not run | 22.030 | Unavailable |
| `cvdp_copilot_vending_machine_0001` | failure | Not run | 264.748 | Unavailable |
| `cvdp_copilot_vga_controller_0001` | success | Not run | 30.333 | Unavailable |
| `cvdp_copilot_vga_controller_0006` | success | Not run | 38.457 | Unavailable |
| `cvdp_copilot_vga_controller_0026` | success | Not run | 63.566 | Unavailable |
| `cvdp_copilot_virtual2physical_tlb_0001` | failure | Not run | 295.502 | Unavailable |
| `cvdp_copilot_wb2ahb_0001` | failure | Not run | 231.094 | Unavailable |
| `cvdp_copilot_word_change_detector_0001` | success | Not run | 29.318 | Unavailable |
| `cvdp_copilot_word_reducer_0001` | success | Not run | 21.559 | Unavailable |
| `cvdp_copilot_word_reducer_0008` | success | Not run | 20.264 | Unavailable |
| `cvdp_copilot_write_buffer_merge_0001` | success | Not run | 63.996 | Unavailable |
| `cvdp_copilot_write_through_data_direct_mapped_cache_0012` | success | Not run | 10.548 | Unavailable |

## Limitations

One bounded non-agentic no-commercial native cohort, not all CVDP workflows or original default budgets. Commercial rows are explicitly excluded by actual tool requirements. API stochasticity and remote latency remain uncontrolled; single-run differences are descriptive, not statistically established effects. Repetitions/ablation must be reported only when actually executed. See environment and opportunities documents for provenance, integrity rules and remaining work.
