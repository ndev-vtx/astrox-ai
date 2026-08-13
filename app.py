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
# 1. CẤU HÌNH BAN ĐẦU & LẤY SECRETS AN TOÀN
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

# --- Khởi tạo Các API Clients ---
ASTROX_API_KEY = get_secret("ASTROX_API_KEY")
OPENROUTER_API_KEY = get_secret("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = get_secret("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
CEREBRAS_API_KEY = get_secret("CEREBRAS_API_KEY")
CLOUDFLARE_API_KEY = get_secret("CLOUDFLARE_API_KEY")
CLOUDFLARE_ACCOUNT_ID = get_secret("CLOUDFLARE_ACCOUNT_ID")

# 1. Gemini Client
client_gemini = None
if ASTROX_API_KEY:
    try:
        client_gemini = genai.Client(api_key=ASTROX_API_KEY)
    except Exception as e:
        st.error(f"Lỗi Gemini Client: {e}")

# 2. OpenRouter Client (NKN Intelligent)
client_openrouter = None
if OPENROUTER_API_KEY:
    client_openrouter = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)

# 3. Cerebras Client (NKN Fast Speed)
client_cerebras = None
if CEREBRAS_API_KEY:
    client_cerebras = OpenAI(api_key=CEREBRAS_API_KEY, base_url="https://api.cerebras.ai/v1")

LOGO_FILE = "astrox_logo.png"

