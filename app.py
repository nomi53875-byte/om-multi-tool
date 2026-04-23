import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="BOM 多批次異動矩陣", layout="wide")

# --- 側邊欄 CSS 縮減版面 ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 150px; max-width: 180px; }
    .stCheckbox { margin-bottom: -12px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 BOM 多批次異動分析矩陣")

# --- 1. 側邊欄：一列整齊排列 ---
with st.sidebar:
    st.subheader("階層篩選")
    selected_levels = []
    for i in range(1, 7):
        if st.checkbox(f"L{i}", value=True if i in [3, 4, 5] else False, key=f"ML{i}"):
            selected_levels.append(i)

# --- 2. 零件位置精準解析函數 ---
def parse_bom_expert(file_bytes):
    try: text = file_bytes.decode("big5")
    except: text = file_bytes.decode("utf-8", errors="ignore")
    
    lines = text.splitlines()
    ref_map = {}
    for line in lines:
        match = re.match(r'^(\d)\s+(\S+)\s+([\d.]+)', line)
        if match:
            level, pn, qty = int(match.group(1)), match.group(2), float(match.group(3))
            parts = re.split(r'\s{2,}', line.strip())
            desc = parts[3] if len(parts) > 3 else ""
            ref_raw = parts[-1] if len(parts) > 4 else ""
            if qty <= 0: continue
            
            # 位置守門員邏輯
            raw_refs = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in ref_raw.split('.') if r.strip()]
            valid_refs = [r for r in raw_refs if re.match(r'^[A-Z]+\d+', r)]
            for r in valid_refs:
                ref_map[r] = {"Level": level, "PN": pn, "Desc": desc}
        elif line.startswith(" " * 10) and 'level' in locals():
            extra = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in line.strip().split('.') if r.strip()]
            for r in [x for x in extra if re.match(r'^[A-Z]+\d+', x)]:
                ref_map[r] = {"Level": level, "PN": pn, "Desc": desc}
    return ref_map

# --- 3. 檔案上傳與矩陣比對 ---
files = st.file_uploader("上傳多個 BOM 進行矩陣比對", accept_multiple_files=True)

if len(files) >= 2:
    all_maps = {f.name: parse_bom_expert(f.getvalue()) for f in files}
    base_file = st.selectbox("請指定基準 BOM (Master):", options=list(all_maps.keys()))
    
    # 取得所有位置聯集並排序
    all_refs = sorted(list(set().union(*(m.keys() for m in all_maps.values()))), 
                      key=lambda x: (re.sub(r'\d+', '', x), int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0))

    matrix_data = []
    for ref in all_refs:
        base_item = all_maps[base_file].get(ref)
        # 決定此位置的階層 (優先從基準找，找不到再從其他版本抓)
        level = base_item['Level'] if base_item else next((all_maps[f][ref]['Level'] for f in all_maps if ref in all_maps[f]), None)
        desc = base_item['Desc'] if base_item else next((all_maps[f][ref]['Desc'] for f in all_maps if ref in all_maps[f]), "")

        if level not in selected_levels: continue

        row = {"位置": ref, "階層": level, "規格描述": desc}
        has_diff = False
        
        for fname in all_maps:
            item = all_maps[fname].get(ref)
            pn = item['PN'] if item else "---"
            row[fname] = pn
            if base_item and item:
                if item['PN'] != base_item['PN']: has_diff = True
            elif base_item or item: 
                has_diff = True
        
        if has_diff: 
            matrix_data.append(row)

    if matrix_data:
        df_matrix = pd.DataFrame(matrix_data)
        # 欄位排序：位置 | 階層 | 規格 | 各版本料號
        cols = ["位置", "階層", "規格描述"] + list(all_maps.keys())
        df_matrix = df_matrix[cols]

        def highlight_diff(s):
            is_diff = s != s[base_file]
            return ['background-color: #fff1f0; color: #cf1322; font-weight: bold' if v else '' for v in is_diff]

        st.subheader(f"📋 異動矩陣 (以 {base_file} 為基準顯示差異)")
        st.dataframe(df_matrix.style.apply(highlight_diff, axis=1, subset=list(all_maps.keys())), use_container_width=True)
    else:
        st.success("✨ 所有檔案在選定階層內完全一致。")
