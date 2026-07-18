from aiogram.fsm.state import State, StatesGroup


class TeacherHomeworkStates(StatesGroup):
    waiting_homework_topic = State()


class TeacherFamilyLinkStates(StatesGroup):
    waiting_student_id = State()


class StudentHomeworkCheckStates(StatesGroup):
    waiting_solution_text = State()


class ParentSubmissionStates(StatesGroup):
    waiting_homework_photo = State()


class ParentFamilyLinkStates(StatesGroup):
    waiting_link_code = State()
