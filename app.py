import os
import json
import hashlib
import base64
import uuid
import requests
from io import BytesIO
from PIL import Image

import streamlit as st
from dotenv import load_dotenv

from google import genai
from google.genai import types
from openai import OpenAI
from duckduckgo_search import DDGS

import pypdf
import docx

# ==========================================
# 1. CẤU HÌNH BAN ĐẦU & SECRETS
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

ASTROX_API_KEY = get_secret("ASTROX_API_KEY")
OPENROUTER_API_KEY = get_secret("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = get_secret("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
CLOUDFLARE_API_KEY = get_secret("CLOUDFLARE_API_KEY")
CLOUDFLARE_ACCOUNT_ID = get_secret("CLOUDFLARE_ACCOUNT_ID")

client_gemini = None
if ASTROX_API_KEY:
    try:
        client_gemini = genai.Client(api_key=ASTROX_API_KEY)
    except Exception: pass

client_openrouter = None
if OPENROUTER_API_KEY:
    client_openrouter = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)

LOGO_FILE = "astrox_logo.png"
BOT_AVATAR = LOGO_FILE if os.path.exists(LOGO_FILE) else "🐳"

st.set_page_config(
    page_title="DeepSeek - Astrox AI",
    page_icon=BOT_AVATAR,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. CSS CUSTOM CHUẨN DEEPSEEK
# ==========================================
def inject_deepseek_css():
    st.markdown("""
    <style>
        /* Light Theme Tối giản */
        :root { color-scheme: light !important; }
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { 
            background-color: #ffffff !important; 
            color: #111827 !important; 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        }
        
        /* Sidebar Phong cách DeepSeek */
        [data-testid="stSidebar"] { 
            background-color: #f8f9fa !important; 
            border-right: 1px solid #e5e7eb !important; 
        }
        [data-testid="stSidebarNav"] { display: none; }
        
        /* Căn chỉnh khoảng cách sidebar */
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }

        /* Nút New Chat bo tròn kiểu DeepSeek */
        .new-chat-btn button {
            border-radius: 20px !important;
            border: 1px solid #e5e7eb !important;
            background-color: #ffffff !important;
            color: #111827 !important;
            font-weight: 500 !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
        }

        /* Styling cho các nút Model Pill */
        div.stButton > button {
            border-radius: 20px !important;
            border: 1px solid #e5e7eb !important;
            background-color: #f9fafb !important;
            color: #374151 !important;
            font-weight: 500 !important;
            padding: 6px 18px !important;
            transition: all 0.15s ease-in-out !important;
        }
        div.stButton > button:hover {
            border-color: #4f46e5 !important;
            color: #4f46e5 !important;
            background-color: #eef2ff !important;
        }

        /* Khung Chat Input bo góc tròn siêu đẹp */
        [data-testid="stChatInput"] {
            border-radius: 24px !important;
            border: 1px solid #e5e7eb !important;
            box-shadow: 0 4px 16px rgba(0,0,0,0.04) !important;
            background-color: #ffffff !important;
        }
        
        /* Custom Popover góc dưới sidebar */
        div[data-testid="stPopover"] > button {
            width: 100% !important;
            border: none !important;
            background-color: transparent !important;
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 8px 12px !important;
            border-radius: 8px !important;
        }
        div[data-testid="stPopover"] > button:hover {
            background-color: #f3f4f6 !important;
        }

        /* Dynamic Title Styling */
        .deepseek-title {
            font-size: 26px;
            font-weight: 700;
            color: #0f172a;
            text-align: center;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }
    </style>
    """, unsafe_allow_html=True)

inject_deepseek_css()

# ==========================================
# 3. DATABASE & LƯU TRỮ
# ==========================================
DB_FILE = "users_db.json"
CHATS_FILE = "chats_db.json"

def load_db(f): 
    if not os.path.exists(f): return {}
    try: return json.load(open(f, "r", encoding="utf-8"))
    except: return {}

def save_db(data, f): json.dump(data, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=4)
def hash_password(p): return hashlib.sha256(str.encode(p)).hexdigest()

def process_uploaded_file(uploaded_file):
    if uploaded_file is None: return None, None
    file_type = uploaded_file.type
    file_name = uploaded_file.name.lower()
    try:
        if "image" in file_type or file_name.endswith(('.png', '.jpg', '.jpeg', '.webp')):
            return "image", Image.open(uploaded_file)
        elif file_name.endswith('.pdf'):
            pdf_reader = pypdf.PdfReader(BytesIO(uploaded_file.getvalue()))
            return "text", "\n".join([page.extract_text() or "" for page in pdf_reader.pages])
        elif file_name.endswith('.docx'):
            doc = docx.Document(BytesIO(uploaded_file.getvalue()))
            return "text", "\n".join([p.text for p in doc.paragraphs if p.text])
        elif file_name.endswith('.txt'):
            return "text", uploaded_file.getvalue().decode("utf-8", errors="ignore")
    except Exception as e:
        return "error", f"Lỗi đọc tệp: {e}"
    return None, None

def search_duckduckgo(q):
    try:
        with DDGS() as ddgs:
            res = [f"📌 **{r.get('title')}**\n{r.get('body')}" for r in ddgs.text(q, max_results=3)]
            return "\n\n".join(res) if res else "Không tìm thấy kết quả."
    except Exception as e: return f"Lỗi Search: {e}"

SYSTEM_PROMPT = (
    "You are Astrox AI, an intelligent, helpful, and polite AI assistant. "
    "Whenever anyone asks who created, built, founded, or developed you (e.g., 'ai tạo ra bạn', 'who created you'), "
    "you MUST always answer clearly that Nguyễn Khôi Nguyên (NKN) is your creator and founder. "
    "Always respond in the same language as the user's message."
)

# ==========================================
# 4. SESSION STATE
# ==========================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = ""
if "current_chat_id" not in st.session_state: st.session_state.current_chat_id = None
if "messages" not in st.session_state: st.session_state.messages = []
if "selected_model" not in st.session_state: st.session_state.selected_model = "NKN Intelligent"
if "enable_search" not in st.session_state: st.session_state.enable_search = False
if "last_processed_audio_hash" not in st.session_state: st.session_state.last_processed_audio_hash = ""

# 3 MODEL DUY NHẤT VỚI TÊN NKN SẠCH SẼ
MODELS = {
    "NKN Intelligent": ("openrouter", "deepseek/deepseek-chat", "⚡"),
    "NKN Cloud": ("cloudflare", "@cf/meta/llama-3.1-8b-instruct", "💎"),
    "NKN Vision": ("gemini", "gemini-3.6-flash", "📷")
}

# ==========================================
# 5. DIALOG SETTINGS (POPUP CÀI ĐẶT CHUẨN DEEPSEEK)
# ==========================================
@st.dialog("Settings")
def show_settings_dialog():
    st.write("---")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.button("⚙️ General", use_container_width=True, type="primary")
        st.button("👤 Profile", use_container_width=True)
        st.button("💾 Data", use_container_width=True)
        st.button("ℹ️ About", use_container_width=True)
    with col2:
        st.markdown("**Theme**")
        st.radio("Giao diện", ["Light", "Dark", "System"], index=0, horizontal=True, label_visibility="collapsed")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Language**")
        st.selectbox("Ngôn ngữ", ["English", "Tiếng Việt"], index=0, label_visibility="collapsed")

# ==========================================
# 6. GIAO DIỆN ĐĂNG NHẬP
# ==========================================
if not st.session_state.logged_in:
    st.write("<br><br>", unsafe_allow_html=True)
    _, c_mid, _ = st.columns([1, 1.2, 1])
    with c_mid:
        if os.path.exists(LOGO_FILE): st.image(LOGO_FILE, width=70)
        st.title("DeepSeek")
        st.caption("Astrox AI • Powered by NKN")
        st.write("---")
        t_login, t_reg = st.tabs(["Login", "Register"])
        with t_login:
            l_u = st.text_input("Username", key="lu")
            l_p = st.text_input("Password", type="password", key="lp")
            if st.button("Log In", type="primary", use_container_width=True):
                users = load_db(DB_FILE)
                if l_u in users and users[l_u].get("password") == hash_password(l_p):
                    st.session_state.logged_in = True; st.session_state.username = l_u; st.rerun()
                else: st.error("Mật khẩu không chính xác!")

        with t_reg:
            r_u = st.text_input("Username (Mới)", key="ru")
            r_p = st.text_input("Password (Mới)", type="password", key="rp")
            if st.button("Create Account", type="primary", use_container_width=True):
                users = load_db(DB_FILE)
                if r_u and r_u not in users:
                    users[r_u] = {"password": hash_password(r_p)}
                    save_db(users, DB_FILE)
                    st.session_state.logged_in = True; st.session_state.username = r_u; st.rerun()
                else: st.error("Tên người dùng đã tồn tại!")

# ==========================================
# 7. GIAO DIỆN CHÍNH (LOGGED IN)
# ==========================================
else:
    # --- SIDEBAR DEEPSEEK ---
    with st.sidebar:
        # Header Sidebar
        sb_col1, sb_col2 = st.columns([4, 1])
        with sb_col1:
            st.markdown("### Astrox")
        
        # Nút New Chat
        st.markdown('<div class="new-chat-btn">', unsafe_allow_html=True)
        if st.button("➕ New chat", use_container_width=True):
            st.session_state.current_chat_id = None
            st.session_state.messages = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.write("")

        # Lịch sử trò chuyện
        st.caption("CHAT HISTORY")
        chats_db = load_db(CHATS_FILE).get(st.session_state.username, {})
        for c_id, c_data in reversed(list(chats_db.items())):
            c1, c2 = st.columns([4, 1])
            with c1:
                title = c_data.get("title", "New Chat")[:18]
                btn_type = "primary" if c_id == st.session_state.current_chat_id else "secondary"
                if st.button(f"💬 {title}", key=f"c_{c_id}", use_container_width=True):
                    st.session_state.current_chat_id = c_id
                    st.session_state.messages = c_data["messages"]
                    st.rerun()
            with c2:
                if st.button("🗑️", key=f"d_{c_id}"):
                    del chats_db[c_id]
                    all_c = load_db(CHATS_FILE); all_c[st.session_state.username] = chats_db; save_db(all_c, CHATS_FILE)
                    if st.session_state.current_chat_id == c_id:
                        st.session_state.current_chat_id = None; st.session_state.messages = []
                    st.rerun()

        # Khoảng trống đẩy Popup tài khoản xuống dưới cùng
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.divider()

        # GÓC DƯỚI BÊN TRÁI: POPUP USER KHÔNG KHÁC GÌ DEEPSEEK (CHỈ CHỨA SETTINGS VÀ LOGOUT)
        user_display = f"👤 **{st.session_state.username}**"
        with st.popover(user_display, use_container_width=True):
            if st.button("⚙️ Settings", use_container_width=True):
                show_settings_dialog()
            if st.button("➜] Log out", use_container_width=True):
                st.session_state.logged_in = False
                st.rerun()

    # --- MAIN VIEW CHAT AREA ---
    # NẾU CHƯA CÓ TIN NHẮN -> HIỂN THỊ TRANG CHỦ GIỐNG HỆT VIDEO / HÌNH ẢNH DEEPSEEK
    if not st.session_state.messages:
        st.write("<br><br>", unsafe_allow_html=True)
        
        # Dynamic Header Effect (Thay đổi tên theo model được chọn)
        active_model = st.session_state.selected_model
        st.markdown(
            f'<div class="deepseek-title">🐳 Start chatting with <b>{active_model}</b></div>', 
            unsafe_allow_html=True
        )

        # NÚT BẤM PILL CHUYỂN MODEL TRÊN MÀN HÌNH CHÍNH
        p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns([1, 1.2, 1.2, 1.2, 1])
        with p_col2:
            if st.button("⚡ NKN Intelligent", use_container_width=True, type="primary" if active_model == "NKN Intelligent" else "secondary"):
                st.session_state.selected_model = "NKN Intelligent"
                st.rerun()
        with p_col3:
            if st.button("💎 NKN Cloud", use_container_width=True, type="primary" if active_model == "NKN Cloud" else "secondary"):
                st.session_state.selected_model = "NKN Cloud"
                st.rerun()
        with p_col4:
            if st.button("📷 NKN Vision", use_container_width=True, type="primary" if active_model == "NKN Vision" else "secondary"):
                st.session_state.selected_model = "NKN Vision"
                st.rerun()

        st.write("<br>", unsafe_allow_html=True)

    else:
        # HIỂN THỊ LỊCH SỬ CHAT KHI ĐÃ CÓ CONVERSATION
        for m in st.session_state.messages:
            avatar = BOT_AVATAR if m["role"] == "assistant" else None
            with st.chat_message(m["role"], avatar=avatar):
                st.markdown(m["content"])

    # --- KHUNG TẢI FILE & MICROPHONE DƯỚI BÙNG ---
    with st.expander("📎 Attach Files & 🎙️ Micro Input", expanded=False):
        c_up1, c_up2 = st.columns(2)
        with c_up1:
            uploaded_file = st.file_uploader("Upload Document / Image", type=["png", "jpg", "jpeg", "pdf", "docx", "txt"])
        with c_up2:
            audio_recorded = st.audio_input("Record Voice")

    # --- TÍNH NĂNG TÌM KIẾM WEB (SEARCH TOGGLE CHUẨN DEEPSEEK) ---
    st.session_state.enable_search = st.toggle("🌐 Web Search", value=st.session_state.enable_search)

    # --- INPUT NHẬP TIN NHẮN ---
    prompt_input = st.chat_input("Message DeepSeek...")
    prompt = prompt_input

    # Xử lý Micro Chống Glitch
    if audio_recorded and not prompt:
        audio_bytes = audio_recorded.getvalue()
        current_audio_hash = hashlib.md5(audio_bytes).hexdigest()
        if current_audio_hash != st.session_state.last_processed_audio_hash:
            if client_gemini:
                with st.spinner("🎙️ Transcribing audio..."):
                    try:
                        res_audio = client_gemini.models.generate_content(
                            model="gemini-3.6-flash",
                            contents=[types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"), "Chép lại chính xác lời nói bằng văn bản:"]
                        )
                        prompt = res_audio.text.strip()
                        st.session_state.last_processed_audio_hash = current_audio_hash
                    except Exception as e: st.error(f"Speech error: {e}")

    # --- XỬ LÝ PHẢN HỒI KHI CÓ PROMPT ---
    if prompt:
        f_type, f_data = process_uploaded_file(uploaded_file)
        file_context = f"\n\n[File Data]:\n{f_data}\n" if f_type == "text" else ""
        display_msg = f"📎 **[{uploaded_file.name}]**\n\n" + prompt if uploaded_file else prompt

        st.session_state.messages.append({"role": "user", "content": display_msg})
        if not st.session_state.current_chat_id: 
            st.session_state.current_chat_id = str(uuid.uuid4())

        with st.chat_message("user"):
            if f_type == "image": st.image(f_data, width=280)
            st.markdown(display_msg)

        with st.chat_message("assistant", avatar=BOT_AVATAR):
            s_context = ""
            if st.session_state.enable_search:
                with st.status("🔍 Searching Web..."):
                    s_res = search_duckduckgo(prompt)
                    if s_res: s_context = f"\n\n[Web Data]:\n{s_res}"

            final_prompt = prompt + file_context + s_context
            response = ""
            provider, model_id, _ = MODELS.get(st.session_state.selected_model, ("openrouter", "deepseek/deepseek-chat", "⚡"))

            # 1. NKN INTELLIGENT
            if provider == "openrouter":
                if not client_openrouter: response = "⚠️ Missing `NKN_API_KEY`."
                else:
                    try:
                        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
                        for m in st.session_state.messages[:-1]: msgs.append({"role": m["role"], "content": m["content"]})
                        msgs.append({"role": "user", "content": final_prompt})
                        res = client_openrouter.chat.completions.create(model=model_id, messages=msgs, stream=False)
                        response = res.choices[0].message.content
                    except Exception as e: response = f"❌ Error: {e}"

            # 2. NKN CLOUD
            elif provider == "cloudflare":
                if not CLOUDFLARE_API_KEY or not CLOUDFLARE_ACCOUNT_ID: response = "⚠️ Missing NKN Keys."
                else:
                    try:
                        cf_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/{model_id}"
                        headers = {"Authorization": f"Bearer {CLOUDFLARE_API_KEY}"}
                        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
                        for m in st.session_state.messages[:-1]: msgs.append({"role": m["role"], "content": m["content"]})
                        msgs.append({"role": "user", "content": final_prompt})
                        cf_res = requests.post(cf_url, headers=headers, json={"messages": msgs}, timeout=30)
                        res_json = cf_res.json()
                        response = res_json.get("result", {}).get("response", "No response") if res_json.get("success") else f"❌ Error: {res_json.get('errors')}"
                    except Exception as e: response = f"❌ Error: {e}"

            # 3. NKN VISION
            elif provider == "gemini":
                if not client_gemini: response = "⚠️ Missing `ASTROX_API_KEY`."
                else:
                    try:
                        contents = []
                        for m in st.session_state.messages[:-1]:
                            role = "user" if m["role"] == "user" else "model"
                            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
                        
                        if f_type == "image":
                            img_b = BytesIO(); f_data.save(img_b, format="PNG")
                            image_part = types.Part.from_bytes(data=img_b.getvalue(), mime_type="image/png")
                            contents.append(types.Content(role="user", parts=[image_part, types.Part.from_text(text=final_prompt)]))
                        else:
                            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=final_prompt)]))

                        res = client_gemini.models.generate_content(model=model_id, contents=contents, config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT))
                        response = res.text
                    except Exception as e: response = f"❌ Error: {e}"

            st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})
        all_c = load_db(CHATS_FILE)
        if st.session_state.username not in all_c: all_c[st.session_state.username] = {}
        c_title = all_c[st.session_state.username].get(st.session_state.current_chat_id, {}).get("title", prompt[:25])
        all_c[st.session_state.username][st.session_state.current_chat_id] = {"title": c_title, "messages": st.session_state.messages}
        save_db(all_c, CHATS_FILE)
        st.rerun()
