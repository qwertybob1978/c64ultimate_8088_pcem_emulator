.setcpu "6502"

; Generated from the linked diagnostic payload by generate_cartridge_include.py.
.include "cartridge_payload.inc"
D016 = $D016
MAGIC_DESK_BANK = $DE00

BANK_NUMBER = $F8
BYTES_LEFT  = $F9
COPY_SOURCE = $FB
COPY_DEST   = $FD
RAM_LOADER  = $0200

.segment "ROM"

; Standard C64 autostart header at $8000.
    .word cold_start
    .word warm_start
    .byte $C3, $C2, $CD, $38, $30       ; "CBM80"

cold_start:
warm_start:
    sei
    lda #$02
    sta $D020                           ; loader entered
    ldx #$FF
    txs
    stx D016
    jsr $FDA3                           ; initialize CIA/I/O
    jsr $FD50                           ; initialize RAM
    jsr $FD15                           ; restore KERNAL vectors
    jsr $FF5B                           ; initialize screen
    lda #$03
    sta $D020                           ; KERNAL initialization complete

    ; Bank switching replaces the complete $8000-$9FFF window, including this
    ; bootstrap. Relocate the copier to RAM before selecting another bank.
    lda #<ram_loader
    sta COPY_SOURCE
    lda #>ram_loader
    sta COPY_SOURCE+1
    lda #<RAM_LOADER
    sta COPY_DEST
    lda #>RAM_LOADER
    sta COPY_DEST+1
    lda #<(ram_loader_end-ram_loader)
    sta BYTES_LEFT
    lda #>(ram_loader_end-ram_loader)
    sta BYTES_LEFT+1
    ldy #$00
@copy_loader:
    lda (COPY_SOURCE),y
    sta (COPY_DEST),y
    inc COPY_SOURCE
    bne :+
    inc COPY_SOURCE+1
:
    inc COPY_DEST
    bne :+
    inc COPY_DEST+1
:
    lda BYTES_LEFT
    bne :+
    dec BYTES_LEFT+1
:
    dec BYTES_LEFT
    lda BYTES_LEFT
    ora BYTES_LEFT+1
    bne @copy_loader
    jmp RAM_LOADER

; This block is position independent except for the translated final halt JMP.
; Relative branches remain valid after the bytes are copied to RAM_LOADER.
ram_loader:
    lda #$00
    sta BANK_NUMBER
    lda #<PAYLOAD_ROM_ADDRESS
    sta COPY_SOURCE
    lda #>PAYLOAD_ROM_ADDRESS
    sta COPY_SOURCE+1
    lda #<PAYLOAD_LOAD_ADDRESS
    sta COPY_DEST
    lda #>PAYLOAD_LOAD_ADDRESS
    sta COPY_DEST+1
    lda #<PAYLOAD_SIZE
    sta BYTES_LEFT
    lda #>PAYLOAD_SIZE
    sta BYTES_LEFT+1

    ldy #$00
@copy_payload:
    lda (COPY_SOURCE),y
    sta (COPY_DEST),y
    inc COPY_SOURCE
    bne @source_advanced
    inc COPY_SOURCE+1
@source_advanced:
    inc COPY_DEST
    bne @dest_advanced
    inc COPY_DEST+1
@dest_advanced:
    ; $A000 is the end of each 8 KiB cartridge bank. Select the next bank and
    ; continue at $8000 while the destination remains contiguous C64 RAM.
    lda COPY_SOURCE
    bne @source_ready
    lda COPY_SOURCE+1
    cmp #$A0
    bne @source_ready
    inc BANK_NUMBER
    lda BANK_NUMBER
    sta MAGIC_DESK_BANK
    lda #$80
    sta COPY_SOURCE+1
@source_ready:
    lda BYTES_LEFT
    bne @decrement_low
    dec BYTES_LEFT+1
@decrement_low:
    dec BYTES_LEFT
    lda BYTES_LEFT
    ora BYTES_LEFT+1
    bne @copy_payload

    ; ld65 BSS is not stored in the PRG. Clear it before entering assembly code
    ; so cache-valid flags and diagnostic state are deterministic.
    lda #<PAYLOAD_BSS_START
    sta COPY_DEST
    lda #>PAYLOAD_BSS_START
    sta COPY_DEST+1
    lda #<PAYLOAD_BSS_SIZE
    sta BYTES_LEFT
    lda #>PAYLOAD_BSS_SIZE
    sta BYTES_LEFT+1
    lda BYTES_LEFT
    ora BYTES_LEFT+1
    bne @clear_bss
    jmp @bss_cleared
@clear_bss:
    lda #$00
    sta (COPY_DEST),y
    inc COPY_DEST
    bne @clear_dest_advanced
    inc COPY_DEST+1
@clear_dest_advanced:
    lda BYTES_LEFT
    bne @clear_decrement_low
    dec BYTES_LEFT+1
@clear_decrement_low:
    dec BYTES_LEFT
    lda BYTES_LEFT
    ora BYTES_LEFT+1
    bne @clear_bss

@bss_cleared:
    lda #$00
    sta MAGIC_DESK_BANK                 ; leave bank 0 mapped for payload media staging
    ; KERNAL screen output used by the diagnostic expects normal C64 IRQ
    ; servicing.  The XT loop masks IRQs again once diagnostic output is done.
    cli
    jsr PAYLOAD_ENTRY
@halt:
    ; The diagnostic is also a normal PRG and therefore returns with RTS.
    ; A cartridge has no BASIC caller to return to, so keep its final screen
    ; visible instead of falling through an undefined reset stack frame.
    jmp RAM_LOADER + (@halt - ram_loader)
ram_loader_end:

.org $81F0
media_descriptor:
    .byte $4D                           ; fixed descriptor signature
    .byte MEDIA_PRESENT
    .byte MEDIA_ROM_BANK
    .byte MEDIA_SIZE_LO
    .byte MEDIA_SIZE_HI
    .byte MEDIA_SIZE_BANK
    .byte MEDIA_REU_ADDR_LO
    .byte MEDIA_REU_ADDR_MI
    .byte MEDIA_REU_ADDR_HI

.assert * <= PAYLOAD_ROM_ADDRESS, error, "cartridge bootstrap exceeds reserved space"
