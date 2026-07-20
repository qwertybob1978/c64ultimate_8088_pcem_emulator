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
.import cpu8088_interrupt
.import cpu8088_iret
.import cpu8088_service_pending_interrupt
.import cpu8088_interrupt_shadow
.import cpu8088_div_u8
.import cpu8088_div_s8
.import cpu8088_div_u16
.import cpu8088_div_s16
.import io_read_u8
.import io_write_u8
.import cpu8088_segment_override
.import cpu8088_repeat_prefix
.import cpu8088_segment_offset_physical
.importzp cpu8088_segment
.importzp cpu8088_offset

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
alu_string_compare:  .res 1
alu_test_only:       .res 1
condition_code:      .res 1
stack_adjust:        .res 2
string_value:        .res 2
string_width:        .res 1
string_source_segment:.res 1
far_target:          .res 4
io_port:             .res 2
io_value:            .res 1
io_cycles:           .res 1
shift_pending:       .res 1
shift_overflow:      .res 1
shift_count:         .res 1
shift_first:         .res 1
rotate_input_carry:  .res 1

.segment "CODE"

; Execute one instruction. This first decoder slice supports the control and
; immediate-register instructions needed by the native smoke test. Unsupported
; opcodes return CPU_STEP_INVALID without pretending to execute them.
cpu8088_step:
    jsr cpu8088_service_pending_interrupt
    long_bcs @memory_error
    cmp #$01
    beq @pending_interrupt_done
    lda cpu8088_halted
    beq @begin
    lda #CPU_STEP_HALTED
    rts

@pending_interrupt_done:
    lda #$32
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@begin:
    lda #$00
    sta shift_pending
    sta alu_test_only
    lda #$FF
    sta cpu8088_segment_override
    lda #$00
    sta cpu8088_repeat_prefix
@fetch:
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta cpu8088_last_opcode

    cmp #$26                    ; ES override
    long_beq @prefix_es
    cmp #$2E                    ; CS override
    long_beq @prefix_cs
    cmp #$36                    ; SS override
    long_beq @prefix_ss
    cmp #$3E                    ; DS override
    long_beq @prefix_ds
    cmp #$F2                    ; REPNE
    long_beq @prefix_repeat
    cmp #$F3                    ; REP/REPE
    long_beq @prefix_repeat
    cmp #$F0                    ; LOCK (bus behavior is implicit on one CPU)
    beq @fetch

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
    cmp #$06
    long_beq @segment_stack
    cmp #$07
    long_beq @segment_stack
    cmp #$0E
    long_beq @segment_stack
    cmp #$16
    long_beq @segment_stack
    cmp #$17
    long_beq @segment_stack
    cmp #$1E
    long_beq @segment_stack
    cmp #$1F
    long_beq @segment_stack
    lda cpu8088_last_opcode
    cmp #$80
    bcc @not_group1_immediate
    cmp #$84
    long_bcc @alu_rm_immediate
@not_group1_immediate:
    lda cpu8088_last_opcode
    and #$C4                    ; core ALU ModR/M forms: 00ooo0dw
    cmp #$00
    long_beq @alu_modrm
    lda cpu8088_last_opcode

    cmp #$90                    ; NOP
    long_beq @nop
    cmp #$9C                    ; PUSHF
    long_beq @pushf
    cmp #$9D                    ; POPF
    long_beq @popf
    cmp #$9E                    ; SAHF
    long_beq @sahf
    cmp #$9F                    ; LAHF
    long_beq @lahf
    cmp #$9A                    ; CALL ptr16:16
    long_beq @call_far
    cmp #$A4                    ; MOVSB/MOVSW
    long_beq @string_instruction
    cmp #$A5
    long_beq @string_instruction
    cmp #$A6                    ; CMPSB/CMPSW
    long_beq @string_instruction
    cmp #$A7
    long_beq @string_instruction
    cmp #$A8                    ; TEST AL/AX, immediate
    long_beq @test_accumulator
    cmp #$A9
    long_beq @test_accumulator
    cmp #$AA                    ; STOSB/STOSW
    long_beq @string_instruction
    cmp #$AB
    long_beq @string_instruction
    cmp #$AC                    ; LODSB/LODSW
    long_beq @string_instruction
    cmp #$AD
    long_beq @string_instruction
    cmp #$AE                    ; SCASB/SCASW
    long_beq @string_instruction
    cmp #$AF
    long_beq @string_instruction
    cmp #$88                    ; MOV r/m,reg and MOV reg,r/m
    long_bcc @check_mov_imm8
    cmp #$8C
    long_bcc @mov_modrm
    cmp #$8C                    ; MOV r/m16,Sreg
    long_beq @mov_segment
    cmp #$8E                    ; MOV Sreg,r/m16
    long_beq @mov_segment
@check_mov_imm8:
    cmp #$B0                    ; MOV r8, imm8
    long_bcc @check_other_opcodes
    cmp #$B8
    long_bcc @mov_r8_imm8
