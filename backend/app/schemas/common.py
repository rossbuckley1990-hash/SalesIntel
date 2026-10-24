from pydantic import BaseModel, ConfigDict


class MisiSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

