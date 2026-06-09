# Cartoon Conversations

A Streamlit app for practising real-life English through short cartoon-style dialogues, key phrases, and instant-feedback exercises.

## What is enhanced in this version

- Responsive Streamlit layout with tabs for cartoon panels, dialogue, phrases, practice, and role-play.
- Sidebar lesson browser with track, level, and lesson search.
- Safer lesson loading with JSON validation and readable error messages.
- Asset handling relative to the app folder, so the app is easier to run from different locations.
- Clear placeholders when image/audio files are listed in JSON but not yet included in the project.
- Copyable dialogue transcripts.
- Role-play mode that hides one speaker's lines for oral practice.
- Practice scoring, progress bar, answer reset, and more forgiving answer checking for punctuation/case.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Add lessons

Add `.json` files under `data/lessons/`. The app expects each lesson to include at least:

```json
{
  "track": "General",
  "level": "A1",
  "lesson_id": "unique_lesson_id",
  "title": "Lesson title",
  "dialogue": [
    {"speaker": "Speaker 1", "text": "Hello!"}
  ]
}
```

Optional fields include `cartoon_panels`, `audio`, `key_phrases`, and `tasks`.

## Media assets

The current lesson files refer to image and audio paths such as:

- `images/general/A1/cafe1.png`
- `audio/general/A1/cafe_line1.mp3`

Those media files are not included in the original zip. Add them under matching folders inside the app directory to make images and audio appear.