@check_other_opcodes:
    cmp #$F4                    ; HLT
    long_beq @hlt
    cmp #$F5                    ; CMC
    long_beq @cmc
    cmp #$F6                    ; NOT/DIV/IDIV group 3 byte
    long_beq @group3_divide
    cmp #$F7                    ; NOT/DIV/IDIV group 3 word
    long_beq @group3_divide
    cmp #$EB                    ; JMP rel8
    long_beq @jmp_rel8
    cmp #$E9                    ; JMP rel16
    long_beq @jmp_rel16
    cmp #$EA                    ; JMP ptr16:16
    long_beq @jmp_far
    cmp #$E8                    ; CALL rel16
    long_beq @call_rel16
    cmp #$E4                    ; IN AL/AX,imm8
    long_beq @in_immediate
    cmp #$E5
    long_beq @in_immediate
    cmp #$E6                    ; OUT imm8,AL/AX
    long_beq @out_immediate
    cmp #$E7
    long_beq @out_immediate
    cmp #$EC                    ; IN AL/AX,DX
    long_beq @in_dx
    cmp #$ED
    long_beq @in_dx
    cmp #$EE                    ; OUT DX,AL/AX
    long_beq @out_dx
    cmp #$EF
    long_beq @out_dx
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
    cmp #$FE                    ; INC/DEC r/m8 group 4
    long_beq @group4_inc_dec
    cmp #$C6                    ; MOV r/m8, imm8 (/0, register form)
    long_beq @mov_rm_imm
    cmp #$C7                    ; MOV r/m16, imm16 (/0, register form)
    long_beq @mov_rm_imm
    cmp #$C4                    ; LES r16,m16:16
    long_beq @load_far_pointer
    cmp #$C5                    ; LDS r16,m16:16
    long_beq @load_far_pointer
    cmp #$86                    ; XCHG r/m8,r8
    long_beq @xchg_modrm
    cmp #$87                    ; XCHG r/m16,r16
    long_beq @xchg_modrm
    cmp #$C2                    ; RET imm16
    long_beq @ret_near_imm
    cmp #$C3                    ; RET
    long_beq @ret_near
    cmp #$CA                    ; RETF imm16
    long_beq @ret_far_imm
    cmp #$CB                    ; RETF
    long_beq @ret_far
    cmp #$CC                    ; INT3
    long_beq @int3
    cmp #$CD                    ; INT imm8
    long_beq @int_imm8
    cmp #$CE                    ; INTO
    long_beq @into
    cmp #$CF                    ; IRET
    long_beq @iret
    cmp #$D0                    ; SHL/SAL/SHR/SAR r/m8,1
    long_beq @shift_one
    cmp #$D1                    ; SHL/SAL/SHR/SAR r/m16,1
    long_beq @shift_one
    cmp #$D2                    ; SHL/SAL/SHR/SAR r/m8,CL
    long_beq @shift_one
    cmp #$D3                    ; SHL/SAL/SHR/SAR r/m16,CL
    long_beq @shift_one
    cmp #$E0                    ; LOOPNE/LOOPE/LOOP/JCXZ
    long_beq @loop_rel8
    cmp #$E1
    long_beq @loop_rel8
    cmp #$E2
    long_beq @loop_rel8
    cmp #$E3
    long_beq @loop_rel8
    cmp #$FF                    ; Group 5 indirect control flow
    long_beq @group5_control

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

@prefix_es:
    lda #CPU_ES
    bne @set_segment_prefix
@prefix_cs:
    lda #CPU_CS
    bne @set_segment_prefix
@prefix_ss:
    lda #CPU_SS
    bne @set_segment_prefix
@prefix_ds:
    lda #CPU_DS
@set_segment_prefix:
    sta cpu8088_segment_override
    jmp @fetch
@prefix_repeat:
    sta cpu8088_repeat_prefix
    jmp @fetch

@string_instruction:
    and #$01
    sta string_width
    lda cpu8088_repeat_prefix
    beq @string_once
    lda cpu8088_state+CPU_CX
    ora cpu8088_state+CPU_CX+1
    long_beq @string_done
@string_once:
@string_loop:
    lda cpu8088_last_opcode
    and #$FE
    cmp #$AA
    long_beq @string_stos
    cmp #$AC
    long_beq @string_lods
    cmp #$A6
    long_beq @string_cmps
    cmp #$AE
    long_beq @string_scas

    jsr @string_source_address
    jsr @string_read_value
    long_bcs @memory_error
    jsr @string_destination_address
    jsr @string_write_value
    long_bcs @memory_error
    jsr @string_adjust_si
    jsr @string_adjust_di
    jmp @string_repeat

@string_stos:
    lda cpu8088_state+CPU_AX
    sta string_value
    lda cpu8088_state+CPU_AX+1
    sta string_value+1
    jsr @string_destination_address
    jsr @string_write_value
    long_bcs @memory_error
    jsr @string_adjust_di
    jmp @string_repeat

@string_lods:
    jsr @string_source_address
    jsr @string_read_value
    long_bcs @memory_error
    lda string_value
    sta cpu8088_state+CPU_AX
    lda string_width
    beq :+
    lda string_value+1
    sta cpu8088_state+CPU_AX+1
:
    jsr @string_adjust_si
    jmp @string_repeat

@string_cmps:
    jsr @string_source_address
    jsr @string_read_value
    long_bcs @memory_error
    jsr @string_value_to_alu_left
    jsr @string_destination_address
    jsr @string_read_value
    long_bcs @memory_error
    jsr @string_value_to_alu_right
    jsr @string_adjust_si
    jsr @string_adjust_di
    jmp @string_compare

@string_scas:
    lda cpu8088_state+CPU_AX
    sta alu_left
    lda cpu8088_state+CPU_AX+1
    sta alu_left+1
    jsr @string_destination_address
    jsr @string_read_value
    long_bcs @memory_error
    jsr @string_value_to_alu_right
    jsr @string_adjust_di

@string_compare:
    lda #$07                    ; CMP
    sta alu_operation
    lda string_width
    sta operand_width
    lda #$00
    sta alu_preserve_cf
    lda #$01
    sta alu_string_compare
    jmp @alu_execute

@string_value_to_alu_left:
    lda string_value
    sta alu_left
    lda string_value+1
    sta alu_left+1
    rts

