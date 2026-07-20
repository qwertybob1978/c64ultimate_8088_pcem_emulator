.setcpu "6502"

.include "cpu8088/state.inc"
.include "cpu8088/core.inc"

.import cpu8088_state
.import cpu8088_halted
.import cpu8088_last_cycles
.import cpu8088_fetch_u8
.import cpu8088_decode_ea
.import cpu8088_ea_next_byte
.import cpu8088_ea_recompute
.import cpu8088_ea_previous_byte
.import cpu8088_ea_rm_index
.import cpu8088_mem_read_u8
.import cpu8088_mem_write_u8
.import cpu8088_push_u16
.import cpu8088_pop_u16

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
alu_operation:       .res 1
alu_left:            .res 2
alu_right:           .res 2
alu_result:          .res 2
alu_carry:           .res 1
alu_temp:            .res 1
alu_xor_operands:    .res 1
alu_xor_result:      .res 1
alu_destination_kind:.res 1
alu_last_cycles:     .res 1
alu_preserve_cf:     .res 1
alu_saved_cf:        .res 1
condition_code:      .res 1
stack_adjust:        .res 2

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

    and #$C6                    ; AL/AX immediate ALU forms: xx00010w
    cmp #$04
    long_beq @alu_accumulator_immediate
    lda cpu8088_last_opcode

    cmp #$40
    bcc @check_push_pop
    cmp #$50
    long_bcc @inc_dec_reg16
@check_push_pop:
    cmp #$50
    bcc @check_jcc
    cmp #$60
    long_bcc @push_pop_reg16
@check_jcc:
    cmp #$70
    bcc @check_regular_dispatch
    cmp #$80
    long_bcc @jcc_rel8
@check_regular_dispatch:
    and #$C4                    ; core ALU ModR/M forms: 00ooo0dw
    cmp #$00
    long_beq @alu_modrm
    lda cpu8088_last_opcode

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
    cmp #$E8                    ; CALL rel16
    long_beq @call_rel16
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
    cmp #$C2                    ; RET imm16
    long_beq @ret_near_imm
    cmp #$C3                    ; RET
    long_beq @ret_near

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

@alu_accumulator_immediate:
    lda #$00
    sta alu_destination_kind
    sta alu_preserve_cf
    sta destination_offset      ; AX
    lda #$04
    sta alu_last_cycles
    lda cpu8088_last_opcode
    and #$01
    sta operand_width
    lda cpu8088_last_opcode
    lsr a
    lsr a
    lsr a
    and #$07
    sta alu_operation

    lda cpu8088_state+CPU_AX
    sta alu_left
    lda cpu8088_state+CPU_AX+1
    sta alu_left+1
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta alu_right
    lda #$00
    sta alu_right+1
    lda operand_width
    long_beq @alu_execute
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta alu_right+1

    jmp @alu_execute

@alu_modrm:
    lda #$00
    sta alu_preserve_cf
    lda cpu8088_last_opcode
    and #$01
    sta operand_width
    lda cpu8088_last_opcode
    lsr a
    lsr a
    lsr a
    and #$07
    sta alu_operation
    lda #$03
    sta alu_last_cycles

    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta modrm_byte
    lsr a
    lsr a
    lsr a
    and #$07
    jsr @register_offset
    stx source_offset           ; reg field
    lda modrm_byte
    jsr cpu8088_decode_ea
    cmp #$FE
    long_beq @memory_error
    cmp #$01
    beq @alu_modrm_register

    lda #$10
    sta alu_last_cycles
    lda cpu8088_last_opcode
    and #$02
    bne @alu_memory_source
    lda #$01                    ; destination is memory
    sta alu_destination_kind
    jsr @read_ea_to_left
    long_bcs @memory_error
    ldx source_offset
    jsr @read_register_to_right
    jmp @alu_execute
@alu_memory_source:
    lda #$00                    ; destination is reg field
    sta alu_destination_kind
    lda source_offset
    sta destination_offset
    ldx source_offset
    jsr @read_register_to_left
    jsr @read_ea_to_right
    long_bcs @memory_error
    jmp @alu_execute

