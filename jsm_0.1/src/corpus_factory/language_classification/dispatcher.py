
from collections.abc import (
    Iterable,
    Iterator,
)
from concurrent.futures import (
    FIRST_COMPLETED,
    ProcessPoolExecutor,
    wait,
)

from src.corpus_factory.language_classification.result import (
    LanguageResult,
    LanguageTask,
)
from src.corpus_factory.language_classification.worker import (
    process_task,
)


def dispatch(
    tasks: Iterable[LanguageTask],
    *,
    workers: int = 4,
    max_pending: int | None = None,
) -> Iterator[LanguageResult]:
    if workers <= 0:
        raise ValueError(
            "workers must be positive"
        )

    if max_pending is None:
        max_pending = (
            workers * 2
        )

    if max_pending < workers:
        max_pending = workers

    iterator = iter(
        tasks
    )

    with ProcessPoolExecutor(
        max_workers=workers
    ) as executor:
        pending = set()

        while (
            len(pending)
            < max_pending
        ):
            try:
                task = next(
                    iterator
                )

            except StopIteration:
                break

            pending.add(
                executor.submit(
                    process_task,
                    task,
                )
            )

        while pending:
            done, pending = wait(
                pending,
                return_when=(
                    FIRST_COMPLETED
                ),
            )

            for future in done:
                yield future.result()

                try:
                    task = next(
                        iterator
                    )

                except StopIteration:
                    continue

                pending.add(
                    executor.submit(
                        process_task,
                        task,
                    )
                )
