# Cartoon Conversations

A Streamlit app for short, media-rich English conversation lessons. Lessons are stored as JSON files and can include MP4 videos, image panels, audio files, key phrases, practice tasks, transcripts, and downloadable media packs.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Lesson structure

Add lesson JSON files anywhere under:

```text
data/lessons/
```

The app reads them automatically.

Minimum required fields:

```json
{
  "track": "General",
  "level": "A1",
  "lesson_id": "a1_directions_01",
  "title": "Asking for Directions",
  "dialogue": []
}
```

## Adding real videos

Put MP4 files under a clear folder such as:

```text
videos/general/A1/
```

Then reference them in the lesson JSON:

```json
"video_panels": [
  {
    "path": "videos/general/A1/directions_panel1.mp4",
    "caption": "Panel 1: Asking for the metro station",
    "description": "The tourist politely stops a local person and asks for directions."
  }
]
```

The app will show the videos in the first tab and create download buttons automatically.

## Adding images

Put image files under a folder such as:

```text
images/general/A1/
```

Then reference them in the lesson JSON:

```json
"cartoon_panels": [
  "images/general/A1/dir1.png",
  "images/general/A1/dir2.png",
  "images/general/A1/dir3.png"
]
```

## Downloads

The app includes:

- download buttons for individual MP4, PNG/JPG, and MP3 files
- a full lesson media-pack zip download
- transcript download
- lesson JSON download

## Included sample media

The `Asking for Directions` lesson includes three sample MP4 video panels and three PNG image panels so the video/download workflow works immediately after deployment.