@string_value_to_alu_right:
    lda string_value
    sta alu_right
    lda string_value+1
    sta alu_right+1
    rts

@string_repeat:
    lda cpu8088_repeat_prefix
    beq @string_done
    sec
    lda cpu8088_state+CPU_CX
    sbc #$01
    sta cpu8088_state+CPU_CX
    lda cpu8088_state+CPU_CX+1
    sbc #$00
    sta cpu8088_state+CPU_CX+1
    ora cpu8088_state+CPU_CX
    long_bne @string_loop
    jmp @string_done

@string_compare_repeat:
    lda cpu8088_repeat_prefix
    beq @string_done
    sec
    lda cpu8088_state+CPU_CX
    sbc #$01
    sta cpu8088_state+CPU_CX
    lda cpu8088_state+CPU_CX+1
    sbc #$00
    sta cpu8088_state+CPU_CX+1
    ora cpu8088_state+CPU_CX
    beq @string_done
    lda cpu8088_state+CPU_FLAGS
    and #<X86_FLAG_ZF
    sta alu_temp
    ldx cpu8088_repeat_prefix
    cpx #$F3
    beq @string_repe
    lda alu_temp
    long_beq @string_loop       ; REPNE continues while unequal
    jmp @string_done
@string_repe:
    lda alu_temp
    long_bne @string_loop       ; REPE continues while equal
@string_done:
    lda #$12
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@string_source_address:
    ldx cpu8088_segment_override
    cpx #$FF
    bne :+
    ldx #CPU_DS
:
    stx string_source_segment
    lda cpu8088_state,x
    sta cpu8088_segment
    lda cpu8088_state+1,x
    sta cpu8088_segment+1
    lda cpu8088_state+CPU_SI
    sta cpu8088_offset
    lda cpu8088_state+CPU_SI+1
    sta cpu8088_offset+1
    jmp cpu8088_segment_offset_physical

@string_destination_address:
    lda cpu8088_state+CPU_ES
    sta cpu8088_segment
    lda cpu8088_state+CPU_ES+1
    sta cpu8088_segment+1
    lda cpu8088_state+CPU_DI
    sta cpu8088_offset
    lda cpu8088_state+CPU_DI+1
    sta cpu8088_offset+1
    jmp cpu8088_segment_offset_physical

@string_read_value:
    jsr cpu8088_mem_read_u8
    bcs @string_io_failed
    sta string_value
    lda #$00
    sta string_value+1
    lda string_width
    beq @string_io_ok
    jsr @string_next_address
    jsr cpu8088_mem_read_u8
    bcs @string_io_failed
    sta string_value+1
@string_io_ok:
    clc
@string_io_failed:
    rts

@string_write_value:
    lda string_value
    jsr cpu8088_mem_write_u8
    bcs @string_io_failed
    lda string_width
    beq @string_io_ok
    jsr @string_next_address
    lda string_value+1
    jsr cpu8088_mem_write_u8
    rts

@string_next_address:
    inc cpu8088_offset
    bne :+
    inc cpu8088_offset+1
:
    jmp cpu8088_segment_offset_physical

@string_adjust_si:
    ldx #CPU_SI
    jmp @string_adjust_index
@string_adjust_di:
    ldx #CPU_DI
@string_adjust_index:
    lda string_width
    clc
    adc #$01
    sta alu_temp
    lda cpu8088_state+CPU_FLAGS+1
    and #X86_FLAG_DF_HI
    bne @string_decrement
    clc
    lda cpu8088_state,x
    adc alu_temp
    sta cpu8088_state,x
    bcc :+
    inc cpu8088_state+1,x
:
    rts
@string_decrement:
    sec
    lda cpu8088_state,x
    sbc alu_temp
    sta cpu8088_state,x
    bcs :+
    dec cpu8088_state+1,x
:
    rts

@alu_accumulator_immediate:
    lda #$00
    sta alu_destination_kind
    sta alu_preserve_cf
    sta alu_string_compare
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
    lda alu_test_only
    beq :+
    lda #$04                    ; TEST uses AND flags without storing
    sta alu_operation
:

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

@test_accumulator:
    lda #$01
    sta alu_test_only
    jmp @alu_accumulator_immediate

@group3_divide:
    and #$01
    sta operand_width
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta modrm_byte
    lsr a
    lsr a
    lsr a
    and #$07
    cmp #$02
    beq @group3_extension_ok
    cmp #$06
    long_bcc @invalid
@group3_extension_ok:
    sta source_offset           ; group extension: 2=NOT, 6=DIV, 7=IDIV
    lda modrm_byte
    jsr cpu8088_decode_ea
    cmp #$FE
    long_beq @memory_error
    cmp #$01
    beq @group3_register
    lda #$01
    sta alu_destination_kind
    jsr cpu8088_mem_read_u8
    long_bcs @memory_error
    sta immediate_low
    lda #$00
    sta relative_high
    lda operand_width
    beq @group3_execute
    jsr cpu8088_ea_next_byte
    jsr cpu8088_mem_read_u8
    long_bcs @memory_error
    sta relative_high
    jmp @group3_execute
@group3_register:
    lda #$00
    sta alu_destination_kind
    lda cpu8088_ea_rm_index
    jsr @register_offset
    stx destination_offset
    lda cpu8088_state,x
    sta immediate_low
    lda #$00
    sta relative_high
    lda operand_width
    beq @group3_execute
    lda cpu8088_state+1,x
    sta relative_high
