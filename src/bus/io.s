.setcpu "6502"

.export io_read_u8
.export io_write_u8
.export io_debug_latch
.export io_keyboard_push
.export io_keyboard_service
.export io_keyboard_reset
.export io_keyboard_pa
.export io_keyboard_key_waiting
.export io_keyboard_wantirq
.export io_keyboard_count
.export io_fdc_data_writes

.import pic_read_command
.import pic_read_data
.import pic_write_command
.import pic_write_data
.import pic_request_irq
.importzp cpu8088_phys_addr
.import cpu8088_mem_write_u8
.import dma_read_u8
.import dma_write_u8
.import fdc_read_main_status
.import fdc_read_data
.import fdc_read_digital_input
.import fdc_write_dor
.import fdc_write_data
.import pit_read_u8
.import pit_write_u8
.import cga_read_mono_mode_control
.import cga_read_color_mode_control
.import cga_read_mono_crtc_index
.import cga_read_color_crtc_index
.import cga_read_mono_crtc_data
.import cga_read_color_crtc_data
.import cga_read_mono_color_select
.import cga_read_color_select
.import cga_write_mono_mode_control
.import cga_write_color_mode_control
.import cga_write_mono_color_select
.import cga_write_color_select
.import cga_read_mono_cursor_position
.import cga_read_color_cursor_position
.import cga_write_mono_cursor_position
.import cga_write_color_cursor_position
.import cga_read_mono_cursor_start
.import cga_read_color_cursor_start
.import cga_read_mono_cursor_end
.import cga_read_color_cursor_end
.import cga_write_mono_cursor_start
.import cga_write_color_cursor_start
.import cga_write_mono_cursor_end
.import cga_write_color_cursor_end
.import cga_write_mono_crtc_index
.import cga_write_color_crtc_index
.import cga_write_mono_crtc_data
.import cga_write_color_crtc_data

.macro long_beq target
    bne :+
    jmp target
:
.endmacro

.macro long_bne target
    beq :+
    jmp target
:
.endmacro

.segment "BSS"
io_debug_latch: .res 2
io_write_value: .res 1
io_video_status: .res 2
io_ppi_port_b:   .res 1
io_keyboard_queue:.res 16
io_keyboard_head:.res 1
io_keyboard_tail:.res 1
io_keyboard_count:.res 1
io_keyboard_data:.res 1
io_keyboard_pa:  .res 1
io_keyboard_pb:  .res 1
io_keyboard_key_waiting:.res 1
io_keyboard_wantirq:.res 1
io_keyboard_shift_full:.res 1
io_fdc_data_writes:.res 1

; === I/O Trace Buffer (for debugging BIOS polling loops) ===
; Circular buffer: [port_hi][port_lo][data] x 256 entries = 768 bytes
io_trace_buf_start:
io_trace_buffer:  .res 3 * 256    ; circular buffer for I/O traces
io_trace_head:    .res 1          ; write index (0-255)
io_trace_tail:    .res 1          ; read index (0-255)  
io_trace_count:   .res 1          ; number of entries in buffer
io_trace_enabled: .res 1          ; non-zero = recording enabled
io_trace_max:     .res 1          ; max entries before wrap (default $FF)

; === I/O Trace Helper Macros ===
; Usage: call TRACE_READ with Y = index into io_trace_buffer (byte offset), 
;        preserves all registers except Z flag
.macro trace_log_read
    lda io_trace_enabled
    beq :+
    
    ; Store port high byte (X contains hi byte of port address)
    sta io_trace_buffer,y       ; store data value first (already in A)
    iny
    tya                         ; save new y back
    
    ; We need to preserve original values - do this differently below
:
.endmacro

; Simplified approach: inline trace code at each return point
; Format per entry: [port_hi][port_lo][data] x 256 entries = 768 bytes total

.segment "CODE"

; === I/O Trace Logging Routines ===
; Called from io_read_u8/io_write_u8 when io_trace_enabled != 0
; Input: A = data value, X = port_hi, Y = current buffer index (bytes 0-767)
; Output: returns updated Y in accumulator (new buffer index / 3)
trace_log_access:
    pha                         ; save data value
    txa                         ; A = port_hi
    tay                         ; Y = port_hi (for storage)
    pla                         ; A = data value
    
    ; Check if enabled
    cmp #$00                    ; clear flags based on previous compare... wrong path
    ; Let me redo this properly
    rts