@alu_modrm_register:
    lda #$00
    sta alu_destination_kind
    lda cpu8088_ea_rm_index
    jsr @register_offset
    stx destination_offset      ; r/m field
    lda cpu8088_last_opcode
    and #$02
    beq @alu_register_operands
    ldx source_offset
    ldy destination_offset
    stx destination_offset
    sty source_offset
@alu_register_operands:
    ldx destination_offset
    jsr @read_register_to_left
    ldx source_offset
    jsr @read_register_to_right
    jmp @alu_execute

@read_register_to_left:
    lda cpu8088_state,x
    sta alu_left
    lda #$00
    sta alu_left+1
    lda operand_width
    beq :+
    lda cpu8088_state+1,x
    sta alu_left+1
:
    rts
@read_register_to_right:
    lda cpu8088_state,x
    sta alu_right
    lda #$00
    sta alu_right+1
    lda operand_width
    beq :+
    lda cpu8088_state+1,x
    sta alu_right+1
:
    rts
@read_ea_to_left:
    jsr cpu8088_mem_read_u8
    bcs @ea_read_failed
    sta alu_left
    lda #$00
    sta alu_left+1
    lda operand_width
    beq :+
    jsr cpu8088_ea_next_byte
    jsr cpu8088_mem_read_u8
    bcs @ea_read_failed
    sta alu_left+1
    jsr cpu8088_ea_previous_byte
:
    clc
@ea_read_failed:
    rts
@read_ea_to_right:
    jsr cpu8088_mem_read_u8
    bcs @ea_read_failed
    sta alu_right
    lda #$00
    sta alu_right+1
    lda operand_width
    beq :+
    jsr cpu8088_ea_next_byte
    jsr cpu8088_mem_read_u8
    bcs @ea_read_failed
    sta alu_right+1
    jsr cpu8088_ea_previous_byte
:
    rts

@alu_execute:
    lda #$00
    sta alu_result+1
    lda alu_operation
    cmp #$01
    long_beq @alu_or
    cmp #$04
    long_beq @alu_and
    cmp #$06
    long_beq @alu_xor
    cmp #$00
    long_beq @alu_add_no_carry
    cmp #$02
    long_beq @alu_add_with_carry
    cmp #$03
    long_beq @alu_sub_with_borrow
    jmp @alu_sub_no_borrow      ; SUB and CMP

@alu_add_no_carry:
    clc
    jmp @alu_add
@alu_add_with_carry:
    lda cpu8088_state+CPU_FLAGS
    lsr a
@alu_add:
    lda alu_left
    adc alu_right
    sta alu_result
    lda operand_width
    beq @alu_save_add_carry
    lda alu_left+1
    adc alu_right+1
    sta alu_result+1
@alu_save_add_carry:
    lda #$00
    adc #$00
    sta alu_carry
    jmp @alu_flags

@alu_sub_no_borrow:
    sec
    jmp @alu_subtract
@alu_sub_with_borrow:
    lda cpu8088_state+CPU_FLAGS
    and #X86_FLAG_CF
    beq @alu_sub_no_borrow
    clc                         ; x86 CF=1 means subtract one more
@alu_subtract:
    lda alu_left
    sbc alu_right
    sta alu_result
    lda operand_width
    beq @alu_save_sub_carry
    lda alu_left+1
    sbc alu_right+1
    sta alu_result+1
@alu_save_sub_carry:
    lda #$00
    adc #$00                    ; 1 means no borrow
    eor #$01
    sta alu_carry
    jmp @alu_flags

@alu_or:
    lda alu_left
    ora alu_right
    sta alu_result
    lda operand_width
    beq @alu_logical
    lda alu_left+1
    ora alu_right+1
    sta alu_result+1
    jmp @alu_logical
@alu_and:
    lda alu_left
    and alu_right
    sta alu_result
    lda operand_width
    beq @alu_logical
    lda alu_left+1
    and alu_right+1
    sta alu_result+1
    jmp @alu_logical
@alu_xor:
    lda alu_left
    eor alu_right
    sta alu_result
    lda operand_width
    beq @alu_logical
    lda alu_left+1
    eor alu_right+1
    sta alu_result+1
@alu_logical:
    lda #$00
    sta alu_carry

