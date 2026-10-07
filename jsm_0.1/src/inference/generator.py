import torch

from src.model.model import TinyLLM
from src.tokenization.tokenizer import Tokenizer


def is_valid_utf8_prefix(
    data: bytes,
) -> bool:
    try:
        data.decode(
            "utf-8",
            errors="strict",
        )

        return True

    except UnicodeDecodeError as error:
        # نسمح فقط إذا sequence صحيحة حتى الآن
        # لكنها تحتاج continuation byte في النهاية.
        return (
            error.reason == "unexpected end of data"
            and error.end == len(data)
        )


def is_complete_utf8(
    data: bytes,
) -> bool:
    try:
        data.decode(
            "utf-8",
            errors="strict",
        )

        return True

    except UnicodeDecodeError:
        return False


def apply_utf8_constraint(
    logits: torch.Tensor,
    tokenizer: Tokenizer,
    current_bytes: bytes,
) -> torch.Tensor:

    constrained = logits.clone()

    for token_id in range(
        tokenizer.vocab_size
    ):
        # BOS should never appear again.
        if token_id == tokenizer.bos_id:
            constrained[token_id] = float("-inf")
            continue

        # PAD is not a generation token.
        if token_id == tokenizer.pad_id:
            constrained[token_id] = float("-inf")
            continue

        # EOS only allowed when we are not
        # in the middle of a UTF-8 character.
        if token_id == tokenizer.eos_id:
            if not is_complete_utf8(
                current_bytes
            ):
                constrained[token_id] = float("-inf")

            continue

        candidate_bytes = (
            current_bytes
            + tokenizer.token_to_bytes(
                token_id
            )
        )

        if not is_valid_utf8_prefix(
            candidate_bytes
        ):
            constrained[token_id] = float("-inf")

    return constrained


@torch.no_grad()
def generate(
    model: TinyLLM,
    tokenizer: Tokenizer,
    prompt: str,
    max_new_tokens: int = 50,
    temperature: float = 1.0,
) -> str:

    model.eval()

    device = next(
        model.parameters()
    ).device

    token_ids = tokenizer.encode(
        prompt,
        add_bos=True,
        add_eos=False,
    )

    current_bytes = tokenizer.tokens_to_bytes(
        token_ids
    )

    for _ in range(max_new_tokens):
        context = token_ids[
            -model.config.context_length:
        ]

        x = torch.tensor(
            [context],
            dtype=torch.long,
            device=device,
        )

        logits = model(x)

        next_token_logits = (
            logits[0, -1]
        )

        next_token_logits = (
            apply_utf8_constraint(
                logits=next_token_logits,
                tokenizer=tokenizer,
                current_bytes=current_bytes,
            )
        )

        if temperature <= 0:
            next_token_id = int(
                torch.argmax(
                    next_token_logits
                )
            )

        else:
            probabilities = torch.softmax(
                next_token_logits
                / temperature,
                dim=-1,
            )

            next_token_id = int(
                torch.multinomial(
                    probabilities,
                    num_samples=1,
                )
            )

        token_ids.append(
            next_token_id
        )

        if next_token_id == tokenizer.eos_id:
            break

        current_bytes += (
            tokenizer.token_to_bytes(
                next_token_id
            )
        )

    # The token budget can run out in the middle of a
    # UTF-8 character. Drop the unfinished tail so the
    # strict decode below cannot fail.
    while not is_complete_utf8(
        tokenizer.tokens_to_bytes(token_ids)
    ):
        token_ids.pop()

    return tokenizer.decode(
        token_ids,
        skip_special_tokens=True,
        errors="strict",
    )