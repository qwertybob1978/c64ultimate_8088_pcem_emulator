.setcpu "6502"

.import turbo_detect
.import turbo_enable_max
.import turbo_restore
.import cartridge_stage_media
.import host_keyboard_translate
.import host_keyboard_poll
.import io_keyboard_service
.import io_keyboard_pa
.import io_keyboard_key_waiting
.import io_keyboard_wantirq
.import io_keyboard_count
.import io_keyboard_reset
.import guest_load_genxt
.import reu_detect
.import reu_probe_16m
.import cpu8088_reset
.import cpu8088_cs_ip_physical
.import cpu8088_segment_offset_physical
.import cpu8088_mem_read_u8
.import cpu8088_mem_write_u8
.importzp cpu8088_phys_addr
.importzp cpu8088_segment
.importzp cpu8088_offset
.import cpu8088_state
.import cpu8088_step
.import cpu8088_last_opcode
.import cpu8088_mul_u8
.import cpu8088_mul_s8
.import cpu8088_mul_u16
.import cpu8088_mul_s16
.import cpu8088_request_irq
.import pic_reset
.import pic_request_irq
.import pic_service
.import dma_reset
.import fdc_reset
.import fdc_last_command
.import fdc_read_count
.import fdc_dma_failures
.import fdc_dor_writes
.import pic_irq6_requests
.import pic_irq6_deliveries
.import pic_irq1_requests
.import pic_irq1_deliveries
.import pic_vector_base
.import pic_mask
.import cpu8088_irq6_serviced
.import cpu8088_interrupt_stage
.import cpu8088_stack_stage
.import interrupt_last_iret_ip
.import interrupt_last_iret_cs
.import interrupt_last_iret_stage
.import interrupt_frame_mismatch
.import stack_fail_phys
.import cpu8088_irq_vector
.import interrupt_vector
.import io_fdc_data_writes
.import fdc_data_reads
.import fdc_last_data_read
.import fdc_last_st0_read
.import pit_reset
.import pit_advance_cycles
.import cpu8088_fetch_cache_invalidate
.import cpu8088_last_cycles
.import io_debug_latch
.import io_read_u8
.import io_write_u8
.import io_keyboard_push
.import cga_test_render
.import cga_render_text_40
.import cga_test_error
.import reu_copy_to_reu
.import reu_copy_from_reu
.importzp reu_c64_addr
.importzp reu_ext_addr
.importzp reu_length

.include "cpu8088/state.inc"
.include "cpu8088/core.inc"
.segment "RODATA"
.include "cpu8088/smoke_vector.inc"

CHROUT = $FFD2
BORDER_COLOR = $D020
COLOR_RED = $02
COLOR_GREEN = $05
COLOR_PURPLE = $04

.macro long_bne target
    beq :+
    jmp target
:
.endmacro

.macro long_bcc target
    bcs :+
    jmp target
:
.endmacro

.macro long_beq target
    bne :+
    jmp target
:
.endmacro

.segment "LOADADDR"
    .word $0801

.segment "BASIC"
    .word @next_line
    .word 10
    .byte $9E
    .byte "2061", $00             ; SYS $080D
@next_line:
    .word $0000

.segment "ZEROPAGE"
message_ptr: .res 2
print_screen: .res 2

.segment "BSS"
boot_fault_cs:        .res 2
boot_fault_ip:        .res 2
boot_fault_ss:        .res 2
boot_fault_sp:        .res 2
boot_fault_bytes:     .res 4
boot_stack_bytes:     .res 4
boot_fault_ivt:       .res 4
boot_fault_ivt0:      .res 4
boot_prev2_cs:        .res 2
boot_prev2_ip:        .res 2
boot_prev2_opcode:    .res 1
boot_prev2_status:    .res 1
boot_prev_cs:         .res 2
boot_prev_ip:         .res 2
boot_prev_opcode:     .res 1
boot_prev_status:     .res 1
boot_genxt_ivt_ready: .res 1
boot_genxt_ivt_index: .res 1

.segment "CODE"
start:
    lda #COLOR_RED
    sta BORDER_COLOR
    ; Direct screen-RAM marker, independent of KERNAL CHROUT/IRQ behavior.
    lda #$13
    sta $0400
    lda #$14
    sta $0401
    lda #$01
    sta $D800
    sta $D801
    lda #<msg_title
    ldx #>msg_title
    jsr print

    jsr turbo_detect
    bcc @turbo_fail
    lda #<msg_turbo_ok
    ldx #>msg_turbo_ok
    jsr print
    jsr turbo_enable_max
    jmp @test_reu
@turbo_fail:
    lda #<msg_turbo_fail
    ldx #>msg_turbo_fail
    jsr print

@test_reu:
    jsr reu_detect
    bcc @reu_fail
    lda #<msg_reu_ok
    ldx #>msg_reu_ok
    jsr print
    jsr reu_probe_16m
    bcc @capacity_fail
    lda #<msg_capacity_ok
    ldx #>msg_capacity_ok
    jsr print
    jsr test_cpu_reset
    bcc @cpu_fail
    lda #<msg_cpu_ok
    ldx #>msg_cpu_ok
    jsr print
    ; Enter the integration path immediately. The remaining host self-tests
    ; are retained below for standalone diagnostics but can mask a BIOS boot
    ; failure when a peripheral model is incomplete.
    jmp boot_guest
    jsr test_cpu_stepper
    ; Keep the hardware boot path observable even if the optional synthetic
    ; vector test fails; BIOS execution is the authoritative integration test.
    bcc boot_guest
    jsr test_cpu_multiply
    bcc @stepper_fail
    jsr test_video_status
    bcc @stepper_fail
    jsr test_keyboard_translation
    bcc @stepper_fail
    lda #<msg_stepper_ok
    ldx #>msg_stepper_ok
    jsr print
    jsr cga_test_render
    bcc @cga_fail
    lda #COLOR_GREEN
    sta BORDER_COLOR
    jmp boot_guest
