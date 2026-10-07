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


def apply_repetition_penalty(
    logits: torch.Tensor,
    token_ids: list[int],
    penalty: float,
) -> torch.Tensor:
    if penalty == 1.0 or not token_ids:
        return logits

    penalized = logits.clone()

    seen = torch.tensor(
        sorted(set(token_ids)),
        dtype=torch.long,
        device=logits.device,
    )

    values = penalized[seen]

    # Dividing a positive logit and multiplying a
    # negative one both make the token less likely.
    penalized[seen] = torch.where(
        values > 0,
        values / penalty,
        values * penalty,
    )

    return penalized


def apply_reply_constraint(
    logits: torch.Tensor,
    tokenizer: Tokenizer,
    newline_token_ids: list[int],
    first_step: bool,
    reply_started: bool,
) -> torch.Tensor:
    constrained = logits.clone()

    if first_step:
        # The reply must open a new line.
        allowed = torch.full_like(
            constrained,
            float("-inf"),
        )

        allowed[newline_token_ids] = (
            constrained[newline_token_ids]
        )

        return allowed

    if not reply_started:
        # No empty replies: the line needs some text
        # before it is allowed to end.
        constrained[newline_token_ids] = float("-inf")
        constrained[tokenizer.eos_id] = float("-inf")

    return constrained


@torch.no_grad()
def generate(
    model: TinyLLM,
    tokenizer: Tokenizer,
    prompt: str,
    max_new_tokens: int = 50,
    temperature: float = 1.0,
    repetition_penalty: float = 1.3,
    reply: bool = False,
) -> str:
    """
    With reply=True the model answers on a new line and
    stops at the end of that line, which is how turns are
    written in the conversation training data.
    """

    if repetition_penalty < 1.0:
        raise ValueError(
            "repetition_penalty must be "
            "at least 1.0"
        )

    model.eval()

    device = next(
        model.parameters()
    ).device

    # Whitespace belongs to the start of the next token,
    # so a trailing space would be encoded as a token the
    # model never saw at the end of a word.
    token_ids = tokenizer.encode(
        prompt.rstrip(),
        add_bos=True,
        add_eos=False,
    )

    current_bytes = tokenizer.tokens_to_bytes(
        token_ids
    )

    newline_token_ids = [
        token_id
        for token_id in range(
            tokenizer.vocab_size
        )
        if b"\n" in tokenizer.token_to_bytes(
            token_id
        )
    ]

    reply_bytes = b""

    for step in range(max_new_tokens):
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

        if reply:
            next_token_logits = (
                apply_reply_constraint(
                    logits=next_token_logits,
                    tokenizer=tokenizer,
                    newline_token_ids=newline_token_ids,
                    first_step=step == 0,
                    reply_started=bool(
                        reply_bytes.strip()
                    ),
                )
            )

        # Applied to the tokens the model can currently
        # see, so a loop in the prompt is not continued.
        next_token_logits = (
            apply_repetition_penalty(
                logits=next_token_logits,
                token_ids=context,
                penalty=repetition_penalty,
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

        next_bytes = tokenizer.token_to_bytes(
            next_token_id
        )

        # A second newline starts the other speaker's
        # turn, so the reply is complete.
        if (
            reply
            and step > 0
            and b"\n" in next_bytes
        ):
            token_ids.pop()
            break

        current_bytes += next_bytes
        reply_bytes += next_bytes

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