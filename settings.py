from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_URL: str = ""
    DB_NAME: str = ""
    SECRET_KEY: str = ""

    @property
    def connection_string(self):
        return f"mongodb+srv://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_URL}/?retryWrites=true&w=majority"