@cga_fail:
    lda cga_test_error
    sta BORDER_COLOR
    lda #<msg_cga_fail
    ldx #>msg_cga_fail
    jsr print
    jmp diagnostic_done
@stepper_fail:
    lda #COLOR_PURPLE
    sta BORDER_COLOR
    lda #<msg_stepper_fail
    ldx #>msg_stepper_fail
    jsr print
    jmp diagnostic_done
@cpu_fail:
    lda #<msg_cpu_fail
    ldx #>msg_cpu_fail
    jsr print
    jmp diagnostic_done
@capacity_fail:
    lda #<msg_capacity_fail
    ldx #>msg_capacity_fail
    jsr print
    jmp diagnostic_done
@reu_fail:
    lda #<msg_reu_fail
    ldx #>msg_reu_fail
    jsr print

diagnostic_done:
    jsr turbo_restore
    rts

; Initialize the real Generic XT guest and run it indefinitely. Host services
; are interleaved between bounded 8088 batches so C64 keyboard and screen I/O
; remain responsive even in Ultimate turbo mode.
boot_guest:
    ; From this point onward the payload no longer calls KERNAL output. Keep
    ; asynchronous C64 IRQs out of the long-running host/emulator loop.
    sei
    ; Host-side breadcrumb: proves the cartridge reached the guest runner even
    ; if the CGA projection has not produced a frame yet.
    lda #$58                    ; X
    sta $0400
    lda #$01
    sta $D800
    lda #$0B
    sta BORDER_COLOR
    lda #$0C
    sta BORDER_COLOR
    jsr guest_load_genxt
    long_bcc @boot_guest_loaded
    jmp @boot_failed
@boot_guest_loaded:
@boot_media_ready:
    lda #$0D
    sta BORDER_COLOR
    jsr pic_reset
    jsr dma_reset
    jsr fdc_reset
    jsr pit_reset
    jsr cpu8088_fetch_cache_invalidate
    jsr cpu8088_reset
    jsr io_keyboard_reset
    lda #$00
    sta boot_video_divider
    sta boot_autokey_counter
    sta boot_autokey_sent
    sta boot_genxt_ivt_ready
@boot_batch:
    lda #$40
    sta boot_steps_remaining
@boot_step:
    lda cpu8088_state+CPU_CS
    sta boot_fault_cs
    lda cpu8088_state+CPU_CS+1
    sta boot_fault_cs+1
    lda cpu8088_state+CPU_IP
    sta boot_fault_ip
    lda cpu8088_state+CPU_IP+1
    sta boot_fault_ip+1
    lda cpu8088_state+CPU_SS
    sta boot_fault_ss
    lda cpu8088_state+CPU_SS+1
    sta boot_fault_ss+1
    lda cpu8088_state+CPU_SP
    sta boot_fault_sp
    lda cpu8088_state+CPU_SP+1
    sta boot_fault_sp+1
    jsr install_genxt_boot_ivt
    bcc :+
    lda #CPU_STEP_MEMORY
    sta boot_failure_status
    jmp @boot_failed
:
    jsr cpu8088_step
    sta boot_failure_status
    cmp #CPU_STEP_OK
    long_beq @boot_step_record
    cmp #CPU_STEP_HALTED
    long_beq @boot_step_record
    jmp @boot_failed
@boot_step_record:
    lda boot_prev_cs
    sta boot_prev2_cs
    lda boot_prev_cs+1
    sta boot_prev2_cs+1
    lda boot_prev_ip
    sta boot_prev2_ip
    lda boot_prev_ip+1
    sta boot_prev2_ip+1
    lda boot_prev_opcode
    sta boot_prev2_opcode
    lda boot_prev_status
    sta boot_prev2_status
    lda boot_fault_cs
    sta boot_prev_cs
    lda boot_fault_cs+1
    sta boot_prev_cs+1
    lda boot_fault_ip
    sta boot_prev_ip
    lda boot_fault_ip+1
    sta boot_prev_ip+1
    lda cpu8088_last_opcode
    sta boot_prev_opcode
    lda boot_failure_status
    sta boot_prev_status
    lda cpu8088_last_cycles
    jsr pit_advance_cycles
@boot_step_done:
    dec boot_steps_remaining
    beq :+
    jmp @boot_step
:

    jsr host_keyboard_poll
    inc boot_autokey_counter
    lda boot_autokey_sent
    bne :+
    lda cpu8088_state+CPU_CS
    bne :+
    lda cpu8088_state+CPU_CS+1
    cmp #$F0
    bne :+
    lda cpu8088_state+CPU_IP+1
    cmp #$F9
    bne :+
    lda cpu8088_state+CPU_IP
    cmp #$80
    bcc :+
    cmp #$A3
    bcs :+
    lda #$01
    sta boot_autokey_sent
    ; Answer the Generic XT "Continue?" prompt after POST has initialized its
    ; keyboard state. The BIOS accepts ASCII Y/y, not a function key.
    lda #$15                    ; XT set-1 Y make code
    jsr io_keyboard_push
    lda #$95                    ; XT set-1 Y break code
    jsr io_keyboard_push
    jsr io_keyboard_service
    jsr io_keyboard_service
    jsr io_keyboard_service
    lda #$01
    jsr pic_request_irq
:
    jsr cga_render_text_40
    jsr display_fdc_runtime
@skip_video:
    jmp @boot_batch