@alu_flags:
    ; Preserve reserved/undefined low bits and control flags, then rebuild
    ; CF/PF/AF/ZF/SF/OF from the result.
    lda cpu8088_state+CPU_FLAGS
    and #$2A
    sta cpu8088_state+CPU_FLAGS
    lda cpu8088_state+CPU_FLAGS+1
    and #$F7
    sta cpu8088_state+CPU_FLAGS+1

    lda alu_carry
    beq @alu_no_cf
    lda cpu8088_state+CPU_FLAGS
    ora #X86_FLAG_CF
    sta cpu8088_state+CPU_FLAGS
@alu_no_cf:
    lda alu_result
    ora alu_result+1
    bne @alu_not_zero
    lda cpu8088_state+CPU_FLAGS
    ora #<X86_FLAG_ZF
    sta cpu8088_state+CPU_FLAGS
@alu_not_zero:
    lda operand_width
    beq @alu_byte_sign
    lda alu_result+1
    jmp @alu_test_sign
@alu_byte_sign:
    lda alu_result
@alu_test_sign:
    bpl @alu_no_sign
    lda cpu8088_state+CPU_FLAGS
    ora #<X86_FLAG_SF
    sta cpu8088_state+CPU_FLAGS
@alu_no_sign:
    lda alu_result
    ldx #$08
    ldy #$00
@alu_parity_loop:
    lsr a
    bcc @alu_parity_next
    iny
@alu_parity_next:
    dex
    bne @alu_parity_loop
    tya
    and #$01
    bne @alu_odd_parity
    lda cpu8088_state+CPU_FLAGS
    ora #<X86_FLAG_PF
    sta cpu8088_state+CPU_FLAGS
@alu_odd_parity:

    lda alu_operation
    cmp #$01
    beq @alu_flags_done         ; AF is undefined for logical operations
    cmp #$04
    beq @alu_flags_done
    cmp #$06
    beq @alu_flags_done
    lda alu_left
    eor alu_right
    eor alu_result
    and #$10
    beq @alu_no_aux_carry
    lda cpu8088_state+CPU_FLAGS
    ora #<X86_FLAG_AF
    sta cpu8088_state+CPU_FLAGS
@alu_no_aux_carry:

    lda operand_width
    beq @alu_overflow_byte
    lda alu_left+1
    sta alu_temp
    lda alu_right+1
    ldx alu_result+1
    jmp @alu_overflow_values
@alu_overflow_byte:
    lda alu_left
    sta alu_temp
    lda alu_right
    ldx alu_result
@alu_overflow_values:
    ; A=right sign byte, X=result sign byte, alu_temp=left sign byte.
    eor alu_temp
    sta alu_xor_operands
    txa
    eor alu_temp
    sta alu_xor_result
    lda alu_operation
    cmp #$00
    beq @alu_add_overflow
    cmp #$02
    beq @alu_add_overflow
    lda alu_xor_operands
    and alu_xor_result
    jmp @alu_test_overflow
@alu_add_overflow:
    lda alu_xor_operands
    eor #$FF
    and alu_xor_result
@alu_test_overflow:
    and #$80
    beq @alu_flags_done
    lda cpu8088_state+CPU_FLAGS+1
    ora #>X86_FLAG_OF
    sta cpu8088_state+CPU_FLAGS+1

@alu_flags_done:
    lda alu_preserve_cf
    beq @alu_store_result
    lda cpu8088_state+CPU_FLAGS
    and #($FF-X86_FLAG_CF)
    ora alu_saved_cf
    sta cpu8088_state+CPU_FLAGS
@alu_store_result:
    lda alu_operation
    cmp #$07                    ; CMP updates flags without storing
    beq @alu_accumulator_done
    lda alu_destination_kind
    bne @alu_store_memory
    ldx destination_offset
    lda alu_result
    sta cpu8088_state,x
    lda operand_width
    beq @alu_accumulator_done
    lda alu_result+1
    sta cpu8088_state+1,x
    jmp @alu_accumulator_done
@alu_store_memory:
    jsr cpu8088_ea_recompute
    lda alu_result
    jsr cpu8088_mem_write_u8
    long_bcs @memory_error
    lda operand_width
    beq @alu_accumulator_done
    jsr cpu8088_ea_next_byte
    lda alu_result+1
    jsr cpu8088_mem_write_u8
    long_bcs @memory_error
