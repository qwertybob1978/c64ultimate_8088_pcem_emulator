; Ultimate 64 turbo control
U64_TURBO_CONTROL = $D031
U64_TURBO_MAX     = $8F       ; index 15, badline stalls disabled

; MOS 8726 / REU register block
REU_STATUS        = $DF00
REU_COMMAND       = $DF01
REU_C64_ADDR_LO   = $DF02
REU_C64_ADDR_HI   = $DF03
REU_REU_ADDR_LO   = $DF04
REU_REU_ADDR_MI   = $DF05
REU_REU_ADDR_HI   = $DF06
REU_LENGTH_LO     = $DF07
REU_LENGTH_HI     = $DF08
REU_IRQ_MASK      = $DF09
REU_ADDR_CONTROL  = $DF0A

; Execute immediately plus transfer type.
REU_CMD_TO_REU    = $90
REU_CMD_FROM_REU  = $91

