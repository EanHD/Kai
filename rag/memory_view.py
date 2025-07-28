import json

def load_memory(file_name):
    try:
        with open(file_name, "r") as f:
            conversation_history = json.load(f)
            return conversation_history
    except FileNotFoundError:
        conversation_history = []
        return conversation_history
        
def save_memory(conversation_history, file_name):
    with open(file_name, "w") as f:
        json.dump(conversation_history, f, indent=4)