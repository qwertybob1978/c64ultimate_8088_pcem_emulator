.setcpu "6502"

.import reu_copy_from_reu
.import reu_copy_to_reu
.importzp reu_c64_addr
.importzp reu_ext_addr
.importzp reu_length
.import cpu8088_mem_cache_flush

.export cga_render_text_40
.export cga_test_render
.export cga_test_error
.export cga_read_mono_mode_control
.export cga_read_color_mode_control
.export cga_read_mono_crtc_index
.export cga_read_color_crtc_index
.export cga_read_mono_crtc_data
.export cga_read_color_crtc_data
.export cga_read_mono_color_select
.export cga_read_color_select
.export cga_write_mono_mode_control
.export cga_write_color_mode_control
.export cga_write_mono_crtc_index
.export cga_write_color_crtc_index
.export cga_write_mono_crtc_data
.export cga_write_color_crtc_data
.export cga_write_mono_color_select
.export cga_write_color_select
.export cga_read_mono_cursor_position
.export cga_read_color_cursor_position
.export cga_write_mono_cursor_position
.export cga_write_color_cursor_position
.export cga_read_mono_cursor_start
.export cga_read_color_cursor_start
.export cga_read_mono_cursor_end
.export cga_read_color_cursor_end
.export cga_write_mono_cursor_start
.export cga_write_color_cursor_start
.export cga_write_mono_cursor_end
.export cga_write_color_cursor_end

C64_SCREEN = $0400
C64_COLOR  = $D800
BACKGROUND_COLOR = $D021
CGA_ROW_BYTES = 160
CGA_ROWS = 25

.macro long_bcs target
    bcc :+
    jmp target
:
.endmacro

.macro long_bne target
    beq :+
    jmp target
:
.endmacro

.segment "ZEROPAGE"
cga_screen_ptr: .res 2
cga_color_ptr:  .res 2

.segment "BSS"
cga_row_buffer:  .res CGA_ROW_BYTES
cga_saved_row:   .res CGA_ROW_BYTES
cga_source_index:.res 1
cga_row_base:    .res 1
cga_row_left_count:  .res 1
cga_row_right_count: .res 1
cga_rows_left:   .res 1
cga_test_error:  .res 1
cga_text_start_offset:   .res 2
cga_mono_mode_control:   .res 1
cga_mono_color_select:    .res 1
cga_mono_cursor_start:    .res 1
cga_mono_cursor_end:      .res 1
cga_mono_cursor_pos:      .res 2
cga_mono_crtc_index:      .res 1
cga_mono_crtc_regs:       .res 32
cga_color_mode_control:   .res 1
cga_color_color_select:   .res 1
cga_color_cursor_start:   .res 1
cga_color_cursor_end:     .res 1
cga_color_cursor_pos:     .res 2
cga_color_crtc_index:     .res 1
cga_color_crtc_regs:      .res 32

.segment "CODE"

; Project the left 40 columns of the 80x25 CGA text page at physical B8000h
; onto the C64's 40x25 text screen. Each CGA row is fetched in one REU DMA.
cga_render_text_40:
    jsr cpu8088_mem_cache_flush
    bcc :+
    rts
:
    lda #$00
    sta BACKGROUND_COLOR
    lda #<C64_SCREEN
    sta cga_screen_ptr
    lda #>C64_SCREEN
    sta cga_screen_ptr+1
    lda #<C64_COLOR
    sta cga_color_ptr
    lda #>C64_COLOR
    sta cga_color_ptr+1
    jsr cga_setup_b8000
    jsr cga_apply_color_start_address
    lda #CGA_ROWS
    sta cga_rows_left

@row:
    lda #<cga_row_buffer
    sta reu_c64_addr
    lda #>cga_row_buffer
    sta reu_c64_addr+1
    lda #<CGA_ROW_BYTES
    sta reu_length
    lda #>CGA_ROW_BYTES
    sta reu_length+1
    jsr reu_copy_from_reu
    long_bcs @failed

    lda #$00
    sta cga_row_left_count
    sta cga_row_right_count
    ldx #$00