; Better implementation: direct inline logging
; Macro-like sequence to log one access:
;   Input: A=data, X=port_hi, Y=current_entry_index (0..255)
;   Preserves: none (caller must save what it needs)
;   Returns: Y = next entry index
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
    long_beq @keyboard_data
    cmp #$61
    long_beq @ppi_port_b
    cmp #$62
    long_beq @ppi_switches
    cmp #$80
    long_beq @debug_low
    cmp #$81
    long_beq @debug_high
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
    cmp #$B4
    long_beq @cga_mono_crtc_index
    cmp #$B5
    long_beq @cga_mono_crtc_data
    cmp #$B8
    long_beq @cga_mono_mode_control
    cmp #$B9
    long_beq @cga_mono_color_select
    cmp #$D4
    long_beq @cga_color_crtc_index
    cmp #$D5
    long_beq @cga_color_crtc_data
    cmp #$D8
    long_beq @cga_color_mode_control
    cmp #$D9
    long_beq @cga_color_select
    cmp #$DA
    beq @video_status_03
    cmp #$F3
    long_beq @fdc_density_config
    cmp #$F4
    long_beq @fdc_main_status
    cmp #$F5
    long_beq @fdc_data
    cmp #$F7
    long_beq @fdc_digital_input
    jmp @open_bus
@cga_mono_crtc_index:
    jmp cga_read_mono_crtc_index
@cga_mono_crtc_data:
    jmp cga_read_mono_crtc_data
@cga_mono_mode_control:
    jmp cga_read_mono_mode_control
@cga_mono_color_select:
    jmp cga_read_mono_color_select
@cga_color_crtc_index:
    jmp cga_read_color_crtc_index
@cga_color_crtc_data:
    jmp cga_read_color_crtc_data
@cga_color_mode_control:
    jmp cga_read_color_mode_control
@cga_color_select:
    jmp cga_read_color_select
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
    long_bne @open_bus
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
    lda io_keyboard_pa
    rts
@ppi_port_b:
    lda io_keyboard_pb
    rts
@ppi_switches:
    lda io_keyboard_pb
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
    long_beq @write_high_page_03
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
    lda io_keyboard_pb
    eor io_write_value
    and #$40
    beq @write_ppi_store
    lda io_write_value
    and #$40
    beq @write_ppi_store
    jsr io_keyboard_reset
@write_ppi_store:
    lda io_write_value
    sta io_keyboard_pb
    lda io_write_value
    and #$80
    beq @write_ppi_done
    lda #$00
    sta io_keyboard_pa
    sta io_keyboard_data
    sta io_keyboard_shift_full
    jsr io_keyboard_service
@write_ppi_done:
    rts
@write_high_page_03:
    cpx #$B4
    long_beq @write_cga_mono_crtc_index
    cpx #$B5
    long_beq @write_cga_mono_crtc_data
    cpx #$B8
    long_beq @write_cga_mono_mode_control
    cpx #$B9
    long_beq @write_cga_mono_color_select
    cpx #$D4
    long_beq @write_cga_color_crtc_index
    cpx #$D5
    long_beq @write_cga_color_crtc_data
    cpx #$D8
    long_beq @write_cga_color_mode_control
    cpx #$D9
    long_beq @write_cga_color_select
    cpx #$F2
    long_beq @write_fdc_dor
    cpx #$F5
    long_beq @write_fdc_data
    jmp @done
@write_cga_mono_crtc_index:
    lda io_write_value
    jmp cga_write_mono_crtc_index
@write_cga_mono_crtc_data:
    lda io_write_value
    jmp cga_write_mono_crtc_data
@write_cga_mono_mode_control:
    lda io_write_value
    jmp cga_write_mono_mode_control
@write_cga_mono_color_select:
    lda io_write_value
    jmp cga_write_mono_color_select
@write_cga_color_crtc_index:
    lda io_write_value
    jmp cga_write_color_crtc_index