@group3_execute:
    lda source_offset
    cmp #$02
    beq @group3_not
    lda operand_width
    bne @group3_word
    lda immediate_low
    ldx source_offset
    cpx #$07
    beq @group3_signed_byte
    jsr cpu8088_div_u8
    jmp @group3_result
@group3_signed_byte:
    jsr cpu8088_div_s8
    jmp @group3_result
@group3_word:
    lda immediate_low
    ldx relative_high
    ldy source_offset
    cpy #$07
    beq @group3_signed_word
    jsr cpu8088_div_u16
    jmp @group3_result
@group3_signed_word:
    jsr cpu8088_div_s16
@group3_result:
    bcc @group3_success
    lda #$00
    jsr cpu8088_interrupt
    long_bcs @memory_error
@group3_success:
    lda #$50
    ldx operand_width
    beq :+
    lda #$90
:
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@group3_not:
    lda immediate_low
    eor #$FF
    sta immediate_low
    lda operand_width
    beq @group3_not_store
    lda relative_high
    eor #$FF
    sta relative_high
@group3_not_store:
    lda alu_destination_kind
    bne @group3_not_memory
    ldx destination_offset
    lda immediate_low
    sta cpu8088_state,x
    lda operand_width
    beq @group3_not_done
    lda relative_high
    sta cpu8088_state+1,x
    jmp @group3_not_done
@group3_not_memory:
    jsr cpu8088_ea_recompute
    lda immediate_low
    jsr cpu8088_mem_write_u8
    long_bcs @memory_error
    lda operand_width
    beq @group3_not_done
    jsr cpu8088_ea_next_byte
    lda relative_high
    jsr cpu8088_mem_write_u8
    long_bcs @memory_error
@group3_not_done:
    lda #$03
    ldx alu_destination_kind
    beq :+
    lda #$10
:
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@alu_modrm:
    lda #$00
    sta alu_preserve_cf
    sta alu_string_compare
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
    long_beq @alu_modrm_register

    lda #$10
    sta alu_last_cycles
    lda cpu8088_last_opcode
    and #$02
    long_bne @alu_memory_source
    lda #$01                    ; destination is memory
    sta alu_destination_kind
    jsr @read_ea_to_left
    long_bcs @memory_error
    ldx source_offset
    jsr @read_register_to_right
    jmp @alu_execute

@shift_one:
    lda #$00
    sta alu_string_compare
    lda cpu8088_last_opcode
    and #$01
    sta operand_width
    lda #$01
    sta shift_count
    lda cpu8088_last_opcode
    cmp #$D2
    bcc @shift_have_count
    lda cpu8088_state+CPU_CX
    sta shift_count
@shift_have_count:
    lda #$00
    sta shift_overflow
    sta shift_first
    lda cpu8088_state+CPU_FLAGS
    and #X86_FLAG_CF
    sta rotate_input_carry
    lda shift_count
    cmp #$01
    bne :+
    lda #$01
    sta shift_first
:
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta modrm_byte
    lsr a
    lsr a
    lsr a
    and #$07
    sta source_offset
@shift_decode:
    lda modrm_byte
    jsr cpu8088_decode_ea
    cmp #$FE
    long_beq @memory_error
    cmp #$01
    beq @shift_register
    lda #$01
    sta alu_destination_kind
    jsr @read_ea_to_left
    long_bcs @memory_error
    lda #$0F
    sta alu_last_cycles
    jmp @shift_execute
@shift_register:
    lda #$00
    sta alu_destination_kind
    lda cpu8088_ea_rm_index
    jsr @register_offset
    stx destination_offset
    jsr @read_register_to_left
    lda #$02
    sta alu_last_cycles
@shift_execute:
    lda shift_count
    long_beq @shift_noop
    lda source_offset
    cmp #$04
    long_bcc @rotate_execute
    cmp #$05
    beq @shift_right
    cmp #$07
    beq @shift_right
    lda #$00
    sta alu_result+1
    lda alu_left
    asl a
    sta alu_result
    lda operand_width
    beq @shift_save_carry
    lda alu_left+1
    rol a
    sta alu_result+1
@shift_save_carry:
    lda #$00
    adc #$00
    sta alu_carry
    lda operand_width
    beq @shift_byte_sign
    lda alu_result+1
    jmp @shift_test_sign
@shift_byte_sign:
    lda alu_result
@shift_test_sign:
    and #$80
    beq :+
    lda #$01
:
    eor alu_carry
    jsr @shift_record_overflow
    jmp @shift_finish

@shift_right:
    lda alu_left
    and #$01
    sta alu_carry
    lda operand_width
    beq @shift_right_byte
    lda alu_left+1
    lsr a
    sta alu_result+1
    lda alu_left
    ror a
    sta alu_result
    lda source_offset
    cmp #$07
    beq @shift_right_arithmetic_word
    lda alu_left+1
    jmp @shift_right_overflow
@shift_right_arithmetic_word:
    lda alu_left+1
    and #$80
    ora alu_result+1
    sta alu_result+1
    lda #$00
    beq @shift_right_overflow
@shift_right_byte:
    lda alu_left
    lsr a
    sta alu_result
    lda #$00
    sta alu_result+1
    lda source_offset
    cmp #$07
    beq @shift_right_arithmetic_byte
    lda alu_left
    jmp @shift_right_overflow
@shift_right_arithmetic_byte:
    lda alu_left
    and #$80
    ora alu_result
    sta alu_result
    lda #$00
@shift_right_overflow:
    and #$80
    beq :+
    lda #$01
:
    jsr @shift_record_overflow
@shift_finish:
    dec shift_count
    beq @shift_flags
    lda alu_result
    sta alu_left
    lda alu_result+1
    sta alu_left+1
    jmp @shift_execute
