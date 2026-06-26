import sys
import os

# Ensure project root is on sys.path when running from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.nlp_module import process_command
from modules.intent_module import detect_intent
from modules.execution_module import execute_task

def test_command(text):
    print(f"--- Testing: '{text}' ---")
    keywords = process_command(text)
    print(f"Keywords: {keywords}")
    
    intent = detect_intent(keywords)
    print(f"Intent: {intent}")
    
    result = execute_task(intent, keywords, text)
    print(f"Result: {result}")
    print()

test_command("open notepad")
test_command("open chrome")
test_command("open spotify")
test_command("open instagram")
test_command("create file test.txt")
test_command("volume up")
