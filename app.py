import os
import json
import hashlib
import base64
import uuid
import streamlit as st
from groq import Groq
from google import genai
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image
import extra_streamlit_components as stx
from duckduckgo_search import DDGS

# --- CẤU HÌNH & TẢI BIẾN MÔI TRƯỜNG ---
load_dotenv()
# Đọc API Key từ Secrets hoặc môi trường
ASTROX_API_KEY = st.secrets.get("ASTROX_API_KEY", os.getenv("ASTROX_API_KEY"))
ARTICFIC_API_KEY = st.secrets.get("ARTICFIC_API_KEY", os.getenv("ARTICFIC_API_KEY"))

LOGO_FILE = "astrox_logo.png"

st.set_page_config(
    page_title="Astrox AI",
    page_icon=LOGO_FILE if os.path.exists(LOGO_FILE) else "✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Quản lý Cookie
cookie_manager = stx.CookieManager()

# --- CSS TÙY CHỈNH NỀN TRẮNG MẶC ĐỊNH & CHỐNG LỖI TƯƠNG PHẢN ---
st.markdown("""
<style>
    /* Nền trắng mặc định */
    .stApp {
        background-color: #ffffff;
        color: #1f2328;
    }
    
    /* Sidebar nền xám nhẹ thanh lịch */
    [data-testid="stSidebar"] {
        background-color: #f6f8fa;
        border-right: 1px solid #d0d7de;
    }

    /* Thẻ gợi ý kiểu Gemini cho nền sáng */
    .suggestion-card {
        background-color: #f6f8fa;
        border: 1px solid #d0d7de;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        color: #1f2328;
    }
    
    /* Ô chat bo tròn hiện đại */
    .stChatInputContainer {
        border-radius: 24px !important;
        border: 1px solid #d0d7de !important;
    }

    /* HỖ TRỢ NỀN ĐEN: Tự động chỉnh chữ trắng khi phát hiện Dark Mode */
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

# --- HÀM TÌM KIẾM WEB ---
def search_web(query, max_results=4):
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"Tiêu đề: {r.get('title')}\nTrích dẫn: {r.get('body')}\nLink: {r.get('href')}")
        return "\n\n".join(results)
    except Exception as e:
        return f"Không thể tìm kiếm web: {e}"

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
        "avatar_base64": ""
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

# TỰ ĐỘNG ĐĂNG NHẬP NẾU CÓ COOKIE
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
    # HỘP THOẠI XÁC NHẬN XÓA
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

        # Nút tạo đoạn chat mới
        if st.button("➕ Cuộc trò chuyện mới", use_container_width=True, type="primary"):
            st.session_state.current_chat_id = None
            st.session_state.messages = []
            st.session_state.show_account_page = False
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        
        # LỰA CHỌN MÔ HÌNH AI
        model_choice = st.selectbox(
            "⚡ Chọn mô hình AI:",
            options=[
                "🚀 Asteroid Fast", 
                "🧠 Asteroid Thông minh",
                "⚡ Artisfic 2.0 (Gemini)",
                "✨ Artisfic 3.0 (Gemini)"
            ],
            index=0,
            help="Asteroid Fast & Artisfic phản hồi siêu nhanh. Asteroid Thông minh tư duy sâu hơn."
        )

        # Bật/tắt Tìm kiếm Web
        enable_web_search = st.toggle("🌐 Tìm kiếm Web thực tế", value=False, help="Cho phép Astrox AI tra cứu dữ liệu mới nhất trên internet.")

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

        # Thông tin User ở cuối Sidebar
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
        # TRANG CHÀO MỪNG DẠNG GEMINI KHI CHƯA NHẮN TIN
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
            # Hiển thị lịch sử chat
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # NHẬP CÂU HỎI
        prompt_input = st.chat_input("Hỏi Astrox AI bất kỳ điều gì...")
        prompt = prompt_input or (prompt_preset if 'prompt_preset' in locals() else None)

        if prompt:
            if st.session_state.current_chat_id is None:
                st.session_state.current_chat_id = str(uuid.uuid4())
                chat_title = prompt[:30] if len(prompt) > 30 else prompt
            else:
                current_chats = get_user_all_chats(st.session_state.username)
                chat_title = current_chats.get(st.session_state.current_chat_id, {}).get("title", prompt[:30])

            st.session_state.messages.append({"role": "user", "content": prompt})

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                search_context = ""
                if enable_web_search:
                    with st.status("🔍 Đang tìm kiếm thông tin trên Web...", expanded=False):
                        search_results = search_web(prompt)
                        if search_results:
                            search_context = f"\n\n[Dữ liệu tìm kiếm thời gian thực từ Web]:\n{search_results}\n\nHãy tổng hợp thông tin từ dữ liệu web trên để trả lời câu hỏi của người dùng một cách chính xác nhất."
                            st.write("Đã tìm thấy dữ liệu liên quan!")

                system_instruction = (
                    "Bạn tên là Astrox AI. "
                    "Người sáng tạo ra bạn là Nguyễn Khôi Nguyên. "
                    "Khi được hỏi, hãy khẳng định bạn là Astrox AI do Nguyễn Khôi Nguyên phát triển. "
                    "Tuyệt đối không tự nhận là do Meta, OpenAI hay Google tạo ra."
                )

                response = ""

                # 1. XỬ LÝ CÁC MODEL ARTISFIC (CHẠY BẰNG ARTICFIC_API_KEY)
                if "Artisfic" in model_choice:
                    if not ARTICFIC_API_KEY:
                        response = "⚠️ Chưa cấu hình `ARTICFIC_API_KEY` trong Secrets!"
                    else:
                        try:
                            gemini_client = genai.Client(api_key=ARTICFIC_API_KEY)
                            
                            conversation_text = f"System: {system_instruction}\n"
                            for msg in st.session_state.messages[:-1]:
                                conversation_text += f"{msg['role'].capitalize()}: {msg['content']}\n"
                            
                            conversation_text += f"User: {prompt} {search_context}"

                            target_gemini_model = 'gemini-2.5-flash' if "2.0" in model_choice else 'gemini-2.5-flash'

                            res = gemini_client.models.generate_content(
                                model=target_gemini_model,
                                contents=conversation_text
                            )
                            response = res.text
                        except Exception as e:
                            response = f"Lỗi Artisfic API: {e}"

                # 2. XỬ LÝ CÁC MODEL ASTEROID (CHẠY BẰNG ASTROX_API_KEY)
                else:
                    if not ASTROX_API_KEY:
                        response = "⚠️ Chưa cấu hình `ASTROX_API_KEY` trong Secrets!"
                    else:
                        client = Groq(api_key=ASTROX_API_KEY)
                        selected_model = "llama-3.1-8b-instant" if "Fast" in model_choice else "llama-3.3-70b-versatile"

                        messages_to_send = [{"role": "system", "content": system_instruction}]
                        for msg in st.session_state.messages[:-1]:
                            messages_to_send.append(msg)
                        
                        latest_user_content = prompt + search_context
                        messages_to_send.append({"role": "user", "content": latest_user_content})

                        try:
                            completion = client.chat.completions.create(
                                model=selected_model,
                                messages=messages_to_send
                            )
                            response = completion.choices[0].message.content
                        except Exception as e:
                            response = f"Lỗi Asteroid API: {e}"

                st.markdown(response)

            st.session_state.messages.append({"role": "assistant", "content": response})

            save_user_chat_session(
                st.session_state.username,
                st.session_state.current_chat_id,
                chat_title,
                st.session_state.messages
            )
            st.rerun()
