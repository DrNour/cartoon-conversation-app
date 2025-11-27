import json
import glob
from pathlib import Path

import streamlit as st

# ---------- Helper functions ----------

CEFR_ORDER = {
    "A1": 1,
    "A2": 2,
    "B1": 3,
    "B2": 4,
    "C1": 5,
    "C2": 6,
    "Beginner": 1,
    "Intermediate": 3,
    "Advanced": 5,
}

def load_lessons():
    lessons = []
    for path_str in glob.glob("data/lessons/**/*.json", recursive=True):
        path = Path(path_str)
        try:
            with open(path, "r", encoding="utf-8") as f:
                lesson = json.load(f)
                lesson["_path"] = str(path)
                lessons.append(lesson)
        except Exception as e:
            print(f"Error loading {path}: {e}")
    return lessons

def normalize_level(level):
    # so "A1" and "Beginner" etc can both work
    return level

def get_sorted_levels(lessons, track):
    levels = {normalize_level(l["level"]) for l in lessons if l["track"] == track}
    # sort by CEFR_ORDER if possible, else alphabetically
    return sorted(levels, key=lambda x: CEFR_ORDER.get(x, 999))

# ---------- UI: tasks ----------

def render_gap_fill_tasks(lesson):
    gap_tasks = lesson.get("tasks", {}).get("gap_fill", [])
    if not gap_tasks:
        return
    st.subheader("Gap-fill practice")
    for i, task in enumerate(gap_tasks, start=1):
        prompt = task["prompt"]
        answer = task["answer"]
        key = f"gap_{lesson['lesson_id']}_{i}"
        user_answer = st.text_input(prompt, key=key)
        if user_answer:
            if user_answer.strip().lower() == answer.strip().lower():
                st.success("✅ Correct!")
            else:
                st.error(f"❌ Not quite. Correct answer: **{answer}**")

def render_multiple_choice_tasks(lesson):
    mc_tasks = lesson.get("tasks", {}).get("multiple_choice", [])
    if not mc_tasks:
        return
    st.subheader("Multiple choice")
    for i, task in enumerate(mc_tasks, start=1):
        question = task["question"]
        options = task["options"]
        answer = task["answer"]
        key = f"mc_{lesson['lesson_id']}_{i}"
        st.write(f"**Q{i}. {question}**")
        choice = st.radio("Choose one:", options, key=key, index=None)
        if choice is not None:
            if choice == answer:
                st.success("✅ Correct!")
            else:
                st.error(f"❌ Correct answer: **{answer}**")

# ---------- App ----------

st.set_page_config(page_title="Cartoon Conversations", page_icon="💬")

st.title("Cartoon Conversations")
st.write("Practice real-life English using short cartoon dialogues.")

lessons = load_lessons()
if not lessons:
    st.error("No lessons found. Please add JSON files in `data/lessons/`.")
    st.stop()

tracks = sorted({l["track"] for l in lessons})
track = st.sidebar.selectbox("Choose track", tracks)

levels = get_sorted_levels(lessons, track)
level = st.sidebar.selectbox("Choose level", levels)

filtered = [l for l in lessons if l["track"] == track and normalize_level(l["level"]) == level]

if not filtered:
    st.warning("No lessons for this track and level yet.")
    st.stop()

lesson_titles = [l["title"] for l in filtered]
selected_title = st.selectbox("Choose a lesson", lesson_titles)
lesson = next(l for l in filtered if l["title"] == selected_title)

st.header(lesson["title"])

# 1) Cartoon panels
st.subheader("1. Look at the cartoon")
for img_path in lesson.get("cartoon_panels", []):
    path = Path(img_path)
    if path.exists():
        st.image(str(path), use_column_width=True)
    else:
        st.info(f"Image not found: `{img_path}`")

# 2) Dialogue
st.subheader("2. Listen and read")
for turn in lesson.get("dialogue", []):
    speaker = turn.get("speaker", "")
    text = turn.get("text", "")
    st.markdown(f"**{speaker}:** {text}")
    audio_path = turn.get("audio")
    if audio_path:
        audio_file = Path(audio_path)
        if audio_file.exists():
            st.audio(str(audio_file))

# 3) Key phrases
key_phrases = lesson.get("key_phrases", [])
if key_phrases:
    st.subheader("3. Key phrases")
    for kp in key_phrases:
        phrase = kp.get("phrase", "")
        meaning = kp.get("meaning", "")
        examples = kp.get("examples", [])
        with st.expander(phrase):
            if meaning:
                st.write(meaning)
            if examples:
                st.markdown("**Examples:**")
                for ex in examples:
                    st.write(f"- {ex}")

# 4) Tasks
st.subheader("4. Practice")
render_gap_fill_tasks(lesson)
render_multiple_choice_tasks(lesson)

st.caption("More exercise types (reordering, matching, speaking) can be added later using the same JSON structure.")