@shift_flags:
    lda source_offset
    cmp #$04
    long_bcc @rotate_flags
    lda #$01
    sta shift_pending
    lda #$04                    ; logical flag path; result already computed
    sta alu_operation
    lda #$00
    sta alu_preserve_cf
    jmp @alu_flags

@rotate_execute:
    lda source_offset
    cmp #$02
    bcc @rotate_plain
    jmp @rotate_through_carry

@rotate_plain:
    cmp #$01
    beq @rotate_right_plain
    lda #$00
    sta alu_result+1
    lda alu_left
    asl a
    sta alu_result
    lda operand_width
    beq :+
    lda alu_left+1
    rol a
    sta alu_result+1
:
    lda #$00
    adc #$00
    sta alu_carry
    bne :+
    jmp @rotate_left_overflow
:
    lda alu_result
    ora #$01
    sta alu_result
    jmp @rotate_left_overflow

@rotate_right_plain:
    lda alu_left
    and #$01
    sta alu_carry
    lda operand_width
    beq @rotate_right_plain_byte
    lda alu_left+1
    lsr a
    sta alu_result+1
    lda alu_left
    ror a
    sta alu_result
    lda alu_carry
    bne :+
    jmp @rotate_right_overflow
:
    lda alu_result+1
    ora #$80
    sta alu_result+1
    jmp @rotate_right_overflow
@rotate_right_plain_byte:
    lda alu_left
    lsr a
    sta alu_result
    lda #$00
    sta alu_result+1
    lda alu_carry
    bne :+
    jmp @rotate_right_overflow
:
    lda alu_result
    ora #$80
    sta alu_result
    jmp @rotate_right_overflow

@rotate_through_carry:
    lda source_offset
    cmp #$03
    beq @rotate_right_carry
    lda #$00
    sta alu_result+1
    lda alu_left
    asl a
    sta alu_result
    lda operand_width
    beq :+
    lda alu_left+1
    rol a
    sta alu_result+1
:
    lda #$00
    adc #$00
    sta alu_carry
    lda rotate_input_carry
    beq @rotate_left_overflow
    lda alu_result
    ora #$01
    sta alu_result
    jmp @rotate_left_overflow

@rotate_right_carry:
    lda alu_left
    and #$01
    sta alu_carry
    lda operand_width
    beq @rotate_right_carry_byte
    lda alu_left+1
    lsr a
    sta alu_result+1
    lda alu_left
    ror a
    sta alu_result
    lda rotate_input_carry
    beq @rotate_right_overflow
    lda alu_result+1
    ora #$80
    sta alu_result+1
    jmp @rotate_right_overflow
@rotate_right_carry_byte:
    lda alu_left
    lsr a
    sta alu_result
    lda #$00
    sta alu_result+1
    lda rotate_input_carry
    beq @rotate_right_overflow
    lda alu_result
    ora #$80
    sta alu_result
    jmp @rotate_right_overflow

@rotate_left_overflow:
    lda operand_width
    beq :+
    lda alu_result+1
    jmp :++
:
    lda alu_result
:
    and #$80
    beq :+
    lda #$01
:
    eor alu_carry
    jsr @shift_record_overflow
    jmp @rotate_finish

@rotate_right_overflow:
    lda operand_width
    beq :+
    lda alu_result+1
    jmp :++
:
    lda alu_result
:
    sta alu_temp
    asl a
    eor alu_temp
    and #$80
    jsr @shift_record_overflow
@rotate_finish:
    lda alu_carry
    sta rotate_input_carry
    jmp @shift_finish

@rotate_flags:
    lda cpu8088_state+CPU_FLAGS
    and #$FE
    ora alu_carry
    sta cpu8088_state+CPU_FLAGS
    lda cpu8088_state+CPU_FLAGS+1
    and #$F7
    ldx shift_overflow
    beq :+
    ora #>X86_FLAG_OF
:
    sta cpu8088_state+CPU_FLAGS+1
    jmp @alu_store_result

@shift_record_overflow:
    ldx shift_first
    beq :+
    sta shift_overflow
    ldx #$00
    stx shift_first
:
    rts

@shift_noop:
    lda #$08
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@alu_rm_immediate:
    lda #$00
    sta alu_preserve_cf
    sta alu_string_compare
    lda cpu8088_last_opcode
    and #$01
    sta operand_width
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta modrm_byte
    lsr a
    lsr a
    lsr a
    and #$07
    sta alu_operation
    lda modrm_byte
    jsr cpu8088_decode_ea
    cmp #$FE
    long_beq @memory_error
    cmp #$01
    beq @alu_rm_imm_register
    lda #$01
    sta alu_destination_kind
    jsr @read_ea_to_left
    long_bcs @memory_error
    lda #$11
    sta alu_last_cycles
    jmp @alu_rm_imm_fetch
@alu_rm_imm_register:
    lda #$00
    sta alu_destination_kind
    lda cpu8088_ea_rm_index
    jsr @register_offset
    stx destination_offset
    jsr @read_register_to_left
    lda #$04
    sta alu_last_cycles
@alu_rm_imm_fetch:
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta alu_right
    lda #$00
    sta alu_right+1
    lda operand_width
    long_beq @alu_execute
    lda cpu8088_last_opcode
    cmp #$83
    beq @alu_rm_imm_sign_extend
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta alu_right+1
    jmp @alu_execute
@alu_rm_imm_sign_extend:
    lda alu_right
    bpl :+
    lda #$FF
    sta alu_right+1
