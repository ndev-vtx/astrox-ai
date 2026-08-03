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

# --- CẤU HÌNH & TẢI BIẾN MÔI TRƯỜNG ---
load_dotenv()
ASTROX_API_KEY = st.secrets.get("ASTROX_API_KEY", os.getenv("ASTROX_API_KEY"))
INVISIBLE_API_KEY = st.secrets.get("INVISIBLE_API_KEY", os.getenv("INVISIBLE_API_KEY"))

# API Keys cho Search
TAVILY_API_KEY = st.secrets.get("TAVILY_API_KEY", os.getenv("TAVILY_API_KEY"))
EXA_API_KEY = st.secrets.get("EXA_API_KEY", os.getenv("EXA_API_KEY"))

LOGO_FILE = "astrox_logo.png"

st.set_page_config(
    page_title="Astrox AI",
    page_icon=LOGO_FILE if os.path.exists(LOGO_FILE) else "✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Quản lý Cookie
cookie_manager = stx.CookieManager()

# --- CSS TÙY CHỈNH GIAO DIỆN & MÀU SẮC ---
st.markdown("""
<style>
    .stApp {
        background-color: #ffffff;
        color: #1f2328;
    }
    
    [data-testid="stSidebar"] {
        background-color: #f6f8fa;
        border-right: 1px solid #d0d7de;
    }

    .suggestion-card {
        background-color: #f6f8fa;
        border: 1px solid #d0d7de;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        color: #1f2328;
    }
    
    .stChatInputContainer {
        border-radius: 24px !important;
        border: 1px solid #d0d7de !important;
    }

    @media (prefers-color-scheme: dark) {
        .stApp {
            background-color: #0d1117 !important;
            color: #f0f6fc !important;
        }
        [data-testid="stSidebar"] {
            background-color: #161b22 !important;
            border-right: 1px solid #30363d !important;
        }
        .suggestion-card {
            background-color: #161b22 !important;
            border: 1px solid #30363d !important;
            color: #f0f6fc !important;
        }
        .suggestion-card span {
            color: #8b949e !important;
        }
        .stChatInputContainer {
            border: 1px solid #30363d !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# --- QUẢN LÝ DATABASE TRÊN MÁY / CLOUD ---
DB_FILE = "users_db.json"
CHATS_FILE = "chats_db.json"
IP_DB_FILE = "ip_db.json"

def load_db(file_name):
    if not os.path.exists(file_name):
        return {}
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
        st.error(f"Lỗi khi lưu dữ liệu: {e}")

# --- XỬ LÝ LẤY IP & GIỚI HẠN SEARCH ---
def get_client_ip():
    try:
        headers = st.context.headers
        if headers:
            forwarded = headers.get("X-Forwarded-For") or headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()
    except Exception:
        pass
    return "127.0.0.1"

def get_ip_search_count(ip):
    db = load_db(IP_DB_FILE)
    return db.get(ip, 0)

def increment_ip_search_count(ip):
    db = load_db(IP_DB_FILE)
    db[ip] = db.get(ip, 0) + 1
    save_db(db, IP_DB_FILE)

def get_user_search_count(username):
    users = load_db(DB_FILE)
    return users.get(username, {}).get("search_count", 0)

def increment_user_search_count(username):
    users = load_db(DB_FILE)
    if username in users:
        users[username]["search_count"] = users[username].get("search_count", 0) + 1
        save_db(users, DB_FILE)

# --- HÀM CHUYỂN GIỌNG NÓI THÀNH VĂN BẢN (GROQ WHISPER FREE) ---
def transcribe_audio_with_groq(audio_bytes):
    if not ASTROX_API_KEY:
        return ""
    try:
        client = Groq(api_key=ASTROX_API_KEY)
        transcription = client.audio.transcriptions.create(
            file=("speech.wav", audio_bytes),
            model="whisper-large-v3-turbo",
            response_format="text",
            language="vi"
        )
        return str(transcription).strip()
    except Exception as e:
        st.error(f"Lỗi nhận diện giọng nói: {e}")
        return ""

# --- CÁC HÀM TÌM KIẾM ĐẦU VÀO (SEARCH PROVIDERS) ---
def search_tavily(query):
    if not TAVILY_API_KEY:
        raise ValueError("Chưa có Tavily API Key")
    client = TavilyClient(api_key=TAVILY_API_KEY)
    response = client.search(query=query, max_results=4)
    results = response.get("results", [])
    if not results:
        raise ValueError("Tavily không trả về kết quả")
    formatted = []
    for r in results:
        formatted.append(f"Tiêu đề: {r.get('title')}\nTrích dẫn: {r.get('content')}\nLink: {r.get('url')}")
    return "\n\n".join(formatted)

def search_exa(query):
    if not EXA_API_KEY:
        raise ValueError("Chưa có Exa API Key")
    exa = Exa(api_key=EXA_API_KEY)
    response = exa.search_and_contents(
        query,
        type="neural",
        use_autoprompt=True,
        num_results=4,
        text=True
    )
    results = getattr(response, "results", [])
    if not results:
        raise ValueError("Exa không trả về kết quả")
    formatted = []
    for r in results:
        text_content = getattr(r, "text", "") or ""
        snippet = (text_content[:350] + "...") if len(text_content) > 350 else text_content
        title = getattr(r, "title", "Không có tiêu đề")
        url = getattr(r, "url", "")
        formatted.append(f"Tiêu đề: {title}\nTrích dẫn: {snippet}\nLink: {url}")
    return "\n\n".join(formatted)

def search_duckduckgo(query):
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=4):
            results.append(f"Tiêu đề: {r.get('title')}\nTrích dẫn: {r.get('body')}\nLink: {r.get('href')}")
    if not results:
        raise ValueError("DuckDuckGo không trả về kết quả")
    return "\n\n".join(results)

def search_web_multi_fallback(query, username):
    client_ip = get_client_ip()
    user_count = get_user_search_count(username)
    ip_count = get_ip_search_count(client_ip)

    if user_count >= 100 or ip_count >= 100:
        try:
            res = search_duckduckgo(query)
            return res, "DuckDuckGo (Đã dùng hết 100 lượt AI Search)"
        except Exception as e:
            return f"Lỗi DuckDuckGo: {e}", "Lỗi Tìm Kiếm"

    try:
        res = search_tavily(query)
        increment_user_search_count(username)
        increment_ip_search_count(client_ip)
        return res, f"Tavily AI Search (Lượt {user_count + 1}/100)"
    except Exception:
        pass

    try:
        res = search_exa(query)
        increment_user_search_count(username)
        increment_ip_search_count(client_ip)
        return res, f"Exa AI Search (Lượt {user_count + 1}/100)"
    except Exception:
        pass

    try:
        res = search_duckduckgo(query)
        return res, "DuckDuckGo (Free)"
    except Exception as e:
        return f"Tất cả công cụ tìm kiếm đều lỗi: {e}", "Lỗi Tìm Kiếm"

# --- XỬ LÝ ẢNH CHUYỂN ĐỔI ---
def image_to_base64(image):
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def base64_to_image(base64_str):
    if not base64_str:
        return None
    try:
        decoded_bytes = base64.b64decode(base64_str)
        return Image.open(BytesIO(decoded_bytes))
    except Exception:
        return None

# --- CHỨC NĂNG TÀI KHOẢN ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def register_user(username, password):
    users = load_db(DB_FILE)
    if username in users:
        return False
    users[username] = {
        "password": hash_password(password),
        "avatar_base64": "",
        "created_ip": get_client_ip(),
        "search_count": 0
    }
    save_db(users, DB_FILE)
    return True

def authenticate_user(username, password):
    users = load_db(DB_FILE)
    if username in users and users[username].get("password") == hash_password(password):
        return True
    return False

def update_user_avatar(username, avatar_base64):
    users = load_db(DB_FILE)
    if username in users:
        users[username]["avatar_base64"] = avatar_base64
        save_db(users, DB_FILE)
        return True
    return False

# --- CHỨC NĂNG QUẢN LÝ LỊCH SỬ CHAT ---
def get_user_all_chats(username):
    chats = load_db(CHATS_FILE)
    if not isinstance(chats, dict):
        return {}
    user_data = chats.get(username, {})
    return user_data if isinstance(user_data, dict) else {}

def save_user_chat_session(username, chat_id, title, messages):
    chats = load_db(CHATS_FILE)
    if not isinstance(chats, dict):
        chats = {}
    if username not in chats or not isinstance(chats[username], dict):
        chats[username] = {}
    chats[username][chat_id] = {
        "title": title,
        "messages": messages
    }
    save_db(chats, CHATS_FILE)

def delete_user_chat_session(username, chat_id):
    chats = load_db(CHATS_FILE)
    if isinstance(chats, dict) and username in chats and isinstance(chats[username], dict):
        if chat_id in chats[username]:
            del chats[username][chat_id]
            save_db(chats, CHATS_FILE)

# --- KHỞI TẠO TRẠNG THÁI PHIÊN VÀ ĐỌC COOKIE ---
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

saved_user = cookie_manager.get('astrox_logged_user')
if saved_user and not st.session_state.logged_in:
    users_db = load_db(DB_FILE)
    if saved_user in users_db:
        st.session_state.logged_in = True
        st.session_state.username = saved_user

# --- TRANG ĐĂNG NHẬP / ĐĂNG KÝ ---
if not st.session_state.logged_in:
    st.write("<br><br>", unsafe_allow_html=True)
    c_left, c_mid, c_right = st.columns([1, 2, 1])
    
    with c_mid:
        if os.path.exists(LOGO_FILE):
            st.image(LOGO_FILE, width=90)
        st.title("Astrox AI")
        st.caption("Intelligence & Innovation — Into the Infinite Era")
        st.write("---")

        tab_login, tab_register = st.tabs(["Đăng nhập", "Đăng ký"])

        with tab_login:
            login_user = st.text_input("Tên đăng nhập", key="login_user")
            login_pass = st.text_input("Mật khẩu", type="password", key="login_pass")
            if st.button("Đăng nhập", type="primary", use_container_width=True, key="btn_login"):
                if not login_user or not login_pass:
                    st.warning("Vui lòng điền đầy đủ tên đăng nhập và mật khẩu!")
                elif authenticate_user(login_user, login_pass):
                    st.session_state.logged_in = True
                    st.session_state.username = login_user
                    st.session_state.current_chat_id = None
                    st.session_state.messages = []
                    cookie_manager.set('astrox_logged_user', login_user, expires_at=None, key="set_cookie_login")
                    st.rerun()
                else:
                    st.error("Tài khoản chưa tồn tại hoặc sai mật khẩu!")

        with tab_register:
            reg_user = st.text_input("Tên đăng nhập mới", key="reg_user")
            reg_pass = st.text_input("Mật khẩu mới", type="password", key="reg_pass")
            reg_pass_confirm = st.text_input("Xác nhận mật khẩu", type="password", key="reg_pass_confirm")
            if st.button("Tạo tài khoản & Bắt đầu", type="primary", use_container_width=True, key="btn_reg"):
                if not reg_user or not reg_pass:
                    st.warning("Vui lòng điền đầy đủ thông tin!")
                elif reg_pass != reg_pass_confirm:
                    st.error("Mật khẩu xác nhận không khớp!")
                elif register_user(reg_user, reg_pass):
                    st.session_state.logged_in = True
                    st.session_state.username = reg_user
                    st.session_state.current_chat_id = None
                    st.session_state.messages = []
                    cookie_manager.set('astrox_logged_user', reg_user, expires_at=None, key="set_cookie_reg")
                    st.rerun()
                else:
                    st.error("Tên đăng nhập này đã tồn tại!")

# --- GIAO DIỆN CHÍNH KHI ĐÃ ĐĂNG NHẬP ---
else:
    @st.dialog("⚠️ Xác nhận xóa cuộc trò chuyện")
    def confirm_delete_dialog(chat_id_to_del):
        st.write("Bạn có chắc chắn muốn xóa cuộc trò chuyện này không? Hành động này không thể hoàn tác.")
        c_yes, c_no = st.columns([1, 1])
        with c_yes:
            if st.button("Xóa vĩnh viễn", type="primary", use_container_width=True):
                delete_user_chat_session(st.session_state.username, chat_id_to_del)
                if st.session_state.current_chat_id == chat_id_to_del:
                    st.session_state.current_chat_id = None
                    st.session_state.messages = []
                st.session_state.chat_to_delete = None
                st.rerun()
        with c_no:
            if st.button("Hủy", use_container_width=True):
                st.session_state.chat_to_delete = None
                st.rerun()

    if st.session_state.chat_to_delete:
        confirm_delete_dialog(st.session_state.chat_to_delete)

    # --- THANH BÊN (SIDEBAR) ---
    with st.sidebar:
        if os.path.exists(LOGO_FILE):
            st.image(LOGO_FILE, width=50)
        st.markdown("### **Astrox AI**")
        st.caption("Astrox Engine")

        if st.button("➕ Cuộc trò chuyện mới", use_container_width=True, type="primary"):
            st.session_state.current_chat_id = None
            st.session_state.messages = []
            st.session_state.show_account_page = False
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        
        model_choice = st.selectbox(
            "⚡ Chọn mô hình AI:",
            options=[
                "✨ Invisible 3.6 (Hỗ trợ Ảnh)",
                "🚀 Invisible 4.0 (Hỗ trợ Ảnh)",
                "⚡ Invisible-flash 3.5 (Văn bản - Groq)"
            ],
            index=0,
            help="Invisible 3.6 & 4.0 hỗ trợ phân tích hình ảnh (Gemini). Invisible-flash 3.5 tối ưu văn bản (Groq)."
        )

        user_used = get_user_search_count(st.session_state.username)
        remaining_search = max(0, 100 - user_used)
        
        enable_web_search = st.toggle(
            f"🌐 Tìm kiếm Web (Còn {remaining_search}/100)",
            value=False,
            help="Tự động dùng Tavily/Exa trong 100 lượt đầu. Sau đó tự động dùng DuckDuckGo miễn phí."
        )

        search_kw = st.text_input("🔍 Tìm kiếm...", key="search_chat_kw", label_visibility="collapsed", placeholder="🔍 Tìm kiếm lịch sử...")

        st.caption("LỊCH SỬ TRÒ CHUYỆN")
        user_chats = get_user_all_chats(st.session_state.username)

        filtered_chats = {}
        if isinstance(user_chats, dict):
            for c_id, c_data in user_chats.items():
                if isinstance(c_data, dict):
                    title = c_data.get("title", "Trò chuyện mới")
                    if not search_kw or search_kw.lower() in title.lower():
                        filtered_chats[c_id] = c_data

        if not filtered_chats:
            st.caption("Chưa có lịch sử chat.")
        else:
            for c_id, c_data in reversed(list(filtered_chats.items())):
                title = c_data.get("title", "Trò chuyện mới")
                display_title = title[:18] + "..." if len(title) > 18 else title
                
                col_c1, col_c2 = st.columns([4, 1])
                with col_c1:
                    is_current = (c_id == st.session_state.current_chat_id)
                    btn_label = f"💬 {display_title}" if not is_current else f"✨ {display_title}"
                    if st.button(btn_label, key=f"chat_{c_id}", use_container_width=True):
                        st.session_state.current_chat_id = c_id
                        st.session_state.messages = c_data.get("messages", [])
                        st.session_state.show_account_page = False
                        st.rerun()
                with col_c2:
                    if st.button("🗑️", key=f"del_{c_id}"):
                        st.session_state.chat_to_delete = c_id
                        st.rerun()

        st.divider()

        users = load_db(DB_FILE)
        current_user_data = users.get(st.session_state.username, {}) if isinstance(users, dict) else {}
        user_avatar_base64 = current_user_data.get("avatar_base64", "")

        col_av, col_name = st.columns([1, 2])
        with col_av:
            avatar_img = base64_to_image(user_avatar_base64)
            if avatar_img:
                st.image(avatar_img, width=45)
            else:
                st.markdown("👤")
        with col_name:
            st.markdown(f"**{st.session_state.username}**")

        c_act, c_logout = st.columns([1, 1])
        with c_act:
            if st.button("⚙️ Hồ sơ", use_container_width=True):
                st.session_state.show_account_page = not st.session_state.show_account_page
                st.rerun()
        with c_logout:
            if st.button("🚪 Thoát", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.session_state.current_chat_id = None
                st.session_state.messages = []
                st.session_state.show_account_page = False
                cookie_manager.delete('astrox_logged_user', key="del_cookie_logout")
                st.rerun()

    # --- KHU VỰC HIỂN THỊ CHÍNH (MAIN CHAT AREA) ---
    if st.session_state.show_account_page:
        st.header(f"Cài đặt tài khoản: {st.session_state.username}")
        st.write("---")
        st.subheader("Cập nhật ảnh đại diện")
        uploaded_file = st.file_uploader("Chọn ảnh đại diện mới", type=["png", "jpg", "jpeg"])
        if uploaded_file is not None:
            try:
                img = Image.open(uploaded_file)
                img.thumbnail((200, 200))
                avatar_base64 = image_to_base64(img)
                if update_user_avatar(st.session_state.username, avatar_base64):
                    st.success("Cập nhật ảnh đại diện thành công!")
                    st.rerun()
            except Exception as e:
                st.error(f"Lỗi khi lưu ảnh: {e}")
        if st.button("← Quay lại trò chuyện"):
            st.session_state.show_account_page = False
            st.rerun()

    else:
        if not st.session_state.messages:
            st.write("<br><br>", unsafe_allow_html=True)
            st.markdown(f"# <span style='color:#0969da;'>Xin chào, {st.session_state.username}</span>", unsafe_allow_html=True)
            st.markdown("### Hôm nay **Astrox AI** có thể giúp gì cho bạn?")
            st.write("<br>", unsafe_allow_html=True)

            col_g1, col_g2, col_g3 = st.columns(3)
            prompt_preset = None

            with col_g1:
                st.markdown("""
                <div class="suggestion-card">
                    <b>💡 Ý tưởng sáng tạo</b><br>
                    <span style="color:#57606a; font-size: 14px;">Gợi ý kịch bản video hoặc viết bài blog hấp dẫn</span>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Thử gợi ý này", key="p1", use_container_width=True):
                    prompt_preset = "Hãy gợi ý cho tôi 3 ý tưởng kịch bản video ngắn thu hút người xem."

            with col_g2:
                st.markdown("""
                <div class="suggestion-card">
                    <b>💻 Lập trình & Code</b><br>
                    <span style="color:#57606a; font-size: 14px;">Viết code Python, HTML hoặc sửa lỗi lập trình</span>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Thử gợi ý này", key="p2", use_container_width=True):
                    prompt_preset = "Hãy viết cho tôi một đoạn script Python đơn giản để tải nội dung web."

            with col_g3:
                st.markdown("""
                <div class="suggestion-card">
                    <b>🌐 Tìm kiếm thông tin</b><br>
                    <span style="color:#57606a; font-size: 14px;">Tin tức mới nhất về công nghệ và AI hiện nay</span>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Thử gợi ý này", key="p3", use_container_width=True):
                    prompt_preset = "Cập nhật các tin tức công nghệ nổi bật nhất tuần này."

        else:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    if "image_base64" in message and message["image_base64"]:
                        img_display = base64_to_image(message["image_base64"])
                        if img_display:
                            st.image(img_display, width=300)

        # --- Ô ĐẦU VÀO ĐA PHƯƠNG TIỆN (AUDIO & ANH) ---
        st.write("---")
        col_mic, col_img_up = st.columns([1, 4])
        
        voice_text = ""
        with col_mic:
            st.caption("🎙️ Bấm để nói:")
            audio_bytes = audio_recorder(text="", recording_color="#e8b1b5", neutral_color="#6aa3b8", icon_size="2x")
            if audio_bytes:
                with st.spinner("Đang chuyển giọng nói..."):
                    voice_text = transcribe_audio_with_groq(audio_bytes)
                    if voice_text:
                        st.success(f"Đã nghe: \"{voice_text}\"")

        with col_img_up:
            uploaded_chat_img = st.file_uploader("🖼️ Đính kèm hình ảnh để AI quét/phân tích (Tùy chọn):", type=["png", "jpg", "jpeg"], key="chat_img_uploader")

        prompt_input = st.chat_input("Hỏi Astrox AI bất kỳ điều gì...")
        
        # Ưu tiên câu hỏi: Nhập tay > Giọng nói > Nút bấm gợi ý
        prompt = prompt_input or voice_text or (prompt_preset if 'prompt_preset' in locals() else None)

        if prompt or uploaded_chat_img:
            if not prompt and uploaded_chat_img:
                prompt = "Hãy phân tích và mô tả chi tiết bức ảnh này giúp tôi."

            if st.session_state.current_chat_id is None:
                st.session_state.current_chat_id = str(uuid.uuid4())
                chat_title = prompt[:30] if len(prompt) > 30 else prompt
            else:
                current_chats = get_user_all_chats(st.session_state.username)
                chat_title = current_chats.get(st.session_state.current_chat_id, {}).get("title", prompt[:30])

            # Xử lý lưu ảnh vào tin nhắn
            img_b64 = ""
            pil_image = None
            if uploaded_chat_img:
                pil_image = Image.open(uploaded_chat_img)
                img_b64 = image_to_base64(pil_image)

            user_msg = {"role": "user", "content": prompt}
            if img_b64:
                user_msg["image_base64"] = img_b64

            st.session_state.messages.append(user_msg)

            with st.chat_message("user"):
                st.markdown(prompt)
                if pil_image:
                    st.image(pil_image, width=300)

            with st.chat_message("assistant"):
                search_context = ""
                if enable_web_search:
                    with st.status("🔍 Đang tìm kiếm thông tin trên Web...", expanded=False):
                        search_results, provider_used = search_web_multi_fallback(prompt, st.session_state.username)
                        if search_results:
                            search_context = f"\n\n[Dữ liệu tìm kiếm thời gian thực từ Web ({provider_used})]:\n{search_results}\n\nHãy tổng hợp thông tin từ dữ liệu web trên để trả lời câu hỏi của người dùng một cách chính xác nhất."
                            st.write(f"Đã tìm thấy dữ liệu từ nguồn: **{provider_used}**")

                system_instruction = "Bạn tên là Astrox AI, do Nguyễn Khôi Nguyên phát triển."
                response = ""

                # 1. XỬ LÝ CÁC MODEL INVISIBLE 3.6 / 4.0 (GEMINI API - HỖ TRỢ XỬ LÝ ẢNH)
                if "Invisible 3.6" in model_choice or "Invisible 4.0" in model_choice:
                    if not INVISIBLE_API_KEY:
                        response = "⚠️ Chưa cấu hình `INVISIBLE_API_KEY` trong Secrets!"
                    else:
                        try:
                            gemini_client = genai.Client(api_key=INVISIBLE_API_KEY)
                            
                            contents_payload = []
                            # Nếu có ảnh đính kèm -> đưa ảnh vào payload
                            if pil_image:
                                contents_payload.append(pil_image)

                            conversation_text = f"System: {system_instruction}\n"
                            for msg in st.session_state.messages[:-1]:
                                conversation_text += f"{msg['role'].capitalize()}: {msg['content']}\n"
                            
                            conversation_text += f"User: {prompt} {search_context}"
                            contents_payload.append(conversation_text)

                            res = gemini_client.models.generate_content(
                                model='gemini-2.5-flash',
                                contents=contents_payload
                            )
                            response = res.text
                        except Exception as e:
                            response = f"Lỗi Gemini Vision API: {e}"

                # 2. XỬ LÝ MODEL INVISIBLE-FLASH 3.5 (GROQ API - CHỈ VĂN BẢN)
                else:
                    if pil_image:
                        st.warning("⚠️ Model Groq hiện tại chưa hỗ trợ quét ảnh. Hệ thống đã tự động phân tích câu hỏi dạng chữ.")
                    if not ASTROX_API_KEY:
                        response = "⚠️ Chưa cấu hình `ASTROX_API_KEY` trong Secrets!"
                    else:
                        client = Groq(api_key=ASTROX_API_KEY)

                        messages_to_send = [{"role": "system", "content": system_instruction}]
                        for msg in st.session_state.messages[:-1]:
                            messages_to_send.append({"role": msg["role"], "content": msg["content"]})
                        
                        latest_user_content = prompt + search_context
                        messages_to_send.append({"role": "user", "content": latest_user_content})

                        try:
                            completion = client.chat.completions.create(
                                model="llama-3.3-70b-versatile",
                                messages=messages_to_send
                            )
                            response = completion.choices[0].message.content
                        except Exception as e:
                            response = f"Lỗi Groq API: {e}"

                st.markdown(response)

            st.session_state.messages.append({"role": "assistant", "content": response})

            save_user_chat_session(
                st.session_state.username,
                st.session_state.current_chat_id,
                chat_title,
                st.session_state.messages
            )
            st.rerun()
