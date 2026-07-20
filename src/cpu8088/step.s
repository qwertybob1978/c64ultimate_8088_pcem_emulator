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

.macro long_bne target
    beq :+
    jmp target
:
.endmacro

.segment "BSS"
cpu8088_last_opcode: .res 1
immediate_low:       .res 1
relative_high:       .res 1
modrm_byte:          .res 1
operand_width:       .res 1
source_offset:       .res 1
destination_offset:  .res 1

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
    cmp #$88                    ; MOV r/m,reg and MOV reg,r/m
    long_bcc @check_mov_imm8
    cmp #$8C
    long_bcc @mov_modrm
@check_mov_imm8:
    cmp #$B0                    ; MOV r8, imm8
    long_bcc @check_other_opcodes
    cmp #$B8
    long_bcc @mov_r8_imm8
@check_other_opcodes:
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
    cmp #$C6                    ; MOV r/m8, imm8 (/0, register form)
    long_beq @mov_rm_imm
    cmp #$C7                    ; MOV r/m16, imm16 (/0, register form)
    long_beq @mov_rm_imm

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

@mov_r8_imm8:
    sec
    sbc #$B0
    jsr @byte_register_offset
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta cpu8088_state,x
    lda #$04
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

; The first native ModR/M slice handles register-to-register MOV. Memory
; effective addresses are added with the guest data cache in the next slice.
@mov_modrm:
    and #$01
    sta operand_width
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta modrm_byte
    and #$C0
    cmp #$C0
    long_bne @invalid

    lda modrm_byte
    and #$07
    jsr @register_offset
    stx destination_offset
    lda modrm_byte
    lsr a
    lsr a
    lsr a
    and #$07
    jsr @register_offset
    stx source_offset

    lda cpu8088_last_opcode
    and #$02
    beq @copy_register
    ldx source_offset
    ldy destination_offset
    stx destination_offset
    sty source_offset
@copy_register:
    ldy source_offset
    ldx destination_offset
    lda cpu8088_state,y
    sta cpu8088_state,x
    lda operand_width
    beq @mov_modrm_done
    iny
    inx
    lda cpu8088_state,y
    sta cpu8088_state,x
@mov_modrm_done:
    lda #$02
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@mov_rm_imm:
    and #$01
    sta operand_width
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta modrm_byte
    and #$F8                    ; require mod=3 and opcode extension /0
    cmp #$C0
    long_bne @invalid
    lda modrm_byte
    and #$07
    jsr @register_offset
    stx destination_offset
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    ldx destination_offset
    sta cpu8088_state,x
    lda operand_width
    beq @mov_rm_imm_done
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    ldx destination_offset
    sta cpu8088_state+1,x
@mov_rm_imm_done:
    lda #$04
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

; Convert a ModR/M register index in A to a byte offset in cpu8088_state.
@register_offset:
    ldx operand_width
    beq @byte_register_offset
    asl a
    tax
    rts
@byte_register_offset:
    cmp #$04
    bcc @low_byte_register
    sec
    sbc #$04
    asl a
    tax
    inx
    rts
@low_byte_register:
    asl a
    tax
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
