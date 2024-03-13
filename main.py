from aiogram import executor
from project import *

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
