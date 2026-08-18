"""A tiny frozen reader for evaluator tests and smoke runs."""

import re
from dataclasses import dataclass

from rsicontext.policy import ContextPack

from .core import ReaderOutput

_ANSWER = re.compile(r"(?:^|\n)ANSWER:\s*([^\n]+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ToyFrozenReader:
    """Extract the first explicit ANSWER marker in assembled order."""

    abstention: str = ""

    def read(self, query: str, context: ContextPack) -> ReaderOutput:
        answer = self.abstention
        for text in context.ordered_text():
            match = _ANSWER.search(text)
            if match:
                answer = match.group(1).strip()
                break
        return ReaderOutput(
            answer=answer,
            input_tokens=len(query.split()) + context.token_count,
            output_tokens=len(answer.split()),
        )