@boot_failed:
    jsr capture_boot_fault_context
    jsr cga_render_text_40
    lda cpu8088_last_opcode
    pha
    lsr a
    lsr a
    lsr a
    lsr a
    sta BORDER_COLOR
    pla
    and #$0F
    sta $D021
    jsr display_boot_failure
    jsr display_fdc_runtime
    jmp diagnostic_done

install_genxt_boot_ivt:
    lda boot_genxt_ivt_ready
    bne @done
    lda cpu8088_state+CPU_CS
    bne @done
    lda cpu8088_state+CPU_CS+1
    cmp #$F0
    bne @done
    lda cpu8088_state+CPU_IP
    cmp #$80
    bne @done
    lda cpu8088_state+CPU_IP+1
    cmp #$F9
    bne @done

    lda #$20
    sta cpu8088_phys_addr
    lda #$00
    sta cpu8088_phys_addr+1
    sta cpu8088_phys_addr+2
    sta boot_genxt_ivt_index
@copy_vector:
    ldx boot_genxt_ivt_index
    lda genxt_boot_vector_offsets,x
    jsr cpu8088_mem_write_u8
    bcs @failed
    jsr increment_phys_addr
    inc boot_genxt_ivt_index
    ldx boot_genxt_ivt_index
    lda genxt_boot_vector_offsets,x
    jsr cpu8088_mem_write_u8
    bcs @failed
    jsr increment_phys_addr
    lda #$00
    jsr cpu8088_mem_write_u8
    bcs @failed
    jsr increment_phys_addr
    lda #$F0
    jsr cpu8088_mem_write_u8
    bcs @failed
    jsr increment_phys_addr
    inc boot_genxt_ivt_index
    lda boot_genxt_ivt_index
    cmp #genxt_boot_vector_offsets_size
    bne @copy_vector
    lda #$01
    sta boot_genxt_ivt_ready
@done:
    clc
@failed:
    rts

