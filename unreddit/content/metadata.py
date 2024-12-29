from typing import List


class Button:
    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url


class Metadata:
    def get_buttons(self) -> List[Button]:
        return []
