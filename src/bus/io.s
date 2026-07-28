.setcpu "6502"

.export io_read_u8
.export io_write_u8
.export io_debug_latch
.export io_keyboard_push
.export io_fdc_data_writes

.import pic_read_command
.import pic_read_data
.import pic_write_command
.import pic_write_data
.import dma_read_u8
.import dma_write_u8
.import fdc_read_main_status
.import fdc_read_data
.import fdc_read_digital_input
.import fdc_write_dor
.import fdc_write_data
.import pit_read_u8
.import pit_write_u8

.segment "BSS"
io_debug_latch: .res 2
io_write_value: .res 1
io_video_status: .res 2
io_ppi_port_b:   .res 1
io_keyboard_data:.res 1
io_fdc_data_writes:.res 1

.segment "CODE"

; Minimal XT I/O dispatcher. A/X form the 16-bit port for reads. Writes pass
; the value in A and the port in X/Y. Unimplemented ports are open bus ($FF).
; Ports $80/$81 are deterministic POST/debug latches used by diagnostics now
; and become the first motherboard trace sink in Phase 3.
io_read_u8:
    cpx #$03
    beq @high_page_03
    cpx #$00
    bne @open_bus
    cmp #$20
    beq @pic_command
    cmp #$21
    beq @pic_data
    cmp #$40
    bcc @keyboard_or_misc
    cmp #$44
    bcc @pit_port
    cmp #$81
    beq @dma_page_2
@keyboard_or_misc:
    cmp #$60
    beq @keyboard_data
    cmp #$61
    beq @ppi_port_b
    cmp #$62
    beq @ppi_switches
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
@pic_command:
    jmp pic_read_command
@pic_data:
    jmp pic_read_data
@pit_port:
    sec
    sbc #$40
    tax
    jmp pit_read_u8
@dma_page_2:
    ldx #$81
    jmp dma_read_u8
@debug_high:
    lda io_debug_latch+1
    rts
@high_page_03:
    cmp #$DA
    beq @video_status_03
    cmp #$F3
    beq @fdc_density_config
    cmp #$F4
    beq @fdc_main_status
    cmp #$F5
    beq @fdc_data
    cmp #$F7
    beq @fdc_digital_input
    jmp @open_bus
@video_status_03:
    ldx #$01
    jmp @toggle_video_status
@fdc_density_config:
    lda #$20                    ; non-enhanced 5.25-inch drive type
    rts
@fdc_main_status:
    jmp fdc_read_main_status
@fdc_data:
    jmp fdc_read_data
@fdc_digital_input:
    jmp fdc_read_digital_input
@video_port:
    cmp #$DA
    bne @open_bus
    ldx #$01
@toggle_video_status:
    lda io_video_status,x
    eor #$01
    sta io_video_status,x
    eor #$01                    ; phase before this read
    beq :+
    lda #$09                    ; display-enable plus vertical retrace
:
    rts
@keyboard_data:
    lda io_keyboard_data
    rts
@ppi_port_b:
    lda io_ppi_port_b
    rts
@ppi_switches:
    lda io_ppi_port_b
    and #$08
    beq @ppi_equipment
    lda #$06                    ; PCem Generic XT: color 80-column display
    rts
@ppi_equipment:
    lda #$0D                    ; no FPU, base equipment switch bank
    rts

io_write_u8:
    sta io_write_value
    cpy #$03
    beq @write_high_page_03
    cpy #$00
    bne @done
    cpx #$20
    beq @write_pic_command
    cpx #$21
    beq @write_pic_data
    cpx #$40
    bcc :+
    cpx #$44
    bcc @write_pit
:
    cpx #$04
    bcc @write_dma
    cpx #$0E
    bcc @write_dma
    cpx #$81
    beq @write_dma_page
    cpx #$61
    beq @write_ppi_port_b
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
@write_pic_command:
    lda io_write_value
    jmp pic_write_command
@write_pic_data:
    lda io_write_value
    jmp pic_write_data
@write_pit:
    txa
    sec
    sbc #$40
    tax
    lda io_write_value
    jmp pit_write_u8
@write_dma:
    lda io_write_value
    jmp dma_write_u8
@write_dma_page:
    lda io_write_value
    ldx #$81
    jmp dma_write_u8
@write_ppi_port_b:
    lda io_write_value
    sta io_ppi_port_b
    rts
@write_high_page_03:
    cpx #$F2
    beq @write_fdc_dor
    cpx #$F5
    beq @write_fdc_data
    jmp @done
@write_fdc_dor:
    lda io_write_value
    jmp fdc_write_dor
@write_fdc_data:
    inc io_fdc_data_writes
    lda io_write_value
    jmp fdc_write_data

; Queue one XT set-1 scan code for the emulated keyboard data port.
io_keyboard_push:
    sta io_keyboard_data
    rts