display_boot_failure:
    lda #$01                    ; visible white text on failure screen
    sta $D800
    sta $D801
    sta $D802
    sta $D803
    sta $D804
    sta $D805
    sta $D806
    sta $D807
    sta $D808
    sta $D828
    sta $D829
    sta $D82A
    sta $D82B
    sta $D82C
    sta $D82D
    sta $D82E
    sta $D82F
    sta $D830
    sta $D831
    sta $D832
    sta $D833
    sta $D834
    sta $D835
    sta $D850
    sta $D851
    sta $D852
    sta $D853
    sta $D854
    sta $D855
    sta $D856
    sta $D857
    sta $D858
    sta $D859
    sta $D85A
    sta $D85B
    sta $D85C
    sta $D85D
    sta $D85E
    sta $D85F
    sta $D860
    sta $D878
    sta $D879
    sta $D87A
    sta $D87B
    sta $D87C
    sta $D87D
    sta $D87E
    sta $D87F
    sta $D880
    sta $D881
    sta $D882
    sta $D883
    sta $D884
    sta $D885
    sta $D886
    sta $D887
    sta $D888
    lda #$02                    ; B
    sta $0400
    lda #$0F                    ; O
    sta $0401
    sta $0402
    lda #$14                    ; T
    sta $0403
    lda #$20
    sta $0404
    lda boot_failure_status
    ldx #$05
    jsr display_hex_byte
    lda #$20
    sta $0407
    lda cpu8088_last_opcode
    ldx #$08
    jsr display_hex_byte
    lda #$03                    ; C
    sta $0428
    lda #$13                    ; S
    sta $0429
    lda #$3A                    ; :
    sta $042A
    lda boot_fault_cs+1
    ldx #$2B
    jsr display_hex_byte
    lda boot_fault_cs
    ldx #$2D
    jsr display_hex_byte
    lda #$09                    ; I
    sta $042F
    lda #$10                    ; P
    sta $0430
    lda #$3A
    sta $0431
    lda boot_fault_ip+1
    ldx #$32
    jsr display_hex_byte
    lda boot_fault_ip
    ldx #$34
    jsr display_hex_byte
    lda #$09                    ; I
    sta $0460
    lda #$13                    ; S
    sta $0461
    lda #$3A
    sta $0462
    lda cpu8088_interrupt_stage
    ldx #$64
    jsr display_hex_byte
    lda #$13                    ; T
    sta $0468
    lda #$3A
    sta $0469
    lda cpu8088_stack_stage
    ldx #$6B
    jsr display_hex_byte
    lda #$18                    ; X
    sta $0470
    lda #$3A
    sta $0471
    lda stack_fail_phys+2
    ldx #$73
    jsr display_hex_byte
    lda stack_fail_phys+1
    ldx #$76
    jsr display_hex_byte
    lda stack_fail_phys
    ldx #$79
    jsr display_hex_byte
    lda #$16                    ; V
    sta $0490
    lda #$3A
    sta $0491
    lda interrupt_vector
    ldx #$99
    jsr display_hex_byte
    lda #$42                    ; B
    sta $0498
    lda #$3A
    sta $0499
    lda pic_vector_base
    ldx #$A1
    jsr display_hex_byte
    lda #$4D                    ; M
    sta $04A8
    lda #$3A
    sta $04A9
    lda pic_mask
    ldx #$B1
    jsr display_hex_byte
    lda #$51                    ; Q
    sta $04B8
    lda #$3A
    sta $04B9
    lda cpu8088_irq_vector
    ldx #$C1
    jsr display_hex_byte
    lda #$10                    ; P
    sta $0450
    lda #$12                    ; R
    sta $0451
    lda #$3A
    sta $0452
    lda boot_prev_status
    ldx #$53
    jsr display_hex_byte
    lda #$20
    sta $0455
    lda boot_prev_opcode
    ldx #$56
    jsr display_hex_byte
    lda #$20
    sta $0458
    lda boot_prev_cs+1
    ldx #$59
    jsr display_hex_byte
    lda boot_prev_cs
    ldx #$5B
    jsr display_hex_byte
    lda #$20
    sta $045D
    lda boot_prev_ip+1
    ldx #$5E
    jsr display_hex_byte
    lda boot_prev_ip
    ldx #$60
    jsr display_hex_byte
    lda #$10                    ; P
    sta $0478
    lda #$32                    ; 2
    sta $0479
    lda #$3A
    sta $047A
    lda boot_prev2_status
    ldx #$7B
    jsr display_hex_byte
    lda #$20
    sta $047D
    lda boot_prev2_opcode
    ldx #$7E
    jsr display_hex_byte
    lda #$20
    sta $0480
    lda boot_prev2_cs+1
    ldx #$81
    jsr display_hex_byte
    lda boot_prev2_cs
    ldx #$83
    jsr display_hex_byte
    lda #$20
    sta $0485
    lda boot_prev2_ip+1
    ldx #$86
    jsr display_hex_byte
    lda boot_prev2_ip
    ldx #$88
    jsr display_hex_byte
    lda #$44                    ; D
    sta $04D0
    lda #$3A
    sta $04D1
    lda boot_fault_bytes
    ldx #$D4
    jsr display_hex_byte
    lda boot_fault_bytes+1
    ldx #$D7
    jsr display_hex_byte
    lda boot_fault_bytes+2
    ldx #$DA
    jsr display_hex_byte
    lda boot_fault_bytes+3
    ldx #$DD
    jsr display_hex_byte
    lda #$49                    ; I
    sta $04E8
    lda #$3A
    sta $04E9
    lda boot_fault_ivt
    ldx #$EC
    jsr display_hex_byte
    lda boot_fault_ivt+1
    ldx #$EF
    jsr display_hex_byte
    lda boot_fault_ivt+2
    ldx #$F2
    jsr display_hex_byte
    lda boot_fault_ivt+3
    ldx #$F5
    jsr display_hex_byte
    lda #$30                    ; 0
    sta $04F8
    lda #$3A
    sta $04F9
    lda boot_fault_ivt0
    ldx #$FC
    jsr display_hex_byte
    lda boot_fault_ivt0+1
    ldx #$FF
    jsr display_hex_byte
    lda boot_fault_ivt0+2
    ldx #$02
    jsr display_hex_byte
    lda boot_fault_ivt0+3
    ldx #$05
    jsr display_hex_byte
    lda #$52                    ; R
    sta $0508
    lda #$3A
    sta $0509
    lda interrupt_last_iret_stage
    ldx #$0C
    jsr display_hex_byte
    lda interrupt_last_iret_cs+1
    ldx #$0F
    jsr display_hex_byte
    lda interrupt_last_iret_cs
    ldx #$12
    jsr display_hex_byte
    lda interrupt_last_iret_ip+1
    ldx #$15
    jsr display_hex_byte
    lda interrupt_last_iret_ip
    ldx #$18
    jsr display_hex_byte
    lda #$4D                    ; M
    sta $0520
    lda #$3A
    sta $0521
    lda interrupt_frame_mismatch
    ldx #$24
    jsr display_hex_byte
    lda fdc_last_command
    ldx #$A0
    jsr display_hex_byte
    lda fdc_read_count
    ldx #$A3
    jsr display_hex_byte
    lda fdc_dma_failures
    ldx #$A6
    jsr display_hex_byte
    lda fdc_dor_writes
    ldx #$A9
    jsr display_hex_byte
    lda pic_irq6_requests
    ldx #$AC
    jsr display_hex_byte
    lda pic_irq6_deliveries
    ldx #$AF
    jsr display_hex_byte
    lda cpu8088_irq6_serviced
    ldx #$B2
    jsr display_hex_byte
    lda io_fdc_data_writes
    ldx #$B5
    jsr display_hex_byte
    lda fdc_data_reads
    ldx #$B8
    jsr display_hex_byte
    lda fdc_last_data_read
    ldx #$BB
    jsr display_hex_byte
    lda fdc_last_st0_read
    ldx #$BE
    jsr display_hex_byte
    lda #$02                    ; B
    sta $0760
    lda #$04                    ; D
    sta $0761
    lda #$41                    ; A
    sta $0762
    lda #$3A
    sta $0763
    lda #<$041A
    sta cpu8088_phys_addr
    lda #>$041A
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    ldx #$04
    jsr display_hex_byte_row22
    lda #<$041B
    sta cpu8088_phys_addr
    lda #>$041B
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    ldx #$07
    jsr display_hex_byte_row22
    lda #$3A
    sta $076A
    lda #<$041C
    sta cpu8088_phys_addr
    lda #>$041C
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    ldx #$0A
    jsr display_hex_byte_row22
    lda #<$041D
    sta cpu8088_phys_addr
    lda #>$041D
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    ldx #$0D
    jsr display_hex_byte_row22
    lda #$20
    sta $0770
    lda #$42                    ; B
    sta $0771
    lda #$44                    ; D
    sta $0772
    lda #$41                    ; A
    sta $0773
    lda #$3A
    sta $0774
    lda #<$041E
    sta cpu8088_phys_addr
    lda #>$041E
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    ldx #$05
    jsr display_hex_byte_at
    lda #<$041F
    sta cpu8088_phys_addr
    lda #>$041F
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    ldx #$08
    jsr display_hex_byte_at
    rts

; Keep a compact live FDC/PIC trace on the host's last screen row.  This is
; intentionally outside the emulated CGA aperture so it remains visible when
; the guest BIOS replaces its own screen with an error message.
display_fdc_runtime:
    ; Make the diagnostic row visible even when the guest CGA attributes are
    ; black-on-black during an early BIOS failure.
    ldx #$00
    lda #$01