@alu_accumulator_done:
    lda alu_last_cycles
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@inc_dec_reg16:
    and #$0F
    cmp #$08
    bcc @inc_reg16
    lda #$05                    ; SUB
    bne @inc_dec_operation
@inc_reg16:
    lda #$00                    ; ADD
@inc_dec_operation:
    sta alu_operation
    lda #$01
    sta operand_width
    sta alu_preserve_cf
    lda cpu8088_state+CPU_FLAGS
    and #X86_FLAG_CF
    sta alu_saved_cf
    lda #$00
    sta alu_destination_kind
    lda cpu8088_last_opcode
    and #$07
    asl a
    sta destination_offset
    tax
    jsr @read_register_to_left
    lda #$01
    sta alu_right
    lda #$00
    sta alu_right+1
    lda #$03
    sta alu_last_cycles
    jmp @alu_execute

@push_pop_reg16:
    lda cpu8088_last_opcode
    and #$07
    asl a
    tax
    lda cpu8088_last_opcode
    and #$08
    bne @pop_reg16
    lda cpu8088_state,x
    pha
    lda cpu8088_state+1,x
    tax
    pla
    jsr cpu8088_push_u16
    long_bcs @memory_error
    lda #$0F
    bne @stack_instruction_done
@pop_reg16:
    txa
    pha
    jsr cpu8088_pop_u16
    long_bcs @memory_error
    sta immediate_low
    stx relative_high
    pla
    tax
    lda immediate_low
    sta cpu8088_state,x
    lda relative_high
    sta cpu8088_state+1,x
    lda #$0C
@stack_instruction_done:
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@call_rel16:
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta immediate_low
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta relative_high
    lda cpu8088_state+CPU_IP
    ldx cpu8088_state+CPU_IP+1
    jsr cpu8088_push_u16
    long_bcs @memory_error
    clc
    lda cpu8088_state+CPU_IP
    adc immediate_low
    sta cpu8088_state+CPU_IP
    lda cpu8088_state+CPU_IP+1
    adc relative_high
    sta cpu8088_state+CPU_IP+1
    lda #$17
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@ret_near_imm:
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta stack_adjust
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta stack_adjust+1
    jmp @ret_pop
@ret_near:
    lda #$00
    sta stack_adjust
    sta stack_adjust+1
@ret_pop:
    jsr cpu8088_pop_u16
    long_bcs @memory_error
    sta cpu8088_state+CPU_IP
    stx cpu8088_state+CPU_IP+1
    clc
    lda cpu8088_state+CPU_SP
    adc stack_adjust
    sta cpu8088_state+CPU_SP
    lda cpu8088_state+CPU_SP+1
    adc stack_adjust+1
    sta cpu8088_state+CPU_SP+1
    lda #$14
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@jcc_rel8:
    and #$0F
    sta condition_code
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta immediate_low
    lda condition_code
    jsr @condition_true
    bcc @jcc_not_taken
    clc
    lda cpu8088_state+CPU_IP
    adc immediate_low
    sta cpu8088_state+CPU_IP
    lda immediate_low
    bpl :+
    lda #$FF
    bne @jcc_add_high
:
    lda #$00
@jcc_add_high:
    adc cpu8088_state+CPU_IP+1
    sta cpu8088_state+CPU_IP+1
    lda #$10
    bne @jcc_done
@jcc_not_taken:
    lda #$04
@jcc_done:
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

@mov_modrm:
    and #$01
    sta operand_width
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta modrm_byte
    lda modrm_byte
    lsr a
    lsr a
    lsr a
    and #$07
    jsr @register_offset
    stx source_offset

    lda modrm_byte
    jsr cpu8088_decode_ea
    cmp #$FE
    long_beq @memory_error
    cmp #$01
    beq @mov_modrm_register

    lda cpu8088_last_opcode
    and #$02
    bne @mov_memory_to_register
    ldx source_offset
    lda cpu8088_state,x
    jsr cpu8088_mem_write_u8
    long_bcs @memory_error
    lda operand_width
    beq @mov_modrm_memory_done
    jsr cpu8088_ea_next_byte
    ldx source_offset
    lda cpu8088_state+1,x
    jsr cpu8088_mem_write_u8
    long_bcs @memory_error
    jmp @mov_modrm_memory_done

