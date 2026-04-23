import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="BOM 多批次異動分析矩陣", layout="wide")

# --- 側邊欄 CSS 微調 ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 150px; max-width: 180px; }
    .stCheckbox { margin-bottom: -12px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 BOM 多批次異動分析矩陣 (精準修正版)")

with st.sidebar:
    st.subheader("階層篩選")
    selected_levels = []
    for i in range(1, 7):
        if st.checkbox(f"L{i}", value=True if i in [3, 4, 5] else False, key=f"ML{i}"):
            selected_levels.append(i)

# --- 強化版解析邏輯 (確保規格完整、過濾版號) ---
def parse_bom_expert(file_bytes):
    try: text = file_bytes.decode("big5")
    except: text = file_bytes.decode("utf-8", errors="ignore")
    
    lines = text.splitlines()
    ref_map = {}
    current_info = None
    
    for line in lines:
        match = re.match(r'^(\d)\s+(\S+)\s+([\d.]+)', line)
        if match:
            level, pn, qty = int(match.group(1)), match.group(2), float(match.group(3))
            
            # 使用更嚴謹的分隔抓取規格與位置
            parts = re.split(r'\s{2,}', line.strip())
            desc = parts[3] if len(parts) > 3 else ""
            ref_raw = parts[-1] if len(parts) > 4 else ""
            
            if qty <= 0: continue
            
            # 位置守門員
            raw_refs = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in ref_raw.split('.') if r.strip()]
            valid_refs = [r for r in raw_refs if re.match(r'^[A-Z]+\d+', r)]
            
            current_info = {"Level": level, "PN": pn, "Desc": desc}
            for r in valid_refs:
                ref_map[r] = current_info
        elif line.startswith(" " * 10) and current_info:
            extra = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in line.strip().split('.') if r.strip()]
            for r in [x for x in extra if re.match(r'^[A-Z]+\d+', x)]:
                ref_map[r] = current_info
    return ref_map

files = st.file_uploader("上傳多個 BOM 進行矩陣比對", accept_multiple_files=True)

if len(files) >= 2:
    all_maps = {f.name: parse_bom_expert(f.getvalue()) for f in files}
    base_file = st.selectbox("請指定基準 BOM (Master):", options=list(all_maps.keys()))
    
    all_refs = sorted(list(set().union(*(m.keys() for m in all_maps.values()))), 
                      key=lambda x: (re.sub(r'\d+', '', x), int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0))

    raw_list = []
    for ref in all_refs:
        base_item = all_maps[base_file].get(ref)
        level = base_item['Level'] if base_item else next((all_maps[f][ref]['Level'] for f in all_maps if ref in all_maps[f]), None)
        desc = base_item['Desc'] if base_item else next((all_maps[f][ref]['Desc'] for f in all_maps if ref in all_maps[f]), "")

        if level not in selected_levels: continue

        row_data = {"階層": level, "規格描述": desc}
        is_different = False
        
        file_pns = {}
        for fname in all_maps:
            item = all_maps[fname].get(ref)
            pn = item['PN'] if item else "---"
            file_pns[fname] = pn
            
            # 比對邏輯：與基準檔不同
            if base_item:
                if pn != base_item['PN']: is_different = True
            elif pn != "---": 
                is_different = True
        
        if is_different:
            row_data.update(file_pns)
            raw_list.append({"ref_id": ref, **row_data})

    if raw_list:
        df_raw = pd.DataFrame(raw_list)
        # 核心修正：將所有變更欄位完全相同的行，把位置(ref_id)合併
        group_keys = ["階層", "規格描述"] + list(all_maps.keys())
        summary = df_raw.groupby(group_keys)["ref_id"].apply(lambda x: ".".join(x)).reset_index()
        
        # 欄位重排
        cols = ["ref_id", "階層", "規格描述"] + list(all_maps.keys())
        summary = summary[cols]
        summary.rename(columns={"ref_id": "位置"}, inplace=True)

        def highlight_diff(s):
            return ['background-color: #fff1f0; color: #cf1322; font-weight: bold' if v != s[base_file] else '' for v in s]

        st.subheader(f"📋 異動矩陣 (對照組數: {len(files)})")
        st.dataframe(summary.style.apply(highlight_diff, axis=1, subset=list(all_maps.keys())), use_container_width=True)
    else:
        st.success("✨ 選定階層內所有 BOM 完全一致。")
