import os
import json
import hashlib
import base64
import streamlit as st
from groq import Groq
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image

# --- CẤU HÌNH & TẢI BIẾN MÔI TRƯỜNG ---
load_dotenv()
ASTROX_API_KEY = st.secrets.get("ASTROX_API_KEY", os.getenv("ASTROX_API_KEY"))

# Tên file logo gốc
LOGO_FILE = "astrox_logo.png"

st.set_page_config(page_title="Astrox AI", page_icon=LOGO_FILE, layout="wide")

# --- QUẢN LÝ DATABASE TRÊN MÁY / CLOUD ---
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
        "avatar_base64": "" # Khởi tạo avatar trống
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

# --- CHỨC NĂNG CHAT ---
def get_user_chat_history(username):
    chats = load_db(CHATS_FILE)
    return chats.get(username, [])

def save_user_chat_history(username, messages):
    chats = load_db(CHATS_FILE)
    chats[username] = messages
    save_db(chats, CHATS_FILE)

# --- KHỞI TẠO TRẠNG THÁI PHIÊN ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_account_page" not in st.session_state:
    st.session_state.show_account_page = False

# --- GIAO DIỆN CHÍNH ---

# Hiển thị Logo Astrox và Tiêu đề
cols_head = st.columns([1, 4])
with cols_head[0]:
    if os.path.exists(LOGO_FILE):
        st.image(LOGO_FILE, width=150)
with cols_head[1]:
    st.title("Astrox AI")
    st.caption("Intelligence & Innovation — Into the Infinite Era")

# --- LOGIN / REGISTER PAGE ---
if not st.session_state.logged_in:
    tab_login, tab_register = st.tabs(["Đăng nhập", "Đăng ký"])

    with tab_login:
        st.subheader("Đăng nhập")
        login_user = st.text_input("Tên đăng nhập", key="login_user")
        login_pass = st.text_input("Mật khẩu", type="password", key="login_pass")
        
        if st.button("Đăng nhập", type="primary"):
            if authenticate_user(login_user, login_pass):
                st.session_state.logged_in = True
                st.session_state.username = login_user
                # Tải lịch sử chat
                st.session_state.messages = get_user_chat_history(login_user)
                st.success("Đăng nhập thành công!")
                st.rerun()
            else:
                st.error("Tên đăng nhập hoặc mật khẩu không chính xác!")

    with tab_register:
        st.subheader("Đăng ký tài khoản")
        reg_user = st.text_input("Tên đăng nhập mới", key="reg_user")
        reg_pass = st.text_input("Mật khẩu mới", type="password", key="reg_pass")
        reg_pass_confirm = st.text_input("Xác nhận mật khẩu", type="password", key="reg_pass_confirm")
        
        if st.button("Đăng ký & Vào AI"):
            if not reg_user or not reg_pass:
                st.warning("Vui lòng điền đầy đủ thông tin!")
            elif reg_pass != reg_pass_confirm:
                st.error("Mật khẩu xác nhận không khớp!")
            else:
                if register_user(reg_user, reg_pass):
                    # --- LOGIC MỚI: VÀO THẲNG AI ---
                    st.session_state.logged_in = True
                    st.session_state.username = reg_user
                    # Khởi tạo lịch sử chat trống cho người dùng mới
                    st.session_state.messages = [] 
                    save_user_chat_history(reg_user, st.session_state.messages)
                    st.success("Đăng ký thành công! Đang vào Astrox AI...")
                    st.rerun()
                else:
                    st.error("Tên đăng nhập này đã có người sử dụng!")

# --- CHAT & ACCOUNT PAGES (KHI ĐÃ ĐĂNG NHẬP) ---
else:
    # --- THANH BÊN (SIDEBAR) ---
    with st.sidebar:
        users = load_db(DB_FILE)
        current_user_data = users.get(st.session_state.username, {})
        user_avatar_base64 = current_user_data.get("avatar_base64", "")
        
        st.markdown(f"**Xin chào, {st.session_state.username}**")

        # Hiển thị Avatar
        avatar_img = base64_to_image(user_avatar_base64)
        if avatar_img:
            st.image(avatar_img, width=100)
        else:
            # Hiển thị icon mặc định nếu chưa có avatar
            st.markdown("👤", help="Chưa có avatar")
            
        st.write(f"Model: **Asteroid 1.24**")
        st.write(f"Nhà phát triển: **Nguyễn Khôi Nguyên**")
        
        # Nút chuyển trang Account
        if st.button("Quản lý tài khoản", key="goto_account"):
            st.session_state.show_account_page = not st.session_state.show_account_page

        if st.button("Xóa lịch sử chat hiện tại"):
            st.session_state.messages = []
            save_user_chat_history(st.session_state.username, st.session_state.messages)
            st.rerun()

        if st.button("Đăng xuất"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.messages = []
            st.rerun()

    # --- TRANG QUẢN LÝ TÀI KHOẢN ---
    if st.session_state.show_account_page:
        st.header(f"Tài khoản của {st.session_state.username}")
        st.write("---")
        
        # Upload Ảnh Đại diện
        st.subheader("Cập nhật ảnh đại diện")
        uploaded_file = st.file_uploader("Chọn ảnh đại diện của bạn", type=["png", "jpg", "jpeg"])
        
        if uploaded_file is not None:
            # Xử lý và lưu ảnh
            try:
                img = Image.open(uploaded_file)
                # Tùy chọn: Resize ảnh để tối ưu dung lượng
                img.thumbnail((200, 200)) # Resize max 200x200

                avatar_base64 = image_to_base64(img)
                if update_user_avatar(st.session_state.username, avatar_base64):
                    st.success("Đã cập nhật ảnh đại diện thành công!")
                    st.rerun() # Tải lại trang để hiển thị ảnh mới trên sidebar
                else:
                    st.error("Lỗi khi cập nhật ảnh đại diện.")
            except Exception as e:
                st.error(f"Lỗi xử lý ảnh: {e}")
        
        # Quay lại trang chat
        if st.button("Quay lại chat"):
            st.session_state.show_account_page = False
            st.rerun()

    # --- TRANG CHAT AI CHÍNH ---
    else:
        st.subheader("Trợ lý Astrox AI")
        
        if not ASTROX_API_KEY:
            st.error("Chưa cấu hình ASTROX_API_KEY!")
        else:
            client = Groq(api_key=ASTROX_API_KEY)

            # Hiển thị lịch sử chat
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Ô nhập câu hỏi
            if prompt := st.chat_input("Hỏi Astrox AI bất kỳ điều gì..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                save_user_chat_history(st.session_state.username, st.session_state.messages) # Lưu ngay lập tức
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    system_instruction = (
                        "Bạn tên là Astrox AI, sử dụng mô hình Asteroid 1.24. "
                        "Người sáng tạo ra bạn là Nguyễn Khôi Nguyên. "
                        "Khi ai đó hỏi bạn, hãy trả lời chính xác rằng bạn là Astrox AI (mô hình Asteroid 1.24) do Nguyễn Khôi Nguyên phát triển. "
                        "Tuyệt đối không tự nhận là do Meta, OpenAI hay Groq tạo ra."
                    )

                    completion = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[
                            {"role": "system", "content": system_instruction},
                            *st.session_state.messages
                        ]
                    )
                    response = completion.choices[0].message.content
                    st.markdown(response)

                st.session_state.messages.append({"role": "assistant", "content": response})
                # Lưu lịch sử chat hoàn chỉnh
                save_user_chat_history(st.session_state.username, st.session_state.messages)
