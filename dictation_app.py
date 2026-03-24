import streamlit as st
import random
import re
import json
import numpy as np
from PIL import Image
import easyocr
import base64

# 设置页面外观
st.set_page_config(page_title="专属英语听写", layout="centered")

# ==========================================
# 🌟 网页背景图片功能
# ==========================================
def set_background(image_file):
    try:
        with open(image_file, "rb") as f:
            encoded_string = base64.b64encode(f.read()).decode()
        
        css = f"""
        <style>
        .stApp {{
            background-image: url(data:image/jpeg;base64,{encoded_string});
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .stMainBlockContainer {{
            background-color: rgba(255, 255, 255, 0.85);
            padding: 2rem;
            border-radius: 15px;
        }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("找不到背景图片 angel.jpg，请确保它已被压缩并放在了当前文件夹中哦！")

set_background("angel.jpg")

# ==========================================

st.title("🎧 自动化分组听写器 (带 AI 视觉)")

# --- 状态初始化 ---
if 'word_list' not in st.session_state:
    st.session_state.word_list = []
if 'group_index' not in st.session_state:
    st.session_state.group_index = 0
if 'input_text' not in st.session_state:
    st.session_state.input_text = ""

# --- 加载 OCR 模型 ---
@st.cache_resource
def load_ocr_model():
    # 在云端部署时如果没有 GPU，它会自动降级使用 CPU
    return easyocr.Reader(['en'], gpu=False) 

# --- 1. 输入与设置区域 ---
with st.expander("⚙️ 第一步：导入单词与设置", expanded=not st.session_state.word_list):
    
    tab1, tab2 = st.tabs(["✍️ 粘贴文本", "📷 提取图片单词"])
    
    with tab1:
        st.session_state.input_text = st.text_area(
            "在此粘贴单词（空格、逗号或换行分隔）：", 
            value=st.session_state.input_text,
            height=150
        )
        
    with tab2:
        st.write("上传包含英文单词的截图或照片，AI 会自动帮你把单词洗出来放到文本框里。")
        uploaded_file = st.file_uploader("选择图片文件", type=['png', 'jpg', 'jpeg'])
        
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="待识别的图片", use_container_width=True)
            
            if st.button("🔍 开始提取单词", type="secondary"):
                with st.spinner("正在全力识别中..."):
                    try:
                        reader = load_ocr_model()
                        img_array = np.array(image.convert('RGB'))
                        results = reader.readtext(img_array, detail=0)
                        
                        extracted_words = []
                        for res in results:
                            found = re.findall(r'\b[a-zA-Z]{3,}\b', res)
                            extracted_words.extend(found)
                        
                        if extracted_words:
                            new_text = " ".join(extracted_words)
                            if st.session_state.input_text:
                                st.session_state.input_text += " \n" + new_text
                            else:
                                st.session_state.input_text = new_text
                            st.success(f"✅ 成功提取 {len(extracted_words)} 个单词！已自动填入左侧【粘贴文本】框中。")
                        else:
                            st.warning("图片里好像没有清晰的英文单词哦。")
                    except Exception as e:
                        st.error(f"识别出错啦: {e}")

    st.divider()
    
    col_a, col_b = st.columns(2)
    with col_a:
        group_size = st.number_input("每组听写几个单词？", min_value=5, max_value=50, value=20, step=5)
    with col_b:
        st.write("") 
        st.write("")
        if st.button("🔀 洗牌并生成听写计划", type="primary", use_container_width=True):
            if st.session_state.input_text.strip():
                words = [w.strip() for w in re.split(r'[\s,]+', st.session_state.input_text) if w.strip()]
                words = list(set(words))
                random.shuffle(words)
                
                st.session_state.word_list = words
                st.session_state.group_index = 0
                st.rerun()
            else:
                st.warning("词库是空的！请先粘贴文本或提取图片。")

st.divider()

# --- 2. 听写主控台 ---
if st.session_state.word_list:
    total_words = len(st.session_state.word_list)
    total_groups = (total_words + group_size - 1) // group_size
    curr_group_idx = st.session_state.group_index

    if curr_group_idx < total_groups:
        start_idx = curr_group_idx * group_size
        end_idx = min(start_idx + group_size, total_words)
        current_group_words = st.session_state.word_list[start_idx:end_idx]
        
        st.markdown(f"### 🎯 当前进度：第 {curr_group_idx + 1} 组 / 共 {total_groups} 组")
        st.caption(f"本组包含 {len(current_group_words)} 个单词。")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("▶️ 自动连播本组单词", use_container_width=True):
                js_words = json.dumps(current_group_words)
                js_code = f"""
                <script>
                window.speechSynthesis.cancel(); 
                const words = {js_words};
                let i = 0;
                
                function getBestVoice() {{
                    let voices = window.speechSynthesis.getVoices();
                    let preferred = [
                        "Microsoft Aria Online", 
                        "Google US English",     
                        "Microsoft Zira",        
                        "Microsoft Mark",        
                        "Samantha"               
                    ];
                    for (let name of preferred) {{
                        let v = voices.find(voice => voice.name.includes(name));
                        if (v) return v;
                    }}
                    return voices.find(voice => voice.lang === 'en-US') || voices[0];
                }}
                
                function playNext() {{
                    if (i >= words.length) {{
                        let endMsg = new SpeechSynthesisUtterance('This group is finished.');
                        endMsg.voice = getBestVoice();
                        window.speechSynthesis.speak(endMsg);
                        return;
                    }}
                    
                    let word = words[i];
                    let msg1 = new SpeechSynthesisUtterance(word);
                    let msg2 = new SpeechSynthesisUtterance(word);
                    
                    let premiumVoice = getBestVoice();
                    if (premiumVoice) {{
                        msg1.voice = premiumVoice;
                        msg2.voice = premiumVoice;
                    }}
                    
                    msg1.rate = 0.75; msg1.pitch = 1.0;
                    msg2.rate = 0.75; msg2.pitch = 1.0;

                    msg1.onend = function() {{
                        setTimeout(() => {{ window.speechSynthesis.speak(msg2); }}, 1500); 
                    }};
                    
                    msg2.onend = function() {{
                        i++;
                        setTimeout(playNext, 3000); 
                    }};
                    
                    window.speechSynthesis.speak(msg1);
                }}
                
                if (window.speechSynthesis.getVoices().length === 0) {{
                    window.speechSynthesis.onvoiceschanged = playNext;
                }} else {{
                    playNext();
                }}
                </script>
                """
                st.components.v1.html(js_code, height=0)
                st.success("🔊 正在使用高清人声播放中... (再次点击可从头重播)")

        with col2:
            if st.button("⏭️ 我已写完，进入下一组", use_container_width=True):
                st.components.v1.html("<script>window.speechSynthesis.cancel();</script>", height=0)
                st.session_state.group_index += 1
                st.rerun()
        
        st.write("")
        
        with st.expander("👀 听写结束？点击核对本组答案"):
            for i in range(0, len(current_group_words), 5):
                chunk = current_group_words[i:i+5]
                st.write(" | ".join([f"**{w}**" for w in chunk]))
                
    else:
        st.balloons()
        st.success(f"🎉 恭喜！全部 {total_words} 个单词听写完毕！")
        if st.button("再来一轮（重新洗牌）", type="primary"):
            random.shuffle(st.session_state.word_list)
            st.session_state.group_index = 0
            st.rerun()
