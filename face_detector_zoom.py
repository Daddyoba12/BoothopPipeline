"""
face_detector_zoom.py
Detects faces in the first frame of a clip.
If no face (or face too small) -> applies 15% zoom to first 0.4s.
If a clear face exists -> re-encodes with vertical padding only.
Usage: python face_detector_zoom.py input.mp4 [--out output.mp4] [--zoom 1.15] [--dur 0.4]
"""
import argparse, subprocess, sys, os, tempfile
from pathlib import Path
import cv2

HAAR_XML = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"


def extract_first_frame(infile, out_jpg):
    subprocess.run(
        ["ffmpeg", "-y", "-i", infile, "-frames:v", "1", "-q:v", "2", out_jpg],
        capture_output=True
    )


def detect_faces(img_path):
    img = cv2.imread(img_path)
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    detector = cv2.CascadeClassifier(HAAR_XML)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
    return faces


def should_zoom(faces, img_w, img_h, face_area_threshold=0.06):
    if len(faces) == 0:
        return True, None
    areas = [(w * h, (x, y, w, h)) for (x, y, w, h) in faces]
    areas.sort(reverse=True)
    largest_area, bbox = areas[0]
    if largest_area < face_area_threshold * (img_w * img_h):
        return True, bbox
    return False, bbox


def make_zoomed_segment(infile, out_segment, zoom=1.15, dur=0.4):
    vf_zoom = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
        f"zoompan=z='min(zoom+0.01,{zoom})':d=1:s=1080x1920"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", infile, "-t", str(dur), "-vf", vf_zoom,
         "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", out_segment],
        capture_output=True
    )


def concat_segments(seg1, seg2, outfile):
    tf = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt")
    tf.write(f"file '{os.path.abspath(seg1)}'\n")
    tf.write(f"file '{os.path.abspath(seg2)}'\n")
    tf.close()
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", tf.name,
             "-c:v", "libx264", "-preset", "fast", "-crf", "20",
             "-c:a", "aac", "-ar", "48000", "-b:a", "128k", outfile],
            capture_output=True
        )
    finally:
        os.unlink(tf.name)


def process_clip(inp, out_path, zoom=1.15, dur=0.4):
    with tempfile.TemporaryDirectory() as td:
        first = os.path.join(td, "first.jpg")
        extract_first_frame(str(inp), first)

        if not os.path.exists(first):
            # Can't read frame — just re-encode with pad
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(inp),
                 "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
                 "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                 "-c:a", "aac", "-ar", "48000", "-b:a", "128k", str(out_path)],
                capture_output=True
            )
            return False

        img = cv2.imread(first)
        h, w = img.shape[:2]
        faces = detect_faces(first)
        do_zoom, _ = should_zoom(faces, w, h)

        if not do_zoom:
            # Good face — re-encode with padding only
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(inp),
                 "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
                 "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                 "-c:a", "aac", "-ar", "48000", "-b:a", "128k", str(out_path)],
                capture_output=True
            )
            return False

        # No face / small face — zoom first 0.4s
        seg1 = os.path.join(td, "zoom_seg.mp4")
        seg2 = os.path.join(td, "rem_seg.mp4")
        make_zoomed_segment(str(inp), seg1, zoom=zoom, dur=dur)
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(dur), "-i", str(inp),
             "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
             "-c:v", "libx264", "-preset", "fast", "-crf", "20",
             "-c:a", "aac", "-ar", "48000", "-b:a", "128k", seg2],
            capture_output=True
        )
        if os.path.exists(seg1) and os.path.exists(seg2):
            concat_segments(seg1, seg2, str(out_path))
            return True
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    ap.add_argument("--zoom", type=float, default=1.15)
    ap.add_argument("--dur",  type=float, default=0.4)
    args = ap.parse_args()
    inp = Path(args.input)
    if not inp.exists():
        print("Input not found:", inp)
        sys.exit(2)
    out = Path(args.out) if args.out else inp.with_name(inp.stem + "_zoomed.mp4")
    zoomed = process_clip(inp, out, zoom=args.zoom, dur=args.dur)
    print("Zoomed:", zoomed, "->", out)


if __name__ == "__main__":
    main()
