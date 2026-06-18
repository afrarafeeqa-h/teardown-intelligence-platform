from pydantic import BaseModel

class SendOTPRequest(BaseModel):
    email: str

class VerifyOTPRequest(BaseModel):
    email: str
    otp: str

class AuthResponse(BaseModel):
    message: str
    role: str
    token: str
