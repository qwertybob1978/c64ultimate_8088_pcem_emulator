.setcpu "6502"

.import cpu8088_request_irq
.import cpu8088_irq_pending

.export pic_reset
.export pic_read_command
.export pic_read_data
.export pic_write_command
.export pic_write_data
.export pic_request_irq
.export pic_service

.segment "BSS"
pic_vector_base:  .res 1
pic_mask:         .res 1
pic_pending:      .res 1
pic_in_service:   .res 1
pic_init_step:    .res 1
pic_icw1:         .res 1
pic_request_bit:  .res 1
pic_request_irqn: .res 1

.segment "CODE"

pic_reset:
    lda #$08
    sta pic_vector_base
    lda #$FF
    sta pic_mask
    lda #$00
    sta pic_pending
    sta pic_in_service
    sta pic_init_step
    rts

pic_read_command:
    lda pic_pending
    rts

pic_read_data:
    lda pic_mask
    rts

; ICW1 starts initialization. OCW2 non-specific EOI clears the currently
; serviced request; rotation and priority nesting are unnecessary for boot.
pic_write_command:
    pha
    and #$10
    beq @operation
    pla
    sta pic_icw1
    lda #$01
    sta pic_init_step
    lda #$00
    sta pic_pending
    sta pic_in_service
    rts
@operation:
    pla
    and #$20
    beq @done
    lda #$00
    sta pic_in_service
@done:
    rts

; Accept the XT BIOS ICW2/ICW3/ICW4 sequence, then treat later data writes as
; OCW1 interrupt-mask updates.
pic_write_data:
    ldx pic_init_step
    beq @mask
    cpx #$01
    bne @later_icw
    and #$F8
    sta pic_vector_base
    lda pic_icw1
    and #$02                    ; single controller skips ICW3
    beq @need_icw3
    lda pic_icw1
    and #$01
    beq @init_done
    lda #$03                    ; consume ICW4 next
    sta pic_init_step
    rts
@need_icw3:
    lda #$02
    sta pic_init_step
    rts
@init_done:
    lda #$00
    sta pic_init_step
    rts
@later_icw:
    cpx #$02
    bne @icw4
    lda pic_icw1
    and #$01
    beq @init_done
    lda #$03
    sta pic_init_step
    rts
@icw4:
    lda #$00
    sta pic_init_step
    rts
@mask:
    sta pic_mask
    jmp pic_service

; Latch IRQ A (0..7). Delivery waits until it is unmasked and the CPU IRQ latch
; is free, so timer and keyboard events cannot overwrite one another.
pic_request_irq:
    and #$07
    sta pic_request_irqn
    tax
    lda pic_irq_bits,x
    ora pic_pending
    sta pic_pending
    jmp pic_service

pic_service:
    lda cpu8088_irq_pending
    bne @nothing
    lda pic_pending
    eor #$FF
    ora pic_mask
    eor #$FF                    ; pending & ~mask
    beq @nothing
    ldx #$00
    lda #$01
@find:
    sta pic_request_bit
    bit pic_pending
    beq @next
    lda pic_request_bit
    bit pic_mask
    beq @deliver
@next:
    asl a
    inx
    cpx #$08
    bne @find
@nothing:
    rts
@deliver:
    lda pic_request_bit
    eor #$FF
    and pic_pending
    sta pic_pending
    lda pic_request_bit
    ora pic_in_service
    sta pic_in_service
    txa
    clc
    adc pic_vector_base
    jmp cpu8088_request_irq

.segment "RODATA"
pic_irq_bits:
    .byte $01,$02,$04,$08,$10,$20,$40,$80