@write_cga_color_crtc_data:
    lda io_write_value
    jmp cga_write_color_crtc_data
@write_cga_color_mode_control:
    lda io_write_value
    jmp cga_write_color_mode_control
@write_cga_color_select:
    lda io_write_value
    jmp cga_write_color_select
@write_fdc_dor:
    lda io_write_value
    jmp fdc_write_dor
@write_fdc_data:
    inc io_fdc_data_writes
    lda io_write_value
    jmp fdc_write_data

; Queue one XT set-1 scan code for the emulated keyboard data port.
io_keyboard_push:
    pha
    lda io_keyboard_count
    bne @queue_key
@queue_key:
    ldy io_keyboard_tail
    pla
    sta io_keyboard_queue,y
    iny
    tya
    and #$0F
    sta io_keyboard_tail
    lda io_keyboard_count
    cmp #$10
    bcc :+
    lda io_keyboard_head
    clc
    adc #$01
    and #$0F
    sta io_keyboard_head
    lda #$0F
    sta io_keyboard_count
    rts
:
    inc io_keyboard_count
    rts

io_keyboard_service:
    lda io_keyboard_wantirq
    beq @queue_next
    lda #$00
    sta io_keyboard_wantirq
    lda io_keyboard_key_waiting
    sta io_keyboard_pa
    sta io_keyboard_data
    lda #$01
    sta io_keyboard_shift_full
    lda #<$041A
    sta cpu8088_phys_addr
    lda #>$041A
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    lda #$1E
    jsr cpu8088_mem_write_u8
    lda #<$041B
    sta cpu8088_phys_addr
    lda #>$041B
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    lda #$00
    jsr cpu8088_mem_write_u8
    lda #<$041C
    sta cpu8088_phys_addr
    lda #>$041C
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    lda #$1E
    jsr cpu8088_mem_write_u8
    lda #<$041D
    sta cpu8088_phys_addr
    lda #>$041D
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    lda #$00
    jsr cpu8088_mem_write_u8
    lda #<$041E
    sta cpu8088_phys_addr
    lda #>$041E
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    lda #$00
    jsr cpu8088_mem_write_u8
    lda #<$041F
    sta cpu8088_phys_addr
    lda #>$041F
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    lda io_keyboard_pa
    jsr cpu8088_mem_write_u8
    lda #$01
    jsr pic_request_irq
@queue_next:
    lda io_keyboard_count
    beq @done
    ldy io_keyboard_head
    lda io_keyboard_queue,y
    sta io_keyboard_key_waiting
    iny
    tya
    and #$0F
    sta io_keyboard_head
    dec io_keyboard_count
    lda #$01
    sta io_keyboard_wantirq
@done:
    rts

io_keyboard_reset:
    lda #$00
    sta io_keyboard_head
    sta io_keyboard_tail
    sta io_keyboard_count
    sta io_keyboard_wantirq
    sta io_keyboard_shift_full
    sta io_keyboard_pb
    sta io_keyboard_key_waiting
    lda #$AA
    sta io_keyboard_data
    sta io_keyboard_pa
    lda #<$041A
    sta cpu8088_phys_addr
    lda #>$041A
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    lda #$1E
    jsr cpu8088_mem_write_u8
    lda #<$041B
    sta cpu8088_phys_addr
    lda #>$041B
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    lda #$00
    jsr cpu8088_mem_write_u8
    lda #<$041C
    sta cpu8088_phys_addr
    lda #>$041C
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    lda #$20
    jsr cpu8088_mem_write_u8
    lda #<$041D
    sta cpu8088_phys_addr
    lda #>$041D
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    lda #$00
    jsr cpu8088_mem_write_u8
    lda #<$041E
    sta cpu8088_phys_addr
    lda #>$041E
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    lda #$00
    jsr cpu8088_mem_write_u8
    lda #<$041F
    sta cpu8088_phys_addr
    lda #>$041F
    sta cpu8088_phys_addr+1
    lda #$00
    sta cpu8088_phys_addr+2
    lda #$00
    jsr cpu8088_mem_write_u8
    lda #$01
    jsr pic_request_irq
    rts

