from aiogram.fsm.state import State, StatesGroup


class TeacherHomeworkStates(StatesGroup):
    waiting_homework_topic = State()


class StudentHomeworkCheckStates(StatesGroup):
    waiting_solution_text = State()