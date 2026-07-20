.setcpu "6502"

.export io_read_u8
.export io_write_u8
.export io_debug_latch

.segment "BSS"
io_debug_latch: .res 2
io_write_value: .res 1
io_video_status: .res 2

.segment "CODE"

; Minimal XT I/O dispatcher. A/X form the 16-bit port for reads. Writes pass
; the value in A and the port in X/Y. Unimplemented ports are open bus ($FF).
; Ports $80/$81 are deterministic POST/debug latches used by diagnostics now
; and become the first motherboard trace sink in Phase 3.
io_read_u8:
    cpx #$03
    beq @video_port
    cpx #$00
    bne @open_bus
    cmp #$80
    beq @debug_low
    cmp #$81
    beq @debug_high
@open_bus:
    lda #$FF
    rts
@debug_low:
    lda io_debug_latch
    rts
@debug_high:
    lda io_debug_latch+1
    rts
@video_port:
    cmp #$BA
    beq @mda_status
    cmp #$DA
    bne @open_bus
    ldx #$01
    bne @toggle_video_status
@mda_status:
    ldx #$00
@toggle_video_status:
    lda io_video_status,x
    eor #$01
    sta io_video_status,x
    eor #$01                    ; return the phase before this read
    rts

io_write_u8:
    sta io_write_value
    cpy #$00
    bne @done
    cpx #$80
    beq @write_low
    cpx #$81
    bne @done
    lda io_write_value
    sta io_debug_latch+1
    rts
@write_low:
    lda io_write_value
    sta io_debug_latch
@done:
    rts
