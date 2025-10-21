"""
FSM States для диалогов бота
"""

from aiogram.fsm.state import State, StatesGroup


class AddChannelStates(StatesGroup):
    """Состояния для добавления канала."""
    waiting_for_username = State()


class AddChatStates(StatesGroup):
    """Состояния для добавления чата."""
    waiting_for_identifier = State()