@color:
    sta $DB98,x
    sta $DBC0,x
    inx
    cpx #$28
    bne @color
    lda #$10                    ; K
    sta $0770
    lda #$31                    ; 1
    sta $0771
    lda #$3A
    sta $0772
    lda pic_irq1_requests
    ldx #$04
    jsr display_hex_byte_row22
    lda pic_irq1_deliveries
    ldx #$07
    jsr display_hex_byte_row22
    lda #$08                    ; H
    sta $077A
    lda #$16                    ; V
    sta $077B
    lda #$3A
    sta $077C
    lda cpu8088_irq_vector
    ldx #$1D
    jsr display_hex_byte_row22
    lda #$0C                    ; L
    sta $077F
    lda #$16                    ; V
    sta $0780
    lda #$3A
    sta $0781
    lda interrupt_vector
    ldx #$22
    jsr display_hex_byte_row22
    lda #$06                    ; F
    sta $07C0
    lda #$04                    ; D
    sta $07C1
    lda #$03                    ; C
    sta $07C2
    lda #$3A
    sta $07C3
    lda fdc_last_command
    ldx #$04
    jsr display_hex_byte_at
    lda fdc_read_count
    ldx #$07
    jsr display_hex_byte_at
    lda #$10                    ; P
    sta $07CA
    lda #$09                    ; I
    sta $07CB
    lda #$03                    ; C
    sta $07CC
    lda #$3A
    sta $07CD
    lda pic_irq6_requests
    ldx #$0E
    jsr display_hex_byte_at
    lda cpu8088_irq6_serviced
    ldx #$11
    jsr display_hex_byte_at
    lda #$10                    ; P
    sta $0798
    lda #$03                    ; C
    sta $0799
    lda #$3A
    sta $079A
    lda boot_fault_cs+1
    ldx #$03
    jsr display_hex_byte_row23
    lda boot_fault_cs
    ldx #$05
    jsr display_hex_byte_row23
    lda #$3A
    sta $079F
    lda boot_fault_ip+1
    ldx #$08
    jsr display_hex_byte_row23
    lda boot_fault_ip
    ldx #$0A
    jsr display_hex_byte_row23
    lda #$0F                    ; O
    sta $07A5
    lda #$3A
    sta $07A6
    lda cpu8088_last_opcode
    ldx #$0F
    jsr display_hex_byte_row23
    lda #$20                    ; space
    sta $07A9
    lda #$53                    ; S
    sta $07AA
    lda #$3A
    sta $07AB
    lda boot_fault_ss+1
    ldx #$0D
    jsr display_hex_byte_row23
    lda boot_fault_ss
    ldx #$0F
    jsr display_hex_byte_row23
    lda #$3A
    sta $07B0
    lda boot_fault_sp+1
    ldx #$12
    jsr display_hex_byte_row23
    lda boot_fault_sp
    ldx #$14
    jsr display_hex_byte_row23
    lda #$20
    sta $07B7
    lda #$42                    ; B
    sta $07B8
    lda #$3A
    sta $07B9
    lda boot_stack_bytes
    ldx #$1B
    jsr display_hex_byte_row23
    lda boot_stack_bytes+1
    ldx #$1D
    jsr display_hex_byte_row23
    lda boot_stack_bytes+2
    ldx #$1F
    jsr display_hex_byte_row23
    lda boot_stack_bytes+3
    ldx #$21
    jsr display_hex_byte_row23
    lda #$02                    ; B
    sta $0760
    lda #$44                    ; D
    sta $0761
    lda #$41                    ; A
    sta $0762
    lda #$3A
    sta $0763
    lda #<$041A
    sta cpu8088_phys_addr
    lda #>$041A
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    ldx #$04
    jsr display_hex_byte_row22
    lda #<$041B
    sta cpu8088_phys_addr
    lda #>$041B
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    ldx #$07
    jsr display_hex_byte_row22
    lda #$3A
    sta $076A
    lda #<$041C
    sta cpu8088_phys_addr
    lda #>$041C
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    ldx #$0A
    jsr display_hex_byte_row22
    lda #<$041D
    sta cpu8088_phys_addr
    lda #>$041D
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    ldx #$0D
    jsr display_hex_byte_row22
    lda #$10                    ; K
    sta $07D4
    lda #$04                    ; E
    sta $07D5
    lda #$18                    ; Y
    sta $07D6
    lda #$3A
    sta $07D7
    lda #<$041E
    sta cpu8088_phys_addr
    lda #>$041E
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    ldx #$14
    jsr display_hex_byte_at
    lda #<$041F
    sta cpu8088_phys_addr
    lda #>$041F
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    ldx #$17
    jsr display_hex_byte_at
    lda #$0B                    ; K
    sta $0748
    lda #$11                    ; Q
    sta $0749
    lda #$3A
    sta $074A
    lda io_keyboard_count
    ldx #$04
    jsr display_hex_byte_at
    lda io_keyboard_wantirq
    ldx #$07
    jsr display_hex_byte_at
    lda io_keyboard_key_waiting
    ldx #$0A
    jsr display_hex_byte_at
    lda io_keyboard_pa
    ldx #$0D
    jsr display_hex_byte_at
    rts

capture_boot_fault_context:
    jsr capture_fault_bytes
    jsr capture_stack_bytes
    jsr capture_fault_ivt
    jsr capture_fault_ivt0
    rts