@density:
    lda cga_row_buffer,x
    cmp #$20
    beq :+
    cmp #$00
    beq :+
    cpx #$50
    bcc @count_left
    inc cga_row_right_count
    bne :+
@count_left:
    inc cga_row_left_count
:
    inx
    inx
    cpx #CGA_ROW_BYTES
    bne @density
    lda cga_row_right_count
    cmp cga_row_left_count
    bcc @use_left_half
    lda #$50
    bne @store_half
@use_left_half:
    lda #$00
@store_half:
    sta cga_row_base
    ldx cga_row_base
    ldy #$00
@cell:
    stx cga_source_index
    lda cga_row_buffer,x
    jsr cga_ascii_to_screen
    sta (cga_screen_ptr),y
    ldx cga_source_index
    lda cga_row_buffer+1,x
    and #$0F
    tax
    lda cga_to_c64_color,x
    sta (cga_color_ptr),y
    ldx cga_source_index
    inx
    inx
    iny
    cpy #40
    bne @cell

    clc
    lda cga_screen_ptr
    adc #40
    sta cga_screen_ptr
    bcc :+
    inc cga_screen_ptr+1
:
    clc
    lda cga_color_ptr
    adc #40
    sta cga_color_ptr
    bcc :+
    inc cga_color_ptr+1
:
    clc
    lda reu_ext_addr
    adc #<CGA_ROW_BYTES
    sta reu_ext_addr
    lda reu_ext_addr+1
    adc #>CGA_ROW_BYTES
    sta reu_ext_addr+1
    bcc :+
    inc reu_ext_addr+2
:
    dec cga_rows_left
    long_bne @row
    clc
    rts
@failed:
    sec
    rts

; Seed and verify a visible CGA text row without permanently changing guest RAM.
cga_test_render:
    jsr cpu8088_mem_cache_flush
    long_bcs @test_failed
    lda #$00
    sta cga_test_error
    jsr cga_setup_b8000
    lda #<cga_saved_row
    sta reu_c64_addr
    lda #>cga_saved_row
    sta reu_c64_addr+1
    lda #<CGA_ROW_BYTES
    sta reu_length
    lda #>CGA_ROW_BYTES
    sta reu_length+1
    jsr reu_copy_from_reu
    long_bcs @test_failed

    lda #$00
    ldx #$00
@clear_demo:
    sta cga_row_buffer,x
    inx
    cpx #CGA_ROW_BYTES
    bne @clear_demo

    ldx #$00
    ldy #$00
@copy_demo:
    lda cga_demo_text,y
    beq @demo_ready
    sta cga_row_buffer,x
    lda #$0F
    sta cga_row_buffer+1,x
    inx
    inx
    iny
    bne @copy_demo
@demo_ready:
    jsr cga_setup_b8000
    lda #<cga_row_buffer
    sta reu_c64_addr
    lda #>cga_row_buffer
    sta reu_c64_addr+1
    lda #<CGA_ROW_BYTES
    sta reu_length
    lda #>CGA_ROW_BYTES
    sta reu_length+1
    jsr reu_copy_to_reu
    long_bcs @test_failed
    jsr cga_render_text_40
    bcs @restore_failed

    lda #$03
    sta cga_test_error
    lda C64_SCREEN
    cmp #$03                    ; C
    bne @restore_failed
    lda #$04
    sta cga_test_error
    lda C64_SCREEN+1
    cmp #$36                    ; 6
    bne @restore_failed
    lda #$05
    sta cga_test_error
    lda C64_SCREEN+2
    cmp #$34                    ; 4
    bne @restore_failed
    lda #$06
    sta cga_test_error
    lda C64_SCREEN+4
    cmp #$18                    ; X
    bne @restore_failed
    lda #$07
    sta cga_test_error
    lda C64_COLOR
    and #$0F                    ; color RAM read high nibble is undefined
    cmp #$01                    ; CGA white -> C64 white
    bne @restore_failed
    lda #$01
    sta cga_source_index
    bne @restore

@restore_failed:
    lda #$00
    sta cga_source_index
