"""Extract viral hooks from YouTube trending titles."""
HOOK_TRIGGERS = ["how", "why", "stop", "never", "always", "this is", "secret",
                  "truth", "real", "surprising", "shocking", "watch", "must",
                  "you need", "everyone", "nobody", "your"]

def extract_hooks(youtube_data):
    hooks = []
    for item in youtube_data:
        title = item.get("title", "").lower()
        if any(w in title for w in HOOK_TRIGGERS):
            hooks.append(item.get("title", ""))
    return hooks[:10]

def boothop_hook_ideas(google_trends):
    """Generate simple hook ideas wrapping BootHop into today's trends."""
    ideas = []
    for trend in google_trends[:5]:
        ideas.append(f"POV: {trend} is happening and your package still hasn't arrived. BootHop fixes that.")
        ideas.append(f"Nobody is talking about how {trend} is affecting deliveries. We are. BootHop.")
    return ideas
