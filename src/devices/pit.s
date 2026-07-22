.setcpu "6502"

.import pic_request_irq

.export pit_reset
.export pit_read_u8
.export pit_write_u8
.export pit_advance_cycles

.segment "BSS"
pit_reload_lo:     .res 3
pit_reload_hi:     .res 3
pit_count_lo:      .res 3
pit_count_hi:      .res 3
pit_access:        .res 3
pit_mode:          .res 3
pit_write_phase:   .res 3
pit_read_phase:    .res 3
pit_latched_lo:    .res 3
pit_latched_hi:    .res 3
pit_latched:       .res 3
pit_running:       .res 3
pit_cycle_accum:   .res 1
pit_data_value:    .res 1
pit_channel_index: .res 1

.segment "CODE"

pit_reset:
    lda #$00
    ldx #$02
@clear:
    sta pit_reload_lo,x
    sta pit_reload_hi,x
    sta pit_count_lo,x
    sta pit_count_hi,x
    sta pit_access,x
    sta pit_mode,x
    sta pit_write_phase,x
    sta pit_read_phase,x
    sta pit_latched_lo,x
    sta pit_latched_hi,x
    sta pit_latched,x
    sta pit_running,x
    dex
    bpl @clear
    sta pit_cycle_accum
    rts

pit_read_u8:
    cpx #$03
    beq @read_control
    stx pit_channel_index
    lda pit_latched,x
    beq @live_count
    lda pit_access,x
    cmp #$03
    bne @read_latched_single
    lda pit_read_phase,x
    beq @read_latched_low
    lda #$00
    sta pit_latched,x
    lda pit_latched_hi,x
    rts
@read_latched_low:
    lda #$01
    sta pit_read_phase,x
    lda pit_latched_lo,x
    rts
@read_latched_single:
    cmp #$02
    beq @read_latched_hi_only
    lda #$00
    sta pit_latched,x
    lda pit_latched_lo,x
    rts
@read_latched_hi_only:
    lda #$00
    sta pit_latched,x
    lda pit_latched_hi,x
    rts

@live_count:
    lda pit_access,x
    cmp #$02
    beq @read_live_hi
    cmp #$03
    beq @read_live_pair
    lda pit_count_lo,x
    rts
@read_live_hi:
    lda pit_count_hi,x
    rts
@read_live_pair:
    lda pit_read_phase,x
    beq @read_live_low
    lda #$00
    sta pit_read_phase,x
    lda pit_count_hi,x
    rts
@read_live_low:
    lda #$01
    sta pit_read_phase,x
    lda pit_count_lo,x
    rts

@read_control:
    lda #$00
    rts

pit_write_u8:
    cpx #$03
    beq @write_control
    sta pit_data_value
    stx pit_channel_index
    lda pit_access,x
    cmp #$02
    beq @write_high_only
    cmp #$03
    beq @write_pair
    lda pit_data_value
    sta pit_reload_lo,x
    lda #$00
    sta pit_reload_hi,x
    jmp pit_load_channel
@write_high_only:
    lda pit_data_value
    sta pit_reload_hi,x
    lda #$00
    sta pit_reload_lo,x
    jmp pit_load_channel
@write_pair:
    lda pit_write_phase,x
    beq @write_pair_low
    lda pit_data_value
    sta pit_reload_hi,x
    lda #$00
    sta pit_write_phase,x
    jmp pit_load_channel
@write_pair_low:
    lda pit_data_value
    sta pit_reload_lo,x
    lda #$01
    sta pit_write_phase,x
    rts

@write_control:
    sta pit_data_value
    lda pit_data_value
    lsr a
    lsr a
    lsr a
    lsr a
    lsr a
    lsr a
    tax
    cpx #$03
    bcs @done
    stx pit_channel_index
    lda pit_data_value
    lsr a
    lsr a
    lsr a
    lsr a
    and #$03
    beq @latch_count
    ldx pit_channel_index
    sta pit_access,x
    lda #$00
    sta pit_write_phase,x
    sta pit_read_phase,x
    lda pit_data_value
    lsr a
    and #$07
    cmp #$06
    bcc :+
    and #$03
:
    sta pit_mode,x
@done:
    rts

@latch_count:
    ldx pit_channel_index
    lda pit_count_lo,x
    sta pit_latched_lo,x
    lda pit_count_hi,x
    sta pit_latched_hi,x
    lda #$01
    sta pit_latched,x
    lda #$00
    sta pit_read_phase,x
    rts

pit_load_channel:
    ldx pit_channel_index
    lda pit_reload_lo,x
    sta pit_count_lo,x
    lda pit_reload_hi,x
    sta pit_count_hi,x
    lda #$01
    sta pit_running,x
    lda #$00
    sta pit_latched,x
    sta pit_read_phase,x
    rts

pit_advance_cycles:
    clc
    adc pit_cycle_accum
    sta pit_cycle_accum
@tick_ready:
    lda pit_cycle_accum
    cmp #$04
    bcc @done
    sec
    sbc #$04
    sta pit_cycle_accum
    ldx #$00
@tick_channel:
    lda pit_running,x
    beq @next_channel
    jsr pit_tick_channel
@next_channel:
    inx
    cpx #$03
    bne @tick_channel
    jmp @tick_ready
@done:
    rts

pit_tick_channel:
    dec pit_count_lo,x
    lda pit_count_lo,x
    cmp #$FF
    bne @check_zero
    dec pit_count_hi,x
@check_zero:
    lda pit_count_lo,x
    ora pit_count_hi,x
    bne @tick_done
    cpx #$00
    bne @reload_or_stop
    lda #$00
    jsr pic_request_irq
@reload_or_stop:
    lda pit_mode,x
    cmp #$02
    beq @reload
    cmp #$03
    beq @reload
    lda #$00
    sta pit_running,x
    rts
@reload:
    lda pit_reload_lo,x
    sta pit_count_lo,x
    lda pit_reload_hi,x
    sta pit_count_hi,x
@tick_done:
    rts
