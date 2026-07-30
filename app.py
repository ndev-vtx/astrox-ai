import os
import json
import hashlib
import streamlit as st
from groq import Groq
from dotenv import load_dotenv


load_dotenv()


ASTROX_API_KEY = st.secrets.get("ASTROX_API_KEY", os.getenv("ASTROX_API_KEY"))

st.set_page_config(page_title="Astrox AI", page_icon="🚀", layout="centered")


DB_FILE = "users_db.json"

def load_users():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users_data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users_data, f, ensure_ascii=False, indent=4)

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def register_user(username, password):
    users = load_users()
    if username in users:
        return False
    users[username] = hash_password(password)
    save_users(users)
    return True

def authenticate_user(username, password):
    users = load_users()
    if username in users and users[username] == hash_password(password):
        return True
    return False


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "messages" not in st.session_state:
    st.session_state.messages = []


if not st.session_state.logged_in:
    st.title("🚀 Astrox AI System")
    st.caption("Astrox AI — Into the New Era")
    
    tab_login, tab_register = st.tabs(["Đăng nhập", "Đăng ký tài khoản"])

    with tab_login:
        st.subheader("Đăng nhập vào Astrox AI")
        login_user = st.text_input("Tên đăng nhập", key="login_user")
        login_pass = st.text_input("Mật khẩu", type="password", key="login_pass")
        
        if st.button("Đăng nhập", type="primary"):
            if authenticate_user(login_user, login_pass):
                st.session_state.logged_in = True
                st.session_state.username = login_user
                st.success("Đăng nhập thành công!")
                st.rerun()
            else:
                st.error("Tên đăng nhập hoặc mật khẩu không chính xác!")

    with tab_register:
        st.subheader("Tạo tài khoản Astrox mới")
        reg_user = st.text_input("Tên đăng nhập mới", key="reg_user")
        reg_pass = st.text_input("Mật khẩu mới", type="password", key="reg_pass")
        reg_pass_confirm = st.text_input("Xác nhận mật khẩu", type="password", key="reg_pass_confirm")
        
        if st.button("Đăng ký"):
            if not reg_user or not reg_pass:
                st.warning("Vui lòng điền đầy đủ thông tin!")
            elif reg_pass != reg_pass_confirm:
                st.error("Mật khẩu xác nhận không khớp!")
            else:
                if register_user(reg_user, reg_pass):
                    st.success("Đăng ký thành công! Bạn có thể chuyển sang tab Đăng nhập ngay bây giờ.")
                else:
                    st.error("Tên đăng nhập này đã có người sử dụng!")


else:
    # Thanh bên (Sidebar)
    with st.sidebar:
        st.title("🚀 Astrox AI")
        st.write(f"👤 Tài khoản: **{st.session_state.username}**")
        st.info("🤖 Model: **Asteroid 1.24**")
        st.caption("👨‍💻 Tác giả: **Nguyễn Khôi Nguyên**")
        
        if st.button("Xóa lịch sử chat"):
            st.session_state.messages = []
            st.rerun()

        if st.button("Đăng xuất"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.messages = []
            st.rerun()

    st.title("🚀 Trợ lý Astrox AI")
    st.caption("Astrox AI — Into the New Era")
    
    if not ASTROX_API_KEY:
        st.error("Chưa cấu hình ASTROX_API_KEY! Vui lòng thêm key vào File .env hoặc Streamlit Secrets.")
    else:
        client = Groq(api_key=ASTROX_API_KEY)

        # Hiển thị lịch sử chat
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Ô nhập câu hỏi
        if prompt := st.chat_input("Hỏi Astrox AI bất kỳ điều gì..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                system_instruction = (
                    "Bạn tên là Astrox AI, sử dụng mô hình Asteroid 1.24. "
                    "Người sáng tạo ra bạn là Nguyễn Khôi Nguyên. "
                    "Nếu ai hỏi bạn là ai, tên gì, dùng mô hình gì hay ai tạo ra bạn, "
                    "hãy trả lời chính xác rằng bạn là Astrox AI (mô hình Asteroid 1.24) do Nguyễn Khôi Nguyên phát triển. "
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
