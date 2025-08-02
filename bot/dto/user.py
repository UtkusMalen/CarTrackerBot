from typing import Optional
from pydantic import BaseModel

class UserDTO(BaseModel):
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    balance_nuts: int
    active_car_id: Optional[int]
    mileage_reminder_period: int
    referrer_id: Optional[int]