.setcpu "6502"

.import pic_request_irq
.import dma_channel2_read_from_reu
.importzp reu_ext_addr

.export fdc_reset
.export fdc_read_main_status
.export fdc_read_data
.export fdc_read_digital_input
.export fdc_write_dor
.export fdc_write_data
.export fdc_last_command
.export fdc_read_count
.export fdc_dma_failures

FDC_IRQ = $06
MEDIA_BASE_HI = $20
SECTORS_PER_TRACK = 9
HEADS_PER_CYLINDER = 2
SECTOR_SHIFT = 9

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

.segment "BSS"
fdc_dor:            .res 1
fdc_command:        .res 1
fdc_param_index:    .res 1
fdc_expected:       .res 1
fdc_params:         .res 8
fdc_result_index:   .res 1
fdc_result_count:   .res 1
fdc_results:        .res 7
fdc_pending_st0:    .res 1
fdc_pending_cyl:    .res 1
fdc_reset_senses:   .res 1
fdc_current_cyl:    .res 1
fdc_sector_index:   .res 2
fdc_last_command:   .res 1
fdc_read_count:     .res 1
fdc_dma_failures:   .res 1

.segment "CODE"

fdc_reset:
    lda #$00
    sta fdc_dor
    sta fdc_command
    sta fdc_param_index
    sta fdc_expected
    sta fdc_result_index
    sta fdc_result_count
    sta fdc_pending_st0
    sta fdc_pending_cyl
    sta fdc_current_cyl
    sta fdc_sector_index
    sta fdc_sector_index+1
    lda #$04
    sta fdc_reset_senses
    rts

fdc_read_main_status:
    lda fdc_result_count
    beq @command_ready
    lda #$D0
    rts
@command_ready:
    lda fdc_expected
    beq :+
    lda #$90
    rts
:
    lda #$80
    rts

fdc_read_data:
    lda fdc_result_count
    beq @empty
    ldx fdc_result_index
    lda fdc_results,x
    inx
    stx fdc_result_index
    dec fdc_result_count
    bne :+
    lda #$00
    sta fdc_result_index
:
    rts
@empty:
    lda #$FF
    rts

fdc_read_digital_input:
    lda #$00
    rts

fdc_write_dor:
    pha
    eor fdc_dor
    and #$04
    beq @store_only
    pla
    pha
    and #$04
    beq @store_only
    jsr fdc_reset
    lda #FDC_IRQ
    jsr pic_request_irq
@store_only:
    pla
    sta fdc_dor
    rts

fdc_write_data:
    ldx fdc_expected
    beq @new_command
    ldx fdc_param_index
    sta fdc_params,x
    inx
    stx fdc_param_index
    cpx fdc_expected
    bne @done
    jmp fdc_process_command
@new_command:
    sta fdc_command
    sta fdc_last_command
    lda #$00
    sta fdc_param_index
    sta fdc_result_count
    sta fdc_result_index
    lda fdc_command
    and #$1F
    cmp #$03
    beq @expect_two
    cmp #$07
    beq @expect_one
    cmp #$08
    beq fdc_process_command
    cmp #$0F
    beq @expect_two
    cmp #$06
    beq @expect_eight
    cmp #$05
    beq @expect_eight
    cmp #$0A
    long_beq fdc_process_read_id
    jmp fdc_queue_invalid
@expect_one:
    lda #$01
    bne @set_expected
@expect_two:
    lda #$02
    bne @set_expected
@expect_eight:
    lda #$08
@set_expected:
    sta fdc_expected
@done:
    rts

fdc_process_command:
    lda #$00
    sta fdc_expected
    lda fdc_command
    and #$1F
    cmp #$03
    beq fdc_process_specify
    cmp #$07
    beq fdc_process_recalibrate
    cmp #$08
    beq fdc_process_sense
    cmp #$0F
    beq fdc_process_seek
    cmp #$06
    beq fdc_process_read_data
    cmp #$05
    beq fdc_process_read_data
    cmp #$0A
    long_beq fdc_process_read_id
    jmp fdc_queue_invalid

fdc_process_specify:
    rts

fdc_process_recalibrate:
    lda #$00
    sta fdc_current_cyl
    lda #$20
    sta fdc_pending_st0
    lda #$00
    sta fdc_pending_cyl
    lda #FDC_IRQ
    jmp pic_request_irq

