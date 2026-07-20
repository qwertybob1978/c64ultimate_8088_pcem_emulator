.setcpu "6502"

.include "host/hardware.inc"

.export reu_detect
.export reu_probe_16m
.export reu_copy_to_reu
.export reu_copy_from_reu
.export reu_clear_guest_page
.export reu_clear_conventional
.exportzp reu_c64_addr
.exportzp reu_ext_addr
.exportzp reu_length

.segment "ZEROPAGE"
reu_c64_addr: .res 2
reu_ext_addr: .res 3
reu_length:   .res 2

.segment "BSS"
probe_byte:      .res 1
probe_saved_0:   .res 1
probe_saved_8m:  .res 1
probe_result:    .res 1
transfer_command:.res 1
reu_clear_byte:  .res 1

.segment "CODE"

; Probe a byte through DMA and restore its original value. Testing an actual
; transfer is more portable than checking register readback: compatible REU
; implementations differ in which address bits read back as writable.
; Returns carry set when a controller responds.
reu_detect:
    lda #<probe_byte
    sta reu_c64_addr
    lda #>probe_byte
    sta reu_c64_addr+1
    lda #$00
    sta reu_ext_addr
    sta reu_ext_addr+1
    sta reu_ext_addr+2
    lda #$01
    sta reu_length
    lda #$00
    sta reu_length+1

    lda #$A5
    sta probe_byte
    jsr reu_copy_from_reu
    lda probe_byte
    sta probe_saved_0
    eor #$FF
    sta probe_result
    sta probe_byte
    jsr reu_copy_to_reu

    lda probe_saved_0
    sta probe_byte
    jsr reu_copy_from_reu
    lda probe_byte
    cmp probe_result
    bne @missing

    lda probe_saved_0
    sta probe_byte
    jsr reu_copy_to_reu
    sec
    rts
@missing:
    clc
    rts

; Transfer reu_length bytes. A zero length is rejected because the hardware
; interprets zero as 65536 bytes. Carry is clear on success, set on rejection.
reu_copy_to_reu:
    lda #REU_CMD_TO_REU
    bne reu_copy

reu_copy_from_reu:
    lda #REU_CMD_FROM_REU

reu_copy:
    sta transfer_command
    lda reu_length
    ora reu_length+1
    bne @valid
    sec
    rts

@valid:
    php
    sei
    lda reu_c64_addr
    sta REU_C64_ADDR_LO
    lda reu_c64_addr+1
    sta REU_C64_ADDR_HI
    lda reu_ext_addr
    sta REU_REU_ADDR_LO
    lda reu_ext_addr+1
    sta REU_REU_ADDR_MI
    lda reu_ext_addr+2
    sta REU_REU_ADDR_HI
    lda reu_length
    sta REU_LENGTH_LO
    lda reu_length+1
    sta REU_LENGTH_HI
    lda #$00
    sta REU_IRQ_MASK
    sta REU_ADDR_CONTROL
    lda transfer_command
    sta REU_COMMAND
    plp
    clc
    rts

; Clear one 64 KiB REU page. A selects address bits 16..23. Fixing the C64
; source address makes the REU replicate one zero byte for the full transfer;
; a zero transfer length is the controller's documented 65536-byte encoding.
reu_clear_guest_page:
    tax
    lda #$00
    sta reu_clear_byte
    lda #<reu_clear_byte
    sta REU_C64_ADDR_LO
    lda #>reu_clear_byte
    sta REU_C64_ADDR_HI
    lda #$00
    sta REU_REU_ADDR_LO
    sta REU_REU_ADDR_MI
    stx REU_REU_ADDR_HI
    sta REU_LENGTH_LO
    sta REU_LENGTH_HI
    sta REU_IRQ_MASK
    lda #$80                    ; hold the C64 address fixed
    sta REU_ADDR_CONTROL
    lda #REU_CMD_TO_REU
    sta REU_COMMAND
    lda #$00
    sta REU_ADDR_CONTROL
    clc
    rts

; Clear the XT's ten 64 KiB conventional-memory pages (00000h-9FFFFh).
reu_clear_conventional:
    ldx #$00
@clear_page:
    txa
    jsr reu_clear_guest_page
    inx
    cpx #$0A
    bne @clear_page
    clc
    rts

; Non-destructively distinguish a 16 MiB REU from smaller devices by checking
; that $000000 and $800000 do not alias. Both tested bytes are restored even on
; failure. Returns carry set only for a non-aliasing 16 MiB address space.
reu_probe_16m:
    jsr reu_detect
    bcs @controller_present
    jmp @not_16m
@controller_present:

    lda #<probe_byte
    sta reu_c64_addr
    lda #>probe_byte
    sta reu_c64_addr+1
    lda #$00
    sta reu_ext_addr
    sta reu_ext_addr+1
    lda #$01
    sta reu_length
    lda #$00
    sta reu_length+1

    lda #$00
    sta reu_ext_addr+2
    jsr reu_copy_from_reu
    lda probe_byte
    sta probe_saved_0

    lda #$80
    sta reu_ext_addr+2
    jsr reu_copy_from_reu
    lda probe_byte
    sta probe_saved_8m

    lda #$55
    sta probe_byte
    lda #$00
    sta reu_ext_addr+2
    jsr reu_copy_to_reu

    lda #$AA
    sta probe_byte
    lda #$80
    sta reu_ext_addr+2
    jsr reu_copy_to_reu

    lda #$00
    sta probe_result
    sta reu_ext_addr+2
    jsr reu_copy_from_reu
    lda probe_byte
    cmp #$55
    bne @restore_bytes

    lda #$80
    sta reu_ext_addr+2
    jsr reu_copy_from_reu
    lda probe_byte
    cmp #$AA
    bne @restore_bytes
    lda #$01
    sta probe_result

@restore_bytes:
    lda probe_saved_0
    sta probe_byte
    lda #$00
    sta reu_ext_addr+2
    jsr reu_copy_to_reu

    lda probe_saved_8m
    sta probe_byte
    lda #$80
    sta reu_ext_addr+2
    jsr reu_copy_to_reu

    lda probe_result
    beq @not_16m
    sec
    rts
@not_16m:
    clc
    rts