@restore:
    jsr cga_setup_b8000
    lda #<cga_saved_row
    sta reu_c64_addr
    lda #>cga_saved_row
    sta reu_c64_addr+1
    lda #<CGA_ROW_BYTES
    sta reu_length
    lda #>CGA_ROW_BYTES
    sta reu_length+1
    jsr reu_copy_to_reu
    bcs @test_failed
    lda cga_source_index
    beq @test_failed
    sec
    rts
@test_failed:
    lda cga_test_error
    bne :+
    lda #$02
    sta cga_test_error
:
    clc
    rts

cga_setup_b8000:
    lda #$00
    sta reu_ext_addr
    lda #$80
    sta reu_ext_addr+1
    lda #$0B
    sta reu_ext_addr+2
    rts

cga_apply_color_start_address:
    lda cga_color_crtc_regs+$0C
    sta cga_text_start_offset+1
    lda cga_color_crtc_regs+$0D
    asl a
    sta cga_text_start_offset
    lda cga_text_start_offset+1
    rol a
    sta cga_text_start_offset+1
    clc
    lda reu_ext_addr+1
    adc cga_text_start_offset
    sta reu_ext_addr+1
    lda reu_ext_addr+2
    adc cga_text_start_offset+1
    sta reu_ext_addr+2
    rts

cga_ascii_to_screen:
    cmp #$20
    bcc @screen_space
    cmp #$40
    bcc @screen_done            ; space, punctuation, digits
    cmp #$5B
    bcs @screen_lower
    sec
    sbc #$40                    ; ASCII A-Z -> screen codes 1-26
    rts
@screen_lower:
    cmp #$61
    bcc @screen_space
    cmp #$7B
    bcs @screen_space
    sec
    sbc #$60                    ; show lowercase as uppercase glyphs
    rts
@screen_space:
    lda #$20
@screen_done:
    rts

cga_write_mono_mode_control:
    sta cga_mono_mode_control
    rts

cga_write_color_mode_control:
    sta cga_color_mode_control
    rts

cga_write_mono_color_select:
    sta cga_mono_color_select
    rts

cga_write_color_select:
    sta cga_color_color_select
    rts

cga_write_mono_crtc_index:
    and #$1F
    sta cga_mono_crtc_index
    rts

cga_write_color_crtc_index:
    and #$1F
    sta cga_color_crtc_index
    rts

cga_write_mono_crtc_data:
    ldx cga_mono_crtc_index
    cpx #$0A
    beq @cursor_start
    cpx #$0B
    beq @cursor_end
    cpx #$0E
    beq @cursor_pos_hi
    cpx #$0F
    beq @cursor_pos_lo
    sta cga_mono_crtc_regs,x
    rts
@cursor_start:
    sta cga_mono_cursor_start
    sta cga_mono_crtc_regs,x
    rts
@cursor_end:
    sta cga_mono_cursor_end
    sta cga_mono_crtc_regs,x
    rts
@cursor_pos_hi:
    sta cga_mono_cursor_pos+1
    sta cga_mono_crtc_regs,x
    rts
@cursor_pos_lo:
    sta cga_mono_cursor_pos
    sta cga_mono_crtc_regs,x
    rts

cga_write_color_crtc_data:
    ldx cga_color_crtc_index
    cpx #$0A
    beq @ccursor_start
    cpx #$0B
    beq @ccursor_end
    cpx #$0E
    beq @ccursor_pos_hi
    cpx #$0F
    beq @ccursor_pos_lo
    sta cga_color_crtc_regs,x
    rts
@ccursor_start:
    sta cga_color_cursor_start
    sta cga_color_crtc_regs,x
    rts
@ccursor_end:
    sta cga_color_cursor_end
    sta cga_color_crtc_regs,x
    rts
@ccursor_pos_hi:
    sta cga_color_cursor_pos+1
    sta cga_color_crtc_regs,x
    rts
@ccursor_pos_lo:
    sta cga_color_cursor_pos
    sta cga_color_crtc_regs,x
    rts

cga_read_mono_mode_control:
    lda cga_mono_mode_control
    rts

