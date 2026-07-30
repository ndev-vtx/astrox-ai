import os
import json
import hashlib
import base64
import uuid
import streamlit as st
from groq import Groq
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image

load_dotenv()
ASTROX_API_KEY = st.secrets.get("ASTROX_API_KEY", os.getenv("ASTROX_API_KEY"))

LOGO_FILE = "astrox_logo.png"

st.set_page_config(page_title="Astrox AI", page_icon=LOGO_FILE if os.path.exists(LOGO_FILE) else "🤖", layout="wide")

DB_FILE = "users_db.json"
CHATS_FILE = "chats_db.json"

def load_db(file_name):
    if not os.path.exists(file_name):
        return {}
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_db(data, file_name):
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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
    if username in users and users[username]["password"] == hash_password(password):
        return True
    return False

def update_user_avatar(username, avatar_base64):
    users = load_db(DB_FILE)
    if username in users:
        users[username]["avatar_base64"] = avatar_base64
        save_db(users, DB_FILE)
        return True
    return False


def get_user_all_chats(username):
    chats = load_db(CHATS_FILE)
    return chats.get(username, {})

def save_user_chat_session(username, chat_id, title, messages):
    chats = load_db(CHATS_FILE)
    if username not in chats:
        chats[username] = {}
    chats[username][chat_id] = {
        "title": title,
        "messages": messages
    }
    save_db(chats, CHATS_FILE)

def delete_user_chat_session(username, chat_id):
    chats = load_db(CHATS_FILE)
    if username in chats and chat_id in chats[username]:
        del chats[username][chat_id]
        save_db(chats, CHATS_FILE)

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
if "auth_error" not in st.session_state:
    st.session_state.auth_error = ""

# --- GIAO DIỆN CHÍNH (HEADER) ---
cols_head = st.columns([1, 4])
with cols_head[0]:
    if os.path.exists(LOGO_FILE):
        st.image(LOGO_FILE, width=110)
with cols_head[1]:
    st.title("Astrox AI")
    st.caption("Intelligence & Innovation — Into the Infinite Era")

# --- TRANG DĂNG NHẬP / ĐĂNG KÝ ---
if not st.session_state.logged_in:
    tab_login, tab_register = st.tabs(["Đăng nhập", "Đăng ký"])

    with tab_login:
        st.subheader("Đăng nhập")
        login_user = st.text_input("Tên đăng nhập", key="login_user")
        login_pass = st.text_input("Mật khẩu", type="password", key="login_pass")
        
        if st.button("Đăng nhập", type="primary", key="btn_login"):
            if not login_user or not login_pass:
                st.warning("Vui lòng điền đầy đủ tên đăng nhập và mật khẩu!")
            elif authenticate_user(login_user, login_pass):
                st.session_state.logged_in = True
                st.session_state.username = login_user
                st.session_state.current_chat_id = None
                st.session_state.messages = []
                st.session_state.auth_error = ""
                st.success("Đăng nhập thành công!")
                st.rerun()
            else:
                st.error("Tài khoản chưa tồn tại hoặc sai mật khẩu!")

    with tab_register:
        st.subheader("Đăng ký tài khoản mới")
        reg_user = st.text_input("Tên đăng nhập mới", key="reg_user")
        reg_pass = st.text_input("Mật khẩu mới", type="password", key="reg_pass")
        reg_pass_confirm = st.text_input("Xác nhận mật khẩu", type="password", key="reg_pass_confirm")
        
        if st.button("Đăng ký & Vào AI ngay", type="primary", key="btn_reg"):
            if not reg_user or not reg_pass:
                st.warning("Vui lòng điền đầy đủ thông tin!")
            elif reg_pass != reg_pass_confirm:
                st.error("Mật khẩu xác nhận không khớp!")
            else:
                if register_user(reg_user, reg_pass):

                    st.session_state.logged_in = True
                    st.session_state.username = reg_user
                    st.session_state.current_chat_id = None
                    st.session_state.messages = []
                    st.session_state.auth_error = ""
                    st.success("Tạo tài khoản thành công! Đang tiến vào Astrox AI...")
                    st.rerun()
                else:
                    st.error("Tên đăng nhập này đã có người sử dụng! Vui lòng chọn tên khác.")

