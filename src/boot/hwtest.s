.setcpu "6502"

.import turbo_detect
.import turbo_enable_max
.import turbo_restore
.import reu_detect
.import reu_probe_16m
.import cpu8088_reset
.import cpu8088_cs_ip_physical
.importzp cpu8088_phys_addr
.import cpu8088_state
.import cpu8088_step
.import cpu8088_fetch_cache_invalidate
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

.segment "CODE"
start:
    lda #COLOR_RED
    sta BORDER_COLOR
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
    jsr test_cpu_stepper
    bcc @stepper_fail
    lda #<msg_stepper_ok
    ldx #>msg_stepper_ok
    jsr print
    lda #COLOR_GREEN
    sta BORDER_COLOR
    jmp @done
@stepper_fail:
    lda #<msg_stepper_fail
    ldx #>msg_stepper_fail
    jsr print
    jmp @done
@cpu_fail:
    lda #<msg_cpu_fail
    ldx #>msg_cpu_fail
    jsr print
    jmp @done
@capacity_fail:
    lda #<msg_capacity_fail
    ldx #>msg_capacity_fail
    jsr print
    jmp @done
@reu_fail:
    lda #<msg_reu_fail
    ldx #>msg_reu_fail
    jsr print

@done:
    jsr turbo_restore
    rts

; A/X point to a zero-terminated PETSCII-compatible string.
print:
    sta message_ptr
    stx message_ptr+1
@next:
    ldy #$00
    lda (message_ptr),y
    beq @return
    jsr CHROUT
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
    bne @restore
    jmp @step_next
@step_last:
    cmp #CPU_STEP_HALTED
    bne @restore

    lda cpu8088_state+CPU_AX
    cmp #<CPU_SMOKE_EXPECTED_AX
    bne @restore
    lda cpu8088_state+CPU_AX+1
    cmp #>CPU_SMOKE_EXPECTED_AX
    bne @restore
    lda cpu8088_state+CPU_CX
    cmp #<CPU_SMOKE_EXPECTED_CX
    bne @restore
    lda cpu8088_state+CPU_CX+1
    cmp #>CPU_SMOKE_EXPECTED_CX
    bne @restore
    lda cpu8088_state+CPU_DX
    cmp #<CPU_SMOKE_EXPECTED_DX
    bne @restore
    lda cpu8088_state+CPU_DX+1
    cmp #>CPU_SMOKE_EXPECTED_DX
    bne @restore
    lda cpu8088_state+CPU_BX
    cmp #<CPU_SMOKE_EXPECTED_BX
    bne @restore
    lda cpu8088_state+CPU_BX+1
    cmp #>CPU_SMOKE_EXPECTED_BX
    bne @restore
    lda cpu8088_state+CPU_FLAGS
    cmp #<CPU_SMOKE_EXPECTED_FLAGS
    bne @restore
    lda cpu8088_state+CPU_FLAGS+1
    cmp #>CPU_SMOKE_EXPECTED_FLAGS
    bne @restore
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

setup_stepper_transfer:
    sta reu_c64_addr
    stx reu_c64_addr+1
    lda #$00
    sta reu_ext_addr
    sta reu_ext_addr+1
    sta reu_ext_addr+2
    lda #CPU_SMOKE_PROGRAM_SIZE
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

.segment "RODATA"
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
