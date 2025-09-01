class UserChatHistory:
    def __init__(self):
        # Each item will be stored as a tuple: (question, answer)
        self.history = []

    def add_entry(self, question: str, answer: str):
        """Add a question and answer pair to the history."""
        self.history.append((question, answer))

    def get_all_history(self):
        """Return the full chat history."""
        return self.history

    def get_last(self):
        """Return the most recent question-answer pair, or None if empty."""
        return self.history[-1] if self.history else None

    def clear_history(self):
        """Clear all stored chat history."""
        self.history.clear()
