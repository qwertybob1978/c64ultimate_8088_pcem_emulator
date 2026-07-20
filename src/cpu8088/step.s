.setcpu "6502"

.include "cpu8088/state.inc"
.include "cpu8088/core.inc"

.import cpu8088_state
.import cpu8088_halted
.import cpu8088_last_cycles
.import cpu8088_fetch_u8

.export cpu8088_step
.export cpu8088_last_opcode

.macro long_beq target
    bne :+
    jmp target
:
.endmacro

.macro long_bcs target
    bcc :+
    jmp target
:
.endmacro

.macro long_bcc target
    bcs :+
    jmp target
:
.endmacro

.segment "BSS"
cpu8088_last_opcode: .res 1
immediate_low:       .res 1
relative_high:       .res 1

.segment "CODE"

; Execute one instruction. This first decoder slice supports the control and
; immediate-register instructions needed by the native smoke test. Unsupported
; opcodes return CPU_STEP_INVALID without pretending to execute them.
cpu8088_step:
    lda cpu8088_halted
    beq @fetch
    lda #CPU_STEP_HALTED
    rts

@fetch:
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta cpu8088_last_opcode

    cmp #$90                    ; NOP
    long_beq @nop
    cmp #$F4                    ; HLT
    long_beq @hlt
    cmp #$EB                    ; JMP rel8
    long_beq @jmp_rel8
    cmp #$E9                    ; JMP rel16
    long_beq @jmp_rel16
    cmp #$F8                    ; CLC
    long_beq @clc
    cmp #$F9                    ; STC
    long_beq @stc
    cmp #$FA                    ; CLI
    long_beq @cli
    cmp #$FB                    ; STI (interrupt shadow is scheduler work)
    long_beq @sti
    cmp #$FC                    ; CLD
    long_beq @cld
    cmp #$FD                    ; STD
    long_beq @std

    cmp #$B8                    ; MOV r16, imm16
    long_bcc @invalid
    cmp #$C0
    long_bcs @invalid
    sec
    sbc #$B8
    asl a
    tax
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta immediate_low
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta cpu8088_state+1,x
    lda immediate_low
    sta cpu8088_state,x
    lda #$04
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@nop:
    lda #$03
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@hlt:
    lda #$01
    sta cpu8088_halted
    lda #$02
    sta cpu8088_last_cycles
    lda #CPU_STEP_HALTED
    rts

@jmp_rel8:
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta immediate_low
    clc
    adc cpu8088_state+CPU_IP
    sta cpu8088_state+CPU_IP
    lda immediate_low
    bpl @rel8_positive
    lda cpu8088_state+CPU_IP+1
    adc #$FF
    jmp @rel8_high_done
@rel8_positive:
    lda cpu8088_state+CPU_IP+1
    adc #$00
@rel8_high_done:
    sta cpu8088_state+CPU_IP+1
    lda #$0F
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@jmp_rel16:
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta immediate_low
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta relative_high
    clc
    lda cpu8088_state+CPU_IP
    adc immediate_low
    sta cpu8088_state+CPU_IP
    lda cpu8088_state+CPU_IP+1
    adc relative_high
    sta cpu8088_state+CPU_IP+1
    lda #$0F
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@clc:
    lda cpu8088_state+CPU_FLAGS
    and #($FF-X86_FLAG_CF)
    sta cpu8088_state+CPU_FLAGS
    jmp @flag_done
@stc:
    lda cpu8088_state+CPU_FLAGS
    ora #X86_FLAG_CF
    sta cpu8088_state+CPU_FLAGS
    jmp @flag_done
@cli:
    lda cpu8088_state+CPU_FLAGS+1
    and #($FF-X86_FLAG_IF_HI)
    sta cpu8088_state+CPU_FLAGS+1
    jmp @flag_done
@sti:
    lda cpu8088_state+CPU_FLAGS+1
    ora #X86_FLAG_IF_HI
    sta cpu8088_state+CPU_FLAGS+1
    jmp @flag_done
@cld:
    lda cpu8088_state+CPU_FLAGS+1
    and #($FF-X86_FLAG_DF_HI)
    sta cpu8088_state+CPU_FLAGS+1
    jmp @flag_done
@std:
    lda cpu8088_state+CPU_FLAGS+1
    ora #X86_FLAG_DF_HI
    sta cpu8088_state+CPU_FLAGS+1
@flag_done:
    lda #$02
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@memory_error:
    lda #$00
    sta cpu8088_last_cycles
    lda #CPU_STEP_MEMORY
    rts
@invalid:
    lda #$00
    sta cpu8088_last_cycles
    lda #CPU_STEP_INVALID
    rts
