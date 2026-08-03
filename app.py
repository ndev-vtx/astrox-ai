import os
import json
import hashlib
import base64
import uuid
import requests
import streamlit as st
from groq import Groq
from google import genai
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image
import extra_streamlit_components as stx
from duckduckgo_search import DDGS
from tavily import TavilyClient
from exa_py import Exa
from audio_recorder_streamlit import audio_recorder
import pypdf
import docx

# --- CẤU HÌNH & TẢI BIẾN MÔI TRƯỜNG ---
load_dotenv()
ASTROX_API_KEY = st.secrets.get("ASTROX_API_KEY", os.getenv("ASTROX_API_KEY"))
INVISIBLE_API_KEY = st.secrets.get("INVISIBLE_API_KEY", os.getenv("INVISIBLE_API_KEY"))
TAVILY_API_KEY = st.secrets.get("TAVILY_API_KEY", os.getenv("TAVILY_API_KEY"))
EXA_API_KEY = st.secrets.get("EXA_API_KEY", os.getenv("EXA_API_KEY"))

LOGO_FILE = "astrox_logo.png"

st.set_page_config(
    page_title="Astrox AI",
    page_icon=LOGO_FILE if os.path.exists(LOGO_FILE) else "✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

cookie_manager = stx.CookieManager()

# --- TỪ ĐIỂN ĐA NGÔN NGỮ (i18n) ---
LANG = {
    "vi": {
        "new_chat": "➕ Cuộc trò chuyện mới",
        "choose_model": "⚡ Chọn mô hình AI:",
        "web_search": "🌐 Tìm kiếm Web",
        "search_hist_placeholder": "🔍 Tìm kiếm lịch sử...",
        "chat_hist": "LỊCH SỬ TRÒ CHUYỆN",
        "no_hist": "Chưa có lịch sử chat.",
        "profile": "⚙️ Hồ sơ",
        "logout": "🚪 Thoát",
        "login": "Đăng nhập",
        "register": "Đăng ký",
        "username": "Tên đăng nhập",
        "password": "Mật khẩu",
        "pass_confirm": "Xác nhận mật khẩu",
        "btn_login": "Đăng nhập",
        "btn_reg": "Tạo tài khoản & Bắt đầu",
        "welcome": "Xin chào, ",
        "help_today": "Hôm nay Astrox AI có thể giúp gì cho bạn?",
        "chat_placeholder": "Hỏi Astrox AI bất kỳ điều gì...",
        "add_attachment": "➕ Đính kèm",
        "add_image": "🖼️ Thêm ảnh (JPG, PNG)",
        "upload_file": "📄 Tải tệp lên (PDF, DOCX, TXT)",
        "mic_hint": "Bấm để thu âm",
        "voice_converted": "Đã nghe: ",
        "search_status": "🔍 Đang tìm kiếm thông tin trên Web...",
        "attached_img": "🖼️ Đã đính kèm ảnh:",
        "attached_doc": "📄 Tài liệu đã đính kèm:",
        "confirm_delete": "Bạn có chắc chắn muốn xóa cuộc trò chuyện này?",
        "del_permanently": "Xóa vĩnh viễn",
        "cancel": "Hủy",
        "settings": "Cài đặt tài khoản",
        "update_avatar": "Cập nhật ảnh đại diện",
        "back_chat": "← Quay lại trò chuyện",
        "idea_title": "💡 Ý tưởng sáng tạo",
        "idea_desc": "Gợi ý kịch bản video hoặc viết bài blog hấp dẫn",
        "code_title": "💻 Lập trình & Code",
        "code_desc": "Viết code Python, HTML hoặc sửa lỗi lập trình",
        "search_title": "🌐 Tìm kiếm thông tin",
        "search_desc": "Tin tức mới nhất về công nghệ và AI hiện nay",
        "try_this": "Thử gợi ý này"
    },
    "en": {
        "new_chat": "➕ New Chat",
        "choose_model": "⚡ Choose AI Model:",
        "web_search": "🌐 Web Search",
        "search_hist_placeholder": "🔍 Search history...",
        "chat_hist": "CHAT HISTORY",
        "no_hist": "No chat history yet.",
        "profile": "⚙️ Profile",
        "logout": "🚪 Logout",
        "login": "Login",
        "register": "Register",
        "username": "Username",
        "password": "Password",
        "pass_confirm": "Confirm Password",
        "btn_login": "Login",
        "btn_reg": "Create Account & Start",
        "welcome": "Hello, ",
        "help_today": "How can Astrox AI help you today?",
        "chat_placeholder": "Ask Astrox AI anything...",
        "add_attachment": "➕ Attach",
        "add_image": "🖼️ Add Image (JPG, PNG)",
        "upload_file": "📄 Upload File (PDF, DOCX, TXT)",
        "mic_hint": "Click to record",
        "voice_converted": "Heard: ",
        "search_status": "🔍 Searching the Web...",
        "attached_img": "🖼️ Image attached:",
        "attached_doc": "📄 Document attached:",
        "confirm_delete": "Are you sure you want to delete this chat?",
        "del_permanently": "Delete Permanently",
        "cancel": "Cancel",
        "settings": "Account Settings",
        "update_avatar": "Update Avatar",
        "back_chat": "← Back to chat",
        "idea_title": "💡 Creative Ideas",
        "idea_desc": "Suggest video scripts or engaging blog posts",
        "code_title": "💻 Programming & Code",
        "code_desc": "Write Python, HTML or fix coding bugs",
        "search_title": "🌐 Search Information",
        "search_desc": "Latest news on tech and AI trends",
        "try_this": "Try this"
    }
}

# --- KHỞI TẠO TRẠNG THÁI PHIÊN (SESSION STATE) ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_account_page" not in st.session_state:
    st.session_state.show_account_page = False
if "chat_to_delete" not in st.session_state:
    st.session_state.chat_to_delete = None
if "pending_attachment" not in st.session_state:
    st.session_state.pending_attachment = None
if "lang" not in st.session_state:
    st.session_state.lang = "vi"
if "theme" not in st.session_state:
    st.session_state.theme = "light"

t = LANG[st.session_state.lang] # Biến t chứa ngôn ngữ hiện tại

# --- CSS ĐỘNG CHO DARK/LIGHT MODE ---
def inject_theme_css():
    if st.session_state.theme == "dark":
        css = """
        <style>
            .stApp, [data-testid="stAppViewContainer"] { background-color: #0d1117 !important; color: #f0f6fc !important; }
            [data-testid="stSidebar"] { background-color: #161b22 !important; border-right: 1px solid #30363d !important; }
            .suggestion-card { background-color: #161b22 !important; border: 1px solid #30363d !important; color: #f0f6fc !important; }
            .suggestion-card span { color: #8b949e !important; }
            .stChatInputContainer { border: 1px solid #30363d !important; background-color: #161b22 !important; }
            textarea { color: #f0f6fc !important; }
            p, h1, h2, h3, h4, h5, h6, span, label { color: #f0f6fc !important; }
            .stPopoverContent { background-color: #161b22 !important; border: 1px solid #30363d !important; }
        </style>
        """
    else:
        css = """
        <style>
            .stApp, [data-testid="stAppViewContainer"] { background-color: #ffffff !important; color: #1f2328 !important; }
            [data-testid="stSidebar"] { background-color: #f6f8fa !important; border-right: 1px solid #d0d7de !important; }
            .suggestion-card { background-color: #f6f8fa !important; border: 1px solid #d0d7de !important; color: #1f2328 !important; }
            .suggestion-card span { color: #57606a !important; }
            .stChatInputContainer { border: 1px solid #d0d7de !important; }
            p, h1, h2, h3, h4, h5, h6, span, label { color: #1f2328 !important; }
        </style>
        """
    
    st.markdown("""
    <style>
        .suggestion-card { border-radius: 12px; padding: 16px; margin-bottom: 12px; }
        .stChatInputContainer { border-radius: 24px !important; }
        .toolbar-container { display: flex; gap: 10px; margin-bottom: 5px; padding-left: 10px; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(css, unsafe_allow_html=True)

inject_theme_css()

# --- DATABASE TẠM ---
DB_FILE = "users_db.json"
CHATS_FILE = "chats_db.json"
IP_DB_FILE = "ip_db.json"

def load_db(file_name):
    if not os.path.exists(file_name): return {}
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except: return {}

def save_db(data, file_name):
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- XỬ LÝ FILE ---
def extract_text_from_file(uploaded_file):
    try:
        filename = uploaded_file.name.lower()
        if filename.endswith(".pdf"):
            reader = pypdf.PdfReader(uploaded_file)
            return "".join([p.extract_text() for p in reader.pages if p.extract_text()])
        elif filename.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            return "\n".join([p.text for p in doc.paragraphs if p.text])
        elif filename.endswith((".txt", ".py", ".json", ".md", ".csv", ".html")):
            return uploaded_file.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return f"File error: {e}"
    return ""

def image_to_base64(image):
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def base64_to_image(base64_str):
    if not base64_str: return None
    try: return Image.open(BytesIO(base64.b64decode(base64_str)))
    except: return None

# --- CHỨC NĂNG ACCOUNT & LOGIC ---
def hash_password(password): return hashlib.sha256(str.encode(password)).hexdigest()
def get_user_search_count(username): return load_db(DB_FILE).get(username, {}).get("search_count", 0)
def increment_user_search_count(username):
    users = load_db(DB_FILE)
    if username in users:
        users[username]["search_count"] = users[username].get("search_count", 0) + 1
        save_db(users, DB_FILE)

# (Các hàm search, auth... giữ nguyên logic)
def search_web_multi_fallback(query, username):
    try:
        res = search_duckduckgo(query)
        return res, "DuckDuckGo"
    except: return "", ""
def search_duckduckgo(query):
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=4):
            results.append(f"Title: {r.get('title')}\nContent: {r.get('body')}")
    return "\n\n".join(results)

def transcribe_audio_with_groq(audio_bytes):
    if not ASTROX_API_KEY: return ""
    try:
        client = Groq(api_key=ASTROX_API_KEY)
        transcription = client.audio.transcriptions.create(
            file=("speech.wav", audio_bytes), model="whisper-large-v3-turbo", response_format="text", language=st.session_state.lang
        )
        return str(transcription).strip()
    except: return ""

saved_user = cookie_manager.get('astrox_logged_user')
if saved_user and not st.session_state.logged_in:
    users_db = load_db(DB_FILE)
    if saved_user in users_db:
        st.session_state.logged_in = True
        st.session_state.username = saved_user

# --- ĐĂNG NHẬP / ĐĂNG KÝ ---
if not st.session_state.logged_in:
    st.write("<br><br>", unsafe_allow_html=True)
    c_left, c_mid, c_right = st.columns([1, 2, 1])
    with c_mid:
        if os.path.exists(LOGO_FILE): st.image(LOGO_FILE, width=90)
        st.title("Astrox AI")
        st.write("---")
        # Chọn ngôn ngữ ngoài màn hình đăng nhập
        col_lg1, col_lg2 = st.columns(2)
        with col_lg1:
             if st.radio("Language / Ngôn ngữ:", ["Tiếng Việt", "English"], horizontal=True) == "English":
                 st.session_state.lang = "en"
             else:
                 st.session_state.lang = "vi"
             t = LANG[st.session_state.lang]

        tab_login, tab_register = st.tabs([t["login"], t["register"]])
        with tab_login:
            l_user = st.text_input(t["username"], key="login_user")
            l_pass = st.text_input(t["password"], type="password", key="login_pass")
            if st.button(t["btn_login"], type="primary", use_container_width=True):
                users = load_db(DB_FILE)
                if l_user in users and users[l_user].get("password") == hash_password(l_pass):
                    st.session_state.logged_in = True
                    st.session_state.username = l_user
                    cookie_manager.set('astrox_logged_user', l_user)
                    st.rerun()
                else: st.error("Error/Lỗi!")

        with tab_register:
            r_user = st.text_input(t["username"] + " (New)", key="reg_user")
            r_pass = st.text_input(t["password"] + " (New)", type="password", key="reg_pass")
            if st.button(t["btn_reg"], type="primary", use_container_width=True):
                users = load_db(DB_FILE)
                if r_user not in users:
                    users[r_user] = {"password": hash_password(r_pass), "avatar_base64": "", "search_count": 0}
                    save_db(users, DB_FILE)
                    st.session_state.logged_in = True
                    st.session_state.username = r_user
                    cookie_manager.set('astrox_logged_user', r_user)
                    st.rerun()
                else: st.error("Exist/Đã tồn tại!")

# --- GIAO DIỆN CHÍNH ---
else:
    # --- SIDEBAR ---
    with st.sidebar:
        col_theme, col_lang = st.columns(2)
        with col_theme:
            theme_choice = st.toggle("🌙 Dark Mode", value=(st.session_state.theme == "dark"))
            new_theme = "dark" if theme_choice else "light"
            if new_theme != st.session_state.theme:
                st.session_state.theme = new_theme
                st.rerun()
        with col_lang:
            lang_choice = st.toggle("🇺🇸 English", value=(st.session_state.lang == "en"))
            new_lang = "en" if lang_choice else "vi"
            if new_lang != st.session_state.lang:
                st.session_state.lang = new_lang
                st.rerun()

        st.divider()

        if st.button(t["new_chat"], use_container_width=True, type="primary"):
            st.session_state.current_chat_id = None
            st.session_state.messages = []
            st.session_state.pending_attachment = None
            st.rerun()
        
        st.markdown("<br>", unsafe_allow_html=True)
        model_choice = st.selectbox(t["choose_model"], ["✨ Invisible 4.0", "🚀 Invisible 3.6", "⚡ Invisible-flash 3.5"])
        
        rem_search = max(0, 100 - get_user_search_count(st.session_state.username))
        enable_search = st.toggle(f"{t['web_search']} ({rem_search}/100)", value=False)
        search_kw = st.text_input("🔍", key="search_kw", label_visibility="collapsed", placeholder=t["search_hist_placeholder"])

        st.caption(t["chat_hist"])
        chats_db = load_db(CHATS_FILE).get(st.session_state.username, {})
        filtered_chats = {k: v for k, v in chats_db.items() if not search_kw or search_kw.lower() in v.get("title", "").lower()}
        
        if not filtered_chats: st.caption(t["no_hist"])
        for c_id, c_data in reversed(list(filtered_chats.items())):
            c_title = c_data.get("title", "Chat")[:18] + "..."
            col1, col2 = st.columns([4, 1])
            with col1:
                btn_icon = "✨ " if c_id == st.session_state.current_chat_id else "💬 "
                if st.button(btn_icon + c_title, key=f"chat_{c_id}", use_container_width=True):
                    st.session_state.current_chat_id, st.session_state.messages = c_id, c_data["messages"]
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_{c_id}"):
                    del chats_db[c_id]
                    all_chats = load_db(CHATS_FILE)
                    all_chats[st.session_state.username] = chats_db
                    save_db(all_chats, CHATS_FILE)
                    if st.session_state.current_chat_id == c_id:
                        st.session_state.current_chat_id, st.session_state.messages = None, []
                    st.rerun()

        st.divider()
        users = load_db(DB_FILE)
        av_b64 = users.get(st.session_state.username, {}).get("avatar_base64", "")
        av_img = base64_to_image(av_b64)
        c_av, c_name = st.columns([1, 2])
        with c_av:
            if av_img: st.image(av_img, width=45)
            else: st.markdown("👤")
        with c_name: st.markdown(f"**{st.session_state.username}**")

        ca, cl = st.columns([1, 1])
        with ca:
            if st.button(t["profile"], use_container_width=True):
                st.session_state.show_account_page = not st.session_state.show_account_page
                st.rerun()
        with cl:
            if st.button(t["logout"], use_container_width=True):
                st.session_state.logged_in, st.session_state.username = False, ""
                cookie_manager.delete('astrox_logged_user')
                st.rerun()

    # --- KHU VỰC CHAT ---
    if st.session_state.show_account_page:
        st.header(t["settings"])
        up_img = st.file_uploader(t["update_avatar"], type=["png", "jpg"])
        if up_img:
            i = Image.open(up_img)
            i.thumbnail((200, 200))
            users = load_db(DB_FILE)
            users[st.session_state.username]["avatar_base64"] = image_to_base64(i)
            save_db(users, DB_FILE)
            st.success("OK!")
            st.rerun()
        if st.button(t["back_chat"]):
            st.session_state.show_account_page = False
            st.rerun()
    else:
        if not st.session_state.messages:
            st.write("<br><br>", unsafe_allow_html=True)
            st.markdown(f"# <span style='color:#0969da;'>{t['welcome']}{st.session_state.username}</span>", unsafe_allow_html=True)
            st.markdown(f"### {t['help_today']}")
            st.write("<br>", unsafe_allow_html=True)

            col_g1, col_g2, col_g3 = st.columns(3)
            prompt_preset = None
            with col_g1:
                st.markdown(f'<div class="suggestion-card"><b>{t["idea_title"]}</b><br><span>{t["idea_desc"]}</span></div>', unsafe_allow_html=True)
                if st.button(t["try_this"], key="p1", use_container_width=True): prompt_preset = "Give me 3 creative video ideas." if st.session_state.lang == "en" else "Gợi ý 3 kịch bản video."
            with col_g2:
                st.markdown(f'<div class="suggestion-card"><b>{t["code_title"]}</b><br><span>{t["code_desc"]}</span></div>', unsafe_allow_html=True)
                if st.button(t["try_this"], key="p2", use_container_width=True): prompt_preset = "Write a Python script for web scraping." if st.session_state.lang == "en" else "Viết script Python tải web."
            with col_g3:
                st.markdown(f'<div class="suggestion-card"><b>{t["search_title"]}</b><br><span>{t["search_desc"]}</span></div>', unsafe_allow_html=True)
                if st.button(t["try_this"], key="p3", use_container_width=True): prompt_preset = "Latest AI news this week." if st.session_state.lang == "en" else "Tin tức AI mới nhất tuần này."
        else:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    if message.get("image_base64"):
                        img = base64_to_image(message["image_base64"])
                        if img: st.image(img, width=300)

        # --- THANH CÔNG CỤ TÍCH HỢP GEMINI STYLE ---
        # Hiển thị Preview File
        if st.session_state.pending_attachment:
            att = st.session_state.pending_attachment
            col_inf, col_del = st.columns([9, 1])
            with col_inf:
                if att["type"] == "image":
                    st.image(att["bytes"], caption=f"{t['attached_img']} {att['name']}", width=80)
                else: st.info(f"{t['attached_doc']} {att['name']}")
            with col_del:
                if st.button("❌"):
                    st.session_state.pending_attachment = None
                    st.rerun()

        # Thanh Toolbar Nằm sát Input
        st.markdown('<div class="toolbar-container">', unsafe_allow_html=True)
        t_col1, t_col2, t_col3 = st.columns([0.5, 0.5, 9])
        voice_text = ""
        
        with t_col1:
            with st.popover(t["add_attachment"]):
                st.write("**" + t["add_image"] + "**")
                img_file = st.file_uploader("", type=["png", "jpg", "jpeg"], key="up_img")
                st.write("---")
                st.write("**" + t["upload_file"] + "**")
                doc_file = st.file_uploader("", type=["pdf", "docx", "txt", "md"], key="up_doc")
                
                if img_file:
                    st.session_state.pending_attachment = {"type": "image", "name": img_file.name, "bytes": img_file.getvalue()}
                    st.rerun()
                elif doc_file:
                    st.session_state.pending_attachment = {"type": "doc", "name": doc_file.name, "bytes": doc_file.getvalue(), "file_obj": doc_file}
                    st.rerun()

        with t_col2:
            audio_bytes = audio_recorder(text="", recording_color="#e8b1b5", neutral_color="#6aa3b8", icon_size="1x")
            if audio_bytes:
                with st.spinner("..."):
                    voice_text = transcribe_audio_with_groq(audio_bytes)
        st.markdown('</div>', unsafe_allow_html=True)

        prompt_input = st.chat_input(t["chat_placeholder"])
        prompt = prompt_input or voice_text or (prompt_preset if 'prompt_preset' in locals() else None)

        # XỬ LÝ GỬI TIN NHẮN
        if prompt:
            active_att = st.session_state.pending_attachment
            st.session_state.pending_attachment = None

            pil_image, img_b64, doc_text = None, "", ""
            if active_att:
                if active_att["type"] == "image":
                    pil_image = Image.open(BytesIO(active_att["bytes"]))
                    img_b64 = image_to_base64(pil_image)
                elif active_att["type"] == "doc":
                    doc_text = extract_text_from_file(active_att["file_obj"])

            display_prompt = prompt
            if active_att and active_att["type"] == "doc":
                display_prompt += f"\n\n*(📎 {t['attached_doc']} {active_att['name']})*"

            user_msg = {"role": "user", "content": display_prompt}
            if img_b64: user_msg["image_base64"] = img_b64
            st.session_state.messages.append(user_msg)
            
            if not st.session_state.current_chat_id: st.session_state.current_chat_id = str(uuid.uuid4())

            with st.chat_message("user"):
                st.markdown(display_prompt)
                if pil_image: st.image(pil_image, width=300)

            with st.chat_message("assistant"):
                s_context = ""
                if enable_search:
                    with st.status(t["search_status"], expanded=False):
                        s_res, p_used = search_web_multi_fallback(prompt, st.session_state.username)
                        if s_res: s_context = f"\n\n[Web Data ({p_used})]:\n{s_res}"

                sys_inst = "You are Astrox AI. Answer based on the language requested."
                final_prompt = prompt
                if doc_text: final_prompt += f"\n\n[Document content]:\n{doc_text[:12000]}"
                response = ""

                if "Invisible 4.0" in model_choice or "Invisible 3.6" in model_choice:
                    if not INVISIBLE_API_KEY: response = "API Key Error"
                    else:
                        try:
                            gemini_client = genai.Client(api_key=INVISIBLE_API_KEY)
                            payload = [pil_image] if pil_image else []
                            payload.append(final_prompt + s_context)
                            res = gemini_client.models.generate_content(model='gemini-2.5-flash', contents=payload)
                            response = res.text
                        except Exception as e: response = f"Gemini Error: {e}"
                else:
                    if pil_image: st.warning("Groq doesn't support images yet.")
                    if not ASTROX_API_KEY: response = "API Key Error"
                    else:
                        try:
                            client = Groq(api_key=ASTROX_API_KEY)
                            msgs = [{"role": "system", "content": sys_inst}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[:-1]] + [{"role": "user", "content": final_prompt + s_context}]
                            comp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs)
                            response = comp.choices[0].message.content
                        except Exception as e: response = f"Groq Error: {e}"
                
                st.markdown(response)

            st.session_state.messages.append({"role": "assistant", "content": response})
            
            # Save Chat
            all_c = load_db(CHATS_FILE)
            if st.session_state.username not in all_c: all_c[st.session_state.username] = {}
            chat_title = all_c[st.session_state.username].get(st.session_state.current_chat_id, {}).get("title", prompt[:30])
            all_c[st.session_state.username][st.session_state.current_chat_id] = {"title": chat_title, "messages": st.session_state.messages}
            save_db(all_c, CHATS_FILE)
            st.rerun()