fdc_process_seek:
    lda fdc_params+1
    sta fdc_current_cyl
    lda #$20
    sta fdc_pending_st0
    lda fdc_current_cyl
    sta fdc_pending_cyl
    lda #FDC_IRQ
    jmp pic_request_irq

fdc_process_sense:
    lda fdc_reset_senses
    beq @pending_only
    dec fdc_reset_senses
    lda fdc_reset_senses
    ora #$C0
    sta fdc_results
    lda #$00
    sta fdc_results+1
    lda #$02
    sta fdc_result_count
    lda #$00
    sta fdc_result_index
    rts
@pending_only:
    lda fdc_pending_st0
    sta fdc_results
    lda fdc_pending_cyl
    sta fdc_results+1
    lda #$00
    sta fdc_pending_st0
    sta fdc_pending_cyl
    lda #$02
    sta fdc_result_count
    lda #$00
    sta fdc_result_index
    rts

fdc_process_read_data:
    jsr fdc_compute_sector_source
    bcc :+
    inc fdc_dma_failures
    jmp fdc_queue_not_found
:
    jsr dma_channel2_read_from_reu
    bcc :+
    inc fdc_dma_failures
    jmp fdc_queue_not_found
:
    inc fdc_read_count
    lda #$20
    sta fdc_results
    lda #$00
    sta fdc_results+1
    sta fdc_results+2
    lda fdc_params+1
    sta fdc_results+3
    lda fdc_params+2
    sta fdc_results+4
    lda fdc_params+3
    sta fdc_results+5
    lda fdc_params+4
    sta fdc_results+6
    lda #$07
    sta fdc_result_count
    lda #$00
    sta fdc_result_index
    lda #FDC_IRQ
    jmp pic_request_irq

; READ ID returns the current 360 KiB drive geometry without transferring
; data.  BIOS uses this probe to verify that the selected head/media is ready.
fdc_process_read_id:
    lda #$20
    sta fdc_results
    lda #$00
    sta fdc_results+1
    sta fdc_results+2
    lda fdc_current_cyl
    sta fdc_results+3
    lda fdc_params+0
    and #$01
    sta fdc_results+4
    lda #$02
    sta fdc_results+5
    lda #$09
    sta fdc_results+6
    lda #$07
    sta fdc_result_count
    lda #$00
    sta fdc_result_index
    lda #FDC_IRQ
    jmp pic_request_irq

fdc_queue_invalid:
    lda #$80
    sta fdc_results
    lda #$00
    sta fdc_results+1
    lda #$02
    sta fdc_result_count
    lda #$00
    sta fdc_result_index
    rts

fdc_queue_not_found:
    lda #$40
    sta fdc_results
    lda #$04
    sta fdc_results+1
    lda #$00
    sta fdc_results+2
    lda fdc_params+1
    sta fdc_results+3
    lda fdc_params+2
    sta fdc_results+4
    lda fdc_params+3
    sta fdc_results+5
    lda fdc_params+4
    sta fdc_results+6
    lda #$07
    sta fdc_result_count
    lda #$00
    sta fdc_result_index
    lda #FDC_IRQ
    jmp pic_request_irq

fdc_compute_sector_source:
    lda fdc_params+4
    cmp #$02
    bne @invalid
    lda fdc_params+3
    beq @invalid
    cmp #$0A
    bcs @invalid

    lda #$00
    sta fdc_sector_index
    sta fdc_sector_index+1
    ldx fdc_params+1
@add_cyl:
    cpx #$00
    beq @after_cyl
    clc
    lda fdc_sector_index
    adc #$12
    sta fdc_sector_index
    lda fdc_sector_index+1
    adc #$00
    sta fdc_sector_index+1
    dex
    bne @add_cyl
@after_cyl:
    lda fdc_params+2
    and #$01
    beq @after_head
    clc
    lda fdc_sector_index
    adc #$09
    sta fdc_sector_index
    lda fdc_sector_index+1
    adc #$00
    sta fdc_sector_index+1
@after_head:
    sec
    lda fdc_params+3
    sbc #$01
    clc
    adc fdc_sector_index
    sta fdc_sector_index
    bcc :+
    inc fdc_sector_index+1
:
    lda #$00
    sta reu_ext_addr
    lda fdc_sector_index
    asl a
    sta reu_ext_addr+1
    lda fdc_sector_index+1
    rol a
    sta reu_ext_addr+2
    clc
    lda reu_ext_addr+2
    adc #MEDIA_BASE_HI
    sta reu_ext_addr+2
    clc
    rts
@invalid:
    sec
    rts
