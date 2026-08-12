import os
import json
import hashlib
import base64
import uuid
from io import BytesIO
from PIL import Image
import requests

import streamlit as st
from dotenv import load_dotenv

# Thư viện AI (Dùng chuẩn OpenAI Client cho OpenRouter) & Tìm kiếm
from openai import OpenAI
from duckduckgo_search import DDGS

# Thư viện bổ trợ Streamlit & Đọc file
import extra_streamlit_components as stx
from audio_recorder_streamlit import audio_recorder
import pypdf
import docx

# ==========================================
# 1. CẤU HÌNH BAN ĐẦU & LẤY SECRET AN TOÀN
# ==========================================
load_dotenv()

def get_secret(key_name, default=""):
    candidates = [key_name, key_name.lower(), key_name.upper()]
    try:
        if hasattr(st, "secrets") and st.secrets:
            for k in candidates:
                if k in st.secrets and st.secrets[k]:
                    val = str(st.secrets[k]).strip().strip('"').strip("'")
                    if val: return val
            for sec_k, sec_v in st.secrets.items():
                if isinstance(sec_v, dict):
                    for k in candidates:
                        if k in sec_v and sec_v[k]:
                            val = str(sec_v[k]).strip().strip('"').strip("'")
                            if val: return val
    except Exception:
        pass

    for k in candidates:
        val = os.getenv(k)
        if val:
            val_clean = str(val).strip().strip('"').strip("'")
            if val_clean: return val_clean

    return default

# Lấy Key & Base URL cho OpenRouter
OPENROUTER_API_KEY = get_secret("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = get_secret("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Phụ trợ (Ghi âm / Key phụ nếu có)
ASTROX_API_KEY = get_secret("ASTROX_API_KEY")

# Khởi tạo OpenAI Client kết nối tới OpenRouter
client_openrouter = None
if OPENROUTER_API_KEY:
    client_openrouter = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL
    )

LOGO_FILE = "astrox_logo.png"

