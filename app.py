import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import streamlit as st

# ---------- Configuration ----------

APP_DIR = Path(__file__).parent
LESSON_DIR = APP_DIR / "data" / "lessons"

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

REQUIRED_LESSON_FIELDS = {"track", "level", "lesson_id", "title", "dialogue"}


# ---------- Page setup ----------

st.set_page_config(
    page_title="Cartoon Conversations",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main .block-container {padding-top: 2rem; padding-bottom: 3rem;}
    .hero-card {
        padding: 1.25rem 1.4rem;
        border-radius: 1.2rem;
        border: 1px solid rgba(120, 120, 120, 0.18);
        background: linear-gradient(135deg, rgba(255, 244, 219, 0.75), rgba(228, 241, 255, 0.75));
        margin-bottom: 1rem;
    }
    .lesson-card {
        padding: 1rem;
        border-radius: 1rem;
        border: 1px solid rgba(120, 120, 120, 0.18);
        background: rgba(250, 250, 250, 0.65);
        margin-bottom: 0.75rem;
    }
    .dialogue-turn {
        padding: 0.8rem 1rem;
        border-radius: 0.9rem;
        border: 1px solid rgba(120, 120, 120, 0.15);
        margin: 0.35rem 0;
        background: rgba(255, 255, 255, 0.74);
    }
    .speaker-chip {
        display: inline-block;
        font-weight: 700;
        padding: 0.15rem 0.55rem;
        border-radius: 999px;
        background: rgba(49, 130, 206, 0.12);
        margin-right: 0.35rem;
    }
    .media-missing {
        padding: 0.8rem;
        border-radius: 0.8rem;
        border: 1px dashed rgba(120, 120, 120, 0.35);
        background: rgba(250, 250, 250, 0.55);
        font-size: 0.92rem;
    }
    .small-muted {color: #6b7280; font-size: 0.9rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Helper functions ----------

@st.cache_data(show_spinner=False)
def load_lessons() -> Tuple[List[Dict[str, Any]], List[str]]:
    """Load all lesson JSON files and return valid lessons plus readable error messages."""
    lessons: List[Dict[str, Any]] = []
    errors: List[str] = []

    for path in sorted(LESSON_DIR.glob("**/*.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                lesson = json.load(f)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.relative_to(APP_DIR)}: invalid JSON ({exc.msg})")
            continue
        except OSError as exc:
            errors.append(f"{path.relative_to(APP_DIR)}: could not read file ({exc})")
            continue

        missing = REQUIRED_LESSON_FIELDS - set(lesson)
        if missing:
            errors.append(
                f"{path.relative_to(APP_DIR)}: missing required field(s): {', '.join(sorted(missing))}"
            )
            continue

        lesson["_path"] = str(path.relative_to(APP_DIR))
        lessons.append(lesson)

    return lessons, errors


def normalize_level(level: str) -> str:
    return str(level).strip()


def level_sort_key(level: str) -> Tuple[int, str]:
    level = normalize_level(level)
    return CEFR_ORDER.get(level, 999), level


def get_sorted_levels(lessons: Iterable[Dict[str, Any]], track: str) -> List[str]:
    levels = {normalize_level(l["level"]) for l in lessons if l.get("track") == track}
    return sorted(levels, key=level_sort_key)


def resolve_asset_path(asset_path: str) -> Path:
    """Resolve media paths relative to the app directory."""
    return APP_DIR / asset_path


def clean_answer(text: str) -> str:
    """Normalize learner answers while allowing small punctuation/case differences."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s']", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def dialogue_transcript(lesson: Dict[str, Any]) -> str:
    lines = []
    for turn in lesson.get("dialogue", []):
        speaker = turn.get("speaker", "Speaker")
        text = turn.get("text", "")
        lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def count_tasks(lesson: Dict[str, Any]) -> int:
    tasks = lesson.get("tasks", {})
    return len(tasks.get("gap_fill", [])) + len(tasks.get("multiple_choice", []))


def reset_lesson_inputs(lesson_id: str) -> None:
    keys_to_clear = [k for k in st.session_state if k.startswith((f"gap_{lesson_id}_", f"mc_{lesson_id}_"))]
    for key in keys_to_clear:
        del st.session_state[key]


# ---------- UI components ----------

def render_header(total_lessons: int) -> None:
    st.markdown(
        f"""
        <div class="hero-card">
            <h1 style="margin:0;">💬 Cartoon Conversations</h1>
            <p style="font-size:1.05rem; margin:0.45rem 0 0;">
                Practice real-life English through short dialogues, key phrases, and instant-feedback activities.
            </p>
            <p class="small-muted" style="margin:0.5rem 0 0;">
                {total_lessons} lesson{'s' if total_lessons != 1 else ''} loaded from the lesson bank.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_lesson_overview(lesson: Dict[str, Any]) -> None:
    dialogue_count = len(lesson.get("dialogue", []))
    phrase_count = len(lesson.get("key_phrases", []))
    task_count = count_tasks(lesson)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Track", lesson.get("track", "—"))
    col2.metric("Level", lesson.get("level", "—"))
    col3.metric("Dialogue turns", dialogue_count)
    col4.metric("Practice items", task_count)

    st.markdown(
        f"""
        <div class="lesson-card">
            <strong>Lesson file:</strong> <code>{lesson.get('_path', 'unknown')}</code><br>
            <span class="small-muted">Use the tabs below to move from noticing → guided practice → role-play.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_cartoon_panels(lesson: Dict[str, Any]) -> None:
    panels = lesson.get("cartoon_panels", [])
    if not panels:
        st.info("No cartoon panels are listed for this lesson yet.")
        return

    columns = st.columns(min(3, len(panels)))
    for index, img_path in enumerate(panels):
        panel_path = resolve_asset_path(img_path)
        with columns[index % len(columns)]:
            if panel_path.exists():
                st.image(str(panel_path), caption=f"Panel {index + 1}", use_container_width=True)
            else:
                st.markdown(
                    f"""
                    <div class="media-missing">
                        🖼️ <strong>Panel {index + 1}</strong><br>
                        Add image asset:<br><code>{img_path}</code>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_dialogue(lesson: Dict[str, Any]) -> None:
    dialogue = lesson.get("dialogue", [])
    if not dialogue:
        st.warning("This lesson has no dialogue yet.")
        return

    for i, turn in enumerate(dialogue, start=1):
        speaker = turn.get("speaker", f"Speaker {i}")
        text = turn.get("text", "")
        st.markdown(
            f"""
            <div class="dialogue-turn">
                <span class="speaker-chip">{speaker}</span>{text}
            </div>
            """,
            unsafe_allow_html=True,
        )

        audio_path = turn.get("audio")
        if audio_path:
            audio_file = resolve_asset_path(audio_path)
            if audio_file.exists():
                st.audio(str(audio_file))

    with st.expander("Copyable transcript"):
        st.code(dialogue_transcript(lesson), language="text")


def render_key_phrases(lesson: Dict[str, Any]) -> None:
    key_phrases = lesson.get("key_phrases", [])
    if not key_phrases:
        st.info("No key phrases are listed for this lesson yet.")
        return

    for kp in key_phrases:
        phrase = kp.get("phrase", "Untitled phrase")
        meaning = kp.get("meaning", "")
        examples = kp.get("examples", [])
        with st.expander(f"✨ {phrase}", expanded=False):
            if meaning:
                st.write(meaning)
            if examples:
                st.markdown("**Examples**")
                for ex in examples:
                    st.write(f"• {ex}")


def render_gap_fill_tasks(lesson: Dict[str, Any]) -> Tuple[int, int]:
    gap_tasks = lesson.get("tasks", {}).get("gap_fill", [])
    attempted = 0
    correct = 0

    if not gap_tasks:
        return attempted, correct

    st.markdown("#### Gap-fill practice")
    for i, task in enumerate(gap_tasks, start=1):
        prompt = task.get("prompt", "")
        answer = task.get("answer", "")
        key = f"gap_{lesson['lesson_id']}_{i}"

        user_answer = st.text_input(f"{i}. {prompt}", key=key, placeholder="Type the missing word or phrase")
        if user_answer.strip():
            attempted += 1
            if clean_answer(user_answer) == clean_answer(answer):
                correct += 1
                st.success("Correct — nice one.")
            else:
                st.error(f"Almost. Correct answer: **{answer}**")

    return attempted, correct


def render_multiple_choice_tasks(lesson: Dict[str, Any]) -> Tuple[int, int]:
    mc_tasks = lesson.get("tasks", {}).get("multiple_choice", [])
    attempted = 0
    correct = 0

    if not mc_tasks:
        return attempted, correct

    st.markdown("#### Multiple choice")
    for i, task in enumerate(mc_tasks, start=1):
        question = task.get("question", "")
        options = task.get("options", [])
        answer = task.get("answer", "")
        key = f"mc_{lesson['lesson_id']}_{i}"

        st.write(f"**{i}. {question}**")
        choice = st.radio(
            "Choose one:",
            options,
            key=key,
            index=None,
            label_visibility="collapsed",
        )
        if choice is not None:
            attempted += 1
            if choice == answer:
                correct += 1
                st.success("Correct — good choice.")
            else:
                st.error(f"Not quite. Correct answer: **{answer}**")

    return attempted, correct


def render_practice(lesson: Dict[str, Any]) -> None:
    total_tasks = count_tasks(lesson)
    if total_tasks == 0:
        st.info("No practice tasks are available for this lesson yet.")
        return

    left, right = st.columns([3, 1])
    with right:
        if st.button("Reset answers", use_container_width=True):
            reset_lesson_inputs(lesson["lesson_id"])
            st.rerun()

    gap_attempted, gap_correct = render_gap_fill_tasks(lesson)
    mc_attempted, mc_correct = render_multiple_choice_tasks(lesson)

    attempted = gap_attempted + mc_attempted
    correct = gap_correct + mc_correct

    st.divider()
    st.markdown("#### Your progress")
    st.progress(correct / total_tasks if total_tasks else 0)
    st.write(f"**Score:** {correct}/{total_tasks} correct · **Attempted:** {attempted}/{total_tasks}")

    if attempted == total_tasks:
        if correct == total_tasks:
            st.balloons()
            st.success("Excellent — you completed the lesson with a perfect score.")
        else:
            st.info("Good effort. Review the highlighted answers, then try again.")


def render_role_play(lesson: Dict[str, Any]) -> None:
    dialogue = lesson.get("dialogue", [])
    speakers = sorted({turn.get("speaker", "Speaker") for turn in dialogue})

    if len(speakers) < 2:
        st.info("Role-play works best with at least two speakers in the dialogue.")
        return

    st.write("Choose a role, hide those lines, and practise responding aloud or with a partner.")
    role = st.selectbox("Practise as", speakers)

    for turn in dialogue:
        speaker = turn.get("speaker", "Speaker")
        text = turn.get("text", "")
        if speaker == role:
            st.markdown(f"**{speaker}:** ▢ ▢ ▢ _Your turn — say the line from memory._")
        else:
            st.markdown(f"**{speaker}:** {text}")

    with st.expander("Show full script"):
        st.code(dialogue_transcript(lesson), language="text")


def render_sidebar(lessons: List[Dict[str, Any]]) -> Dict[str, Any]:
    st.sidebar.title("Lesson browser")

    tracks = sorted({l["track"] for l in lessons})
    track = st.sidebar.selectbox("Track", tracks)

    levels = get_sorted_levels(lessons, track)
    level = st.sidebar.selectbox("Level", levels)

    filtered = sorted(
        [l for l in lessons if l["track"] == track and normalize_level(l["level"]) == level],
        key=lambda lesson: lesson["title"],
    )

    query = st.sidebar.text_input("Search lessons", placeholder="e.g., café, patient, lawyer")
    if query.strip():
        q = query.strip().lower()
        filtered = [
            lesson
            for lesson in filtered
            if q in lesson.get("title", "").lower()
            or q in dialogue_transcript(lesson).lower()
            or any(q in kp.get("phrase", "").lower() for kp in lesson.get("key_phrases", []))
        ]

    if not filtered:
        st.sidebar.warning("No lessons match your filters.")
        st.stop()

    lesson_titles = [l["title"] for l in filtered]
    selected_title = st.sidebar.selectbox("Lesson", lesson_titles)
    lesson = next(l for l in filtered if l["title"] == selected_title)

    st.sidebar.divider()
    st.sidebar.caption("Tip: add more JSON lessons under `data/lessons/` and they will appear automatically.")
    return lesson


# ---------- App ----------

lessons, load_errors = load_lessons()

if not lessons:
    st.error("No valid lessons found. Add JSON files in `data/lessons/`.")
    if load_errors:
        with st.expander("Loading errors"):
            for error in load_errors:
                st.write(f"• {error}")
    st.stop()

lesson = render_sidebar(lessons)
render_header(total_lessons=len(lessons))

if load_errors:
    with st.expander("Some lesson files need attention"):
        for error in load_errors:
            st.warning(error)

st.header(lesson["title"])
render_lesson_overview(lesson)

story_tab, dialogue_tab, phrases_tab, practice_tab, roleplay_tab = st.tabs(
    ["1 · Cartoon", "2 · Dialogue", "3 · Key phrases", "4 · Practice", "5 · Role-play"]
)

with story_tab:
    render_cartoon_panels(lesson)

with dialogue_tab:
    render_dialogue(lesson)

with phrases_tab:
    render_key_phrases(lesson)

with practice_tab:
    render_practice(lesson)

with roleplay_tab:
    render_role_play(lesson)

st.caption(
    "Enhanced version: responsive layout, lesson search, validated loading, media placeholders, copyable transcripts, role-play mode, progress scoring, and reset support."
)
