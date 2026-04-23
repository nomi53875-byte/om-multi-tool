import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="BOM 多批次異動分析矩陣", layout="wide")

# --- 僅保留基礎樣式：文字置中 ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 150px; max-width: 180px; }
    .stCheckbox { margin-bottom: -12px; }
    [data-testid="stDataFrame"] td { text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 BOM 多批次異動分析矩陣 (回歸穩定版)")

with st.sidebar:
    st.subheader("階層篩選")
    selected_levels = []
    for i in range(1, 7):
        if st.checkbox(f"L{i}", value=True if i in [3, 4, 5] else False, key=f"ML{i}"):
            selected_levels.append(i)

# --- 採用 4.txt 最穩定的解析器 ---
def parse_bom_logic_fixed(file_bytes):
    try: text = file_bytes.decode("big5")
    except: text = file_bytes.decode("utf-8", errors="ignore")
    lines = text.splitlines()
    ref_map = {}
    current_info = None
    for line in lines:
        match = re.match(r'^(\d)\s+(\S+)\s+([\d.]+)', line)
        if match:
            level, pn, qty = int(match.group(1)), match.group(2), float(match.group(3))
            parts = re.split(r'\s{2,}', line.strip())
            desc = parts[3] if len(parts) > 3 else ""
            ref_raw = parts[-1] if len(parts) > 4 else ""
            if qty <= 0: continue
            raw_refs = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in ref_raw.split('.') if r.strip()]
            valid_refs = [r for r in raw_refs if re.match(r'^[A-Z]+\d+', r)]
            current_info = {"Level": level, "PN": pn, "Desc": desc}
            for r in valid_refs: ref_map[r] = current_info
        elif line.startswith(" " * 10) and current_info:
            extra = [re.sub(r'\(.*?\)\d*', '', r).strip() for r in line.strip().split('.') if r.strip()]
            for r in [x for x in extra if re.match(r'^[A-Z]+\d+', x)]:
                ref_map[r] = current_info
    return ref_map

files = st.file_uploader("上傳多個 BOM 進行矩陣比對", accept_multiple_files=True)

if len(files) >= 2:
    all_maps = {f.name: parse_bom_logic_fixed(f.getvalue()) for f in files}
    base_file = st.selectbox("請指定基準 BOM (Master):", options=list(all_maps.keys()))
    
    all_refs = sorted(list(set().union(*(m.keys() for m in all_maps.values()))), 
                      key=lambda x: (re.sub(r'\d+', '', x), int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0))

    final_data = []
    for ref in all_refs:
        base_item = all_maps[base_file].get(ref)
        level = base_item['Level'] if base_item else next((all_maps[f][ref]['Level'] for f in all_maps if ref in all_maps[f]), None)
        desc = base_item['Desc'] if base_item else next((all_maps[f][ref]['Desc'] for f in all_maps if ref in all_maps[f]), "")

        if level not in selected_levels: continue

        file_pns = {}
        # 圖標設定：僅變更使用 🟡，其餘維持原狀
        status_label = "✅ 無差異"
        
        diff_found = False
        for fname in all_maps:
            item = all_maps[fname].get(ref)
            pn = item['PN'] if item else "---"
            file_pns[fname] = pn
            
            if fname != base_file:
                if not base_item and item: 
                    status_label, diff_found = "🆕 新增", True
                elif base_item and not item: 
                    status_label, diff_found = "❌ 刪除", True
                elif base_item and item and item['PN'] != base_item['PN']: 
                    status_label, diff_found = "🟡 變更", True
        
        if diff_found:
            final_data.append({
                "階層": level, 
                "變更項目": status_label, 
                "位置": ref, 
                **file_pns, 
                "規格描述": desc
            })

    if final_data:
        df = pd.DataFrame(final_data)
        cols = ["階層", "變更項目", "位置"] + list(all_maps.keys()) + ["規格描述"]
        df = df[cols]

        st.subheader(f"📋 異動分析矩陣 (基準: {base_file})")
        # 直接顯示，不添加任何自定義顏色樣式，回歸原始外觀
        st.dataframe(df, use_container_width=True, height=600)
    else:
        st.success("✨ 選定階層內所有 BOM 完全一致。")
