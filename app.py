import os

import openai
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "").strip() or "gpt-6-astra"
MAX_CHARS = 5000

LANGUAGES = {
    "영어": "English",
    "일본어": "Japanese",
    "베트남어": "Vietnamese",
}

SYSTEM_PROMPT = """You are a professional translator.
Translate the user's text into {target_language}.
Preserve the original meaning, tone, and formatting (line breaks, lists).
Keep proper nouns, numbers, and URLs unchanged.
Output only the translated text, with no explanations."""


@st.cache_resource
def get_client(api_key: str) -> openai.OpenAI:
    return openai.OpenAI(api_key=api_key)


def translate(text: str, target_language: str) -> str:
    client = get_client(OPENAI_API_KEY)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(target_language=target_language)},
        {"role": "user", "content": text},
    ]
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL, messages=messages, temperature=0.3
        )
    except openai.BadRequestError as e:
        # 일부 모델은 temperature 조정을 지원하지 않음 → 기본값으로 재시도
        if "temperature" not in str(e):
            raise
        response = client.chat.completions.create(model=OPENAI_MODEL, messages=messages)
    return (response.choices[0].message.content or "").strip()


def error_message(e: Exception) -> str:
    if isinstance(e, openai.AuthenticationError):
        return "API 키가 올바르지 않습니다."
    if isinstance(e, openai.RateLimitError):
        return "요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요."
    if isinstance(e, openai.APIStatusError):
        detail = getattr(e, "message", "") or e.__class__.__name__
        return f"번역 중 오류가 발생했습니다: {detail}"
    if isinstance(e, openai.APIConnectionError):
        return "번역 중 오류가 발생했습니다: 서버에 연결할 수 없습니다."
    return f"번역 중 오류가 발생했습니다: {e.__class__.__name__}"


def run_translation(label: str, text: str) -> None:
    if not text.strip():
        st.session_state.notice = ("warning", "번역할 글을 입력해 주세요.")
        return
    if len(text) > MAX_CHARS:
        st.session_state.notice = (
            "warning",
            f"글이 너무 깁니다. {MAX_CHARS:,}자 이하로 입력해 주세요. (현재 {len(text):,}자)",
        )
        return
    with st.spinner("번역 중입니다..."):
        try:
            result = translate(text, LANGUAGES[label])
        except Exception as e:  # noqa: BLE001 - 모든 오류를 사용자 메시지로 변환
            st.session_state.notice = ("error", error_message(e))
            return
    st.session_state.result = {"source": text, "label": label, "text": result}


FLAGS = {"영어": "🇺🇸", "일본어": "🇯🇵", "베트남어": "🇻🇳"}

CSS = """
<style>
[data-testid="stMainBlockContainer"] { max-width: 760px; padding-top: 3rem; }
h1 { font-weight: 700; letter-spacing: -0.02em; }
.subtitle { opacity: 0.7; margin-top: -0.75rem; margin-bottom: 1.5rem; }
.char-count { text-align: right; font-size: 0.8rem; opacity: 0.6; margin-top: -0.75rem; }
.char-count.over { color: #DC2626; opacity: 1; font-weight: 600; }
.empty-state { text-align: center; opacity: 0.55; padding: 1.5rem 0; }
[data-testid="stCode"] pre,
[data-testid="stCode"] code {
    font-family: "Source Sans Pro", "Source Sans 3", "Malgun Gothic", sans-serif !important;
    font-size: 1rem !important;
    line-height: 1.6 !important;
}
button[kind="primary"] { background-color: #2563EB; border-color: #2563EB; color: #FFFFFF; }
button[kind="primary"]:hover { background-color: #1D4ED8; border-color: #1D4ED8; color: #FFFFFF; }
</style>
"""

st.set_page_config(page_title="다국어 번역기", page_icon="🌐", layout="centered")
st.markdown(CSS, unsafe_allow_html=True)

st.session_state.setdefault("result", None)
st.session_state.setdefault("notice", None)

with st.sidebar:
    st.header("사용 방법")
    st.markdown(
        "1. 번역할 글을 입력합니다.\n"
        "2. 번역할 언어 버튼을 누릅니다.\n"
        "3. 결과 오른쪽 위 아이콘으로 복사합니다."
    )
    st.divider()
    st.caption(f"사용 모델: `{OPENAI_MODEL}`")

st.title("🌐 다국어 번역기")
st.markdown(
    '<p class="subtitle">글을 입력하고 번역할 언어 버튼을 누르세요.</p>',
    unsafe_allow_html=True,
)

if not OPENAI_API_KEY:
    st.error(".env 파일에 OPENAI_API_KEY를 설정해 주세요.")

text = st.text_area(
    "번역할 글",
    placeholder="번역할 글을 입력하세요...",
    height=200,
    label_visibility="collapsed",
)
over = " over" if len(text) > MAX_CHARS else ""
st.markdown(
    f'<p class="char-count{over}">{len(text):,} / {MAX_CHARS:,}자</p>',
    unsafe_allow_html=True,
)

last_label = st.session_state.result["label"] if st.session_state.result else None
clicked = None
cols = st.columns(len(LANGUAGES))
for col, label in zip(cols, LANGUAGES):
    if col.button(
        f"{FLAGS[label]} {label}",
        key=f"btn_{label}",
        type="primary" if label == last_label else "secondary",
        use_container_width=True,
        disabled=not OPENAI_API_KEY,
    ):
        clicked = label

# 메시지 자리를 먼저 비워서, 이전 실행의 경고가 번역 중에 남아 보이지 않게 함
notice_slot = st.empty()
st.session_state.notice = None
if clicked:
    with notice_slot.container():
        run_translation(clicked, text)
    if st.session_state.notice is None and clicked != last_label:
        st.rerun()  # 선택한 언어 버튼 강조를 즉시 반영

if st.session_state.notice:
    kind, msg = st.session_state.notice
    getattr(notice_slot, kind)(msg)
else:
    notice_slot.empty()

result = st.session_state.result
with st.container(border=True):
    if result:
        title = "이전 번역 결과" if st.session_state.notice else "번역 결과"
        st.markdown(f"**{title} · {FLAGS[result['label']]} {result['label']}**")
        st.code(result["text"], language=None, wrap_lines=True)
    else:
        st.markdown(
            '<p class="empty-state">아직 번역된 글이 없습니다.</p>',
            unsafe_allow_html=True,
        )
