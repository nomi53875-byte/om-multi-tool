import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="BOM 多批次異動分析矩陣", layout="wide")

# --- 介面樣式 ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 150px; max-width: 180px; }
    .stCheckbox { margin-bottom: -12px; }
    [data-testid="stDataFrame"] td { text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 BOM 多批次異動分析矩陣 (穩定邏輯版)")

with st.sidebar:
    st.subheader("階層篩選")
    selected_levels = []
    for i in range(1, 7):
        if st.checkbox(f"L{i}", value=True if i in [3, 4, 5] else False, key=f"ML{i}"):
            selected_levels.append(i)

# --- 使用 4.txt 時代穩定的解析器 ---
def parse_bom_stable(file_bytes):
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
    all_maps = {f.name: parse_bom_stable(f.getvalue()) for f in files}
    base_file = st.selectbox("請指定基準 BOM (Master):", options=list(all_maps.keys()))
    
    # 取得位置聯集並排序
    all_refs = sorted(list(set().union(*(m.keys() for m in all_maps.values()))), 
                      key=lambda x: (re.sub(r'\d+', '', x), int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0))

    final_rows = []
    for ref in all_refs:
        base_item = all_maps[base_file].get(ref)
        # 決定這一行應該顯示的階層與規格
        level = base_item['Level'] if base_item else next((all_maps[f][ref]['Level'] for f in all_maps if ref in all_maps[f]), None)
        desc = base_item['Desc'] if base_item else next((all_maps[f][ref]['Desc'] for f in all_maps if ref in all_maps[f]), "")

        if level not in selected_levels: continue

        file_pns = {}
        status_icon = "✅"
        status_text = "無差異"
        
        # 進行多檔橫向比對
        diff_detected = False
        for fname in all_maps:
            item = all_maps[fname].get(ref)
            pn = item['PN'] if item else "---"
            file_pns[fname] = pn
            
            if fname != base_file:
                if not base_item and item: 
                    status_icon, status_text, diff_detected = "🔵", "新增", True
                elif base_item and not item: 
                    status_icon, status_text, diff_detected = "🔴", "刪除", True
                elif base_item and item and item['PN'] != base_item['PN']: 
                    status_icon, status_text, diff_detected = "🟡", "變更", True
        
        if diff_detected:
            final_rows.append({
                "階層": level,
                "變更項目": f"{status_icon} {status_text}",
                "位置": ref,
                **file_pns,
                "規格描述": desc
            })

    if final_rows:
        df = pd.DataFrame(final_rows)
        # 排序與 4.txt 保持一致
        cols = ["階層", "變更項目", "位置"] + list(all_maps.keys()) + ["規格描述"]
        df = df[cols]

        # --- 僅針對文字與圖標上色，底色保持原本樣子 ---
        def apply_stable_styles(row):
            styles = [''] * len(row)
            status = row['變更項目']
            
            color = ""
            if "🟡" in status: color = "#D4A017" # 黃褐色
            elif "🔵" in status: color = "#0056b3" # 深藍色
            elif "🔴" in status: color = "#c82333" # 深紅色

            for i, col_name in enumerate(row.index):
                if col_name == "變更項目":
                    styles[i] = f"color: {color}; font-weight: bold;"
                elif col_name in all_maps.keys():
                    if row[col_name] != row[base_file]:
                        styles[i] = f"color: {color}; font-weight: bold;"
                elif col_name in ["階層", "位置"]:
                    styles[i] = "text-align: center;"
            return styles

        st.subheader(f"📋 異動分析矩陣 (以 {base_file} 為基準)")
        st.dataframe(df.style.apply(apply_stable_styles, axis=1), use_container_width=True, height=600)
    else:
        st.success("✨ 所選階層內所有 BOM 內容一致。")
