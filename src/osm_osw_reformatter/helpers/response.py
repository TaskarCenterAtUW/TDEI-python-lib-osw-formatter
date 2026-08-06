from dataclasses import dataclass
from typing import List, Union, Optional


@dataclass
class Response:
    status: bool
    generated_files: Optional[Union[str, List[str]]] = None
    error: str = None