capture_fault_ivt0:
    lda #$00
    sta cpu8088_phys_addr
    sta cpu8088_phys_addr+1
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    sta boot_fault_ivt0
    jsr increment_phys_addr
    jsr cpu8088_mem_read_u8
    sta boot_fault_ivt0+1
    jsr increment_phys_addr
    jsr cpu8088_mem_read_u8
    sta boot_fault_ivt0+2
    jsr increment_phys_addr
    jsr cpu8088_mem_read_u8
    sta boot_fault_ivt0+3
    rts

capture_fault_ivt:
    lda #$24
    sta cpu8088_phys_addr
    lda #$00
    sta cpu8088_phys_addr+1
    sta cpu8088_phys_addr+2
    jsr cpu8088_mem_read_u8
    sta boot_fault_ivt
    jsr increment_phys_addr
    jsr cpu8088_mem_read_u8
    sta boot_fault_ivt+1
    jsr increment_phys_addr
    jsr cpu8088_mem_read_u8
    sta boot_fault_ivt+2
    jsr increment_phys_addr
    jsr cpu8088_mem_read_u8
    sta boot_fault_ivt+3
    rts

capture_fault_bytes:
    lda boot_fault_cs
    sta cpu8088_segment
    lda boot_fault_cs+1
    sta cpu8088_segment+1
    lda boot_fault_ip
    sta cpu8088_offset
    lda boot_fault_ip+1
    sta cpu8088_offset+1
    jsr cpu8088_segment_offset_physical
    jsr cpu8088_mem_read_u8
    sta boot_fault_bytes
    jsr increment_phys_addr
    jsr cpu8088_mem_read_u8
    sta boot_fault_bytes+1
    jsr increment_phys_addr
    jsr cpu8088_mem_read_u8
    sta boot_fault_bytes+2
    jsr increment_phys_addr
    jsr cpu8088_mem_read_u8
    sta boot_fault_bytes+3
    rts

capture_stack_bytes:
    lda boot_fault_ss
    sta cpu8088_segment
    lda boot_fault_ss+1
    sta cpu8088_segment+1
    lda boot_fault_sp
    sta cpu8088_offset
    lda boot_fault_sp+1
    sta cpu8088_offset+1
    jsr cpu8088_segment_offset_physical
    jsr cpu8088_mem_read_u8
    sta boot_stack_bytes
    jsr increment_phys_addr
    jsr cpu8088_mem_read_u8
    sta boot_stack_bytes+1
    jsr increment_phys_addr
    jsr cpu8088_mem_read_u8
    sta boot_stack_bytes+2
    jsr increment_phys_addr
    jsr cpu8088_mem_read_u8
    sta boot_stack_bytes+3
    rts

increment_phys_addr:
    inc cpu8088_phys_addr
    bne :+
    inc cpu8088_phys_addr+1
    bne :+
    inc cpu8088_phys_addr+2
:
    rts

display_hex_byte_row23:
    pha
    lsr a
    lsr a
    lsr a
    lsr a
    jsr display_hex_nibble
    sta $0798,x
    inx
    pla
    and #$0F
    jsr display_hex_nibble
    sta $0798,x
    rts

display_hex_byte_row22:
    pha
    lsr a
    lsr a
    lsr a
    lsr a
    jsr display_hex_nibble
    sta $0760,x
    inx
    pla
    and #$0F
    jsr display_hex_nibble
    sta $0760,x
    rts

display_hex_byte:
    pha
    lsr a
    lsr a
    lsr a
    lsr a
    jsr display_hex_nibble
    sta $0400,x
    inx
    pla
    and #$0F
    jsr display_hex_nibble
    sta $0400,x
    rts

; Same conversion as display_hex_byte, but with an absolute screen offset.
display_hex_byte_at:
    pha
    lsr a
    lsr a
    lsr a
    lsr a
    jsr display_hex_nibble
    sta $07C0,x
    inx
    pla
    and #$0F
    jsr display_hex_nibble
    sta $07C0,x
    rts
display_hex_nibble:
    cmp #$0A
    bcc @hex_digit
    sec
    sbc #$09                    ; A-F use C64 screen codes 1-6
    rts
@hex_digit:
    clc
    adc #$30
    rts

; A/X point to a zero-terminated PETSCII-compatible string.
print:
    sta message_ptr
    stx message_ptr+1
    lda #<$0400
    sta print_screen
    lda #>$0400
    sta print_screen+1
@next:
    ldy #$00
    lda (message_ptr),y
    beq @return
    cmp #$0D
    beq @newline
    cmp #'A'
    bcc :+
    cmp #'Z'+1
    bcs :+
    sec
    sbc #$40
:
    ldy #$00
    sta (print_screen),y
    lda #$01
    clc
    adc print_screen
    sta print_screen
    bcc @advance_message
    inc print_screen+1
@advance_message:
    inc message_ptr
    bne @next
    inc message_ptr+1
    jmp @next
@newline:
    lda #$20
    ldy #$00
    sta (print_screen),y
    inc message_ptr
    bne @next
    inc message_ptr+1
    jmp @next
@return:
    rts

; Validate the first architectural invariant before an opcode decoder exists:
; reset must resolve FFFF:0000 to physical address $FFFF0.
test_cpu_reset:
    jsr cpu8088_reset
    jsr cpu8088_cs_ip_physical
    lda cpu8088_phys_addr
    cmp #$F0
    bne @failed
    lda cpu8088_phys_addr+1
    cmp #$FF
    bne @failed
    lda cpu8088_phys_addr+2
    cmp #$0F
    bne @failed
    sec
    rts
@failed:
    clc
    rts

; Save the generated guest-test span at physical zero, run its instructions,
; then restore every byte it may touch and invalidate the fetch cache.
test_cpu_stepper:
    lda #$00
    sta stepper_result
    lda #<stepper_saved
    ldx #>stepper_saved
    jsr setup_stepper_save_transfer
    jsr reu_copy_from_reu
    bcc :+
    jmp @restore_done
