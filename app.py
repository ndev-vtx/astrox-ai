import os
import json
import hashlib
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
BOT_AVATAR = LOGO_FILE if os.path.exists(LOGO_FILE) else "✨"

st.set_page_config(
    page_title="Astrox",
    page_icon=BOT_AVATAR,
    layout="wide",
    initial_sidebar_state="expanded"
)

def inject_custom_css():
    st.markdown("""
    <style>
        :root { color-scheme: light !important; }
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { 
            background-color: #fafafa !important; 
            color: #1f2937 !important; 
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, sans-serif !important;
        }
        
        [data-testid="stSidebar"] { 
            background-color: #f3f4f6 !important; 
            border-right: 1px solid #e5e7eb !important; 
        }
        [data-testid="stSidebarNav"] { display: none; }
        
        [data-testid="stSidebar"] > div:first-child {
            padding: 1.2rem 0.8rem;
        }

        .stButton button {
            border-radius: 12px !important;
            border: 1px solid #e5e7eb !important;
            background-color: #ffffff !important;
            color: #374151 !important;
            font-weight: 500 !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
            transition: all 0.2s ease !important;
        }
        .stButton button:hover {
            border-color: #3b82f6 !important;
            color: #2563eb !important;
            background-color: #eff6ff !important;
        }

        div[data-testid="column"] .stButton > button {
            border-radius: 20px !important;
            padding: 6px 16px !important;
        }

        [data-testid="stChatInput"] {
            border-radius: 20px !important;
            border: 1px solid #e5e7eb !important;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05) !important;
            background-color: #ffffff !important;
        }
        
        div[data-testid="stPopover"] > button {
            width: 100% !important;
            border: none !important;
            background-color: transparent !important;
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 10px 12px !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
        }
        div[data-testid="stPopover"] > button:hover {
            background-color: #e5e7eb !important;
        }

        .main-title {
            font-size: 28px;
            font-weight: 700;
            color: #111827;
            text-align: center;
            margin-top: 40px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

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
        return "error", f"Error reading file: {e}"
    return None, None

def search_duckduckgo(q):
    try:
        with DDGS() as ddgs:
            res = [f"📌 **{r.get('title')}**\n{r.get('body')}" for r in ddgs.text(q, max_results=3)]
            return "\n\n".join(res) if res else "No results found."
    except Exception as e: return f"Search Error: {e}"

SYSTEM_PROMPT = (
    "You are Astrox, an intelligent AI assistant created and developed by Nguyễn Khôi Nguyên (NKN). "
    "Respond directly, helpfully, and naturally. When greeted (such as 'hi' or 'hello'), reply simply and concisely with a greeting like 'Hello! How can I help you today?' without giving an unprompted introduction or background about yourself. "
    "Only mention your creator/developer if specifically asked."
)

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = ""
if "current_chat_id" not in st.session_state: st.session_state.current_chat_id = None
if "messages" not in st.session_state: st.session_state.messages = []
if "selected_model" not in st.session_state: st.session_state.selected_model = "NKN Intelligent"
if "enable_search" not in st.session_state: st.session_state.enable_search = False
if "last_processed_audio_hash" not in st.session_state: st.session_state.last_processed_audio_hash = ""

MODELS = {
    "NKN Intelligent": ("openrouter", "deepseek/deepseek-chat", "⚡"),
    "NKN Cloud": ("cloudflare", "@cf/meta/llama-3.1-8b-instruct", "💎"),
    "NKN Vision": ("gemini", "gemini-3.6-flash", "📷")
}

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
        st.radio("Theme", ["Light", "Dark", "System"], index=0, horizontal=True, label_visibility="collapsed")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Language**")
        st.selectbox("Language", ["English", "Tiếng Việt"], index=0, label_visibility="collapsed")

if not st.session_state.logged_in:
    st.write("<br><br>", unsafe_allow_html=True)
    _, c_mid, _ = st.columns([1, 1.2, 1])
    with c_mid:
        if os.path.exists(LOGO_FILE): st.image(LOGO_FILE, width=70)
        st.title("Astrox")
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
                else: st.error("Incorrect password!")

        with t_reg:
            r_u = st.text_input("Username (New)", key="ru")
            r_p = st.text_input("Password (New)", type="password", key="rp")
            if st.button("Create Account", type="primary", use_container_width=True):
                users = load_db(DB_FILE)
                if r_u and r_u not in users:
                    users[r_u] = {"password": hash_password(r_p)}
                    save_db(users, DB_FILE)
                    st.session_state.logged_in = True; st.session_state.username = r_u; st.rerun()
                else: st.error("Username already exists!")

else:
    with st.sidebar:
        sb_col1, sb_col2 = st.columns([4, 1])
        with sb_col1:
            st.markdown("### ✨ Astrox")
        
        if st.button("➕ New chat", use_container_width=True):
            st.session_state.current_chat_id = None
            st.session_state.messages = []
            st.rerun()
        st.write("")

        st.caption("CHAT HISTORY")
        chats_db = load_db(CHATS_FILE).get(st.session_state.username, {})
        for c_id, c_data in reversed(list(chats_db.items())):
            c1, c2 = st.columns([4, 1])
            with c1:
                title = c_data.get("title", "New Chat")[:18]
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

        st.markdown("<br><br>", unsafe_allow_html=True)
        st.divider()

        user_display = f"👤 **{st.session_state.username}**"
        with st.popover(user_display, use_container_width=True):
            if st.button("⚙️ Settings", use_container_width=True):
                show_settings_dialog()
            if st.button("🚪 Log out", use_container_width=True):
                st.session_state.logged_in = False
                st.rerun()

    if not st.session_state.messages:
        active_model = st.session_state.selected_model
        st.markdown(
            f'<div class="main-title">✨ Start chatting with <b>{active_model}</b></div>', 
            unsafe_allow_html=True
        )

        _, p1, p2, p3, _ = st.columns([1, 1.2, 1.2, 1.2, 1])
        with p1:
            if st.button("⚡ NKN Intelligent", use_container_width=True, type="primary" if active_model == "NKN Intelligent" else "secondary"):
                st.session_state.selected_model = "NKN Intelligent"
                st.rerun()
        with p2:
            if st.button("💎 NKN Cloud", use_container_width=True, type="primary" if active_model == "NKN Cloud" else "secondary"):
                st.session_state.selected_model = "NKN Cloud"
                st.rerun()
        with p3:
            if st.button("📷 NKN Vision", use_container_width=True, type="primary" if active_model == "NKN Vision" else "secondary"):
                st.session_state.selected_model = "NKN Vision"
                st.rerun()

        st.write("<br>", unsafe_allow_html=True)

    else:
        for m in st.session_state.messages:
            avatar = BOT_AVATAR if m["role"] == "assistant" else None
            with st.chat_message(m["role"], avatar=avatar):
                st.markdown(m["content"])

    with st.expander("📎 Attach Files & 🎙️ Micro Input", expanded=False):
        c_up1, c_up2 = st.columns(2)
        with c_up1:
            uploaded_file = st.file_uploader("Upload Document / Image", type=["png", "jpg", "jpeg", "pdf", "docx", "txt"])
        with c_up2:
            audio_recorded = st.audio_input("Record Voice")

    st.session_state.enable_search = st.toggle("🌐 Web Search", value=st.session_state.enable_search)

    prompt_input = st.chat_input("Message Astrox...")
    prompt = prompt_input

    if audio_recorded and not prompt:
        audio_bytes = audio_recorded.getvalue()
        current_audio_hash = hashlib.md5(audio_bytes).hexdigest()
        if current_audio_hash != st.session_state.last_processed_audio_hash:
            if client_gemini:
                with st.spinner("🎙️ Transcribing audio..."):
                    try:
                        res_audio = client_gemini.models.generate_content(
                            model="gemini-3.6-flash",
                            contents=[types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"), "Transcribe audio accurately:"]
                        )
                        prompt = res_audio.text.strip()
                        st.session_state.last_processed_audio_hash = current_audio_hash
                    except Exception as e: st.error(f"Speech error: {e}")

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

            if provider == "openrouter":
                if not client_openrouter: response = "⚠️ Missing `OPENROUTER_API_KEY`."
                else:
                    try:
                        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
                        for m in st.session_state.messages[:-1]: msgs.append({"role": m["role"], "content": m["content"]})
                        msgs.append({"role": "user", "content": final_prompt})
                        res = client_openrouter.chat.completions.create(model=model_id, messages=msgs, stream=False)
                        response = res.choices[0].message.content
                    except Exception as e: response = f"❌ Error: {e}"

            elif provider == "cloudflare":
                if not CLOUDFLARE_API_KEY or not CLOUDFLARE_ACCOUNT_ID: response = "⚠️ Missing Cloudflare Keys."
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
