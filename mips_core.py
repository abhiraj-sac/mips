# mips_core.py
from typing import List, Dict, Any, Optional

R_FUNCTS = {
    0x20: 'add',
    0x22: 'sub',
    0x24: 'and',
    0x25: 'or',
    0x2A: 'slt',
}
I_OPCODES = {
    0x08: 'addi',
    0x23: 'lw',
    0x2b: 'sw',
    0x04: 'beq',
    0x05: 'bne',
}
J_OPCODES = {
    0x02: 'j'
}

DEFAULT_BASE_PC = 0x00400000


def parse_word(s: str) -> Optional[int]:
    s = s.strip()
    if not s:
        return None
    try:
        if s.startswith('0x') or s.startswith('0X'):
            return int(s, 16)
        if all(c in '01' for c in s) and len(s) == 32:
            return int(s, 2)
        return int(s, 16)
    except Exception:
        return None


def decode(instr: int) -> Dict[str, Any]:
    opcode = (instr >> 26) & 0x3F
    if opcode == 0:
        rs = (instr >> 21) & 0x1F
        rt = (instr >> 16) & 0x1F
        rd = (instr >> 11) & 0x1F
        shamt = (instr >> 6) & 0x1F
        funct = instr & 0x3F
        mnemonic = R_FUNCTS.get(funct, f'unknown_r(0x{funct:02x})')
        return {
            'type': 'R', 'opcode': opcode, 'rs': rs, 'rt': rt, 'rd': rd,
            'shamt': shamt, 'funct': funct, 'mnemonic': mnemonic
        }
    elif opcode in J_OPCODES:
        addr = instr & 0x03FFFFFF
        mnemonic = J_OPCODES[opcode]
        return {'type': 'J', 'opcode': opcode, 'address': addr, 'mnemonic': mnemonic}
    else:
        rs = (instr >> 21) & 0x1F
        rt = (instr >> 16) & 0x1F
        imm = instr & 0xFFFF
        if imm & 0x8000:
            imm = imm - 0x10000
        mnemonic = I_OPCODES.get(opcode, f'unknown_i(0x{opcode:02x})')
        return {'type': 'I', 'opcode': opcode, 'rs': rs, 'rt': rt, 'imm': imm, 'mnemonic': mnemonic}


def format_decoded(d: Dict[str, Any]) -> str:
    if d['type'] == 'R':
        return f"R-type: {d['mnemonic']} rs=${d['rs']} rt=${d['rt']} rd=${d['rd']} shamt={d['shamt']} funct=0x{d['funct']:02x}"
    if d['type'] == 'I':
        return f"I-type: {d['mnemonic']} rs=${d['rs']} rt=${d['rt']} imm={d['imm']}"
    return f"J-type: {d['mnemonic']} addr=0x{d['address']:07x}"


class SimpleMIPS:
    def __init__(self, instr_words: List[int], base_pc: int = DEFAULT_BASE_PC):
        self.regs = [0] * 32
        self.mem: Dict[int, int] = {}  # byte-address -> word
        self.pc = base_pc
        self.base = base_pc
        self.instrs = instr_words[:]  # copy
        self.step_count = 0
        self.halted = False

    def fetch_instr_at_pc(self, pc: int) -> Optional[int]:
        idx = (pc - self.base) // 4
        if idx < 0 or idx >= len(self.instrs):
            return None
        return self.instrs[idx]

    def step(self) -> Dict[str, Any]:
        if self.halted:
            return {'status': 'halted'}
        instr = self.fetch_instr_at_pc(self.pc)
        if instr is None:
            self.halted = True
            return {'status': 'pc_out_of_range', 'pc': self.pc}
        dec = decode(instr)
        action = {'pc': self.pc, 'instr': instr, 'decoded': dec}
        # Execute
        if dec['type'] == 'R':
            rs, rt, rd = dec['rs'], dec['rt'], dec['rd']
            if dec['mnemonic'] == 'add':
                self.regs[rd] = (self.regs[rs] + self.regs[rt]) & 0xFFFFFFFF
            elif dec['mnemonic'] == 'sub':
                self.regs[rd] = (self.regs[rs] - self.regs[rt]) & 0xFFFFFFFF
            elif dec['mnemonic'] == 'and':
                self.regs[rd] = self.regs[rs] & self.regs[rt]
            elif dec['mnemonic'] == 'or':
                self.regs[rd] = self.regs[rs] | self.regs[rt]
            elif dec['mnemonic'] == 'slt':
                self.regs[rd] = 1 if (self.regs[rs] & 0xFFFFFFFF) < (self.regs[rt] & 0xFFFFFFFF) else 0
            self.pc += 4
        elif dec['type'] == 'I':
            rs, rt, imm = dec['rs'], dec['rt'], dec['imm']
            if dec['mnemonic'] == 'addi':
                self.regs[rt] = (self.regs[rs] + imm) & 0xFFFFFFFF
                self.pc += 4
            elif dec['mnemonic'] == 'lw':
                addr = (self.regs[rs] + imm)
                word = self.mem.get(addr, 0)
                self.regs[rt] = word
                self.pc += 4
                action['mem_access'] = {'type': 'read', 'addr': addr, 'value': word}
            elif dec['mnemonic'] == 'sw':
                addr = (self.regs[rs] + imm)
                self.mem[addr] = self.regs[rt] & 0xFFFFFFFF
                self.pc += 4
                action['mem_access'] = {'type': 'write', 'addr': addr, 'value': self.mem[addr]}
            elif dec['mnemonic'] == 'beq':
                if self.regs[rs] == self.regs[rt]:
                    self.pc = self.pc + 4 + (imm << 2)
                else:
                    self.pc += 4
            elif dec['mnemonic'] == 'bne':
                if self.regs[rs] != self.regs[rt]:
                    self.pc = self.pc + 4 + (imm << 2)
                else:
                    self.pc += 4
            else:
                self.pc += 4
        elif dec['type'] == 'J':
            if dec['mnemonic'] == 'j':
                target = (self.pc & 0xF0000000) | ((dec['address'] << 2) & 0x0FFFFFFF)
                self.pc = target
            else:
                self.halted = True
                return {'status': 'unknown_j', 'decoded': dec}
        else:
            self.halted = True
            return {'status': 'unknown_type', 'decoded': dec}

        # enforce $zero = 0
        self.regs[0] = 0
        self.step_count += 1
        action['status'] = 'ok'
        action['step'] = self.step_count
        action['regs_snapshot'] = self.regs.copy()
        return action

    def run_n(self, n: int) -> List[Dict[str, Any]]:
        actions = []
        for _ in range(n):
            if self.halted:
                break
            actions.append(self.step())
        return actions