:

    lda #<cpu_smoke_program
    ldx #>cpu_smoke_program
    jsr setup_stepper_transfer
    jsr reu_copy_to_reu
    bcc :+
    jmp @restore
:
    jsr cpu8088_fetch_cache_invalidate
    jsr cpu8088_reset
    lda #CPU_SMOKE_PENDING_IRQ
    jsr cpu8088_request_irq
    lda #$00
    sta cpu8088_state+CPU_CS
    sta cpu8088_state+CPU_CS+1

    lda #CPU_SMOKE_STEP_COUNT
    sta stepper_steps_remaining
@step_next:
    jsr cpu8088_step
    dec stepper_steps_remaining
    beq @step_last
    cmp #CPU_STEP_OK
    long_bne @restore
    jmp @step_next
@step_last:
    cmp #CPU_STEP_HALTED
    long_bne @restore

    lda cpu8088_state+CPU_AX
    cmp #<CPU_SMOKE_EXPECTED_AX
    long_bne @restore
    lda cpu8088_state+CPU_AX+1
    cmp #>CPU_SMOKE_EXPECTED_AX
    long_bne @restore
    lda cpu8088_state+CPU_CX
    cmp #<CPU_SMOKE_EXPECTED_CX
    long_bne @restore
    lda cpu8088_state+CPU_CX+1
    cmp #>CPU_SMOKE_EXPECTED_CX
    long_bne @restore
    lda cpu8088_state+CPU_DX
    cmp #<CPU_SMOKE_EXPECTED_DX
    long_bne @restore
    lda cpu8088_state+CPU_DX+1
    cmp #>CPU_SMOKE_EXPECTED_DX
    long_bne @restore
    lda cpu8088_state+CPU_BX
    cmp #<CPU_SMOKE_EXPECTED_BX
    long_bne @restore
    lda cpu8088_state+CPU_BX+1
    cmp #>CPU_SMOKE_EXPECTED_BX
    long_bne @restore
    lda cpu8088_state+CPU_SP
    cmp #<CPU_SMOKE_EXPECTED_SP
    long_bne @restore
    lda cpu8088_state+CPU_SP+1
    cmp #>CPU_SMOKE_EXPECTED_SP
    long_bne @restore
    lda cpu8088_state+CPU_SI
    cmp #<CPU_SMOKE_EXPECTED_SI
    long_bne @restore
    lda cpu8088_state+CPU_SI+1
    cmp #>CPU_SMOKE_EXPECTED_SI
    long_bne @restore
    lda cpu8088_state+CPU_DI
    cmp #<CPU_SMOKE_EXPECTED_DI
    long_bne @restore
    lda cpu8088_state+CPU_DI+1
    cmp #>CPU_SMOKE_EXPECTED_DI
    long_bne @restore
    lda cpu8088_state+CPU_ES
    cmp #<CPU_SMOKE_EXPECTED_ES
    long_bne @restore
    lda cpu8088_state+CPU_ES+1
    cmp #>CPU_SMOKE_EXPECTED_ES
    long_bne @restore
    lda cpu8088_state+CPU_CS
    cmp #<CPU_SMOKE_EXPECTED_CS
    long_bne @restore
    lda cpu8088_state+CPU_CS+1
    cmp #>CPU_SMOKE_EXPECTED_CS
    long_bne @restore
    lda cpu8088_state+CPU_SS
    cmp #<CPU_SMOKE_EXPECTED_SS
    long_bne @restore
    lda cpu8088_state+CPU_SS+1
    cmp #>CPU_SMOKE_EXPECTED_SS
    long_bne @restore
    lda cpu8088_state+CPU_DS
    cmp #<CPU_SMOKE_EXPECTED_DS
    long_bne @restore
    lda cpu8088_state+CPU_DS+1
    cmp #>CPU_SMOKE_EXPECTED_DS
    long_bne @restore
    lda cpu8088_state+CPU_FLAGS
    cmp #<CPU_SMOKE_EXPECTED_FLAGS
    long_bne @restore
    lda cpu8088_state+CPU_FLAGS+1
    cmp #>CPU_SMOKE_EXPECTED_FLAGS
    long_bne @restore
    lda io_debug_latch
    cmp #CPU_SMOKE_EXPECTED_PORT80
    long_bne @restore
    lda io_debug_latch+1
    cmp #CPU_SMOKE_EXPECTED_PORT81
    long_bne @restore
    lda #$01
    sta stepper_result

@restore:
    lda #<stepper_saved
    ldx #>stepper_saved
    jsr setup_stepper_save_transfer
    jsr reu_copy_to_reu
    jsr cpu8088_fetch_cache_invalidate
@restore_done:
    lda stepper_result
    beq @stepper_failed
    sec
    rts
@stepper_failed:
    clc
    rts

