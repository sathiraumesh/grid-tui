"""The base of the models that read the API's JSON."""

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class ApiModel(BaseModel):
    """A model read from the API's JSON: frozen, and forgiving about nulls.

    The API sometimes sends null for a value it doesn't have. Every null is
    dropped before reading, so the field gets its default instead of failing
    the whole answer. Fields the model doesn't list are ignored, and a number
    sent where text is expected (e.g. a port 12) is read as text ('12').
    """

    model_config = ConfigDict(
        frozen=True,  # can't be changed once made
        coerce_numbers_to_str=True,  # 12 → '12' for a text field
    )

    @model_validator(mode='before')
    @classmethod
    def _drop_nulls(cls, data: Any) -> Any:
        """{'model': None, 'uid': 'x'} → {'uid': 'x'}: null fields use defaults."""
        if isinstance(data, dict):
            return {key: value for key, value in data.items() if value is not None}
        return data
