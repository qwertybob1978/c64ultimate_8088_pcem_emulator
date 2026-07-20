.setcpu "6502"

.import reu_copy_from_reu
.import reu_copy_to_reu
.importzp reu_c64_addr
.importzp reu_ext_addr
.importzp reu_length

.export cga_render_text_40
.export cga_test_render
.export cga_test_error

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

.segment "ZEROPAGE"
cga_screen_ptr: .res 2
cga_color_ptr:  .res 2

.segment "BSS"
cga_row_buffer:  .res CGA_ROW_BYTES
cga_saved_row:   .res CGA_ROW_BYTES
cga_source_index:.res 1
cga_rows_left:   .res 1
cga_test_error:  .res 1

.segment "CODE"

; Project the left 40 columns of the 80x25 CGA text page at physical B8000h
; onto the C64's 40x25 text screen. Each CGA row is fetched in one REU DMA.
cga_render_text_40:
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
    bcs @failed

    ldx #$00
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
    bne @row
    clc
    rts
@failed:
    sec
    rts

; Seed and verify a visible CGA text row without permanently changing guest RAM.
cga_test_render:
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

    lda C64_SCREEN
    cmp #$03                    ; C
    bne @restore_failed
    lda C64_SCREEN+1
    cmp #$36                    ; 6
    bne @restore_failed
    lda C64_SCREEN+2
    cmp #$34                    ; 4
    bne @restore_failed
    lda C64_SCREEN+4
    cmp #$18                    ; X
    bne @restore_failed
    lda C64_COLOR
    cmp #$01                    ; CGA white -> C64 white
    bne @restore_failed
    lda #$01
    sta cga_source_index
    bne @restore

@restore_failed:
    lda #$09
    sta cga_test_error
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

.segment "RODATA"
cga_demo_text:
    .byte "C64 X86 CGA TEXT READY - BIOS OUTPUT", $00

; Approximate the 16 CGA foreground colors with the C64 palette.
cga_to_c64_color:
    .byte $00, $06, $05, $03, $02, $04, $09, $0F
    .byte $0B, $0E, $0D, $03, $0A, $04, $07, $01
