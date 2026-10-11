# ACE-RTL measured comparison

Baseline state: `completed`; coverage 292/292.
Improved state: **Not run**.

| 지표 | Baseline | JEV-like | 변화 (JEV − baseline) |
|---|---:|---:|---:|
| 평가 케이스 수 | 292 | Not run | Unavailable |
| 성공 케이스 수 | 239 | Not run | Unavailable |
| 성공률 (0–1) | 0.818 | Not run | Unavailable |
| 총 토큰 (reported + disclosed estimates) | Unavailable | Not run | Unavailable |
| 평균 토큰/케이스 | Unavailable | Not run | Unavailable |
| 총 실행 시간 (batch wall s) | 4367.250 | Not run | Unavailable |
| 평균 실행 시간/케이스 (s) | 109.631 | Not run | Unavailable |
| 주력 LLM 호출 수 | 1311 | Not run | Unavailable |
| JEV-like 호출 수 | 0 | Not run | Unavailable |
| 평균 호출 지연 시간 (s) | 17.161 | Not run | Unavailable |
| 실패 및 오류 건수 | 53 | Not run | Unavailable |

Measured token savings (%): Unavailable.
Measured batch wall-time savings (%): Unavailable.

## Conditions and measurement

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

Warmup is actual inference, excluded from evaluation metrics. Total wall time is concurrent batch wall time; average case time includes subprocess/evaluator/repair overhead. Retry calls, JEV calls and primary fallback calls count toward totals.
An inflight/error call with unavailable usage is not assigned fictional zero cost. Unknown billing suppresses token savings. Char/4 estimates are labeled and cannot establish measured token savings. Provider caches/load time may be opaque; no custom cache was added.

## Provider accounting