:
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
    lda shift_pending
    beq @alu_preserve_carry
    lda shift_overflow
    beq @alu_preserve_carry
    lda cpu8088_state+CPU_FLAGS+1
    ora #>X86_FLAG_OF
    sta cpu8088_state+CPU_FLAGS+1
@alu_preserve_carry:
    lda alu_preserve_cf
    beq @alu_store_result
    lda cpu8088_state+CPU_FLAGS
    and #($FF-X86_FLAG_CF)
    ora alu_saved_cf
    sta cpu8088_state+CPU_FLAGS
@alu_store_result:
    lda alu_string_compare
    long_bne @string_compare_repeat
    lda alu_test_only
    long_bne @alu_accumulator_done
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
    lda #$00
    sta alu_string_compare
    lda cpu8088_last_opcode
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

@group4_inc_dec:
    lda #$00
    sta operand_width
    sta alu_string_compare
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta modrm_byte
    lsr a
    lsr a
    lsr a
    and #$07
    cmp #$02
    long_bcs @invalid
    cmp #$00
    beq @group4_inc
    lda #$05                    ; SUB
    bne @group4_operation
@group4_inc:
    lda #$00                    ; ADD
@group4_operation:
    sta alu_operation
    lda #$01
    sta alu_preserve_cf
    lda cpu8088_state+CPU_FLAGS
    and #X86_FLAG_CF
    sta alu_saved_cf
    lda modrm_byte
    jsr cpu8088_decode_ea
    cmp #$FE
    long_beq @memory_error
    cmp #$01
    beq @group4_register
    lda #$01
    sta alu_destination_kind
    jsr @read_ea_to_left
    long_bcs @memory_error
    lda #$0F
    sta alu_last_cycles
    jmp @group4_execute
@group4_register:
    lda #$00
    sta alu_destination_kind
    lda cpu8088_ea_rm_index
    jsr @register_offset
    stx destination_offset
    jsr @read_register_to_left
    lda #$03
    sta alu_last_cycles
@group4_execute:
    lda #$01
    sta alu_right
    lda #$00
    sta alu_right+1
    jmp @alu_execute

@group5_control:
    lda #$01
    sta operand_width
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta modrm_byte
    lsr a
    lsr a
    lsr a
    and #$07
    cmp #$02
    beq @group5_extension_ok
    cmp #$04
    long_bne @invalid
@group5_extension_ok:
    sta source_offset
    lda modrm_byte
    jsr cpu8088_decode_ea
    cmp #$FE
    long_beq @memory_error
    cmp #$01
    beq @group5_register
    lda #$01
    sta alu_destination_kind
    jsr @read_ea_to_left
    long_bcs @memory_error
    jmp @group5_execute
@group5_register:
    lda #$00
    sta alu_destination_kind
    lda cpu8088_ea_rm_index
    jsr @register_offset
    jsr @read_register_to_left
@group5_execute:
    lda source_offset
    cmp #$02
    bne @group5_install_ip
    lda cpu8088_state+CPU_IP
    ldx cpu8088_state+CPU_IP+1
    jsr cpu8088_push_u16
    long_bcs @memory_error
@group5_install_ip:
    lda alu_left
    sta cpu8088_state+CPU_IP
    lda alu_left+1
    sta cpu8088_state+CPU_IP+1
    lda source_offset
    cmp #$02
    bne @group5_jump_cycles
    lda #$10
    ldx alu_destination_kind
    beq @group5_done
    lda #$15
    bne @group5_done
@group5_jump_cycles:
    lda #$0B
    ldx alu_destination_kind
    beq @group5_done
    lda #$12
@group5_done:
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@load_far_pointer:
    lda #$01
    sta operand_width
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta modrm_byte
    lsr a
    lsr a
    lsr a
    and #$07
    jsr @register_offset
    stx destination_offset
    lda modrm_byte
    jsr cpu8088_decode_ea
    cmp #$FE
    long_beq @memory_error
    cmp #$01
    long_beq @invalid           ; LES/LDS require a memory pointer
    ldx #$00
@load_far_pointer_byte:
    jsr cpu8088_mem_read_u8
    long_bcs @memory_error
    sta far_target,x
    inx
    cpx #$04
    beq @load_far_pointer_commit
    jsr cpu8088_ea_next_byte
    jmp @load_far_pointer_byte
@load_far_pointer_commit:
    ldx destination_offset
    lda far_target
    sta cpu8088_state,x
    lda far_target+1
    sta cpu8088_state+1,x
    ldx #CPU_ES
    lda cpu8088_last_opcode
    cmp #$C4
    beq :+
    ldx #CPU_DS
:
    lda far_target+2
    sta cpu8088_state,x
    lda far_target+3
    sta cpu8088_state+1,x
    lda #$10
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@xchg_modrm:
    and #$01
    sta operand_width
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta modrm_byte
    lsr a
    lsr a
    lsr a
    and #$07
    jsr @register_offset
    stx source_offset
    jsr @read_register_to_right
    lda modrm_byte
    jsr cpu8088_decode_ea
    cmp #$FE
    long_beq @memory_error
    cmp #$01
    beq @xchg_register
    lda #$01
    sta alu_destination_kind
    jsr @read_ea_to_left
    long_bcs @memory_error
    jsr cpu8088_ea_recompute
    lda alu_right
    jsr cpu8088_mem_write_u8
    long_bcs @memory_error
    lda operand_width
    beq @xchg_store_source
    jsr cpu8088_ea_next_byte
    lda alu_right+1
    jsr cpu8088_mem_write_u8
    long_bcs @memory_error
    jmp @xchg_store_source
