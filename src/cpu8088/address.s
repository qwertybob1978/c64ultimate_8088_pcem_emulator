.setcpu "6502"

.include "cpu8088/state.inc"

.import cpu8088_state
.import reu_copy_from_reu
.importzp reu_c64_addr
.importzp reu_ext_addr
.importzp reu_length

.export cpu8088_cs_ip_physical
.export cpu8088_segment_offset_physical
.export cpu8088_fetch_u8_slow
.exportzp cpu8088_phys_addr
.exportzp cpu8088_segment
.exportzp cpu8088_offset

.segment "ZEROPAGE"
cpu8088_phys_addr: .res 3
cpu8088_segment:   .res 2
cpu8088_offset:    .res 2

.segment "BSS"
fetch_byte: .res 1

.segment "CODE"

; Calculate ((CS << 4) + IP) & $FFFFF. The result is little-endian in
; cpu8088_phys_addr. This routine deliberately avoids 16-bit host arithmetic
; helpers because it will become part of the instruction-page cache refill.
cpu8088_cs_ip_physical:
    lda cpu8088_state+CPU_CS
    sta cpu8088_segment
    lda cpu8088_state+CPU_CS+1
    sta cpu8088_segment+1
    lda cpu8088_state+CPU_IP
    sta cpu8088_offset
    lda cpu8088_state+CPU_IP+1
    sta cpu8088_offset+1

; Calculate ((cpu8088_segment << 4) + cpu8088_offset) & $FFFFF.
cpu8088_segment_offset_physical:
    lda cpu8088_segment
    asl a
    asl a
    asl a
    asl a
    sta cpu8088_phys_addr

    lda cpu8088_segment
    lsr a
    lsr a
    lsr a
    lsr a
    sta cpu8088_phys_addr+1
    lda cpu8088_segment+1
    asl a
    asl a
    asl a
    asl a
    ora cpu8088_phys_addr+1
    sta cpu8088_phys_addr+1

    lda cpu8088_segment+1
    lsr a
    lsr a
    lsr a
    lsr a
    sta cpu8088_phys_addr+2

    clc
    lda cpu8088_phys_addr
    adc cpu8088_offset
    sta cpu8088_phys_addr
    lda cpu8088_phys_addr+1
    adc cpu8088_offset+1
    sta cpu8088_phys_addr+1
    lda cpu8088_phys_addr+2
    adc #$00
    and #$0F
    sta cpu8088_phys_addr+2
    rts

; Bootstrap-only byte fetch from REU guest memory. This proves the complete
; reset-address path but is intentionally not the interpreter's eventual fast
; path; normal execution will fetch from an internal-RAM page cache.
; Returns A=byte and carry clear, or carry set if the guarded DMA was rejected.
cpu8088_fetch_u8_slow:
    jsr cpu8088_cs_ip_physical
    lda cpu8088_phys_addr
    sta reu_ext_addr
    lda cpu8088_phys_addr+1
    sta reu_ext_addr+1
    lda cpu8088_phys_addr+2
    sta reu_ext_addr+2
    lda #<fetch_byte
    sta reu_c64_addr
    lda #>fetch_byte
    sta reu_c64_addr+1
    lda #$01
    sta reu_length
    lda #$00
    sta reu_length+1
    jsr reu_copy_from_reu
    bcs @failed

    inc cpu8088_state+CPU_IP
    bne @loaded
    inc cpu8088_state+CPU_IP+1
@loaded:
    lda fetch_byte
    clc
@failed:
    rts