cga_read_color_mode_control:
    lda cga_color_mode_control
    rts

cga_read_mono_crtc_index:
    lda cga_mono_crtc_index
    rts

cga_read_color_crtc_index:
    lda cga_color_crtc_index
    rts

cga_read_mono_crtc_data:
    ldx cga_mono_crtc_index
    cpx #$0A
    beq @cursor_start
    cpx #$0B
    beq @cursor_end
    cpx #$0E
    beq @cursor_pos_hi
    cpx #$0F
    beq @cursor_pos_lo
    lda cga_mono_crtc_regs,x
    rts
@cursor_start:
    lda cga_mono_cursor_start
    rts
@cursor_end:
    lda cga_mono_cursor_end
    rts
@cursor_pos_hi:
    lda cga_mono_cursor_pos+1
    rts
@cursor_pos_lo:
    lda cga_mono_cursor_pos
    rts

cga_read_mono_color_select:
    lda cga_mono_color_select
    rts

cga_read_color_crtc_data:
    ldx cga_color_crtc_index
    cpx #$0A
    beq @ccursor_start
    cpx #$0B
    beq @ccursor_end
    cpx #$0E
    beq @ccursor_pos_hi
    cpx #$0F
    beq @ccursor_pos_lo
    lda cga_color_crtc_regs,x
    rts
@ccursor_start:
    lda cga_color_cursor_start
    rts
@ccursor_end:
    lda cga_color_cursor_end
    rts
@ccursor_pos_hi:
    lda cga_color_cursor_pos+1
    rts
@ccursor_pos_lo:
    lda cga_color_cursor_pos
    rts

cga_read_color_select:
    lda cga_color_color_select
    rts

cga_write_mono_cursor_start:
    sta cga_mono_cursor_start
    rts

cga_write_color_cursor_start:
    sta cga_color_cursor_start
    rts

cga_write_mono_cursor_end:
    sta cga_mono_cursor_end
    rts

cga_write_color_cursor_end:
    sta cga_color_cursor_end
    rts

cga_write_mono_cursor_position:
    ldx cga_mono_crtc_index
    cpx #$0E
    beq @pos_hi
    cpx #$0F
    beq @pos_lo
    rts
@pos_hi:
    sta cga_mono_cursor_pos+1
    rts
@pos_lo:
    sta cga_mono_cursor_pos
    rts

cga_write_color_cursor_position:
    ldx cga_color_crtc_index
    cpx #$0E
    beq @cpos_hi
    cpx #$0F
    beq @cpos_lo
    rts
@cpos_hi:
    sta cga_color_cursor_pos+1
    rts
@cpos_lo:
    sta cga_color_cursor_pos
    rts

cga_read_mono_cursor_start:
    lda cga_mono_cursor_start
    rts

cga_read_color_cursor_start:
    lda cga_color_cursor_start
    rts

cga_read_mono_cursor_end:
    lda cga_mono_cursor_end
    rts

cga_read_color_cursor_end:
    lda cga_color_cursor_end
    rts

cga_read_mono_cursor_position:
    ldx cga_mono_crtc_index
    cpx #$0E
    beq @rpos_hi
    cpx #$0F
    beq @rpos_lo
    lda #$00
    rts
@rpos_hi:
    lda cga_mono_cursor_pos+1
    rts
@rpos_lo:
    lda cga_mono_cursor_pos
    rts

cga_read_color_cursor_position:
    ldx cga_color_crtc_index
    cpx #$0E
    beq @crpos_hi
    cpx #$0F
    beq @crpos_lo
    lda #$00
    rts
@crpos_hi:
    lda cga_color_cursor_pos+1
    rts
@crpos_lo:
    lda cga_color_cursor_pos
    rts

.segment "RODATA"
cga_demo_text:
    .byte "C64 X86 CGA TEXT READY - BIOS OUTPUT", $00

; Approximate the 16 CGA foreground colors with the C64 palette.
cga_to_c64_color:
    .byte $00, $06, $05, $03, $02, $04, $09, $0F
    .byte $0B, $0E, $0D, $03, $0A, $04, $07, $01