@mov_memory_to_register:
    jsr cpu8088_mem_read_u8
    long_bcs @memory_error
    sta immediate_low
    lda operand_width
    beq @store_memory_register_byte
    jsr cpu8088_ea_next_byte
    jsr cpu8088_mem_read_u8
    long_bcs @memory_error
    ldx source_offset
    sta cpu8088_state+1,x
@store_memory_register_byte:
    ldx source_offset
    lda immediate_low
    sta cpu8088_state,x
@mov_modrm_memory_done:
    lda #$08
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@mov_modrm_register:
    lda cpu8088_ea_rm_index
    jsr @register_offset
    stx destination_offset
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
    and #$38                    ; require opcode extension /0
    cmp #$00
    long_bne @invalid
    lda modrm_byte
    jsr cpu8088_decode_ea
    cmp #$FE
    long_beq @memory_error
    sta destination_offset      ; EA_MEMORY or EA_REGISTER
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta immediate_low
    lda operand_width
    beq @mov_rm_imm_value_ready
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta relative_high
@mov_rm_imm_value_ready:
    lda destination_offset
    beq @mov_rm_imm_memory
    lda cpu8088_ea_rm_index
    jsr @register_offset
    stx destination_offset
    lda immediate_low
    ldx destination_offset
    sta cpu8088_state,x
    lda operand_width
    beq @mov_rm_imm_done
    lda relative_high
    ldx destination_offset
    sta cpu8088_state+1,x
    jmp @mov_rm_imm_done
@mov_rm_imm_memory:
    ; Immediate fetches use cpu8088_phys_addr too, so restore the decoded
    ; effective address before touching guest data.
    jsr cpu8088_ea_recompute
    lda immediate_low
    jsr cpu8088_mem_write_u8
    long_bcs @memory_error
    lda operand_width
    beq @mov_rm_imm_done
    jsr cpu8088_ea_next_byte
    lda relative_high
    jsr cpu8088_mem_write_u8
    long_bcs @memory_error
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

; Return carry set when Jcc condition A is true.
@condition_true:
    and #$0F
    sta condition_code
    cmp #$08
    bcs @condition_high
    cmp #$04
    bcs @condition_zf_group
    cmp #$02
    bcs @condition_cf_group
    lda cpu8088_state+CPU_FLAGS+1
    and #>X86_FLAG_OF
    jmp @condition_maybe_invert
@condition_cf_group:
    lda cpu8088_state+CPU_FLAGS
    and #X86_FLAG_CF
    ldx condition_code
    cpx #$06
    bcc @condition_maybe_invert
    ora cpu8088_state+CPU_FLAGS
    and #(X86_FLAG_CF|<X86_FLAG_ZF)
    jmp @condition_maybe_invert
@condition_zf_group:
    lda cpu8088_state+CPU_FLAGS
    ldx condition_code
    cpx #$06
    bcs @condition_cf_group
    and #<X86_FLAG_ZF
    jmp @condition_maybe_invert
@condition_high:
    cmp #$0A
    bcs @condition_parity_or_signed
    lda cpu8088_state+CPU_FLAGS
    and #<X86_FLAG_SF
    jmp @condition_maybe_invert
@condition_parity_or_signed:
    cmp #$0C
    bcs @condition_signed
    lda cpu8088_state+CPU_FLAGS
    and #<X86_FLAG_PF
    jmp @condition_maybe_invert
@condition_signed:
    lda cpu8088_state+CPU_FLAGS
    and #<X86_FLAG_SF
    beq :+
    lda #$01
:
    sta alu_temp
    lda cpu8088_state+CPU_FLAGS+1
    and #>X86_FLAG_OF
    beq :+
    lda #$01
:
    eor alu_temp               ; SF != OF
    ldx condition_code
    cpx #$0E
    bcc @condition_maybe_invert
    ora cpu8088_state+CPU_FLAGS
    and #(<X86_FLAG_ZF|$01)
@condition_maybe_invert:
    pha
    lda condition_code
    and #$01
    sta alu_temp
    pla
    beq @condition_false_value
    lda #$01
@condition_false_value:
    eor alu_temp
    lsr a
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
