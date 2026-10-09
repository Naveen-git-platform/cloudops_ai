from typing import Annotated

from pydantic import ConfigDict, Field, StringConstraints

# Lowercase slug such as "payment-service".
ResourceId = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=1, max_length=64)]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

# Reject unknown fields so typos surface as validation errors.
STRICT_INPUT = ConfigDict(extra="forbid")