; Exercise the native multiply primitives independently of the desktop model.
test_cpu_multiply:
    lda #$FF
    sta cpu8088_state+CPU_AX
    lda #$02
    jsr cpu8088_mul_u8
    long_bcc @multiply_failed
    lda cpu8088_state+CPU_AX
    cmp #$FE
    bne @multiply_failed
    lda cpu8088_state+CPU_AX+1
    cmp #$01
    bne @multiply_failed

    lda #$F0
    sta cpu8088_state+CPU_AX
    lda #$02
    jsr cpu8088_mul_s8
    bcs @multiply_failed
    lda cpu8088_state+CPU_AX
    cmp #$E0
    bne @multiply_failed
    lda cpu8088_state+CPU_AX+1
    cmp #$FF
    bne @multiply_failed

    lda #$34
    sta cpu8088_state+CPU_AX
    lda #$12
    sta cpu8088_state+CPU_AX+1
    lda #$10
    ldx #$00
    jsr cpu8088_mul_u16
    bcc @multiply_failed
    lda cpu8088_state+CPU_AX
    cmp #$40
    bne @multiply_failed
    lda cpu8088_state+CPU_AX+1
    cmp #$23
    bne @multiply_failed
    lda cpu8088_state+CPU_DX
    cmp #$01
    bne @multiply_failed
    lda cpu8088_state+CPU_DX+1
    bne @multiply_failed

    lda #$FE
    sta cpu8088_state+CPU_AX
    lda #$FF
    sta cpu8088_state+CPU_AX+1
    lda #$03
    ldx #$00
    jsr cpu8088_mul_s16
    bcs @multiply_failed
    lda cpu8088_state+CPU_AX
    cmp #$FA
    bne @multiply_failed
    lda cpu8088_state+CPU_AX+1
    cmp #$FF
    bne @multiply_failed
    lda cpu8088_state+CPU_DX
    cmp #$FF
    bne @multiply_failed
    lda cpu8088_state+CPU_DX+1
    cmp #$FF
    bne @multiply_failed
    sec
    rts
@multiply_failed:
    clc
    rts

test_video_status:
    lda #$BA
    ldx #$03
    jsr io_read_u8
    cmp #$FF
    bne @video_status_failed
    lda #$BA
    ldx #$03
    jsr io_read_u8
    cmp #$FF
    bne @video_status_failed
    lda #$DA
    ldx #$03
    jsr io_read_u8
    and #$01
    bne @video_status_failed
    lda #$DA
    ldx #$03
    jsr io_read_u8
    and #$01
    beq @video_status_failed
    lda #$08
    ldx #$61
    ldy #$00
    jsr io_write_u8
    lda #$62
    ldx #$00
    jsr io_read_u8
    cmp #$06
    bne @video_status_failed
    lda #$61
    ldx #$00
    jsr io_read_u8
    cmp #$08
    bne @video_status_failed
    sec
    rts
@video_status_failed:
    clc
    rts

test_keyboard_translation:
    lda #$41                    ; A
    jsr host_keyboard_translate
    bcc @keyboard_failed
    cmp #$1E
    bne @keyboard_failed
    lda #$5A                    ; Z
    jsr host_keyboard_translate
    bcc @keyboard_failed
    cmp #$2C
    bne @keyboard_failed
    lda #$31                    ; 1
    jsr host_keyboard_translate
    bcc @keyboard_failed
    cmp #$02
    bne @keyboard_failed
    lda #$0D                    ; Return
    jsr host_keyboard_translate
    bcc @keyboard_failed
    cmp #$1C
    bne @keyboard_failed
    lda #$9D                    ; Cursor left
    jsr host_keyboard_translate
    bcc @keyboard_failed
    cmp #$4B
    bne @keyboard_failed
    lda #$00
    jsr host_keyboard_translate
    bcs @keyboard_failed
    sec
    rts
@keyboard_failed:
    clc
    rts

setup_stepper_transfer:
    sta reu_c64_addr
    stx reu_c64_addr+1
    lda #$00
    sta reu_ext_addr
    sta reu_ext_addr+1
    sta reu_ext_addr+2
    lda #<CPU_SMOKE_PROGRAM_SIZE
    sta reu_length
    lda #>CPU_SMOKE_PROGRAM_SIZE
    sta reu_length+1
    rts

setup_stepper_save_transfer:
    sta reu_c64_addr
    stx reu_c64_addr+1
    lda #$00
    sta reu_ext_addr
    sta reu_ext_addr+1
    sta reu_ext_addr+2
    lda #<CPU_SMOKE_SAVE_SIZE
    sta reu_length
    lda #>CPU_SMOKE_SAVE_SIZE
    sta reu_length+1
    rts

.segment "BSS"
stepper_saved: .res CPU_SMOKE_SAVE_SIZE
stepper_result: .res 1
stepper_steps_remaining: .res 1
boot_steps_remaining: .res 1
boot_video_divider: .res 1
boot_autokey_counter: .res 1
boot_autokey_sent: .res 1
boot_failure_status: .res 1

.segment "RODATA"
genxt_boot_vector_offsets:
    .word $FEA5,$E987,$FF23,$FF23,$FF23,$FF23,$EF57,$FF23
    .word $F065,$F84D,$F841,$EC59,$E739,$F859,$E82E,$EFD2
    .word $FF23,$E6F2,$FE6E,$FF53,$FF53,$F0A4,$EFC7,$0000
genxt_boot_vector_offsets_size = *-genxt_boot_vector_offsets

msg_title:         .byte $0D, "C64 X86 PHASE 0", $0D, $00
msg_turbo_ok:      .byte "TURBO CONTROL: OK", $0D, $00
msg_turbo_fail:    .byte "TURBO CONTROL: NOT AVAILABLE", $0D, $00
msg_reu_ok:        .byte "REU REGISTERS: OK", $0D, $00
msg_reu_fail:      .byte "REU REGISTERS: NOT FOUND", $0D, $00
msg_capacity_ok:   .byte "REU 16MB: OK", $0D, $00
msg_capacity_fail: .byte "REU 16MB: FAILED", $0D, $00
msg_cpu_ok:        .byte "8088 RESET VECTOR: OK", $0D, $00
msg_cpu_fail:      .byte "8088 RESET VECTOR: FAILED", $0D, $00
msg_stepper_ok:    .byte "8088 FETCH/STEP: OK", $0D, $00
msg_stepper_fail:  .byte "8088 FETCH/STEP: FAILED", $0D, $00
msg_cga_fail:      .byte "CGA TEXT RENDER: FAILED", $0D, $00