| Mode/provider | Calls | Reported input | Reported output | Reported total | Estimated total | Unknown usage calls | Fallback calls | Mean latency (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline/primary | 1311 | 14235838 | 2302443 | 16538281 | 0 | 33 | 0 | 17.161 |
| baseline/jev | 0 | 0 | 0 | 0 | 0 | 0 | 0 | Unavailable |

## Case outcomes

| Case | Baseline | JEV-like | Baseline s | JEV s |
|---|---|---|---:|---:|
| `cvdp_copilot_16qam_mapper_0001` | success | Not run | 35.501 | Unavailable |
| `cvdp_copilot_16qam_mapper_0006` | success | Not run | 95.382 | Unavailable |
| `cvdp_copilot_32_bit_Brent_Kung_PP_adder_0001` | success | Not run | 31.575 | Unavailable |
| `cvdp_copilot_64b66b_decoder_0001` | success | Not run | 8.265 | Unavailable |
| `cvdp_copilot_64b66b_decoder_0011` | success | Not run | 326.109 | Unavailable |
| `cvdp_copilot_64b66b_encoder_0001` | success | Not run | 9.018 | Unavailable |
| `cvdp_copilot_64b66b_encoder_0005` | success | Not run | 11.392 | Unavailable |
| `cvdp_copilot_64b66b_encoder_0009` | failure | Not run | 277.939 | Unavailable |
| `cvdp_copilot_64b66b_encoder_0022` | success | Not run | 29.705 | Unavailable |
| `cvdp_copilot_8x3_priority_encoder_0001` | success | Not run | 9.759 | Unavailable |
| `cvdp_copilot_8x3_priority_encoder_0013` | success | Not run | 18.952 | Unavailable |
| `cvdp_copilot_Attenuator_0001` | success | Not run | 27.714 | Unavailable |
| `cvdp_copilot_Carry_Lookahead_Adder_0001` | success | Not run | 5.238 | Unavailable |
| `cvdp_copilot_Carry_Lookahead_Adder_0005` | success | Not run | 57.079 | Unavailable |
| `cvdp_copilot_FIR_0001` | success | Not run | 25.441 | Unavailable |
| `cvdp_copilot_FIR_0003` | success | Not run | 16.615 | Unavailable |
| `cvdp_copilot_GFCM_0001` | success | Not run | 51.759 | Unavailable |
| `cvdp_copilot_GFCM_0003` | success | Not run | 81.588 | Unavailable |
| `cvdp_copilot_IIR_filter_0019` | success | Not run | 140.332 | Unavailable |
| `cvdp_copilot_MSHR_0001` | failure | Not run | 326.406 | Unavailable |
| `cvdp_copilot_MSHR_0008` | success | Not run | 49.528 | Unavailable |
| `cvdp_copilot_Serial_Line_Converter_0001` | success | Not run | 66.562 | Unavailable |
| `cvdp_copilot_Serial_Line_Converter_0011` | failure | Not run | 251.145 | Unavailable |
| `cvdp_copilot_String_to_ASCII_0001` | success | Not run | 23.014 | Unavailable |
| `cvdp_copilot_Synchronous_Muller_C_Element_0001` | success | Not run | 16.086 | Unavailable |
| `cvdp_copilot_adc_data_rotate_0001` | success | Not run | 15.457 | Unavailable |
| `cvdp_copilot_aes_key_expansion_0001` | success | Not run | 336.318 | Unavailable |
| `cvdp_copilot_ahb_clk_counter_0001` | success | Not run | 23.527 | Unavailable |
| `cvdp_copilot_alphablending_0003` | success | Not run | 116.164 | Unavailable |
| `cvdp_copilot_apb_dsp_op_0002` | failure | Not run | 250.076 | Unavailable |
| `cvdp_copilot_apb_dsp_unit_0001` | failure | Not run | 233.048 | Unavailable |
| `cvdp_copilot_apb_gpio_0001` | success | Not run | 220.891 | Unavailable |
| `cvdp_copilot_apb_gpio_0005` | success | Not run | 173.785 | Unavailable |
| `cvdp_copilot_apb_history_shift_register_0001` | failure | Not run | 132.480 | Unavailable |
| `cvdp_copilot_arithmetic_progression_generator_0003` | success | Not run | 21.857 | Unavailable |
| `cvdp_copilot_arithmetic_progression_generator_0015` | success | Not run | 47.240 | Unavailable |
| `cvdp_copilot_async_filo_0001` | success | Not run | 189.412 | Unavailable |
| `cvdp_copilot_async_filo_0025` | success | Not run | 25.939 | Unavailable |
| `cvdp_copilot_axi_alu_0001` | timeout | Not run | 1800.047 | Unavailable |
| `cvdp_copilot_axi_register_0001` | failure | Not run | 224.035 | Unavailable |
| `cvdp_copilot_axi_stream_downscale_0001` | failure | Not run | 112.447 | Unavailable |
| `cvdp_copilot_axi_stream_upscale_0001` | failure | Not run | 109.094 | Unavailable |
| `cvdp_copilot_axi_tap_0001` | failure | Not run | 383.419 | Unavailable |
| `cvdp_copilot_axi_tap_0009` | success | Not run | 157.844 | Unavailable |
| `cvdp_copilot_axil_precision_counter_0001` | success | Not run | 368.422 | Unavailable |
| `cvdp_copilot_axis_border_gen_0001` | failure | Not run | 307.614 | Unavailable |
| `cvdp_copilot_axis_border_gen_0014` | failure | Not run | 1798.796 | Unavailable |
| `cvdp_copilot_axis_joiner_0001` | failure | Not run | 209.086 | Unavailable |
| `cvdp_copilot_axis_mux_0001` | success | Not run | 37.520 | Unavailable |
| `cvdp_copilot_barrel_shifter_0001` | success | Not run | 5.921 | Unavailable |
| `cvdp_copilot_barrel_shifter_0037` | success | Not run | 18.757 | Unavailable |
| `cvdp_copilot_barrel_shifter_0054` | success | Not run | 12.451 | Unavailable |
| `cvdp_copilot_barrel_shifter_0058` | success | Not run | 38.921 | Unavailable |
| `cvdp_copilot_barrel_shifter_0064` | success | Not run | 18.681 | Unavailable |
| `cvdp_copilot_bcd_adder_0001` | success | Not run | 12.720 | Unavailable |
| `cvdp_copilot_bcd_counter_0001` | success | Not run | 11.043 | Unavailable |
| `cvdp_copilot_bcd_to_excess_3_0001` | success | Not run | 5.529 | Unavailable |
| `cvdp_copilot_bcd_to_excess_3_0008` | success | Not run | 6.899 | Unavailable |
| `cvdp_copilot_binary_multiplier_0012` | success | Not run | 28.200 | Unavailable |
| `cvdp_copilot_binary_search_tree_sorting_0001` | success | Not run | 95.308 | Unavailable |
| `cvdp_copilot_binary_search_tree_sorting_0014` | failure | Not run | 318.290 | Unavailable |
| `cvdp_copilot_binary_to_BCD_0001` | success | Not run | 11.950 | Unavailable |
| `cvdp_copilot_binary_to_BCD_0010` | success | Not run | 26.428 | Unavailable |
| `cvdp_copilot_binary_to_BCD_0036` | success | Not run | 9.801 | Unavailable |
| `cvdp_copilot_binary_to_gray_0001` | success | Not run | 4.594 | Unavailable |
| `cvdp_copilot_binary_to_gray_0013` | success | Not run | 3.868 | Unavailable |
| `cvdp_copilot_binary_to_one_hot_decoder_0001` | success | Not run | 28.206 | Unavailable |
| `cvdp_copilot_bit_synchronizer_0001` | success | Not run | 10.598 | Unavailable |
| `cvdp_copilot_bus_arbiter_0001` | success | Not run | 43.794 | Unavailable |
| `cvdp_copilot_bus_arbiter_0004` | success | Not run | 12.853 | Unavailable |
| `cvdp_copilot_cache_lru_0001` | success | Not run | 26.864 | Unavailable |
| `cvdp_copilot_cache_lru_0008` | success | Not run | 23.955 | Unavailable |
| `cvdp_copilot_cache_lru_0011` | success | Not run | 15.571 | Unavailable |
| `cvdp_copilot_cache_lru_0016` | success | Not run | 25.618 | Unavailable |
| `cvdp_copilot_cache_lru_0019` | success | Not run | 92.625 | Unavailable |
| `cvdp_copilot_cache_lru_0022` | success | Not run | 9.606 | Unavailable |
| `cvdp_copilot_caesar_cipher_0001` | success | Not run | 13.281 | Unavailable |
| `cvdp_copilot_caesar_cipher_0024` | success | Not run | 21.405 | Unavailable |
| `cvdp_copilot_caesar_cipher_0038` | success | Not run | 15.029 | Unavailable |
| `cvdp_copilot_car_parking_management_0001` | success | Not run | 41.581 | Unavailable |
| `cvdp_copilot_car_parking_management_0015` | success | Not run | 33.392 | Unavailable |
| `cvdp_copilot_car_parking_management_0018` | success | Not run | 188.536 | Unavailable |
| `cvdp_copilot_car_parking_management_0031` | success | Not run | 29.524 | Unavailable |
| `cvdp_copilot_cascaded_adder_0001` | success | Not run | 49.628 | Unavailable |
| `cvdp_copilot_cascaded_adder_0025` | success | Not run | 191.162 | Unavailable |
| `cvdp_copilot_cdc_pulse_synchronizer_0004` | success | Not run | 4.169 | Unavailable |
| `cvdp_copilot_cdc_pulse_synchronizer_0013` | success | Not run | 14.970 | Unavailable |
| `cvdp_copilot_cellular_automata_0001` | success | Not run | 19.692 | Unavailable |
| `cvdp_copilot_cellular_automata_0017` | success | Not run | 13.817 | Unavailable |
| `cvdp_copilot_clock_divider_0003` | success | Not run | 10.508 | Unavailable |
| `cvdp_copilot_clock_jitter_detection_module_0003` | success | Not run | 158.920 | Unavailable |
| `cvdp_copilot_coffee_machine_0001` | success | Not run | 112.770 | Unavailable |
| `cvdp_copilot_comparator_0001` | success | Not run | 8.459 | Unavailable |
| `cvdp_copilot_complex_multiplier_0001` | success | Not run | 12.296 | Unavailable |
| `cvdp_copilot_compression_engine_0001` | success | Not run | 57.389 | Unavailable |
| `cvdp_copilot_concatenate_0001` | failure | Not run | 167.085 | Unavailable |
| `cvdp_copilot_configurable_digital_low_pass_filter_0001` | success | Not run | 36.081 | Unavailable |
| `cvdp_copilot_configurable_digital_low_pass_filter_0004` | success | Not run | 60.321 | Unavailable |
| `cvdp_copilot_configurable_digital_low_pass_filter_0011` | success | Not run | 78.003 | Unavailable |
| `cvdp_copilot_configurable_digital_low_pass_filter_0014` | success | Not run | 19.939 | Unavailable |
| `cvdp_copilot_cont_adder_0006` | success | Not run | 22.021 | Unavailable |
| `cvdp_copilot_cont_adder_0023` | success | Not run | 34.496 | Unavailable |
| `cvdp_copilot_cont_adder_0042` | success | Not run | 84.079 | Unavailable |
| `cvdp_copilot_convolutional_encoder_0001` | success | Not run | 6.152 | Unavailable |
| `cvdp_copilot_convolutional_encoder_0010` | success | Not run | 5.071 | Unavailable |
| `cvdp_copilot_crossbar_switch_0001` | success | Not run | 8.530 | Unavailable |
| `cvdp_copilot_data_bus_controller_0001` | success | Not run | 68.212 | Unavailable |
| `cvdp_copilot_data_serializer_0001` | success | Not run | 19.692 | Unavailable |
| `cvdp_copilot_data_width_converter_0003` | success | Not run | 6.210 | Unavailable |
| `cvdp_copilot_dbi_0001` | success | Not run | 12.224 | Unavailable |
| `cvdp_copilot_dbi_0008` | success | Not run | 8.039 | Unavailable |
| `cvdp_copilot_dbi_dec_0001` | success | Not run | 4.500 | Unavailable |
| `cvdp_copilot_decode_firstbit_0001` | success | Not run | 67.042 | Unavailable |
| `cvdp_copilot_decoder_8b10b_0001` | success | Not run | 7.696 | Unavailable |
| `cvdp_copilot_digital_dice_roller_0001` | failure | Not run | 156.058 | Unavailable |
| `cvdp_copilot_digital_dice_roller_0004` | success | Not run | 20.622 | Unavailable |
| `cvdp_copilot_digital_stopwatch_0001` | failure | Not run | 1322.071 | Unavailable |
| `cvdp_copilot_digital_stopwatch_0012` | success | Not run | 53.287 | Unavailable |
| `cvdp_copilot_dot_product_0002` | success | Not run | 13.239 | Unavailable |
| `cvdp_copilot_dot_product_0005` | success | Not run | 76.783 | Unavailable |
| `cvdp_copilot_dot_product_0012` | success | Not run | 10.953 | Unavailable |
| `cvdp_copilot_edge_detector_0001` | success | Not run | 4.600 | Unavailable |
| `cvdp_copilot_elastic_buffer_0001` | success | Not run | 21.224 | Unavailable |
| `cvdp_copilot_elevator_control_0006` | failure | Not run | 1753.394 | Unavailable |
| `cvdp_copilot_elevator_control_0009` | success | Not run | 78.723 | Unavailable |
| `cvdp_copilot_elevator_control_0026` | success | Not run | 221.175 | Unavailable |
| `cvdp_copilot_elevator_control_0033` | success | Not run | 38.102 | Unavailable |
| `cvdp_copilot_elevator_control_0036` | success | Not run | 101.849 | Unavailable |
| `cvdp_copilot_ethernet_packet_parser_0001` | success | Not run | 47.860 | Unavailable |
| `cvdp_copilot_events_to_apb_0001` | success | Not run | 42.992 | Unavailable |
| `cvdp_copilot_factorial_0001` | success | Not run | 19.465 | Unavailable |
| `cvdp_copilot_fan_controller_0001` | success | Not run | 21.156 | Unavailable |
| `cvdp_copilot_fan_controller_0005` | success | Not run | 15.735 | Unavailable |
| `cvdp_copilot_fan_controller_0008` | failure | Not run | 225.728 | Unavailable |
| `cvdp_copilot_fibonacci_series_0001` | success | Not run | 81.728 | Unavailable |
| `cvdp_copilot_fifo_async_0001` | success | Not run | 71.101 | Unavailable |
| `cvdp_copilot_fifo_to_axis_0001` | failure | Not run | 201.515 | Unavailable |
| `cvdp_copilot_fifo_to_axis_0005` | success | Not run | 41.659 | Unavailable |
| `cvdp_copilot_filo_0005` | success | Not run | 16.297 | Unavailable |
| `cvdp_copilot_filo_0033` | success | Not run | 26.772 | Unavailable |
| `cvdp_copilot_findfasterclock_0001` | success | Not run | 44.741 | Unavailable |
| `cvdp_copilot_flop_0001` | success | Not run | 5.815 | Unavailable |
| `cvdp_copilot_flop_0002` | success | Not run | 5.970 | Unavailable |
| `cvdp_copilot_fsm_seq_detector_0001` | success | Not run | 12.161 | Unavailable |
| `cvdp_copilot_fsm_seq_detector_0023` | success | Not run | 24.581 | Unavailable |
| `cvdp_copilot_galois_encryption_0001` | failure | Not run | 327.891 | Unavailable |
| `cvdp_copilot_gaussian_rounding_div_0003` | success | Not run | 58.575 | Unavailable |
| `cvdp_copilot_gaussian_rounding_div_0005` | failure | Not run | 310.373 | Unavailable |
| `cvdp_copilot_gcd_0001` | success | Not run | 248.342 | Unavailable |
| `cvdp_copilot_gcd_0009` | success | Not run | 50.894 | Unavailable |
| `cvdp_copilot_gcd_0015` | success | Not run | 40.543 | Unavailable |
| `cvdp_copilot_gcd_0023` | success | Not run | 105.260 | Unavailable |
| `cvdp_copilot_generic_nbit_counter_0036` | success | Not run | 19.452 | Unavailable |
| `cvdp_copilot_generic_nbit_counter_0039` | success | Not run | 17.207 | Unavailable |
| `cvdp_copilot_gf_multiplier_0001` | success | Not run | 10.776 | Unavailable |
| `cvdp_copilot_gf_multiplier_0005` | success | Not run | 7.421 | Unavailable |
| `cvdp_copilot_gf_multiplier_0013` | success | Not run | 33.247 | Unavailable |
| `cvdp_copilot_gf_multiplier_0021` | success | Not run | 88.235 | Unavailable |
| `cvdp_copilot_gmii_axis_0001` | success | Not run | 26.718 | Unavailable |
| `cvdp_copilot_gray_to_binary_0001` | success | Not run | 11.933 | Unavailable |
| `cvdp_copilot_grayscale_image_0014` | success | Not run | 16.983 | Unavailable |
| `cvdp_copilot_halfband_fir_0005` | success | Not run | 21.181 | Unavailable |
| `cvdp_copilot_hamming_code_tx_and_rx_0001` | success | Not run | 5.026 | Unavailable |
| `cvdp_copilot_hamming_code_tx_and_rx_0003` | success | Not run | 10.609 | Unavailable |
| `cvdp_copilot_hamming_code_tx_and_rx_0009` | success | Not run | 42.438 | Unavailable |
| `cvdp_copilot_hamming_code_tx_and_rx_0011` | success | Not run | 26.414 | Unavailable |
| `cvdp_copilot_hamming_code_tx_and_rx_0013` | success | Not run | 68.778 | Unavailable |
| `cvdp_copilot_hebbian_rule_0012` | failure | Not run | 337.618 | Unavailable |
| `cvdp_copilot_hebbian_rule_0017` | failure | Not run | 213.385 | Unavailable |
| `cvdp_copilot_hill_cipher_0001` | success | Not run | 42.302 | Unavailable |
| `cvdp_copilot_hill_cipher_0015` | success | Not run | 53.535 | Unavailable |
| `cvdp_copilot_hmac_register_0001` | failure | Not run | 245.643 | Unavailable |
| `cvdp_copilot_huffman_0001` | success | Not run | 53.177 | Unavailable |
| `cvdp_copilot_icache_controller_0001` | success | Not run | 48.644 | Unavailable |
| `cvdp_copilot_image_rotate_0001` | success | Not run | 136.129 | Unavailable |
| `cvdp_copilot_image_rotate_0014` | success | Not run | 43.747 | Unavailable |
| `cvdp_copilot_image_rotate_0015` | success | Not run | 32.285 | Unavailable |
| `cvdp_copilot_image_stego_0004` | success | Not run | 10.512 | Unavailable |
| `cvdp_copilot_interrupt_controller_0014` | failure | Not run | 185.813 | Unavailable |
| `cvdp_copilot_interrupt_controller_0017` | failure | Not run | 243.677 | Unavailable |
| `cvdp_copilot_interrupt_controller_0019` | failure | Not run | 200.298 | Unavailable |
| `cvdp_copilot_ir_receiver_0001` | failure | Not run | 1678.030 | Unavailable |
| `cvdp_copilot_ir_receiver_0005` | failure | Not run | 351.059 | Unavailable |
| `cvdp_copilot_kogge_stone_adder_0007` | success | Not run | 29.042 | Unavailable |
| `cvdp_copilot_lfsr_0007` | success | Not run | 5.530 | Unavailable |
| `cvdp_copilot_line_buffer_0003` | success | Not run | 54.052 | Unavailable |
| `cvdp_copilot_load_store_unit_0001` | success | Not run | 63.214 | Unavailable |
| `cvdp_copilot_load_store_unit_0003` | success | Not run | 28.623 | Unavailable |
| `cvdp_copilot_load_store_unit_0009` | success | Not run | 52.221 | Unavailable |
| `cvdp_copilot_manchester_enc_0005` | success | Not run | 11.820 | Unavailable |
| `cvdp_copilot_manchester_enc_0013` | success | Not run | 8.881 | Unavailable |
| `cvdp_copilot_matrix_multiplier_0001` | success | Not run | 33.128 | Unavailable |
| `cvdp_copilot_matrix_multiplier_0007` | success | Not run | 64.892 | Unavailable |
| `cvdp_copilot_matrix_multiplier_0010` | success | Not run | 99.185 | Unavailable |
| `cvdp_copilot_mem_allocator_0001` | success | Not run | 31.215 | Unavailable |
| `cvdp_copilot_microcode_sequencer_0001` | failure | Not run | 197.478 | Unavailable |
| `cvdp_copilot_modified_booth_mul_0002` | success | Not run | 33.767 | Unavailable |
| `cvdp_copilot_modified_booth_mul_0005` | success | Not run | 32.524 | Unavailable |
| `cvdp_copilot_montgomery_0001` | success | Not run | 38.115 | Unavailable |
| `cvdp_copilot_montgomery_0002` | failure | Not run | 338.825 | Unavailable |
| `cvdp_copilot_morse_code_0001` | success | Not run | 9.751 | Unavailable |
| `cvdp_copilot_morse_code_0014` | success | Not run | 10.024 | Unavailable |
| `cvdp_copilot_moving_average_0001` | success | Not run | 8.857 | Unavailable |
| `cvdp_copilot_moving_average_0005` | success | Not run | 8.000 | Unavailable |
| `cvdp_copilot_mux_synch_0001` | success | Not run | 14.473 | Unavailable |
| `cvdp_copilot_mux_synch_0011` | success | Not run | 54.237 | Unavailable |
| `cvdp_copilot_nbit_swizzling_0001` | success | Not run | 19.226 | Unavailable |
| `cvdp_copilot_nbit_swizzling_0014` | success | Not run | 13.793 | Unavailable |
| `cvdp_copilot_nbit_swizzling_0020` | success | Not run | 36.971 | Unavailable |
| `cvdp_copilot_neuromorphic_array_0001` | success | Not run | 36.506 | Unavailable |
| `cvdp_copilot_one_hot_address_0001` | success | Not run | 25.244 | Unavailable |
| `cvdp_copilot_packet_controller_0001` | success | Not run | 55.465 | Unavailable |
| `cvdp_copilot_palindrome_3b_0002` | success | Not run | 18.581 | Unavailable |
| `cvdp_copilot_password_generator_0001` | success | Not run | 58.187 | Unavailable |
| `cvdp_copilot_perceptron_0001` | success | Not run | 45.602 | Unavailable |
| `cvdp_copilot_perceptron_0006` | failure | Not run | 308.152 | Unavailable |
| `cvdp_copilot_perceptron_0013` | failure | Not run | 304.109 | Unavailable |
| `cvdp_copilot_perf_counters_0001` | failure | Not run | 1623.169 | Unavailable |
| `cvdp_copilot_perfect_squares_0001` | success | Not run | 13.372 | Unavailable |
| `cvdp_copilot_ping_pong_buffer_0001` | failure | Not run | 199.187 | Unavailable |
| `cvdp_copilot_pipeline_mac_0017` | success | Not run | 50.555 | Unavailable |
| `cvdp_copilot_piso_0001` | success | Not run | 11.702 | Unavailable |
| `cvdp_copilot_pkt_detector_0001` | success | Not run | 36.236 | Unavailable |
| `cvdp_copilot_prbs_gen_0003` | failure | Not run | 225.253 | Unavailable |
| `cvdp_copilot_prim_max_0001` | success | Not run | 27.883 | Unavailable |
| `cvdp_copilot_radix2_div_0001` | success | Not run | 9.887 | Unavailable |
| `cvdp_copilot_reed_solomon_encoder_and_decoder_0005` | failure | Not run | 243.259 | Unavailable |
| `cvdp_copilot_register_file_2R1W_0006` | failure | Not run | 214.343 | Unavailable |
| `cvdp_copilot_register_file_2R1W_0013` | success | Not run | 11.276 | Unavailable |
| `cvdp_copilot_restoring_division_0001` | success | Not run | 27.723 | Unavailable |
| `cvdp_copilot_reverse_bits_0001` | success | Not run | 4.476 | Unavailable |
| `cvdp_copilot_rgb2ycbcr_0001` | success | Not run | 29.540 | Unavailable |
| `cvdp_copilot_round_robin_arbiter_0005` | success | Not run | 30.315 | Unavailable |
| `cvdp_copilot_rounding_0001` | failure | Not run | 132.736 | Unavailable |
| `cvdp_copilot_rs_232_0001` | success | Not run | 51.926 | Unavailable |
| `cvdp_copilot_run_length_0001` | failure | Not run | 213.294 | Unavailable |
| `cvdp_copilot_run_length_0007` | failure | Not run | 287.105 | Unavailable |
| `cvdp_copilot_scrambler_0001` | failure | Not run | 302.381 | Unavailable |
| `cvdp_copilot_scrambler_0009` | failure | Not run | 507.694 | Unavailable |
| `cvdp_copilot_scrambler_0018` | failure | Not run | 236.567 | Unavailable |
| `cvdp_copilot_scrambler_0024` | success | Not run | 16.091 | Unavailable |
| `cvdp_copilot_sdram_controller_0001` | success | Not run | 97.426 | Unavailable |
| `cvdp_copilot_secure_ALU_0001` | success | Not run | 8.118 | Unavailable |
| `cvdp_copilot_secure_read_write_bus_0001` | success | Not run | 11.954 | Unavailable |
| `cvdp_copilot_secure_read_write_register_bank_0001` | success | Not run | 53.046 | Unavailable |
| `cvdp_copilot_secure_variable_timer_0001` | success | Not run | 16.709 | Unavailable |
| `cvdp_copilot_sequencial_binary_to_one_hot_decoder_0001` | success | Not run | 20.992 | Unavailable |
| `cvdp_copilot_serial_in_parallel_out_0004` | success | Not run | 3.620 | Unavailable |
| `cvdp_copilot_serial_in_parallel_out_0011` | success | Not run | 104.959 | Unavailable |
| `cvdp_copilot_serial_in_parallel_out_0014` | failure | Not run | 245.501 | Unavailable |
| `cvdp_copilot_set_bit_calculator_0001` | success | Not run | 7.852 | Unavailable |
| `cvdp_copilot_sigma_delta_audio_0007` | success | Not run | 28.881 | Unavailable |
| `cvdp_copilot_signal_correlator_0015` | success | Not run | 10.253 | Unavailable |
| `cvdp_copilot_signed_adder_0001` | success | Not run | 22.398 | Unavailable |
| `cvdp_copilot_simple_spi_0001` | failure | Not run | 166.110 | Unavailable |
| `cvdp_copilot_single_number_0001` | success | Not run | 4.425 | Unavailable |
| `cvdp_copilot_skid_buffer_0001` | failure | Not run | 130.876 | Unavailable |
| `cvdp_copilot_sobel_filter_0011` | success | Not run | 59.069 | Unavailable |
| `cvdp_copilot_sorter_0001` | success | Not run | 34.466 | Unavailable |
| `cvdp_copilot_sorter_0003` | success | Not run | 76.812 | Unavailable |
| `cvdp_copilot_sorter_0009` | success | Not run | 39.669 | Unavailable |
| `cvdp_copilot_sorter_0031` | success | Not run | 54.618 | Unavailable |
| `cvdp_copilot_sound_generator_0001` | success | Not run | 31.273 | Unavailable |
| `cvdp_copilot_sprite_0004` | failure | Not run | 236.454 | Unavailable |
| `cvdp_copilot_sprite_0010` | success | Not run | 77.430 | Unavailable |
| `cvdp_copilot_square_root_0003` | success | Not run | 14.991 | Unavailable |
| `cvdp_copilot_static_branch_predict_0001` | success | Not run | 98.242 | Unavailable |
| `cvdp_copilot_static_branch_predict_0009` | success | Not run | 19.388 | Unavailable |
| `cvdp_copilot_static_branch_predict_0013` | success | Not run | 22.078 | Unavailable |
| `cvdp_copilot_static_branch_predict_0014` | success | Not run | 20.728 | Unavailable |
| `cvdp_copilot_strobe_divider_0001` | success | Not run | 30.029 | Unavailable |
| `cvdp_copilot_swizzler_0009` | success | Not run | 30.673 | Unavailable |
| `cvdp_copilot_swizzler_0014` | success | Not run | 25.194 | Unavailable |
| `cvdp_copilot_sync_lifo_0001` | success | Not run | 19.581 | Unavailable |
| `cvdp_copilot_sync_lifo_0010` | success | Not run | 27.441 | Unavailable |
| `cvdp_copilot_sync_serial_communication_0001` | success | Not run | 92.409 | Unavailable |
| `cvdp_copilot_sync_serial_communication_0014` | success | Not run | 82.092 | Unavailable |
| `cvdp_copilot_sync_serial_communication_0052` | success | Not run | 56.793 | Unavailable |
| `cvdp_copilot_thermostat_0001` | success | Not run | 16.112 | Unavailable |
| `cvdp_copilot_ttc_lite_0001` | success | Not run | 49.237 | Unavailable |
| `cvdp_copilot_unpacker_one_hot_0001` | success | Not run | 20.937 | Unavailable |
| `cvdp_copilot_vending_machine_0001` | failure | Not run | 241.990 | Unavailable |
| `cvdp_copilot_vga_controller_0001` | success | Not run | 29.049 | Unavailable |
| `cvdp_copilot_vga_controller_0006` | success | Not run | 32.019 | Unavailable |
| `cvdp_copilot_vga_controller_0026` | success | Not run | 68.451 | Unavailable |
| `cvdp_copilot_virtual2physical_tlb_0001` | failure | Not run | 299.898 | Unavailable |
| `cvdp_copilot_wb2ahb_0001` | failure | Not run | 242.726 | Unavailable |
| `cvdp_copilot_word_change_detector_0001` | success | Not run | 25.036 | Unavailable |
| `cvdp_copilot_word_reducer_0001` | success | Not run | 26.336 | Unavailable |
| `cvdp_copilot_word_reducer_0008` | success | Not run | 18.884 | Unavailable |
| `cvdp_copilot_write_buffer_merge_0001` | success | Not run | 72.064 | Unavailable |
| `cvdp_copilot_write_through_data_direct_mapped_cache_0012` | success | Not run | 12.167 | Unavailable |

## Limitations

One bounded non-agentic no-commercial native cohort, not all CVDP workflows or original default budgets. Commercial rows are explicitly excluded by actual tool requirements. API stochasticity and remote latency remain uncontrolled; single-run differences are descriptive, not statistically established effects. Repetitions/ablation must be reported only when actually executed. See environment and opportunities documents for provenance, integrity rules and remaining work.