st.set_page_config(
    page_title="Astrox AI - Powered by NKN",
    page_icon=LOGO_FILE if os.path.exists(LOGO_FILE) else "✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. XỬ LÝ FILE & TỪ ĐIỂN ĐA NGÔN NGỮ
# ==========================================
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

LANG = {
    "vi": {
        "new_chat": "➕ Cuộc trò chuyện mới",
        "choose_model": "⚡ Chọn mô hình NKN AI:",
        "web_search": "🌐 Tìm kiếm Web",
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
        "try_this": "Thử gợi ý này",
        "upload_title": "📁 Tải tệp lên (Quét ảnh / Đọc file PDF, Docx, TXT)",
        "upload_label": "Chọn tệp từ máy tính:"
    },
    "en": {
        "new_chat": "➕ New Chat",
        "choose_model": "⚡ Choose NKN AI Model:",
        "web_search": "🌐 Web Search",
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
        "try_this": "Try this",
        "upload_title": "📁 Upload File (Scan Image / Read PDF, Docx, TXT)",
        "upload_label": "Choose a file from your computer:"
    }
}

# ==========================================
# 3. SESSION STATE & CSS TỐI ƯU GIAO DIỆN
# ==========================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = ""
if "current_chat_id" not in st.session_state: st.session_state.current_chat_id = None
if "messages" not in st.session_state: st.session_state.messages = []
if "show_account_page" not in st.session_state: st.session_state.show_account_page = False
if "lang" not in st.session_state: st.session_state.lang = "vi"

t = LANG[st.session_state.lang]

def inject_custom_css():
    st.markdown("""
    <style>
        :root { color-scheme: light !important; }
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { 
            background-color: #ffffff !important; color: #1f2328 !important; 
        }
        [data-testid="stSidebar"] { 
            background-color: #f6f8fa !important; border-right: 1px solid #d0d7de !important; 
        }
        div[data-baseweb="select"] > div, .stTextInput input, [data-testid="stChatInput"] textarea, [data-testid="stChatInput"] {
            background-color: #ffffff !important; color: #1f2328 !important; border-color: #d0d7de !important;
        }
        .stButton > button { background-color: #ffffff !important; color: #1f2328 !important; border: 1px solid #d0d7de !important; }
        .suggestion-card { background-color: #f6f8fa !important; border: 1px solid #d0d7de !important; color: #1f2328 !important; border-radius: 12px; padding: 16px; margin-bottom: 12px; min-height: 100px; }
        .suggestion-card span { color: #57606a !important; font-size: 0.9em; }
        p, h1, h2, h3, h4, h5, h6, span, label { color: #1f2328 !important; }
        [data-testid="stSidebarNav"] { display: none; }
        @import url('https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&display=swap');
        body, button, input, select, textarea { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Color Emoji", sans-serif !important; }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ==========================================
# 4. DATABASE & BẢO MẬT
# ==========================================
DB_FILE = "users_db.json"
CHATS_FILE = "chats_db.json"

def load_db(f): 
    if not os.path.exists(f): return {}
    try: return json.load(open(f, "r", encoding="utf-8"))
    except: return {}

def save_db(data, f): json.dump(data, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=4)
def hash_password(p): return hashlib.sha256(str.encode(p)).hexdigest()

def image_to_base64(img):
    b = BytesIO(); img.save(b, format="PNG"); return base64.b64encode(b.getvalue()).decode('utf-8')

def base64_to_image(b64):
    try: return Image.open(BytesIO(base64.b64decode(b64)))
    except: return None

def search_duckduckgo(q):
    try:
        with DDGS() as ddgs:
            res = [f"📌 **{r.get('title')}**\n{r.get('body')}" for r in ddgs.text(q, max_results=4)]
            return "\n\n".join(res) if res else "Không tìm thấy kết quả."
    except Exception as e: return f"Lỗi Search: {e}"

SYSTEM_PROMPT = (
    "You are Astrox AI, an intelligent, helpful, and polite AI assistant. "
    "Whenever anyone asks who created, built, founded, or developed you (e.g., 'ai tạo ra bạn', 'who created you', 'ai là người sáng lập'), "
    "you MUST always answer clearly that Nguyễn Khôi Nguyên (NKN) is your creator and founder. "
    "Always respond in the same language as the user's message."
)

# ==========================================
# 5. GIAO DIỆN CHƯA ĐĂNG NHẬP
# ==========================================
if not st.session_state.logged_in:
    st.write("<br><br>", unsafe_allow_html=True)
    _, c_mid, _ = st.columns([1, 2, 1])
    with c_mid:
        if os.path.exists(LOGO_FILE): st.image(LOGO_FILE, width=80)
        st.title("Astrox AI")
        st.caption("Powered by Nguyễn Khôi Nguyên (NKN)")
        st.write("---")
        lang_sel = st.radio("Language / Ngôn ngữ:", ["Tiếng Việt", "English"], horizontal=True)
        st.session_state.lang = "en" if lang_sel == "English" else "vi"
        t = LANG[st.session_state.lang]

        t_login, t_reg = st.tabs([t["login"], t["register"]])
        with t_login:
            l_u = st.text_input(t["username"], key="lu")
            l_p = st.text_input(t["password"], type="password", key="lp")
            if st.button(t["btn_login"], type="primary", use_container_width=True):
                users = load_db(DB_FILE)
                if l_u in users and users[l_u].get("password") == hash_password(l_p):
                    st.session_state.logged_in = True; st.session_state.username = l_u; st.rerun()
                else: st.error("Mật khẩu không chính xác!")

        with t_reg:
            r_u = st.text_input(t["username"] + " (Mới)", key="ru")
            r_p = st.text_input(t["password"] + " (Mới)", type="password", key="rp")
            if st.button(t["btn_reg"], type="primary", use_container_width=True):
                users = load_db(DB_FILE)
                if r_u and r_u not in users:
                    users[r_u] = {"password": hash_password(r_p), "avatar_base64": ""}
                    save_db(users, DB_FILE)
                    st.session_state.logged_in = True; st.session_state.username = r_u; st.rerun()
                else: st.error("Tên đã tồn tại hoặc không hợp lệ!")

# ==========================================
# 6. GIAO DIỆN CHÍNH (ĐÃ ĐĂNG NHẬP)
# ==========================================
else:
    with st.sidebar:
        st.title("Astrox AI")
        st.divider()
        if st.toggle("🇺🇸 English Mode", value=(st.session_state.lang == "en")):
            if st.session_state.lang != "en": st.session_state.lang = "en"; st.rerun()
        else:
            if st.session_state.lang != "vi": st.session_state.lang = "vi"; st.rerun()

        if st.button(t["new_chat"], use_container_width=True, type="primary"):
            st.session_state.current_chat_id = None; st.session_state.messages = []; st.rerun()

        # 📌 ĐÃ CẬP NHẬT MODEL CLOUDFLARE SANG @cf/meta/llama-3.1-8b-instruct
        MODEL_MAPPING = {
            "🧠 NKN Intelligent": ("openrouter", "deepseek/deepseek-chat"),
            "⚡ NKN Vision 3.6": ("gemini", "gemini-3.6-flash"),
            "🚀 NKN Fast Speed": ("cerebras", "llama3.1-8b"),
            "💥 NKN Cloud": ("cloudflare", "@cf/meta/llama-3.1-8b-instruct")
        }
        model_choice = st.selectbox(t["choose_model"], list(MODEL_MAPPING.keys()))
        enable_search = st.toggle(f"{t['web_search']} (DuckDuckGo)", value=False)

        with st.expander("🔑 Trạng thái API Key", expanded=False):
            st.caption(f"• **OpenRouter (NKN Intelligent):** {'✅' if OPENROUTER_API_KEY else '❌'}")
            st.caption(f"• **NKN API (NKN Vision):** {'✅' if ASTROX_API_KEY else '❌'}")
            st.caption(f"• **Cerebras (NKN Fast):** {'✅' if CEREBRAS_API_KEY else '❌'}")
            st.caption(f"• **Cloudflare (NKN Cloud):** {'✅' if CLOUDFLARE_API_KEY and CLOUDFLARE_ACCOUNT_ID else '❌'}")

        search_kw = st.text_input("🔍", key="skw", label_visibility="collapsed", placeholder=t["search_hist_placeholder"])
        st.caption(t["chat_hist"])
        
        chats_db = load_db(CHATS_FILE).get(st.session_state.username, {})
        filtered_chats = {k: v for k, v in chats_db.items() if not search_kw or search_kw.lower() in v.get("title", "").lower()}
        
        for c_id, c_data in reversed(list(filtered_chats.items())):
            c1, c2 = st.columns([4, 1])
            with c1:
                if st.button(("✨ " if c_id == st.session_state.current_chat_id else "💬 ") + c_data.get("title", "Chat")[:18], key=f"c_{c_id}", use_container_width=True):
                    st.session_state.current_chat_id = c_id; st.session_state.messages = c_data["messages"]; st.rerun()
            with c2:
                if st.button("🗑️", key=f"d_{c_id}"):
                    del chats_db[c_id]
                    all_c = load_db(CHATS_FILE); all_c[st.session_state.username] = chats_db; save_db(all_c, CHATS_FILE)
                    if st.session_state.current_chat_id == c_id: st.session_state.current_chat_id = None; st.session_state.messages = []
                    st.rerun()

        st.divider()
        if st.button(t["profile"], use_container_width=True):
            st.session_state.show_account_page = not st.session_state.show_account_page; st.rerun()
        if st.button(t["logout"], use_container_width=True):
            st.session_state.logged_in = False; st.rerun()

    # --- MAIN VIEW ---
    if st.session_state.show_account_page:
        st.header(t["settings"])
        up_img = st.file_uploader(t["update_avatar"], type=["png", "jpg", "jpeg"])
        if up_img:
            i = Image.open(up_img); i.thumbnail((200, 200))
            u = load_db(DB_FILE)
            if st.session_state.username in u:
                u[st.session_state.username]["avatar_base64"] = image_to_base64(i); save_db(u, DB_FILE)
                st.success("Đã cập nhật ảnh đại diện!"); st.rerun()
        if st.button(t["back_chat"]): st.session_state.show_account_page = False; st.rerun()

    else:
        prompt_preset = None
        if not st.session_state.messages:
            st.title(f"{t['welcome']}{st.session_state.username} 👋")
            st.caption(t['help_today'])
            cg1, cg2, cg3 = st.columns(3)
            with cg1:
                st.markdown(f'<div class="suggestion-card"><b>{t["idea_title"]}</b><br><span>{t["idea_desc"]}</span></div>', unsafe_allow_html=True)
                if st.button(t["try_this"], key="p1", use_container_width=True): prompt_preset = "Gợi ý 3 kịch bản video ngắn."
            with cg2:
                st.markdown(f'<div class="suggestion-card"><b>{t["code_title"]}</b><br><span>{t["code_desc"]}</span></div>', unsafe_allow_html=True)
                if st.button(t["try_this"], key="p2", use_container_width=True): prompt_preset = "Viết script Python crawl dữ liệu đơn giản."
            with cg3:
                st.markdown(f'<div class="suggestion-card"><b>{t["search_title"]}</b><br><span>{t["search_desc"]}</span></div>', unsafe_allow_html=True)
                if st.button(t["try_this"], key="p3", use_container_width=True): prompt_preset = "Tin tức mới nhất về AI?"
        else:
            for m in st.session_state.messages:
                with st.chat_message(m["role"]): st.markdown(m["content"])

        with st.expander(t["upload_title"], expanded=False):
            uploaded_file = st.file_uploader(t["upload_label"], type=["png", "jpg", "jpeg", "webp", "pdf", "docx", "txt"])

        prompt_input = st.chat_input(t["chat_placeholder"])
        prompt = prompt_input or prompt_preset

        if prompt:
            f_type, f_data = process_uploaded_file(uploaded_file)
            file_context = f"\n\n[Dữ liệu tệp]:\n{f_data}\n" if f_type == "text" else ""
            display_msg = f"📎 **[{uploaded_file.name}]**\n\n" + prompt if uploaded_file else prompt

            st.session_state.messages.append({"role": "user", "content": display_msg})
            if not st.session_state.current_chat_id: st.session_state.current_chat_id = str(uuid.uuid4())

            with st.chat_message("user"):
                if f_type == "image": st.image(f_data, width=300)
                st.markdown(display_msg)

            with st.chat_message("assistant"):
                s_context = ""
                if enable_search:
                    with st.status(t['search_status']):
                        s_res = search_duckduckgo(prompt)
                        if s_res: s_context = f"\n\n[Search Data]:\n{s_res}"

                final_prompt = prompt + file_context + s_context
                response = ""
                provider, model_id = MODEL_MAPPING.get(model_choice, ("openrouter", "deepseek/deepseek-chat"))

                # 1. NKN INTELLIGENT (OPENROUTER - DEEPSEEK V3)
                if provider == "openrouter":
                    if not client_openrouter: response = "⚠️ Chưa cấu hình `OPENROUTER_API_KEY` cho NKN Intelligent."
                    else:
                        try:
                            msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
                            for m in st.session_state.messages[:-1]: msgs.append({"role": m["role"], "content": m["content"]})
                            msgs.append({"role": "user", "content": final_prompt})

                            res = client_openrouter.chat.completions.create(model=model_id, messages=msgs, stream=False)
                            response = res.choices[0].message.content
                        except Exception as e: response = f"❌ Lỗi NKN Intelligent API: {e}"

                # 2. NKN VISION 3.6 (GEMINI)
                elif provider == "gemini":
                    if not client_gemini: response = "⚠️ Chưa có `ASTROX_API_KEY`."
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
                        except Exception as e: response = f"❌ Lỗi NKN Vision API: {e}"

                # 3. NKN FAST SPEED (CEREBRAS)
                elif provider == "cerebras":
                    if not client_cerebras: response = "⚠️ Chưa cấu hình `CEREBRAS_API_KEY`."
                    else:
                        try:
                            msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
                            for m in st.session_state.messages[:-1]: msgs.append({"role": m["role"], "content": m["content"]})
                            msgs.append({"role": "user", "content": final_prompt})

                            res = client_cerebras.chat.completions.create(model=model_id, messages=msgs, stream=False)
                            response = res.choices[0].message.content
                        except Exception as e: response = f"❌ Lỗi NKN Fast Speed API: {e}"

                # 4. NKN CLOUD (CLOUDFLARE WORKERS AI - MODEL MỚI)
                elif provider == "cloudflare":
                    if not CLOUDFLARE_API_KEY or not CLOUDFLARE_ACCOUNT_ID: response = "⚠️ Chưa cấu hình `CLOUDFLARE_API_KEY` hoặc `CLOUDFLARE_ACCOUNT_ID`."
                    else:
                        try:
                            cf_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/{model_id}"
                            headers = {"Authorization": f"Bearer {CLOUDFLARE_API_KEY}"}
                            
                            msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
                            for m in st.session_state.messages[:-1]: msgs.append({"role": m["role"], "content": m["content"]})
                            msgs.append({"role": "user", "content": final_prompt})

                            cf_res = requests.post(cf_url, headers=headers, json={"messages": msgs}, timeout=30)
                            res_json = cf_res.json()

                            if res_json.get("success"):
                                response = res_json.get("result", {}).get("response", "Không có phản hồi.")
                            else:
                                response = f"❌ Lỗi NKN Cloud: {res_json.get('errors')}"
                        except Exception as e: response = f"❌ Lỗi NKN Cloud API: {e}"

                st.markdown(response)

            st.session_state.messages.append({"role": "assistant", "content": response})
            all_c = load_db(CHATS_FILE)
            if st.session_state.username not in all_c: all_c[st.session_state.username] = {}
            c_title = all_c[st.session_state.username].get(st.session_state.current_chat_id, {}).get("title", prompt[:30])
            all_c[st.session_state.username][st.session_state.current_chat_id] = {"title": c_title, "messages": st.session_state.messages}
            save_db(all_c, CHATS_FILE)
            st.rerun()
