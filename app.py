import io
import json
import mimetypes
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Union

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
MEDIA_FIELD_NAMES = ("video_panels", "cartoon_panels")


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


def normalise_media_item(item: Union[str, Dict[str, Any]], default_caption: str) -> Dict[str, str]:
    """Accept either a plain path string or a richer media dictionary from lesson JSON."""
    if isinstance(item, str):
        return {"path": item, "caption": default_caption, "description": ""}
    if isinstance(item, dict):
        path = str(item.get("path") or item.get("src") or "")
        caption = str(item.get("caption") or item.get("title") or default_caption)
        description = str(item.get("description") or "")
        return {"path": path, "caption": caption, "description": description}
    return {"path": "", "caption": default_caption, "description": ""}


def mime_for_path(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def render_download_button(asset_path: Path, label: str, key: str) -> None:
    if not asset_path.exists() or not asset_path.is_file():
        return
    with asset_path.open("rb") as f:
        st.download_button(
            label=label,
            data=f.read(),
            file_name=asset_path.name,
            mime=mime_for_path(asset_path),
            key=key,
            use_container_width=True,
        )


def collect_lesson_assets(lesson: Dict[str, Any]) -> List[Path]:
    """Return all existing video, image, and audio assets referenced by a lesson."""
    paths: List[Path] = []

    for field_name in MEDIA_FIELD_NAMES:
        for i, item in enumerate(lesson.get(field_name, []), start=1):
            media = normalise_media_item(item, f"{field_name} {i}")
            if media["path"]:
                path = resolve_asset_path(media["path"])
                if path.exists() and path.is_file():
                    paths.append(path)

    for turn in lesson.get("dialogue", []):
        audio_path = turn.get("audio")
        if audio_path:
            path = resolve_asset_path(audio_path)
            if path.exists() and path.is_file():
                paths.append(path)

    # Deduplicate while preserving order.
    seen = set()
    unique_paths = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique_paths.append(path)
    return unique_paths


def make_lesson_asset_zip(lesson: Dict[str, Any]) -> bytes:
    """Build a downloadable zip containing all existing media assets for one lesson."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in collect_lesson_assets(lesson):
            zf.write(path, arcname=str(path.relative_to(APP_DIR)))
        zf.writestr("transcript.txt", dialogue_transcript(lesson))
        zf.writestr("lesson.json", json.dumps({k: v for k, v in lesson.items() if k != "_path"}, indent=2, ensure_ascii=False))
    return buffer.getvalue()


# ---------- UI components ----------

def render_header(total_lessons: int) -> None:
    st.markdown(
        f"""
        <div class="hero-card">
            <h1 style="margin:0;">💬 Cartoon Conversations</h1>
            <p style="font-size:1.05rem; margin:0.45rem 0 0;">
                Practice real-life English through short dialogues, downloadable videos, key phrases, and instant-feedback activities.
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
    video_count = len(lesson.get("video_panels", []))

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Track", lesson.get("track", "—"))
    col2.metric("Level", lesson.get("level", "—"))
    col3.metric("Videos", video_count)
    col4.metric("Dialogue turns", dialogue_count)
    col5.metric("Practice items", task_count)

    st.markdown(
        f"""
        <div class="lesson-card">
            <strong>Lesson file:</strong> <code>{lesson.get('_path', 'unknown')}</code><br>
            <span class="small-muted">Use the tabs below to watch, download, practise, and role-play.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_video_panels(lesson: Dict[str, Any]) -> None:
    videos = lesson.get("video_panels", [])
    if not videos:
        st.info("No videos are listed for this lesson yet. Add MP4 files and reference them with `video_panels` in the lesson JSON.")
        return

    st.markdown("#### Watch the lesson videos")
    columns = st.columns(min(3, len(videos)))
    for index, item in enumerate(videos):
        media = normalise_media_item(item, f"Video {index + 1}")
        video_path = resolve_asset_path(media["path"])
        with columns[index % len(columns)]:
            if video_path.exists():
                st.video(str(video_path))
                st.caption(media["caption"])
                if media["description"]:
                    st.write(media["description"])
                render_download_button(video_path, "Download video", f"download_video_{lesson['lesson_id']}_{index}")
            else:
                st.markdown(
                    f"""
                    <div class="media-missing">
                        🎬 <strong>{media['caption']}</strong><br>
                        Add video asset:<br><code>{media['path']}</code>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_cartoon_panels(lesson: Dict[str, Any]) -> None:
    panels = lesson.get("cartoon_panels", [])
    if not panels:
        st.info("No cartoon panels are listed for this lesson yet.")
        return

    st.markdown("#### Optional image panels")
    columns = st.columns(min(3, len(panels)))
    for index, item in enumerate(panels):
        media = normalise_media_item(item, f"Panel {index + 1}")
        panel_path = resolve_asset_path(media["path"])
        with columns[index % len(columns)]:
            if panel_path.exists():
                st.image(str(panel_path), caption=media["caption"], use_container_width=True)
                render_download_button(panel_path, "Download image", f"download_image_{lesson['lesson_id']}_{index}")
            else:
                st.markdown(
                    f"""
                    <div class="media-missing">
                        🖼️ <strong>{media['caption']}</strong><br>
                        Add image asset:<br><code>{media['path']}</code>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_story_media(lesson: Dict[str, Any]) -> None:
    render_video_panels(lesson)
    st.divider()
    render_cartoon_panels(lesson)


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
                render_download_button(audio_file, "Download audio", f"download_audio_{lesson['lesson_id']}_{i}")
            else:
                st.caption(f"Audio not found: `{audio_path}`")

    with st.expander("Copyable transcript"):
        st.code(dialogue_transcript(lesson), language="text")
        st.download_button(
            label="Download transcript",
            data=dialogue_transcript(lesson).encode("utf-8"),
            file_name=f"{lesson.get('lesson_id', 'lesson')}_transcript.txt",
            mime="text/plain",
            use_container_width=True,
        )


def render_downloads(lesson: Dict[str, Any]) -> None:
    assets = collect_lesson_assets(lesson)
    st.markdown("#### Lesson downloads")

    if assets:
        st.write("Download individual media files below, or download the whole lesson pack as one zip.")
        for path in assets:
            st.write(f"• `{path.relative_to(APP_DIR)}`")
        st.download_button(
            label="Download full lesson pack (.zip)",
            data=make_lesson_asset_zip(lesson),
            file_name=f"{lesson.get('lesson_id', 'lesson')}_media_pack.zip",
            mime="application/zip",
            use_container_width=True,
        )
    else:
        st.info("No downloadable media files exist yet for this lesson. Once you add MP4, PNG/JPG, or MP3 files, they will appear here automatically.")

    st.divider()
    st.markdown("#### Lesson data")
    lesson_json = json.dumps({k: v for k, v in lesson.items() if k != "_path"}, indent=2, ensure_ascii=False)
    st.download_button(
        label="Download lesson JSON",
        data=lesson_json.encode("utf-8"),
        file_name=f"{lesson.get('lesson_id', 'lesson')}.json",
        mime="application/json",
        use_container_width=True,
    )
    st.download_button(
        label="Download transcript",
        data=dialogue_transcript(lesson).encode("utf-8"),
        file_name=f"{lesson.get('lesson_id', 'lesson')}_transcript.txt",
        mime="text/plain",
        use_container_width=True,
    )


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
    st.sidebar.caption("Tip: add MP4 files under `videos/` and reference them with `video_panels` in your lesson JSON.")
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

story_tab, dialogue_tab, phrases_tab, practice_tab, roleplay_tab, downloads_tab = st.tabs(
    ["1 · Videos", "2 · Dialogue", "3 · Key phrases", "4 · Practice", "5 · Role-play", "6 · Downloads"]
)

with story_tab:
    render_story_media(lesson)

with dialogue_tab:
    render_dialogue(lesson)

with phrases_tab:
    render_key_phrases(lesson)

with practice_tab:
    render_practice(lesson)

with roleplay_tab:
    render_role_play(lesson)

with downloads_tab:
    render_downloads(lesson)

st.caption(
    "Enhanced video version: MP4 lesson videos, individual downloads, full lesson media packs, transcript downloads, responsive layout, validated loading, role-play mode, and progress scoring."
)