@xchg_register:
    lda #$00
    sta alu_destination_kind
    lda cpu8088_ea_rm_index
    jsr @register_offset
    stx destination_offset
    jsr @read_register_to_left
    ldx destination_offset
    lda alu_right
    sta cpu8088_state,x
    lda operand_width
    beq @xchg_store_source
    lda alu_right+1
    sta cpu8088_state+1,x
@xchg_store_source:
    ldx source_offset
    lda alu_left
    sta cpu8088_state,x
    lda operand_width
    beq @xchg_done
    lda alu_left+1
    sta cpu8088_state+1,x
@xchg_done:
    lda #$04
    ldx alu_destination_kind
    beq :+
    lda #$11
:
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

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

@segment_stack:
    lda cpu8088_last_opcode
    and #$18
    lsr a
    lsr a
    clc
    adc #CPU_ES
    tax
    lda cpu8088_last_opcode
    and #$01
    bne @segment_pop
    lda cpu8088_state,x
    pha
    lda cpu8088_state+1,x
    tax
    pla
    jsr cpu8088_push_u16
    long_bcs @memory_error
    lda #$0E
    bne @segment_stack_done
@segment_pop:
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
    cpx #CPU_SS
    bne :+
    lda #$01
    sta cpu8088_interrupt_shadow
:
    lda #$0C
@segment_stack_done:
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@pushf:
    lda cpu8088_state+CPU_FLAGS
    ldx cpu8088_state+CPU_FLAGS+1
    txa
    ora #$F0
    tax
    lda cpu8088_state+CPU_FLAGS
    jsr cpu8088_push_u16
    long_bcs @memory_error
    lda #$0E
    bne @flags_transfer_done
@popf:
    jsr cpu8088_pop_u16
    long_bcs @memory_error
    ora #$02
    sta cpu8088_state+CPU_FLAGS
    txa
    and #$0F
    sta cpu8088_state+CPU_FLAGS+1
    lda #$0C
    bne @flags_transfer_done
@sahf:
    lda cpu8088_state+CPU_FLAGS
    and #$2A
    sta immediate_low
    lda cpu8088_state+CPU_AX+1
    and #$D5
    ora immediate_low
    ora #$02
    sta cpu8088_state+CPU_FLAGS
    lda #$04
    bne @flags_transfer_done
@lahf:
    lda cpu8088_state+CPU_FLAGS
    sta cpu8088_state+CPU_AX+1
    lda #$04
@flags_transfer_done:
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

@call_far:
    jsr @fetch_far_target
    long_bcs @memory_error
    lda cpu8088_state+CPU_CS
    ldx cpu8088_state+CPU_CS+1
    jsr cpu8088_push_u16
    long_bcs @memory_error
    lda cpu8088_state+CPU_IP
    ldx cpu8088_state+CPU_IP+1
    jsr cpu8088_push_u16
    long_bcs @memory_error
    jsr @install_far_target
    lda #$1C
    bne @far_control_done
@jmp_far:
    jsr @fetch_far_target
    long_bcs @memory_error
    jsr @install_far_target
    lda #$0F
@far_control_done:
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@in_immediate:
    jsr @io_immediate_port
    long_bcs @memory_error
    jmp @io_read_accumulator
@in_dx:
    jsr @io_dx_port
@io_read_accumulator:
    lda io_port
    ldx io_port+1
    jsr io_read_u8
    sta cpu8088_state+CPU_AX
    lda cpu8088_last_opcode
    and #$01
    beq @io_done
    jsr @io_next_port
    lda io_port
    ldx io_port+1
    jsr io_read_u8
    sta cpu8088_state+CPU_AX+1
    jmp @io_done

@out_immediate:
    jsr @io_immediate_port
    long_bcs @memory_error
    jmp @io_write_accumulator
@out_dx:
    jsr @io_dx_port
@io_write_accumulator:
    lda cpu8088_state+CPU_AX
    sta io_value
    ldx io_port
    ldy io_port+1
    jsr io_write_u8
    lda cpu8088_last_opcode
    and #$01
    beq @io_done
    jsr @io_next_port
    lda cpu8088_state+CPU_AX+1
    sta io_value
    ldx io_port
    ldy io_port+1
    jsr io_write_u8
@io_done:
    lda io_cycles
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@io_immediate_port:
    jsr cpu8088_fetch_u8
    bcs @io_port_failed
    sta io_port
    lda #$00
    sta io_port+1
    lda #$0A
    sta io_cycles
    clc
@io_port_failed:
    rts
@io_dx_port:
    lda cpu8088_state+CPU_DX
    sta io_port
    lda cpu8088_state+CPU_DX+1
    sta io_port+1
    lda #$08
    sta io_cycles
    rts
@io_next_port:
    inc io_port
    bne :+
    inc io_port+1
:
    rts

@fetch_far_target:
    ldx #$00
@fetch_far_byte:
    jsr cpu8088_fetch_u8
    bcs @fetch_far_failed
    sta far_target,x
    inx
    cpx #$04
    bne @fetch_far_byte
    clc
@fetch_far_failed:
    rts

@install_far_target:
    lda far_target
    sta cpu8088_state+CPU_IP
    lda far_target+1
    sta cpu8088_state+CPU_IP+1
    lda far_target+2
    sta cpu8088_state+CPU_CS
    lda far_target+3
    sta cpu8088_state+CPU_CS+1
    rts

@ret_near_imm:
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta stack_adjust
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta stack_adjust+1
    jmp @ret_pop

@ret_far_imm:
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta stack_adjust
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta stack_adjust+1
    jmp @ret_far_pop
@ret_far:
    lda #$00
    sta stack_adjust
    sta stack_adjust+1