else:

    with st.sidebar:
        users = load_db(DB_FILE)
        current_user_data = users.get(st.session_state.username, {})
        user_avatar_base64 = current_user_data.get("avatar_base64", "")
        
        # Thông tin User & Avatar
        col_av, col_name = st.columns([1, 2])
        with col_av:
            avatar_img = base64_to_image(user_avatar_base64)
            if avatar_img:
                st.image(avatar_img, width=60)
            else:
                st.markdown("👤", help="Chưa có avatar")
        with col_name:
            st.markdown(f"**{st.session_state.username}**")
            if st.button("⚙️ Tài khoản", key="goto_account"):
                st.session_state.show_account_page = not st.session_state.show_account_page
                st.rerun()

        st.divider()

        if st.button("➕ Đoạn chat mới", use_container_width=True, type="primary"):
            st.session_state.current_chat_id = None
            st.session_state.messages = []
            st.session_state.show_account_page = False
            st.rerun()

        st.markdown("### 🔍 Tìm kiếm chat")
        search_kw = st.text_input("Nhập từ khóa...", key="search_chat_kw", label_visibility="collapsed")

        st.markdown("### 📜 Lịch sử trò chuyện")
        user_chats = get_user_all_chats(st.session_state.username)

        filtered_chats = {}
        for c_id, c_data in user_chats.items():
            title = c_data.get("title", "Trò chuyện mới")
            if not search_kw or search_kw.lower() in title.lower():
                filtered_chats[c_id] = c_data

        if not filtered_chats:
            st.caption("Chưa có lịch sử hoặc không tìm thấy.")
        else:
            # Hiển thị danh sách các mục Chat
            for c_id, c_data in reversed(list(filtered_chats.items())):
                title = c_data.get("title", "Trò chuyện mới")
 
                display_title = title[:22] + "..." if len(title) > 22 else title
                
                col_c1, col_c2 = st.columns([4, 1])
                with col_c1:
            
                    is_current = (c_id == st.session_state.current_chat_id)
                    btn_label = f"💬 {display_title}" if not is_current else f"👉 {display_title}"
                    if st.button(btn_label, key=f"chat_{c_id}", use_container_width=True):
                        st.session_state.current_chat_id = c_id
                        st.session_state.messages = c_data.get("messages", [])
                        st.session_state.show_account_page = False
                        st.rerun()
                with col_c2:

                    if st.button("🗑️", key=f"del_{c_id}"):
                        delete_user_chat_session(st.session_state.username, c_id)
                        if st.session_state.current_chat_id == c_id:
                            st.session_state.current_chat_id = None
                            st.session_state.messages = []
                        st.rerun()

        st.divider()

        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.current_chat_id = None
            st.session_state.messages = []
            st.session_state.show_account_page = False
            st.rerun()

    # Trang quản lý tài khoản
    if st.session_state.show_account_page:
        st.header(f"Cài đặt tài khoản: {st.session_state.username}")
        st.write("---")
        
        st.subheader("Cập nhật ảnh đại diện")
        uploaded_file = st.file_uploader("Tải lên ảnh mới (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"])
        
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
        st.subheader("Trợ lý Astrox AI")
        st.caption("Model: **Asteroid 1.24** | Phát triển bởi: **Nguyễn Khôi Nguyên**")

        if not ASTROX_API_KEY:
            st.error("Chưa cấu hình API Key cho Astrox AI!")
        else:
            client = Groq(api_key=ASTROX_API_KEY)

            # Hiển thị các tin nhắn của hội thoại hiện tại
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if prompt := st.chat_input("Hỏi Astrox AI bất kỳ điều gì..."):

                if st.session_state.current_chat_id is None:
                    st.session_state.current_chat_id = str(uuid.uuid4())
                    chat_title = prompt[:30] if len(prompt) > 30 else prompt
                else:
                    # Lấy lại tiêu đề cũ
                    current_chats = get_user_all_chats(st.session_state.username)
                    chat_title = current_chats.get(st.session_state.current_chat_id, {}).get("title", prompt[:30])

                # Thêm câu hỏi người dùng
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                # AI trả lời
                with st.chat_message("assistant"):
                    system_instruction = (
                        "Bạn tên là Astrox AI, sử dụng mô hình Asteroid 1.24. "
                        "Người sáng tạo ra bạn là Nguyễn Khôi Nguyên. "
                        "Khi được hỏi, hãy khẳng định bạn là Astrox AI (mô hình Asteroid 1.24) do Nguyễn Khôi Nguyên phát triển. "
                        "Tuyệt đối không tự nhận là do Meta, OpenAI hay Groq tạo ra."
                    )

                    try:
                        completion = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[
                                {"role": "system", "content": system_instruction},
                                *st.session_state.messages
                            ]
                        )
                        response = completion.choices[0].message.content
                    except Exception as e:
                        response = f"Lỗi kết nối AI: {e}"

                    st.markdown(response)

                st.session_state.messages.append({"role": "assistant", "content": response})

                # Tự động lưu mục Chat vào database
                save_user_chat_session(
                    st.session_state.username,
                    st.session_state.current_chat_id,
                    chat_title,
                    st.session_state.messages
                )
                st.rerun()
