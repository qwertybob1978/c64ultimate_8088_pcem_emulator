.setcpu "6502"

.importzp cpu8088_phys_addr
.import reu_copy_from_reu
.import reu_copy_to_reu
.importzp reu_c64_addr
.importzp reu_ext_addr
.importzp reu_length

.export cpu8088_mem_read_u8
.export cpu8088_mem_write_u8

.segment "BSS"
guest_data_byte: .res 1

.segment "CODE"

; Read/write one byte at cpu8088_phys_addr. These correctness-first DMA paths
; are replaced by the data-page cache in Phase 2.
cpu8088_mem_read_u8:
    jsr guest_setup_transfer
    jsr reu_copy_from_reu
    bcs @failed
    lda guest_data_byte
    clc
@failed:
    rts

cpu8088_mem_write_u8:
    sta guest_data_byte
    jsr guest_setup_transfer
    jmp reu_copy_to_reu

guest_setup_transfer:
    lda #<guest_data_byte
    sta reu_c64_addr
    lda #>guest_data_byte
    sta reu_c64_addr+1
    lda cpu8088_phys_addr
    sta reu_ext_addr
    lda cpu8088_phys_addr+1
    sta reu_ext_addr+1
    lda cpu8088_phys_addr+2
    sta reu_ext_addr+2
    lda #$01
    sta reu_length
    lda #$00
    sta reu_length+1
    rts
