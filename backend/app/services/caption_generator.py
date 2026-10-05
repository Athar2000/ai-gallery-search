"""
Caption + tag generation (Phase 7, spec section 11).

This is deliberately NOT a vision-language captioning model (BLIP-2 etc.
would need the same blocked Hugging Face weight downloads as CLIP/ArcFace).
Instead it builds a simple, honest sentence and a tag list directly from
what YOLO and the face pipeline actually detected in this photo — real
information, just not a natural-language model's phrasing of it. A real ML
caption ("a man in a red jacket standing near a car outside a building")
would be materially richer; this produces something more like "Contains 2
people (Priya) and a car." It's a legitimate, useful default that's honest
about being rule-based, and a real captioning model is a reasonable future
upgrade behind the same kind of swappable interface used elsewhere.
"""
from collections import Counter


def generate_caption_and_tags(object_names: list[str], person_names: list[str]) -> tuple[str, list[str]]:
    """
    object_names: one entry per detected object instance (duplicates
        expected, e.g. ["person", "person", "car"] for a photo with 2 people).
    person_names: names of any *named* people detected in this photo
        (unnamed people are already counted in object_names' "person" entries).
    """
    tags = sorted(set(object_names) | {n.lower() for n in person_names})

    if not object_names and not person_names:
        return "", tags

    counts = Counter(object_names)
    parts: list[str] = []
    for name, count in counts.most_common():
        parts.append(f"{count} {name}s" if count > 1 else f"a {name}")

    sentence = "Contains " + ", ".join(parts) if parts else "Contains"
    if person_names:
        sentence += f" ({', '.join(person_names)})"
    return sentence + ".", tags