@ret_far_pop:
    jsr cpu8088_pop_u16
    long_bcs @memory_error
    sta far_target
    stx far_target+1
    jsr cpu8088_pop_u16
    long_bcs @memory_error
    sta far_target+2
    stx far_target+3
    jsr @install_far_target
    clc
    lda cpu8088_state+CPU_SP
    adc stack_adjust
    sta cpu8088_state+CPU_SP
    lda cpu8088_state+CPU_SP+1
    adc stack_adjust+1
    sta cpu8088_state+CPU_SP+1
    lda #$22
    ldx cpu8088_last_opcode
    cpx #$CA
    bne :+
    lda #$21
:
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts

@int3:
    lda #$03
    bne @interrupt_vector
@int_imm8:
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
@interrupt_vector:
    jsr cpu8088_interrupt
    long_bcs @memory_error
    lda #$47
    ldx cpu8088_last_opcode
    cpx #$CC
    bne @interrupt_done
    lda #$48
    bne @interrupt_done
@into:
    lda cpu8088_state+CPU_FLAGS+1
    and #>X86_FLAG_OF
    beq @into_not_taken
    lda #$04
    jsr cpu8088_interrupt
    long_bcs @memory_error
    lda #$49
    bne @interrupt_done
@into_not_taken:
    lda #$04
    bne @interrupt_done
@iret:
    jsr cpu8088_iret
    long_bcs @memory_error
    lda #$2C
@interrupt_done:
    sta cpu8088_last_cycles
    lda #CPU_STEP_OK
    rts
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

@loop_rel8:
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta immediate_low
    lda cpu8088_last_opcode
    cmp #$E3
    beq @jcxz_test
    lda cpu8088_state+CPU_CX
    bne :+
    dec cpu8088_state+CPU_CX+1
:
    dec cpu8088_state+CPU_CX
    lda cpu8088_state+CPU_CX
    ora cpu8088_state+CPU_CX+1
    beq @loop_not_taken
    lda cpu8088_last_opcode
    cmp #$E2
    beq @loop_taken
    lda cpu8088_state+CPU_FLAGS
    and #<X86_FLAG_ZF
    ldx cpu8088_last_opcode
    cpx #$E1
    beq @loope_test
    cmp #$00                    ; LOOPNE requires ZF clear
    beq @loop_taken
    bne @loop_not_taken
@loope_test:
    cmp #$00                    ; LOOPE requires ZF set
    bne @loop_taken
    beq @loop_not_taken
@jcxz_test:
    lda cpu8088_state+CPU_CX
    ora cpu8088_state+CPU_CX+1
    bne @loop_not_taken
@loop_taken:
    clc
    lda cpu8088_state+CPU_IP
    adc immediate_low
    sta cpu8088_state+CPU_IP
    lda immediate_low
    bpl :+
    lda #$FF
    bne @loop_add_high
:
    lda #$00
@loop_add_high:
    adc cpu8088_state+CPU_IP+1
    sta cpu8088_state+CPU_IP+1
    lda #$12
    bne @loop_done
@loop_not_taken:
    lda #$05
@loop_done:
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

@mov_segment:
    lda #$01
    sta operand_width
    jsr cpu8088_fetch_u8
    long_bcs @memory_error
    sta modrm_byte
    lsr a
    lsr a
    lsr a
    and #$07
    cmp #$04
    long_bcs @invalid
    cmp #$01
    bne @segment_index_ready
    lda cpu8088_last_opcode
    cmp #$8E
    long_beq @invalid           ; MOV CS,r/m16 is not encodable
    lda #$01
@segment_index_ready:
    asl a
    clc
    adc #CPU_ES
    sta source_offset
    lda modrm_byte
    jsr cpu8088_decode_ea
    cmp #$FE
    long_beq @memory_error
    cmp #$01
    beq @mov_segment_register
    lda cpu8088_last_opcode
    cmp #$8E
    beq @load_segment_memory
    ldx source_offset
    lda cpu8088_state,x
    jsr cpu8088_mem_write_u8
    long_bcs @memory_error
    jsr cpu8088_ea_next_byte
    ldx source_offset
    lda cpu8088_state+1,x
    jsr cpu8088_mem_write_u8
    long_bcs @memory_error
    jmp @mov_segment_done
@load_segment_memory:
    jsr cpu8088_mem_read_u8
    long_bcs @memory_error
    sta immediate_low
    jsr cpu8088_ea_next_byte
    jsr cpu8088_mem_read_u8
    long_bcs @memory_error
    ldx source_offset
    sta cpu8088_state+1,x
    lda immediate_low
    sta cpu8088_state,x
    jmp @mov_segment_shadow
@mov_segment_register:
    lda cpu8088_ea_rm_index
    jsr @register_offset
    ldy source_offset
    lda cpu8088_last_opcode
    cmp #$8E
    beq @load_segment_register
    lda cpu8088_state,y
    sta cpu8088_state,x
    lda cpu8088_state+1,y
    sta cpu8088_state+1,x
    jmp @mov_segment_done
@load_segment_register:
    lda cpu8088_state,x
    sta cpu8088_state,y
    lda cpu8088_state+1,x
    sta cpu8088_state+1,y
@mov_segment_shadow:
    ldx source_offset
    cpx #CPU_SS
    bne @mov_segment_done
    lda #$01
    sta cpu8088_interrupt_shadow
@mov_segment_done:
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
@cmc:
    lda cpu8088_state+CPU_FLAGS
    eor #X86_FLAG_CF
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
    lda #$01
    sta cpu8088_interrupt_shadow
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
