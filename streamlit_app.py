## File: `streamlit_app.py`


# streamlit_app.py
import streamlit as st
from typing import Optional
from mips_core import parse_word, decode, format_decoded, SimpleMIPS, DEFAULT_BASE_PC

st.set_page_config(page_title='MIPS Decoder & Visual Executor', layout='wide')
st.title('MIPS Instruction Decoder & Visual Executor (Streamlit)')

# Sidebar - input
st.sidebar.header('Program Input')
upload = st.sidebar.file_uploader('Upload instruction file (hex values, 0x... or 32-bit bin) each line', type=['txt', 'hex'])
text_area = st.sidebar.text_area('Or paste instructions here (one per line)')
base_pc = st.sidebar.text_input('Base PC (hex)', value=hex(DEFAULT_BASE_PC))
if base_pc.startswith('0x') or base_pc.startswith('0X'):
    try:
        base_pc_val = int(base_pc, 16)
    except Exception:
        base_pc_val = DEFAULT_BASE_PC
else:
    try:
        base_pc_val = int(base_pc)
    except Exception:
        base_pc_val = DEFAULT_BASE_PC

if 'sim' not in st.session_state:
    st.session_state.sim = None
    st.session_state.decoded = []
    st.session_state.trace = []

col1, col2 = st.columns([2, 3])
with col1:
    st.subheader('Load / Decode')
    if upload is not None:
        data = upload.getvalue().decode('utf-8')
        source_lines = [l for l in data.splitlines()]
    else:
        source_lines = [l for l in text_area.splitlines()]

    if st.button('Decode Instructions'):
        words = []
        for ln in source_lines:
            w = parse_word(ln)
            if w is not None:
                words.append(w)
        st.session_state.decoded = []
        pc = base_pc_val
        for w in words:
            d = decode(w)
            st.session_state.decoded.append({'pc': pc, 'word': w, 'decoded': d})
            pc += 4
        st.session_state.sim = SimpleMIPS(words, base_pc=base_pc_val)
        st.session_state.trace = []
        st.success(f'Decoded {len(words)} instructions and initialized simulator.')

    st.markdown('**Decoded Instructions**')
    if st.session_state.decoded:
        tbl = []
        for item in st.session_state.decoded:
            tbl.append({
                'PC': hex(item['pc']),
                'Instr (hex)': f"0x{item['word']:08x}",
                'Decoded': format_decoded(item['decoded'])
            })
        st.table(tbl)
    else:
        st.info('No instructions decoded. Paste instructions or upload a file and click Decode.')

with col2:
    st.subheader('Execution Controls')
    if st.session_state.sim is None:
        st.info('Simulator not initialized. Decode instructions first.')
    else:
        sim: SimpleMIPS = st.session_state.sim
        cols = st.columns([1,1,1,1,1])
        if cols[0].button('Step'):
            act = sim.step()
            st.session_state.trace.append(act)
        if cols[1].button('Run 10'):
            acts = sim.run_n(10)
            st.session_state.trace.extend(acts)
        if cols[2].button('Run 100'):
            acts = sim.run_n(100)
            st.session_state.trace.extend(acts)
        if cols[3].button('Run until end'):
            acts = sim.run_n(10000)
            st.session_state.trace.extend(acts)
        if cols[4].button('Reset'):
            if st.session_state.decoded:
                words = [item['word'] for item in st.session_state.decoded]
                st.session_state.sim = SimpleMIPS(words, base_pc=base_pc_val)
                st.session_state.trace = []
                st.success('Simulator reset')

        st.write('---')
        st.write(f"PC = 0x{sim.pc:08x}  | Steps executed: {sim.step_count}  | Halted: {sim.halted}")

st.subheader('Execution Trace')
if st.session_state.trace:
    for t in st.session_state.trace[-20:]:
        with st.expander(f"Step {t.get('step','?')}  PC=0x{t.get('pc',0):08x}", expanded=False):
            dec = t.get('decoded')
            st.write(format_decoded(dec) if dec else 'N/A')
            if 'mem_access' in t:
                st.write('Memory access:', t['mem_access'])
            st.write('Registers (non-zero):')
            regsnz = {f'${i}': v for i, v in enumerate(t.get('regs_snapshot',[])) if v != 0}
            st.write(regsnz)
else:
    st.info('No execution steps yet. Use step/run controls.')

st.subheader('Registers')
if st.session_state.sim is not None:
    regs = st.session_state.sim.regs
    reg_table = []
    for i in range(0, 32, 4):
        reg_table.append({
            'r0': f"${i}", 'v0': regs[i],
            'r1': f"${i+1}", 'v1': regs[i+1],
            'r2': f"${i+2}", 'v2': regs[i+2],
            'r3': f"${i+3}", 'v3': regs[i+3],
        })
    st.table(reg_table)
else:
    st.info('Simulator not initialized.')

st.subheader('Memory (non-zero words)')
if st.session_state.sim is not None:
    mem = st.session_state.sim.mem
    if mem:
        mem_tbl = [{'addr': hex(a), 'value': hex(v)} for a, v in sorted(mem.items())]
        st.table(mem_tbl)
    else:
        st.info('Memory empty')

st.markdown('---')
st.caption('This front-end decodes MIPS instructions and steps through a small execution model. It supports add, sub, and, or, slt, addi, lw, sw, beq, bne, j. $zero is enforced as 0. For lw/sw, memory addresses are treated as byte addresses (word-aligned addresses recommended).')