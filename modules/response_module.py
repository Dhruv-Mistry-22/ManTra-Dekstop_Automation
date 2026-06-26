# modules/response_module.py
def give_feedback(message):
    """Give formatted feedback to user with emoji"""
    if message:
        print(f"🤖 Mantra: {message}")