st.set_page_config(
    page_title="Astrox AI",
    page_icon=LOGO_FILE if os.path.exists(LOGO_FILE) else "✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

try:
    cookie_manager = stx.CookieManager(key="astrox_cookie_mgr")
except Exception:
    cookie_manager = None

# ==========================================
# 2. TỪ ĐIỂN ĐA NGÔN NGỮ (i18n)
# ==========================================
LANG = {
    "vi": {
        "new_chat": "➕ Cuộc trò chuyện mới",
        "choose_model": "⚡ Chọn mô hình AI:",
        "web_search": "🌐 Tìm kiếm Web",
        "search_provider": "⚙️ Công cụ tìm kiếm:",
        "search_hist_placeholder": "🔍 Tìm kiếm lịch sử...",
        "chat_hist": "LỊCH SỬ TRÒ CHUYỆN",
        "no_hist": "Chưa có lịch sử chat nào.",
        "profile": "⚙️ Hồ sơ cá nhân",
        "logout": "🚪 Đăng xuất",
        "login": "Đăng nhập",
        "register": "Đăng ký",
        "username": "Tên đăng nhập",
        "password": "Mật khẩu",
        "btn_login": "Đăng nhập",
        "btn_reg": "Tạo tài khoản & Bắt đầu",
        "welcome": "Xin chào, ",
        "help_today": "Hôm nay Astrox AI có thể giúp gì cho bạn?",
        "chat_placeholder": "Nhập tin nhắn hoặc hỏi bất kỳ điều gì...",
        "add_attachment": "Thêm tệp đính kèm",
        "search_status": "🔍 Đang tìm kiếm thông tin trên Web...",
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
        "search_provider": "⚙️ Search Provider:",
        "search_hist_placeholder": "🔍 Search history...",
        "chat_hist": "CHAT HISTORY",
        "no_hist": "No chat history yet.",
        "profile": "⚙️ Profile Settings",
        "logout": "🚪 Logout",
        "login": "Login",
        "register": "Register",
        "username": "Username",
        "password": "Password",
        "btn_login": "Login",
        "btn_reg": "Create Account & Start",
        "welcome": "Hello, ",
        "help_today": "How can Astrox AI help you today?",
        "chat_placeholder": "Ask Astrox AI anything...",
        "add_attachment": "Add attachment",
        "search_status": "🔍 Searching the Web...",
        "settings": "Account Settings",
        "update_avatar": "Update Profile Picture",
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

# ==========================================
# 3. KHỞI TẠO SESSION STATE & CSS
# ==========================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = ""
if "current_chat_id" not in st.session_state: st.session_state.current_chat_id = None
if "messages" not in st.session_state: st.session_state.messages = []
if "show_account_page" not in st.session_state: st.session_state.show_account_page = False
if "lang" not in st.session_state: st.session_state.lang = "vi"

t = LANG[st.session_state.lang]

def inject_custom_css():
    css = """
    <style>
        .stApp, [data-testid="stAppViewContainer"] { background-color: #ffffff !important; color: #1f2328 !important; }
        [data-testid="stSidebar"] { background-color: #f6f8fa !important; border-right: 1px solid #d0d7de !important; }
        .suggestion-card { background-color: #f6f8fa !important; border: 1px solid #d0d7de !important; color: #1f2328 !important; border-radius: 12px; padding: 16px; margin-bottom: 12px; min-height: 100px;}
        .suggestion-card span { color: #57606a !important; font-size: 0.9em; }
        .stChatInputContainer { border-radius: 20px !important; border: 1px solid #d0d7de !important; }
        p, h1, h2, h3, h4, h5, h6, span, label { color: #1f2328 !important; }
        [data-testid="stBottomBlockContainer"] { padding-bottom: 12px !important; }
        [data-testid="stSidebarNav"] { display: none; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

inject_custom_css()

# ==========================================
# 4. HÀM DATABASE JSON & FILE
# ==========================================
DB_FILE = "users_db.json"
CHATS_FILE = "chats_db.json"

def load_db(file_name):
    if not os.path.exists(file_name): return {}
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_db(data, file_name):
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"Lỗi lưu dữ liệu: {e}")

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def image_to_base64(image):
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def base64_to_image(base64_str):
    if not base64_str: return None
    try:
        return Image.open(BytesIO(base64.b64decode(base64_str)))
    except Exception:
        return None

# ==========================================
# 5. TÌM KIẾM WEB (DUCKDUCKGO)
# ==========================================
def search_duckduckgo(query):
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=4):
                results.append(f"📌 **{r.get('title')}**\n{r.get('body')}")
        return "\n\n".join(results) if results else "Không tìm thấy kết quả phù hợp từ DuckDuckGo."
    except Exception as e:
        return f"Lỗi DuckDuckGo Search: {e}"

# ==========================================
# 6. GIAO DIỆN CHƯA ĐĂNG NHẬP
# ==========================================
if not st.session_state.logged_in:
    st.write("<br><br>", unsafe_allow_html=True)
    c_left, c_mid, c_right = st.columns([1, 2, 1])
    with c_mid:
        if os.path.exists(LOGO_FILE):
            st.image(LOGO_FILE, width=80)
        st.title("Astrox AI")
        st.write("---")
        
        lang_sel = st.radio("Language / Ngôn ngữ:", ["Tiếng Việt", "English"], horizontal=True)
        st.session_state.lang = "en" if lang_sel == "English" else "vi"
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
                    st.rerun()
                else:
                    st.error("Tên đăng nhập hoặc mật khẩu không chính xác!")

        with tab_register:
            r_user = st.text_input(t["username"] + " (Mới)", key="reg_user")
            r_pass = st.text_input(t["password"] + " (Mới)", type="password", key="reg_pass")
            if st.button(t["btn_reg"], type="primary", use_container_width=True):
                if not r_user or not r_pass:
                    st.warning("Vui lòng điền đầy đủ thông tin!")
                else:
                    users = load_db(DB_FILE)
                    if r_user not in users:
                        users[r_user] = {"password": hash_password(r_pass), "avatar_base64": ""}
                        save_db(users, DB_FILE)
                        st.session_state.logged_in = True
                        st.session_state.username = r_user
                        st.rerun()
                    else:
                        st.error("Tên đăng nhập này đã tồn tại!")

# ==========================================
# 7. GIAO DIỆN CHÍNH (ĐÃ ĐĂNG NHẬP)
# ==========================================
else:
    # --- SIDEBAR ---
    with st.sidebar:
        c_logo, c_title = st.columns([1, 4])
        with c_logo:
            if os.path.exists(LOGO_FILE):
                st.image(LOGO_FILE, width=40)
            else:
                st.markdown("## ✨")
        with c_title:
            st.markdown("<h3 style='margin: 0; padding-top: 5px;'>Astrox AI</h3>", unsafe_allow_html=True)
            
        st.divider()

        lang_choice = st.toggle("🇺🇸 English Mode", value=(st.session_state.lang == "en"))
        new_lang = "en" if lang_choice else "vi"
        if new_lang != st.session_state.lang:
            st.session_state.lang = new_lang
            st.rerun()

        if st.button(t["new_chat"], use_container_width=True, type="primary"):
            st.session_state.current_chat_id = None
            st.session_state.messages = []
            st.rerun()
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 📌 DANH SÁCH MÔ HÌNH CHUẨN OPENROUTER (KÈM CÁC BẢN MIỄN PHÍ RẤT MẠNH)
       # Danh sách Model ID mới nhất đã cập nhật cho OpenRouter
       # 1. Danh sách mô hình AI duy nhất (DeepSeek V3 & GPT-4o Mini)
MODEL_MAPPING = {
    "🧠 nknbel V3": "deepseek/deepseek-chat",
    "Orchesta 4": "openai/gpt-4o-mini"
}
        
        model_choice = st.selectbox(t["choose_model"], list(MODEL_MAPPING.keys()))
        
        enable_search = st.toggle(f"{t['web_search']} (DuckDuckGo)", value=False)

        with st.expander("🔑 Trạng thái API Key", expanded=False):
            st.caption(f"• **OpenRouter API:** {'✅ Đã cấu hình' if OPENROUTER_API_KEY else '❌ Chưa có Key'}")

        search_kw = st.text_input("🔍", key="search_kw", label_visibility="collapsed", placeholder=t["search_hist_placeholder"])

        st.caption(t["chat_hist"])
        chats_db = load_db(CHATS_FILE).get(st.session_state.username, {})
        filtered_chats = {k: v for k, v in chats_db.items() if not search_kw or search_kw.lower() in v.get("title", "").lower()}
        
        if not filtered_chats:
            st.caption(t["no_hist"])
            
        for c_id, c_data in reversed(list(filtered_chats.items())):
            c_title = c_data.get("title", "Chat")[:18] + "..."
            col1, col2 = st.columns([4, 1])
            with col1:
                btn_icon = "✨ " if c_id == st.session_state.current_chat_id else "💬 "
                if st.button(btn_icon + c_title, key=f"chat_{c_id}", use_container_width=True):
                    st.session_state.current_chat_id = c_id
                    st.session_state.messages = c_data["messages"]
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_{c_id}"):
                    del chats_db[c_id]
                    all_chats = load_db(CHATS_FILE)
                    all_chats[st.session_state.username] = chats_db
                    save_db(all_chats, CHATS_FILE)
                    if st.session_state.current_chat_id == c_id:
                        st.session_state.current_chat_id = None
                        st.session_state.messages = []
                    st.rerun()

        st.divider()
        users = load_db(DB_FILE)
        av_b64 = users.get(st.session_state.username, {}).get("avatar_base64", "")
        av_img = base64_to_image(av_b64)
        
        c_av, c_name = st.columns([1, 2])
        with c_av:
            if av_img: st.image(av_img, width=40)
            else: st.markdown("👤")
        with c_name:
            st.markdown(f"**{st.session_state.username}**")

        ca, cl = st.columns([1, 1])
        with ca:
            if st.button(t["profile"], use_container_width=True):
                st.session_state.show_account_page = not st.session_state.show_account_page
                st.rerun()
        with cl:
            if st.button(t["logout"], use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.rerun()

    # --- NỘI DUNG CHÍNH ---
    if st.session_state.show_account_page:
        st.header(t["settings"])
        up_img = st.file_uploader(t["update_avatar"], type=["png", "jpg", "jpeg"])
        if up_img:
            i = Image.open(up_img)
            i.thumbnail((200, 200))
            users = load_db(DB_FILE)
            if st.session_state.username in users:
                users[st.session_state.username]["avatar_base64"] = image_to_base64(i)
                save_db(users, DB_FILE)
                st.success("Đã cập nhật ảnh đại diện thành công!")
                st.rerun()
        if st.button(t["back_chat"]):
            st.session_state.show_account_page = False
            st.rerun()
            
    else:
        prompt_preset = None
        
        if not st.session_state.messages:
            st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
            st.markdown(f"<h1 style='color:#0969da; margin-bottom: 5px;'>{t['welcome']}{st.session_state.username} 👋</h1>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='margin-top: 0px; color: #57606a;'>{t['help_today']}</h3>", unsafe_allow_html=True)
            st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)

            col_g1, col_g2, col_g3 = st.columns(3)
            with col_g1:
                st.markdown(f'<div class="suggestion-card"><b>{t["idea_title"]}</b><br><span>{t["idea_desc"]}</span></div>', unsafe_allow_html=True)
                if st.button(t["try_this"], key="p1", use_container_width=True):
                    prompt_preset = "Gợi ý 3 kịch bản video ngắn thu hút người xem."
            with col_g2:
                st.markdown(f'<div class="suggestion-card"><b>{t["code_title"]}</b><br><span>{t["code_desc"]}</span></div>', unsafe_allow_html=True)
                if st.button(t["try_this"], key="p2", use_container_width=True):
                    prompt_preset = "Viết script Python crawl dữ liệu bài viết đơn giản."
            with col_g3:
                st.markdown(f'<div class="suggestion-card"><b>{t["search_title"]}</b><br><span>{t["search_desc"]}</span></div>', unsafe_allow_html=True)
                if st.button(t["try_this"], key="p3", use_container_width=True):
                    prompt_preset = "Tin tức mới nhất về trí tuệ nhân tạo tuần này?"
        
        else:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        prompt_input = st.chat_input(t["chat_placeholder"])
        prompt = prompt_input or prompt_preset

        if prompt:
            user_msg = {"role": "user", "content": prompt}
            st.session_state.messages.append(user_msg)
            
            if not st.session_state.current_chat_id:
                st.session_state.current_chat_id = str(uuid.uuid4())

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                s_context = ""
                if enable_search:
                    with st.status(t['search_status'], expanded=False):
                        s_res = search_duckduckgo(prompt)
                        if s_res:
                            s_context = f"\n\n[Dữ liệu Tìm kiếm Web từ DuckDuckGo]:\n{s_res}"

                final_prompt = prompt
                response = ""

                # --- GỌI API OPENROUTER ---
               # --- GỌI API OPENROUTER ---
                if not OPENROUTER_API_KEY:
                    response = "⚠️ **Lỗi**: Chưa cấu hình `OPENROUTER_API_KEY`."
                else:
                    try:
                        selected_model_id = MODEL_MAPPING.get(model_choice, "deepseek/deepseek-chat")

                        SYSTEM_PROMPT = (
                            "You are Astrox AI, an intelligent, helpful, and polite AI assistant. "
                            "Whenever anyone asks who created, built, founded, or developed you (e.g., 'ai tạo ra bạn', 'ai là người sáng lập', 'who created you', 'who is your founder'), "
                            "you MUST always answer clearly that Nguyễn Khôi Nguyên is your creator and founder. "
                            "Always respond in the same language as the user's message."
                        )

                        formatted_messages = [
                            {"role": "system", "content": SYSTEM_PROMPT}
                        ]
                        for m in st.session_state.messages[:-1]:
                            formatted_messages.append({"role": m["role"], "content": m["content"]})
                        
                        formatted_messages.append({"role": "user", "content": final_prompt + s_context})

                        completion = client_openrouter.chat.completions.create(
                            model=selected_model_id,
                            messages=formatted_messages,
                            extra_headers={
                                "HTTP-Referer": "https://astrox.streamlit.app",
                                "X-Title": "Astrox AI"
                            },
                            stream=False
                        )
                        
                        response = completion.choices[0].message.content

                    except Exception as e:
                        response = f"❌ **Lỗi gọi OpenRouter API ({model_choice})**: {e}"

                st.markdown(response)

            st.session_state.messages.append({"role": "assistant", "content": response})
            
            all_chats = load_db(CHATS_FILE)
            if st.session_state.username not in all_chats:
                all_chats[st.session_state.username] = {}
                
            chat_title = all_chats[st.session_state.username].get(
                st.session_state.current_chat_id, {}
            ).get("title", prompt[:30])
            
            all_chats[st.session_state.username][st.session_state.current_chat_id] = {
                "title": chat_title, 
                "messages": st.session_state.messages
            }
            save_db(all_chats, CHATS_FILE)
            st.rerun()
