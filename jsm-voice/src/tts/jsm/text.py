"""Arabic text to symbol ids, with no external phonemizer.

Dialect is written without vowel marks, so the model reads letters and learns the
pronunciation from the recorded speaker.
"""

import re
import unicodedata

PAD, UNKNOWN = "_", "�"
LETTERS = "ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىيپچڤگ"
MARKS = "ًٌٍَُِّْ"
DIGITS = "0123456789"
PUNCTUATION = " ،.؟!؛:-"
SYMBOLS = (PAD, UNKNOWN, *LETTERS, *MARKS, *DIGITS, *PUNCTUATION)
_IDS = {symbol: index for index, symbol in enumerate(SYMBOLS)}

_REPLACE = str.maketrans({
    ",": "،", "?": "؟", ";": "؛", "ـ": None, "‏": None, "‎": None,
    "…": ".", "\n": ".", "\t": " ", "«": None, "»": None, '"': None, "'": None, "(": "،", ")": "،",
    **{chr(0x0660 + value): str(value) for value in range(10)},
    **{chr(0x06F0 + value): str(value) for value in range(10)},
    "ک": "ك", "ی": "ي", "ٱ": "ا",
})


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(_REPLACE)
    # A stretched word such as "هلااااا" is read as one long vowel, not five letters.
    text = re.sub(r"(.)\1{2,}", r"\1\1", text)
    return re.sub(r"\s+", " ", text).strip()


def encode(text: str) -> list[int]:
    ids = [_IDS.get(symbol, _IDS[UNKNOWN]) for symbol in normalize(text)]
    if not ids:
        raise ValueError("Text has nothing to speak.")
    return ids
