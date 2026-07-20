; Word register order follows the 8088 ModR/M register encoding where useful.
CPU_AX    = 0
CPU_CX    = 2
CPU_DX    = 4
CPU_BX    = 6
CPU_SP    = 8
CPU_BP    = 10
CPU_SI    = 12
CPU_DI    = 14
CPU_ES    = 16
CPU_CS    = 18
CPU_SS    = 20
CPU_DS    = 22
CPU_IP    = 24
CPU_FLAGS = 26
CPU_STATE_SIZE = 28

X86_FLAG_RESERVED = $0002
X86_FLAG_CF        = $0001
X86_FLAG_IF_HI     = $02
X86_FLAG_DF_HI     = $04
